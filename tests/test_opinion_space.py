"""Tests for user-defined opinion spaces."""

import copy
import dataclasses

import numpy as np
import pytest

from policyswarm.config import DEFAULT_SPLIT_DELTAS, GovernanceConfig, RunSpec, SimConfig
from policyswarm.dynamics import Simulation
from policyswarm.experiments.params import ParamError
from policyswarm.extraction import DEFAULT_POLICY_TEXT, policy_from_text
from policyswarm.opinion_space import OpinionSpace, presets
from policyswarm.registry import describe, experiments_from_spec, validate_run_spec

SMALL = {"n_agents": 30, "n_ticks": 12, "interactions": 30, "policy_split_tick": 6}

CUSTOM = {
    "dimensions": [
        {"name": "openness", "description": "x", "ideology_sensitivity": -0.2},
        {"name": "oversight", "ideology_sensitivity": 0.3, "tightening": 0.2},
        {"name": "funding"},
    ],
    "violator_dimension": "openness",
    "violator_threshold": 0.5,
    "position": {"openness": -0.4, "oversight": 0.7, "funding": 0.1},
}


def _custom(**changes):
    return {**copy.deepcopy(CUSTOM), **changes}


# ---------------------------------------------------------------------------
# The default space reproduces the built-in behaviour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [DEFAULT_POLICY_TEXT, "A ban with strict penalties and audits.", ""])
def test_default_space_builds_the_legacy_policy(text):
    legacy = policy_from_text(text)
    built = OpinionSpace.default().build_policy(text)
    np.testing.assert_array_equal(built.vector, legacy.vector)
    np.testing.assert_array_equal(built.dimension_salience, legacy.dimension_salience)
    assert built.dimension_names == legacy.dimension_names
    assert (built.violator_dim_index, built.violator_threshold) == (
        legacy.violator_dim_index, legacy.violator_threshold)
    assert built.split_deltas == DEFAULT_SPLIT_DELTAS
    assert built.narrative == legacy.narrative


def test_default_space_survives_a_json_round_trip():
    space = OpinionSpace.default()
    again = OpinionSpace.from_dict(space.to_dict())
    assert again == space
    np.testing.assert_array_equal(again.build_policy(DEFAULT_POLICY_TEXT).vector,
                                  policy_from_text(DEFAULT_POLICY_TEXT).vector)


def test_run_with_default_space_spelled_out_matches_run_without_it(tmp_path):
    base = dict(experiments=["lag"], seeds=[0, 1], sim_config=SMALL,
                params={"lag": {"lags": [0, 4]}})
    (plain,) = experiments_from_spec(RunSpec(output_dir=str(tmp_path / "a"), **base))
    (spelled,) = experiments_from_spec(RunSpec(
        output_dir=str(tmp_path / "b"), opinion_space=OpinionSpace.default().to_dict(), **base))
    assert plain.policy is None and spelled.policy is not None
    assert plain.run().equals(spelled.run())


# ---------------------------------------------------------------------------
# Custom spaces
# ---------------------------------------------------------------------------

def test_hand_set_position_builds_the_expected_policy():
    policy = OpinionSpace.from_dict(CUSTOM).build_policy("text is ignored here")
    assert policy.dimension_names == ["openness", "oversight", "funding"]
    np.testing.assert_array_equal(policy.vector, [-0.4, 0.7, 0.1])
    np.testing.assert_array_equal(policy.dimension_salience, [-0.2, 0.3, 0.0])
    assert (policy.violator_dim_index, policy.violator_threshold) == (0, 0.5)
    assert policy.split_deltas == {"oversight": 0.2}


def test_keyword_rules_move_the_right_dimension():
    space = OpinionSpace.from_dict(_custom(position=None, keywords=[
        {"keyword": "open source", "dimension": "openness", "delta": 0.5},
        {"keyword": "Inspector", "dimension": "oversight", "delta": 0.3},
        {"keyword": "grant", "dimension": "funding", "delta": -0.2},
    ]))
    text = "Open source models are reviewed by an inspector."
    assert space.matched_keywords(text) == ["inspector", "open source"]
    assert space.policy_position(text) == pytest.approx(
        {"openness": 0.5, "oversight": 0.3, "funding": 0.0})


def test_keyword_position_is_clipped():
    space = OpinionSpace.from_dict(_custom(position=None, keywords=[
        {"keyword": "a", "dimension": "openness", "delta": 1.5},
        {"keyword": "b", "dimension": "openness", "delta": 1.5},
    ]))
    assert space.policy_position("a b")["openness"] == pytest.approx(0.9)


@pytest.mark.parametrize("experiment, params", [
    ("lag", {"lags": [0, 4]}),
    ("geometry", {"alphas": [0.1]}),
])
def test_custom_space_runs_end_to_end(tmp_path, experiment, params):
    spec = RunSpec(experiments=[experiment], seeds=[0], output_dir=str(tmp_path),
                   sim_config=SMALL, params={experiment: params}, opinion_space=CUSTOM)
    (exp,) = experiments_from_spec(spec)
    assert exp.sim_config.opinion_dim == 3
    df = exp.run()
    assert len(df) > 0 and np.isfinite(df["variance"]).all()


def _policy_after_split(policy):
    sc = dataclasses.replace(SimConfig(**SMALL), opinion_dim=policy.dim)
    sim = Simulation(sc, GovernanceConfig(), policy, shocks=[], seed=0)
    sim.run()
    return sim.policy.vector


def test_custom_tightening_is_applied_at_the_split_tick():
    policy = OpinionSpace.from_dict(CUSTOM).build_policy("")
    np.testing.assert_allclose(_policy_after_split(policy), [-0.4, 0.9, 0.1])


def test_no_tightening_when_every_dimension_is_zero():
    dims = [{"name": "openness"}, {"name": "oversight"}, {"name": "funding"}]
    policy = OpinionSpace.from_dict(_custom(dimensions=dims)).build_policy("")
    assert policy.split_deltas == {}
    np.testing.assert_array_equal(_policy_after_split(policy), [-0.4, 0.7, 0.1])


def test_presets_are_valid_and_listed():
    for space in presets().values():
        space.validate()
    catalogue = describe()["opinion_space"]
    assert list(catalogue["presets"]) == ["AI governance (default)", "Healthcare"]
    assert [d["name"] for d in catalogue["presets"]["Healthcare"]["dimensions"]] == [
        "access_restriction", "cost_sharing", "provider_regulation", "coverage_mandate"]
    assert catalogue["presets"]["Healthcare"]["violator_threshold"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "not an object",
    {"violator_dimension": "openness"},                                  # no dimensions
    _custom(dimensions=[{"name": "only_one"}]),                          # too few
    _custom(dimensions=[{"name": f"d{i}"} for i in range(13)]),          # too many
    _custom(dimensions=[{"name": "Openness"}, {"name": "b"}]),           # bad name
    _custom(dimensions=[{"name": "a"}, {"name": "a"}]),                  # duplicate
    _custom(dimensions=[{"name": "a", "colour": "red"}, {"name": "b"}]),  # unknown field
    _custom(violator_dimension="missing"),
    _custom(violator_threshold=1.5),
    _custom(position={"openness": 0.1}),                                 # incomplete
    _custom(position={"openness": 2, "oversight": 0, "funding": 0}),     # out of range
    _custom(position={"openness": "high", "oversight": 0, "funding": 0}),
    _custom(keywords=[{"keyword": "x", "dimension": "missing", "delta": 0.1}]),
    _custom(keywords=[{"keyword": "x", "dimension": "openness", "delta": 0.1},
                      {"keyword": "X", "dimension": "funding", "delta": 0.1}]),   # duplicate
    _custom(keywords=[{"keyword": "", "dimension": "openness", "delta": 0.1}]),
    _custom(keywords=[{"keyword": "x", "dimension": "openness", "delta": True}]),
    _custom(extra=1),
])
def test_invalid_spaces_are_rejected(bad):
    with pytest.raises(ParamError):
        OpinionSpace.from_dict(bad)


def test_run_spec_carries_and_validates_the_space(tmp_path):
    spec = RunSpec(experiments=["lag"], seeds=[0], opinion_space=CUSTOM)
    path = tmp_path / "run.json"
    spec.save(path)
    assert RunSpec.load(path) == spec
    validate_run_spec(spec)
    with pytest.raises(ParamError):
        validate_run_spec(RunSpec(experiments=["lag"], seeds=[0],
                                  opinion_space=_custom(violator_dimension="nope")))


def test_space_and_prebuilt_policy_cannot_be_combined(tmp_path):
    spec = RunSpec(experiments=["lag"], seeds=[0], output_dir=str(tmp_path), opinion_space=CUSTOM)
    with pytest.raises(ParamError):
        experiments_from_spec(spec, policy=policy_from_text(""))


def test_generic_policy_with_builtin_names_keeps_its_vector():
    """Regression: construction used to zero the vector via the legacy-field sync."""
    from policyswarm.config import Policy
    source = np.array([0.5, 0.7, 0.8, 0.6])
    policy = Policy(vector=source, dimension_names=[
        "deployment_cap", "transparency", "enforcement", "audit_intensity"])
    np.testing.assert_array_equal(policy.vector, [0.5, 0.7, 0.8, 0.6])
    np.testing.assert_array_equal(source, [0.5, 0.7, 0.8, 0.6])
    assert policy.enforcement == 0.8
    policy.enforcement = 0.1               # assignment after construction still syncs
    assert policy.vector[2] == 0.1


def test_end_descriptions_are_optional_and_round_trip():
    default = OpinionSpace.default().to_dict()
    assert all(d["positive_means"] and d["negative_means"] for d in default["dimensions"])
    # A space written before the two fields existed loads and round-trips unchanged.
    legacy = {**default, "dimensions": [
        {k: v for k, v in d.items() if k not in ("positive_means", "negative_means")}
        for d in default["dimensions"]]}
    assert OpinionSpace.from_dict(legacy).to_dict() == legacy

    described = {**legacy, "dimensions": [
        {**legacy["dimensions"][0], "positive_means": "permissive", "negative_means": "restricted"},
        *legacy["dimensions"][1:]]}
    space = OpinionSpace.from_dict(described)
    assert space.dimensions[0].positive_means == "permissive"
    assert space.to_dict() == described
    # The simulation ignores them: same policy either way.
    assert np.array_equal(space.build_policy("A ban.").vector,
                          OpinionSpace.default().build_policy("A ban.").vector)
