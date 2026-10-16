"""The two methods-note switches on SimConfig: gate_space and policy_pull.

Defaults keep the audited model; the golden tests cover that the default
path is unchanged.
"""

import dataclasses

import numpy as np
import pytest

from policyswarm.config import Geometry, GovernanceConfig, Policy, SimConfig
from policyswarm.dynamics import Simulation
from policyswarm.geometry import matched_epsilons, pass_fraction

SMALL = SimConfig(n_agents=40, n_ticks=12, interactions=60)
POLICY = np.array([0.2, 0.6, 0.9, 0.6])
QUIET = dict(enable_media=False, policy_pull_onset=10_000)   # peers (and anchor) only


def _run(sim_config, geometry=Geometry.EUCLIDEAN, gov=None, seed=3):
    sim = Simulation(sim_config, gov or GovernanceConfig(), Policy(vector=POLICY.copy()), [],
                     apply_shocks=False, seed=seed, geometry=geometry)
    sim.run()
    return sim


def test_defaults_are_the_audited_model():
    assert SimConfig().gate_space == "centred"
    assert SimConfig().policy_pull == "anchor"


@pytest.mark.parametrize("field, value", [("gate_space", "sphere"), ("policy_pull", "always")])
def test_unknown_switch_values_are_rejected(field, value):
    with pytest.raises(ValueError):
        _run(dataclasses.replace(SMALL, **{field: value}))


def test_unit_gate_is_a_rescaling_for_euclidean():
    # Euclidean distance halves on [0, 1] coordinates and its step is affine,
    # so eps 0.5 on the unit gate must reproduce eps 1.0 on the centred gate.
    centred = _run(dataclasses.replace(SMALL, epsilon=1.0))
    unit = _run(dataclasses.replace(SMALL, epsilon=0.5, gate_space="unit"))
    np.testing.assert_allclose(unit.final_opinions, centred.final_opinions, atol=1e-12)
    assert unit.gate_pass_rate == centred.gate_pass_rate


def test_unit_gate_measures_angles_from_the_cube_corner():
    sim = Simulation(dataclasses.replace(SMALL, gate_space="unit"), GovernanceConfig(),
                     Policy(vector=POLICY.copy()), [], seed=3, geometry=Geometry.COSINE)
    a, b = sim.opinions[0], sim.opinions[1]
    ua, ub = (a + 1) / 2, (b + 1) / 2
    want = 1 - ua @ ub / (np.linalg.norm(ua) * np.linalg.norm(ub))
    assert sim._distance(a, b) == pytest.approx(want)


def test_unit_gate_reproduces_audit_coverage_on_network_pairs():
    sc = dataclasses.replace(SimConfig(), gate_space="unit")
    assert pass_fraction(sc, Geometry.EUCLIDEAN, 0.5, seeds=range(5)) == pytest.approx(0.13, abs=0.03)
    assert pass_fraction(sc, Geometry.COSINE, 0.5, seeds=range(5)) == pytest.approx(0.94, abs=0.03)
    eps, _ = matched_epsilons(sc, [Geometry.EUCLIDEAN, Geometry.COSINE], reference_epsilon=0.5,
                              seeds=range(5))
    assert eps["cosine"] < 0.2


def test_gated_pull_needs_a_conversation():
    # No conversation can pass at eps 0: the gated nudge never fires and the
    # ungated anchor is switched off, so nobody moves.
    sc = dataclasses.replace(SMALL, epsilon=0.0, policy_pull="gated")
    sim = _run(sc, gov=GovernanceConfig(**QUIET))
    np.testing.assert_array_equal(sim.final_opinions, sim.initial_opinions)


def test_gated_pull_moves_listeners_toward_policy():
    # mu = 0: peers have no influence, so any movement is the gated nudge.
    sc = dataclasses.replace(SMALL, epsilon=10.0, mu=0.0, policy_pull="gated")
    sim = _run(sc, gov=GovernanceConfig(**QUIET))
    before = np.linalg.norm(sim.initial_opinions - POLICY, axis=1).mean()
    after = np.linalg.norm(sim.final_opinions - POLICY, axis=1).mean()
    assert after < 0.9 * before


def test_anchor_mode_moves_without_conversations():
    sc = dataclasses.replace(SMALL, epsilon=0.0)            # anchor default
    sim = _run(sc, gov=GovernanceConfig(**QUIET))
    assert not np.array_equal(sim.final_opinions, sim.initial_opinions)
