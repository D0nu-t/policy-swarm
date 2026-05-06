"""
policyswarm.experiments.base
============================
Abstract base class for all experiments.

Every experiment follows the same contract:
  1. Receive a canonical set of parameters via __init__
  2. Expose a .run() method that returns a pd.DataFrame of raw results
  3. Expose a .analyse() method that returns a stats DataFrame
  4. Expose a .plot() method that writes figures and returns file paths
  5. Expose a .report() convenience method that runs all three steps
"""

from __future__ import annotations

import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List

import pandas as pd

log = logging.getLogger("policyswarm")


class BaseExperiment(ABC):
    """Abstract experiment base class.

    Parameters
    ----------
    output_dir : str
        Directory to write CSV, JSON, and PNG outputs. Created if absent.
    seeds : list of int
        Random seeds for Monte Carlo runs. Default list(range(5)).
    """

    def __init__(
        self,
        output_dir : str,
        seeds      : Optional[List[int]] = None,
    ):
        self.output_dir = output_dir
        self.seeds      = seeds if seeds is not None else list(range(5))
        os.makedirs(output_dir, exist_ok=True)

        self._results_df : Optional[pd.DataFrame] = None
        self._stats_df   : Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self) -> pd.DataFrame:
        """Execute the experiment across all seeds and conditions.

        Returns
        -------
        pd.DataFrame
            One row per (seed × condition) combination.
        """

    @abstractmethod
    def analyse(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute statistical summaries over the raw results DataFrame.

        Returns
        -------
        pd.DataFrame
            Grouped statistics / test results.
        """

    @abstractmethod
    def plot(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> List[str]:
        """Write all figures for this experiment.

        Returns
        -------
        list of str
            File paths of generated figures.
        """

    # ------------------------------------------------------------------
    # Convenience: full pipeline
    # ------------------------------------------------------------------

    def report(self) -> dict:
        """Run, analyse, plot, save, and summarise the experiment.

        Returns
        -------
        dict with keys:
            results_df, stats_df, figure_paths, csv_path, stats_csv_path
        """
        log.info(f"[{self.__class__.__name__}] Running experiment ...")
        df = self.run()
        self._results_df = df

        log.info(f"[{self.__class__.__name__}] Analysing results ...")
        stats_df = self.analyse(df)
        self._stats_df = stats_df

        log.info(f"[{self.__class__.__name__}] Generating plots ...")
        figure_paths = self.plot(df, stats_df)

        # Persist raw results and stats
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path   = os.path.join(
            self.output_dir,
            f"{self.__class__.__name__}_results_{ts}.csv",
        )
        stats_path = os.path.join(
            self.output_dir,
            f"{self.__class__.__name__}_stats_{ts}.csv",
        )
        df.to_csv(csv_path, index=False)
        stats_df.to_csv(stats_path, index=False)

        # Print executive summary to stdout
        print(stats_df.to_string(index=False))
        print(f"\nCSV  → {csv_path}")
        print(f"Stats → {stats_path}")
        print(f"Plots → {figure_paths}")

        return {
            "results_df"      : df,
            "stats_df"        : stats_df,
            "figure_paths"    : figure_paths,
            "csv_path"        : csv_path,
            "stats_csv_path"  : stats_path,
        }
