"""
policyswarm.dynamics
====================
Core agent-based model simulation engine.

The Simulation class implements the full multi-component step() loop:

  1. Time-varying policy update (once, at policy_split_tick)
  2. Shock application   (exogenous perturbation)
  3. Media broadcast     (ideology-aligned competing media)
  4. Peer interactions   (bounded-confidence update, geometry-dependent)
  5. Policy anchor       (weak ungated pull toward the policy vector)
  6. Perceived-policy pull (trust-weighted, after the pull onset)

Opinions live in the centred cube [-1, 1]^d (0 = neutral); see config.py.
Distance and update rules for each geometry live in geometry.py.

Random streams
--------------
Three independent generators are derived from the seed so that the paired
control/treatment design differs *only* in shock application:
  _rng        agent initialisation
  _shock_rng  shock target sampling (consumed only when shocks are applied)
  _pull_rng   perceived-policy noise
Peer sampling uses the stdlib ``random`` module, seeded per simulation.

Changes from original
---------------------
_apply_policy_shift
    Uses Policy.shift_dimension() instead of direct attribute assignment.
    Works for any N-dim policy as long as the schema includes "enforcement"
    and "audit_intensity". Silently skips dimensions not in schema.

_is_violator
    Reads Policy.violator_dim_index and Policy.violator_threshold rather
    than hardcoding dim 0 > 0.8. Schema-driven.

_policy_pull_step
    Passes Policy.dimension_salience to perceived_policy() instead of relying
    on the hardcoded AI-policy bias. Also scales per-dimension noise by inverse
    confidence so low-confidence dimensions contribute more noise.
"""

from __future__ import annotations

import copy
import logging
import random
from typing import List

import networkx as nx
import numpy as np

from . import geometry as _geom
from .config import (
    DEFAULT_SPLIT_DELTAS, GATE_SPACES, GATED_POLICY_RATE, POLICY_PULLS,
    Geometry, GovernanceConfig, Policy, ShockMode, SimConfig,
)
from .extraction import perceived_policy as _perceived_policy
from .network import build_neighbour_cache, build_network, top_hub_indices
from .shocks import ShockSchedule, apply_shock_to_opinions

log = logging.getLogger("policyswarm")

_LOG_THRESHOLD = 0.01


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class Simulation:
    """Agent-based opinion dynamics simulation.

    Parameters
    ----------
    sim_config : SimConfig
    gov_config : GovernanceConfig
    policy : Policy
        N-D policy object. opinion_dim in sim_config must equal policy.dim.
    shocks : ShockSchedule
    apply_shocks : bool
    seed : int
    geometry : Geometry
    recorder : object, optional
        Observer of what happens inside each tick (see
        ``policyswarm.trace.TraceRecorder``). It is only ever told what
        happened; it draws no random numbers and changes no state, so a
        recorded run is numerically identical to an unrecorded one.
    """

    def __init__(
        self,
        sim_config   : SimConfig,
        gov_config   : GovernanceConfig,
        policy       : Policy,
        shocks       : ShockSchedule,
        apply_shocks : bool     = True,
        seed         : int      = 0,
        geometry     : Geometry = Geometry.EUCLIDEAN,
        recorder                = None,
    ):
        self.sim_config   = sim_config
        self.gov_config   = gov_config
        # copy.copy uses Policy.__copy__ which deep-copies numpy arrays,
        # preventing _apply_policy_shift from mutating the caller's policy.
        self.policy       = copy.copy(policy)
        self.shocks       = shocks
        self.apply_shocks = apply_shocks
        self.seed         = seed
        self.geometry     = geometry
        self.recorder     = recorder

        if sim_config.gate_space not in GATE_SPACES:
            raise ValueError(f"gate_space must be one of {GATE_SPACES}")
        if sim_config.policy_pull not in POLICY_PULLS:
            raise ValueError(f"policy_pull must be one of {POLICY_PULLS}")
        self._unit_gate   = sim_config.gate_space == "unit"
        self._gated_pull  = sim_config.policy_pull == "gated"

        np.random.seed(seed)
        random.seed(seed)
        self._rng       = np.random.default_rng(seed)
        self._shock_rng = np.random.default_rng([seed, 1])
        self._pull_rng  = np.random.default_rng([seed, 2])

        self._init_agents()

        # Bounded-confidence gate bookkeeping (see gate_pass_rate)
        self.gate_attempts = 0
        self.gate_passes   = 0
        self.history        : List[np.ndarray] = []
        self.influence_graph: nx.DiGraph        = nx.DiGraph()

        self._policy_applied: bool = False

        self._shock_index = {}
        for ev in shocks:
            self._shock_index.setdefault(ev["tick"], []).append(ev)

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def _init_agents(self) -> None:
        n   = self.sim_config.n_agents
        dim = self.sim_config.opinion_dim

        self.opinions = self._rng.uniform(-1.0, 1.0, size=(n, dim))
        self.initial_opinions = self.opinions.copy()

        self.graph, self.influence, self.community_labels = build_network(
            self.sim_config, seed=self.seed
        )
        self.neighbors    = build_neighbour_cache(self.graph)
        self._hub_indices = top_hub_indices(self.graph, k=10)

        self.ideology = self._rng.uniform(-1.0, 1.0, size=n)
        self.trust    = self._rng.beta(2, 2, size=n)

    # -----------------------------------------------------------------------
    # Geometry
    # -----------------------------------------------------------------------

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        if self._unit_gate:
            a, b = (a + 1.0) / 2.0, (b + 1.0) / 2.0
        return _geom.distance(self.geometry, a, b)

    def _step_toward(self, op_i: np.ndarray, op_j: np.ndarray, rate: float) -> np.ndarray:
        if self._unit_gate:
            moved = _geom.step(self.geometry, (op_i + 1.0) / 2.0, (op_j + 1.0) / 2.0, rate)
            return 2.0 * moved - 1.0
        return _geom.step(self.geometry, op_i, op_j, rate)

    def _retract(self, op: np.ndarray) -> np.ndarray:
        return np.clip(op, -1.0, 1.0)

    # -----------------------------------------------------------------------
    # Shock step
    # -----------------------------------------------------------------------

    def _shock_step(self, tick: int) -> None:
        if not self.apply_shocks:
            return
        for shock in self._shock_index.get(tick, []):
            if shock["type"] == "hub":
                targets = self._hub_indices[:self.sim_config.ba_m * 3]
            else:
                targets = list(self._shock_rng.choice(
                    self.sim_config.n_agents,
                    size=min(10, self.sim_config.n_agents),
                    replace=False,
                ))

            policy_vec = (
                self.policy.as_vector()
                if shock.get("mode") == ShockMode.DIRECTIONAL.value
                else None
            )

            old = self.opinions[targets].copy()
            apply_shock_to_opinions(
                self.opinions, targets, shock,
                policy_vector=policy_vec, rng=self._shock_rng,
            )
            if self.recorder is not None:
                self.recorder.shock(shock, targets)
            for idx, t in enumerate(targets):
                change = float(np.linalg.norm(self.opinions[t] - old[idx]))
                if change > _LOG_THRESHOLD:
                    self._log_influence("shock", t, change, tick)

    # -----------------------------------------------------------------------
    # Media step
    # -----------------------------------------------------------------------

    def _media_step(self, tick: int) -> None:
        if not self.gov_config.enable_media:
            return

        policy_vec = self.policy.as_vector()
        strength   = self.gov_config.media_strength
        n          = self.sim_config.n_agents

        for i in range(n):
            ideology = self.ideology[i]
            trust    = self.trust[i]

            if ideology > 0:
                target = policy_vec
                mag    = strength * ideology * trust
                source = "media_pro"
            else:
                target = - policy_vec
                mag    = strength * (-ideology) * trust
                source = "media_anti"

            old = self.opinions[i].copy()
            self.opinions[i] += mag * (target - self.opinions[i])
            self.opinions[i] = np.clip(self.opinions[i], -1.0, 1.0)

            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence(source, i, change, tick)

    # -----------------------------------------------------------------------
    # Peer interaction step
    # -----------------------------------------------------------------------

    def _peer_step(self, tick: int) -> None:
        n       = self.sim_config.n_agents
        mu      = self.sim_config.mu
        epsilon = self.sim_config.epsilon
        lag     = self.policy.lag
        gov     = self.gov_config
        rec     = self.recorder

        for _ in range(self.sim_config.interactions):
            i = random.randrange(n)
            if not self.neighbors[i]:
                continue
            j = random.choice(self.neighbors[i])

            if random.random() > gov.deployment_rate_cap:
                if rec is not None:
                    rec.conversation(i, j, "blocked")
                continue

            self.gate_attempts += 1
            dist = self._distance(self.opinions[i], self.opinions[j])
            if dist > epsilon:
                if rec is not None:
                    rec.conversation(i, j, "too_far", dist)
                continue
            self.gate_passes += 1

            infl = self.influence[j]

            penalised = False
            if tick >= lag:
                if self._is_violator(j):
                    infl *= (1.0 - gov.penalty_severity)
                    penalised = True

            old = self.opinions[i].copy()

            self.opinions[i] = self._retract(
                self._step_toward(self.opinions[i], self.opinions[j], mu * infl)
            )
            if self._gated_pull:
                self.opinions[i] = self._retract(
                    self.opinions[i]
                    + GATED_POLICY_RATE * (self.policy.as_vector() - self.opinions[i])
                )

            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence(j, i, change, tick)
            if rec is not None:
                rec.conversation(i, j, "penalised" if penalised else "heard", dist, change)

    # -----------------------------------------------------------------------
    # Policy anchor step
    # -----------------------------------------------------------------------

    def _policy_anchor_step(self, tick: int) -> None:
        """Weak, ungated pull of every agent toward the policy vector.

        Replaces the 0.05 * (p - o_i) nudge that used to be applied inside the
        peer loop only when the bounded-confidence gate passed. Keeping it
        there made the policy pull scale with the gate pass rate, i.e. with
        geometry and epsilon, which confounded geometry comparisons.
        """
        rate = self.sim_config.policy_anchor_rate
        if rate <= 0 or self._gated_pull:
            return
        old = self.opinions.copy()
        self.opinions = self._retract(
            self.opinions + rate * (self.policy.as_vector() - self.opinions)
        )
        changes = np.linalg.norm(self.opinions - old, axis=1)
        for i in np.flatnonzero(changes > _LOG_THRESHOLD):
            self._log_influence("policy", int(i), float(changes[i]), tick)

    # -----------------------------------------------------------------------
    # Policy pull step — UPDATED for generic N-dim policy
    # -----------------------------------------------------------------------

    def _policy_pull_step(self, tick: int) -> None:
        """
        Trust-weighted perceived-policy pull on each agent.

        Passes Policy.dimension_salience to perceived_policy() rather than
        relying on the hardcoded AI-policy bias vector. Also scales per-dimension
        noise by inverse confidence: dimensions the extractor was uncertain about
        get more perceptual noise in agents' interpretation.
        """
        onset = self.gov_config.policy_pull_onset
        if tick < (self.policy.lag if onset is None else onset):
            return

        policy_vec = self.policy.as_vector()
        n          = self.sim_config.n_agents

        # noise_scale shape: (d,) — low confidence → higher noise
        # confidence ∈ [0, 1], so (2 - confidence) ∈ [1, 2]
        # base scale 0.03 * (2 - confidence) → range [0.03, 0.06]
        noise_scale = 0.03 * (2.0 - self.policy.confidence)

        for i in range(n):
            pp = _perceived_policy(
                policy_vec,
                ideology           = self.ideology[i],
                trust              = self.trust[i],
                dimension_salience = self.policy.dimension_salience,
                noise_scale        = noise_scale,
                rng                = self._pull_rng,
            )
            old = self.opinions[i].copy()
            self.opinions[i] = np.clip(
                self.opinions[i] + 0.04 * (pp - self.opinions[i]),
                -1.0, 1.0,
            )
            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence("policy", i, change, tick)

    # -----------------------------------------------------------------------
    # Time-varying policy update — UPDATED for generic N-dim policy
    # -----------------------------------------------------------------------

    def _check_policy_update(self, tick: int) -> None:
        split = self.sim_config.policy_split_tick
        if tick == split and not self._policy_applied:
            self._apply_policy_shift()
            self._policy_applied = True

    def _apply_policy_shift(self) -> None:
        """
        Tighten the policy at policy_split_tick.

        Each dimension named in ``Policy.split_deltas`` shifts by its delta
        (centred units). A policy that does not set ``split_deltas`` gets the
        built-in ``DEFAULT_SPLIT_DELTAS`` (enforcement and audit intensity);
        names the policy does not have are skipped, so a schema without those
        dimensions is simply not tightened.
        """
        deltas = self.policy.split_deltas
        if deltas is None:
            deltas = DEFAULT_SPLIT_DELTAS
        for name, delta in deltas.items():
            try:
                self.policy.shift_dimension(name, delta)
            except KeyError:
                log.debug(
                    f"_apply_policy_shift: dimension '{name}' not in schema, skipping."
                )

    # -----------------------------------------------------------------------
    # Helpers — UPDATED for generic N-dim policy
    # -----------------------------------------------------------------------

    def _is_violator(self, agent_idx: int) -> bool:
        """
        Agent is a violator if the policy's designated violator dimension
        exceeds the schema-defined threshold.

        Reads Policy.violator_dim_index and Policy.violator_threshold, which
        are set by the schema YAML (Tier 1) or corpus analysis (Tier 2).
        Defaults to dim 0 > 0.8 for the legacy AI-policy schema.
        """
        idx   = self.policy.violator_dim_index
        thresh = self.policy.violator_threshold
        return bool(self.opinions[agent_idx, idx] > thresh)

    def _log_influence(
        self, source, target: int, weight: float, tick: int
    ) -> None:
        if self.influence_graph.has_edge(source, target):
            self.influence_graph[source][target]["weight"] += weight
        else:
            self.influence_graph.add_edge(
                source, target, weight=weight, tick=tick
            )

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------

    def step(self, tick: int) -> None:
        self._check_policy_update(tick)
        if self.recorder is not None:
            self.recorder.begin_tick(tick, self)
        self._phase("shock",  self._shock_step, tick)
        self._phase("media",  self._media_step, tick)
        self._phase("peer",   self._peer_step, tick)
        self._phase("policy", self._policy_anchor_step, tick)
        self._phase("policy", self._policy_pull_step, tick)
        self.history.append(self.opinions.copy())
        if self.recorder is not None:
            self.recorder.end_tick(tick, self)

    def _phase(self, name: str, phase_step, tick: int) -> None:
        """Run one phase of a tick, telling the recorder how far it moved each agent."""
        if self.recorder is None:
            phase_step(tick)
            return
        before = self.opinions.copy()
        phase_step(tick)
        self.recorder.phase(name, np.linalg.norm(self.opinions - before, axis=1))

    def run(self) -> List[np.ndarray]:
        for t in range(self.sim_config.n_ticks):
            self.step(t)
        return self.history

    # -----------------------------------------------------------------------
    # Public accessors
    # -----------------------------------------------------------------------

    @property
    def gate_pass_rate(self) -> float:
        """Fraction of peer interaction attempts that passed the
        bounded-confidence gate over the whole run (after the deployment-cap
        gate). Reported so geometry comparisons can verify coverage matching
        holds beyond initialisation."""
        if self.gate_attempts == 0:
            return float("nan")
        return self.gate_passes / self.gate_attempts

    @property
    def final_opinions(self) -> np.ndarray:
        return self.history[-1] if self.history else self.opinions

    @property
    def pre_opinions(self) -> np.ndarray:
        split = self.sim_config.policy_split_tick
        if len(self.history) <= split:
            return self.history[0] if self.history else self.opinions
        return self.history[split - 1]

    @property
    def post_opinions(self) -> np.ndarray:
        return self.final_opinions
