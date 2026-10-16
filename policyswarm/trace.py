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

from .config import (
    GATE_SPACES, POLICY_PULLS, TRUST_ANCHORS, Geometry, GovernanceConfig, ShockConfig, ShockMode,
)
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

#: Which hidden choice varies across the viewer's columns, and its values.
COMPARE_MODES = ("geometry", "threshold_rule", "trust_anchor", "gate_space", "policy_pull")
THRESHOLD_RULES = ("shared", "matched_start", "matched_run")
COMPARE_VALUES = {
    "threshold_rule": THRESHOLD_RULES,
    "trust_anchor": ("centre", "corner", "status_quo", "own"),
    "gate_space": GATE_SPACES,
    "policy_pull": POLICY_PULLS,
}
_VALUE_LABELS = {
    "shared": "shared ε", "matched_start": "matched at start", "matched_run": "matched over run",
    "centre": "trust → neutral", "corner": "trust → no regulation",
    "status_quo": "trust → status quo", "own": "trust → own view",
    "level_shift": "level-shift control",
    "centred": "gate from centre", "unit": "gate from corner",
    "anchor": "anchor pull", "gated": "gated pull",
}
#: Most columns the viewer shows at once, and the largest run it calibrates
#: "matched over the run" for (agents x ticks).
MAX_COLUMNS = 4
MATCH_RUN_BUDGET = 12_000

#: Number of bars in the neighbour-distance histogram.
HISTOGRAM_BINS = 24

_GOV = GovernanceConfig(**BASELINE_GOVERNANCE)

#: Scenario settings of a traced run (everything that is not SimConfig).
TRACE_PARAMS: Tuple[ParamSpec, ...] = (
    ParamSpec("geometries", "choice", [Geometry.EUCLIDEAN.value], many=True, enum=Geometry,
              help="How the distance between two opinions is measured. Tick two or "
                   "three to watch the same scenario side by side."),
    ParamSpec("compare", "choice", "geometry", choices=COMPARE_MODES, label="Compare",
              group="Hidden choices",
              help="What changes from column to column; everything else, including the "
                   "seed, stays the same. geometry: the ticked geometries. Any other "
                   "choice: one column per value, using the first ticked geometry."),
    ParamSpec("threshold_rule", "choice", "matched_start", choices=THRESHOLD_RULES,
              label="Threshold rule", group="Hidden choices",
              help="shared: every geometry uses Euclidean's ε number. matched_start: each "
                   "gets the ε that lets the same share of neighbour pairs talk at the "
                   "start. matched_run: the same share over the whole run (found by a "
                   "short search; slower)."),
    ParamSpec("gate_space", "choice", "centred", choices=GATE_SPACES,
              label="Gate measured from", group="Hidden choices",
              help="centred: angles from the neutral point. unit: from the corner where "
                   "every dimension is at its minimum (the pre-audit space)."),
    ParamSpec("policy_pull", "choice", "anchor", choices=POLICY_PULLS,
              label="Policy pull", group="Hidden choices",
              help="anchor: a small pull on everyone each tick. gated: only after a heard "
                   "conversation (pre-audit)."),
    ParamSpec("trust_anchor", "choice", "centre", choices=TRUST_ANCHORS,
              label="Low trust perceives", group="Hidden choices",
              help="centre: neutral. corner: no regulation at all. status_quo: the "
                   "starting average. own: the agent's own view. level_shift: a control."),
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
    params = dict(params or {})
    if "match_epsilon" in params:                     # legacy key, kept for old run files
        legacy = params.pop("match_epsilon")
        params.setdefault("threshold_rule", "matched_start" if legacy else "shared")
    p = {spec.name: spec.parse(spec.default) for spec in TRACE_PARAMS}
    p.update(parse_params(TRACE_PARAMS, params))
    geometries: List[Geometry] = p["geometries"]
    if len(set(geometries)) != len(geometries):
        raise ParamError("geometries: the same geometry is listed twice")
    if p["compare"] == "geometry" and len(geometries) > MAX_GEOMETRIES:
        raise ParamError(f"geometries: compare at most {MAX_GEOMETRIES} at a time")

    base = {name: p[name] for name in ("threshold_rule", "gate_space", "policy_pull", "trust_anchor")}
    if p["compare"] == "geometry":
        columns = [(g, dict(base)) for g in geometries]
    else:
        values = COMPARE_VALUES[p["compare"]]
        columns = [(geometries[0], {**base, p["compare"]: v}) for v in values][:MAX_COLUMNS]

    config = build_sim_config(sim_config)
    for name, limit in TRACE_LIMITS.items():
        if getattr(config, name) > limit:
            raise ParamError(f"{name}: the viewer handles at most {limit} "
                             f"(got {getattr(config, name)})")
    size = config.n_agents * config.n_ticks * len(columns)
    if size > TRACE_BUDGET:
        raise ParamError(
            f"This is too much to replay: {config.n_agents} agents x {config.n_ticks} ticks x "
            f"{len(columns)} columns = {size:,}, and the viewer handles {TRACE_BUDGET:,}. "
            "Use fewer agents, ticks or columns.")
    if any(c["threshold_rule"] == "matched_run" for _, c in columns) \
            and config.n_agents * config.n_ticks > MATCH_RUN_BUDGET:
        raise ParamError(
            f"matched_run searches for ε by running the model repeatedly, so it is limited to "
            f"{MATCH_RUN_BUDGET:,} agents x ticks (got {config.n_agents * config.n_ticks:,}). "
            "Use fewer agents or ticks, or another threshold rule.")

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
    matching = any(g != Geometry.EUCLIDEAN for g, _ in columns)   # anything to match to?
    with _RUN_LOCK:
        for geometry, choice in columns:
            run_config = dataclasses.replace(
                config, gate_space=choice["gate_space"], policy_pull=choice["policy_pull"],
                trust_anchor=choice["trust_anchor"])
            eps, coverage = _column_epsilon(run_config, geometry, choice["threshold_rule"],
                                            governance, policy, p["seed"], matching)
            run_config = dataclasses.replace(run_config, epsilon=eps)
            recorder = TraceRecorder()
            sim = Simulation(run_config, governance, policy, shocks, apply_shocks=bool(shocks),
                             seed=p["seed"], geometry=geometry, recorder=recorder)
            if not runs:        # identical for every column: same seed, same draws
                shared = _shared(sim, p, governance, shocks)
            start = recorder.measure(sim)
            sim.run()
            record = _run_record(sim, recorder, start, coverage)
            record["choices"] = dict(choice)
            if p["compare"] != "geometry":
                record["label"] = f"{record['label']} · {_VALUE_LABELS[choice[p['compare']]]}"
            runs.append(record)

    return {"shared": shared, "runs": runs}


def _reference_epsilon(config) -> float:
    """Euclidean's ε in the gate's own units: SimConfig.epsilon is in centred
    units, and the unit-cube gate measures half those distances."""
    return config.epsilon if config.gate_space == "centred" else config.epsilon / 2.0


def _pass_rate(config, geometry, eps, governance, policy, seeds) -> float:
    rates = []
    for seed in seeds:
        sim = Simulation(dataclasses.replace(config, epsilon=eps), governance, policy, [],
                         apply_shocks=False, seed=seed, geometry=geometry)
        sim.run()
        rates.append(sim.gate_pass_rate)
    return float(np.mean(rates))


def _column_epsilon(config, geometry, rule, governance, policy, seed, matching=True):
    """ε for one column under a threshold rule, and the matched start coverage."""
    ref = _reference_epsilon(config)
    if rule == "shared":
        return ref, None
    if geometry == Geometry.EUCLIDEAN:
        if not matching:
            return ref, None
        # Euclidean is the reference; report the coverage everyone is matched to.
        _, target = matched_epsilons(config, [Geometry.EUCLIDEAN], reference_epsilon=ref)
        return ref, (target if rule == "matched_start" else None)
    if rule == "matched_start":
        eps, coverage = matched_epsilons(config, [Geometry.EUCLIDEAN, geometry],
                                         reference_epsilon=ref)
        return eps[geometry.value], coverage
    # matched_run: a short bisection on pilot seeds the viewer does not show.
    pilots = [seed + 1000 + k for k in range(3)]
    target = _pass_rate(config, Geometry.EUCLIDEAN, ref, governance, policy, pilots)
    lo, hi = 0.0, geometry_spec(geometry).max_distance(config.opinion_dim)
    eps = 0.5 * (lo + hi)
    for _ in range(8):
        eps = 0.5 * (lo + hi)
        rate = _pass_rate(config, geometry, eps, governance, policy, pilots)
        lo, hi = (eps, hi) if rate < target else (lo, eps)
    return eps, None


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
