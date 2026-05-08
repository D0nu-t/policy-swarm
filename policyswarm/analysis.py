"""
policyswarm.analysis
====================
Statistical analysis functions for the experiment runner outputs.

The core statistical design is the paired within-seed t-test: control and
treatment runs share the same initial seed, so variance from initial conditions
is eliminated, isolating the treatment effect.

All stat_test_table() outputs include 95% confidence intervals on the paired
effect estimate, formatted for direct inclusion in LaTeX tables via latex.py.
"""

from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.stats import ttest_rel, sem, t as t_dist


# ---------------------------------------------------------------------------
# Confidence interval helper
# ---------------------------------------------------------------------------

def confidence_interval(
    vals       : np.ndarray,
    confidence : float = 0.95,
) -> Tuple[float, float, float]:
    """Compute mean and symmetric confidence interval.

    Parameters
    ----------
    vals : np.ndarray
    confidence : float

    Returns
    -------
    (mean, ci_low, ci_high)
    """
    vals = np.array(vals)
    n    = len(vals)
    mean = float(np.mean(vals))

    if n < 2:
        return mean, mean, mean

    stderr = float(sem(vals))
    if np.isnan(stderr) or stderr == 0:
        return mean, mean, mean

    h = stderr * t_dist.ppf((1 + confidence) / 2.0, n - 1)
    return mean, mean - h, mean + h


# ---------------------------------------------------------------------------
# Paired t-test
# ---------------------------------------------------------------------------

def paired_ttest(
    control_vals  : np.ndarray,
    treatment_vals: np.ndarray,
) -> Tuple[float, float, float]:
    """Paired one-sample t-test between control and treatment values.

    Returns
    -------
    (t_stat, p_value, effect)
        effect = mean(treatment) - mean(control)
    """
    t_stat, p = ttest_rel(control_vals, treatment_vals)
    effect = float(np.mean(treatment_vals) - np.mean(control_vals))
    return float(t_stat), float(p), effect


# ---------------------------------------------------------------------------
# Group summary with CIs
# ---------------------------------------------------------------------------

def group_summary(
    df           : pd.DataFrame,
    groupby_cols : List[str],
    value_cols   : Optional[List[str]] = None,
) -> pd.DataFrame:
    """Compute grouped mean, std, 95% CI, and n for numeric columns.

    Parameters
    ----------
    df : pd.DataFrame
    groupby_cols : list of str
    value_cols : list of str, optional
        If None, uses all numeric columns not in groupby_cols.

    Returns
    -------
    pd.DataFrame
        Columns: <groupby_cols> | <col>_mean | <col>_std | <col>_ci_low |
                 <col>_ci_high | n
    """
    if value_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols   = [c for c in numeric_cols if c not in groupby_cols]

    rows = []
    for keys, sub in df.groupby(groupby_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(groupby_cols, keys))

        for col in value_cols:
            vals = sub[col].dropna().values
            mean_, ci_low, ci_high = confidence_interval(vals)
            row[f"{col}_mean"]    = mean_
            row[f"{col}_std"]     = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            row[f"{col}_ci_low"]  = ci_low
            row[f"{col}_ci_high"] = ci_high

        row["n"] = len(sub)
        rows.append(row)

    return pd.DataFrame(rows)


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
    """Run paired t-tests for each group and return a results table.

    Output columns: <groupby_cols> | t_stat | p_value | <label> |
                    effect_ci_low | effect_ci_high | significant
    """
    rows = []
    for keys, sub in df.groupby(groupby_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)

        ctrl = sub[control_col].values
        trt  = sub[treatment_col].values

        t_stat, p_val, effect = paired_ttest(ctrl, trt)

        diffs = trt - ctrl
        _, ci_low, ci_high = confidence_interval(diffs)

        row                  = dict(zip(groupby_cols, keys))
        row["t_stat"]        = t_stat
        row["p_value"]       = p_val
        row[label]           = effect
        row["effect_ci_low"] = ci_low
        row["effect_ci_high"]= ci_high
        row["significant"]   = p_val < 0.05

        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

_STAT_COLS = {"t_stat", "p_value", "significant", "effect",
              "effect_ci_low", "effect_ci_high"}


def executive_summary(
    stats_df   : pd.DataFrame,
    experiment : str = "",
    metric_col : str = "effect",
    p_col      : str = "p_value",
) -> str:
    """Format a human-readable executive summary."""
    lines = [f"\n{'='*60}"]
    if experiment:
        lines.append(f"EXPERIMENT: {experiment}")
    lines.append("=" * 60)

    for _, row in stats_df.iterrows():
        cond_cols = [c for c in stats_df.columns if c not in _STAT_COLS]
        cond      = " | ".join(f"{c}={row[c]}" for c in cond_cols)

        sig    = "**" if row.get("significant", False) else "  "
        eff    = row.get(metric_col, float("nan"))
        p      = row.get(p_col, float("nan"))
        ci_low = row.get("effect_ci_low", float("nan"))
        ci_hi  = row.get("effect_ci_high", float("nan"))

        lines.append(
            f"  {sig} {cond:<40} "
            f"Δ={eff:+.5f}  "
            f"95% CI [{ci_low:.5f}, {ci_hi:.5f}]  "
            f"p={p:.4f}"
        )

    lines.append("=" * 60)
    lines.append("** = significant at α=0.05")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cohen's d
# ---------------------------------------------------------------------------

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d effect size for two independent samples."""
    pooled_std = np.sqrt(
        (np.std(a, ddof=1) ** 2 + np.std(b, ddof=1) ** 2) / 2
    )
    if pooled_std < 1e-12:
        return 0.0
    return float((np.mean(b) - np.mean(a)) / pooled_std)