"""
policyswarm.experiments.exp5_centrality
=======================================
Experiment 5: Centrality × Shock Strength Sweep (Iteration 11)

Design
------
Fix the shock tick schedule (per seed), then vary:
  shock_strength ∈ linspace(0.05, 0.60, 8)
  target_type    ∈ {"hub", "random"}

Use DIRECTIONAL shock mode (toward policy vector) for coherent signal
propagation — a separate experimental regime from the noise shocks in Exp 4.

Competing hypotheses
--------------------
H1: hub targeting consistently outperforms random → centrality necessary
H2: curves converge at high strength → critical threshold above which
    topology becomes irrelevant
H3: crossover point → centrality matters in low-energy regime only

The crossover connects to the debate between threshold contagion models
(Watts & Dodds, 2007) and linear influence models.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ..analysis import group_summary
from ..config import GovernanceConfig, Policy, ShockConfig, ShockMode, SimConfig
from ..extraction import DEFAULT_POLICY_TEXT
from ..shocks import generate_shocks, override_strength
from ..visualization import plot_centrality_sweep
from .base import BASELINE_GOVERNANCE, BaseExperiment, run_paired
from .exp5_mechanism_check import run_bimodality_check
from .params import ParamSpec

_DEFAULT_STRENGTHS = [float(s) for s in np.linspace(0.05, 0.60, 8)]
_TARGET_TYPES = ("hub", "random")


class CentralitySweepExperiment(BaseExperiment):
    """Experiment 5: Centrality × Shock Strength Sweep.

    Parameters
    ----------
    strengths : list of float
        Shock strength values to sweep. Default linspace(0.05, 0.60, 8).
    target_types : list of str
        Targeting strategies. Default ["hub", "random"].
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "centrality"
    title = "Exp 5: Centrality × shock strength sweep"
    PARAMS = (
        ParamSpec("strengths", "float", _DEFAULT_STRENGTHS, many=True, minimum=0.0, maximum=1.0,
                  help="Shock strengths to sweep. The bimodality check needs 0.05 and 0.6."),
        ParamSpec("target_types", "choice", list(_TARGET_TYPES), many=True, choices=_TARGET_TYPES,
                  help="Shock targeting strategies. The KDE figure needs both."),
    )

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]   = None,
        policy_text  : str                   = DEFAULT_POLICY_TEXT,
        strengths    : Optional[List[float]] = None,
        target_types : Optional[List[str]]   = None,
        sim_config   : Optional[SimConfig]   = None,
        policy       : Optional[Policy]      = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.strengths    = strengths or list(_DEFAULT_STRENGTHS)
        self.target_types = target_types or list(_TARGET_TYPES)

    def total_units(self) -> int:
        return len(self.seeds) * len(self.target_types) * len(self.strengths)

    # Shared with exp5_mechanism_check so both use identical conditions.
    shock_config = ShockConfig(shock_prob=0.2, mode=ShockMode.DIRECTIONAL)
    gov_config   = GovernanceConfig(**BASELINE_GOVERNANCE)

    def run(self) -> pd.DataFrame:
        policy = self._policy()
        rows   = []
        total  = self.total_units()

        for seed in self.seeds:
            base_schedule = generate_shocks(self.shock_config, self.sim_config.n_ticks, seed)

            for target_type in self.target_types:
                for strength in self.strengths:
                    schedule = override_strength(base_schedule, strength, target_type)
                    m_c, m_t = run_paired(
                        self.sim_config, self.gov_config, policy, schedule, seed
                    )

                    rows.append({
                        "seed"           : seed,
                        "target_type"    : target_type,
                        "shock_strength" : round(float(strength), 4),
                        "control_var"    : m_c["variance"],
                        "treat_var"      : m_t["variance"],
                        "delta"          : m_t["variance"] - m_c["variance"],
                        "delta_variance" : m_t["delta_variance"],
                        "cascade_breadth": m_t["cascade_breadth"],
                        "num_shocks"     : len(schedule),
                    })

                    self._emit(
                        type="seed_complete", experiment=self.__class__.__name__,
                        completed=len(rows), total=total,
                        condition={
                            "target_type": target_type,
                            "shock_strength": round(float(strength), 4),
                        },
                        seed=seed,
                    )

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        summary = group_summary(
            df,
            ["target_type", "shock_strength"],
            ["delta", "cascade_breadth"],
        )

        print("\n=== Exp 5: Centrality × Shock Strength ===")
        print(summary.to_string(index=False))

        # Post-hoc mechanism measurement (bifurcation index + KDE figure)
        self.mechanism_summary = run_bimodality_check(self)

        return summary

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        return [plot_centrality_sweep(df, self.output_dir)]
