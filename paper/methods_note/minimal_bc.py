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


def simulate(metric: str, space: str, d: int, eps: float, seed: int,
             n: int = 500, k: float = 10, mu: float = 0.3, rounds: int = 2000,
             keep_initial: bool = False) -> dict:
    """One run; see the module docstring for the outcomes."""
    world = np.random.default_rng([seed, 0])          # graph and opinions
    order = np.random.default_rng([seed, 1])          # matchings
    edges = build_graph(n, k, world)
    x = sample_opinions(space, d, n, world)
    initial = x.copy()
    lo, hi = _bounds(space)

    attempts = passes = 0
    converged_at: Optional[int] = None
    for r in range(rounds):
        m = random_matching(edges, order)
        a, b = x[m[:, 0]], x[m[:, 1]]
        ok = distances(metric, a, b) <= eps
        attempts += len(m)
        passes += int(ok.sum())
        if ok.any():
            i, j = m[ok, 0], m[ok, 1]
            xi, xj = x[i], x[j]
            new_i = np.clip(step_batch(metric, xi, xj, mu), lo, hi)
            new_j = np.clip(step_batch(metric, xj, xi, mu), lo, hi)
            moved = max(np.abs(new_i - xi).max(), np.abs(new_j - xj).max())
            x[i], x[j] = new_i, new_j
        else:
            moved = 0.0
        if moved > CONVERGED:
            converged_at = None
        elif converged_at is None:
            converged_at = r

    sizes = _groups(metric, x, CLUSTER_FRACTION * eps)
    shares = sizes / n
    norms = np.linalg.norm(x, axis=1)
    units = x[norms > _NORM_EPS] / norms[norms > _NORM_EPS, None]
    out = {
        "variance": float(x.var(axis=0).mean()),
        "dispersion": float(1.0 - np.linalg.norm(units.mean(axis=0))) if len(units) else 1.0,
        "clusters": int(np.sum(shares >= max(0.01, 2 / n))),
        "eff_clusters": float(1.0 / np.sum(shares ** 2)),
        "pass_rate": passes / attempts if attempts else 0.0,
        "converged_at": rounds if converged_at is None else converged_at,
        "edges": edges,
        "final": x,
    }
    if keep_initial:
        out["initial"] = initial
    return out


# --- run-average threshold calibration -------------------------------------

def mean_pass_rate(metric, space, d, eps, seeds, **kw) -> float:
    return float(np.mean([simulate(metric, space, d, eps, s, **kw)["pass_rate"] for s in seeds]))


def calibrate_run_average(metric: str, space: str, d: int, target: float,
                          seeds: Iterable[int], tol: float = 0.005,
                          max_iter: int = 30, **kw) -> float:
    """``eps`` whose run-averaged pass rate matches ``target``.

    Bisection on ``eps``; the pass rate rises with ``eps`` (more pairs pass at
    t = 0, and a looser gate keeps pulling pairs together). Use pilot seeds
    that are not reused for reported runs.
    """
    seeds = list(seeds)
    lo, hi = 0.0, {"euclidean": 2.0 * np.sqrt(d) * (_bounds(space)[1] - _bounds(space)[0]),
                   "cosine": 2.0, "manifold": np.pi}[metric]
    eps = 0.5 * (lo + hi)
    for _ in range(max_iter):
        eps = 0.5 * (lo + hi)
        rate = mean_pass_rate(metric, space, d, eps, seeds, **kw)
        if abs(rate - target) <= tol:
            break
        lo, hi = (eps, hi) if rate < target else (lo, eps)
    return eps
