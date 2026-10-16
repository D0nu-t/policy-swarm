"""
Run the minimal-model experiments (revision round) and write ``results/*_v2.csv``.

Designs (``--design``):

factorial   space {unit, centred} x dimension {2, 4, 8} x reference coverage
            {5%, 15%, 30%}. Euclidean runs at the eps giving the reference
            coverage at t = 0; cosine and angular ("manifold") each run under
            three threshold rules:
                raw   the same number as Euclidean's eps
                t0    eps giving the same coverage of uniform pairs at t = 0
                run   eps giving the same pass rate over the first 2,000 rounds
                      as Euclidean's (bisection on pilot seeds 1000-1049, not
                      reused; the calibration report is saved)
            Runs last 4,000 rounds; every outcome is recorded after 500,
            1,000, 2,000 and 4,000 rounds (the horizon sweep).
crossing    the same cells with the gate and the update rule crossed: a
            cosine gate (t0-matched) with a Euclidean step, and a Euclidean
            gate with a cosine step, beside the pure pairings, 2,000 rounds.

Seeds 0-99, paired across every rule in a cell.

    python run_minimal.py --design factorial [--seeds 100] [--workers 10]
    python run_minimal.py --design crossing
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
PILOT_SEEDS = range(1000, 1050)
CALIBRATION_ROUNDS = 2000
ROUNDS = 4000
CHECKPOINTS = (500, 1000, 2000, 4000)
OUT = Path(__file__).parent / "results"
CELL = ("space", "d", "target")


def _previous_run_eps() -> dict:
    """Round-1 run-matched eps per cell, used only to narrow the bisection."""
    path = OUT / "minimal_thresholds.csv"
    prev = {}
    if path.exists():
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if row["mode"] == "run":
                    key = (row["space"], int(row["d"]), float(row["target"]), row["metric"])
                    prev[key] = float(row["eps"])
    return prev


def _thresholds(job):
    (space, d, target), prev = job
    ref = cov.matched_epsilon("euclidean", space, d, target)
    ref_rate = mbc.mean_pass_rate("euclidean", space, d, ref, PILOT_SEEDS,
                                  rounds=CALIBRATION_ROUNDS)
    rows = [{"space": space, "d": d, "target": target, "metric": "euclidean",
             "mode": "reference", "eps": ref, "achieved": ref_rate}]
    for metric in ANGULAR:
        rows.append({"space": space, "d": d, "target": target, "metric": metric,
                     "mode": "raw", "eps": ref})
        rows.append({"space": space, "d": d, "target": target, "metric": metric,
                     "mode": "t0", "eps": cov.matched_epsilon(metric, space, d, target)})
        old = prev.get((space, d, target, metric))
        bracket = (0.5 * old, 1.6 * old) if old else None
        rep = mbc.calibrate_report(metric, space, d, ref_rate, PILOT_SEEDS,
                                   rounds=CALIBRATION_ROUNDS, bracket=bracket)
        rows.append({"space": space, "d": d, "target": target, "metric": metric,
                     "mode": "run", **{k: rep[k] for k in
                                       ("eps", "achieved", "error", "iterations",
                                        "within_tol", "monotone")}})
    return rows


def _run_factorial(job):
    row, seed = job
    r = mbc.simulate(row["metric"], row["space"], row["d"], row["eps"], seed,
                     rounds=ROUNDS, checkpoints=CHECKPOINTS)
    base = {k: row[k] for k in (*CELL, "metric", "mode", "eps")}
    out = []
    for cp, snap in sorted(r["at"].items()):
        out.append({**base, "seed": seed, "checkpoint": cp, **snap,
                    "converged_at": r["converged_at"], "clip_rate": r["clip_rate"]})
    return out


def _run_crossing(job):
    cell, gate, step, eps, seed = job
    space, d, target = cell
    r = mbc.simulate(gate, space, d, eps, seed, step_metric=step, rounds=CALIBRATION_ROUNDS)
    keep = {k: v for k, v in r.items() if k not in ("edges", "final", "at")}
    return {"space": space, "d": d, "target": target, "gate": gate, "step": step,
            "eps": eps, "seed": seed, **keep}


def _write(path: Path, rows):
    rows = list(rows)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _load_thresholds(path: Path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            row["d"], row["target"], row["eps"] = int(row["d"]), float(row["target"]), float(row["eps"])
            rows.append(row)
    return rows


def factorial(args, t):
    """Calibrate (or reuse saved thresholds), then run every job, writing each
    run's rows as soon as it finishes so a crash loses nothing; on a restart,
    runs already in the file are skipped."""
    tpath, rpath = OUT / "minimal_thresholds_v2.csv", OUT / "minimal_runs_v2.csv"
    if tpath.exists() and not args.recalibrate:
        thresholds = _load_thresholds(tpath)
        print(f"reusing {len(thresholds)} saved thresholds", flush=True)
    else:
        cells = list(itertools.product(SPACES, DIMS, TARGETS))
        prev = _previous_run_eps()
        with ProcessPoolExecutor(args.workers) as pool:
            thresholds = [r for rows in pool.map(_thresholds, [(c, prev) for c in cells]) for r in rows]
        _write(tpath, thresholds)
        misses = [r for r in thresholds if r.get("within_tol") is False]
        print(f"thresholds: {len(thresholds)} in {time.time() - t:.0f} s; "
              f"{len(misses)} calibrations outside tolerance", flush=True)

    key = lambda r: (r["space"], str(r["d"]), f"{float(r['target']):g}", r["metric"], r["mode"], str(r["seed"]))  # noqa: E731
    done = set()
    if rpath.exists():
        with open(rpath, newline="") as f:
            done = {key(r) for r in csv.DictReader(f)}
    jobs = [(row, seed) for row in thresholds for seed in range(args.seeds)
            if key({**row, "seed": seed}) not in done]
    print(f"{len(done)} runs already saved; {len(jobs)} to go", flush=True)

    probe = mbc.simulate("euclidean", "unit", 2, 0.3, 0, n=40, rounds=CHECKPOINTS[0],
                         checkpoints=CHECKPOINTS[:1])
    fields = [*CELL, "metric", "mode", "eps", "seed", "checkpoint", *probe["at"][CHECKPOINTS[0]],
              "converged_at", "clip_rate"]
    new_file = not rpath.exists()
    with open(rpath, "a", newline="") as f, ProcessPoolExecutor(args.workers) as pool:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for k, rows in enumerate(pool.map(_run_factorial, jobs, chunksize=4), 1):
            w.writerows(rows)
            if k % 200 == 0:
                f.flush()
            if k % 1000 == 0:
                print(f"{k}/{len(jobs)} runs, {time.time() - t:.0f} s", flush=True)
    print(f"done: {len(jobs)} runs in {time.time() - t:.0f} s", flush=True)


def crossing(args, t):
    jobs = []
    for cell in itertools.product(SPACES, DIMS, TARGETS):
        space, d, target = cell
        ref = cov.matched_epsilon("euclidean", space, d, target)
        cos_eps = cov.matched_epsilon("cosine", space, d, target)
        for gate, step, eps in (("euclidean", "euclidean", ref), ("cosine", "cosine", cos_eps),
                                ("cosine", "euclidean", cos_eps), ("euclidean", "cosine", ref)):
            jobs += [(cell, gate, step, eps, seed) for seed in range(args.seeds)]
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for k, row in enumerate(pool.map(_run_crossing, jobs, chunksize=10), 1):
            rows.append(row)
            if k % 1000 == 0:
                print(f"{k}/{len(jobs)} runs, {time.time() - t:.0f} s", flush=True)
    _write(OUT / "minimal_crossing_v2.csv", rows)
    print(f"done: {len(jobs)} runs in {time.time() - t:.0f} s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", choices=("factorial", "crossing"), default="factorial")
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--recalibrate", action="store_true",
                    help="recompute the thresholds even if a saved file exists")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t = time.time()
    (factorial if args.design == "factorial" else crossing)(args, t)


if __name__ == "__main__":
    main()
