"""
policyswarm
===========
A research-grade agent-based modelling framework for studying how governance
decisions propagate through synthetic social ecosystems.

Quick start — keyword extraction (no extra dependencies)
---------------------------------------------------------
    from policyswarm import PolicySwarm
    ps = PolicySwarm(output_dir="my_run")
    ps.run_experiment("lag")
    ps.run_all()

Quick start — command line and dashboard
-----------------------------------------
    python run_all.py --experiments lag geometry --seeds 0 1 2
    python run_all.py --spec my_run.json          # a saved RunSpec
    python -m policyswarm.gui                     # local web dashboard

Quick start — Tier 1 LLM extraction
-------------------------------------
    from policyswarm.extraction_llm import LLMPolicyExtractor
    extractor = LLMPolicyExtractor.from_yaml(
        "policyswarm/schemas/ai_policy.yaml", backend="ollama", model="llama3.2:3b"
    )
    policy = extractor.extract("data/eu_ai_act.pdf")
    PolicySwarm(policy=policy).run_all()

Quick start — Tier 2 embedding extraction
------------------------------------------
    # Fit once:
    # python -m policyswarm.tools.fit_encoder --corpus-dir data/ --output models/enc.pkl
    from policyswarm.extraction_embedding import EmbeddingPolicyExtractor
    extractor = EmbeddingPolicyExtractor.load("models/enc.pkl")
    policy = extractor.extract("data/new_regulation.pdf")
    PolicySwarm(policy=policy).run_all()

Module map
----------
policyswarm.config              — Configuration dataclasses, enumerations, RunSpec
policyswarm.extraction          — Keyword/KG policy ingestion (Tier 0)
policyswarm.extraction_llm      — LLM-based schema-driven extraction (Tier 1)
policyswarm.extraction_embedding— Corpus PCA embedding extraction (Tier 2)
policyswarm.network             — Social network topology builders
policyswarm.shocks              — Exogenous shock schedule generation
policyswarm.geometry            — Opinion-space distances, updates, epsilon calibration
policyswarm.dynamics            — Core ABM simulation engine (Simulation)
policyswarm.metrics             — Outcome metric computations
policyswarm.analysis            — Statistical analysis utilities
policyswarm.visualization       — Publication-ready plot generation
policyswarm.experiments         — Experiment classes (Exp 1-6, 4b, 4c), events, params
policyswarm.registry            — Experiment registry and RunSpec validation
policyswarm.facade              — PolicySwarm high-level runner
policyswarm.cli                 — Command-line entry point (run_all.py)
policyswarm.gui                 — Local web dashboard (FastAPI + SSE)
policyswarm.latex               — LaTeX table generation
policyswarm.schema              — Runtime schema validation
policyswarm.tools.fit_encoder   — CLI for fitting a Tier 2 CorpusEncoder
"""

from .analysis import (
    cohens_d, executive_summary, group_summary, paired_ttest, stat_test_table,
)
from .config import (
    REGIME_PARAMS, Geometry, GovernanceConfig, NetworkType, OverlapRegime,
    Policy, RunSpec, ShockConfig, ShockMode, SimConfig,
)
from .dynamics import Simulation
from .experiments import (
    CentralitySweepExperiment,
    CounterfactualShockExperiment,
    EnforcementLagExperiment,
    EpsilonCalibrationExperiment,
    GeometryExperiment,
    MediaInteractionExperiment,
    OversightPhaseExperiment,
    TopologyValidationExperiment,
)
from .extraction import (
    DEFAULT_POLICY_TEXT, build_kg, describe_extraction, extract_entities,
    extract_narrative_scores, perceived_policy, policy_from_kg, policy_from_text,
)
from .facade import PolicySwarm
from .metrics import (
    bifurcation_index, cascade_breadth, causal_centrality, compute_all_metrics,
    delta_variance, effect_size, opinion_variance, phase_transition_tick,
    polarization_index,
)
from .network import build_network, compute_influence, top_hub_indices
from .registry import EXPERIMENTS
from .shocks import generate_shocks, override_strength, summarise_schedule

__version__ = "1.2.0"
__author__  = "krishnasai-addala"

# ---------------------------------------------------------------------------
# Optional Tier 1 exports (requires: pip install policyswarm[llm])
# ---------------------------------------------------------------------------
try:
    from .extraction_llm import (
        DimensionSpec,
        HuggingFaceBackend,
        LLMPolicyExtractor,
        OllamaBackend,
        PolicySchema,
    )
    _TIER1_AVAILABLE = True
    _TIER1_EXPORTS = ["LLMPolicyExtractor", "PolicySchema", "DimensionSpec",
                      "OllamaBackend", "HuggingFaceBackend"]
except ImportError:
    _TIER1_AVAILABLE = False
    _TIER1_EXPORTS = []

# ---------------------------------------------------------------------------
# Optional Tier 2 exports (requires: pip install policyswarm[embedding])
# ---------------------------------------------------------------------------
try:
    from .extraction_embedding import (
        CorpusEncoder,
        EmbeddingPolicyExtractor,
    )
    _TIER2_AVAILABLE = True
    _TIER2_EXPORTS = ["CorpusEncoder", "EmbeddingPolicyExtractor"]
except ImportError:
    _TIER2_AVAILABLE = False
    _TIER2_EXPORTS = []

__all__ = [
    # configuration
    "SimConfig", "GovernanceConfig", "Policy", "ShockConfig", "RunSpec",
    "OverlapRegime", "NetworkType", "Geometry", "ShockMode", "REGIME_PARAMS",
    # policy ingestion
    "DEFAULT_POLICY_TEXT", "policy_from_text", "policy_from_kg", "extract_entities",
    "extract_narrative_scores", "build_kg", "perceived_policy", "describe_extraction",
    # model
    "Simulation", "build_network", "compute_influence", "top_hub_indices",
    "generate_shocks", "override_strength", "summarise_schedule",
    # metrics and analysis
    "opinion_variance", "polarization_index", "bifurcation_index", "cascade_breadth",
    "phase_transition_tick", "causal_centrality", "delta_variance", "effect_size",
    "compute_all_metrics", "paired_ttest", "group_summary", "stat_test_table",
    "executive_summary", "cohens_d",
    # experiments
    "PolicySwarm", "EXPERIMENTS",
    "OversightPhaseExperiment", "EnforcementLagExperiment", "MediaInteractionExperiment",
    "CounterfactualShockExperiment", "TopologyValidationExperiment",
    "EpsilonCalibrationExperiment", "CentralitySweepExperiment", "GeometryExperiment",
]
__all__ += _TIER1_EXPORTS + _TIER2_EXPORTS
