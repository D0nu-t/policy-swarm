"""
policyswarm.visualization
=========================
Publication-ready plot generation for all experiments.

All functions accept a DataFrame (from an experiment runner) plus an output
directory path, write a PNG, and return the file path.

Plot catalogue
--------------
plot_phase_diagram          Shock effect (Δvar) vs enforcement lag, by geometry
plot_cb_vs_lag              Cascade breadth vs lag, by media condition
plot_variance_timeline      Opinion variance over time with shock tick markers
plot_opinion_scatter        2D opinion scatter coloured by community
plot_causal_heatmap         Network diagram with node size ∝ out-strength
plot_centrality_sweep       Δvar vs shock strength, hub vs random targets
plot_geometry_comparison    Polarization comparison across geometries
plot_oversight_phase        CB and variance across oversight regimes
"""

from __future__ import annotations

import os
from typing import List, Optional, Dict
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless runs
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# Consistent style across all plots
plt.rcParams.update({
    "font.family"     : "sans-serif",
    "axes.spines.top" : False,
    "axes.spines.right": False,
    "axes.grid"       : True,
    "grid.alpha"      : 0.3,
    "figure.dpi"      : 120,
})

_COLORS = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0"]


def _save(fig, path: str) -> str:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 1. Phase diagram: shock effect vs enforcement lag
# ---------------------------------------------------------------------------

def plot_phase_diagram(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "phase_diagram.png",
) -> str:
    """Plot mean Δvariance vs enforcement lag, with separate lines per geometry.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: geometry, lag, delta (or delta_variance).
    output_dir : str
    filename : str

    Returns
    -------
    str : file path of saved figure.
    """
    delta_col = "delta" if "delta" in df.columns else "delta_variance"

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (geom, sub) in enumerate(df.groupby("geometry")):
        grouped = sub.groupby("lag")[delta_col].agg(["mean", "sem"])
        ax.errorbar(
            grouped.index, grouped["mean"],
            yerr=grouped["sem"],
            marker="o", label=str(geom),
            color=_COLORS[i % len(_COLORS)],
            capsize=3, linewidth=1.8,
        )

    ax.axhline(0, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Enforcement Lag (ticks)")
    ax.set_ylabel("Δ Opinion Variance (treat − control)")
    ax.set_title("Phase Diagram: Shock Effect vs Enforcement Lag")
    ax.legend(title="Geometry", frameon=False)

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 2. Cascade breadth vs lag
# ---------------------------------------------------------------------------

def plot_cb_vs_lag(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "cb_vs_lag.png",
) -> str:
    """Cascade breadth vs enforcement lag, split by media condition.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: lag, cascade_breadth, enable_media (bool/int).
    output_dir : str
    """
    if "cascade_breadth" not in df.columns:
        return ""

    media_col = "enable_media" if "enable_media" in df.columns else None
    fig, ax = plt.subplots(figsize=(7, 4))

    if media_col and df[media_col].nunique() > 1:
        for i, (media, sub) in enumerate(df.groupby(media_col)):
            grouped = sub.groupby("lag")["cascade_breadth"].agg(["mean", "sem"])
            label   = "Media ON" if media else "Media OFF"
            ax.errorbar(
                grouped.index, grouped["mean"],
                yerr=grouped["sem"],
                marker="s", label=label,
                color=_COLORS[i], capsize=3, linewidth=1.8,
            )
    else:
        grouped = df.groupby("lag")["cascade_breadth"].agg(["mean", "sem"])
        ax.errorbar(
            grouped.index, grouped["mean"],
            yerr=grouped["sem"],
            marker="s", color=_COLORS[0], capsize=3, linewidth=1.8,
        )

    ax.set_xlabel("Enforcement Lag (ticks)")
    ax.set_ylabel("Cascade Breadth")
    ax.set_title("Cascade Breadth vs Enforcement Lag")
    ax.legend(frameon=False)

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 3. Variance timeline with shock markers
# ---------------------------------------------------------------------------

def plot_variance_timeline(
    history    : List[np.ndarray],
    shocks     : List[Dict],
    output_dir : str,
    filename   : str = "variance_timeline.png",
    label      : str = "",
) -> str:
    """Plot opinion variance over time, annotated with shock ticks.

    Parameters
    ----------
    history : list of np.ndarray, each shape (n_agents, dim)
    shocks : list of shock event dicts (from generate_shocks)
    output_dir : str
    label : str
        Line label (e.g., "Treatment" or "Control").
    """
    from .metrics import opinion_variance
    variances = [opinion_variance(h) for h in history]
    ticks     = list(range(len(variances)))

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(ticks, variances, label=label or "Opinion Variance",
            color=_COLORS[0], linewidth=1.8)

    # Shock tick markers
    for shock in shocks:
        t = shock["tick"]
        if t < len(variances):
            ax.axvline(t, color="#F44336", alpha=0.35, linewidth=0.9,
                       linestyle="--")
            ax.text(t, max(variances) * 0.95,
                    f"{shock['strength']:.2f}",
                    fontsize=6, ha="center", color="#F44336", alpha=0.7,
                    rotation=90)

    ax.set_xlabel("Tick")
    ax.set_ylabel("Opinion Variance")
    ax.set_title("Opinion Variance Over Time (red dashes = shocks)")
    if label:
        ax.legend(frameon=False)

    return _save(fig, os.path.join(output_dir, filename))


def plot_variance_comparison(
    history_control   : List[np.ndarray],
    history_treatment : List[np.ndarray],
    shocks            : List[Dict],
    output_dir        : str,
    filename          : str = "variance_comparison.png",
) -> str:
    """Overlay control and treatment variance timelines."""
    from .metrics import opinion_variance
    var_c = [opinion_variance(h) for h in history_control]
    var_t = [opinion_variance(h) for h in history_treatment]
    ticks = list(range(max(len(var_c), len(var_t))))

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(range(len(var_c)), var_c, label="Control",
            color=_COLORS[1], linewidth=1.8, linestyle="--")
    ax.plot(range(len(var_t)), var_t, label="Treatment",
            color=_COLORS[0], linewidth=1.8)

    for shock in shocks:
        t = shock["tick"]
        ax.axvline(t, color="grey", alpha=0.2, linewidth=0.7)

    ax.set_xlabel("Tick")
    ax.set_ylabel("Opinion Variance")
    ax.set_title("Control vs Treatment Variance (grey = shock ticks)")
    ax.legend(frameon=False)

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 4. Opinion scatter (2D projection)
# ---------------------------------------------------------------------------

def plot_opinion_scatter(
    opinions          : np.ndarray,
    community_labels  : Optional[np.ndarray] = None,
    output_dir        : str = ".",
    filename          : str = "opinion_scatter.png",
    dim_x             : int = 0,
    dim_y             : int = 1,
) -> str:
    """2D scatter of agent opinions, coloured by community membership.

    Parameters
    ----------
    opinions : np.ndarray, shape (n_agents, dim)
    community_labels : np.ndarray, shape (n_agents,), optional
    dim_x, dim_y : int
        Dimensions to plot. Default 0 (deployment_cap) and 1 (transparency).
    """
    fig, ax = plt.subplots(figsize=(6, 5))
    x = opinions[:, dim_x]
    y = opinions[:, dim_y]

    if community_labels is not None and len(np.unique(community_labels)) > 1:
        for ci, color in zip(np.unique(community_labels), _COLORS):
            mask = community_labels == ci
            ax.scatter(x[mask], y[mask], s=18, alpha=0.7,
                       color=color, label=f"Community {ci}", edgecolors="none")
        ax.legend(frameon=False, markerscale=1.5)
    else:
        ax.scatter(x, y, s=18, alpha=0.65, color=_COLORS[0], edgecolors="none")

    ax.set_xlabel("Opinion Dim 0 (deployment_cap)")
    ax.set_ylabel("Opinion Dim 1 (transparency)")
    ax.set_title("Agent Opinion Distribution (2D projection)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 5. Causal heatmap (network with out-strength node sizing)
# ---------------------------------------------------------------------------

def plot_causal_heatmap(
    base_graph       : nx.Graph,
    influence_graph  : nx.DiGraph,
    output_dir       : str,
    filename         : str = "causal_heatmap.png",
) -> str:
    """Visualise the base network with node colour ∝ causal out-strength.

    Parameters
    ----------
    base_graph : nx.Graph
        Interaction network.
    influence_graph : nx.DiGraph
        Causal influence graph from Simulation.
    """
    from .metrics import causal_centrality
    centrality = causal_centrality(influence_graph)

    n = base_graph.number_of_nodes()
    strengths = np.array([centrality.get(i, 0.0) for i in range(n)])
    max_s     = strengths.max()
    if max_s > 0:
        strengths /= max_s

    # Use spring layout with fixed seed for reproducibility
    pos = nx.spring_layout(base_graph, seed=42, k=0.5)

    fig, ax = plt.subplots(figsize=(8, 7))
    cmap   = cm.get_cmap("YlOrRd")
    colors = [cmap(s) for s in strengths]
    sizes  = [20 + 200 * s for s in strengths]

    nx.draw_networkx_edges(base_graph, pos, ax=ax,
                           alpha=0.08, width=0.5, edge_color="grey")
    nx.draw_networkx_nodes(base_graph, pos, ax=ax,
                           node_color=colors, node_size=sizes,
                           edgecolors="none")

    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=0, vmax=max_s))
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="Causal Out-Strength (normalised)")
    ax.set_title("Causal Influence Network (node colour = out-strength)")
    ax.axis("off")

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 6. Centrality sweep: Δvar vs shock strength
# ---------------------------------------------------------------------------

def plot_centrality_sweep(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "centrality_sweep.png",
) -> str:
    """Δvar vs shock strength, separate lines for hub vs random targeting.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: shock_strength, target_type, delta (or delta_variance).
    """
    delta_col = "delta" if "delta" in df.columns else "delta_variance"

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (ttype, sub) in enumerate(df.groupby("target_type")):
        grouped = sub.groupby("shock_strength")[delta_col].agg(["mean", "sem"])
        ax.errorbar(
            grouped.index, grouped["mean"],
            yerr=grouped["sem"],
            marker="^" if ttype == "hub" else "o",
            label=f"Target: {ttype}",
            color=_COLORS[i], capsize=3, linewidth=1.8,
        )

    ax.axhline(0, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Shock Strength")
    ax.set_ylabel("Δ Opinion Variance (treat − control)")
    ax.set_title("Centrality × Shock Strength Sweep\n(hub vs random targeting)")
    ax.legend(frameon=False)

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 7. Geometry comparison
# ---------------------------------------------------------------------------

def plot_geometry_comparison(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "geometry_comparison.png",
) -> str:
    """Box-plot comparison of polarization and variance across geometries.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: geometry, polarization (and optionally variance).
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    metrics = [
        ("polarization", "Polarization Index"),
        ("variance",     "Opinion Variance"),
    ]

    for ax, (col, label) in zip(axes, metrics):
        if col not in df.columns:
            ax.set_visible(False)
            continue
        groups = [sub[col].values for _, sub in df.groupby("geometry")]
        labels = [str(g) for g, _ in df.groupby("geometry")]
        bp = ax.boxplot(groups, patch_artist=True, labels=labels)
        for patch, color in zip(bp["boxes"], _COLORS):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax.set_ylabel(label)
        ax.set_title(f"{label} by Geometry")

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 8. Oversight regime phase transitions
# ---------------------------------------------------------------------------

def plot_oversight_phase(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "oversight_phase.png",
) -> str:
    """Bar charts of CB and variance across oversight regimes.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: regime, cascade_breadth, variance.
    """
    regime_order = ["none", "voluntary", "mandatory", "prohibitive"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for ax, (col, label) in zip(
        axes,
        [("cascade_breadth", "Cascade Breadth"), ("variance", "Opinion Variance")]
    ):
        if col not in df.columns:
            ax.set_visible(False)
            continue
        means = df.groupby("regime")[col].mean().reindex(regime_order).dropna()
        sems  = df.groupby("regime")[col].sem().reindex(regime_order).dropna()
        ax.bar(
            range(len(means)), means.values,
            yerr=sems.values, color=_COLORS[:len(means)],
            alpha=0.8, capsize=4,
        )
        ax.set_xticks(range(len(means)))
        ax.set_xticklabels(means.index, rotation=15)
        ax.set_ylabel(label)
        ax.set_title(f"{label} by Oversight Regime")

    return _save(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# 9. Pre/post variance shift (media amplification)
# ---------------------------------------------------------------------------

def plot_variance_shift(
    df         : pd.DataFrame,
    output_dir : str,
    filename   : str = "variance_shift.png",
) -> str:
    """Pre/post variance shift by media condition and lag.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: lag, enable_media, delta_variance.
    """
    if "delta_variance" not in df.columns:
        return ""

    fig, ax = plt.subplots(figsize=(7, 4))
    media_col = "enable_media" if "enable_media" in df.columns else None

    if media_col and df[media_col].nunique() > 1:
        for i, (media, sub) in enumerate(df.groupby(media_col)):
            grouped = sub.groupby("lag")["delta_variance"].agg(["mean", "sem"])
            label   = "Media ON" if media else "Media OFF"
            ax.errorbar(
                grouped.index, grouped["mean"],
                yerr=grouped["sem"],
                marker="D", label=label,
                color=_COLORS[i], capsize=3, linewidth=1.8,
            )
    else:
        grouped = df.groupby("lag")["delta_variance"].agg(["mean", "sem"])
        ax.errorbar(
            grouped.index, grouped["mean"],
            yerr=grouped["sem"],
            marker="D", color=_COLORS[0], capsize=3, linewidth=1.8,
        )

    ax.axhline(0, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Enforcement Lag (ticks)")
    ax.set_ylabel("Δ Variance (post − pre)")
    ax.set_title("Pre/Post Variance Shift by Media Condition")
    ax.legend(frameon=False)

    return _save(fig, os.path.join(output_dir, filename))
