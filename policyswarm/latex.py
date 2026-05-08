"""
policyswarm.latex
=================
LaTeX table generation from experiment output DataFrames.

All functions consume the DataFrames produced by ``analysis.py`` and return
LaTeX strings ready for ``\\input{}`` inclusion. Tables use the ``booktabs``
package (``\\toprule``, ``\\midrule``, ``\\bottomrule``) and are formatted
for single-column arXiv submissions.

Two primary functions
---------------------
stat_table_to_latex(df, caption, label)
    Converts ``stat_test_table()`` output (one row per condition) into a
    results table with effect sizes, 95% CIs, and p-values.
    Used for: lag, oversight, media, counterfactual experiments.

summary_table_to_latex(df, caption, label)
    Converts ``group_summary()`` output (aggregated metrics with CIs)
    into a multi-column comparison table.
    Used for: geometry experiment.

Usage
-----
    from policyswarm.latex import stat_table_to_latex, summary_table_to_latex

    # After running an experiment:
    latex = stat_table_to_latex(
        stats_df,
        caption="Effect of enforcement lag on opinion variance (S=20, paired t-test).",
        label="tab:lag",
    )
    with open("results/lag/lag_table.tex", "w") as f:
        f.write(latex)

    # Then in your paper:
    # \\input{results/lag/lag_table.tex}

Required LaTeX preamble
-----------------------
    \\usepackage{booktabs}
    \\usepackage{siunitx}   % optional — for S-column alignment
    \\usepackage{multirow}  % optional — not currently used but useful for extensions

Column sources
--------------
stat_table_to_latex expects:
    groupby condition columns (e.g. lag, geometry) from stat_test_table()
    effect          — mean(treatment) - mean(control)
    effect_ci_low   — lower bound of 95% CI on paired differences
    effect_ci_high  — upper bound of 95% CI on paired differences
    p_value         — two-sided paired t-test p-value
    significant     — bool, p < 0.05

summary_table_to_latex expects:
    geometry, alpha — condition columns from group_summary()
    variance_mean, variance_ci_low, variance_ci_high
    polarization_mean, polarization_ci_low, polarization_ci_high
    bifurcation_index_mean, bifurcation_index_ci_low, bifurcation_index_ci_high
    phase_t_mean, phase_t_ci_low, phase_t_ci_high
    n
"""

from __future__ import annotations

from typing import Optional, List
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

# Columns that contain statistics — excluded from condition string construction
_STAT_EXCLUDE = {
    "t_stat", "p_value", "effect", "effect_ci_low", "effect_ci_high",
    "significant", "n", "schema_version",
}


def _fmt(val: float, precision: int = 4) -> str:
    """Format a float to fixed decimal places, preserving sign."""
    if np.isnan(val):
        return "---"
    return f"{val:.{precision}f}"


def _fmt_signed(val: float, precision: int = 4) -> str:
    """Format a float with explicit sign."""
    if np.isnan(val):
        return "---"
    return f"{val:+.{precision}f}"


def _fmt_ci(low: float, high: float, precision: int = 4) -> str:
    """Format a confidence interval as [low, high]."""
    if np.isnan(low) or np.isnan(high):
        return "[---, ---]"
    return f"[{low:.{precision}f}, {high:.{precision}f}]"


def _fmt_pval(p: float) -> str:
    """Format p-value: show 4 decimal places, use <0.0001 for very small values."""
    if np.isnan(p):
        return "---"
    if p < 0.0001:
        return "$<$0.0001"
    return f"{p:.4f}"


def _condition_string(row: pd.Series, columns: List[str]) -> str:
    """Build a readable condition label from groupby columns."""
    parts = []
    for col in columns:
        val = row[col]
        # Format floats cleanly (e.g. alpha=0.05, not alpha=0.050000)
        if isinstance(val, float):
            parts.append(f"{col}={val:g}")
        else:
            parts.append(f"{col}={val}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# stat_table_to_latex
# ---------------------------------------------------------------------------

def stat_table_to_latex(
    df        : pd.DataFrame,
    caption   : str,
    label     : str,
    precision : int            = 4,
    note      : Optional[str] = None,
) -> str:
    """Convert a stat_test_table() DataFrame to a LaTeX table string.

    Each row in ``df`` becomes one table row, showing the condition,
    effect size, 95% CI, and p-value. Significant rows (p < 0.05) are
    annotated with a dagger (†).

    Parameters
    ----------
    df : pd.DataFrame
        Output of ``analysis.stat_test_table()``. Required columns:
        effect, effect_ci_low, effect_ci_high, p_value, significant.
    caption : str
        LaTeX table caption string.
    label : str
        LaTeX \\label{} string (e.g. "tab:lag").
    precision : int
        Decimal places for effect and CI values. Default 4.
    note : str, optional
        Table note appended below the table in a minipage.
        E.g. "† significant at α = 0.05."

    Returns
    -------
    str
        Complete LaTeX table environment, ready for \\input{}.

    Example output
    --------------
    \\begin{table}[t]
      \\centering
      \\caption{...}
      \\label{...}
      \\begin{tabular}{lccc}
        \\toprule
        Condition & Effect & 95\\% CI & $p$-value \\\\
        \\midrule
        lag=0     & -0.0019 & [-0.0039, 0.0001] & 0.0563 \\\\
        lag=40    & -0.0039† & [-0.0056, -0.0021] & 0.0106 \\\\
        \\bottomrule
      \\end{tabular}
    \\end{table}
    """
    # Identify condition columns (everything that is not a stat column)
    cond_cols = [c for c in df.columns if c not in _STAT_EXCLUDE]

    lines = []
    lines.append("\\begin{table}[t]")
    lines.append("  \\centering")
    lines.append(f"  \\caption{{{caption}}}")
    lines.append(f"  \\label{{{label}}}")
    lines.append("  \\begin{tabular}{lccc}")
    lines.append("    \\toprule")
    lines.append(
        "    Condition & Effect $\\Delta$ & 95\\% CI & $p$-value \\\\"
    )
    lines.append("    \\midrule")

    for _, row in df.iterrows():
        cond   = _condition_string(row, cond_cols)
        effect = _fmt_signed(row["effect"], precision)
        ci     = _fmt_ci(row["effect_ci_low"], row["effect_ci_high"], precision)
        pval   = _fmt_pval(row["p_value"])
        sig    = "\\dag{}" if row.get("significant", False) else ""

        lines.append(
            f"    {cond} & {effect}{sig} & {ci} & {pval} \\\\"
        )

    lines.append("    \\bottomrule")
    lines.append("  \\end{tabular}")

    # Optional table note
    _note = note or "\\dag{} significant at $\\alpha = 0.05$ (paired $t$-test, two-sided)."
    lines.append("  \\begin{minipage}{\\linewidth}")
    lines.append("    \\vspace{4pt}")
    lines.append(f"    \\footnotesize {_note}")
    lines.append("  \\end{minipage}")

    lines.append("\\end{table}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# summary_table_to_latex
# ---------------------------------------------------------------------------

def summary_table_to_latex(
    df        : pd.DataFrame,
    caption   : str,
    label     : str,
    precision : int = 3,
    note      : Optional[str] = None,
) -> str:
    """Convert a group_summary() DataFrame to a multi-metric comparison table.

    Formats four metrics — Variance, Polarisation, Bifurcation Index, and
    Phase Transition Tick — as mean [ci_low, ci_high] per condition row.

    Parameters
    ----------
    df : pd.DataFrame
        Output of ``analysis.group_summary()`` for the geometry experiment.
        Required columns: geometry, alpha, variance_mean, variance_ci_low,
        variance_ci_high, polarization_mean, polarization_ci_low,
        polarization_ci_high, bifurcation_index_mean,
        bifurcation_index_ci_low, bifurcation_index_ci_high, phase_t_mean,
        phase_t_ci_low, phase_t_ci_high, n.
    caption : str
        LaTeX table caption.
    label : str
        LaTeX \\label{} string.
    precision : int
        Decimal places. Default 3.
    note : str, optional
        Table note. Defaults to seed count note.

    Returns
    -------
    str
        Complete LaTeX table environment.

    Example output
    --------------
    \\begin{table}[t]
      ...
      Euclidean, 0.00 & 0.050 [0.047, 0.053] & 0.531 [0.510, 0.552] & ...
      ...
    \\end{table}
    """
    # Validate required columns exist
    required = [
        "geometry", "alpha",
        "variance_mean", "variance_ci_low", "variance_ci_high",
        "polarization_mean", "polarization_ci_low", "polarization_ci_high",
        "bifurcation_index_mean", "bifurcation_index_ci_low", "bifurcation_index_ci_high",
        "phase_t_mean", "phase_t_ci_low", "phase_t_ci_high",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"summary_table_to_latex: missing columns {missing}.\n"
            f"Ensure you are passing group_summary() output, not raw results."
        )

    def _cell(mean_col, lo_col, hi_col, row, p=precision) -> str:
        mean = row[mean_col]
        lo   = row[lo_col]
        hi   = row[hi_col]
        if any(np.isnan(v) for v in [mean, lo, hi]):
            return "---"
        return f"{mean:.{p}f} [{lo:.{p}f}, {hi:.{p}f}]"

    lines = []
    lines.append("\\begin{table}[t]")
    lines.append("  \\centering")
    lines.append(f"  \\caption{{{caption}}}")
    lines.append(f"  \\label{{{label}}}")
    # 5 columns: condition, OV, PI, BI, PTT
    lines.append("  \\begin{tabular}{lcccc}")
    lines.append("    \\toprule")
    lines.append(
        "    Condition & Variance (OV) & Polarisation (PI) "
        "& Bif.\\ Index (BI) & Phase Tick (PTT) \\\\"
    )
    lines.append(
        "    & mean [95\\% CI] & mean [95\\% CI] "
        "& mean [95\\% CI] & mean [95\\% CI] \\\\"
    )
    lines.append("    \\midrule")

    prev_geom = None
    for _, row in df.iterrows():
        geom = str(row["geometry"]).capitalize()
        alph = float(row["alpha"])

        # Insert a thin rule between geometry groups for readability
        if prev_geom is not None and geom != prev_geom:
            lines.append("    \\midrule")
        prev_geom = geom

        cond = f"{geom}, $\\mu$={alph:g}"
        ov   = _cell("variance_mean",          "variance_ci_low",          "variance_ci_high",          row)
        pi   = _cell("polarization_mean",       "polarization_ci_low",      "polarization_ci_high",      row)
        bi   = _cell("bifurcation_index_mean",  "bifurcation_index_ci_low", "bifurcation_index_ci_high", row, p=2)
        ptt  = _cell("phase_t_mean",            "phase_t_ci_low",           "phase_t_ci_high",           row, p=1)

        lines.append(f"    {cond} & {ov} & {pi} & {bi} & {ptt} \\\\")

    lines.append("    \\bottomrule")
    lines.append("  \\end{tabular}")

    # Table note
    n_val = int(df["n"].iloc[0]) if "n" in df.columns else "?"
    _note = note or (
        f"Results averaged over $S={n_val}$ seeds per cell. "
        "OV = opinion variance; PI = polarisation index (mean pairwise $L_2$); "
        "BI = bifurcation index (KDE peak count, $h=0.08$); "
        "PTT = phase transition tick."
    )
    lines.append("  \\begin{minipage}{\\linewidth}")
    lines.append("    \\vspace{4pt}")
    lines.append(f"    \\footnotesize {_note}")
    lines.append("  \\end{minipage}")

    lines.append("\\end{table}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: write tables directly to file
# ---------------------------------------------------------------------------

def write_stat_table(
    df         : pd.DataFrame,
    path       : str,
    caption    : str,
    label      : str,
    precision  : int = 4,
    note       : Optional[str] = None,
) -> None:
    """Generate and write a stat table to ``path``.

    Parameters
    ----------
    df : pd.DataFrame
        Output of stat_test_table().
    path : str
        Destination file path, e.g. "results/lag/lag_table.tex".
    caption, label, precision, note
        Forwarded to stat_table_to_latex().
    """
    latex = stat_table_to_latex(df, caption, label, precision, note)
    with open(path, "w", encoding="utf-8") as f:
        f.write(latex)


def write_summary_table(
    df        : pd.DataFrame,
    path      : str,
    caption   : str,
    label     : str,
    precision : int = 3,
    note      : Optional[str] = None,
) -> None:
    """Generate and write a summary table to ``path``.

    Parameters
    ----------
    df : pd.DataFrame
        Output of group_summary().
    path : str
        Destination file path, e.g. "results/geometry/geometry_table.tex".
    caption, label, precision, note
        Forwarded to summary_table_to_latex().
    """
    latex = summary_table_to_latex(df, caption, label, precision, note)
    with open(path, "w", encoding="utf-8") as f:
        f.write(latex)


# ---------------------------------------------------------------------------
# Format a single CI cell — exposed for use in custom table builders
# ---------------------------------------------------------------------------

def format_ci(
    mean      : float,
    low       : float,
    high      : float,
    precision : int = 4,
) -> str:
    """Return a formatted ``mean [low, high]`` string.

    Parameters
    ----------
    mean, low, high : float
    precision : int

    Returns
    -------
    str
        e.g. "-0.0127 [-0.0158, -0.0096]"
    """
    if any(np.isnan(v) for v in [mean, low, high]):
        return "---"
    return f"{mean:.{precision}f} [{low:.{precision}f}, {high:.{precision}f}]"