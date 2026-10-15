"""
policyswarm.gui.server
======================
FastAPI application for the experiment dashboard.

Endpoints
---------
GET  /                               the single-page front end
GET  /api/experiments                experiment catalogue and parameter specs
GET  /api/runs                       runs started in this server session
POST /api/policy/preview             policy position for a text + opinion space
POST /api/simulate                   tick-by-tick trace of one simulation (viewer)
POST /api/suggest/topics             topics in the policy text (candidate dimensions)
POST /api/suggest/keywords           keyword rules proposed by a decision model
POST /api/runs                       start a run (422 invalid, 409 busy)
GET  /api/runs/{id}                  run status
GET  /api/runs/{id}/events           server-sent event stream of run messages
POST /api/runs/{id}/cancel           terminate a run
GET  /api/runs/{id}/results          stats tables and figure URLs per experiment
GET  /api/runs/{id}/files/{experiment}/{filename}   a figure / CSV / TeX file
"""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import registry, suggest, trace
from ..config import RunSpec
from ..experiments.params import ParamError
from ..extraction import DEFAULT_POLICY_TEXT
from ..opinion_space import OpinionSpace
from .runner import Run, RunBusyError, RunManager

STATIC_DIR = Path(__file__).parent / "static"
_SERVABLE_SUFFIXES = {".png", ".csv", ".tex"}


class RunRequest(BaseModel):
    """Body of ``POST /api/runs``. The output location is chosen by the server."""
    experiments : List[str]
    seeds       : List[int]
    policy_text : Optional[str]             = None
    sim_config  : Dict[str, Any]            = Field(default_factory=dict)
    params      : Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    opinion_space : Optional[Dict[str, Any]] = None


class SimulateRequest(BaseModel):
    """Body of ``POST /api/simulate``: one simulation to trace for the viewer."""
    params        : Dict[str, Any]           = Field(default_factory=dict)
    sim_config    : Dict[str, Any]           = Field(default_factory=dict)
    policy_text   : Optional[str]            = None
    opinion_space : Optional[Dict[str, Any]] = None


class TopicsRequest(BaseModel):
    """Body of ``POST /api/suggest/topics``."""
    policy_text : Optional[str] = None
    corpus_dir  : Optional[str] = None
    n_topics    : int           = 4


class KeywordsRequest(BaseModel):
    """Body of ``POST /api/suggest/keywords``."""
    policy_text   : Optional[str]       = None
    opinion_space : Dict[str, Any]
    phrases       : Optional[List[str]] = None


class PolicyPreviewRequest(BaseModel):
    """Body of ``POST /api/policy/preview``."""
    policy_text   : Optional[str] = None
    opinion_space : Dict[str, Any]


def create_app(runs_dir: str = "runs",
               decider_checkpoint: str = suggest.DEFAULT_CHECKPOINT) -> FastAPI:
    """Build the dashboard app.

    Runs are written under ``runs_dir``. ``decider_checkpoint`` is the Laya
    model "Suggest keyword rules" uses: the stock model id, or the folder of a
    fine-tuned checkpoint.
    """
    manager = RunManager(Path(runs_dir))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(title="PolicySwarm dashboard", lifespan=lifespan)
    app.state.manager = manager
    #: The System One model behind keyword suggestions; tests replace it.
    app.state.decider = suggest.LayaDecider(decider_checkpoint)

    def get_run(run_id: str) -> Run:
        try:
            return manager.runs[run_id]
        except KeyError:
            raise HTTPException(404, f"Unknown run: {run_id}") from None

    @app.get("/api/experiments")
    def experiments() -> dict:
        return {**registry.describe(), "viewer": trace.describe(),
                "suggest": {**suggest.available(), "max_phrases": suggest.MAX_PHRASES,
                            "fine_tuned": decider_checkpoint != suggest.DEFAULT_CHECKPOINT}}

    @app.post("/api/suggest/topics")
    def suggest_topics(request: TopicsRequest) -> dict:
        """Topics found in the policy text (plus an optional local folder of documents)."""
        text = request.policy_text or DEFAULT_POLICY_TEXT
        try:
            texts = suggest.load_texts(text, request.corpus_dir or None)
            topics = suggest.find_topics(texts, request.n_topics)
        except ParamError as exc:
            raise HTTPException(422, str(exc)) from None
        return {
            "units"  : len(texts),
            "topics" : [{**topic.to_dict(),
                         "in_text": [t["term"] for t in topic.terms
                                     if suggest.occurs_in(t["term"], text)]}
                        for topic in topics],
        }

    @app.post("/api/suggest/keywords")
    def suggest_keywords(request: KeywordsRequest) -> dict:
        """Keyword rules a decision model proposes for the space's dimensions.

        Candidate phrases are the ones given, or the terms of a fresh topic
        model with one topic per dimension. Only phrases that occur in the
        policy text and have no rule yet are rated.
        """
        text = request.policy_text or DEFAULT_POLICY_TEXT
        try:
            space = OpinionSpace.from_dict(request.opinion_space)
            phrases = request.phrases
            if phrases is None:
                topics = suggest.find_topics(suggest.load_texts(text), len(space.dimensions))
                phrases = suggest.candidate_phrases(topics, text)
            existing = {rule.keyword for rule in space.keywords}
            phrases = [p.strip().lower() for p in phrases]
            phrases = [p for i, p in enumerate(phrases)
                       if p and p not in existing and p not in phrases[:i]
                       and suggest.occurs_in(p, text)][:suggest.MAX_PHRASES]
            rules = suggest.rate_keywords(app.state.decider, phrases, space.dimensions, text)
        except ParamError as exc:
            raise HTTPException(422, str(exc)) from None
        return {"rated": len(phrases), "rules": [rule.to_dict() for rule in rules]}

    @app.post("/api/simulate")
    def simulate(request: SimulateRequest) -> dict:
        """Run one simulation in this process and return everything that happened.

        Declared with ``def`` so FastAPI runs it in a worker thread and the
        event loop stays free for a batch run's progress stream.
        """
        try:
            return trace.record_trace(
                params        = request.params,
                sim_config    = request.sim_config,
                policy_text   = request.policy_text or None,
                opinion_space = request.opinion_space,
            )
        except ParamError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/api/policy/preview")
    def policy_preview(request: PolicyPreviewRequest) -> dict:
        """The policy position an opinion space and text produce. Starts nothing."""
        text = request.policy_text or DEFAULT_POLICY_TEXT
        try:
            space = OpinionSpace.from_dict(request.opinion_space)
        except ParamError as exc:
            raise HTTPException(422, str(exc)) from None
        return {
            "position": space.policy_position(text),
            "matched_keywords": [] if space.position is not None else space.matched_keywords(text),
            "source": "set by hand" if space.position is not None else "policy text",
        }

    @app.get("/api/runs")
    def list_runs() -> List[dict]:
        return [run.summary() for run in manager.runs.values()]

    @app.post("/api/runs", status_code=201)
    async def start_run(request: RunRequest) -> dict:
        spec = RunSpec(
            experiments = request.experiments,
            seeds       = request.seeds,
            policy_text = request.policy_text or None,
            sim_config  = request.sim_config,
            params      = request.params,
            opinion_space = request.opinion_space,
        )
        try:
            registry.validate_run_spec(spec)
        except ParamError as exc:
            raise HTTPException(422, str(exc)) from None
        try:
            return manager.start(spec).summary()
        except RunBusyError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/runs/{run_id}")
    def run_status(run_id: str) -> dict:
        return get_run(run_id).summary()

    @app.get("/api/runs/{run_id}/events", response_class=EventSourceResponse)
    async def run_events(run_id: str):
        get_run(run_id)
        async for message in manager.stream(run_id):
            yield ServerSentEvent(data=message)

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict:
        get_run(run_id)
        return manager.cancel(run_id).summary()

    @app.get("/api/runs/{run_id}/results")
    def run_results(run_id: str) -> dict:
        run = get_run(run_id)
        return {
            "id": run.id,
            "status": run.status,
            "experiments": [_experiment_results(run, name) for name in run.spec.experiments],
        }

    @app.get("/api/runs/{run_id}/files/{experiment}/{filename}")
    def run_file(run_id: str, experiment: str, filename: str) -> FileResponse:
        run = get_run(run_id)
        if experiment not in run.spec.experiments:
            raise HTTPException(404, "Unknown experiment for this run")
        path = (run.directory / experiment / filename).resolve()
        # resolve() collapses any ".." so the parent check cannot be bypassed
        if path.parent != (run.directory / experiment).resolve() \
                or path.suffix not in _SERVABLE_SUFFIXES or not path.is_file():
            raise HTTPException(404, "File not found")
        return FileResponse(path)

    # Mounted last so it cannot shadow the API routes.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def _experiment_results(run: Run, name: str) -> dict:
    """Latest stats table and the output files of one experiment of a run."""
    directory = run.directory / name
    stats_files = sorted(directory.glob("*_stats_*.csv"))
    stats = None
    if stats_files:
        df = pd.read_csv(stats_files[-1])
        stats = {"columns": list(df.columns),
                 "rows": [[_json_safe(v) for v in row] for row in df.itertuples(index=False)]}
    base = f"/api/runs/{run.id}/files/{name}/"
    files = sorted(directory.glob("*")) if directory.is_dir() else []
    return {
        "name"   : name,
        "stats"  : stats,
        "figures": [base + f.name for f in files if f.suffix == ".png"],
        "files"  : [base + f.name for f in files if f.suffix in {".csv", ".tex"}],
    }


def _json_safe(value: Any) -> Any:
    """Convert numpy scalars to Python, and NaN / inf (invalid JSON) to None."""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
