"""
policyswarm.coverage
====================
How many pairs a confidence threshold lets talk ("coverage").

A bounded-confidence gate ``d(x_i, x_j) <= eps`` admits a share of pairs that
depends on the metric, on where the opinion space sits (the unit cube [0,1]^d
or the centred cube [-1,1]^d) and on the dimension, so one shared ``eps``
means a different interaction rate under each metric. Opinions are uniform and
independent, so the share among random pairs equals the share among
network-neighbour pairs at the start.

Used by the methods note (paper/methods_note) and the dashboard's ε explorer.
Metrics are the geometry registry's: ``euclidean``, ``cosine`` (1 - cos) and
``manifold`` (the angle).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

from .config import Geometry
from .geometry import pairwise_distance

METRICS = ("euclidean", "cosine", "manifold")
SPACES = ("unit", "centred")


def sample_opinions(space: str, d: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` uniform opinions in ``d`` dimensions."""
    if space == "unit":
        return rng.uniform(0.0, 1.0, size=(n, d))
    if space == "centred":
        return rng.uniform(-1.0, 1.0, size=(n, d))
    raise ValueError(f"unknown space {space!r}; use one of {SPACES}")


def sample_pairs(space: str, d: int, n_pairs: int, rng: np.random.Generator):
    """Two arrays of ``n_pairs`` independent uniform opinions."""
    return sample_opinions(space, d, n_pairs, rng), sample_opinions(space, d, n_pairs, rng)


def distances(metric: str, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise distance under one of PolicySwarm's metrics."""
    return pairwise_distance(Geometry(metric), a, b)


def pass_fraction(metric: str, space: str, d: int, eps: float,
                  n_pairs: int = 200_000, seed: int = 0) -> float:
    """Monte Carlo share of uniform pairs within ``eps``."""
    a, b = sample_pairs(space, d, n_pairs, np.random.default_rng(seed))
    return float(np.mean(distances(metric, a, b) <= eps))


def pass_curve(metric: str, space: str, d: int, eps_grid: Iterable[float],
               n_pairs: int = 200_000, seed: int = 0) -> np.ndarray:
    """Pass fraction at every ``eps`` in ``eps_grid`` from one sample."""
    a, b = sample_pairs(space, d, n_pairs, np.random.default_rng(seed))
    dist = np.sort(distances(metric, a, b))
    eps = np.asarray(list(eps_grid), dtype=float)
    return np.searchsorted(dist, eps, side="right") / dist.size


def matched_epsilon(metric: str, space: str, d: int, target: float,
                    n_pairs: int = 200_000, seed: int = 0) -> float:
    """The ``eps`` admitting a share ``target`` of uniform pairs."""
    if not 0.0 < target <= 1.0:
        raise ValueError("target must be in (0, 1]")
    a, b = sample_pairs(space, d, n_pairs, np.random.default_rng(seed))
    dist = distances(metric, a, b)
    return float(np.quantile(dist[np.isfinite(dist)], target))


def pass_fraction_quadrature(metric: str, space: str, eps: float, grid: int = 120) -> float:
    """Deterministic pass fraction in two dimensions (midpoint rule).

    Integrates the indicator ``d(x, y) <= eps`` over the square with a
    ``grid`` x ``grid`` lattice for each point. Used to check the Monte
    Carlo estimate; its error shrinks like 1 / grid.
    """
    lo, hi = (0.0, 1.0) if space == "unit" else (-1.0, 1.0) if space == "centred" else (None, None)
    if lo is None:
        raise ValueError(f"unknown space {space!r}; use one of {SPACES}")
    centres = lo + (np.arange(grid) + 0.5) * (hi - lo) / grid
    xs, ys = np.meshgrid(centres, centres)
    pts = np.column_stack([xs.ravel(), ys.ravel()])
    n = len(pts)
    hits = 0
    for start in range(0, n, 256):
        block = pts[start:start + 256]
        a = np.repeat(block, n, axis=0)
        b = np.tile(pts, (len(block), 1))
        hits += int(np.count_nonzero(distances(metric, a, b) <= eps))
    return hits / (n * n)
