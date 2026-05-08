"""
policyswarm
===========
A research-grade agent-based modelling framework for studying how AI
governance decisions propagate through synthetic social ecosystems.

Quick start
-----------
    from policyswarm import PolicySwarm
    ps = PolicySwarm(output_dir="my_run")
    ps.run_experiment("lag")   # Experiment 2: enforcement lag sensitivity
    ps.run_all()               # all six experiments

Module map
----------
policyswarm.config         — Configuration dataclasses and enumerations
policyswarm.extraction     — Policy-text ingestion and KG pipeline
policyswarm.network        — Social network topology builders
policyswarm.shocks         — Exogenous shock schedule generation
policyswarm.dynamics       — Core ABM simulation engine (Simulation)
policyswarm.metrics        — Outcome metric computations
policyswarm.analysis       — Statistical analysis utilities
policyswarm.visualization  — Publication-ready plot generation
policyswarm.experiments    — Individual experiment classes (Exp 1-6)
policyswarm.latex          — LaTeX table generation
policyswarm.schema         — Runtime schema validation
"""

from .config import (
    SimConfig, GovernanceConfig, Policy, ShockConfig,
    OverlapRegime, NetworkType, Geometry, ShockMode,
    REGIME_PARAMS,
)
from .extraction import (
    policy_from_text, policy_from_kg, extract_entities,
    extract_narrative_scores, build_kg, perceived_policy,
    describe_extraction,
)
from .network   import build_network, compute_influence, top_hub_indices
from .shocks    import generate_shocks, override_strength, summarise_schedule
from .dynamics  import Simulation
from .metrics   import (
    opinion_variance, polarization_index, bifurcation_index,
    cascade_breadth, phase_transition_tick, causal_centrality,
    delta_variance, effect_size, compute_all_metrics,
)
from .analysis  import (
    paired_ttest, group_summary, stat_test_table,
    executive_summary, cohens_d,
)
from .experiments import (
    OversightPhaseExperiment,
    EnforcementLagExperiment,
    MediaInteractionExperiment,
    CounterfactualShockExperiment,
    CentralitySweepExperiment,
    GeometryExperiment,
)

import os

__version__ = "1.0.0"
__author__  = "krishnasai-addala"

_EXPERIMENT_MAP = {
    "oversight"      : OversightPhaseExperiment,
    "lag"            : EnforcementLagExperiment,
    "media"          : MediaInteractionExperiment,
    "counterfactual" : CounterfactualShockExperiment,
    "centrality"     : CentralitySweepExperiment,
    "geometry"       : GeometryExperiment,
}


class PolicySwarm:
    """High-level facade for running PolicySwarm experiments.

    Parameters
    ----------
    output_dir : str
        Root directory for all experiment outputs. Default 'policyswarm_output'.
    seeds : list of int, optional
        Monte Carlo seeds shared across all experiments. Default list(range(20)).
    policy_text : str, optional
        Raw policy text to ingest.
    """

    DEFAULT_POLICY_TEXT = """
    The government introduces strict AI safety regulations requiring transparency
    audits, limiting deployment of high-risk systems, and enforcing penalties for
    non-compliance. The policy prioritises public safety over innovation risks.
    """

    def __init__(self, output_dir="policyswarm_output", seeds=None, policy_text=None):
        self.output_dir  = output_dir
        # Default S=20. Override via --seeds CLI arg or seeds= constructor kwarg.
        self.seeds       = seeds or list(range(20))
        self.policy_text = policy_text or self.DEFAULT_POLICY_TEXT
        os.makedirs(output_dir, exist_ok=True)

    def run_experiment(self, name, **kwargs):
        """Run a single named experiment."""
        if name not in _EXPERIMENT_MAP:
            raise ValueError(
                f"Unknown experiment: {name!r}. "
                f"Choose from: {list(_EXPERIMENT_MAP)}"
            )
        ExperimentClass = _EXPERIMENT_MAP[name]
        exp_dir = os.path.join(self.output_dir, name)
        exp = ExperimentClass(
            output_dir  = exp_dir,
            seeds       = self.seeds,
            policy_text = kwargs.pop("policy_text", self.policy_text),
            **kwargs,
        )
        return exp.report()

    def run_all(self, experiments=None):
        """Run all (or a subset of) experiments sequentially."""
        to_run = experiments or list(_EXPERIMENT_MAP)
        reports = {}
        for name in to_run:
            print(f"\n{'='*60}\nRunning experiment: {name}\n{'='*60}")
            try:
                reports[name] = self.run_experiment(name)
            except Exception as exc:
                print(f"[ERROR] Experiment '{name}' failed: {exc}")
                reports[name] = {"error": str(exc)}
        return reports

    @staticmethod
    def describe_policy(text):
        """Print the KG extraction summary for a policy text."""
        print(describe_extraction(text))