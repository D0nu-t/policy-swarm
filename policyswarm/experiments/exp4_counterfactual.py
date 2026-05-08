"""
policyswarm.experiments.exp4_counterfactual
============================================
Experiment 4: Counterfactual Shock Analysis

Design
------
Paired counterfactual design (Iteration 10):
  - Generate one shock schedule per seed (shared between control and treatment)
  - Control:   apply_shocks=False
  - Treatment: apply_shocks=True
  - Shock mode configurable (default: COORDINATING = mean-reverting)

Grid: lag ∈ {0, 20, 40} × geometry ∈ {euclidean, cosine} × seed ∈ seeds

Key finding (design document)
------------------------------
  Lag  0:  ΔVariance = -0.0135 (p = 0.0018)
  Lag 20:  ΔVariance = -0.0128 (p = 0.0029)
  Lag 40:  ΔVariance = -0.0115 (p = 0.0051)

Coordinating (mean-reverting) shocks reduce variance with high statistical
significance across all lag conditions. The weakening effect at higher lag
is a real and interpretable signal: governance delays reduce the stabilizing
impact of coordinating shocks.

Note on shock polarity (design document)
-----------------------------------------
The COORDINATING shock models crisis-induced consensus, not polarizing events.
Use ShockMode.POLARIZING to study the destabilising regime. Both are
empirically real phenomena requiring different implementations.
"""

from __future__ import annotations

import copy
from typing import List, Optional
import pandas as pd

from ..config import (
    SimConfig, GovernanceConfig, ShockConfig, ShockMode, Geometry
)
from ..extraction import policy_from_text
from ..shocks import generate_shocks
from ..dynamics import Simulation
from ..metrics import compute_all_metrics
from ..analysis import stat_test_table, executive_summary
from ..visualization import (
    plot_phase_diagram, plot_variance_comparison,
)
from .base import BaseExperiment

_DEFAULT_TEXT = """
The government introduces strict AI safety regulations requiring transparency
audits, limiting deployment of high-risk systems, and enforcing penalties for
non-compliance. The policy prioritises public safety over innovation risks.
"""


class CounterfactualShockExperiment(BaseExperiment):
    """Experiment 4: Counterfactual Shock Analysis.

    Parameters
    ----------
    lags : list of int
    geometries : list of Geometry
    shock_mode : ShockMode
        Directional character of shocks. Default COORDINATING.
    """

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]   = None,
        policy_text  : str                   = _DEFAULT_TEXT,
        lags         : Optional[List[int]]   = None,
        geometries   : Optional[List[Geometry]] = None,
        shock_mode   : ShockMode             = ShockMode.COORDINATING,
        sim_config   : Optional[SimConfig]   = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text = policy_text
        self.lags        = lags or [0, 20, 40]
        self.geometries  = geometries or [Geometry.EUCLIDEAN, Geometry.COSINE]
        self.shock_mode  = shock_mode
        self.sim_config  = sim_config or SimConfig()

    def run(self) -> pd.DataFrame:
        base_policy = policy_from_text(self.policy_text)
        rows = []

        for geometry in self.geometries:
            for lag in self.lags:
                policy = copy.copy(base_policy)
                policy.lag = lag
                shock_config = ShockConfig(mode=self.shock_mode)

                gov_config = GovernanceConfig(
                    deployment_rate_cap = 0.5,
                    penalty_severity    = 0.5,
                    enforcement_lag     = lag,
                )

                for seed in self.seeds:
                    shocks = generate_shocks(
                        shock_config, self.sim_config.n_ticks, seed
                    )

                    sim_c = Simulation(
                        self.sim_config, gov_config, base_policy, shocks,
                        apply_shocks=False, seed=seed, geometry=geometry,
                    )
                    sim_c.run()

                    sim_t = Simulation(
                        self.sim_config, gov_config, base_policy, shocks,
                        apply_shocks=True, seed=seed, geometry=geometry,
                    )
                    sim_t.run()

                    m_c = compute_all_metrics(sim_c)
                    m_t = compute_all_metrics(sim_t)

                    rows.append({
                        "geometry"       : geometry.value,
                        "lag"            : lag,
                        "seed"           : seed,
                        "control_var"    : m_c["variance"],
                        "treat_var"      : m_t["variance"],
                        "delta"          : m_t["variance"] - m_c["variance"],
                        "polarization"   : m_t["polarization"],
                        "cascade_breadth": m_t["cascade_breadth"],
                        "phase_t"        : m_t["phase_transition_tick"],
                        "delta_variance" : m_t["delta_variance"],
                        "num_shocks"     : len(shocks),
                        "shock_mode"     : self.shock_mode.value,
                    })

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = stat_test_table(
            df,
            groupby_cols  = ["geometry", "lag"],
            control_col   = "control_var",
            treatment_col = "treat_var",
            label         = "effect",
        )
        print(executive_summary(
            stats, experiment="Exp 4: Counterfactual Shock Analysis"
        ))
        return stats

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [plot_phase_diagram(df, self.output_dir)]

        # Generate one control vs treatment comparison plot for seed 0, lag 0, euclidean
        plot_policy = copy.copy(policy_from_text(self.policy_text))
        plot_policy.lag = 0
        sc = ShockConfig(mode=self.shock_mode)
        gov = GovernanceConfig(deployment_rate_cap=0.5, penalty_severity=0.5)
        shocks = generate_shocks(sc, self.sim_config.n_ticks, seed=0)

        sim_c = Simulation(self.sim_config, gov, plot_policy, shocks,
                           apply_shocks=False, seed=0)
        sim_c.run()
        sim_t = Simulation(self.sim_config, gov, plot_policy, shocks,
                           apply_shocks=True, seed=0)
        sim_t.run()

        p = plot_variance_comparison(
            sim_c.history, sim_t.history, shocks,
            self.output_dir, "variance_comparison_exp4.png",
        )
        paths.append(p)
        return [p for p in paths if p]