"""
policyswarm.projection
======================
Flat pictures of a set of points known only by their pairwise distances.

Used by the dashboard's "distance map": agents are placed in 2-D so that the
distance between two of them on screen approximates their distance under the
simulation's geometry, over all opinion dimensions at once.

classical_mds
    Torgerson's classical multidimensional scaling. Exact when the distances
    are Euclidean and the points lie in ``k`` dimensions; otherwise the best
    rank-``k`` approximation of the centred Gram matrix. Distances that are
    not Euclidean (cosine distance is not a metric) give some negative
    eigenvalues, which are dropped; ``fit`` reports how much was kept.

procrustes_align
    MDS coordinates are only defined up to rotation and reflection, so two
    maps of slightly different data can come out flipped. Aligning each map
    to the previous one keeps a sequence of maps steady.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
from scipy.linalg import eigh


def classical_mds(distances: np.ndarray, k: int = 2) -> Tuple[np.ndarray, float]:
    """Place n points in ``k`` dimensions from an (n, n) distance matrix.

    Returns
    -------
    coordinates : ndarray, shape (n, k)
        Centred on the origin, in the units of ``distances``.
    fit : float
        Share of the positive eigenvalue mass the ``k`` axes capture, in
        [0, 1]. 1.0 means the picture reproduces the distances exactly.
    """
    d = np.asarray(distances, dtype=float)
    n = d.shape[0]
    if n <= k:
        return np.zeros((n, k)), 1.0
    squared = d ** 2
    gram = -0.5 * (squared - squared.mean(axis=0) - squared.mean(axis=1)[:, None] + squared.mean())
    values, vectors = eigh(gram)                  # ascending eigenvalues
    kept = np.clip(values[::-1][:k], 0.0, None)
    coordinates = vectors[:, ::-1][:, :k] * np.sqrt(kept)
    positive = values[values > 0].sum()
    fit = float(kept.sum() / positive) if positive > 0 else 1.0
    return coordinates, min(fit, 1.0)


def procrustes_align(points: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Rotate / reflect ``points`` to lie as close as possible to ``reference``.

    Both arrays have shape (n, k) and are taken as centred. No scaling is
    applied, so distances within ``points`` are unchanged.
    """
    u, _, vt = np.linalg.svd(points.T @ reference)
    return points @ (u @ vt)
