"""
policyswarm.analysis
====================
Statistical analysis functions for the experiment runner outputs.

All analysis operates on pandas DataFrames produced by the experiment modules.
The core statistical design is the paired within-seed t-test (Iteration 10):
control and treatment runs share the same initial seed, so variance from
initial conditions is eliminated, isolating the treatment effect.
"""

from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.stats import ttest_rel, ttest_1samp


# ---------------------------------------------------------------------------
# Paired t-test
# ---------------------------------------------------------------------------

def paired_ttest(
    control_vals  : np.ndarray,
    treatment_vals: np.ndarray,
) -> Tuple[float, float, float]:
    """Paired one-sample t-test between control and treatment values.

    Parameters
    ----------
    control_vals : np.ndarray, shape (n_seeds,)
        Metric values from the control condition.
    treatment_vals : np.ndarray, shape (n_seeds,)
        Metric values from the matched treatment condition.

    Returns
    -------
    t_stat : float
    p_value : float
    effect : float
        mean(treatment) - mean(control)
    """
    t, p = ttest_rel(control_vals, treatment_vals)
    effect = float(np.mean(treatment_vals) - np.mean(control_vals))
    return float(t), float(p), effect


# ---------------------------------------------------------------------------
# Group summary
# ---------------------------------------------------------------------------

def group_summary(
    df          : pd.DataFrame,
    groupby_cols: List[str],
    value_cols  : Optional[List[str]] = None,
) -> pd.DataFrame:
    """Compute grouped mean, std, and n for numeric columns.

    Parameters
    ----------
    df : pd.DataFrame
    groupby_cols : list of str
        Columns to group by (e.g., ["geometry", "lag"]).
    value_cols : list of str, optional
        Columns to aggregate. If None, uses all numeric columns not in
        groupby_cols.

    Returns
    -------
    pd.DataFrame with columns:
        <groupby_cols> | <col>_mean | <col>_std | n
    """
    if value_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols   = [c for c in numeric_cols if c not in groupby_cols]

    agg_fns = {col: ["mean", "std"] for col in value_cols}
    agg_fns["seed"] = "count" if "seed" in df.columns else None

    grouped = df.groupby(groupby_cols)[value_cols].agg(["mean", "std"])
    grouped.columns = [f"{col}_{fn}" for col, fn in grouped.columns]
    grouped["n"] = df.groupby(groupby_cols).size()
    return grouped.reset_index()


# ---------------------------------------------------------------------------
# Stat-test table
# ---------------------------------------------------------------------------

def stat_test_table(
    df            : pd.DataFrame,
    groupby_cols  : List[str],
    control_col   : str,
    treatment_col : str,
    label         : str = "effect",
) -> pd.DataFrame:
    """Run paired t-tests for each group in a long-format DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain groupby_cols, 'seed', control_col, treatment_col.
    groupby_cols : list of str
    control_col : str
        Column holding control condition values.
    treatment_col : str
        Column holding treatment condition values.
    label : str
        Name for the effect column in the output. Default "effect".

    Returns
    -------
    pd.DataFrame with columns:
        <groupby_cols> | t_stat | p_value | <label> | significant
    """
    rows = []
    for keys, sub in df.groupby(groupby_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        t, p, eff = paired_ttest(
            sub[control_col].values,
            sub[treatment_col].values,
        )
        row = dict(zip(groupby_cols, keys))
        row["t_stat"]     = t
        row["p_value"]    = p
        row[label]        = eff
        row["significant"]= p < 0.05
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Executive summary generator
# ---------------------------------------------------------------------------

def executive_summary(
    stats_df  : pd.DataFrame,
    experiment : str = "",
    metric_col : str = "effect",
    p_col      : str = "p_value",
) -> str:
    """Format a human-readable executive summary from a stats DataFrame.

    Parameters
    ----------
    stats_df : pd.DataFrame
        Output of stat_test_table().
    experiment : str
        Experiment name for the header. Default "".
    metric_col : str
        Column holding effect sizes. Default "effect".
    p_col : str
        Column holding p-values. Default "p_value".

    Returns
    -------
    str
        Multi-line summary suitable for stdout or logging.
    """
    lines = [f"\n{'='*60}"]
    if experiment:
        lines.append(f"EXPERIMENT: {experiment}")
    lines.append(f"{'='*60}")

    for _, row in stats_df.iterrows():
        # Build condition string from non-metric columns
        cond_parts = []
        for col in stats_df.columns:
            if col in (metric_col, p_col, "t_stat", "significant"):
                continue
            cond_parts.append(f"{col}={row[col]}")
        cond = " | ".join(cond_parts)

        sig_marker = "**" if row.get("significant", False) else "  "
        eff_val    = row.get(metric_col, float("nan"))
        p_val      = row.get(p_col, float("nan"))
        lines.append(
            f"  {sig_marker} {cond:<40} Δ={eff_val:+.5f}  p={p_val:.4f}"
        )

    lines.append(f"{'='*60}")
    lines.append("** = significant at α=0.05")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cohen's d equivalent for unpaired comparisons
# ---------------------------------------------------------------------------

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cohen's d effect size for two independent samples.

    Parameters
    ----------
    a, b : np.ndarray

    Returns
    -------
    float
    """
    pooled_std = np.sqrt((np.std(a, ddof=1)**2 + np.std(b, ddof=1)**2) / 2)
    if pooled_std < 1e-12:
        return 0.0
    return float((np.mean(b) - np.mean(a)) / pooled_std)
