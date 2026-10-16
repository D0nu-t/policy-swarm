"""
Run the PolicySwarm factorial and write ``results/policyswarm_runs.csv``.

Each pre-audit choice is switched on or off independently:

gate_space   unit (angles from the cube corner, eps in [0,1] units) | centred
eps_mode     raw (one shared number) | matched (coverage-matched at t = 0)
             | run (cosine's realised pass rate over a run matched to
             Euclidean's; calibrated on pilot seeds 1000-1009, control runs,
             lag 20, in each gate_space x policy_pull corner)
policy_pull  gated (nudge only after a heard conversation) | anchor (ungated)

crossed with geometry {euclidean, cosine} and enforcement lag {0, 20, 40},
using Experiment 4's paired control / treatment design and the paper's
coupled timing (the policy pull starts at the lag). Euclidean's threshold is
the paper's 0.5 in unit-cube units, which is 1.0 in centred units: the same
Euclidean gate either way.

The pre-audit update bugs are not reintroduced; the paper's own numbers come
from ``policyswarm_output/`` and are only quoted.

    python run_policyswarm.py [--seeds 100] [--workers 11] [--modes raw matched]
    python run_policyswarm.py --modes run --tag _run      # the run-matched arm
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from policyswarm.analysis import lag_geometry_interaction
from policyswarm.config import Geometry, GovernanceConfig, ShockConfig, ShockMode, SimConfig
from policyswarm.experiments.base import BASELINE_GOVERNANCE, run_paired
from policyswarm.extraction import DEFAULT_POLICY_TEXT, policy_from_text
from policyswarm.geometry import matched_epsilons
from policyswarm.shocks import generate_shocks

GATE_SPACES = ("unit", "centred")
EPS_MODES = ("raw", "matched", "run")
PILOT_SEEDS = range(1000, 1010)
PULLS = ("gated", "anchor")
GEOMETRIES = (Geometry.EUCLIDEAN, Geometry.COSINE)
LAGS = (0, 20, 40)
REFERENCE_EPS = {"unit": 0.5, "centred": 1.0}
OUT = Path(__file__).parent / "results"


def sim_config(space: str, pull: str) -> SimConfig:
    return dataclasses.replace(SimConfig(), gate_space=space, policy_pull=pull,
                               epsilon=REFERENCE_EPS[space])


def thresholds(seeds) -> dict:
    """eps per (space, mode, geometry). Matching ignores the pull switch:
    it only looks at the t = 0 opinions."""
    out = {}
    for space in GATE_SPACES:
        sc = sim_config(space, "anchor")
        matched, _ = matched_epsilons(sc, GEOMETRIES, seeds=seeds)
        for g in GEOMETRIES:
            out[(space, "raw", g.value)] = sc.epsilon
            out[(space, "matched", g.value)] = matched[g.value]
    return out


def _realised_pass(space, pull, geometry, eps, seeds=PILOT_SEEDS, lag=20):
    """Mean realised gate pass rate of control runs at one eps."""
    from policyswarm.dynamics import Simulation

    sc = dataclasses.replace(sim_config(space, pull), epsilon=eps)
    policy = policy_from_text(DEFAULT_POLICY_TEXT)
    policy.lag = lag
    gov = GovernanceConfig(**BASELINE_GOVERNANCE, enforcement_lag=lag, policy_pull_onset=None)
    rates = []
    for seed in seeds:
        sim = Simulation(sc, gov, policy, [], apply_shocks=False, seed=seed, geometry=geometry)
        sim.run()
        rates.append(sim.gate_pass_rate)
    return sum(rates) / len(rates)


def _calibrate_run(corner, tol=0.005, max_iter=25):
    """Cosine eps whose realised pass rate matches Euclidean's in one corner."""
    space, pull = corner
    target = _realised_pass(space, pull, Geometry.EUCLIDEAN, REFERENCE_EPS[space])
    lo, hi = 0.0, 2.0
    for _ in range(max_iter):
        eps = 0.5 * (lo + hi)
        rate = _realised_pass(space, pull, Geometry.COSINE, eps)
        if abs(rate - target) <= tol:
            break
        lo, hi = (eps, hi) if rate < target else (lo, eps)
    return corner, eps, target, rate


def _run(job):
    space, mode, pull, geometry, lag, seed, eps = job
    sc = dataclasses.replace(sim_config(space, pull), epsilon=eps)
    policy = policy_from_text(DEFAULT_POLICY_TEXT)
    policy.lag = lag
    gov = GovernanceConfig(**BASELINE_GOVERNANCE, enforcement_lag=lag, policy_pull_onset=None)
    shocks = generate_shocks(ShockConfig(mode=ShockMode.COORDINATING), sc.n_ticks, seed)
    m_c, m_t = run_paired(sc, gov, policy, shocks, seed, Geometry(geometry))
    delta = m_t["variance"] - m_c["variance"]
    return {"gate_space": space, "eps_mode": mode, "policy_pull": pull, "geometry": geometry,
            "epsilon": eps, "lag": lag, "seed": seed,
            "control_var": m_c["variance"], "treat_var": m_t["variance"],
            "delta": delta, "rel_delta": delta / m_c["variance"],
            "gate_pass_ctrl": m_c["gate_pass_rate"], "gate_pass_treat": m_t["gate_pass_rate"]}


def interactions(df: pd.DataFrame) -> pd.DataFrame:
    """Lag x geometry interaction (Euclidean minus cosine) in every cell."""
    rows = []
    for (space, mode, pull), cell in df.groupby(["gate_space", "eps_mode", "policy_pull"]):
        for col in ("delta", "rel_delta"):
            per_g, pair = lag_geometry_interaction(cell, col)
            trend = dict(zip(per_g["geometry"], per_g["trend"]))
            contrast = dict(zip(per_g["geometry"], per_g["contrast"]))
            p = pair.iloc[0]
            rows.append({"gate_space": space, "eps_mode": mode, "policy_pull": pull,
                         "value": col, "pair": f"{p['geometry_a']}-{p['geometry_b']}",
                         "euclidean_contrast": contrast.get("euclidean"),
                         "cosine_contrast": contrast.get("cosine"),
                         "euclidean_trend": trend.get("euclidean"),
                         "cosine_trend": trend.get("cosine"),
                         "interaction": p["interaction"], "ci_low": p["interaction_ci_low"],
                         "ci_high": p["interaction_ci_high"], "p_value": p["p_value"]})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=11)
    ap.add_argument("--modes", nargs="+", default=["raw", "matched"], choices=EPS_MODES)
    ap.add_argument("--tag", default="", help="suffix for the output files")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    seeds = list(range(args.seeds))

    t = time.time()
    eps = thresholds(seeds)
    if "run" in args.modes:
        corners = list(itertools.product(GATE_SPACES, PULLS))
        with ProcessPoolExecutor(args.workers) as pool:
            for (space, pull), e, target, rate in pool.map(_calibrate_run, corners):
                eps[(space, "run", pull, "cosine")] = e
                eps[(space, "run", pull, "euclidean")] = REFERENCE_EPS[space]
                print(f"run-matched {space}/{pull}: cosine eps {e:.4f}, "
                      f"pass {rate:.3f} vs Euclidean {target:.3f}", flush=True)
    pd.DataFrame([{"key": "/".join(map(str, k)), "epsilon": e} for k, e in eps.items()]).to_csv(
        OUT / f"policyswarm_thresholds{args.tag}.csv", index=False)

    def eps_for(s, m, p, g):
        return eps[(s, m, p, g)] if m == "run" else eps[(s, m, g)]

    jobs = [(s, m, p, g.value, lag, seed, eps_for(s, m, p, g.value))
            for s, m, p, g, lag, seed in itertools.product(
                GATE_SPACES, args.modes, PULLS, GEOMETRIES, LAGS, seeds)]
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for k, row in enumerate(pool.map(_run, jobs, chunksize=10), 1):
            rows.append(row)
            if k % 500 == 0:
                print(f"{k}/{len(jobs)} paired runs, {time.time() - t:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"policyswarm_runs{args.tag}.csv", index=False)
    inter = interactions(df)
    inter.to_csv(OUT / f"policyswarm_interactions{args.tag}.csv", index=False)
    print(inter[inter["value"] == "rel_delta"].to_string(index=False))
    print(f"done: {len(jobs)} paired runs in {time.time() - t:.0f} s")


if __name__ == "__main__":
    main()
