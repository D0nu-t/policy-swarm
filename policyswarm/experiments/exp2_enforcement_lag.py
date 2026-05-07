"""
policyswarm.experiments.exp2_enforcement_lag
============================================
Experiment 2: Enforcement Lag Sensitivity

Key finding (design document, strongest result)
-------------------------------------------------
Enforcement lag has a LARGER effect on final opinion distributions than
penalty severity, despite being a process parameter rather than a content
parameter. Runs with lag ≥ 20 showed significantly higher bifurcation index
than runs with lag ≤ 5, even when penalty severity was maximal.

Design
------
Grid: lag ∈ {0, 5, 10, 20, 40} × seed ∈ seeds
Paired control (no shocks) / treatment (shocks applied)
Fixed GovernanceConfig otherwise (MANDATORY regime)
"""

from __future__ import annotations

from typing import List, Optional
import pandas as pd
import numpy as np

from ..config import SimConfig, GovernanceConfig, ShockConfig, ShockMode
from ..extraction import policy_from_text
from ..shocks import generate_shocks
from ..dynamics import Simulation
from ..metrics import compute_all_metrics, bifurcation_index
from ..analysis import stat_test_table, executive_summary
from ..visualization import plot_phase_diagram, plot_variance_timeline
from .base import BaseExperiment

_DEFAULT_TEXT = """
The government introduces strict AI safety regulations requiring transparency
audits, limiting deployment of high-risk systems, and enforcing penalties for
non-compliance. The policy prioritises public safety over innovation risks.
"""


class EnforcementLagExperiment(BaseExperiment):
    """Experiment 2: Enforcement Lag Sensitivity.

    Parameters
    ----------
    lags : list of int
        Enforcement lag values to sweep. Default [0, 5, 10, 20, 40].
    """

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]] = None,
        policy_text  : str                 = _DEFAULT_TEXT,
        lags         : Optional[List[int]] = None,
        sim_config   : Optional[SimConfig]   = None,
        shock_config : Optional[ShockConfig] = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text  = policy_text
        self.lags         = lags or [0, 5, 10, 20, 40]
        self.sim_config   = sim_config or SimConfig()
        self.shock_config = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    def run(self) -> pd.DataFrame:
        base_policy = policy_from_text(self.policy_text)
        rows = []

        for lag in self.lags:
            policy = base_policy
            policy.lag = lag  # direct assignment (dataclass is mutable)

            gov_config = GovernanceConfig(
                oversight_regime = None,
                deployment_rate_cap = 0.5,
                penalty_severity    = 0.5,
                enforcement_lag     = lag,
            )

            for seed in self.seeds:
                shocks = generate_shocks(
                    self.shock_config, self.sim_config.n_ticks, seed
                )

                sim_c = Simulation(
                    self.sim_config, gov_config, policy, shocks,
                    apply_shocks=False, seed=seed,
                )
                sim_c.run()

                sim_t = Simulation(
                    self.sim_config, gov_config, policy, shocks,
                    apply_shocks=True, seed=seed,
                )
                sim_t.run()

                m_c = compute_all_metrics(sim_c)
                m_t = compute_all_metrics(sim_t)

                rows.append({
                    "lag"              : lag,
                    "seed"             : seed,
                    "geometry"         : "euclidean",
                    "control_var"      : m_c["variance"],
                    "treat_var"        : m_t["variance"],
                    "delta"            : m_t["variance"] - m_c["variance"],
                    "variance"         : m_t["variance"],
                    "polarization"     : m_t["polarization"],
                    "bifurcation_index": m_t["bifurcation_index"],
                    "cascade_breadth"  : m_t["cascade_breadth"],
                    "phase_t"         : m_t["phase_transition_tick"],
                    "delta_variance"   : m_t["delta_variance"],
                    "num_shocks"       : len(shocks),
                })

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = stat_test_table(
            df,
            groupby_cols  = ["lag"],
            control_col   = "control_var",
            treatment_col = "treat_var",
            label         = "effect",
        )
        print(executive_summary(stats, experiment="Exp 2: Enforcement Lag Sensitivity"))
        return stats

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [plot_phase_diagram(df, self.output_dir)]
        return [p for p in paths if p]
