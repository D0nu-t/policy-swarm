"""
policyswarm.experiments.exp4b_topology_validation
===================================================
Experiment 4b: Cross-Topology Geometry Validation

Addresses the single largest open robustness question for the paper's
central finding: does the Euclidean/cosine lag interaction in Experiment 4
hold on Stochastic Block Model networks, or is it a BA-network artefact?

Design
------
Identical to Experiment 4 (geometry x lag, COORDINATING shocks, coverage-
matched epsilon by default) except SimConfig.network_type is set to
STOCHASTIC_BLOCK. Same seeds, same lag grid, same geometries, so results are
directly comparable row-by-row against exp4_counterfactual.py's BA output.
Epsilon is re-calibrated on the SBM networks, since neighbour-pair distances
depend on the topology.

Interpretation
--------------
Read the lag x geometry interaction table (sbm_lag_geometry_interaction.csv),
not the per-cell significance: the direction of the lag trend per geometry
(amplifies / attenuates / n.s.) and whether the between-geometry interaction
is significant.
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional
import pandas as pd

from ..config import SimConfig, ShockMode, Geometry, NetworkType
from ..visualization import plot_phase_diagram
from .base import BaseExperiment
from .exp4_counterfactual import (
    _DEFAULT_TEXT, analyse_geometry_lag, run_paired_geometry_lag,
)


class TopologyValidationExperiment(BaseExperiment):
    """Experiment 4b: Cross-Topology Geometry Validation (SBM).

    Identical grid to CounterfactualShockExperiment but forces
    NetworkType.STOCHASTIC_BLOCK. Intended to be run alongside Experiment 4
    (BA) so the two result tables can be placed side by side.

    Parameters
    ----------
    lags : list of int
    geometries : list of Geometry
    shock_mode : ShockMode
    epsilon_mode : {"matched", "raw"}
    sbm_communities, sbm_p_in, sbm_p_out : SBM topology parameters,
        matching the defaults documented in Section 4.3 of the paper.
    """

    def __init__(
        self,
        output_dir      : str,
        seeds           : Optional[List[int]]      = None,
        policy_text     : str                       = _DEFAULT_TEXT,
        lags            : Optional[List[int]]       = None,
        geometries      : Optional[List[Geometry]]  = None,
        shock_mode      : ShockMode                 = ShockMode.COORDINATING,
        sim_config      : Optional[SimConfig]       = None,
        sbm_communities : int                       = 3,
        sbm_p_in        : float                     = 0.20,
        sbm_p_out       : float                     = 0.02,
        epsilon_mode    : str                       = "matched",
    ):
        super().__init__(output_dir, seeds)
        self.policy_text  = policy_text
        self.lags         = lags or [0, 20, 40]
        self.geometries   = geometries or [Geometry.EUCLIDEAN, Geometry.COSINE]
        self.shock_mode   = shock_mode
        self.epsilon_mode = epsilon_mode

        # Force SBM topology; keep every other parameter identical to Exp 4
        self.sim_config = dataclasses.replace(
            sim_config or SimConfig(),
            network_type      = NetworkType.STOCHASTIC_BLOCK,
            sbm_n_communities = sbm_communities,
            sbm_p_in          = sbm_p_in,
            sbm_p_out         = sbm_p_out,
        )

    def total_units(self) -> int:
        return len(self.geometries) * len(self.lags) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        epsilons = self._geometry_epsilons(
            self.sim_config, self.geometries, self.epsilon_mode
        )
        return run_paired_geometry_lag(
            self, self.sim_config, self.geometries, self.lags, epsilons,
            self.shock_mode, extra_fields={"topology": "sbm"},
        )

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        return analyse_geometry_lag(
            df, self.output_dir,
            "Exp 4b: Cross-Topology Geometry Validation (SBM)", prefix="sbm_",
        )

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [
            plot_phase_diagram(df, self.output_dir,
                               filename="sbm_phase_diagram.png"),
            plot_phase_diagram(df, self.output_dir, delta_col="rel_delta",
                               filename="sbm_phase_diagram_relative.png"),
        ]
        return [p for p in paths if p]
