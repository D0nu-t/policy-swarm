"""
policyswarm.experiments.exp4_counterfactual
============================================
Experiment 4: Counterfactual Shock Analysis

Design
------
Paired counterfactual design (Iteration 10):
  - Generate one shock schedule per seed (shared between control and treatment)
  - Control:   apply_shocks=False
  - Treatment: apply_shocks=True
  - Shock mode configurable (default: COORDINATING = mean-reverting)

Grid: lag ∈ {0, 20, 40} × geometry ∈ {euclidean, cosine} × seed ∈ seeds

Bounded-confidence threshold
----------------------------
By default each geometry gets a coverage-matched epsilon (see
geometry.matched_epsilons): Euclidean keeps SimConfig.epsilon and cosine is
calibrated to admit the same fraction of neighbour pairs at initialisation.
A single raw epsilon across geometries confounds the geometry comparison with
threshold coverage (under the old [0, 1] opinion space, cosine at epsilon=0.5
admitted ~94% of pairs vs ~13% for Euclidean). ``epsilon_mode="raw"``
reproduces the unmatched comparison for sensitivity analysis. The realised
gate pass rate of every run is recorded (``gate_pass_rate``).

Analysis
--------
  1. Per-cell paired t-test of Δ = OV_treat - OV_ctrl (absolute and relative).
  2. Lag x geometry interaction (analysis.lag_geometry_interaction): per-seed
     contrast Δ(lag_max) - Δ(lag_min) within each geometry, and the paired
     difference of contrasts between geometries. A claim that geometry
     reverses the lag effect requires this test, not the per-cell tests.

Note on shock polarity (design document)
-----------------------------------------
The COORDINATING shock models crisis-induced consensus, not polarizing events.
Use ShockMode.POLARIZING to study the destabilising regime. Both are
empirically real phenomena requiring different implementations.
"""

from __future__ import annotations

import dataclasses
import os
from typing import List, Optional

import pandas as pd

from ..analysis import (
    executive_summary, interaction_summary, lag_geometry_interaction, stat_test_table,
)
from ..config import Geometry, GovernanceConfig, Policy, ShockConfig, ShockMode, SimConfig
from ..dynamics import Simulation
from ..extraction import DEFAULT_POLICY_TEXT
from ..shocks import generate_shocks
from ..visualization import plot_phase_diagram, plot_variance_comparison
from .base import BASELINE_GOVERNANCE, BaseExperiment, run_paired
from .exp6_geometry import EPSILON_MODES
from .params import ParamSpec

_DEFAULT_LAGS = [0, 20, 40]
_DEFAULT_GEOMETRIES = [Geometry.EUCLIDEAN, Geometry.COSINE]

#: ParamSpecs shared by the three geometry x lag experiments (4, 4b, 4c).
LAGS_PARAM = ParamSpec("lags", "int", _DEFAULT_LAGS, many=True, minimum=0,
                       help="Enforcement lag values (ticks) to sweep.")
GEOMETRIES_PARAM = ParamSpec("geometries", "choice", [g.value for g in _DEFAULT_GEOMETRIES],
                             many=True, enum=Geometry,
                             help="Opinion-space geometries to compare.")
SHOCK_MODE_PARAM = ParamSpec("shock_mode", "choice", ShockMode.COORDINATING.value,
                             enum=ShockMode, help="Directional character of the shocks.")
EPSILON_MODE_PARAM = ParamSpec(
    "epsilon_mode", "choice", "matched", choices=EPSILON_MODES,
    help="matched: coverage-matched threshold per geometry; raw: one shared value.")


def run_paired_geometry_lag(
    exp,
    sim_config   : SimConfig,
    geometries   : List[Geometry],
    lags         : List[int],
    epsilons     : dict,
    shock_mode   : ShockMode,
    extra_fields : Optional[dict] = None,
    pull_onset   : Optional[int]  = GovernanceConfig.policy_pull_onset,
    progress_offset : int           = 0,
    progress_total  : Optional[int] = None,
) -> pd.DataFrame:
    """Shared paired control/treatment loop for Experiments 4, 4b and 4c.

    ``exp`` supplies the policy, seeds and _emit(). One row per
    (geometry, lag, seed). ``progress_offset``/``progress_total`` let callers
    that invoke this several times emit cumulative progress events.
    """
    rows  = []
    total = progress_total or len(geometries) * len(lags) * len(exp.seeds)
    extra_fields = extra_fields or {}

    for geometry in geometries:
        sc = dataclasses.replace(sim_config, epsilon=epsilons[geometry.value])

        for lag in lags:
            policy = exp._policy()
            policy.lag = lag
            shock_config = ShockConfig(mode=shock_mode)

            gov_config = GovernanceConfig(
                **BASELINE_GOVERNANCE,
                enforcement_lag   = lag,
                policy_pull_onset = pull_onset,
            )

            for seed in exp.seeds:
                shocks = generate_shocks(shock_config, sc.n_ticks, seed)
                m_c, m_t = run_paired(sc, gov_config, policy, shocks, seed, geometry)
                delta = m_t["variance"] - m_c["variance"]

                rows.append({
                    **extra_fields,
                    "geometry"        : geometry.value,
                    "epsilon"         : sc.epsilon,
                    "lag"             : lag,
                    "seed"            : seed,
                    "control_var"     : m_c["variance"],
                    "treat_var"       : m_t["variance"],
                    "delta"           : delta,
                    "rel_delta"       : delta / m_c["variance"],
                    "polarization"    : m_t["polarization"],
                    "cascade_breadth" : m_t["cascade_breadth"],
                    "phase_t"         : m_t["phase_transition_tick"],
                    "delta_variance"  : m_t["delta_variance"],
                    "gate_pass_ctrl"  : m_c["gate_pass_rate"],
                    "gate_pass_treat" : m_t["gate_pass_rate"],
                    "num_shocks"      : len(shocks),
                    "shock_mode"      : shock_mode.value,
                })

                exp._emit(
                    type="seed_complete", experiment=exp.__class__.__name__,
                    completed=progress_offset + len(rows), total=total,
                    condition={"geometry": geometry.value, "lag": lag,
                               **extra_fields},
                    seed=seed,
                )

    return pd.DataFrame(rows)


def analyse_geometry_lag(df: pd.DataFrame, output_dir: str, title: str,
                         prefix: str = "") -> pd.DataFrame:
    """Per-cell stats plus lag x geometry interaction for Experiments 4/4b."""
    stats = stat_test_table(
        df,
        groupby_cols  = ["geometry", "lag"],
        control_col   = "control_var",
        treatment_col = "treat_var",
        label         = "effect",
    )
    print(executive_summary(stats, experiment=title))

    gate = df.groupby(["geometry", "lag"])[["epsilon", "gate_pass_ctrl"]].mean()
    print("\nEpsilon and realised gate pass rate (control runs):")
    print(gate.to_string())

    frames_g, frames_p = [], []
    for value_col in ("delta", "rel_delta"):
        per_g, pair = lag_geometry_interaction(df, value_col)
        print(interaction_summary(per_g, pair, title=f"({value_col})"))
        frames_g.append(per_g)
        frames_p.append(pair)
    pd.concat(frames_g).to_csv(
        os.path.join(output_dir, f"{prefix}lag_trend_by_geometry.csv"), index=False)
    pd.concat(frames_p).to_csv(
        os.path.join(output_dir, f"{prefix}lag_geometry_interaction.csv"), index=False)
    return stats


class CounterfactualShockExperiment(BaseExperiment):
    """Experiment 4: Counterfactual Shock Analysis.

    Parameters
    ----------
    lags : list of int
    geometries : list of Geometry
    shock_mode : ShockMode
        Directional character of shocks. Default COORDINATING.
    epsilon_mode : {"matched", "raw"}
        How each geometry's bounded-confidence threshold is set. Default
        "matched" (coverage-matched to Euclidean at SimConfig.epsilon).
    pull_onset : int, optional
        Perceived-policy pull onset. Defaults to GovernanceConfig's fixed
        onset, so "lag" varies only the enforcement penalty. None restores
        the legacy coupling (pull starts at the enforcement lag).
    output_dir, seeds, policy_text, policy, sim_config
        See ``BaseExperiment``.
    """

    name  = "counterfactual"
    title = "Exp 4: Counterfactual shocks (geometry × lag)"
    PARAMS = (
        LAGS_PARAM, GEOMETRIES_PARAM, SHOCK_MODE_PARAM, EPSILON_MODE_PARAM,
        ParamSpec("pull_onset", "int", GovernanceConfig.policy_pull_onset, optional=True,
                  minimum=0, help="Tick the perceived-policy pull starts. Empty = start at the lag."),
    )

    def __init__(
        self,
        output_dir   : str,
        seeds        : Optional[List[int]]      = None,
        policy_text  : str                      = DEFAULT_POLICY_TEXT,
        lags         : Optional[List[int]]      = None,
        geometries   : Optional[List[Geometry]] = None,
        shock_mode   : ShockMode                = ShockMode.COORDINATING,
        sim_config   : Optional[SimConfig]      = None,
        epsilon_mode : str                      = "matched",
        pull_onset   : Optional[int]            = GovernanceConfig.policy_pull_onset,
        policy       : Optional[Policy]         = None,
    ):
        super().__init__(output_dir, seeds, policy_text, policy, sim_config)
        self.lags         = lags or list(_DEFAULT_LAGS)
        self.geometries   = geometries or list(_DEFAULT_GEOMETRIES)
        self.shock_mode   = shock_mode
        self.epsilon_mode = epsilon_mode
        self.pull_onset   = pull_onset

    def total_units(self) -> int:
        return len(self.geometries) * len(self.lags) * len(self.seeds)

    def run(self) -> pd.DataFrame:
        epsilons = self._geometry_epsilons(
            self.sim_config, self.geometries, self.epsilon_mode
        )
        return run_paired_geometry_lag(
            self, self.sim_config, self.geometries, self.lags, epsilons,
            self.shock_mode, pull_onset=self.pull_onset,
        )

    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        return analyse_geometry_lag(
            df, self.output_dir, "Exp 4: Counterfactual Shock Analysis"
        )

    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        paths = [
            plot_phase_diagram(df, self.output_dir),
            plot_phase_diagram(df, self.output_dir, delta_col="rel_delta",
                               filename="phase_diagram_relative.png"),
        ]

        # One control vs treatment comparison plot for the first seed, lowest
        # lag, Euclidean geometry — using the experiment's own configuration.
        seed = self.seeds[0]
        lag  = min(self.lags)
        plot_policy = self._policy()
        plot_policy.lag = lag
        sc = ShockConfig(mode=self.shock_mode)
        gov = GovernanceConfig(
            **BASELINE_GOVERNANCE,
            enforcement_lag=lag, policy_pull_onset=self.pull_onset,
        )
        eps = df.loc[df["geometry"] == Geometry.EUCLIDEAN.value, "epsilon"]
        sim_config = (
            dataclasses.replace(self.sim_config, epsilon=float(eps.iloc[0]))
            if len(eps) else self.sim_config
        )
        shocks = generate_shocks(sc, sim_config.n_ticks, seed=seed)

        sim_c = Simulation(sim_config, gov, plot_policy, shocks,
                           apply_shocks=False, seed=seed)
        sim_c.run()
        sim_t = Simulation(sim_config, gov, plot_policy, shocks,
                           apply_shocks=True, seed=seed)
        sim_t.run()

        p = plot_variance_comparison(
            sim_c.history, sim_t.history, shocks,
            self.output_dir, "variance_comparison_exp4.png",
        )
        paths.append(p)
        return [p for p in paths if p]
