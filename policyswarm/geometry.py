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

Adding a geometry
-----------------
A geometry is one ``GeometrySpec``: its two functions plus the plain-language
text the dashboard shows. To add one:

  1. add a member to ``config.Geometry`` (its value is the name users type);
  2. write ``pairwise(a, b)`` (row-wise distances) and ``step(o_i, o_j, rate)``;
  3. call ``register_geometry(GeometrySpec(...))`` at the bottom of this module.

Nothing else needs to change: ``Simulation``, epsilon calibration, the trace
and the dashboard all go through ``geometry_spec``.

Future note: function-space geometries (set aside, not implemented)
-------------------------------------------------------------------
Candidates considered for treating an opinion as a function rather than a
point: the Lp family (p = 1 total disagreement, p = infinity the single most
contested dimension), a Sobolev H1 "profile" distance that also compares the
differences between adjacent dimensions, and a Gaussian-kernel (RKHS)
distance that saturates beyond a bandwidth. The policy dimensions have no
natural order, so the Sobolev variant is only meaningful once an order is
defined; the Lp family needs none.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np

from .config import Geometry, SimConfig

_NORM_EPS = 1e-9


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeometrySpec:
    """One opinion-space geometry: its maths and how to describe it.

    Parameters
    ----------
    key : str
        Registry name; the ``value`` of the matching ``config.Geometry`` member.
    label, summary, distance_text, step_text, epsilon_text : str
        Plain-language description shown in the dashboard.
    pairwise : callable (a, b) -> ndarray
        Row-wise distance between two arrays of shape (..., d).
    step : callable (o_i, o_j, rate) -> ndarray
        Agent i's opinion after moving toward j by ``rate``. Not clipped.
    max_distance : callable (dim) -> float
        Largest possible distance in a d-dimensional opinion cube.
    angular : bool
        True if the geometry compares directions only (ignores magnitude).
    """
    key           : str
    label         : str
    summary       : str
    distance_text : str
    step_text     : str
    epsilon_text  : str
    pairwise      : Callable[[np.ndarray, np.ndarray], np.ndarray]
    step          : Callable[[np.ndarray, np.ndarray, float], np.ndarray]
    max_distance  : Callable[[int], float]
    angular       : bool = False


GEOMETRIES: Dict[str, GeometrySpec] = {}


def register_geometry(spec: GeometrySpec) -> GeometrySpec:
    """Make a geometry available to ``Simulation`` and the dashboard."""
    GEOMETRIES[spec.key] = spec
    return spec


def geometry_spec(geometry) -> GeometrySpec:
    """Look up a geometry by ``config.Geometry`` member or by name."""
    try:
        return GEOMETRIES[getattr(geometry, "value", geometry)]
    except KeyError:
        raise ValueError(f"Unknown geometry: {geometry}") from None


def describe_geometries() -> List[dict]:
    """JSON-serialisable description of every registered geometry."""
    return [
        {"key": s.key, "label": s.label, "summary": s.summary, "distance": s.distance_text,
         "step": s.step_text, "epsilon": s.epsilon_text, "angular": s.angular}
        for s in GEOMETRIES.values()
    ]


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------

def pairwise_distance(geometry: Geometry, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise distance between a and b (same shape (..., d)).

    Angular distances involving a zero vector (an agent exactly at the neutral
    origin has no direction) are +inf, so such pairs never pass the gate.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return geometry_spec(geometry).pairwise(a, b)


def distance(geometry: Geometry, a: np.ndarray, b: np.ndarray) -> float:
    """Scalar distance between two opinion vectors."""
    return float(pairwise_distance(geometry, a, b))


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
    return geometry_spec(geometry).step(op_i, op_j, rate)


# ---------------------------------------------------------------------------
# Euclidean
# ---------------------------------------------------------------------------

def _euclidean_pairwise(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.linalg.norm(a - b, axis=-1)


def _euclidean_step(op_i: np.ndarray, op_j: np.ndarray, rate: float) -> np.ndarray:
    return op_i + rate * (op_j - op_i)


# ---------------------------------------------------------------------------
# Angular geometries (cosine, manifold)
# ---------------------------------------------------------------------------

def _unit_rows(x: np.ndarray):
    """Return (unit vectors, norms, valid mask) for the rows of x."""
    norms = np.linalg.norm(x, axis=-1)
    valid = norms > _NORM_EPS
    safe  = np.where(valid, norms, 1.0)
    return x / safe[..., None], norms, valid


def _cosines(a: np.ndarray, b: np.ndarray):
    """Cosine of the angle between rows of a and b, and where it is defined."""
    ua, _, va = _unit_rows(a)
    ub, _, vb = _unit_rows(b)
    return np.clip(np.sum(ua * ub, axis=-1), -1.0, 1.0), va & vb


def _cosine_pairwise(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    cos, valid = _cosines(a, b)
    return np.where(valid, 1.0 - cos, np.inf)


def _manifold_pairwise(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    cos, valid = _cosines(a, b)
    return np.where(valid, np.arccos(cos), np.inf)


def _directions(op_i: np.ndarray, op_j: np.ndarray):
    """(norm of i, unit i, unit j), or None if either opinion has no direction."""
    ni = np.linalg.norm(op_i)
    nj = np.linalg.norm(op_j)
    if ni < _NORM_EPS or nj < _NORM_EPS:
        return None
    return ni, op_i / ni, op_j / nj


def _cosine_step(op_i: np.ndarray, op_j: np.ndarray, rate: float) -> np.ndarray:
    directions = _directions(op_i, op_j)
    if directions is None:
        return op_i.copy()
    ni, u_i, u_j = directions
    moved = u_i + rate * (u_j - u_i)
    nm = np.linalg.norm(moved)
    if nm < _NORM_EPS:          # exactly antipodal and rate = 0.5
        return op_i.copy()
    return ni * moved / nm


def _manifold_step(op_i: np.ndarray, op_j: np.ndarray, rate: float) -> np.ndarray:
    directions = _directions(op_i, op_j)
    if directions is None:
        return op_i.copy()
    ni, u_i, u_j = directions
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


register_geometry(GeometrySpec(
    key           = Geometry.EUCLIDEAN.value,
    label         = "Euclidean",
    summary       = "Straight-line distance: how far apart two opinions are on every "
                    "dimension, strength of feeling included.",
    distance_text = "The length of the line between the two opinions. 0 means identical; "
                    "the most it can be is the diagonal of the opinion cube.",
    step_text     = "The listener moves in a straight line toward the speaker, changing "
                    "both what it believes and how strongly.",
    epsilon_text  = "ε is a length in opinion units (each dimension runs from −1 to 1).",
    pairwise      = _euclidean_pairwise,
    step          = _euclidean_step,
    max_distance  = lambda dim: 2.0 * math.sqrt(dim),
))

register_geometry(GeometrySpec(
    key           = Geometry.COSINE.value,
    label         = "Cosine",
    summary       = "Direction only: do two opinions lean the same way, seen from neutral, "
                    "however strongly each is held?",
    distance_text = "1 − cos(angle between them): 0 = same direction, 1 = unrelated, "
                    "2 = opposite. An agent exactly at neutral has no direction and is never heard.",
    step_text     = "The listener turns its direction toward the speaker's. How strongly it "
                    "feels does not change.",
    epsilon_text  = "ε is a value of 1 − cos; 0.5 lets pairs up to 60° apart talk.",
    pairwise      = _cosine_pairwise,
    step          = _cosine_step,
    max_distance  = lambda dim: 2.0,
    angular       = True,
))

register_geometry(GeometrySpec(
    key           = Geometry.MANIFOLD.value,
    label         = "Manifold (geodesic)",
    summary       = "Direction only, like cosine, but distance is the angle itself, "
                    "measured along the sphere of directions.",
    distance_text = "The angle between the two opinions in radians: 0 = same direction, "
                    "π (3.14) = opposite.",
    step_text     = "The listener rotates toward the speaker along the shortest arc between "
                    "them. How strongly it feels does not change.",
    epsilon_text  = "ε is an angle in radians; 0.5 is about 29°.",
    pairwise      = _manifold_pairwise,
    step          = _manifold_step,
    max_distance  = lambda dim: math.pi,
    angular       = True,
))


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
