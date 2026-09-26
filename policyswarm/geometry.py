"""
policyswarm.geometry
====================
Opinion-space geometries for the bounded-confidence update rule.

Every geometry supplies two things:

  distance(a, b)          – the bounded-confidence gate metric
  step(o_i, o_j, rate)    – agent i's new opinion after being influenced by j

Opinions live in the centred cube [-1, 1]^d, where the origin is the neutral
position on every policy dimension. This matters for the angular geometries:
cosine / manifold distance is measured from the origin, so the origin must
mean "no opinion either way" for angular alignment to mean ideological
alignment. (In the older [0, 1]^d space every vector sat in the positive
orthant and almost every pair of agents was angularly "close".)

Geometries
----------
EUCLIDEAN  distance = ||a - b||_2
           step     = o_i + rate * (o_j - o_i)

COSINE     distance = 1 - cos(a, b)                         ∈ [0, 2]
           step     = extrinsic (chordal) update of the direction:
                      u_i <- normalise(u_i + rate * (u_j - u_i)),
                      magnitude ||o_i|| preserved

MANIFOLD   distance = arccos(<u_a, u_b>)  (geodesic on S^(d-1)) ∈ [0, π]
           step     = intrinsic geodesic update (slerp): u_i rotated toward
                      u_j by rate * θ, magnitude ||o_i|| preserved

The angular geometries only move an agent's *direction* (which views it
holds in proportion); intensity ||o_i|| is untouched by peer influence.

Note on COSINE vs MANIFOLD
--------------------------
1 - cos θ is a monotone function of θ, so once each geometry's epsilon is
calibrated to the same interacting fraction the two gates admit exactly the
same pairs. After coverage matching, COSINE and MANIFOLD differ only in the
update rule (chordal vs geodesic step).

Epsilon calibration
-------------------
A single epsilon means different things under different metrics (e.g. 0.5
admits 60° under COSINE but 28.6° under MANIFOLD). ``calibrate_epsilon``
returns, for each geometry, the epsilon that makes a target fraction of
*network-neighbour* pairs pass the gate at initialisation — the only pairs
that can ever interact. Geometry comparisons should use calibrated epsilon;
``Simulation`` additionally records the realised gate pass rate so coverage
can be checked over the whole trajectory.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from .config import Geometry, SimConfig

_NORM_EPS = 1e-9


# ---------------------------------------------------------------------------
# Distances
# ---------------------------------------------------------------------------

def _unit_rows(x: np.ndarray):
    """Return (unit vectors, norms, valid mask) for the rows of x."""
    norms = np.linalg.norm(x, axis=-1)
    valid = norms > _NORM_EPS
    safe  = np.where(valid, norms, 1.0)
    return x / safe[..., None], norms, valid


def pairwise_distance(geometry: Geometry, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise distance between a and b (same shape (..., d)).

    Angular distances involving a zero vector (an agent exactly at the neutral
    origin has no direction) are +inf, so such pairs never pass the gate.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    if geometry == Geometry.EUCLIDEAN:
        return np.linalg.norm(a - b, axis=-1)

    ua, _, va = _unit_rows(a)
    ub, _, vb = _unit_rows(b)
    cos = np.clip(np.sum(ua * ub, axis=-1), -1.0, 1.0)

    if geometry == Geometry.COSINE:
        d = 1.0 - cos
    elif geometry == Geometry.MANIFOLD:
        d = np.arccos(cos)
    else:
        raise ValueError(f"Unknown geometry: {geometry}")

    return np.where(va & vb, d, np.inf)


def distance(geometry: Geometry, a: np.ndarray, b: np.ndarray) -> float:
    """Scalar distance between two opinion vectors."""
    return float(pairwise_distance(geometry, a, b))


# ---------------------------------------------------------------------------
# Update step
# ---------------------------------------------------------------------------

def step(
    geometry : Geometry,
    op_i     : np.ndarray,
    op_j     : np.ndarray,
    rate     : float,
) -> np.ndarray:
    """Return agent i's opinion after moving toward agent j by ``rate``.

    ``rate`` ∈ [0, 1] is the fraction of the way moved (µ · influence_j in
    the simulation). The result is not clipped; the caller retracts it into
    the opinion cube.
    """
    if geometry == Geometry.EUCLIDEAN:
        return op_i + rate * (op_j - op_i)

    ni = np.linalg.norm(op_i)
    nj = np.linalg.norm(op_j)
    if ni < _NORM_EPS or nj < _NORM_EPS:
        return op_i.copy()
    u_i = op_i / ni
    u_j = op_j / nj

    if geometry == Geometry.COSINE:
        moved = u_i + rate * (u_j - u_i)
        nm = np.linalg.norm(moved)
        if nm < _NORM_EPS:          # exactly antipodal and rate = 0.5
            return op_i.copy()
        return ni * moved / nm

    if geometry == Geometry.MANIFOLD:
        cos   = float(np.clip(np.dot(u_i, u_j), -1.0, 1.0))
        theta = np.arccos(cos)
        if theta < 1e-12:
            return op_i.copy()
        tangent = u_j - cos * u_i
        nt = np.linalg.norm(tangent)
        if nt < _NORM_EPS:          # antipodal: geodesic direction undefined
            return op_i.copy()
        angle = rate * theta
        moved = np.cos(angle) * u_i + np.sin(angle) * (tangent / nt)
        return ni * moved

    raise ValueError(f"Unknown geometry: {geometry}")


# ---------------------------------------------------------------------------
# Coverage and epsilon calibration
# ---------------------------------------------------------------------------

def _edge_distances(
    sim_config : SimConfig,
    geometry   : Geometry,
    seeds      : Iterable[int],
) -> np.ndarray:
    """Distances across every network edge at initialisation, pooled over seeds.

    Uses Simulation's own initialisation so the opinion and network draws are
    exactly the ones the experiment will start from.
    """
    from .dynamics import Simulation          # local import: avoids a cycle
    from .config import GovernanceConfig, Policy

    dists = []
    for seed in seeds:
        sim = Simulation(
            sim_config, GovernanceConfig(), Policy(), shocks=[],
            apply_shocks=False, seed=seed, geometry=geometry,
        )
        edges = np.array(sim.graph.edges(), dtype=int)
        if edges.size == 0:
            continue
        dists.append(pairwise_distance(
            geometry, sim.opinions[edges[:, 0]], sim.opinions[edges[:, 1]],
        ))
    return np.concatenate(dists) if dists else np.array([])


def pass_fraction(
    sim_config : SimConfig,
    geometry   : Geometry,
    epsilon    : float,
    seeds      : Iterable[int] = range(10),
) -> float:
    """Fraction of network-neighbour pairs with distance <= epsilon at t=0."""
    d = _edge_distances(sim_config, geometry, seeds)
    return float(np.mean(d <= epsilon)) if d.size else 0.0


def calibrate_epsilon(
    sim_config      : SimConfig,
    geometry        : Geometry,
    target_fraction : float,
    seeds           : Iterable[int] = range(10),
) -> float:
    """Epsilon under ``geometry`` admitting ``target_fraction`` of neighbour pairs.

    Computed exactly as the ``target_fraction`` quantile of the pooled
    initial edge-distance distribution (no search needed).
    """
    if not 0.0 < target_fraction <= 1.0:
        raise ValueError("target_fraction must be in (0, 1]")
    d = _edge_distances(sim_config, geometry, seeds)
    d = d[np.isfinite(d)]
    if d.size == 0:
        raise ValueError("No finite neighbour distances to calibrate against")
    return float(np.quantile(d, target_fraction))


def matched_epsilons(
    sim_config          : SimConfig,
    geometries          : Iterable[Geometry],
    reference_geometry  : Geometry        = Geometry.EUCLIDEAN,
    reference_epsilon   : Optional[float] = None,
    seeds               : Iterable[int]   = range(10),
):
    """Coverage-matched epsilon for each geometry.

    The target coverage is the pass fraction of ``reference_geometry`` at
    ``reference_epsilon`` (default: ``sim_config.epsilon``), so the reference
    geometry keeps its configured threshold and every other geometry is
    matched to it.

    Returns
    -------
    (dict geometry.value -> epsilon, target_fraction)
    """
    seeds = list(seeds)
    ref_eps = sim_config.epsilon if reference_epsilon is None else reference_epsilon
    target  = pass_fraction(sim_config, reference_geometry, ref_eps, seeds)
    eps = {}
    for g in geometries:
        eps[g.value] = (
            ref_eps if g == reference_geometry
            else calibrate_epsilon(sim_config, g, target, seeds)
        )
    return eps, target
