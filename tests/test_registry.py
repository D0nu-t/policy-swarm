"""Tests for the experiment registry, parameter specs, RunSpec and event protocol."""

import json

import numpy as np
import pytest

from policyswarm.config import Geometry, OverlapRegime, Policy, RunSpec, ShockMode, SimConfig
from policyswarm.experiments.events import EVENT_PREFIX, emit_event, parse_event_line
from policyswarm.experiments.params import ParamError, ParamSpec, parse_params
from policyswarm.registry import (
    EXPERIMENTS, SIM_CONFIG_PARAMS, build_experiment, build_sim_config, describe,
    experiments_from_spec, validate_run_spec,
)

# ---------------------------------------------------------------------------
# Registry and parameter declarations
# ---------------------------------------------------------------------------

def test_registry_lists_all_eight_experiments():
    assert list(EXPERIMENTS) == [
        "oversight", "lag", "media", "counterfactual", "topology", "epsilon",
        "centrality", "geometry",
    ]
    assert all(cls.name == name and cls.title for name, cls in EXPERIMENTS.items())


@pytest.mark.parametrize("name", list(EXPERIMENTS))
def test_declared_defaults_match_constructor_defaults(name, tmp_path):
    """PARAMS is what the dashboard shows; it must not drift from the code."""
    cls = EXPERIMENTS[name]
    default_exp = cls(output_dir=str(tmp_path / "a"))
    declared = {p.name: p.default for p in cls.PARAMS}
    from_declared = build_experiment(name, str(tmp_path / "b"), seeds=[0], params=declared)
    attr = {"sbm_communities": lambda e: e.sim_config.sbm_n_communities,
            "sbm_p_in": lambda e: e.sim_config.sbm_p_in,
            "sbm_p_out": lambda e: e.sim_config.sbm_p_out}
    for p in cls.PARAMS:
        get = attr.get(p.name, lambda e, n=p.name: getattr(e, n))
        assert get(from_declared) == get(default_exp), p.name


def test_describe_is_json_serialisable():
    catalogue = json.loads(json.dumps(describe()))
    assert [e["name"] for e in catalogue["experiments"]] == list(EXPERIMENTS)
    assert {"n_agents", "mu", "epsilon"} <= {p["name"] for p in catalogue["sim_config"]}
    assert "opinion_dim" not in {p["name"] for p in catalogue["sim_config"]}


# ---------------------------------------------------------------------------
# Parameter parsing
# ---------------------------------------------------------------------------

def test_enum_values_are_converted():
    exp_params = parse_params(EXPERIMENTS["counterfactual"].PARAMS,
                              {"geometries": ["cosine"], "shock_mode": "polarizing",
                               "pull_onset": None})
    assert exp_params == {"geometries": [Geometry.COSINE], "shock_mode": ShockMode.POLARIZING,
                          "pull_onset": None}
    assert parse_params(EXPERIMENTS["oversight"].PARAMS, {"regimes": ["none"]}) == {
        "regimes": [OverlapRegime.NONE]}


@pytest.mark.parametrize("name, params", [
    ("lag", {"lags": []}),                       # empty sweep
    ("lag", {"lags": [0, -5]}),                  # below minimum
    ("lag", {"lags": [1.5]}),                    # not an integer
    ("lag", {"lags": "0,5"}),                    # not a list
    ("lag", {"laggs": [0]}),                     # unknown name
    ("geometry", {"geometries": ["hyperbolic"]}),  # not a choice
    ("geometry", {"epsilon_mode": "auto"}),
    ("media", {"media_conditions": [1, 0]}),     # ints are not bools
    ("topology", {"sbm_p_in": 1.5}),             # above maximum
    ("topology", {"sbm_communities": None}),     # required scalar
])
def test_invalid_params_are_rejected(name, params):
    with pytest.raises(ParamError):
        parse_params(EXPERIMENTS[name].PARAMS, params)


def test_bool_is_not_accepted_as_number():
    with pytest.raises(ParamError):
        ParamSpec("n", "int", 1).parse(True)


def test_sim_config_overrides():
    sc = build_sim_config({"n_agents": 60, "network_type": "sbm", "mu": 0.1})
    assert (sc.n_agents, sc.network_type.value, sc.mu) == (60, "sbm", 0.1)
    assert sc.n_ticks == SimConfig().n_ticks
    with pytest.raises(ParamError):
        build_sim_config({"opinion_dim": 6})     # not user-settable
    with pytest.raises(ParamError):
        build_sim_config({"n_agents": 2})
    assert all(p.name != "shock_prob" for p in SIM_CONFIG_PARAMS)


# ---------------------------------------------------------------------------
# RunSpec
# ---------------------------------------------------------------------------

def test_run_spec_round_trip(tmp_path):
    spec = RunSpec(experiments=["lag", "geometry"], seeds=[0, 1], output_dir="out",
                   sim_config={"n_agents": 50}, params={"lag": {"lags": [0, 10]}})
    path = tmp_path / "run.json"
    spec.save(path)
    assert RunSpec.load(path) == spec


def test_run_spec_rejects_unknown_and_missing_fields():
    with pytest.raises(ValueError):
        RunSpec.from_dict({"experiments": ["lag"], "seeds": [0], "sedes": [1]})
    with pytest.raises(ValueError):
        RunSpec.from_dict({"experiments": ["lag"]})


@pytest.mark.parametrize("changes", [
    {"experiments": []},
    {"experiments": ["nope"]},
    {"seeds": []},
    {"seeds": [0, 0]},
    {"seeds": [-1]},
    {"params": {"geometry": {"alphas": [0.1]}}},   # params for an unselected experiment
    {"params": {"lag": {"lags": [-1]}}},
    {"sim_config": {"n_agents": "many"}},
])
def test_validate_run_spec_rejects(changes):
    base = {"experiments": ["lag"], "seeds": [0, 1]}
    with pytest.raises(ParamError):
        validate_run_spec(RunSpec.from_dict({**base, **changes}))


def test_experiments_from_spec_applies_everything(tmp_path):
    spec = RunSpec(experiments=["lag"], seeds=[3, 4], output_dir=str(tmp_path),
                   sim_config={"n_agents": 40}, params={"lag": {"lags": [0, 7]}})
    (exp,) = experiments_from_spec(spec)
    assert (exp.seeds, exp.lags, exp.sim_config.n_agents) == ([3, 4], [0, 7], 40)
    assert exp.output_dir.endswith("lag")


# ---------------------------------------------------------------------------
# Explicit policy injection
# ---------------------------------------------------------------------------

def test_injected_policy_is_used_and_copied(tmp_path):
    policy = Policy(vector=np.array([0.1, -0.2, 0.3, 0.4]))
    exp = build_experiment("lag", str(tmp_path), seeds=[0], policy=policy)
    got = exp._policy()
    np.testing.assert_array_equal(got.vector, policy.vector)
    got.lag = 99
    got.vector[0] = 1.0
    assert policy.lag != 99 and policy.vector[0] == 0.1


def test_spec_sets_opinion_dim_from_injected_policy(tmp_path):
    policy = Policy(vector=np.zeros(6), dimension_names=[f"d{i}" for i in range(6)])
    spec = RunSpec(experiments=["lag"], seeds=[0], output_dir=str(tmp_path))
    (exp,) = experiments_from_spec(spec, policy=policy)
    assert exp.sim_config.opinion_dim == 6


# ---------------------------------------------------------------------------
# Event protocol
# ---------------------------------------------------------------------------

def test_event_round_trip(capsys):
    emit_event(type="seed_complete", experiment="X", completed=1, total=2,
               condition={"lag": 5}, seed=0)
    line = capsys.readouterr().out.strip()
    assert line.startswith(EVENT_PREFIX)
    assert parse_event_line(line) == {"type": "seed_complete", "experiment": "X",
                                      "completed": 1, "total": 2,
                                      "condition": {"lag": 5}, "seed": 0}


@pytest.mark.parametrize("line", [
    "plain log output",
    "  ##EVENT## {\"type\": \"start\"}",       # sentinel must start the line
    "##EVENT## {not json",
    "##EVENT## [1, 2]",
    "##EVENT## {\"experiment\": \"X\"}",        # no type
])
def test_non_events_are_ignored(line):
    assert parse_event_line(line) is None
