"""
policyswarm.facade
==================
``PolicySwarm``: the high-level entry point for running experiments from
Python.

    from policyswarm import PolicySwarm
    ps = PolicySwarm(output_dir="my_run", seeds=[0, 1, 2])
    ps.run_experiment("lag", lags=[0, 20])
    ps.run_all()
"""

from __future__ import annotations

import os
import traceback
from typing import Any, Dict, List, Optional

from .config import Policy, RunSpec, SimConfig
from .experiments.events import emit_event
from .extraction import DEFAULT_POLICY_TEXT, describe_extraction
from .registry import EXPERIMENTS, experiments_from_spec, get_experiment


class PolicySwarm:
    """High-level facade for running PolicySwarm experiments.

    Parameters
    ----------
    output_dir : str
        Root directory for all experiment outputs. Default 'policyswarm_output'.
    seeds : list of int, optional
        Monte Carlo seeds shared across all experiments. Default list(range(30)).
    policy_text : str, optional
        Raw policy text for the keyword extraction path.
    policy : Policy, optional
        Pre-built policy (LLM or embedding extraction). Overrides ``policy_text``.
    sim_config : SimConfig, optional
        Simulation mechanics shared by all experiments.
    """

    DEFAULT_POLICY_TEXT = DEFAULT_POLICY_TEXT

    def __init__(
        self,
        output_dir  : str                 = "policyswarm_output",
        seeds       : Optional[List[int]] = None,
        policy_text : Optional[str]       = None,
        policy      : Optional[Policy]    = None,
        sim_config  : Optional[SimConfig] = None,
    ):
        self.output_dir  = output_dir
        self.seeds       = seeds or list(range(30))
        self.policy_text = policy_text or DEFAULT_POLICY_TEXT
        self.policy      = policy
        self.sim_config  = sim_config
        os.makedirs(output_dir, exist_ok=True)

    def run_experiment(self, name: str, **kwargs: Any) -> dict:
        """Run a single named experiment and return its report dict.

        Extra keyword arguments are forwarded to the experiment constructor
        as Python objects (e.g. ``lags=[0, 20]``, ``geometries=[Geometry.COSINE]``).
        """
        cls = get_experiment(name)
        kwargs.setdefault("policy_text", self.policy_text)
        kwargs.setdefault("policy", self.policy)
        kwargs.setdefault("sim_config", self.sim_config)
        exp = cls(
            output_dir = os.path.join(self.output_dir, name),
            seeds      = self.seeds,
            **kwargs,
        )
        return exp.report()

    def run_all(self, experiments: Optional[List[str]] = None) -> Dict[str, dict]:
        """Run all (or a subset of) experiments sequentially.

        A failing experiment is reported and recorded as ``{"error": ...}``;
        the remaining experiments still run.
        """
        return _run_each(
            (name, lambda name=name: self.run_experiment(name))
            for name in (experiments or list(EXPERIMENTS))
        )

    @staticmethod
    def run_spec(spec: RunSpec, policy: Optional[Policy] = None) -> Dict[str, dict]:
        """Run a validated ``RunSpec`` (the CLI ``--spec`` / dashboard path)."""
        os.makedirs(spec.output_dir, exist_ok=True)
        experiments = experiments_from_spec(spec, policy=policy)
        return _run_each((exp.name, exp.report) for exp in experiments)

    @staticmethod
    def describe_policy(text: str) -> None:
        """Print the KG extraction summary for a policy text."""
        print(describe_extraction(text))

    @staticmethod
    def tier_status() -> dict:
        """Report which extraction tiers are available given installed packages."""
        from . import _TIER1_AVAILABLE, _TIER2_AVAILABLE
        return {
            "tier0_keyword"  : True,
            "tier1_llm"      : _TIER1_AVAILABLE,
            "tier2_embedding": _TIER2_AVAILABLE,
        }


def _run_each(named_runs) -> Dict[str, dict]:
    """Run ``(name, callable)`` pairs in order, isolating failures."""
    reports: Dict[str, dict] = {}
    for name, run in named_runs:
        print(f"\n{'='*60}\nRunning experiment: {name}\n{'='*60}")
        try:
            reports[name] = run()
        except Exception as exc:
            print(f"[ERROR] Experiment '{name}' failed: {exc}")
            traceback.print_exc()
            emit_event(type="error", experiment=name, message=str(exc))
            reports[name] = {"error": str(exc)}
    return reports
