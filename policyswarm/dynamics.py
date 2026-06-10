"""
policyswarm.dynamics
====================
Core agent-based model simulation engine.

The Simulation class implements the full multi-component step() loop:

  1. Time-varying policy update (once, at policy_split_tick)
  2. Shock application   (exogenous perturbation)
  3. Media broadcast     (ideology-aligned competing media)
  4. Peer interactions   (bounded-confidence update)
  5. Perceived-policy pull (trust-weighted)

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
from typing import List, Optional

import networkx as nx
import numpy as np

from .config import (
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

        np.random.seed(seed)
        random.seed(seed)
        self._rng = np.random.default_rng(seed)

        self._init_agents()
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

        self.opinions = self._rng.random((n, dim))
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
        if self.geometry == Geometry.EUCLIDEAN:
            return float(np.linalg.norm(a - b))

        elif self.geometry == Geometry.COSINE:
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na < 1e-9 or nb < 1e-9:
                return 1.0
            cos = np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0)
            return float(1.0 - cos)

        elif self.geometry == Geometry.MANIFOLD:
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na < 1e-9 or nb < 1e-9:
                return 1.0
            dot = np.clip(np.dot(a / na, b / nb), -1.0, 1.0)
            return float(np.arccos(dot))

        raise ValueError(f"Unknown geometry: {self.geometry}")

    def _update_direction(self, op_i: np.ndarray, op_j: np.ndarray) -> np.ndarray:
        if self.geometry == Geometry.EUCLIDEAN:
            return op_j - op_i

        elif self.geometry == Geometry.COSINE:
            nj = np.linalg.norm(op_j)
            ni = np.linalg.norm(op_i)
            if nj < 1e-9 or ni < 1e-9:
                return np.zeros_like(op_i)
            return op_j / nj - op_i / ni

        elif self.geometry == Geometry.MANIFOLD:
            na = np.linalg.norm(op_i)
            nb = np.linalg.norm(op_j)
            if na < 1e-9 or nb < 1e-9:
                return np.zeros_like(op_i)
            a_n = op_i / na
            b_n = op_j / nb
            tangent = b_n - np.dot(a_n, b_n) * a_n
            return tangent

        raise ValueError(f"Unknown geometry: {self.geometry}")

    def _retract(self, op: np.ndarray) -> np.ndarray:
        return np.clip(op, 0.0, 1.0)

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
                targets = list(self._rng.choice(
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
                policy_vector=policy_vec, rng=self._rng,
            )
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
                target = 1.0 - policy_vec
                mag    = strength * (-ideology) * trust
                source = "media_anti"

            old = self.opinions[i].copy()
            self.opinions[i] += mag * (target - self.opinions[i])
            self.opinions[i] = np.clip(self.opinions[i], 0.0, 1.0)

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

        for _ in range(self.sim_config.interactions):
            i = random.randrange(n)
            if not self.neighbors[i]:
                continue
            j = random.choice(self.neighbors[i])

            if random.random() > gov.deployment_rate_cap:
                continue

            if self._distance(self.opinions[i], self.opinions[j]) > epsilon:
                continue

            infl = self.influence[j]

            if tick >= lag:
                if self._is_violator(j):
                    infl *= (1.0 - gov.penalty_severity)

            old = self.opinions[i].copy()

            direction = self._update_direction(self.opinions[i], self.opinions[j])
            self.opinions[i] = self._retract(
                self.opinions[i] + mu * infl * direction
            )

            policy_vec = self.policy.as_vector()
            self.opinions[i] = np.clip(
                self.opinions[i] + 0.05 * (policy_vec - self.opinions[i]),
                0.0, 1.0,
            )

            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence(j, i, change, tick)

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
        if tick < self.policy.lag:
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
                rng                = self._rng,
            )
            old = self.opinions[i].copy()
            self.opinions[i] = np.clip(
                self.opinions[i] + 0.04 * (pp - self.opinions[i]),
                0.0, 1.0,
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
        Tighten enforcement at policy_split_tick.

        Uses Policy.shift_dimension() which works for any schema. If the
        schema doesn't include "enforcement" or "audit_intensity" (domain-
        agnostic case), the KeyError is caught and the shift skipped. Domain-
        specific experiment subclasses should override this method to implement
        their own policy update semantics.
        """
        for name, delta in [("enforcement", 0.15), ("audit_intensity", 0.10)]:
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
        self._shock_step(tick)
        self._media_step(tick)
        self._peer_step(tick)
        self._policy_pull_step(tick)
        self.history.append(self.opinions.copy())

    def run(self) -> List[np.ndarray]:
        for t in range(self.sim_config.n_ticks):
            self.step(t)
        return self.history

    # -----------------------------------------------------------------------
    # Public accessors
    # -----------------------------------------------------------------------

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
