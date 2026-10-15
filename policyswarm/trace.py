"""
policyswarm.trace
=================
Record everything that happens inside a simulation, tick by tick, so a front
end can replay it (the dashboard's "Watch one simulation" viewer).

The experiments only keep end-of-tick opinions. A trace adds, per tick:

  * every peer conversation attempt: who listened, who spoke, and how it
    ended (blocked by the deployment cap, ignored because the two opinions
    were further apart than epsilon, or heard);
  * which agents each shock hit;
  * how far each phase (shock, media, peers, policy) moved every agent;
  * measurements under the run's geometry: the distribution of distances
    between network neighbours, the share of them within epsilon, and a 2-D
    "distance map" of all agents (see ``policyswarm.projection``).

``TraceRecorder`` is the observer ``Simulation`` reports to. ``record_trace``
runs the same scenario under one to three geometries from the same seed, so
the runs share their network, starting opinions and shock schedule and differ
only in how distance is measured. Recording draws no random numbers, so a
traced run equals an untraced one with the same inputs.
"""

from __future__ import annotations

import dataclasses
import math
import threading
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from .config import Geometry, GovernanceConfig, ShockConfig, ShockMode
from .dynamics import Simulation
from .experiments.base import BASELINE_GOVERNANCE
from .experiments.params import ParamError, ParamSpec, parse_params
from .extraction import DEFAULT_POLICY_TEXT, policy_from_text
from .geometry import describe_geometries, geometry_spec, matched_epsilons, pairwise_distance
from .metrics import opinion_variance
from .opinion_space import OpinionSpace
from .projection import classical_mds, procrustes_align
from .registry import build_sim_config
from .shocks import generate_shocks

#: How a conversation attempt ended, as stored in a trace.
OUTCOME_CODES = {"blocked": 0, "too_far": 1, "heard": 2, "penalised": 3}

#: Upper bounds for a traced run. A trace is drawn agent by agent and sent to
#: the browser in one response, so it is kept to a size that stays readable.
TRACE_LIMITS = {"n_agents": 400, "n_ticks": 300, "interactions": 2000}

#: Most geometries that can be compared side by side in one request.
MAX_GEOMETRIES = 3

#: Ceiling on agents x ticks x geometries. Each tick of each run stores every
#: agent and needs one distance map, so the three multiply.
TRACE_BUDGET = 60_000

#: Number of bars in the neighbour-distance histogram.
HISTOGRAM_BINS = 24

_GOV = GovernanceConfig(**BASELINE_GOVERNANCE)

#: Scenario settings of a traced run (everything that is not SimConfig).
TRACE_PARAMS: Tuple[ParamSpec, ...] = (
    ParamSpec("geometries", "choice", [Geometry.EUCLIDEAN.value], many=True, enum=Geometry,
              help="How the distance between two opinions is measured. Tick two or "
                   "three to watch the same scenario side by side."),
    ParamSpec("match_epsilon", "bool", True,
              help="Give every geometry the ε that lets the same share of neighbour pairs "
                   "talk as Euclidean does. Without it, one raw ε means a different "
                   "amount of talking in each geometry."),
    ParamSpec("seed", "int", 0, minimum=0,
              help="Fixes the network, the starting opinions and the shock schedule."),
    ParamSpec("deployment_rate_cap", "float", _GOV.deployment_rate_cap,
              minimum=0.0, maximum=1.0,
              help="Chance that a conversation attempt is allowed to happen."),
    ParamSpec("penalty_severity", "float", _GOV.penalty_severity,
              minimum=0.0, maximum=1.0,
              help="Share of influence a violating speaker loses once enforcement starts."),
    ParamSpec("enforcement_lag", "int", 10, minimum=0,
              help="Tick from which violating speakers are penalised."),
    ParamSpec("policy_pull_onset", "int", 10, minimum=0,
              help="Tick from which agents are pulled toward their own reading of the policy."),
    ParamSpec("enable_media", "bool", _GOV.enable_media,
              help="Pro- and anti-policy media pull agents every tick."),
    ParamSpec("media_strength", "float", _GOV.media_strength, minimum=0.0, maximum=1.0,
              help="Strength of the media pull."),
    ParamSpec("shocks", "bool", True, help="Apply the random shock schedule."),
    ParamSpec("shock_mode", "choice", ShockMode.COORDINATING.value, enum=ShockMode,
              help="coordinating pulls to neutral, polarizing pushes outward, "
                   "directional pulls to the policy."),
    ParamSpec("shock_prob", "float", ShockConfig().shock_prob, minimum=0.0, maximum=1.0,
              help="Chance of a shock on each tick."),
)

# Simulation seeds the process-wide ``random`` / ``numpy.random`` state, so two
# traces computed at once in the same process would disturb each other.
_RUN_LOCK = threading.Lock()


class TraceRecorder:
    """Collects what ``Simulation`` reports during a run.

    ``Simulation`` calls ``begin_tick`` / ``end_tick`` around each tick,
    ``phase`` after each phase with the distance every agent moved,
    ``conversation`` for each peer attempt and ``shock`` for each shock.
    ``measure`` can also be called directly, e.g. on the starting state.
    """

    def __init__(self) -> None:
        self.ticks: List[Dict[str, Any]] = []
        self._tick: Dict[str, Any] = {}
        self._previous_map: Optional[np.ndarray] = None

    def begin_tick(self, tick: int, sim: Simulation) -> None:
        self._tick = {
            "policy"       : _rounded(sim.policy.as_vector()),
            "conversations": [],
            "shocks"       : [],
            "moved"        : {},
        }

    def phase(self, name: str, moved: np.ndarray) -> None:
        if not np.any(moved > 0):
            return
        totals = self._tick["moved"]
        totals[name] = moved if name not in totals else totals[name] + moved

    def conversation(self, listener: int, speaker: int, outcome: str,
                     distance: Optional[float] = None, moved: float = 0.0) -> None:
        self._tick["conversations"].append([
            int(listener), int(speaker), OUTCOME_CODES[outcome],
            _number(distance), _number(moved),
        ])

    def shock(self, event: Dict[str, Any], targets) -> None:
        self._tick["shocks"].append({
            "type"    : event["type"],
            "mode"    : event.get("mode", ShockMode.COORDINATING.value),
            "strength": _number(event["strength"]),
            "targets" : [int(t) for t in targets],
        })

    def end_tick(self, tick: int, sim: Simulation) -> None:
        current = self._tick
        current["moved"]    = {name: _rounded(moved) for name, moved in current["moved"].items()}
        current["opinions"] = _rounded(sim.opinions)
        current["variance"] = _number(opinion_variance(sim.opinions), 6)
        current["measure"]  = self.measure(sim)
        self.ticks.append(current)

    def measure(self, sim: Simulation) -> Dict[str, Any]:
        """Distances under the run's geometry at the simulation's current state.

        Returns the histogram of distances across network edges (the only
        pairs that can ever talk), the share of them within epsilon, and the
        2-D distance map of every agent plus the policy.
        """
        spec = geometry_spec(sim.geometry)
        ceiling = spec.max_distance(sim.sim_config.opinion_dim)
        opinions = sim.opinions

        edges = np.array(sim.graph.edges(), dtype=int).reshape(-1, 2)
        across = pairwise_distance(sim.geometry, opinions[edges[:, 0]], opinions[edges[:, 1]])
        defined = across[np.isfinite(across)]
        counts, _ = np.histogram(defined, bins=HISTOGRAM_BINS, range=(0.0, ceiling))
        coverage = float(np.mean(across <= sim.sim_config.epsilon)) if across.size else 0.0

        # Map: every agent and the policy, by their distances over all dimensions.
        points = np.vstack([opinions, sim.policy.as_vector()])
        full = pairwise_distance(sim.geometry, points[:, None, :], points[None, :, :])
        full = np.where(np.isfinite(full), full, ceiling)
        np.fill_diagonal(full, 0.0)
        coordinates, fit = classical_mds(full)
        if self._previous_map is not None:
            coordinates = procrustes_align(coordinates, self._previous_map)
        self._previous_map = coordinates

        return {
            "histogram" : counts.tolist(),
            "undefined" : int(across.size - defined.size),
            "coverage"  : _number(coverage),
            "map"       : _rounded(coordinates[:-1]),
            "map_policy": _rounded(coordinates[-1]),
            "map_fit"   : _number(fit),
        }


def describe() -> Dict[str, Any]:
    """JSON-serialisable description of the trace inputs (for the dashboard form)."""
    return {
        "params"        : [p.to_dict() for p in TRACE_PARAMS],
        "limits"        : dict(TRACE_LIMITS),
        "budget"        : TRACE_BUDGET,
        "max_geometries": MAX_GEOMETRIES,
        "geometries"    : describe_geometries(),
    }


def record_trace(
    params        : Optional[Dict[str, Any]] = None,
    sim_config    : Optional[Dict[str, Any]] = None,
    policy_text   : Optional[str]            = None,
    opinion_space : Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run one scenario under each requested geometry and return the traces.

    Parameters
    ----------
    params : dict, optional
        Overrides for ``TRACE_PARAMS`` (geometries, seed, governance, shocks).
    sim_config : dict, optional
        Overrides for ``SimConfig`` fields, as in ``RunSpec.sim_config``.
    policy_text : str, optional
        Policy document. None = the package default.
    opinion_space : dict, optional
        Custom opinion space, as in ``RunSpec.opinion_space``.

    Returns
    -------
    dict
        ``shared``: what every run has in common (settings, agents, network,
        starting opinions). ``runs``: one entry per geometry with its epsilon,
        starting measurements and per-tick record.

    Raises
    ------
    ParamError
        If a value is invalid or the run exceeds ``TRACE_LIMITS``.
    """
    p = {spec.name: spec.parse(spec.default) for spec in TRACE_PARAMS}
    p.update(parse_params(TRACE_PARAMS, params))
    geometries: List[Geometry] = p["geometries"]
    if len(set(geometries)) != len(geometries):
        raise ParamError("geometries: the same geometry is listed twice")
    if len(geometries) > MAX_GEOMETRIES:
        raise ParamError(f"geometries: compare at most {MAX_GEOMETRIES} at a time")

    config = build_sim_config(sim_config)
    for name, limit in TRACE_LIMITS.items():
        if getattr(config, name) > limit:
            raise ParamError(f"{name}: the viewer handles at most {limit} "
                             f"(got {getattr(config, name)})")
    size = config.n_agents * config.n_ticks * len(geometries)
    if size > TRACE_BUDGET:
        raise ParamError(
            f"This is too much to replay: {config.n_agents} agents x {config.n_ticks} ticks x "
            f"{len(geometries)} geometries = {size:,}, and the viewer handles {TRACE_BUDGET:,}. "
            "Use fewer agents, ticks or geometries.")

    text = policy_text or DEFAULT_POLICY_TEXT
    if opinion_space is not None:
        policy = OpinionSpace.from_dict(opinion_space).build_policy(text, lag=p["enforcement_lag"])
    else:
        policy = policy_from_text(text, lag=p["enforcement_lag"])
    config = dataclasses.replace(config, opinion_dim=policy.dim)

    governance = GovernanceConfig(
        deployment_rate_cap = p["deployment_rate_cap"],
        penalty_severity    = p["penalty_severity"],
        enforcement_lag     = p["enforcement_lag"],
        enable_media        = p["enable_media"],
        media_strength      = p["media_strength"],
        policy_pull_onset   = p["policy_pull_onset"],
    )
    shocks = generate_shocks(
        ShockConfig(shock_prob=p["shock_prob"], mode=p["shock_mode"]), config.n_ticks, p["seed"],
    ) if p["shocks"] else []

    runs, shared = [], None
    with _RUN_LOCK:
        epsilons = {g.value: config.epsilon for g in geometries}
        coverage = None
        if p["match_epsilon"] and any(g != Geometry.EUCLIDEAN for g in geometries):
            epsilons, coverage = matched_epsilons(config, geometries)
        for geometry in geometries:
            run_config = dataclasses.replace(config, epsilon=epsilons[geometry.value])
            recorder = TraceRecorder()
            sim = Simulation(run_config, governance, policy, shocks, apply_shocks=bool(shocks),
                             seed=p["seed"], geometry=geometry, recorder=recorder)
            if not runs:        # identical for every geometry: same seed, same draws
                shared = _shared(sim, p, governance, shocks)
            start = recorder.measure(sim)
            sim.run()
            runs.append(_run_record(sim, recorder, start, coverage))

    return {"shared": shared, "runs": runs}


def _shared(sim: Simulation, p: Dict[str, Any], governance: GovernanceConfig,
            shocks: list) -> Dict[str, Any]:
    """Everything that does not depend on the geometry."""
    config, policy = sim.sim_config, sim.policy
    return {
        "meta": {
            "seed"               : p["seed"],
            "n_agents"           : config.n_agents,
            "n_ticks"            : config.n_ticks,
            "interactions"       : config.interactions,
            "mu"                 : config.mu,
            "policy_split_tick"  : config.policy_split_tick,
            "dimensions"         : list(policy.dimension_names),
            "violator_dimension" : policy.violator_dim_index,
            "violator_threshold" : policy.violator_threshold,
            "deployment_rate_cap": governance.deployment_rate_cap,
            "penalty_severity"   : governance.penalty_severity,
            "enforcement_lag"    : p["enforcement_lag"],
            "policy_pull_onset"  : p["policy_pull_onset"],
            "media"              : governance.enable_media,
            "shock_ticks"        : [ev["tick"] for ev in shocks],
        },
        "agents"          : _agents(sim, p["seed"]),
        "edges"           : [[int(a), int(b)] for a, b in sim.graph.edges()],
        "initial"         : _rounded(sim.opinions),
        "initial_policy"  : _rounded(policy.as_vector()),
        "initial_variance": _number(opinion_variance(sim.opinions), 6),
    }


def _run_record(sim: Simulation, recorder: TraceRecorder, start: Dict[str, Any],
                coverage: Optional[float]) -> Dict[str, Any]:
    """One geometry's run: its settings, starting measurements and ticks."""
    spec = geometry_spec(sim.geometry)
    maps = [start["map"]] + [tick["measure"]["map"] for tick in recorder.ticks]
    return {
        "geometry"        : spec.key,
        "label"           : spec.label,
        "angular"         : spec.angular,
        "epsilon"         : _number(sim.sim_config.epsilon),
        "matched_coverage": _number(coverage),
        "max_distance"    : _number(spec.max_distance(sim.sim_config.opinion_dim)),
        "map_extent"      : _number(max(float(np.abs(m).max()) for m in maps) or 1.0),
        "gate_pass_rate"  : _number(sim.gate_pass_rate),
        "initial_measure" : start,
        "ticks"           : recorder.ticks,
    }


def _agents(sim: Simulation, seed: int) -> Dict[str, list]:
    """Fixed per-agent attributes, plus a 2-D layout of the network in [0, 1]."""
    n = sim.sim_config.n_agents
    layout = nx.spring_layout(sim.graph, seed=seed, iterations=80)
    xy = np.array([layout[i] for i in range(n)], dtype=float)
    span = xy.max(axis=0) - xy.min(axis=0)
    xy = (xy - xy.min(axis=0)) / np.where(span > 0, span, 1.0)
    hubs = set(sim._hub_indices)
    return {
        "x"        : _rounded(xy[:, 0]),
        "y"        : _rounded(xy[:, 1]),
        "degree"   : [int(sim.graph.degree(i)) for i in range(n)],
        "influence": _rounded(sim.influence),
        "ideology" : _rounded(sim.ideology),
        "trust"    : _rounded(sim.trust),
        "community": [int(c) for c in sim.community_labels],
        "hub"      : [i in hubs for i in range(n)],
    }


def _number(value, digits: int = 4) -> Optional[float]:
    """A rounded float, or None for missing / non-finite values (invalid JSON)."""
    if value is None:
        return None
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def _rounded(array: np.ndarray) -> list:
    return np.round(np.asarray(array, dtype=float), 4).tolist()
