"""
eps-response curves for the minimal model: ``results/minimal_curves_v2.csv``.

For each space {unit, centred} and dimension {2, 4, 8}, each metric runs at
the eps values that admit COVERAGES of uniform pairs at t = 0, so every curve
spans the same range of starting coverage. Each run records its realised pass
rate over 2,000 rounds and every outcome, so outcomes can be plotted against
realised coverage with no single matched point privileged. The matched points
from run_minimal.py sit on these curves.

    python run_curves.py [--seeds 50] [--workers 10]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import coverage as cov
import minimal_bc as mbc

SPACES = ("unit", "centred")
DIMS = (2, 4, 8)
METRICS = ("euclidean", "cosine", "manifold")
COVERAGES = (0.02, 0.03, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60)
ROUNDS = 2000
SEED_OFFSET = 2000          # disjoint from the factorial (0-99) and pilots (1000-1049)
OUT = Path(__file__).parent / "results"


def _run(job):
    space, d, metric, coverage, eps, seed = job
    r = mbc.simulate(metric, space, d, eps, seed, rounds=ROUNDS)
    keep = {k: v for k, v in r.items() if k not in ("edges", "final", "at")}
    return {"space": space, "d": d, "metric": metric, "start_coverage": coverage,
            "eps": eps, "seed": seed, **keep}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t = time.time()
    jobs = []
    for space, d, metric in itertools.product(SPACES, DIMS, METRICS):
        for c in COVERAGES:
            eps = cov.matched_epsilon(metric, space, d, c)
            jobs += [(space, d, metric, c, eps, SEED_OFFSET + s) for s in range(args.seeds)]
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for k, row in enumerate(pool.map(_run, jobs, chunksize=10), 1):
            rows.append(row)
            if k % 1000 == 0:
                print(f"{k}/{len(jobs)} runs, {time.time() - t:.0f} s", flush=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with open(OUT / "minimal_curves_v2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"done: {len(jobs)} runs in {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
