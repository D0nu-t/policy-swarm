"""
policyswarm.experiments.exp1_oversight
=======================================
Experiment 1: Oversight Regime Phase Transitions

Design
------
Vary the oversight regime across the ordinal scale:
  NONE → VOLUNTARY → MANDATORY → PROHIBITIVE

For each regime and seed, run paired control/treatment simulations (the
treatment applies shocks; the control does not). Measure cascade breadth (CB),
opinion variance, bifurcation index (BI), and phase transition tick (PTT).

Key finding (from the design document)
---------------------------------------
A phase transition in cascade breadth occurs at the VOLUNTARY/MANDATORY
boundary. Under mandatory regimes, penalty costs suppress hub posting
frequency, flattening the effective degree distribution and reducing CB by
a mean of 34%. The effect is topological, not belief-level.

Output files
------------
<output_dir>/exp1_oversight_results_<ts>.csv
<output_dir>/exp1_oversight_stats_<ts>.csv
<output_dir>/oversight_phase.png
<output_dir>/variance_timeline_regime_<regime>.png  (one per regime)
"""

from __future__ import annotations

from typing import List, Optional
import pandas as pd
import numpy as np

from ..config import (
    SimConfig, GovernanceConfig, Policy,
    OverlapRegime, ShockConfig, ShockMode,
)
from ..extraction import policy_from_text
from ..shocks import generate_shocks
from ..dynamics import Simulation
from ..metrics import (
    opinion_variance, cascade_breadth, bifurcation_index,
    phase_transition_tick, compute_all_metrics,
)
from ..analysis import group_summary, stat_test_table, executive_summary
from ..visualization import (
    plot_oversight_phase, plot_variance_timeline,
)
from .base import BaseExperiment

_DEFAULT_POLICY_TEXT = """
The government introduces strict AI safety regulations requiring transparency audits,
limiting deployment of high-risk systems, and enforcing penalties for non-compliance.
The policy prioritises public safety over innovation risks.
"""


class OversightPhaseExperiment(BaseExperiment):
    """Experiment 1: Oversight Regime Phase Transitions.

    Parameters
    ----------
    policy_text : str
        Raw policy text to ingest. Defaults to the canonical design-doc text.
    regimes : list of OverlapRegime, optional
        Regimes to sweep. Default: all four.
    sim_config : SimConfig, optional
    shock_config : ShockConfig, optional
    output_dir : str
    seeds : list of int
    """

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]] = None,
        policy_text  : str                 = _DEFAULT_POLICY_TEXT,
        regimes      : Optional[List[OverlapRegime]] = None,
        sim_config   : Optional[SimConfig]   = None,
        shock_config : Optional[ShockConfig] = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text  = policy_text
        self.regimes      = regimes or list(OverlapRegime)
        self.sim_config   = sim_config or SimConfig()
        self.shock_config = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        policy = policy_from_text(self.policy_text)
        rows   = []

        for regime in self.regimes:
            gov_config = GovernanceConfig(oversight_regime=regime)

            for seed in self.seeds:
                shocks = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed)

                # Control: no shocks
                sim_c = Simulation(
                    self.sim_config, gov_config, policy, shocks,
                    apply_shocks=False, seed=seed,
                )
                sim_c.run()

                # Treatment: shocks applied
                sim_t = Simulation(
                    self.sim_config, gov_config, policy, shocks,
                    apply_shocks=True, seed=seed,
                )
                sim_t.run()

                m_c = compute_all_metrics(sim_c)
                m_t = compute_all_metrics(sim_t)

                rows.append({
                    "regime"             : regime.value,
                    "seed"               : seed,
                    "deployment_rate_cap": gov_config.deployment_rate_cap,
                    "penalty_severity"   : gov_config.penalty_severity,
                    # Treatment metrics
                    "variance"           : m_t["variance"],
                    "cascade_breadth"    : m_t["cascade_breadth"],
                    "bifurcation_index"  : m_t["bifurcation_index"],
                    "phase_t"            : m_t["phase_transition_tick"],
                    "delta_variance"     : m_t["delta_variance"],
                    # Paired control
                    "control_variance"   : m_c["variance"],
                    "control_cb"         : m_c["cascade_breadth"],
                    "delta"              : m_t["variance"] - m_c["variance"],
                    "num_shocks"         : len(shocks),
                })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = stat_test_table(
            df,
            groupby_cols  = ["regime"],
            control_col   = "control_variance",
            treatment_col = "variance",
            label         = "effect",
        )
        print(executive_summary(stats, experiment="Exp 1: Oversight Phase Transitions"))
        return stats

    # ------------------------------------------------------------------

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = []
        paths.append(plot_oversight_phase(df, self.output_dir))

        # One variance timeline per regime (treatment condition, seed 0)
        from ..shocks import generate_shocks as _gen
        policy = policy_from_text(self.policy_text)
        for regime in self.regimes:
            gov = GovernanceConfig(oversight_regime=regime)
            shocks = _gen(self.shock_config, self.sim_config.n_ticks, seed=0)
            sim = Simulation(
                self.sim_config, gov, policy, shocks,
                apply_shocks=True, seed=0,
            )
            sim.run()
            p = plot_variance_timeline(
                sim.history, shocks, self.output_dir,
                filename=f"variance_timeline_regime_{regime.value}.png",
                label=regime.value,
            )
            paths.append(p)

        return [p for p in paths if p]
