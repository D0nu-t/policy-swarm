from dataclasses import dataclass
from typing import List, Dict
import pandas as pd

SCHEMA_VERSION = "1.0.0"


@dataclass
class ResultSchema:
    name: str
    required_columns: List[str]

    def validate(self, df: pd.DataFrame):
        missing = [c for c in self.required_columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"[{self.name}] Missing columns: {missing}\n"
                f"Found: {list(df.columns)}"
            )

    def enforce(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce schema at write-time.
        Adds missing columns if derivable, otherwise errors.
        """
        self.validate(df)
        df = df.copy()
        df["schema_version"] = SCHEMA_VERSION
        return df
    
GEOMETRY_RESULTS_SCHEMA = ResultSchema(
    name="geometry_results",
    required_columns=[
        "geometry", "alpha",
        "variance_mean", "variance_ci_low", "variance_ci_high",
        "polarization_mean", "polarization_ci_low", "polarization_ci_high",
        "bifurcation_index_mean", "bifurcation_index_ci_low", "bifurcation_index_ci_high",
        "phase_t_mean", "phase_t_ci_low", "phase_t_ci_high",
        "n",
    ],
)

STATS_SCHEMA = ResultSchema(
    name="stats",
    required_columns=[
        "t_stat", "p_value", "effect",
        "effect_ci_low", "effect_ci_high",
        "significant",
    ],
)