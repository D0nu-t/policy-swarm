"""
Which pre-audit difference produced the draft's geometry "reversal"?

The gate factorial (run_policyswarm.py) switches the threshold and policy-pull
choices on the *audited* engine and never reproduces the reversal. This
script goes the other way: it starts from the *pre-audit* engine, which does
reproduce it, and undoes the audit's other fixes one at a time.

Setup (once):

    git worktree add <dir> 50a42e5
    git -C <dir> apply paper/methods_note/preaudit_switches.patch

The patch adds two switches, read from the environment, to the old engine:

PS_FIX_COSINE=1  the audited cosine step (rotate the direction, keep the
                 magnitude) instead of adding a direction-space step to the
                 raw opinion
PS_FIX_RNG=1     shocks draw from their own random stream, so a treatment run
                 consumes no draws that its paired control run does not
PS_TRUST_CENTRE=1  an agent's trust shrinks the perceived policy toward the
                 neutral point (0.5) instead of toward 0, the cube corner
                 (the audited engine does this in centred coordinates)

and the tightening tick is set through SimConfig (pre-audit 40, audited 30).
Everything else is the pre-audit model: unit space, raw eps 0.5, gated
policy nudge, pull starting at the lag, run_all.py's policy text.

    python diagnose_reversal.py --preaudit <dir> [--seeds 100] [--workers 10]
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent / "results"
LAGS = (0, 20, 40)
GEOMETRIES = ("euclidean", "cosine")
# fix_cosine, fix_rng, split tick, trust centre
SWITCHES = [(*c, 0) for c in itertools.product((0, 1), (0, 1), (40, 30))]
TRUST_SWITCHES = [(0, 0, 40, 1), (1, 1, 30, 1)]


def _load_old(preaudit: str):
    """Import the pre-audit package from the worktree, not the installed one."""
    sys.meta_path[:] = [f for f in sys.meta_path if "__editable__" not in repr(f)
                        and "__editable__" not in getattr(f, "__name__", "")]
    sys.path.insert(0, preaudit)
    import policyswarm
    if not str(Path(policyswarm.__file__)).startswith(str(Path(preaudit))):
        raise RuntimeError(f"imported {policyswarm.__file__}, not the pre-audit worktree")
    return policyswarm


def _policy_text(preaudit: str) -> str:
    src = (Path(preaudit) / "run_all.py").read_text(encoding="utf-8")
    start = src.index('POLICY_TEXT = """') + len('POLICY_TEXT = """')
    return src[start:src.index('"""', start)]


def _job(args):
    preaudit, fix_cosine, fix_rng, split, trust_centre, geometry, lag, seed = args
    os.environ["PS_FIX_COSINE"] = str(fix_cosine)
    os.environ["PS_FIX_RNG"] = str(fix_rng)
    os.environ["PS_TRUST_CENTRE"] = str(trust_centre)
    _load_old(preaudit)
    from policyswarm.config import (Geometry, GovernanceConfig, ShockConfig, ShockMode,
                                    SimConfig)
    from policyswarm.dynamics import Simulation
    from policyswarm.extraction import policy_from_text
    from policyswarm.metrics import compute_all_metrics
    from policyswarm.shocks import generate_shocks

    policy = policy_from_text(_policy_text(preaudit))
    policy.lag = lag
    sc = SimConfig(opinion_dim=policy.dim, policy_split_tick=split)
    gov = GovernanceConfig(deployment_rate_cap=0.5, penalty_severity=0.5, enforcement_lag=lag)
    shocks = generate_shocks(ShockConfig(mode=ShockMode.COORDINATING), sc.n_ticks, seed)
    out = []
    for apply in (False, True):
        sim = Simulation(sc, gov, policy, shocks, apply_shocks=apply, seed=seed,
                         geometry=Geometry(geometry))
        sim.run()
        out.append(compute_all_metrics(sim)["variance"])
    return {"fix_cosine": fix_cosine, "fix_rng": fix_rng, "split_tick": split,
            "trust_centre": trust_centre,
            "geometry": geometry, "lag": lag, "seed": seed,
            "control_var": out[0], "treat_var": out[1], "delta": out[1] - out[0]}


def lag_index(df: pd.DataFrame) -> pd.DataFrame:
    """The draft's measure: |mean shock effect| by lag, lag 0 = 100."""
    keys = ["fix_cosine", "fix_rng", "split_tick", "trust_centre", "geometry"]
    rows = []
    for key, g in df.groupby(keys):
        m = g.groupby("lag")["delta"].mean()
        rows.append({**dict(zip(keys, key)),
                     **{f"lag{lag}": 100 * abs(m[lag]) / abs(m[0]) for lag in LAGS}})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preaudit", required=True)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--only-original", action="store_true",
                    help="run only the unpatched pre-audit model (a reproduction check)")
    ap.add_argument("--trust", action="store_true",
                    help="run the trust-centre variants (original and all-fixed)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    switches = ([(0, 0, 40, 0)] if args.only_original
                else TRUST_SWITCHES if args.trust else SWITCHES)
    jobs = [(args.preaudit, fc, fr, sp, tc, g, lag, seed)
            for (fc, fr, sp, tc) in switches for g in GEOMETRIES for lag in LAGS
            for seed in range(args.seeds)]
    t = time.time()
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for k, row in enumerate(pool.map(_job, jobs, chunksize=10), 1):
            rows.append(row)
            if k % 500 == 0:
                print(f"{k}/{len(jobs)} paired runs, {time.time() - t:.0f} s", flush=True)
    df = pd.DataFrame(rows)
    tag = "_check" if args.only_original else "_trust" if args.trust else ""
    df.to_csv(OUT / f"diagnosis_runs{tag}.csv", index=False)
    idx = lag_index(df)
    idx.to_csv(OUT / f"diagnosis_lag_index{tag}.csv", index=False)
    print(idx.round(0).to_string(index=False))
    print(f"done: {len(jobs)} paired runs in {time.time() - t:.0f} s")


if __name__ == "__main__":
    main()
