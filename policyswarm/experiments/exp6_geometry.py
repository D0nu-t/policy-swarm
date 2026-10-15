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

from ..analysis import group_summary
from ..config import Geometry, GovernanceConfig, Policy, ShockConfig, ShockMode, SimConfig
from ..dynamics import Simulation
from ..extraction import DEFAULT_POLICY_TEXT
from ..metrics import compute_all_metrics
from ..shocks import generate_shocks
from ..visualization import plot_geometry_comparison, plot_geometry_ptt
from .base import BaseExperiment
from .params import ParamSpec

# Pinned by name so a geometry added to the registry later does not change this experiment.
_DEFAULT_GEOMETRIES = ["euclidean", "cosine", "manifold"]
_DEFAULT_ALPHAS = [0.0, 0.05, 0.10, 0.15]
EPSILON_MODES = ("matched", "raw")


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
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "geometry"
    title = "Exp 6: Opinion-space geometry × convergence rate"
    PARAMS = (
        ParamSpec("geometries", "choice", _DEFAULT_GEOMETRIES, many=True, enum=Geometry,
                  help="Opinion-space geometries to compare."),
        ParamSpec("alphas", "float", _DEFAULT_ALPHAS, many=True, minimum=0.0, maximum=1.0,
                  help="Convergence rates (mu) to sweep."),
        ParamSpec("epsilon_mode", "choice", "matched", choices=EPSILON_MODES,
                  help="matched: coverage-matched threshold per geometry; raw: one shared value."),
    )

    # Note: this experiment has always used penalty_severity = 0.3, not the
    # 0.5 baseline of the other experiments. Kept as is: changing it would
    # alter the published Experiment 6 numbers.
    gov_config   = GovernanceConfig(deployment_rate_cap=0.5, penalty_severity=0.3)
    shock_config = ShockConfig(mode=ShockMode.COORDINATING)

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]      = None,
        policy_text  : str                      = DEFAULT_POLICY_TEXT,
        geometries   : Optional[List[Geometry]] = None,
        alphas       : Optional[List[float]]    = None,
        sim_config   : Optional[SimConfig]      = None,
        epsilon_mode : str                      = "matched",
        policy       : Optional[Policy]         = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.geometries   = geometries or [Geometry(g) for g in _DEFAULT_GEOMETRIES]
        self.alphas       = alphas if alphas is not None else list(_DEFAULT_ALPHAS)
        self.epsilon_mode = epsilon_mode

    def total_units(self) -> int:
        return len(self.geometries) * len(self.alphas) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        policy = self._policy()
        rows   = []
        total  = self.total_units()
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
                    shocks = generate_shocks(self.shock_config, sc.n_ticks, seed)
                    sim = Simulation(
                        sc, self.gov_config, policy, shocks,
                        apply_shocks=True, seed=seed, geometry=geometry,
                    )
                    sim.run()
                    m = compute_all_metrics(sim)

                    rows.append({
                        "geometry"         : geometry.value,
                        "alpha"            : alpha,
                        "epsilon"          : sc.epsilon,
                        "seed"             : seed,
                        "variance"         : m["variance"],
                        "polarization"     : m["polarization"],
                        "bifurcation_index": m["bifurcation_index"],
                        "phase_t"          : m["phase_transition_tick"],
                        "cascade_breadth"  : m["cascade_breadth"],
                        "gate_pass_rate"   : m["gate_pass_rate"],
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
        paths = [
            plot_geometry_comparison(df, self.output_dir),
            plot_geometry_ptt(df, self.output_dir, n_ticks=self.sim_config.n_ticks),
        ]
        return [p for p in paths if p]
