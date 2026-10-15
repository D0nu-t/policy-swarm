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

from ..analysis import executive_summary, stat_test_table
from ..config import GovernanceConfig, OverlapRegime, Policy, ShockConfig, ShockMode, SimConfig
from ..dynamics import Simulation
from ..extraction import DEFAULT_POLICY_TEXT
from ..shocks import generate_shocks
from ..visualization import plot_oversight_phase, plot_variance_timeline
from .base import BaseExperiment, run_paired
from .params import ParamSpec


class OversightPhaseExperiment(BaseExperiment):
    """Experiment 1: Oversight Regime Phase Transitions.

    Parameters
    ----------
    regimes : list of OverlapRegime, optional
        Regimes to sweep. Default: all four.
    shock_config : ShockConfig, optional
        Default: COORDINATING shocks.
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "oversight"
    title = "Exp 1: Oversight regime phase transitions"
    PARAMS = (
        ParamSpec("regimes", "choice", [r.value for r in OverlapRegime], many=True,
                  enum=OverlapRegime, help="Oversight regimes to sweep."),
    )

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]           = None,
        policy_text  : str                           = DEFAULT_POLICY_TEXT,
        regimes      : Optional[List[OverlapRegime]] = None,
        sim_config   : Optional[SimConfig]           = None,
        shock_config : Optional[ShockConfig]         = None,
        policy       : Optional[Policy]              = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.regimes      = regimes or list(OverlapRegime)
        self.shock_config = shock_config or ShockConfig(mode=ShockMode.COORDINATING)

    def total_units(self) -> int:
        return len(self.regimes) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        policy = self._policy()
        rows   = []
        total  = self.total_units()

        for regime in self.regimes:
            gov_config = GovernanceConfig(oversight_regime=regime)

            for seed in self.seeds:
                shocks = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed)
                m_c, m_t = run_paired(self.sim_config, gov_config, policy, shocks, seed)

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

                self._emit(
                    type="seed_complete", experiment=self.__class__.__name__,
                    completed=len(rows), total=total,
                    condition={"regime": regime.value}, seed=seed,
                )

        return pd.DataFrame(rows)

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

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [plot_oversight_phase(df, self.output_dir)]

        # One variance timeline per regime (treatment condition, seed 0)
        policy = self._policy()
        for regime in self.regimes:
            gov = GovernanceConfig(oversight_regime=regime)
            shocks = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed=0)
            sim = Simulation(
                self.sim_config, gov, policy, shocks,
                apply_shocks=True, seed=0,
            )
            sim.run()
            paths.append(plot_variance_timeline(
                sim.history, shocks, self.output_dir,
                filename=f"variance_timeline_regime_{regime.value}.png",
                label=regime.value,
            ))

        return [p for p in paths if p]
