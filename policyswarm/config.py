"""
policyswarm.config
==================
All configuration dataclasses and enumerations used throughout the framework.

Design note
-----------
Configuration is deliberately split into three orthogonal concerns:

  SimConfig        – simulation mechanics (agent count, tick budget, interaction rate)
  GovernanceConfig – regulatory regime parameters (caps, penalties, lag)
  Policy           – N-D policy object. Supports two construction modes:
                       Legacy: 4-dim named fields (backward compatible)
                       Generic: N-dim vector + dimension_names from extractor

The generic mode is required for Tier 1 (LLM extraction) and Tier 2 (embedding
extraction). The legacy mode keeps all existing experiments working unchanged.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OverlapRegime(str, Enum):
    """Ordinal oversight regimes used in Experiment 1."""
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
    BARABASI_ALBERT  = "ba"
    STOCHASTIC_BLOCK = "sbm"


class Geometry(str, Enum):
    """Opinion-space metric for the bounded-confidence update rule."""
    EUCLIDEAN = "euclidean"
    COSINE    = "cosine"
    MANIFOLD  = "manifold"


class ShockMode(str, Enum):
    COORDINATING = "coordinating"
    POLARIZING   = "polarizing"
    DIRECTIONAL  = "directional"


# ---------------------------------------------------------------------------
# Simulation configuration
# ---------------------------------------------------------------------------

@dataclass
class SimConfig:
    """Mechanical parameters of the ABM simulation."""
    n_agents         : int         = 120
    n_ticks          : int         = 60
    interactions     : int         = 150
    shock_prob       : float       = 0.2
    mu               : float       = 0.15
    epsilon          : float       = 0.5
    network_type     : NetworkType = NetworkType.BARABASI_ALBERT
    ba_m             : int         = 3
    sbm_n_communities: int         = 3
    sbm_p_in         : float       = 0.2
    sbm_p_out        : float       = 0.02
    opinion_dim      : int         = 4
    policy_split_tick: int         = 40

    def to_dict(self) -> dict:
        d = asdict(self)
        d["network_type"] = self.network_type.value
        return d


# ---------------------------------------------------------------------------
# Governance configuration
# ---------------------------------------------------------------------------

@dataclass
class GovernanceConfig:
    """Regulatory regime parameters."""
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
# Policy object — generic N-dim with legacy 4-dim backward compatibility
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    """
    N-dimensional regulatory policy object.

    Two construction modes:

    Legacy (4-dim AI policy, fully backward compatible — all existing
    experiments continue to work without any changes):

        Policy(deployment_cap=0.5, transparency=0.7, enforcement=0.8,
               audit_intensity=0.6, lag=10)

    Generic (N-dim, produced by LLMPolicyExtractor or EmbeddingPolicyExtractor):

        Policy(
            vector=np.array([0.5, 0.7, 0.8, 0.6]),
            dimension_names=["deployment_cap", "transparency",
                              "enforcement", "audit_intensity"],
            confidence=np.array([0.9, 0.8, 0.7, 0.6]),
            dimension_salience=np.array([-0.3, 0.1, 0.2, 0.15]),
            violator_dim_index=0,
            violator_threshold=0.8,
            lag=10,
        )

    Parameters
    ----------
    vector : np.ndarray, shape (n_dims,), optional
        Policy position vector. Takes precedence over named legacy fields
        when provided. All values in [0, 1].
    dimension_names : list of str, optional
        Human-readable name for each dimension. Required for shift_dimension()
        and for _apply_policy_shift() to locate "enforcement"/"audit_intensity".
    confidence : np.ndarray, shape (n_dims,), optional
        Per-dimension extraction confidence in [0, 1]. Used by perceived_policy()
        to scale perceptual noise: low-confidence dims get higher noise.
    dimension_salience : np.ndarray, shape (n_dims,), optional
        Per-dimension ideology sensitivity. Replaces the hardcoded
        [-0.3, 0.1, 0.2, 0.15] bias in perceived_policy(). Loaded from schema
        YAML or computed from PCA loadings (Tier 2).
    violator_dim_index : int
        Index of the dimension used for violator detection. Default 0
        (deployment_cap in the legacy schema).
    violator_threshold : float
        Threshold above which an agent on violator_dim_index is a "violator".
        Default 0.8.
    """

    # Generic fields (N-dim, optional — set by extractors)
    vector             : Optional[np.ndarray] = None
    dimension_names    : Optional[List[str]]  = None
    confidence         : Optional[np.ndarray] = None
    dimension_salience : Optional[np.ndarray] = None
    violator_dim_index : int                  = 0
    violator_threshold : float                = 0.8

    # Legacy named fields (4-dim AI policy, always present for compat)
    deployment_cap  : float = 0.5
    transparency    : float = 0.5
    enforcement     : float = 0.5
    audit_intensity : float = 0.5
    lag             : int   = 10
    narrative       : Dict[str, float] = field(
        default_factory=lambda: {
            "safety": 0.5, "innovation": 0.5, "transparency": 0.5
        }
    )

    def __post_init__(self):
        if self.vector is None:
            # Legacy construction: build vector from named fields
            self.vector = np.array([
                self.deployment_cap,
                self.transparency,
                self.enforcement,
                self.audit_intensity,
            ], dtype=float)
            if self.dimension_names is None:
                self.dimension_names = [
                    "deployment_cap", "transparency",
                    "enforcement", "audit_intensity",
                ]
        else:
            self.vector = np.asarray(self.vector, dtype=float)

        if self.dimension_names is None:
            self.dimension_names = [f"dim_{i}" for i in range(len(self.vector))]

        if self.confidence is None:
            self.confidence = np.ones(len(self.vector), dtype=float)
        else:
            self.confidence = np.asarray(self.confidence, dtype=float)

        if self.dimension_salience is None:
            if (
                len(self.vector) == 4
                and self.dimension_names[:4] == [
                    "deployment_cap", "transparency",
                    "enforcement", "audit_intensity",
                ]
            ):
                # Legacy default: AI policy hardcoded ideology bias
                self.dimension_salience = np.array([-0.3, 0.1, 0.2, 0.15])
            else:
                self.dimension_salience = np.zeros(len(self.vector), dtype=float)
        else:
            self.dimension_salience = np.asarray(self.dimension_salience, dtype=float)

        # Keep legacy named fields in sync with vector for any code that reads them
        self._sync_legacy_fields()

    def _sync_legacy_fields(self) -> None:
        """Sync the 4 legacy named fields from the vector when dimension names match."""
        legacy = {
            "deployment_cap": 0,
            "transparency":   1,
            "enforcement":    2,
            "audit_intensity": 3,
        }
        for name, expected_idx in legacy.items():
            if (
                name in self.dimension_names
                and self.dimension_names.index(name) < len(self.vector)
            ):
                idx = self.dimension_names.index(name)
                object.__setattr__(self, name, float(self.vector[idx]))

    def __setattr__(self, name: str, value) -> None:
        """
        Intercept direct field assignment to keep vector and legacy named
        fields in sync.

        After __post_init__ has run (i.e. vector and dimension_names are set),
        assigning to any of the four legacy fields also updates the
        corresponding vector element in-place.  This preserves backward
        compatibility with code that does ``policy.enforcement = 0.9``.

        During __init__ / __post_init__, when vector or dimension_names are
        not yet set, the AttributeError is silently caught so construction
        still works.
        """
        object.__setattr__(self, name, value)
        _LEGACY = {"deployment_cap", "transparency", "enforcement", "audit_intensity"}
        if name in _LEGACY:
            try:
                vec       = object.__getattribute__(self, "vector")
                dim_names = object.__getattribute__(self, "dimension_names")
                if vec is not None and dim_names is not None and name in dim_names:
                    idx = dim_names.index(name)
                    if idx < len(vec):
                        # In-place update preserves the array object reference
                        vec[idx] = float(value)
            except AttributeError:
                pass  # vector or dimension_names not yet initialised

    def __copy__(self) -> Policy:
        """Shallow copy that deep-copies numpy arrays to prevent cross-Simulation mutation."""
        new = object.__new__(Policy)
        new.__dict__.update(self.__dict__)
        new.vector             = self.vector.copy()
        new.confidence         = self.confidence.copy()
        new.dimension_salience = self.dimension_salience.copy()
        new.dimension_names    = list(self.dimension_names)
        new.narrative          = dict(self.narrative)
        return new

    @property
    def dim(self) -> int:
        return len(self.vector)

    def as_vector(self) -> np.ndarray:
        """Return the policy position as a NumPy array (copy)."""
        return self.vector.copy()

    def shift_dimension(self, name: str, delta: float) -> None:
        """
        Shift a named dimension by delta, clamped to [0, 1].

        Used by _apply_policy_shift() in Simulation. If the name is not in
        dimension_names (e.g., domain-agnostic schema without "enforcement"),
        raises KeyError — callers should catch this and skip silently.

        Parameters
        ----------
        name : str
            Dimension name. Must be in self.dimension_names.
        delta : float
            Signed shift amount. Clamped to keep result in [0, 1].
        """
        if name not in self.dimension_names:
            raise KeyError(
                f"Dimension '{name}' not in schema. "
                f"Available: {self.dimension_names}"
            )
        idx = self.dimension_names.index(name)
        self.vector[idx] = float(np.clip(self.vector[idx] + delta, 0.0, 1.0))
        # Keep legacy field in sync
        if name in ("deployment_cap", "transparency", "enforcement", "audit_intensity"):
            object.__setattr__(self, name, float(self.vector[idx]))

    def to_dict(self) -> dict:
        return {
            "dimension_names"    : self.dimension_names,
            "vector"             : self.vector.tolist(),
            "confidence"         : self.confidence.tolist(),
            "dimension_salience" : self.dimension_salience.tolist(),
            "violator_dim_index" : self.violator_dim_index,
            "violator_threshold" : self.violator_threshold,
            "lag"                : self.lag,
            "narrative"          : self.narrative,
        }


# ---------------------------------------------------------------------------
# Shock configuration
# ---------------------------------------------------------------------------

@dataclass
class ShockConfig:
    """Parameters governing the exogenous shock process."""
    shock_prob   : float     = 0.2
    min_strength : float     = 0.1
    max_strength : float     = 0.4
    mode         : ShockMode = ShockMode.COORDINATING
    n_targets    : int       = 10
