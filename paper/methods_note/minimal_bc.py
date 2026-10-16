"""
A minimal bounded-confidence model for the methods note.

The only thing that differs between runs being compared is the distance
used by the confidence gate (and its threshold). There is no media, policy,
shocks or influence weights, so any difference between metrics comes from
the gate and from the update rule, nothing else.

Model
-----
* ``n`` agents on an Erdős–Rényi graph with mean degree ``k``; opinions
  uniform in the unit cube [0,1]^d or the centred cube [-1,1]^d.
* Each round draws a random matching of the graph's edges (no agent in two
  pairs), so every update in a round is independent and can be vectorised.
  For each matched pair within ``eps`` under the metric, both agents move a
  fraction ``mu`` toward the other's old opinion (Deffuant et al. 2000),
  using PolicySwarm's update for that metric, then are clipped to the cube.
* Seeds are paired: a seed fixes the graph, the initial opinions and the
  sequence of matchings, whatever the metric.

Outcomes
--------
variance       mean per-dimension variance of final opinions
dispersion     1 - |mean of unit opinion vectors| (direction spread)
clusters       opinion groups holding >= 1% of agents: components of the
               graph joining final opinions within 0.1 * eps under the
               metric (tight, so groups do not chain through stragglers)
eff_clusters   1 / sum(share^2) over all components
pass_rate      share of matched pairs within eps, over the whole run
converged_at   first round after which no matched pair moved more than 1e-4
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from coverage import distances, sample_opinions

_NORM_EPS = 1e-12
CONVERGED = 1e-4          # largest move in a round that still counts as settled
CLUSTER_FRACTION = 0.1   # opinions within this share of eps form one group


# --- graph and matchings ---------------------------------------------------

def build_graph(n: int, k: float, rng: np.random.Generator) -> np.ndarray:
    """Edges (m, 2) of an Erdős–Rényi graph with mean degree about ``k``."""
    m = int(round(n * k / 2))
    u = rng.integers(0, n, size=3 * m)
    v = rng.integers(0, n, size=3 * m)
    keep = u != v
    pairs = np.sort(np.column_stack([u[keep], v[keep]]), axis=1)
    _, first = np.unique(pairs, axis=0, return_index=True)
    return pairs[np.sort(first)][:m]


def random_matching(edges: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A random set of edges with no agent in two of them.

    An edge is kept when it comes first, in a random order, among all edges
    touching either of its agents.
    """
    order = rng.permutation(len(edges))
    e = edges[order]
    n = int(edges.max()) + 1
    first = np.full(n, len(e))
    pos = np.arange(len(e))
    np.minimum.at(first, e[:, 0], pos)
    np.minimum.at(first, e[:, 1], pos)
    keep = (first[e[:, 0]] == pos) & (first[e[:, 1]] == pos)
    return e[keep]


# --- vectorised updates (same arithmetic as policyswarm.geometry.step) -----

def step_batch(metric: str, a: np.ndarray, b: np.ndarray, rate: float) -> np.ndarray:
    """Move each row of ``a`` toward the matching row of ``b`` by ``rate``."""
    if metric == "euclidean":
        return a + rate * (b - a)
    na = np.linalg.norm(a, axis=1)
    nb = np.linalg.norm(b, axis=1)
    ok = (na > _NORM_EPS) & (nb > _NORM_EPS)
    ua = a / np.where(ok, na, 1.0)[:, None]
    ub = b / np.where(ok, nb, 1.0)[:, None]
    if metric == "cosine":
        moved = ua + rate * (ub - ua)
        nm = np.linalg.norm(moved, axis=1)
        ok &= nm > _NORM_EPS
        out = na[:, None] * moved / np.where(ok, nm, 1.0)[:, None]
    elif metric == "manifold":
        cos = np.clip(np.sum(ua * ub, axis=1), -1.0, 1.0)
        theta = np.arccos(cos)
        tangent = ub - cos[:, None] * ua
        nt = np.linalg.norm(tangent, axis=1)
        ok &= (theta >= 1e-12) & (nt > _NORM_EPS)
        angle = rate * theta
        direction = tangent / np.where(ok, nt, 1.0)[:, None]
        out = na[:, None] * (np.cos(angle)[:, None] * ua + np.sin(angle)[:, None] * direction)
    else:
        raise ValueError(f"unknown metric {metric!r}")
    return np.where(ok[:, None], out, a)


# --- one run ---------------------------------------------------------------

def _bounds(space: str):
    return (0.0, 1.0) if space == "unit" else (-1.0, 1.0)


def _groups(metric: str, x: np.ndarray, eps: float):
    """Component sizes of the 'within eps' graph on final opinions."""
    n = len(x)
    i, j = np.triu_indices(n, k=1)
    close = distances(metric, x[i], x[j]) <= eps
    graph = coo_matrix((np.ones(close.sum()), (i[close], j[close])), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    return np.bincount(labels)


#: Group radii as fractions of eps, each in the run's own metric (a ruler that
#: changes with the metric, kept for comparison with the paper's first draft).
RADIUS_FRACTIONS = (0.01, 0.05, 0.2)
#: The common ruler: Euclidean distance in centred coordinates, as a fraction
#: of the centred cube's diagonal (2 * sqrt(d)). Same for every metric.
COMMON_RADIUS = 0.05


def _shares(sizes: np.ndarray, n: int):
    shares = sizes / n
    return int(np.sum(shares >= max(0.01, 2 / n))), float(1.0 / np.sum(shares ** 2))


def outcomes(metric: str, space: str, x: np.ndarray, eps: float) -> dict:
    """Every outcome of a final (or checkpoint) state."""
    n, d = x.shape
    norms = np.linalg.norm(x, axis=1)
    units = x[norms > _NORM_EPS] / norms[norms > _NORM_EPS, None]
    out = {
        "variance": float(x.var(axis=0).mean()),
        "radial_var": float(norms.var()),
        "dispersion": float(1.0 - np.linalg.norm(units.mean(axis=0))) if len(units) else 1.0,
    }
    out["clusters"], out["eff_clusters"] = _shares(_groups(metric, x, CLUSTER_FRACTION * eps), n)
    for f in RADIUS_FRACTIONS:
        out[f"clusters_r{f:g}"], out[f"eff_clusters_r{f:g}"] = _shares(_groups(metric, x, f * eps), n)
    centred = 2.0 * x - 1.0 if space == "unit" else x
    radius = COMMON_RADIUS * 2.0 * np.sqrt(d)
    out["groups_common"], out["eff_groups_common"] = _shares(_groups("euclidean", centred, radius), n)
    return out


def simulate(metric: str, space: str, d: int, eps: float, seed: int,
             n: int = 500, k: float = 10, mu: float = 0.3, rounds: int = 2000,
             keep_initial: bool = False, step_metric: Optional[str] = None,
             checkpoints: Iterable[int] = (), measure: bool = True) -> dict:
    """One run; see the module docstring for the outcomes.

    ``metric`` is the gate; ``step_metric`` (default: the same) is the update
    rule, so the two can be crossed. ``checkpoints`` records every outcome
    after those rounds in ``out["at"]``. ``measure=False`` skips the
    group computations (pilot runs for calibration need only the pass rate).
    """
    step_metric = step_metric or metric
    checkpoints = set(int(c) for c in checkpoints)
    world = np.random.default_rng([seed, 0])          # graph and opinions
    order = np.random.default_rng([seed, 1])          # matchings
    edges = build_graph(n, k, world)
    x = sample_opinions(space, d, n, world)
    initial = x.copy()
    lo, hi = _bounds(space)
    angular_step = step_metric != "euclidean"

    attempts = passes = updates = clipped = 0
    converged_at: Optional[int] = None
    at = {}
    for r in range(rounds):
        m = random_matching(edges, order)
        a, b = x[m[:, 0]], x[m[:, 1]]
        ok = distances(metric, a, b) <= eps
        attempts += len(m)
        passes += int(ok.sum())
        if ok.any():
            i, j = m[ok, 0], m[ok, 1]
            xi, xj = x[i], x[j]
            raw_i = step_batch(step_metric, xi, xj, mu)
            raw_j = step_batch(step_metric, xj, xi, mu)
            new_i, new_j = np.clip(raw_i, lo, hi), np.clip(raw_j, lo, hi)
            if angular_step:
                updates += 2 * len(i)
                clipped += int(np.sum(np.any(new_i != raw_i, axis=1)))
                clipped += int(np.sum(np.any(new_j != raw_j, axis=1)))
            moved = max(np.abs(new_i - xi).max(), np.abs(new_j - xj).max())
            x[i], x[j] = new_i, new_j
        else:
            moved = 0.0
        if moved > CONVERGED:
            converged_at = None
        elif converged_at is None:
            converged_at = r
        if (r + 1) in checkpoints:
            snap = {"pass_rate": passes / attempts if attempts else 0.0,
                    "settled": converged_at is not None}
            if measure:
                snap.update(outcomes(metric, space, x, eps))
            at[r + 1] = snap

    out = {
        "pass_rate": passes / attempts if attempts else 0.0,
        "converged_at": rounds if converged_at is None else converged_at,
        "clip_rate": clipped / updates if updates else 0.0,
        "edges": edges,
        "final": x,
        "at": at,
    }
    if measure:
        out.update(outcomes(metric, space, x, eps))
    if keep_initial:
        out["initial"] = initial
    return out


# --- run-average threshold calibration -------------------------------------

def mean_pass_rate(metric, space, d, eps, seeds, **kw) -> float:
    kw.setdefault("measure", False)
    return float(np.mean([simulate(metric, space, d, eps, s, **kw)["pass_rate"] for s in seeds]))


def _upper(metric: str, space: str, d: int) -> float:
    return {"euclidean": 2.0 * np.sqrt(d) * (_bounds(space)[1] - _bounds(space)[0]),
            "cosine": 2.0, "manifold": np.pi}[metric]


def calibrate_report(metric: str, space: str, d: int, target: float,
                     seeds: Iterable[int], tol: float = 0.005, max_iter: int = 30,
                     bracket: Optional[tuple] = None, **kw) -> dict:
    """Bisection for the ``eps`` whose run-averaged pass rate equals ``target``.

    Returns the eps and how well it did: the achieved rate, its error, the
    iterations used, whether it met ``tol``, and whether the evaluated rates
    rose with eps (a noisy check; small dips under 0.01 are allowed).
    ``bracket`` narrows the search; it is widened to the full range if the
    target lies outside it.
    """
    seeds = list(seeds)
    lo, hi = 0.0, _upper(metric, space, d)
    tried = []
    if bracket is not None:
        b_lo, b_hi = max(0.0, bracket[0]), min(hi, bracket[1])
        r_lo = mean_pass_rate(metric, space, d, b_lo, seeds, **kw)
        r_hi = mean_pass_rate(metric, space, d, b_hi, seeds, **kw)
        tried += [(b_lo, r_lo), (b_hi, r_hi)]
        if r_lo <= target <= r_hi:
            lo, hi = b_lo, b_hi
    eps, rate, iterations = 0.5 * (lo + hi), float("nan"), 0
    for iterations in range(1, max_iter + 1):
        eps = 0.5 * (lo + hi)
        rate = mean_pass_rate(metric, space, d, eps, seeds, **kw)
        tried.append((eps, rate))
        if abs(rate - target) <= tol:
            break
        lo, hi = (eps, hi) if rate < target else (lo, eps)
    rates = [r for _, r in sorted(tried)]
    monotone = all(b >= a - 0.01 for a, b in zip(rates, rates[1:]))
    return {"eps": eps, "target": target, "achieved": rate, "error": rate - target,
            "iterations": iterations, "within_tol": bool(abs(rate - target) <= tol),
            "monotone": bool(monotone)}


def calibrate_run_average(metric: str, space: str, d: int, target: float,
                          seeds: Iterable[int], tol: float = 0.005,
                          max_iter: int = 30, **kw) -> float:
    """``eps`` whose run-averaged pass rate matches ``target`` (see calibrate_report)."""
    rep = calibrate_report(metric, space, d, target, seeds, tol=tol, max_iter=max_iter, **kw)
    if not rep["within_tol"]:
        import warnings
        warnings.warn(f"calibration missed tolerance: {rep}")
    return rep["eps"]
