"""
policyswarm.experiments.exp5_centrality_sweep
==============================================
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

from ..config import SimConfig, GovernanceConfig, ShockConfig, ShockMode
from ..extraction import policy_from_text
from ..shocks import generate_shocks, override_strength
from ..dynamics import Simulation
from ..metrics import compute_all_metrics
from ..analysis import group_summary, executive_summary
from ..visualization import plot_centrality_sweep
from .base import BaseExperiment

_DEFAULT_TEXT = """
The government introduces strict AI safety regulations requiring transparency
audits, limiting deployment of high-risk systems, and enforcing penalties for
non-compliance. The policy prioritises public safety over innovation risks.
"""


class CentralitySweepExperiment(BaseExperiment):
    """Experiment 5: Centrality × Shock Strength Sweep.

    Parameters
    ----------
    strengths : list of float
        Shock strength values to sweep. Default linspace(0.05, 0.60, 8).
    target_types : list of str
        Targeting strategies. Default ["hub", "random"].
    """

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]  = None,
        policy_text  : str                  = _DEFAULT_TEXT,
        strengths    : Optional[List[float]] = None,
        target_types : Optional[List[str]]   = None,
        sim_config   : Optional[SimConfig]   = None,
    ):
        super().__init__(output_dir, seeds)
        self.policy_text  = policy_text
        self.strengths    = strengths or list(np.linspace(0.05, 0.60, 8))
        self.target_types = target_types or ["hub", "random"]
        self.sim_config   = sim_config or SimConfig()

    def run(self) -> pd.DataFrame:
        base_policy = policy_from_text(self.policy_text)
        # Use directional shock mode for Exp 5
        base_shock_config = ShockConfig(
            shock_prob = 0.2,
            mode       = ShockMode.DIRECTIONAL,
        )
        gov_config = GovernanceConfig(
            deployment_rate_cap = 0.5, penalty_severity = 0.5
        )
        rows = []

        for seed in self.seeds:
            base_schedule = generate_shocks(
                base_shock_config, self.sim_config.n_ticks, seed
            )

            for target_type in self.target_types:
                for strength in self.strengths:
                    schedule = override_strength(base_schedule, strength, target_type)

                    sim_c = Simulation(
                        self.sim_config, gov_config, base_policy, schedule,
                        apply_shocks=False, seed=seed,
                    )
                    sim_c.run()

                    sim_t = Simulation(
                        self.sim_config, gov_config, base_policy, schedule,
                        apply_shocks=True, seed=seed,
                    )
                    sim_t.run()

                    m_c = compute_all_metrics(sim_c)
                    m_t = compute_all_metrics(sim_t)

                    rows.append({
                        "seed"          : seed,
                        "target_type"   : target_type,
                        "shock_strength": round(float(strength), 4),
                        "control_var"   : m_c["variance"],
                        "treat_var"     : m_t["variance"],
                        "delta"         : m_t["variance"] - m_c["variance"],
                        "delta_variance": m_t["delta_variance"],
                        "cascade_breadth": m_t["cascade_breadth"],
                        "num_shocks"    : len(schedule),
                    })

        return pd.DataFrame(rows)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        summary = group_summary(
            df, ["target_type", "shock_strength"],
            ["delta", "cascade_breadth"]
        )
        print("\n=== Exp 5: Centrality × Shock Strength ===")
        print(summary.to_string(index=False))
        return summary

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        return [plot_centrality_sweep(df, self.output_dir)]
