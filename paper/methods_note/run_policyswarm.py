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


def sim_config(space: str, pull: str, anchor: str = "centre") -> SimConfig:
    return dataclasses.replace(SimConfig(), gate_space=space, policy_pull=pull,
                               trust_anchor=anchor, epsilon=REFERENCE_EPS[space])


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


def _realised_pass(space, pull, geometry, eps, seeds=PILOT_SEEDS, lag=20, anchor="centre"):
    """Mean realised gate pass rate of control runs at one eps."""
    from policyswarm.dynamics import Simulation

    sc = dataclasses.replace(sim_config(space, pull, anchor), epsilon=eps)
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
    """Cosine eps whose realised pass rate matches Euclidean's in one corner
    (space, pull[, trust anchor])."""
    space, pull, anchor = (*corner, "centre")[:3]
    target = _realised_pass(space, pull, Geometry.EUCLIDEAN, REFERENCE_EPS[space], anchor=anchor)
    lo, hi = 0.0, 2.0
    for _ in range(max_iter):
        eps = 0.5 * (lo + hi)
        rate = _realised_pass(space, pull, Geometry.COSINE, eps, anchor=anchor)
        if abs(rate - target) <= tol:
            break
        lo, hi = (eps, hi) if rate < target else (lo, eps)
    return corner, eps, target, rate


def _run(job):
    space, mode, pull, geometry, lag, seed, eps, anchor = (*job, "centre")[:8]
    sc = dataclasses.replace(sim_config(space, pull, anchor), epsilon=eps)
    policy = policy_from_text(DEFAULT_POLICY_TEXT)
    policy.lag = lag
    gov = GovernanceConfig(**BASELINE_GOVERNANCE, enforcement_lag=lag, policy_pull_onset=None)
    shocks = generate_shocks(ShockConfig(mode=ShockMode.COORDINATING), sc.n_ticks, seed)
    m_c, m_t = run_paired(sc, gov, policy, shocks, seed, Geometry(geometry))
    delta = m_t["variance"] - m_c["variance"]
    return {"gate_space": space, "eps_mode": mode, "policy_pull": pull,
            "trust_anchor": anchor, "geometry": geometry,
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


def _collect(jobs, args, t, tag):
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for k, row in enumerate(pool.map(_run, jobs, chunksize=10), 1):
            rows.append(row)
            if k % 500 == 0:
                print(f"{k}/{len(jobs)} paired runs, {time.time() - t:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"policyswarm_runs_{tag}.csv", index=False)
    print(f"done: {len(jobs)} paired runs in {time.time() - t:.0f} s", flush=True)
    return df


def trust_designs(args, seeds):
    """The revision's case designs (see --design)."""
    t = time.time()
    jobs = []
    if args.design == "trust":
        for space, anchor in itertools.product(GATE_SPACES, ("corner", "centre")):
            jobs += [(space, "raw", "gated", g.value, lag, s, REFERENCE_EPS[space], anchor)
                     for g, lag, s in itertools.product(GEOMETRIES, LAGS, seeds)]
        jobs += [("unit", "raw", "gated", g.value, lag, s, REFERENCE_EPS["unit"], "level_shift")
                 for g, lag, s in itertools.product(GEOMETRIES, LAGS, seeds)]
        return _collect(jobs, args, t, "trust_v2")
    anchors = ("corner", "centre", "status_quo", "own")
    corners = [("centred", "anchor", a) for a in anchors]
    with ProcessPoolExecutor(args.workers) as pool:
        calib = {c[2]: (e, target, rate) for c, e, target, rate in pool.map(_calibrate_run, corners)}
    pd.DataFrame([{"trust_anchor": a, "cosine_eps": e, "target": tg, "achieved": r}
                  for a, (e, tg, r) in calib.items()]).to_csv(
        OUT / "policyswarm_thresholds_anchors_v2.csv", index=False)
    for a in anchors:
        print(f"anchor {a}: cosine eps {calib[a][0]:.4f}, pass {calib[a][2]:.3f} "
              f"vs Euclidean {calib[a][1]:.3f}", flush=True)
        for g, lag, s in itertools.product(GEOMETRIES, LAGS, seeds):
            eps = REFERENCE_EPS["centred"] if g == Geometry.EUCLIDEAN else calib[a][0]
            jobs.append(("centred", "run", "anchor", g.value, lag, s, eps, a))
            jobs.append(("unit", "raw", "gated", g.value, lag, s, REFERENCE_EPS["unit"], a))
    return _collect(jobs, args, t, "anchors_v2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=11)
    ap.add_argument("--modes", nargs="+", default=["raw", "matched"], choices=EPS_MODES)
    ap.add_argument("--tag", default="", help="suffix for the output files")
    ap.add_argument("--design", choices=("factorial", "trust", "anchors"), default="factorial",
                    help="factorial: the gate factorial; trust: trust anchor (corner/centre) x "
                         "gate space with the draft's shared eps and gated pull, plus the "
                         "level-shift control; anchors: all four trust anchors in the draft "
                         "setting and in the recommended (centred, run-matched, anchor) one")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    seeds = list(range(args.seeds))
    if args.design != "factorial":
        return trust_designs(args, seeds)

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
