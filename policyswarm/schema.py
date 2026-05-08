"""
policyswarm.schema
==================
Runtime schema validation for experiment output DataFrames.

Used in run_all.py before LaTeX generation to catch column mismatches
early with a clear error message rather than a cryptic KeyError.

Both schemas validate the *_stats_*.csv files (aggregated outputs from
analyse()), not the raw *_results_*.csv files (per-seed rows).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
import pandas as pd

SCHEMA_VERSION = "1.0.0"


@dataclass
class ResultSchema:
    name: str
    required_columns: List[str]

    def validate(self, df: pd.DataFrame) -> None:
        """Raise ValueError with a clear message if required columns are absent."""
        missing = [c for c in self.required_columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"[Schema: {self.name}] Missing columns: {missing}\n"
                f"Found: {sorted(df.columns.tolist())}\n"
                f"Hint: ensure you are reading *_stats_*.csv, not *_results_*.csv."
            )

    def enforce(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and stamp schema version. Returns a copy."""
        self.validate(df)
        df = df.copy()
        df["schema_version"] = SCHEMA_VERSION
        return df


# ---------------------------------------------------------------------------
# Geometry experiment — expects group_summary() output columns
# ---------------------------------------------------------------------------
# group_summary(df, ["geometry", "alpha"], ["variance", "polarization",
#                    "bifurcation_index", "phase_t"])
# produces: geometry, alpha, variance_mean, variance_std, variance_ci_low,
#           variance_ci_high, polarization_mean, ..., n

GEOMETRY_RESULTS_SCHEMA = ResultSchema(
    name="geometry_stats",
    required_columns=[
        "geometry",
        "alpha",
        "variance_mean",
        "variance_ci_low",
        "variance_ci_high",
        "polarization_mean",
        "polarization_ci_low",
        "polarization_ci_high",
        "bifurcation_index_mean",
        "bifurcation_index_ci_low",
        "bifurcation_index_ci_high",
        "phase_t_mean",
        "phase_t_ci_low",
        "phase_t_ci_high",
        "n",
    ],
)

# ---------------------------------------------------------------------------
# All other experiments — expects stat_test_table() output columns
# ---------------------------------------------------------------------------
STATS_SCHEMA = ResultSchema(
    name="stats",
    required_columns=[
        "t_stat",
        "p_value",
        "effect",
        "effect_ci_low",
        "effect_ci_high",
        "significant",
    ],
)