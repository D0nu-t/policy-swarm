"""
policyswarm.config
==================
All configuration dataclasses and enumerations used throughout the framework.

Design note
-----------
Configuration is deliberately split into three orthogonal concerns:

  SimConfig        – simulation mechanics (agent count, tick budget, interaction rate)
  GovernanceConfig – regulatory regime parameters (caps, penalties, lag)
  Policy           – the 4-D policy object produced by the KG extraction layer

This separation allows fixing governance while varying simulation mechanics, or
vice-versa, without coupling changes across the codebase.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OverlapRegime(str, Enum):
    """Ordinal oversight regimes used in Experiment 1.

    Maps to (deployment_rate_cap, penalty_severity) pairs that parametrize
    how strictly the governance framework curtails high-influence agents.

    Attributes
    ----------
    NONE        : No regulatory constraint. Baseline.
    VOLUNTARY   : Self-regulatory guidelines; no enforcement mechanism.
    MANDATORY   : Legally binding rules with non-trivial penalties.
    PROHIBITIVE : Near-complete ban on high-risk deployment.
    """
    NONE        = "none"
    VOLUNTARY   = "voluntary"
    MANDATORY   = "mandatory"
    PROHIBITIVE = "prohibitive"


REGIME_PARAMS: Dict[OverlapRegime, Dict[str, float]] = {
    OverlapRegime.NONE        : {"deployment_rate_cap": 1.0, "penalty_severity": 0.0},
    OverlapRegime.VOLUNTARY   : {"deployment_rate_cap": 0.8, "penalty_severity": 0.1},
    OverlapRegime.MANDATORY   : {"deployment_rate_cap": 0.5, "penalty_severity": 0.5},
    OverlapRegime.PROHIBITIVE : {"deployment_rate_cap": 0.2, "penalty_severity": 0.9},
}


class NetworkType(str, Enum):
    """Social network topology selection.

    Attributes
    ----------
    BARABASI_ALBERT      : Scale-free network via preferential attachment.
                           Reflects heavy-tailed influence distributions.
    STOCHASTIC_BLOCK     : Community-structured network (3 blocks).
                           Produces echo-chamber dynamics.
    """
    BARABASI_ALBERT  = "ba"
    STOCHASTIC_BLOCK = "sbm"


class Geometry(str, Enum):
    """Opinion-space metric for the bounded-confidence update rule.

    The geometry choice is a substantive modelling decision (see Iteration 12
    and Experiment 6 in the design document). Euclidean is the default and
    dominant choice in the literature; cosine and manifold are alternatives
    with distinct polarization properties.

    Attributes
    ----------
    EUCLIDEAN : L2 norm in R^d. Highest polarization.
    COSINE    : Angular disagreement only. Lowest polarization.
    MANIFOLD  : Geodesic retraction onto unit hypersphere S^(d-1).
    """
    EUCLIDEAN = "euclidean"
    COSINE    = "cosine"
    MANIFOLD  = "manifold"


class ShockMode(str, Enum):
    """Controls the directional character of exogenous shocks.

    Attributes
    ----------
    COORDINATING : Mean-reverting toward opinion-space centre (0.5).
                   Models crisis-induced consensus / coordinated messaging.
    POLARIZING   : Centrifugal push away from centre.
                   Models wedge events, disinformation campaigns.
    DIRECTIONAL  : Pull toward the current policy vector.
                   Used in Experiment 5 (centrality sweep) for coherent
                   signal propagation studies.
    """
    COORDINATING = "coordinating"
    POLARIZING   = "polarizing"
    DIRECTIONAL  = "directional"


# ---------------------------------------------------------------------------
# Simulation configuration
# ---------------------------------------------------------------------------

@dataclass
class SimConfig:
    """Mechanical parameters of the ABM simulation.

    Parameters
    ----------
    n_agents : int
        Number of agents in the population. Default 120.
    n_ticks : int
        Simulation duration in discrete time steps. Default 60.
    interactions : int
        Number of peer-interaction attempts per tick. Default 150.
    shock_prob : float
        Probability that an exogenous shock occurs on any given tick. Default 0.2.
    mu : float
        Opinion-update step size (convergence rate) in the bounded-confidence
        rule. Bounded to (0, 1]. Default 0.15.
    epsilon : float
        Global confidence radius. Agents only interact when their opinion
        distance is below this threshold. Default 0.5.
    network_type : NetworkType
        Social network topology. Default BARABASI_ALBERT.
    ba_m : int
        Edges added per node in BA preferential attachment. Default 3.
    sbm_n_communities : int
        Number of communities in the SBM topology. Default 3.
    sbm_p_in : float
        Within-community edge probability. Default 0.2.
    sbm_p_out : float
        Cross-community edge probability. Default 0.02.
    opinion_dim : int
        Dimensionality of the opinion vectors. Should match Policy.dim. Default 4.
    policy_split_tick : int
        Tick at which the pre/post variance measurement splits.
        Also the tick at which time-varying policy updates activate. Default 40.
    """
    n_agents        : int         = 120
    n_ticks         : int         = 60
    interactions    : int         = 150
    shock_prob      : float       = 0.2
    mu              : float       = 0.15
    epsilon         : float       = 0.5
    network_type    : NetworkType = NetworkType.BARABASI_ALBERT
    ba_m            : int         = 3
    sbm_n_communities: int        = 3
    sbm_p_in        : float       = 0.2
    sbm_p_out       : float       = 0.02
    opinion_dim     : int         = 4
    policy_split_tick: int        = 40

    def to_dict(self) -> dict:
        d = asdict(self)
        d["network_type"] = self.network_type.value
        return d


# ---------------------------------------------------------------------------
# Governance configuration
# ---------------------------------------------------------------------------

@dataclass
class GovernanceConfig:
    """Regulatory regime parameters.

    These map directly to simulation mechanics via the GovernanceConfig ×
    Simulation interface. They are the primary independent variables in most
    experiments.

    Parameters
    ----------
    oversight_regime : OverlapRegime
        Categorical regime label. When set, automatically populates
        deployment_rate_cap and penalty_severity from REGIME_PARAMS.
        If set to None, the individual float values are used directly.
    deployment_rate_cap : float
        Probability that any given peer interaction is permitted per tick.
        Models regulatory restriction on AI-system interaction frequency.
        Range [0, 1]. Default 0.5.
    penalty_severity : float
        Multiplicative reduction applied to the effective influence of
        "violator" agents (opinion[0] > 0.8 = extreme pro-AI stance).
        0 = no penalty, 1 = complete silencing. Default 0.3.
    enforcement_lag : int
        Ticks between simulation start and penalty activation. Key
        variable in Experiment 2. Default 10.
    enable_media : bool
        Whether ideology-aligned competing media broadcasts are active.
        Key variable in Experiment 3. Default True.
    media_strength : float
        Scalar on ideology-aligned media push. Default 0.1.
    """
    oversight_regime    : Optional[OverlapRegime] = None
    deployment_rate_cap : float                   = 0.5
    penalty_severity    : float                   = 0.3
    enforcement_lag     : int                     = 10
    enable_media        : bool                    = True
    media_strength      : float                   = 0.1

    def __post_init__(self):
        if self.oversight_regime is not None:
            params = REGIME_PARAMS[self.oversight_regime]
            self.deployment_rate_cap = params["deployment_rate_cap"]
            self.penalty_severity    = params["penalty_severity"]

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.oversight_regime is not None:
            d["oversight_regime"] = self.oversight_regime.value
        return d


# ---------------------------------------------------------------------------
# Policy object
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    """4-D regulatory policy object produced by the KG extraction layer.

    Each dimension represents an independently measurable aspect of a
    governance framework. Agent opinions are also 4-D, allowing agreement
    on one dimension while disagreeing on another.

    Parameters
    ----------
    deployment_cap : float
        Permissiveness of AI deployment. High = permissive. Range [0,1].
    transparency : float
        Disclosure requirement stringency. High = strict. Range [0,1].
    enforcement : float
        Penalty intensity (complement to GovernanceConfig.penalty_severity,
        which affects interaction; this affects the policy pull direction).
    audit_intensity : float
        Monitoring depth. High = extensive. Range [0,1].
    lag : int
        Enforcement lag in ticks. Overrides GovernanceConfig.enforcement_lag
        when passed to Simulation directly. Default 10.
    narrative : dict
        Framing weights extracted from policy text. Keys: "safety",
        "innovation", "transparency". Values in [0, 1].
    """
    deployment_cap  : float = 0.5
    transparency    : float = 0.5
    enforcement     : float = 0.5
    audit_intensity : float = 0.5
    lag             : int   = 10
    narrative       : Dict[str, float] = field(
        default_factory=lambda: {"safety": 0.5, "innovation": 0.5, "transparency": 0.5}
    )

    @property
    def dim(self) -> int:
        return 4

    def as_vector(self) -> np.ndarray:
        """Return the 4-D policy position as a NumPy array."""
        return np.array([
            self.deployment_cap,
            self.transparency,
            self.enforcement,
            self.audit_intensity,
        ], dtype=float)

    def to_dict(self) -> dict:
        return {
            "deployment_cap" : self.deployment_cap,
            "transparency"   : self.transparency,
            "enforcement"    : self.enforcement,
            "audit_intensity": self.audit_intensity,
            "lag"            : self.lag,
            "narrative"      : self.narrative,
        }


# ---------------------------------------------------------------------------
# Shock configuration
# ---------------------------------------------------------------------------

@dataclass
class ShockConfig:
    """Parameters governing the exogenous shock process.

    Parameters
    ----------
    shock_prob : float
        Per-tick probability of a shock. Default 0.2.
    min_strength : float
        Minimum shock magnitude. Default 0.1.
    max_strength : float
        Maximum shock magnitude. Default 0.4.
    mode : ShockMode
        Directional character of shocks. Default COORDINATING.
    n_targets : int
        Number of agents targeted per shock event. Default 10.
    """
    shock_prob   : float     = 0.2
    min_strength : float     = 0.1
    max_strength : float     = 0.4
    mode         : ShockMode = ShockMode.COORDINATING
    n_targets    : int       = 10
