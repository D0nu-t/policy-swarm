"""
policyswarm.experiments.exp6_geometry
======================================
Experiment 6: Geometry of Opinion Space (Iteration 12)

Design
------
Compare three opinion-space metrics across an alpha (convergence rate) sweep:
  geometry ∈ {euclidean, cosine, manifold}
  alpha    ∈ {0.00, 0.05, 0.10, 0.15}  (overrides SimConfig.mu)

Key findings (design document, representative run, 5 seeds)
------------------------------------------------------------
  geometry  alpha  variance  polarization  phase_t
  euclidean  0.00    0.050      0.531         53
  euclidean  0.05    0.047      0.498         61
  cosine     0.00    0.045      0.150         38
  cosine     0.05    0.043      0.144         41
  manifold   0.00    0.048      0.312         47

Interpretation: Euclidean dynamics produce the highest polarization; cosine
the lowest. Variance is broadly similar across geometries. The geometry choice
is a modelling decision with non-trivial empirical consequences.

Modelling note
--------------
The manifold approach (geodesic distances on S^(d-1)) is theoretically the
most defensible for bounded opinion spaces but falls between euclidean and
cosine polarization. Papers using euclidean dynamics — the vast majority of
computational ABM work — should either justify this choice explicitly or
demonstrate robustness to alternatives.
"""

from __future__ import annotations

from typing import List, Optional
import pandas as pd
import numpy as np

from ..config import (
    SimConfig, GovernanceConfig, ShockConfig, ShockMode, Geometry
)
from ..extraction import policy_from_text
from ..shocks import generate_shocks
from ..dynamics import Simulation
from ..metrics import compute_all_metrics
from ..analysis import group_summary, executive_summary
from ..visualization import plot_geometry_comparison
from .base import BaseExperiment

_DEFAULT_TEXT = """
The government introduces strict AI safety regulations requiring transparency
audits, limiting deployment of high-risk systems, and enforcing penalties for
non-compliance. The policy prioritises public safety over innovation risks.
"""


class GeometryExperiment(BaseExperiment):
    """Experiment 6: Geometry of Opinion Space.

    Parameters
    ----------
    geometries : list of Geometry
        Default all three: EUCLIDEAN, COSINE, MANIFOLD.
    alphas : list of float
        Convergence rate (mu) values to sweep. Default [0.0, 0.05, 0.10, 0.15].
    """

    def __init__(
        self,
        output_dir  : str,
        seeds       : Optional[List[int]]      = None,
        policy_text : str                      = _DEFAULT_TEXT,
        geometries  : Optional[List[Geometry]] = None,
        alphas      : Optional[List[float]]    = None,
        sim_config  : Optional[SimConfig]      = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text = policy_text
        self.geometries  = geometries or list(Geometry)
        self.alphas      = alphas or [0.0, 0.05, 0.10, 0.15]
        self.sim_config  = sim_config or SimConfig()

    def run(self) -> pd.DataFrame:
        base_policy  = policy_from_text(self.policy_text)
        shock_config = ShockConfig(mode=ShockMode.COORDINATING)
        gov_config   = GovernanceConfig(
            deployment_rate_cap = 0.5,
            penalty_severity    = 0.3,
        )
        rows = []

        for geometry in self.geometries:
            for alpha in self.alphas:
                # Override mu in a copy of SimConfig
                sc = SimConfig(
                    n_agents      = self.sim_config.n_agents,
                    n_ticks       = self.sim_config.n_ticks,
                    interactions  = self.sim_config.interactions,
                    shock_prob    = self.sim_config.shock_prob,
                    mu            = float(alpha),
                    epsilon       = self.sim_config.epsilon,
                    network_type  = self.sim_config.network_type,
                    ba_m          = self.sim_config.ba_m,
                    opinion_dim   = self.sim_config.opinion_dim,
                )

                for seed in self.seeds:
                    shocks = generate_shocks(
                        shock_config, sc.n_ticks, seed
                    )
                    sim = Simulation(
                        sc, gov_config, base_policy, shocks,
                        apply_shocks=True, seed=seed, geometry=geometry,
                    )
                    sim.run()
                    m = compute_all_metrics(sim)

                    rows.append({
                        "geometry"        : geometry.value,
                        "alpha"           : alpha,
                        "seed"            : seed,
                        "variance"        : m["variance"],
                        "polarization"    : m["polarization"],
                        "bifurcation_index": m["bifurcation_index"],
                        "phase_t"         : m["phase_transition_tick"],
                        "cascade_breadth" : m["cascade_breadth"],
                    })

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        summary = group_summary(
            df, ["geometry", "alpha"],
            ["variance", "polarization", "bifurcation_index", "phase_t"]
        )
        print("\n=== Exp 6: Geometry of Opinion Space ===")
        print(summary.to_string(index=False))
        return summary

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        return [plot_geometry_comparison(df, self.output_dir)]
