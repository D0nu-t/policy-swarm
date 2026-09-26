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

Structured progress events
---------------------------
In addition to the human-readable prose this class and its subclasses print,
report() and run() also emit single-line JSON progress events prefixed with
the sentinel token "##EVENT## ". These are consumed by tooling that wraps
this process (e.g. tui/), which can safely grep for the prefix without
risking a false match against the prose output or the stats_df.to_string()
dump below. See _emit().
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
    # Progress sizing — override in subclasses with a condition grid
    # ------------------------------------------------------------------

    def total_units(self) -> int:
        """Total number of seed-iterations run(), used to size progress bars.

        Default assumes a single condition (no grid): len(seeds). Experiments
        that sweep a condition grid (lag values, geometries, regimes, ...)
        should override this to len(grid) * len(seeds) so consumers of the
        event stream can render an accurate percentage rather than just a
        running count.
        """
        return len(self.seeds)

    # ------------------------------------------------------------------
    # Geometry-aware bounded-confidence thresholds
    # ------------------------------------------------------------------

    def _geometry_epsilons(self, sim_config, geometries, mode: str = "matched") -> dict:
        """Epsilon to use for each geometry, keyed by Geometry.value.

        mode="matched" (default): Euclidean keeps sim_config.epsilon and every
            other geometry gets the epsilon admitting the same fraction of
            network-neighbour pairs at initialisation (geometry.matched_epsilons).
        mode="raw": sim_config.epsilon for every geometry. A raw epsilon means
            different coverage under each metric, so this confounds geometry
            with threshold; use only for sensitivity analysis.
        """
        from ..config import Geometry
        from ..geometry import matched_epsilons

        if mode == "raw":
            return {g.value: sim_config.epsilon for g in geometries}
        if mode != "matched":
            raise ValueError(f"Unknown epsilon mode: {mode!r}")

        eps, target = matched_epsilons(
            sim_config, geometries, reference_geometry=Geometry.EUCLIDEAN,
            seeds=self.seeds,
        )
        print(f"Coverage-matched epsilon (target neighbour pass fraction "
              f"{target:.3f}): " + ", ".join(f"{g}={e:.4f}" for g, e in eps.items()))
        return eps

    # ------------------------------------------------------------------
    # Structured progress events (consumed by tui/)
    # ------------------------------------------------------------------

    def _emit(self, **fields) -> None:
        """Emit a structured progress event as a single JSON line on stdout.

        Parameters
        ----------
        **fields
            Arbitrary JSON-serialisable key/value pairs. Callers always
            include "type" (e.g. "start", "seed_complete", "complete",
            "error") and "experiment" (self.__class__.__name__).

        Notes
        -----
        flush=True is required: when this process is spawned as a child
        (e.g. by the TUI via child_process.spawn), stdout is not a TTY, so
        CPython switches from line-buffered to fully block-buffered. Without
        an explicit flush, events queue up invisibly until the OS pipe
        buffer fills or the process exits, which defeats the purpose of a
        live progress stream.
        """
        print("##EVENT## " + json.dumps(fields), flush=True)

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
        name = self.__class__.__name__

        log.info(f"[{name}] Running experiment ...")
        self._emit(type="start", experiment=name, total=self.total_units())

        df = self.run()
        self._results_df = df

        log.info(f"[{name}] Analysing results ...")
        stats_df = self.analyse(df)
        self._stats_df = stats_df

        log.info(f"[{name}] Generating plots ...")
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

        self._emit(
            type="complete", experiment=name,
            figures=len(figure_paths), rows=len(df),
        )

        return {
            "results_df"      : df,
            "stats_df"        : stats_df,
            "figure_paths"    : figure_paths,
            "csv_path"        : csv_path,
            "stats_csv_path"  : stats_path,
        }
