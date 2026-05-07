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

from ..config import SimConfig, GovernanceConfig, ShockConfig, ShockMode
from ..extraction import policy_from_text
from ..shocks import generate_shocks
from ..dynamics import Simulation
from ..metrics import compute_all_metrics
from ..analysis import stat_test_table, group_summary, executive_summary
from ..visualization import plot_cb_vs_lag, plot_variance_shift
from .base import BaseExperiment

_DEFAULT_TEXT = """
The government introduces strict AI safety regulations requiring transparency
audits, limiting deployment of high-risk systems, and enforcing penalties for
non-compliance. The policy prioritises public safety over innovation risks.
"""


class MediaInteractionExperiment(BaseExperiment):
    """Experiment 3: Media × Enforcement Lag Interaction.

    Parameters
    ----------
    lags : list of int
        Enforcement lag grid. Default [0, 20, 40].
    media_conditions : list of bool
        Media conditions to compare. Default [True, False].
    """

    def __init__(
        self,
        output_dir       : str,
        seeds            : Optional[List[int]] = None,
        policy_text      : str                 = _DEFAULT_TEXT,
        lags             : Optional[List[int]] = None,
        media_conditions : Optional[List[bool]] = None,
        sim_config       : Optional[SimConfig]   = None,
        shock_config     : Optional[ShockConfig] = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text      = policy_text
        self.lags             = lags or [0, 20, 40]
        self.media_conditions = media_conditions if media_conditions is not None else [True, False]
        self.sim_config       = sim_config or SimConfig()
        self.shock_config     = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    def run(self) -> pd.DataFrame:
        base_policy = policy_from_text(self.policy_text)
        rows = []

        for lag in self.lags:
            base_policy.lag = lag

            for enable_media in self.media_conditions:
                gov_config = GovernanceConfig(
                    deployment_rate_cap = 0.5,
                    penalty_severity    = 0.5,
                    enforcement_lag     = lag,
                    enable_media        = enable_media,
                )

                for seed in self.seeds:
                    shocks = generate_shocks(
                        self.shock_config, self.sim_config.n_ticks, seed
                    )

                    sim_c = Simulation(
                        self.sim_config, gov_config, base_policy, shocks,
                        apply_shocks=False, seed=seed,
                    )
                    sim_c.run()

                    sim_t = Simulation(
                        self.sim_config, gov_config, base_policy, shocks,
                        apply_shocks=True, seed=seed,
                    )
                    sim_t.run()

                    m_c = compute_all_metrics(sim_c)
                    m_t = compute_all_metrics(sim_t)

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
