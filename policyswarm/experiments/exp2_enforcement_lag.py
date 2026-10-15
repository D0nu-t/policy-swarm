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

Lag varies only the onset of the violator penalty: the perceived-policy pull
onset (GovernanceConfig.policy_pull_onset) and the policy tightening tick
(SimConfig.policy_split_tick = 30) are fixed across all lag conditions.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from ..analysis import executive_summary, stat_test_table
from ..config import GovernanceConfig, Policy, ShockConfig, ShockMode, SimConfig
from ..extraction import DEFAULT_POLICY_TEXT
from ..shocks import generate_shocks
from ..visualization import plot_phase_diagram
from .base import BASELINE_GOVERNANCE, BaseExperiment, run_paired
from .params import ParamSpec


class EnforcementLagExperiment(BaseExperiment):
    """Experiment 2: Enforcement Lag Sensitivity.

    Parameters
    ----------
    lags : list of int
        Enforcement lag values to sweep. Default [0, 5, 10, 20, 40].
    shock_config : ShockConfig, optional
        Default: COORDINATING shocks.
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "lag"
    title = "Exp 2: Enforcement lag sensitivity"
    PARAMS = (
        ParamSpec("lags", "int", [0, 5, 10, 20, 40], many=True, minimum=0,
                  help="Enforcement lag values (ticks) to sweep."),
    )

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]   = None,
        policy_text  : str                   = DEFAULT_POLICY_TEXT,
        lags         : Optional[List[int]]   = None,
        sim_config   : Optional[SimConfig]   = None,
        shock_config : Optional[ShockConfig] = None,
        policy       : Optional[Policy]      = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.lags         = lags or [0, 5, 10, 20, 40]
        self.shock_config = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    def total_units(self) -> int:
        return len(self.lags) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        rows  = []
        total = self.total_units()

        for lag in self.lags:
            # A fresh policy per lag: the lag assignment cannot bleed into the
            # next iteration.
            policy = self._policy()
            policy.lag = lag

            gov_config = GovernanceConfig(**BASELINE_GOVERNANCE, enforcement_lag=lag)

            for seed in self.seeds:
                shocks = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed)
                m_c, m_t = run_paired(self.sim_config, gov_config, policy, shocks, seed)

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
                    "phase_t"          : m_t["phase_transition_tick"],
                    "delta_variance"   : m_t["delta_variance"],
                    "num_shocks"       : len(shocks),
                })

                self._emit(
                    type="seed_complete", experiment=self.__class__.__name__,
                    completed=len(rows), total=total,
                    condition={"lag": lag}, seed=seed,
                )

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
