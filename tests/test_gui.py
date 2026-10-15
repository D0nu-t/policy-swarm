"""Tests for the dashboard API (no experiment is actually simulated here)."""

import json
import sys
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from policyswarm.gui.server import create_app  # noqa: E402

# A stand-in for `python -m policyswarm.cli --spec ...`: prints one log line
# and the four event types, then (optionally) waits so cancellation can be tested.
_FAKE_CLI = r"""
import json, sys, time
spec = json.load(open(sys.argv[sys.argv.index("--spec") + 1]))
emit = lambda **e: print("##EVENT## " + json.dumps(e), flush=True)
print("hello from the child", flush=True)
emit(type="start", experiment="EnforcementLagExperiment", total=2)
emit(type="seed_complete", experiment="EnforcementLagExperiment", completed=1, total=2,
     condition={"lag": 0}, seed=0)
if spec["seeds"] == [99]:
    time.sleep(60)
emit(type="complete", experiment="EnforcementLagExperiment", figures=0, rows=2)
sys.exit(3 if spec["seeds"] == [13] else 0)
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "runs"))
    fake = tmp_path / "fake_cli.py"
    fake.write_text(_FAKE_CLI, encoding="utf-8")

    # Run the fake script instead of the real CLI module.
    import subprocess
    real_popen = subprocess.Popen

    def popen(cmd, **kwargs):
        return real_popen([sys.executable, "-u", str(fake), *cmd[4:]], **kwargs)

    monkeypatch.setattr("policyswarm.gui.runner.subprocess.Popen", popen)
    with TestClient(app) as test_client:
        yield test_client


def _messages(client, run_id):
    with client.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        return [json.loads(line[len("data: "):]) for line in response.iter_lines()
                if line.startswith("data: ")]


def test_catalogue(client):
    body = client.get("/api/experiments").json()
    assert len(body["experiments"]) == 8
    assert body["experiments"][1]["params"][0]["name"] == "lags"


def test_index_is_served(client):
    assert "PolicySwarm" in client.get("/").text


def test_run_streams_events_then_finishes(client):
    run = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [0, 1]}).json()
    messages = _messages(client, run["id"])

    assert messages[0] == {"kind": "status", "status": "running", "returncode": None}
    assert {"kind": "log", "line": "hello from the child"} in messages
    assert [m["event"]["type"] for m in messages if m["kind"] == "event"] == [
        "start", "seed_complete", "complete"]
    assert messages[-1] == {"kind": "status", "status": "succeeded", "returncode": 0}
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "succeeded"

    # A late subscriber gets the full history replayed.
    assert _messages(client, run["id"]) == messages


def test_nonzero_exit_is_reported_as_failed(client):
    run = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [13]}).json()
    assert _messages(client, run["id"])[-1]["status"] == "failed"


def test_output_directory_is_chosen_by_the_server(client, tmp_path):
    response = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [0],
                                              "output_dir": "C:/somewhere/else"})
    run = response.json()
    _messages(client, run["id"])
    assert run["spec"]["output_dir"].startswith(str((tmp_path / "runs").resolve()))


@pytest.mark.parametrize("body", [
    {"experiments": [], "seeds": [0]},
    {"experiments": ["nope"], "seeds": [0]},
    {"experiments": ["lag"], "seeds": []},
    {"experiments": ["lag"], "seeds": [0], "params": {"lag": {"lags": [-1]}}},
    {"experiments": ["lag"], "seeds": [0], "sim_config": {"n_agents": 1}},
    {"experiments": ["lag"], "seeds": ["zero"]},
])
def test_invalid_requests_are_rejected_without_starting(client, body):
    assert client.post("/api/runs", json=body).status_code == 422
    assert client.get("/api/runs").json() == []


def test_second_run_is_refused_while_one_is_active_and_cancel_stops_it(client):
    run = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [99]}).json()
    assert client.post("/api/runs", json={"experiments": ["lag"], "seeds": [0]}).status_code == 409

    assert client.post(f"/api/runs/{run['id']}/cancel").json()["status"] == "cancelled"
    assert _messages(client, run["id"])[-1]["status"] == "cancelled"

    process = client.app.state.manager.runs[run["id"]]._process
    for _ in range(50):
        if process.poll() is not None:
            break
        time.sleep(0.1)
    assert process.poll() is not None, "child process is still alive after cancel"


def test_unknown_run_and_path_traversal(client):
    assert client.get("/api/runs/nope").status_code == 404
    run = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [0]}).json()
    _messages(client, run["id"])
    base = f"/api/runs/{run['id']}/files"
    assert client.get(f"{base}/lag/missing.png").status_code == 404
    assert client.get(f"{base}/geometry/x.png").status_code == 404          # not in this run
    assert client.get(f"{base}/lag/..%2Frun.json").status_code == 404       # escapes the folder
    assert client.get(f"/api/runs/{run['id']}/results").json()["experiments"][0]["stats"] is None


def test_policy_preview_and_opinion_space_validation(client):
    catalogue = client.get("/api/experiments").json()
    default = catalogue["opinion_space"]["default"]
    preview = client.post("/api/policy/preview", json={
        "policy_text": "A ban with strict penalties.", "opinion_space": default}).json()
    assert preview["source"] == "policy text"
    assert preview["matched_keywords"] == ["ban", "penalties", "strict"]
    assert preview["position"]["deployment_cap"] == pytest.approx(-0.7)

    by_hand = {**default, "position": {d["name"]: 0.25 for d in default["dimensions"]}}
    preview = client.post("/api/policy/preview", json={"opinion_space": by_hand}).json()
    assert preview["source"] == "set by hand" and preview["matched_keywords"] == []

    broken = {**default, "violator_dimension": "nope"}
    assert client.post("/api/policy/preview", json={"opinion_space": broken}).status_code == 422
    response = client.post("/api/runs", json={"experiments": ["lag"], "seeds": [0],
                                              "opinion_space": broken})
    assert response.status_code == 422 and "violator_dimension" in response.json()["detail"]
    assert client.get("/api/runs").json() == []


def test_simulate_returns_a_trace_and_validates(client):
    viewer = client.get("/api/experiments").json()["viewer"]
    assert "seed" in [p["name"] for p in viewer["params"]]
    assert [g["key"] for g in viewer["geometries"]][:2] == ["euclidean", "cosine"]

    small = {"n_agents": 20, "n_ticks": 8, "interactions": 10}
    trace = client.post("/api/simulate", json={
        "sim_config": small, "params": {"seed": 1, "geometries": ["euclidean", "cosine"]}}).json()
    assert trace["shared"]["meta"]["seed"] == 1
    assert [run["geometry"] for run in trace["runs"]] == ["euclidean", "cosine"]
    assert all(len(run["ticks"]) == 8 and len(run["ticks"][0]["opinions"]) == 20
               for run in trace["runs"])

    too_big = client.post("/api/simulate", json={"sim_config": {"n_agents": 5000}})
    assert too_big.status_code == 422 and "n_agents" in too_big.json()["detail"]
    assert client.post("/api/simulate", json={"params": {"geometries": ["nope"]}}).status_code == 422
    assert client.get("/api/runs").json() == []          # a trace is not a run


def test_suggest_endpoints(client):
    pytest.importorskip("sklearn")
    from policyswarm.suggest import NO_DIMENSION

    class Fake:
        def decide(self, states, questions):
            picks = {"aspect": "enforcement", "direction": "raises", "strength": "moderate"}
            out = []
            for state in states:
                chosen = dict(picks, aspect=NO_DIMENSION) if state["phrase"] == "tier" else picks
                out.append({q: {"choice": chosen[q], "probabilities": {chosen[q]: 0.7}} for q in questions})
            return out

    client.app.state.decider = Fake()
    catalogue = client.get("/api/experiments").json()
    assert catalogue["suggest"]["topics"] is True and "keywords" in catalogue["suggest"]

    found = client.post("/api/suggest/topics", json={"n_topics": 3}).json()
    assert len(found["topics"]) == 3 and found["units"] > 10
    assert all(t["terms"] and set(t["in_text"]) <= {x["term"] for x in t["terms"]} for t in found["topics"])
    assert client.post("/api/suggest/topics", json={"n_topics": 99}).status_code == 422
    short = client.post("/api/suggest/topics", json={"policy_text": "Too short to model.", "n_topics": 2})
    assert short.status_code == 422 and "Too little text" in short.json()["detail"]

    space = catalogue["opinion_space"]["default"]
    body = {"opinion_space": space, "phrases": ["tier", "Turnover", "turnover", "penalties", "unicorn"]}
    result = client.post("/api/suggest/keywords", json=body).json()
    # "penalties" already has a rule, "unicorn" is not in the text, the repeat is dropped, "tier" is unrelated.
    assert result["rated"] == 2
    assert result["rules"] == [{"keyword": "turnover", "dimension": "enforcement", "delta": 0.4,
                                "confidence": 0.7, "low_confidence": False}]
    assert len(client.post("/api/suggest/keywords", json={"opinion_space": space}).json()["rules"]) > 0
    broken = {**space, "violator_dimension": "nope"}
    assert client.post("/api/suggest/keywords", json={"opinion_space": broken}).status_code == 422


def test_cancelled_run_is_not_finished_until_its_process_exits(tmp_path):
    """A stream opened between cancel() and the child's exit must still get the final status.

    Regression: ``finished`` used to mean "status is not running", so in that
    window a new stream replayed the history and closed without the last message.
    """
    import asyncio
    from policyswarm.config import RunSpec
    from policyswarm.gui.runner import Run, RunBusyError, RunManager

    class StillExiting:                     # a child that has been told to stop but has not yet
        terminated = 0

        def terminate(self):
            self.terminated += 1

    async def scenario():
        manager = RunManager(tmp_path)
        run = Run(id="r1", spec=RunSpec(experiments=["lag"], seeds=[0]), directory=tmp_path)
        run._process = StillExiting()
        manager.runs[run.id] = run
        run._publish({"kind": "status", "status": "running", "returncode": None})

        assert manager.cancel(run.id).status == "cancelled"
        manager.cancel(run.id)                                   # a second click does nothing more
        assert run._process.terminated == 1
        assert not run.finished and manager.active is run        # still occupies the single slot
        with pytest.raises(RunBusyError):
            manager.start(RunSpec(experiments=["lag"], seeds=[1]))

        received = []

        async def consume():
            async for message in manager.stream(run.id):
                received.append(message)

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        assert not consumer.done(), "the stream closed before the run's final status"
        assert [m["status"] for m in received] == ["running"]

        manager._finish(run, 1)                                  # the child exits
        await asyncio.wait_for(consumer, timeout=2)
        assert received[-1] == {"kind": "status", "status": "cancelled", "returncode": 1}
        assert run.finished and manager.active is None

    asyncio.run(scenario())
