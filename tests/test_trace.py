"""Tests for the tick-by-tick simulation trace behind the dashboard viewer."""

import json

import numpy as np
import pytest

from policyswarm.config import GovernanceConfig, ShockConfig, SimConfig
from policyswarm.dynamics import Simulation
from policyswarm.experiments.base import BASELINE_GOVERNANCE
from policyswarm.experiments.params import ParamError
from policyswarm.extraction import DEFAULT_POLICY_TEXT, policy_from_text
from policyswarm.opinion_space import OpinionSpace
from policyswarm.shocks import generate_shocks
from policyswarm.trace import (
    HISTOGRAM_BINS, MAX_GEOMETRIES, OUTCOME_CODES, TRACE_BUDGET, TRACE_LIMITS, TraceRecorder,
    describe, record_trace,
)

SMALL = {"n_agents": 30, "n_ticks": 20, "interactions": 40, "policy_split_tick": 10}


def _simulate(recorder=None):
    config = SimConfig(**SMALL)
    shocks = generate_shocks(ShockConfig(), config.n_ticks, seed=3)
    sim = Simulation(config, GovernanceConfig(**BASELINE_GOVERNANCE), policy_from_text(DEFAULT_POLICY_TEXT),
                     shocks, seed=3, recorder=recorder)
    sim.run()
    return sim


def test_recording_does_not_change_the_simulation():
    plain, traced = _simulate(), _simulate(TraceRecorder())
    assert np.array_equal(plain.final_opinions, traced.final_opinions)
    assert plain.gate_attempts == traced.gate_attempts
    assert plain.gate_passes == traced.gate_passes


def test_conversation_outcomes_account_for_every_attempt():
    recorder = TraceRecorder()
    sim = _simulate(recorder)
    outcomes = [c[2] for tick in recorder.ticks for c in tick["conversations"]]
    blocked = outcomes.count(OUTCOME_CODES["blocked"])
    too_far = outcomes.count(OUTCOME_CODES["too_far"])

    assert len(recorder.ticks) == SMALL["n_ticks"]
    assert len(outcomes) - blocked == sim.gate_attempts
    assert len(outcomes) - blocked - too_far == sim.gate_passes
    for listener, speaker, code, distance, moved in recorder.ticks[0]["conversations"]:
        assert speaker in sim.neighbors[listener]
        if code == OUTCOME_CODES["blocked"]:
            assert distance is None and moved == 0
        elif code == OUTCOME_CODES["too_far"]:
            assert distance > sim.sim_config.epsilon and moved == 0
        else:
            assert distance <= sim.sim_config.epsilon


def test_trace_is_json_and_matches_the_run_it_describes():
    trace = record_trace(params={"seed": 3}, sim_config=SMALL)
    json.dumps(trace, allow_nan=False)

    shared, (run,) = trace["shared"], trace["runs"]
    meta = shared["meta"]
    assert meta["n_agents"] == 30 and len(run["ticks"]) == 20
    assert meta["dimensions"] == ["deployment_cap", "transparency", "enforcement", "audit_intensity"]
    assert np.shape(shared["initial"]) == (30, 4)
    assert len(shared["agents"]["x"]) == 30 and min(shared["agents"]["x"]) >= 0
    assert all(len(t["conversations"]) <= 40 for t in run["ticks"])
    assert meta["shock_ticks"] == [t for t, tick in enumerate(run["ticks"]) if tick["shocks"]]
    assert run["geometry"] == "euclidean" and run["matched_coverage"] is None
    # The policy tightens at the split tick and not before.
    split = meta["policy_split_tick"]
    assert run["ticks"][split - 1]["policy"] == shared["initial_policy"]
    assert run["ticks"][split]["policy"] != shared["initial_policy"]
    # Same inputs as the direct run above, so the same final state.
    assert np.allclose(run["ticks"][-1]["opinions"], _simulate().final_opinions, atol=1e-4)


def test_geometries_share_everything_but_the_metric():
    trace = record_trace(params={"geometries": ["euclidean", "cosine", "manifold"], "seed": 3},
                         sim_config=SMALL)
    euclidean, cosine, manifold = trace["runs"]
    assert [r["geometry"] for r in trace["runs"]] == ["euclidean", "cosine", "manifold"]
    assert euclidean["epsilon"] == SimConfig().epsilon
    # Matched epsilon: every geometry is given the same starting coverage target.
    assert euclidean["matched_coverage"] == cosine["matched_coverage"] > 0
    assert cosine["epsilon"] != euclidean["epsilon"]
    # Same seed: identical shocks, and identical conversation pairs on the first tick.
    assert [t["shocks"] for t in euclidean["ticks"]] == [t["shocks"] for t in cosine["ticks"]]
    pairs = lambda run: [c[:2] for c in run["ticks"][0]["conversations"]]  # noqa: E731
    assert pairs(euclidean) == pairs(cosine) == pairs(manifold)
    # Cosine and manifold gates admit the same pairs once matched; only the step differs.
    assert cosine["initial_measure"]["coverage"] == manifold["initial_measure"]["coverage"]


def test_measurements_describe_the_neighbour_distances():
    trace = record_trace(params={"geometries": ["euclidean", "cosine"], "seed": 3}, sim_config=SMALL)
    edges = np.array(trace["shared"]["edges"])
    for run in trace["runs"]:
        for measure in [run["initial_measure"]] + [t["measure"] for t in run["ticks"]]:
            assert len(measure["histogram"]) == HISTOGRAM_BINS
            assert sum(measure["histogram"]) + measure["undefined"] == len(edges)
            assert 0 <= measure["coverage"] <= 1 and 0 <= measure["map_fit"] <= 1
            assert np.shape(measure["map"]) == (30, 2) and len(measure["map_policy"]) == 2
            assert np.abs(measure["map"]).max() <= run["map_extent"] + 1e-6

    # Euclidean coverage can be recomputed from the stored opinions.
    run = trace["runs"][0]
    opinions = np.array(run["ticks"][5]["opinions"])
    across = np.linalg.norm(opinions[edges[:, 0]] - opinions[edges[:, 1]], axis=1)
    assert run["ticks"][5]["measure"]["coverage"] == pytest.approx(np.mean(across <= run["epsilon"]), abs=0.05)
    # The Euclidean map of 4-D points keeps most, not all, of the distances at the start.
    assert 0.3 < run["initial_measure"]["map_fit"] < 1


def test_scenario_settings_reach_the_simulation():
    quiet = record_trace(params={"shocks": False, "enable_media": False,
                                 "deployment_rate_cap": 0.0}, sim_config=SMALL)
    assert quiet["shared"]["meta"]["shock_ticks"] == []
    for tick in quiet["runs"][0]["ticks"]:
        assert "media" not in tick["moved"] and "shock" not in tick["moved"]
        assert {c[2] for c in tick["conversations"]} <= {OUTCOME_CODES["blocked"]}

    raw = record_trace(params={"geometries": ["cosine"], "match_epsilon": False}, sim_config=SMALL)
    assert raw["runs"][0]["epsilon"] == SimConfig().epsilon
    assert raw["runs"][0]["matched_coverage"] is None


def test_custom_opinion_space_sets_the_dimensions():
    space = OpinionSpace.default().to_dict()
    space["dimensions"] = space["dimensions"][:2]
    space["keywords"] = []
    space["position"] = {d["name"]: 0.5 for d in space["dimensions"]}
    trace = record_trace(sim_config=SMALL, opinion_space=space)
    assert len(trace["shared"]["meta"]["dimensions"]) == 2
    assert trace["shared"]["initial_policy"] == [0.5, 0.5]


@pytest.mark.parametrize("kwargs", [
    {"params": {"geometries": ["hyperbolic"]}},
    {"params": {"geometries": []}},
    {"params": {"geometries": ["cosine", "cosine"]}},
    {"params": {"deployment_rate_cap": 1.5}},
    {"params": {"nope": 1}},
    {"sim_config": {"n_agents": TRACE_LIMITS["n_agents"] + 1}},
    {"sim_config": {"n_ticks": TRACE_LIMITS["n_ticks"] + 1}},
    {"sim_config": {"n_agents": 400, "n_ticks": TRACE_BUDGET // 400 + 1}},
    {"opinion_space": {"dimensions": []}},
])
def test_invalid_trace_requests_are_rejected(kwargs):
    with pytest.raises(ParamError):
        record_trace(**kwargs)


def test_describe_lists_the_scenario_settings_and_geometries():
    description = describe()
    names = [p["name"] for p in description["params"]]
    assert names[0] == "geometries" and "shock_mode" in names
    assert description["max_geometries"] == MAX_GEOMETRIES == 3
    assert [g["key"] for g in description["geometries"]] == ["euclidean", "cosine", "manifold"]
    assert all(g["summary"] and g["distance"] and g["step"] and g["epsilon"]
               for g in description["geometries"])


# --- compare one hidden choice ---------------------------------------------

def test_compare_trust_anchor_gives_one_column_per_value():
    out = record_trace(params={"compare": "trust_anchor", "geometries": ["cosine"]}, sim_config=SMALL)
    labels = [r["label"] for r in out["runs"]]
    assert len(labels) == 4 and all("Cosine" in label for label in labels)
    assert [r["choices"]["trust_anchor"] for r in out["runs"]] == ["centre", "corner", "status_quo", "own"]


def test_compare_gate_space_keeps_euclidean_identical_in_both_spaces():
    out = record_trace(params={"compare": "gate_space", "geometries": ["euclidean"]}, sim_config=SMALL)
    a, b = out["runs"]
    assert a["epsilon"] == pytest.approx(2 * b["epsilon"])          # same gate in unit units
    assert a["gate_pass_rate"] == pytest.approx(b["gate_pass_rate"])


def test_threshold_rules_differ_for_an_angular_geometry():
    out = record_trace(params={"compare": "threshold_rule", "geometries": ["cosine"]}, sim_config=SMALL)
    eps = [r["epsilon"] for r in out["runs"]]
    assert [r["choices"]["threshold_rule"] for r in out["runs"]] == ["shared", "matched_start", "matched_run"]
    assert len(set(eps)) == 3


def test_legacy_match_epsilon_still_accepted():
    out = record_trace(params={"geometries": ["cosine"], "match_epsilon": False}, sim_config=SMALL)
    assert out["runs"][0]["choices"]["threshold_rule"] == "shared"


def test_compare_respects_the_size_budget():
    big = {**SMALL, "n_agents": 400, "n_ticks": 60}
    with pytest.raises(ParamError):
        record_trace(params={"compare": "trust_anchor", "geometries": ["cosine"]}, sim_config=big)
