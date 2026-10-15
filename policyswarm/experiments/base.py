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
report() and run() emit progress events in the format defined in
``events.py``, consumed by the front ends that wrap this process (tui/, gui/).

Shared building blocks
----------------------
``run_paired`` runs one control / treatment pair, the unit every paired
experiment is built from. ``BASELINE_GOVERNANCE`` holds the governance
parameters the lag, media, counterfactual and centrality experiments share.
"""

from __future__ import annotations

import copy
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Dict, List, Optional, Tuple

import pandas as pd

from ..config import Geometry, GovernanceConfig, Policy, SimConfig
from ..dynamics import Simulation
from ..extraction import DEFAULT_POLICY_TEXT, policy_from_text
from ..metrics import compute_all_metrics
from ..shocks import ShockSchedule
from .events import emit_event
from .params import ParamSpec

log = logging.getLogger("policyswarm")

#: Governance parameters shared by the experiments that do not sweep the regime.
BASELINE_GOVERNANCE = {"deployment_rate_cap": 0.5, "penalty_severity": 0.5}


def run_paired(
    sim_config : SimConfig,
    gov_config : GovernanceConfig,
    policy     : Policy,
    shocks     : ShockSchedule,
    seed       : int,
    geometry   : Geometry = Geometry.EUCLIDEAN,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Run one paired control / treatment simulation.

    Both runs share the seed (network, initial opinions) and the shock
    schedule; only ``apply_shocks`` differs, so the difference between the
    two metric dicts is the within-seed effect of the shocks.

    Returns
    -------
    (control_metrics, treatment_metrics)
        Each as returned by ``metrics.compute_all_metrics``.
    """
    control   = _simulate(sim_config, gov_config, policy, shocks, seed, geometry, False)
    treatment = _simulate(sim_config, gov_config, policy, shocks, seed, geometry, True)
    return control, treatment


def _simulate(sim_config, gov_config, policy, shocks, seed, geometry, apply_shocks):
    sim = Simulation(
        sim_config, gov_config, policy, shocks,
        apply_shocks=apply_shocks, seed=seed, geometry=geometry,
    )
    sim.run()
    return compute_all_metrics(sim)


class BaseExperiment(ABC):
    """Abstract experiment base class.

    Parameters
    ----------
    output_dir : str
        Directory to write CSV, JSON, and PNG outputs. Created if absent.
    seeds : list of int
        Random seeds for Monte Carlo runs. Default list(range(5)).
    policy_text : str
        Policy document to ingest with the keyword extractor. Ignored when
        ``policy`` is given.
    policy : Policy, optional
        Pre-built policy object (e.g. from the LLM or embedding extractor).
        Takes precedence over ``policy_text``.
    sim_config : SimConfig, optional
        Simulation mechanics. Default ``SimConfig()``.

    Class attributes
    ----------------
    name : str
        Registry key and output sub-directory (e.g. "lag").
    title : str
        Human-readable title.
    PARAMS : tuple of ParamSpec
        The sweepable constructor arguments, beyond the common ones above.
    """

    name   : ClassVar[str] = ""
    title  : ClassVar[str] = ""
    PARAMS : ClassVar[Tuple[ParamSpec, ...]] = ()

    def __init__(
        self,
        output_dir  : str,
        seeds       : Optional[List[int]] = None,
        policy_text : str                 = DEFAULT_POLICY_TEXT,
        policy      : Optional[Policy]    = None,
        sim_config  : Optional[SimConfig] = None,
    ):
        self.output_dir  = output_dir
        self.seeds       = seeds if seeds is not None else list(range(5))
        self.policy_text = policy_text
        self.policy      = policy
        self.sim_config  = sim_config or SimConfig()
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
    # Policy
    # ------------------------------------------------------------------

    def _policy(self) -> Policy:
        """A fresh Policy for this experiment.

        Returns a copy of the injected ``policy`` if one was given, otherwise
        extracts one from ``policy_text``. Always a new object, so callers
        may set ``lag`` on it freely.
        """
        if self.policy is not None:
            return copy.copy(self.policy)
        return policy_from_text(self.policy_text)

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
        """Emit a structured progress event (see ``events.emit_event``).

        Callers always include "type" (e.g. "start", "seed_complete",
        "complete") and "experiment" (self.__class__.__name__).
        """
        emit_event(**fields)

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
