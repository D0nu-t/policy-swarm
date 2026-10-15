"""
policyswarm.experiments.exp5_mechanism_check
============================================
Post-hoc mechanism measurement for Experiment 5, called from
CentralitySweepExperiment.analyse(). Not a registered experiment.

Addendum to Experiment 5 addressing the advisor review's core remaining
request: "at least one proposed mechanism should actually be measured."

This patch adds a dedicated post-hoc measurement step, run_bimodality_check(),
which the paper's Experiment 5 section can now cite directly instead of
describing bimodality as an untested hypothesis. It does NOT change the
main sweep (run/analyse/plot) — those stay exactly as before, so all
existing S=30 results in Table 4 / Figure 4 are unaffected and remain
reproducible byte-for-byte.

What it measures
-----------------
At the highest tested shock strength (0.60) and lowest (0.05), for both
target types (hub, random), across the same S=30 seeds:
  1. Bifurcation Index (BI) on the final opinion distribution
     (p_dep dimension) -- already implemented in metrics.py, simply not
     previously reported for Experiment 5.
  2. A saved KDE plot of the final p_dep distribution, overlaying hub vs
     random at high strength, so bimodality (or its absence) is directly
     visible rather than inferred from the variance trend alone.

Usage
-----
    from policyswarm.experiments.exp5_centrality import CentralitySweepExperiment
    from policyswarm.experiments.exp5_mechanism_check import run_bimodality_check

    exp = CentralitySweepExperiment(output_dir="policyswarm_output/centrality",
                                    seeds=list(range(30)))
    report = exp.report()                     # unchanged main sweep
    bi_summary = run_bimodality_check(exp)     # new: measures the mechanism
"""

from __future__ import annotations

from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from ..dynamics import Simulation
from ..metrics import bifurcation_index
from ..shocks import generate_shocks, override_strength

_KDE_COLORS = {"hub": "#D85A30", "random": "#1D9E75"}


def _final_opinions_for_condition(
    exp,
    target_type : str,
    strength    : float,
    seed        : int,
) -> np.ndarray:
    """Re-run a single (target_type, strength, seed) condition from
    CentralitySweepExperiment and return the treatment run's final
    opinion matrix. Mirrors exp.run()'s per-cell logic exactly so the
    mechanism check uses identical dynamics to the reported results."""
    base_schedule = generate_shocks(exp.shock_config, exp.sim_config.n_ticks, seed)
    schedule = override_strength(base_schedule, strength, target_type)

    sim_t = Simulation(
        exp.sim_config, exp.gov_config, exp._policy(), schedule,
        apply_shocks=True, seed=seed,
    )
    sim_t.run()
    return sim_t.final_opinions


def run_bimodality_check(
    exp,
    strengths_to_check : List[float] = (0.05, 0.60),
    dim                : int = 0,
    save_path          : str = None,
) -> pd.DataFrame:
    """
    Measure whether hub targeting produces bimodal final opinion
    distributions while random targeting does not, at the strength
    extremes tested in the main sweep.

    Parameters
    ----------
    exp : CentralitySweepExperiment
        Must already be constructed with the same seeds/policy_text/
        sim_config used for the main results, so this check uses the
        identical population and shock schedule per seed.
    strengths_to_check : tuple of float
        Which shock_strength values from exp.strengths to inspect.
        Default (0.05, 0.60) -- the low and high ends of the sweep.
    dim : int
        Opinion dimension to project onto for BI and the KDE plot.
        Default 0 (deployment_cap / p_dep), matching bifurcation_index's
        default and the paper's stated convention.
    save_path : str, optional
        Where to save the KDE comparison figure. Defaults to
        f"{exp.output_dir}/opinion_kde_hub_vs_random.png".

    Returns
    -------
    pd.DataFrame
        Columns: target_type, strength, seed, bifurcation_index.
        One row per (target_type, strength, seed) combination in
        strengths_to_check x exp.target_types x exp.seeds.
    """
    rows = []
    all_finals = {}  # (target_type, strength) -> list of final opinion matrices

    for strength in strengths_to_check:
        for target_type in exp.target_types:
            finals = []
            for seed in exp.seeds:
                final = _final_opinions_for_condition(exp, target_type, strength, seed)
                finals.append(final)
                bi = bifurcation_index(final, dim=dim)
                rows.append({
                    "target_type": target_type,
                    "strength": round(float(strength), 4),
                    "seed": seed,
                    "bifurcation_index": bi,
                })
            all_finals[(target_type, strength)] = finals

    bi_df = pd.DataFrame(rows)

    # --- KDE comparison figure -------------------------------------------
    # Pool the final p_dep values across all seeds for each condition at
    # the HIGHEST strength tested, since that is where the mechanistic
    # account predicts the sharpest bimodality contrast.
    high_strength = max(strengths_to_check)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    grid = np.linspace(-1, 1, 300)
    bandwidth = 0.16   # absolute, same as metrics.bifurcation_index

    for target_type in exp.target_types:
        color = _KDE_COLORS.get(target_type, "#555555")
        pooled = np.concatenate([
            finals[:, dim] for finals in all_finals[(target_type, high_strength)]
        ])
        # scipy's scalar bw_method is a factor on the sample std
        kde = gaussian_kde(pooled, bw_method=bandwidth / np.std(pooled, ddof=1))
        density = kde(grid)
        ax.plot(grid, density, color=color, lw=2.2,
                label=f"{target_type.capitalize()} targeting")
        ax.fill_between(grid, density, color=color, alpha=0.15)

    ax.set_xlabel(r"Final opinion, $p_{\mathrm{dep}}$ dimension")
    ax.set_ylabel("Density")
    ax.set_title(
        f"Final Opinion Distribution at Shock Strength = {high_strength}\n"
        "(pooled across S seeds; measures the bimodality mechanism directly)"
    )
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out_path = save_path or f"{exp.output_dir}/opinion_kde_hub_vs_random.png"
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    # --- Summary printed to stdout ----------------------------------------
    print(f"\n=== Bimodality Mechanism Check (dim={dim}) ===")
    summary = bi_df.groupby(["target_type", "strength"])["bifurcation_index"].agg(
        ["mean", "std"]
    ).reset_index()
    print(summary.to_string(index=False))
    print(f"\nKDE comparison saved to: {out_path}")

    if not {"hub", "random"} <= set(exp.target_types):
        return bi_df    # the verdict compares hub against random; needs both

    mean_bi_hub_high = bi_df[
        (bi_df.target_type == "hub") & (bi_df.strength == high_strength)
    ]["bifurcation_index"].mean()
    mean_bi_random_high = bi_df[
        (bi_df.target_type == "random") & (bi_df.strength == high_strength)
    ]["bifurcation_index"].mean()

    if mean_bi_hub_high > mean_bi_random_high + 0.3:
        verdict = (
            "SUPPORTED: hub targeting shows higher mean BI than random "
            "targeting at high strength, consistent with the bimodality "
            "account."
        )
    elif abs(mean_bi_hub_high - mean_bi_random_high) <= 0.3:
        verdict = (
            "NOT SUPPORTED: BI does not meaningfully differ between hub "
            "and random targeting at high strength. The variance increase "
            "under hub targeting may have a different structural cause "
            "than simple bimodal clustering."
        )
    else:
        verdict = (
            "UNEXPECTED: random targeting shows higher BI than hub "
            "targeting -- opposite of the candidate mechanism's prediction."
        )

    print(f"\nVerdict: {verdict}")

    return bi_df
