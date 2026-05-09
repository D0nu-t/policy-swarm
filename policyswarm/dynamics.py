"""
policyswarm.dynamics
====================
Core agent-based model simulation engine.

The Simulation class implements the full multi-component step() loop:

  1. Shock application   (exogenous perturbation — Iteration 10)
  2. Media broadcast     (ideology-aligned competing media — Iteration 8)
  3. Peer interactions   (bounded-confidence update — Iterations 1–12)
  4. Policy pull         (perceived_policy, trust-weighted — Iteration 6)
  5. Time-varying policy update (single-application gate — Iteration 9)

All inter-agent influence events that cross the change threshold (0.01) are
logged to ``self.influence_graph`` (DiGraph) with edge attributes:
  weight : cumulative magnitude of opinion change caused
  tick   : tick at which the first (or largest) change occurred
  source_type : "peer" | "media_pro" | "media_anti" | "shock" | "policy"

The paired counterfactual design (Iteration 10) is implemented by:
  - Generating shocks once, outside the Simulation
  - Passing the same ShockSchedule to both control and treatment Simulations
  - Setting apply_shocks=False in the control run

Geometry of opinion space (Iteration 12):
  - Euclidean : standard L2 distance and linear interpolation update
  - Cosine    : angular distance; updates in normalised direction space
  - Manifold  : geodesic retraction onto unit hypersphere S^(d-1)
"""

from __future__ import annotations

import copy
import random
from typing import List, Optional, Tuple

import numpy as np
import networkx as nx

from .config import (
    SimConfig, GovernanceConfig, Policy, Geometry, ShockMode
)
from .extraction import perceived_policy as _perceived_policy
from .network import build_network, build_neighbour_cache, top_hub_indices
from .shocks import ShockSchedule, apply_shock_to_opinions

# Minimum opinion change to log in the influence graph
_LOG_THRESHOLD = 0.01


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class Simulation:
    """Agent-based opinion dynamics simulation.

    Parameters
    ----------
    sim_config : SimConfig
        Mechanical simulation parameters.
    gov_config : GovernanceConfig
        Regulatory regime parameters.
    policy : Policy
        4-D policy object produced by the KG extraction layer.
    shocks : ShockSchedule
        Pre-generated shock schedule (list of dicts). Shared between paired
        control/treatment runs for causal validity.
    apply_shocks : bool
        Whether to apply shocks during the run. False = control condition.
        Default True.
    seed : int
        Random seed for agent initialisation and peer-interaction sampling.
        Default 0.
    geometry : Geometry
        Opinion-space metric. Default Geometry.EUCLIDEAN.

    Attributes
    ----------
    opinions : np.ndarray, shape (n_agents, opinion_dim)
        Current opinion matrix.
    initial_opinions : np.ndarray
        Snapshot of opinions at tick 0 (before any dynamics).
    history : list of np.ndarray
        One snapshot per tick, shape (n_agents, opinion_dim).
    influence_graph : nx.DiGraph
        Weighted directed causal influence graph.
    community_labels : np.ndarray, shape (n_agents,)
        Community membership for each agent.
    """

    def __init__(
        self,
        sim_config   : SimConfig,
        gov_config   : GovernanceConfig,
        policy       : Policy,
        shocks       : ShockSchedule,
        apply_shocks : bool       = True,
        seed         : int        = 0,
        geometry     : Geometry   = Geometry.EUCLIDEAN,
    ):
        self.sim_config   = sim_config
        self.gov_config   = gov_config
        # Deep-copy the policy so _apply_policy_shift() cannot corrupt the
        # caller's object or any other Simulation sharing the same policy.
        self.policy       = copy.copy(policy)
        self.shocks       = shocks
        self.apply_shocks = apply_shocks
        self.seed         = seed
        self.geometry     = geometry

        # Seed both numpy and python random for full reproducibility
        np.random.seed(seed)
        random.seed(seed)
        self._rng = np.random.default_rng(seed)

        self._init_agents()
        self.history        : List[np.ndarray] = []
        self.influence_graph: nx.DiGraph        = nx.DiGraph()

        # Time-varying policy gate (Iteration 9 bug fix: attribute, not hasattr)
        self._policy_applied: bool = False

        # Build shock lookup: tick → list of events for O(1) per-tick dispatch
        self._shock_index = {}
        for ev in shocks:
            self._shock_index.setdefault(ev["tick"], []).append(ev)

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def _init_agents(self) -> None:
        """Initialise the agent population and network."""
        n   = self.sim_config.n_agents
        dim = self.sim_config.opinion_dim

        # ── Opinion vectors ∈ [0,1]^dim
        self.opinions = self._rng.random((n, dim))
        self.initial_opinions = self.opinions.copy()

        # ── Network
        self.graph, self.influence, self.community_labels = build_network(
            self.sim_config, seed=self.seed
        )
        self.neighbors = build_neighbour_cache(self.graph)
        self._hub_indices = top_hub_indices(self.graph, k=10)

        # ── Agent attributes
        self.ideology = self._rng.uniform(-1.0, 1.0, size=n)
        self.trust    = self._rng.beta(2, 2, size=n)

    # -----------------------------------------------------------------------
    # Geometry
    # -----------------------------------------------------------------------

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute opinion-space distance between two agents."""
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
            a_n = a / na
            b_n = b / nb
            # Geodesic distance on S^(d-1)
            dot = np.clip(np.dot(a_n, b_n), -1.0, 1.0)
            return float(np.arccos(dot))

        raise ValueError(f"Unknown geometry: {self.geometry}")

    def _update_direction(
        self, op_i: np.ndarray, op_j: np.ndarray
    ) -> np.ndarray:
        """Compute the update direction from agent i toward agent j."""
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
            # Parallel transport tangent vector
            tangent = b_n - np.dot(a_n, b_n) * a_n
            return tangent

        raise ValueError(f"Unknown geometry: {self.geometry}")

    def _retract(self, op: np.ndarray) -> np.ndarray:
        """Clip opinion vector back into [0, 1]^d after an update step.

        The MANIFOLD geometry uses geodesic distances and tangent-vector update
        directions on S^(d-1), but the original sphere-projection retraction
        (1 + op/||op||) / 2 maps all opinions into [0.5, 1.0]^d, collapsing
        variance to near zero within a few ticks. Simple clipping preserves
        the geometric update semantics while keeping opinions in valid range.
        """
        return np.clip(op, 0.0, 1.0)

    # -----------------------------------------------------------------------
    # Shock step
    # -----------------------------------------------------------------------

    def _shock_step(self, tick: int) -> None:
        """Apply all scheduled shocks at this tick."""
        if not self.apply_shocks:
            return
        for shock in self._shock_index.get(tick, []):
            if shock["type"] == "hub":
                targets = self._hub_indices[:self.sim_config.ba_m * 3]
            else:
                targets = list(self._rng.choice(
                    self.sim_config.n_agents,
                    size=min(10, self.sim_config.n_agents),
                    replace=False
                ))

            policy_vec = (
                self.policy.as_vector()
                if shock.get("mode") == ShockMode.DIRECTIONAL.value
                else None
            )

            old = self.opinions[targets].copy()
            apply_shock_to_opinions(
                self.opinions, targets, shock,
                policy_vector=policy_vec, rng=self._rng
            )
            for idx, t in enumerate(targets):
                change = float(np.linalg.norm(self.opinions[t] - old[idx]))
                if change > _LOG_THRESHOLD:
                    self._log_influence("shock", t, change, tick)

    # -----------------------------------------------------------------------
    # Media step (Iteration 8)
    # -----------------------------------------------------------------------

    def _media_step(self, tick: int) -> None:
        """Ideology-aligned competing media broadcast."""
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
    # Peer interaction step (Iteration 1–5)
    # -----------------------------------------------------------------------

    def _peer_step(self, tick: int) -> None:
        """Bounded-confidence peer interaction."""
        n          = self.sim_config.n_agents
        mu         = self.sim_config.mu
        epsilon    = self.sim_config.epsilon
        lag        = self.policy.lag
        gov        = self.gov_config

        for _ in range(self.sim_config.interactions):
            i = random.randrange(n)
            if not self.neighbors[i]:
                continue
            j = random.choice(self.neighbors[i])

            # Deployment rate cap gates interaction probability
            if random.random() > gov.deployment_rate_cap:
                continue

            if self._distance(self.opinions[i], self.opinions[j]) > epsilon:
                continue

            # Effective influence of j
            infl = self.influence[j]

            # Penalty on violators post-lag (Iteration 5)
            if tick >= lag:
                if self._is_violator(j):
                    infl *= (1.0 - gov.penalty_severity)

            old = self.opinions[i].copy()

            # Peer update
            direction = self._update_direction(self.opinions[i], self.opinions[j])
            self.opinions[i] = self._retract(
                self.opinions[i] + mu * infl * direction
            )

            # Weak policy pull (Iteration 4)
            policy_vec = self.policy.as_vector()
            self.opinions[i] = np.clip(
                self.opinions[i] + 0.05 * (policy_vec - self.opinions[i]),
                0.0, 1.0
            )

            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence(j, i, change, tick)

    # -----------------------------------------------------------------------
    # Policy pull step (Iteration 6 — perceived_policy)
    # -----------------------------------------------------------------------

    def _policy_pull_step(self, tick: int) -> None:
        """Trust-weighted perceived-policy pull on each agent."""
        if tick < self.policy.lag:
            return

        policy_vec = self.policy.as_vector()
        n          = self.sim_config.n_agents

        for i in range(n):
            pp  = _perceived_policy(
                policy_vec,
                ideology    = self.ideology[i],
                trust       = self.trust[i],
                noise_scale = 0.03,
                rng         = self._rng,
            )
            old = self.opinions[i].copy()
            self.opinions[i] = np.clip(
                self.opinions[i] + 0.04 * (pp - self.opinions[i]),
                0.0, 1.0
            )
            change = float(np.linalg.norm(self.opinions[i] - old))
            if change > _LOG_THRESHOLD:
                self._log_influence("policy", i, change, tick)

    # -----------------------------------------------------------------------
    # Time-varying policy update (Iteration 9)
    # -----------------------------------------------------------------------

    def _check_policy_update(self, tick: int) -> None:
        """Apply a one-time policy tightening at policy_split_tick.

        The `_policy_applied` flag (not hasattr check) prevents re-application
        on subsequent ticks — the bug documented in Iteration 9.
        """
        split = self.sim_config.policy_split_tick
        if tick == split and not self._policy_applied:
            self._apply_policy_shift()
            self._policy_applied = True

    def _apply_policy_shift(self) -> None:
        """Tighten enforcement: raise enforcement and audit by 0.15."""
        self.policy.enforcement     = min(1.0, self.policy.enforcement + 0.15)
        self.policy.audit_intensity = min(1.0, self.policy.audit_intensity + 0.10)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _is_violator(self, agent_idx: int) -> bool:
        """Agent is a violator if opinion[0] (deployment_cap dimension) > 0.8."""
        return bool(self.opinions[agent_idx, 0] > 0.8)

    def _log_influence(
        self, source, target: int, weight: float, tick: int
    ) -> None:
        """Accumulate edge weight in the causal influence graph."""
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
        """Execute one simulation tick.

        Order (matching the design document architecture):
        1. Time-varying policy update (once, at policy_split_tick)
        2. Shock application
        3. Media broadcast
        4. Peer interactions
        5. Perceived-policy pull
        """
        self._check_policy_update(tick)
        self._shock_step(tick)
        self._media_step(tick)
        self._peer_step(tick)
        self._policy_pull_step(tick)

        self.history.append(self.opinions.copy())

    def run(self) -> List[np.ndarray]:
        """Run the simulation for sim_config.n_ticks ticks.

        Returns
        -------
        history : list of np.ndarray
            One opinion snapshot per tick.
        """
        for t in range(self.sim_config.n_ticks):
            self.step(t)
        return self.history

    # -----------------------------------------------------------------------
    # Public accessors
    # -----------------------------------------------------------------------

    @property
    def final_opinions(self) -> np.ndarray:
        """Opinion matrix at the last simulated tick."""
        return self.history[-1] if self.history else self.opinions

    @property
    def pre_opinions(self) -> np.ndarray:
        """Last opinion snapshot before the policy split tick."""
        split = self.sim_config.policy_split_tick
        if len(self.history) <= split:
            return self.history[0] if self.history else self.opinions
        return self.history[split - 1]

    @property
    def post_opinions(self) -> np.ndarray:
        """Last opinion snapshot (same as final_opinions, provided for symmetry)."""
        return self.final_opinions