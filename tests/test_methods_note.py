"""Tests for the methods-note analysis code in ``paper/methods_note``."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper" / "methods_note"))

import coverage as cov  # noqa: E402


# --- pass fractions --------------------------------------------------------

def test_reproduces_audit_pass_fractions():
    # Audit (Sep 2026): uniform opinions in [0,1]^4 at eps = 0.5 passed the
    # gate 13% (Euclidean), 94% (cosine), 31% (angular) of the time.
    got = {m: cov.pass_fraction(m, "unit", 4, 0.5, n_pairs=200_000, seed=1)
           for m in ("euclidean", "cosine", "manifold")}
    assert got["euclidean"] == pytest.approx(0.13, abs=0.02)
    assert got["cosine"] == pytest.approx(0.94, abs=0.02)
    assert got["manifold"] == pytest.approx(0.31, abs=0.02)


@pytest.mark.slow
def test_monte_carlo_matches_quadrature_in_two_dimensions():
    for metric in ("euclidean", "cosine"):
        for space in ("unit", "centred"):
            mc = cov.pass_fraction(metric, space, 2, 0.4, n_pairs=400_000, seed=2)
            exact = cov.pass_fraction_quadrature(metric, space, 0.4, grid=120)
            assert mc == pytest.approx(exact, abs=0.01), (metric, space)


def test_matched_cosine_and_angular_admit_the_same_pairs():
    a, b = cov.sample_pairs("centred", 4, 50_000, np.random.default_rng(3))
    eps = cov.matched_epsilon("cosine", "centred", 4, target=0.2, n_pairs=50_000, seed=3)
    eps_m = cov.matched_epsilon("manifold", "centred", 4, target=0.2, n_pairs=50_000, seed=3)
    passes_c = cov.distances("cosine", a, b) <= eps
    passes_m = cov.distances("manifold", a, b) <= eps_m
    assert np.mean(passes_c != passes_m) < 1e-3


def test_matched_epsilon_hits_its_target():
    for metric in ("euclidean", "cosine", "manifold"):
        eps = cov.matched_epsilon(metric, "unit", 4, target=0.15, n_pairs=100_000, seed=4)
        frac = cov.pass_fraction(metric, "unit", 4, eps, n_pairs=100_000, seed=4)
        assert frac == pytest.approx(0.15, abs=0.005)


def test_unknown_space_is_rejected():
    with pytest.raises(ValueError):
        cov.sample_pairs("sphere", 3, 10, np.random.default_rng(0))


# --- minimal bounded-confidence model --------------------------------------

import minimal_bc as mbc  # noqa: E402
from policyswarm.config import Geometry  # noqa: E402
from policyswarm.geometry import step as engine_step  # noqa: E402


@pytest.mark.parametrize("metric", ["euclidean", "cosine", "manifold"])
def test_batch_step_matches_engine_step(metric):
    rng = np.random.default_rng(5)
    a, b = rng.uniform(-1, 1, (50, 4)), rng.uniform(-1, 1, (50, 4))
    got = mbc.step_batch(metric, a, b, 0.3)
    want = np.array([engine_step(Geometry(metric), a[k], b[k], 0.3) for k in range(50)])
    assert np.allclose(got, want)


def test_matching_has_no_shared_agents():
    rng = np.random.default_rng(6)
    edges = mbc.build_graph(200, 10, rng)
    m = mbc.random_matching(edges, rng)
    nodes = m.ravel()
    assert len(nodes) == len(set(nodes.tolist())) and len(m) > 20


def test_runs_are_paired_across_metrics():
    r1 = mbc.simulate("euclidean", "centred", 3, 0.5, seed=7, n=100, rounds=5, keep_initial=True)
    r2 = mbc.simulate("cosine", "centred", 3, 0.5, seed=7, n=100, rounds=5, keep_initial=True)
    assert np.array_equal(r1["initial"], r2["initial"])
    assert np.array_equal(r1["edges"], r2["edges"])


def test_zero_threshold_freezes_everyone():
    r = mbc.simulate("euclidean", "unit", 2, 0.0, seed=8, n=100, rounds=20, keep_initial=True)
    assert r["pass_rate"] == 0.0
    assert np.array_equal(r["initial"], r["final"])


def test_wide_threshold_gives_consensus():
    r = mbc.simulate("euclidean", "unit", 2, 10.0, seed=9, n=100, rounds=400)
    assert r["clusters"] == 1 and r["variance"] < 1e-4


def test_run_average_calibration_hits_target():
    target = mbc.simulate("euclidean", "centred", 4, 1.0, seed=10, n=120, rounds=60)["pass_rate"]
    eps = mbc.calibrate_run_average("cosine", "centred", 4, target, seeds=[10, 11],
                                    n=120, rounds=60, tol=0.01)
    got = np.mean([mbc.simulate("cosine", "centred", 4, eps, seed=s, n=120, rounds=60)["pass_rate"]
                   for s in (10, 11)])
    assert got == pytest.approx(target, abs=0.02)


# --- revision features: crossing, checkpoints, rulers, calibration report ---

def test_gate_and_step_can_be_crossed():
    a = mbc.simulate("cosine", "centred", 3, 0.4, seed=12, n=100, rounds=50)
    b = mbc.simulate("cosine", "centred", 3, 0.4, seed=12, n=100, rounds=50, step_metric="euclidean")
    assert not np.array_equal(a["final"], b["final"])


def test_checkpoints_record_outcomes_and_end_matches_final():
    r = mbc.simulate("euclidean", "centred", 2, 0.6, seed=13, n=100, rounds=60,
                     checkpoints=(20, 60))
    assert set(r["at"]) == {20, 60}
    for key in ("variance", "groups_common", "eff_groups_common", "clusters_r0.05",
                "radial_var", "pass_rate", "settled"):
        assert key in r["at"][20]
    assert r["at"][60]["variance"] == pytest.approx(r["variance"])


def test_common_ruler_counts_one_group_at_consensus():
    r = mbc.simulate("cosine", "centred", 2, 2.0, seed=14, n=100, rounds=400, checkpoints=(400,))
    assert r["at"][400]["groups_common"] >= 1


def test_measure_off_skips_groups():
    r = mbc.simulate("euclidean", "unit", 2, 0.3, seed=15, n=80, rounds=10, measure=False)
    assert "clusters" not in r and "pass_rate" in r


def test_calibration_report_flags_misses():
    target = mbc.simulate("euclidean", "centred", 4, 1.0, seed=10, n=120, rounds=60,
                          measure=False)["pass_rate"]
    rep = mbc.calibrate_report("cosine", "centred", 4, target, seeds=[10, 11],
                               n=120, rounds=60, tol=0.01)
    assert {"eps", "achieved", "error", "iterations", "within_tol", "monotone"} <= set(rep)
    bad = mbc.calibrate_report("cosine", "centred", 4, 1.5, seeds=[10], n=60, rounds=20,
                               tol=0.001, max_iter=3)
    assert bad["within_tol"] is False
