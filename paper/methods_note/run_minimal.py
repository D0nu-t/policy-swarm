"""
Run the minimal-model factorial and write ``results/minimal_runs.csv``.

Design: space {unit, centred} x dimension {2, 4, 8} x reference coverage
{5%, 15%, 30%}. In each cell Euclidean runs at the threshold that gives the
reference coverage at t = 0. Cosine and angular ("manifold") each run under
three threshold rules:

raw         the same number as Euclidean's eps (the common practice)
t0          eps giving the same coverage of uniform pairs at t = 0
run         eps giving the same pass rate averaged over a whole run as
            Euclidean's (calibrated on pilot seeds 1000-1009, not reused)

Seeds 0-99, paired across every rule in a cell.

    python run_minimal.py [--seeds 100] [--workers 11]
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
TARGETS = (0.05, 0.15, 0.30)
ANGULAR = ("cosine", "manifold")
PILOT_SEEDS = range(1000, 1010)
OUT = Path(__file__).parent / "results"
FIELDS = ["space", "d", "target", "metric", "mode", "eps", "seed", "variance", "dispersion",
          "clusters", "eff_clusters", "pass_rate", "converged_at"]


def _thresholds(cell):
    """All (metric, mode, eps) to run in one (space, d, target) cell."""
    space, d, target = cell
    ref = cov.matched_epsilon("euclidean", space, d, target)
    ref_rate = mbc.mean_pass_rate("euclidean", space, d, ref, PILOT_SEEDS)
    rows = [(cell, "euclidean", "reference", ref)]
    for metric in ANGULAR:
        rows.append((cell, metric, "raw", ref))
        rows.append((cell, metric, "t0", cov.matched_epsilon(metric, space, d, target)))
        rows.append((cell, metric, "run",
                     mbc.calibrate_run_average(metric, space, d, ref_rate, PILOT_SEEDS)))
    return rows


def _run(job):
    (space, d, target), metric, mode, eps, seed = job
    r = mbc.simulate(metric, space, d, eps, seed)
    return {"space": space, "d": d, "target": target, "metric": metric, "mode": mode,
            "eps": eps, "seed": seed, **{k: r[k] for k in FIELDS[7:]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=11)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    cells = list(itertools.product(SPACES, DIMS, TARGETS))

    t = time.time()
    with ProcessPoolExecutor(args.workers) as pool:
        thresholds = [row for rows in pool.map(_thresholds, cells) for row in rows]
    with open(OUT / "minimal_thresholds.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["space", "d", "target", "metric", "mode", "eps"])
        for (space, d, target), metric, mode, eps in thresholds:
            w.writerow([space, d, target, metric, mode, eps])
    print(f"thresholds: {len(thresholds)} in {time.time() - t:.0f} s", flush=True)

    jobs = [(*row, seed) for row in thresholds for seed in range(args.seeds)]
    with open(OUT / "minimal_runs.csv", "w", newline="") as f, \
            ProcessPoolExecutor(args.workers) as pool:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k, row in enumerate(pool.map(_run, jobs, chunksize=20), 1):
            w.writerow(row)
            if k % 1000 == 0:
                print(f"{k}/{len(jobs)} runs, {time.time() - t:.0f} s", flush=True)
    print(f"done: {len(jobs)} runs in {time.time() - t:.0f} s")


if __name__ == "__main__":
    main()
