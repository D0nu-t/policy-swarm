"""Tests for opinion-space geometry, epsilon calibration and the paired design."""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from policyswarm.analysis import lag_geometry_interaction, paired_ttest
from policyswarm.config import (
    Geometry, GovernanceConfig, Policy, ShockConfig, SimConfig, unit_to_centred,
)
from policyswarm.dynamics import Simulation
from policyswarm.extraction import perceived_policy
from policyswarm.geometry import (
    calibrate_epsilon, distance, matched_epsilons, pass_fraction, step,
)
from policyswarm.metrics import bifurcation_index
from policyswarm.shocks import generate_shocks, override_strength

SMALL = SimConfig(n_agents=40, n_ticks=15, interactions=50)
ANGULAR = [Geometry.COSINE, Geometry.MANIFOLD]


def _angle(a, b):
    return np.arccos(np.clip(a @ b / np.linalg.norm(a) / np.linalg.norm(b), -1, 1))


# ---------------------------------------------------------------------------
# Distances
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("geometry", ANGULAR)
def test_angular_distance_ignores_magnitude(geometry):
    a, b = np.array([0.3, -0.2, 0.5, 0.1]), np.array([-0.4, 0.2, 0.1, 0.6])
    assert distance(geometry, a, b) == pytest.approx(distance(geometry, 3 * a, 0.5 * b))


def test_euclidean_distance_depends_on_magnitude():
    a, b = np.array([0.3, -0.2, 0.5, 0.1]), np.array([-0.4, 0.2, 0.1, 0.6])
    assert distance(Geometry.EUCLIDEAN, a, b) != pytest.approx(
        distance(Geometry.EUCLIDEAN, 3 * a, b))


def test_angular_distance_distinguishes_opposed_views_in_centred_space():
    # Strongly pro vs mildly anti on every dimension: opposite directions
    pro, anti = np.full(4, 0.7), np.full(4, -0.2)
    assert distance(Geometry.COSINE, pro, anti) == pytest.approx(2.0)
    assert distance(Geometry.MANIFOLD, pro, anti) == pytest.approx(np.pi)


@pytest.mark.parametrize("geometry", ANGULAR)
def test_zero_vector_never_passes_gate(geometry):
    assert distance(geometry, np.zeros(4), np.ones(4)) == np.inf


# ---------------------------------------------------------------------------
# Update step
# ---------------------------------------------------------------------------

def test_euclidean_step_is_linear_interpolation():
    a, b = np.array([0.2, 0.4]), np.array([-0.2, 0.0])
    np.testing.assert_allclose(step(Geometry.EUCLIDEAN, a, b, 0.25), [0.1, 0.3])


@pytest.mark.parametrize("geometry", ANGULAR)
def test_angular_step_preserves_magnitude_and_reduces_angle(geometry):
    a, b = np.array([0.5, 0.1, -0.2, 0.3]), np.array([-0.1, 0.6, 0.2, -0.4])
    out = step(geometry, a, b, 0.3)
    assert np.linalg.norm(out) == pytest.approx(np.linalg.norm(a))
    assert _angle(out, b) < _angle(a, b)


def test_manifold_step_moves_rate_times_geodesic_angle():
    a, b = np.array([0.5, 0.1, -0.2, 0.3]), np.array([-0.1, 0.6, 0.2, -0.4])
    theta = _angle(a, b)
    out = step(Geometry.MANIFOLD, a, b, 0.3)
    assert _angle(a, out) == pytest.approx(0.3 * theta)
    assert _angle(out, b) == pytest.approx(0.7 * theta)


@pytest.mark.parametrize("geometry", list(Geometry))
def test_zero_rate_step_is_identity(geometry):
    a, b = np.array([0.5, 0.1, -0.2, 0.3]), np.array([-0.1, 0.6, 0.2, -0.4])
    np.testing.assert_allclose(step(geometry, a, b, 0.0), a)


# ---------------------------------------------------------------------------
# Epsilon calibration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("geometry", list(Geometry))
def test_calibrated_epsilon_hits_target_coverage(geometry):
    seeds = range(5)
    eps = calibrate_epsilon(SMALL, geometry, 0.3, seeds)
    assert pass_fraction(SMALL, geometry, eps, seeds) == pytest.approx(0.3, abs=0.02)


def test_matched_epsilons_equalise_coverage():
    seeds = range(5)
    eps, target = matched_epsilons(SMALL, list(Geometry), seeds=seeds)
    assert eps[Geometry.EUCLIDEAN.value] == SMALL.epsilon
    for g in Geometry:
        assert pass_fraction(SMALL, g, eps[g.value], seeds) == pytest.approx(target, abs=0.02)


# ---------------------------------------------------------------------------
# Simulation-level invariants
# ---------------------------------------------------------------------------

def _run(geometry, sim_config=SMALL, shocks=(), apply_shocks=False, seed=3):
    policy = Policy(vector=np.array([0.2, 0.6, 0.9, 0.6]))
    sim = Simulation(sim_config, GovernanceConfig(), policy, list(shocks),
                     apply_shocks=apply_shocks, seed=seed, geometry=geometry)
    sim.run()
    return sim


def test_zero_strength_shocks_leave_trajectory_unchanged():
    """Shock target sampling must not perturb any other random stream, so
    treatment differs from control only through the shocks themselves."""
    schedule = override_strength(
        generate_shocks(ShockConfig(shock_prob=0.5), SMALL.n_ticks, seed=3), 0.0,
    )
    assert any(ev["type"] == "random" for ev in schedule)
    ctrl = _run(Geometry.EUCLIDEAN, shocks=schedule, apply_shocks=False)
    trt  = _run(Geometry.EUCLIDEAN, shocks=schedule, apply_shocks=True)
    np.testing.assert_array_equal(ctrl.final_opinions, trt.final_opinions)


def test_geometry_has_no_effect_without_peer_influence():
    """With mu = 0 geometry may only affect the gate bookkeeping, never opinions."""
    sc = dataclasses.replace(SMALL, mu=0.0)
    finals = [_run(g, sim_config=sc).final_opinions for g in Geometry]
    for f in finals[1:]:
        np.testing.assert_allclose(f, finals[0], atol=1e-12)


def test_lag_only_acts_through_enforcement_penalty():
    """With no penalty, enforcement lag must not change anything: pull onset
    and policy tightening are fixed independently of lag."""
    policy = Policy(vector=np.array([0.2, 0.6, 0.9, 0.6]))
    finals = []
    for lag in (0, 40):
        p = Policy(vector=policy.vector.copy(), lag=lag)
        sim = Simulation(SMALL, GovernanceConfig(penalty_severity=0.0), p, [],
                         seed=3, geometry=Geometry.EUCLIDEAN)
        sim.run()
        finals.append(sim.final_opinions)
    np.testing.assert_array_equal(finals[0], finals[1])


def test_gate_pass_rate_recorded():
    sim = _run(Geometry.COSINE)
    assert 0.0 <= sim.gate_pass_rate <= 1.0
    assert sim.gate_attempts > 0


# ---------------------------------------------------------------------------
# Centred opinion space
# ---------------------------------------------------------------------------

def test_unit_to_centred():
    assert unit_to_centred(0.5) == 0.0
    np.testing.assert_allclose(unit_to_centred(np.array([0.0, 0.8, 1.0])), [-1.0, 0.6, 1.0])


def test_perceived_policy_can_be_negative():
    pp = perceived_policy(np.full(4, -0.8), ideology=0.0, trust=1.0,
                          noise_scale=0.0, rng=np.random.default_rng(0))
    np.testing.assert_allclose(pp, -0.8)


def test_bifurcation_index_uses_absolute_bandwidth():
    rng = np.random.default_rng(0)
    unimodal = rng.normal(0.0, 0.2, size=(200, 1))
    bimodal  = np.concatenate([rng.normal(-0.6, 0.08, (100, 1)),
                               rng.normal(0.6, 0.08, (100, 1))])
    assert bifurcation_index(unimodal) == 1
    assert bifurcation_index(bimodal) == 2


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_paired_ttest_sign_matches_effect():
    t, _, effect = paired_ttest(np.array([1.0, 2.0, 3.0]), np.array([0.5, 1.4, 2.6]))
    assert effect < 0 and t < 0


def test_lag_geometry_interaction_detects_opposite_trends():
    rng = np.random.default_rng(0)
    rows = []
    for seed in range(30):
        noise = rng.normal(0, 0.01, size=4)
        rows += [
            {"geometry": "a", "lag": 0,  "seed": seed, "delta": -1.0 + noise[0]},
            {"geometry": "a", "lag": 40, "seed": seed, "delta": -1.5 + noise[1]},
            {"geometry": "b", "lag": 0,  "seed": seed, "delta": -1.0 + noise[2]},
            {"geometry": "b", "lag": 40, "seed": seed, "delta": -0.5 + noise[3]},
        ]
    per_g, pair = lag_geometry_interaction(pd.DataFrame(rows), "delta")
    trends = dict(zip(per_g["geometry"], per_g["trend"]))
    assert trends == {"a": "amplifies", "b": "attenuates"}
    assert pair.iloc[0]["interaction"] == pytest.approx(-1.0, abs=0.02)
    assert pair.iloc[0]["significant"]
