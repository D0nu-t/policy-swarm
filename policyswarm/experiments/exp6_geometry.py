"""
policyswarm.experiments.exp6_geometry
======================================
Experiment 6: Geometry of Opinion Space (Iteration 12)

Design
------
Compare three opinion-space metrics across an alpha (convergence rate) sweep:
  geometry ∈ {euclidean, cosine, manifold}
  alpha    ∈ {0.00, 0.05, 0.10, 0.15}  (overrides SimConfig.mu)

Bounded-confidence threshold
----------------------------
By default each geometry gets a coverage-matched epsilon (Euclidean keeps
SimConfig.epsilon; cosine and manifold admit the same fraction of neighbour
pairs at initialisation). ``epsilon_mode="raw"`` uses one raw epsilon for all
geometries, which confounds geometry with threshold coverage.

Sanity check at alpha = 0
-------------------------
With mu = 0 peer influence is switched off, and since the policy anchor is no
longer applied inside the gated peer loop, geometry has no channel left to
act through: all geometries must produce identical trajectories at alpha = 0.
Any difference there indicates a leak of geometry into non-peer dynamics.

Note on COSINE vs MANIFOLD: under coverage matching their gates admit the
same pairs (1 - cos θ is monotone in θ), so they differ only in the update
rule (chordal vs geodesic step).

Modelling note
--------------
Papers using euclidean dynamics — the vast majority of computational ABM
work — should either justify this choice explicitly or demonstrate
robustness to alternatives, with thresholds matched for coverage.
"""

from __future__ import annotations

import dataclasses
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
    epsilon_mode : {"matched", "raw"}
        How each geometry's bounded-confidence threshold is set.
    """

    def __init__(
        self,
        output_dir  : str,
        seeds       : Optional[List[int]]      = None,
        policy_text : str                      = _DEFAULT_TEXT,
        geometries  : Optional[List[Geometry]] = None,
        alphas      : Optional[List[float]]    = None,
        sim_config  : Optional[SimConfig]      = None,
        epsilon_mode: str                      = "matched",
    ):
        super().__init__(output_dir, seeds)
        self.policy_text  = policy_text
        self.geometries   = geometries or list(Geometry)
        self.alphas       = alphas if alphas is not None else [0.0, 0.05, 0.10, 0.15]
        self.sim_config   = sim_config or SimConfig()
        self.epsilon_mode = epsilon_mode

    def total_units(self) -> int:
        return len(self.geometries) * len(self.alphas) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        base_policy  = policy_from_text(self.policy_text)
        shock_config = ShockConfig(mode=ShockMode.COORDINATING)
        gov_config   = GovernanceConfig(
            deployment_rate_cap = 0.5,
            penalty_severity    = 0.3,
        )
        rows  = []
        total = self.total_units()
        epsilons = self._geometry_epsilons(
            self.sim_config, self.geometries, self.epsilon_mode
        )

        for geometry in self.geometries:
            for alpha in self.alphas:
                # Override mu and epsilon, keeping every other field
                sc = dataclasses.replace(
                    self.sim_config,
                    mu      = float(alpha),
                    epsilon = epsilons[geometry.value],
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
                        "epsilon"         : sc.epsilon,
                        "seed"            : seed,
                        "variance"        : m["variance"],
                        "polarization"    : m["polarization"],
                        "bifurcation_index": m["bifurcation_index"],
                        "phase_t"         : m["phase_transition_tick"],
                        "cascade_breadth" : m["cascade_breadth"],
                        "gate_pass_rate"  : m["gate_pass_rate"],
                    })

                    self._emit(
                        type="seed_complete", experiment=self.__class__.__name__,
                        completed=len(rows), total=total,
                        condition={"geometry": geometry.value, "alpha": alpha},
                        seed=seed,
                    )

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        # Right-censor never-stabilised runs at the horizon so means stay finite
        df = df.copy()
        df["phase_t"] = df["phase_t"].replace(
            float("inf"), float(self.sim_config.n_ticks)
        )
        summary = group_summary(
            df, ["geometry", "alpha"],
            ["variance", "polarization", "bifurcation_index", "phase_t",
             "gate_pass_rate"]
        )
        print("\n=== Exp 6: Geometry of Opinion Space ===")
        print(summary.to_string(index=False))
        return summary

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        from ..visualization import plot_geometry_ptt
        paths = [
            plot_geometry_comparison(df, self.output_dir),
            plot_geometry_ptt(df, self.output_dir,
                              n_ticks=self.sim_config.n_ticks),
        ]
        return [p for p in paths if p]
