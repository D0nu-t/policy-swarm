"""
policyswarm.gui.runner
======================
Runs experiment batches as child processes and fans their output out to
subscribers.

A run is ``python -u -m policyswarm.cli --spec <run_dir>/run.json``. The child
prints prose and ``##EVENT##`` progress lines (see
``policyswarm.experiments.events``); this module turns each stdout line into
a message and delivers it to every subscriber of that run:

    {"kind": "event",  "event": {...}}        a parsed progress event
    {"kind": "log",    "line": "..."}         any other output line
    {"kind": "status", "status": "...", "returncode": int | None}

Simulations are CPU-bound, so only one run may be active at a time.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from ..config import RunSpec
from ..experiments.events import parse_event_line

RUNNING, SUCCEEDED, FAILED, CANCELLED = "running", "succeeded", "failed", "cancelled"
MAX_LOG_LINES = 5000
_PACKAGE_PARENT = str(Path(__file__).resolve().parents[2])


class RunBusyError(RuntimeError):
    """A run is already in progress."""


@dataclass
class Run:
    """One experiment batch and everything it has reported so far."""
    id         : str
    spec       : RunSpec
    directory  : Path
    status     : str = RUNNING
    returncode : Optional[int] = None
    started    : str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    history    : List[dict] = field(default_factory=list)
    _subscribers : List[asyncio.Queue] = field(default_factory=list, repr=False)
    _process     : Optional[subprocess.Popen] = field(default=None, repr=False)
    _log_lines   : int = field(default=0, repr=False)

    @property
    def finished(self) -> bool:
        """True once the child has exited and the final status message is published.

        Not the same as ``status != RUNNING``: a cancelled run is marked
        ``cancelled`` at once, but it is only finished when its process has
        actually gone. Until then it still blocks new runs, and open streams
        keep waiting for the final message.
        """
        return self.returncode is not None

    def summary(self) -> dict:
        return {"id": self.id, "status": self.status, "returncode": self.returncode,
                "started": self.started, "spec": self.spec.to_dict()}

    def _publish(self, message: dict) -> None:
        """Record a message and deliver it to subscribers. Event-loop thread only."""
        if message["kind"] == "log":
            self._log_lines += 1
            if self._log_lines > MAX_LOG_LINES:
                return
        self.history.append(message)
        for queue in self._subscribers:
            queue.put_nowait(message)


class RunManager:
    """Starts, tracks and cancels runs under a single root directory.

    Parameters
    ----------
    runs_root : Path
        Every run writes to ``runs_root/<run id>/``. Callers cannot choose an
        output location outside it.
    python : str
        Interpreter for the child process. Default: this interpreter.
    """

    def __init__(self, runs_root: Path, python: str = sys.executable):
        self.runs_root = Path(runs_root).resolve()
        self.python    = python
        self.runs: Dict[str, Run] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def active(self) -> Optional[Run]:
        return next((r for r in self.runs.values() if not r.finished), None)

    def start(self, spec: RunSpec) -> Run:
        """Launch ``spec`` (already validated). Must be called on the event loop."""
        if self.active is not None:
            raise RunBusyError(f"Run {self.active.id} is still in progress")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        directory = self.runs_root / run_id
        directory.mkdir(parents=True)
        spec.output_dir = str(directory)
        spec_path = directory / "run.json"
        spec.save(spec_path)

        env = dict(os.environ, PYTHONUNBUFFERED="1")
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (_PACKAGE_PARENT, env.get("PYTHONPATH")) if p
        )
        run = Run(id=run_id, spec=spec, directory=directory)
        run._process = subprocess.Popen(
            [self.python, "-u", "-m", "policyswarm.cli", "--spec", str(spec_path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, cwd=str(directory), text=True, encoding="utf-8", errors="replace",
        )
        self.runs[run_id] = run
        run._publish({"kind": "status", "status": RUNNING, "returncode": None})

        loop = asyncio.get_running_loop()
        threading.Thread(
            target=self._pump, args=(run, loop), name=f"run-{run_id}", daemon=True
        ).start()
        return run

    def cancel(self, run_id: str) -> Run:
        run = self.runs[run_id]
        if not run.finished and run.status != CANCELLED:
            run.status = CANCELLED          # read by _finish once the child exits
            run._process.terminate()
        return run

    def shutdown(self) -> None:
        """Terminate any child still running (server shutdown)."""
        for run in self.runs.values():
            if not run.finished and run._process is not None:
                run._process.terminate()

    # ------------------------------------------------------------------
    # Output pump (worker thread) and completion (event-loop thread)
    # ------------------------------------------------------------------

    def _pump(self, run: Run, loop: asyncio.AbstractEventLoop) -> None:
        """Read the child's output line by line and hand it to the loop."""
        for raw in run._process.stdout:
            line = raw.rstrip("\r\n")
            event = parse_event_line(line)
            message = ({"kind": "event", "event": event} if event is not None
                       else {"kind": "log", "line": line})
            loop.call_soon_threadsafe(run._publish, message)
        returncode = run._process.wait()
        loop.call_soon_threadsafe(self._finish, run, returncode)

    @staticmethod
    def _finish(run: Run, returncode: int) -> None:
        run.returncode = returncode
        if run.status != CANCELLED:
            run.status = SUCCEEDED if returncode == 0 else FAILED
        run._publish({"kind": "status", "status": run.status, "returncode": returncode})
        for queue in run._subscribers:
            queue.put_nowait(None)          # end-of-stream sentinel

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    async def stream(self, run_id: str) -> AsyncIterator[dict]:
        """Yield every message of a run: history first, then live until it ends."""
        run = self.runs[run_id]
        queue: asyncio.Queue = asyncio.Queue()
        # No await between the snapshot and the subscription, so no message
        # can fall in the gap.
        backlog = list(run.history)
        ended = run.finished
        if not ended:
            run._subscribers.append(queue)
        try:
            for message in backlog:
                yield message
            while not ended:
                message = await queue.get()
                if message is None:
                    break
                yield message
        finally:
            if queue in run._subscribers:
                run._subscribers.remove(queue)
