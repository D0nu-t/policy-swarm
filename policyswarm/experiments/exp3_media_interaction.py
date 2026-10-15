"""
policyswarm.experiments.exp3_media_interaction
===============================================
Experiment 3: Media × Enforcement Lag Interaction

Design
------
Grid: lag ∈ {0, 20, 40} × enable_media ∈ {True, False} × seed ∈ seeds
Paired within-seed comparison (control = no shocks, treatment = shocks applied).
Ideology-aligned competing media is toggled via GovernanceConfig.enable_media.

Key finding (design document)
------------------------------
  Lag  0:  effect_size = +0.009 (p < 0.001)
  Lag 20:  effect_size = +0.010 (p < 0.001)
  Lag 40:  effect_size = +0.013 (p < 0.001)

Competing media consistently amplifies post-enforcement residual disagreement,
with the effect modestly increasing at higher enforcement lags. Media does not
prevent enforcement from operating but creates persistent polarized clusters
that enforcement cannot dissolve.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from ..analysis import executive_summary, group_summary, stat_test_table
from ..config import GovernanceConfig, Policy, ShockConfig, ShockMode, SimConfig
from ..extraction import DEFAULT_POLICY_TEXT
from ..shocks import generate_shocks
from ..visualization import plot_cb_vs_lag, plot_variance_shift
from .base import BASELINE_GOVERNANCE, BaseExperiment, run_paired
from .params import ParamSpec


class MediaInteractionExperiment(BaseExperiment):
    """Experiment 3: Media × Enforcement Lag Interaction.

    Parameters
    ----------
    lags : list of int
        Enforcement lag grid. Default [0, 20, 40].
    media_conditions : list of bool
        Media conditions to compare. Default [True, False].
    shock_config : ShockConfig, optional
        Default: COORDINATING shocks.
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "media"
    title = "Exp 3: Media × enforcement lag interaction"
    PARAMS = (
        ParamSpec("lags", "int", [0, 20, 40], many=True, minimum=0,
                  help="Enforcement lag values (ticks) to sweep."),
        ParamSpec("media_conditions", "bool", [True, False], many=True,
                  help="Run with ideology-aligned media on, off, or both."),
    )

    def __init__(
        self,
        output_dir       : str,
        seeds            : Optional[List[int]]   = None,
        policy_text      : str                   = DEFAULT_POLICY_TEXT,
        lags             : Optional[List[int]]   = None,
        media_conditions : Optional[List[bool]]  = None,
        sim_config       : Optional[SimConfig]   = None,
        shock_config     : Optional[ShockConfig] = None,
        policy           : Optional[Policy]      = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.lags             = lags or [0, 20, 40]
        self.media_conditions = media_conditions if media_conditions is not None else [True, False]
        self.shock_config     = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    def total_units(self) -> int:
        return len(self.lags) * len(self.media_conditions) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        policy = self._policy()
        rows   = []
        total  = self.total_units()

        for lag in self.lags:
            policy.lag = lag

            for enable_media in self.media_conditions:
                gov_config = GovernanceConfig(
                    **BASELINE_GOVERNANCE,
                    enforcement_lag = lag,
                    enable_media    = enable_media,
                )

                for seed in self.seeds:
                    shocks = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed)
                    m_c, m_t = run_paired(self.sim_config, gov_config, policy, shocks, seed)

                    rows.append({
                        "lag"            : lag,
                        "enable_media"   : enable_media,
                        "seed"           : seed,
                        "control_var"    : m_c["variance"],
                        "treat_var"      : m_t["variance"],
                        "delta"          : m_t["variance"] - m_c["variance"],
                        "variance"       : m_t["variance"],
                        "polarization"   : m_t["polarization"],
                        "cascade_breadth": m_t["cascade_breadth"],
                        "delta_variance" : m_t["delta_variance"],
                        "num_shocks"     : len(shocks),
                    })

                    self._emit(
                        type="seed_complete", experiment=self.__class__.__name__,
                        completed=len(rows), total=total,
                        condition={"lag": lag, "enable_media": enable_media},
                        seed=seed,
                    )

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = stat_test_table(
            df,
            groupby_cols  = ["lag", "enable_media"],
            control_col   = "control_var",
            treatment_col = "treat_var",
            label         = "effect",
        )
        print(executive_summary(stats, experiment="Exp 3: Media × Lag Interaction"))

        # Also report grouped means for quick interpretation
        summary = group_summary(df, ["lag", "enable_media"],
                                ["variance", "polarization", "cascade_breadth"])
        print("\nGrouped means:")
        print(summary.to_string(index=False))
        return stats

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [
            plot_cb_vs_lag(df, self.output_dir),
            plot_variance_shift(df, self.output_dir),
        ]
        return [p for p in paths if p]
