"""
policyswarm.experiments.events
==============================
The structured progress-event protocol shared by every front end.

Experiments report progress as single-line JSON on stdout, prefixed with the
sentinel ``##EVENT## ``. The sentinel lets a consumer (the Ink TUI in
``tui/``, the web dashboard in ``gui/``) pick events out of the surrounding
prose output — executive summaries, stats tables, file paths — without
heuristics.

Event types
-----------
start          {"experiment", "total"}
seed_complete  {"experiment", "completed", "total", "condition", "seed"}
complete       {"experiment", "figures", "rows"}
error          {"experiment", "message"}

This module is the single definition of the wire format: ``emit_event``
writes it and ``parse_event_line`` reads it.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

EVENT_PREFIX = "##EVENT## "


def emit_event(**fields: Any) -> None:
    """Write one progress event to stdout.

    ``flush=True`` is required: when this process is a child of a front end,
    stdout is a pipe rather than a TTY and CPython block-buffers it, so
    without an explicit flush events would arrive in bursts or only at exit.
    """
    print(EVENT_PREFIX + json.dumps(fields), flush=True)


def parse_event_line(line: str) -> Optional[Dict[str, Any]]:
    """Return the event carried by ``line``, or None if it is not an event.

    Malformed payloads (invalid JSON, non-object, missing ``type``) are
    treated as ordinary log lines rather than raised, so one bad line can
    never take a front end down.
    """
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        event = json.loads(line[len(EVENT_PREFIX):])
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or "type" not in event:
        return None
    return event
