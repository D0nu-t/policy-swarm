"""
policyswarm.experiments.exp4c_epsilon_calibration
===================================================
Experiment 4c: Geometry-Adjusted Threshold Sensitivity

Is the Experiment 4 geometry x lag interaction a genuine geometry effect or
a threshold (epsilon) artefact? A single raw epsilon produces very different
interaction coverage under Euclidean vs angular distance, so this experiment
runs two arms over the same lag grid and seeds as Experiment 4:

1. RAW: every geometry uses the same raw epsilon, for each value in
   ``epsilons`` (default {0.6, 1.0, 1.4}, the centred-space equivalents of
   {0.3, 0.5, 0.7} on [0, 1]). This documents the confounded comparison.

2. COVERAGE_MATCHED: for each value in ``epsilons`` taken as the Euclidean
   reference threshold, every other geometry gets the epsilon admitting the
   same fraction of network-neighbour pairs at initialisation
   (geometry.matched_epsilons). If a geometry effect survives across all
   coverage levels, the asymmetric-threshold confound is ruled out; if it
   appears only in the RAW arm, it is a threshold artefact.

Output
------
raw_sweep_stats.csv, coverage_matched_stats.csv       per-cell paired tests
lag_trend_by_geometry.csv, lag_geometry_interaction.csv
    lag x geometry interaction for every (mode, ref_epsilon) level
The realised gate pass rate of every run is recorded in the results CSV.
"""

from __future__ import annotations

import dataclasses
import os
from typing import List, Optional

import pandas as pd

from ..analysis import (
    executive_summary, interaction_summary, lag_geometry_interaction, stat_test_table,
)
from ..config import Geometry, Policy, ShockMode, SimConfig
from ..extraction import DEFAULT_POLICY_TEXT
from ..visualization import plot_phase_diagram
from .base import BaseExperiment
from .exp4_counterfactual import (
    GEOMETRIES_PARAM, LAGS_PARAM, SHOCK_MODE_PARAM, run_paired_geometry_lag,
)
from .params import ParamSpec

_DEFAULT_EPSILONS = [0.6, 1.0, 1.4]


class EpsilonCalibrationExperiment(BaseExperiment):
    """Experiment 4c: Geometry-Adjusted Threshold Sensitivity.

    Parameters
    ----------
    lags : list of int
        Default matches Experiment 4: [0, 20, 40].
    epsilons : list of float
        Raw epsilon values (RAW arm) and Euclidean reference thresholds
        (COVERAGE_MATCHED arm). Default [0.6, 1.0, 1.4].
    geometries : list of Geometry
        Default [EUCLIDEAN, COSINE].
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "epsilon"
    title = "Exp 4c: Raw vs coverage-matched threshold sensitivity"
    PARAMS = (
        LAGS_PARAM,
        ParamSpec("epsilons", "float", _DEFAULT_EPSILONS, many=True, minimum=0.0,
                  help="Raw thresholds, also used as the Euclidean reference when matching."),
        GEOMETRIES_PARAM, SHOCK_MODE_PARAM,
    )

    def __init__(
        self,
        output_dir  : str,
        seeds       : Optional[List[int]]      = None,
        policy_text : str                      = DEFAULT_POLICY_TEXT,
        lags        : Optional[List[int]]      = None,
        epsilons    : Optional[List[float]]    = None,
        geometries  : Optional[List[Geometry]] = None,
        shock_mode  : ShockMode                = ShockMode.COORDINATING,
        sim_config  : Optional[SimConfig]      = None,
        policy      : Optional[Policy]         = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.lags        = lags or list(LAGS_PARAM.default)
        self.epsilons    = epsilons or list(_DEFAULT_EPSILONS)
        self.geometries  = geometries or [Geometry.EUCLIDEAN, Geometry.COSINE]
        self.shock_mode  = shock_mode

        # Populated by run(): {ref_epsilon: {geometry: epsilon}}
        self.calibrated_epsilon: dict = {}

    def total_units(self) -> int:
        return 2 * len(self.epsilons) * len(self.geometries) * len(self.lags) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        frames = []
        done   = 0
        total  = self.total_units()

        def arm(mode, ref_eps, epsilons):
            nonlocal done
            df = run_paired_geometry_lag(
                self, self.sim_config, self.geometries, self.lags, epsilons,
                self.shock_mode,
                extra_fields={"mode": mode, "ref_epsilon": ref_eps},
                progress_offset=done, progress_total=total,
            )
            done += len(df)
            frames.append(df)

        for ref_eps in self.epsilons:
            arm("raw", ref_eps, {g.value: ref_eps for g in self.geometries})

        for ref_eps in self.epsilons:
            sc = dataclasses.replace(self.sim_config, epsilon=ref_eps)
            matched = self._geometry_epsilons(sc, self.geometries, "matched")
            self.calibrated_epsilon[ref_eps] = matched
            arm("coverage_matched", ref_eps, matched)

        return pd.concat(frames, ignore_index=True)

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        results = {}
        trends, inters = [], []
        for mode in ["raw", "coverage_matched"]:
            sub = df[df["mode"] == mode]
            stats = stat_test_table(
                sub, groupby_cols=["ref_epsilon", "geometry", "lag"],
                control_col="control_var", treatment_col="treat_var",
                label="effect",
            )
            print(executive_summary(
                stats, experiment=f"Exp 4c: Epsilon sensitivity ({mode})"
            ))
            results[mode] = stats

            for ref_eps, cell in sub.groupby("ref_epsilon"):
                for value_col in ("delta", "rel_delta"):
                    per_g, pair = lag_geometry_interaction(cell, value_col)
                    for frame in (per_g, pair):
                        frame.insert(0, "ref_epsilon", ref_eps)
                        frame.insert(0, "mode", mode)
                    print(interaction_summary(
                        per_g, pair,
                        title=f"({mode}, ref eps={ref_eps:g}, {value_col})",
                    ))
                    trends.append(per_g)
                    inters.append(pair)

        gate = df.groupby(["mode", "ref_epsilon", "geometry"])[
            ["epsilon", "gate_pass_ctrl"]].mean()
        print("\nEpsilon and realised gate pass rate (control runs):")
        print(gate.to_string())

        results["raw"].to_csv(
            os.path.join(self.output_dir, "raw_sweep_stats.csv"), index=False)
        results["coverage_matched"].to_csv(
            os.path.join(self.output_dir, "coverage_matched_stats.csv"), index=False)
        pd.concat(trends).to_csv(
            os.path.join(self.output_dir, "lag_trend_by_geometry.csv"), index=False)
        pd.concat(inters).to_csv(
            os.path.join(self.output_dir, "lag_geometry_interaction.csv"), index=False)

        # The coverage-matched table is the primary summary since it is the
        # direct test of the geometry-vs-threshold confound.
        return results["coverage_matched"]

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = []
        for mode in ["raw", "coverage_matched"]:
            for ref_eps, cell in df[df["mode"] == mode].groupby("ref_epsilon"):
                paths.append(plot_phase_diagram(
                    cell, self.output_dir, delta_col="rel_delta",
                    filename=f"epsilon_{mode}_{ref_eps:g}_phase_diagram.png",
                ))
        return [p for p in paths if p]
