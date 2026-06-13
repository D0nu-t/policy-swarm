#!/usr/bin/env python3
"""
run_all.py
==========
Command-line entrypoint for the PolicySwarm framework.

Usage
-----
    # Original (keyword extraction, fully unchanged)
    python run_all.py
    python run_all.py --experiments lag geometry
    python run_all.py --seeds 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19
    python run_all.py --output my_results
    python run_all.py --describe

    # Tier 1: LLM extraction from text (Ollama backend)
    python run_all.py \\
        --policy-source llm \\
        --schema schemas/ai_policy.yaml \\
        --policy-text "The government introduces strict AI safety..." \\
        --llm-backend ollama \\
        --llm-model llama3.2:3b

    # Tier 1: LLM extraction from PDF
    python run_all.py \\
        --policy-source llm \\
        --schema schemas/ai_policy.yaml \\
        --policy-doc data/eu_ai_act.pdf

    # Tier 1: HuggingFace backend, different domain
    python run_all.py \\
        --policy-source llm \\
        --schema schemas/healthcare_policy.yaml \\
        --policy-doc data/aca.pdf \\
        --llm-backend huggingface \\
        --llm-model microsoft/Phi-3-mini-4k-instruct

    # Tier 2: Embedding extraction (fit encoder first)
    python -m policyswarm.tools.fit_encoder \\
        --corpus-dir data/policy_corpus/ --n-dims 6 --output models/encoder.pkl
    python run_all.py \\
        --policy-source embedding \\
        --encoder models/encoder.pkl \\
        --policy-doc data/new_regulation.pdf

Injection mechanism for Tier 1/2
---------------------------------
When --policy-source is llm or embedding, the pre-built Policy object is
injected into all experiments by temporarily replacing
policyswarm.extraction.policy_from_text at the module level.  Every
experiment's run() method calls policy_from_text(self.policy_text); with
the patch in place, it returns copy.copy(pre_built_policy) regardless of
the text argument.  The original function is always restored in a finally
block.  sim_config is forwarded to each experiment via PolicySwarm.run_experiment()
**kwargs to set SimConfig.opinion_dim to policy.dim.
"""

import argparse
import copy
import os
import sys
import traceback
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

import policyswarm.extraction as _policyswarm_extraction_module
from policyswarm import PolicySwarm
from policyswarm.config import SimConfig
from policyswarm.latex import stat_table_to_latex, summary_table_to_latex
from policyswarm.schema import STATS_SCHEMA, GEOMETRY_RESULTS_SCHEMA


POLICY_TEXT = """
1. OBJECTIVE AND GUIDING PRINCIPLE
The government hereby establishes a comprehensive, risk-based regulatory framework for Artificial Intelligence (AI). This policy explicitly prioritizes public safety, fundamental human rights, and systemic security over unrestrained technical innovation. Where severe or irreversible risks to public welfare are identified, the absence of full scientific certainty shall not be used as a reason for postponing precautionary regulations.

2. CLASSIFICATION OF RISK TIERS
AI systems shall be categorized into distinct risk tiers, drawing direct inspiration from the European Union AI Act framework:
  * Prohibited Systems: AI practices that present an unacceptable risk to human safety and civil liberties are banned outright. This includes systems utilizing subliminal techniques to manipulate behavior, untargeted scraping of facial images for biometric surveillance, and state-backed social scoring systems.
  * High-Risk Systems: AI deployed in critical infrastructure (such as water, electricity, and transport networks), medical devices, biometric identification, law enforcement, and systemic employment or education algorithms are subject to rigorous pre-market and post-market obligations.

3. MANDATORY TRANSPARENCY AUDITS AND LIFECYCLE MANAGEMENT
Providers and deployers of High-Risk and General-Purpose AI (GPAI) models must adhere to strict transparency and technical documentation standards:
  * Conformity Assessments: Developers must perform independent or third-party conformity assessments before any high-risk system can be placed on the open market.
  * Traceability & Explainability: System architectures must maintain automated logs (audit trails) ensuring transparency. AI systems interacting directly with humans must be designed to explicitly notify users that they are interacting with an AI. Synthetic content (e.g., text, video, audio) must be digitally watermarked in a machine-readable format.
  * NIST Risk Management Alignment: Entities must implement continuous risk-mitigation frameworks detailing model architecture, dataset curation, bias testing, and human-in-the-loop oversight mechanisms that allow real-time intervention and system overrides.

4. PENALTIES FOR NON-COMPLIANCE AND ENFORCEMENT
To enforce compliance, the regulatory authority establishes a tiered, dissuasive penalty regime based on global annual turnover:
  * Tier 1 (Prohibited Practices): Violations involving banned AI applications shall face administrative fines of up to €35,000,000 or up to 7% of the offending entity's total worldwide annual turnover for the preceding financial year, whichever is higher.
  * Tier 2 (High-Risk Failures): Non-compliance with mandatory high-risk obligations, data governance gaps, or structural transparency failures shall be subject to fines of up to €15,000,000 or 3% of global annual turnover.
  * Tier 3 (Procedural & Information Violations): Supplying incorrect, incomplete, or misleading information to auditing bodies or national competent authorities during an inspection shall carry penalties of up to €7,500,000 or 1% of global annual turnover.
"""

VALID_EXPERIMENTS = [
    "oversight",
    "lag",
    "media",
    "counterfactual",
    "centrality",
    "geometry",
]


# ---------------------------------------------------------------------------
# Policy construction helpers
# ---------------------------------------------------------------------------

def build_policy_keyword(policy_text: str):
    """
    Legacy keyword extraction.

    Returns
    -------
    (Policy, None)
        None sim_config_override: experiments use default SimConfig(opinion_dim=4).
    """
    from policyswarm.extraction import policy_from_text
    return policy_from_text(policy_text), None


def build_policy_llm(args):
    """
    Tier 1: schema-driven LLM extraction.

    Returns
    -------
    (Policy, SimConfig)
        SimConfig has opinion_dim set to policy.dim.
    """
    from policyswarm.extraction_llm import LLMPolicyExtractor

    if not args.schema:
        print(
            "ERROR: --policy-source llm requires --schema "
            "(e.g. schemas/ai_policy.yaml)"
        )
        sys.exit(1)

    extractor = LLMPolicyExtractor.from_yaml(
        schema_path = args.schema,
        backend     = args.llm_backend,
        model       = args.llm_model,
    )

    if args.policy_doc:
        print(f"\nExtracting policy from PDF: {args.policy_doc}")
        policy = extractor.extract(args.policy_doc)
    else:
        text = args.policy_text or POLICY_TEXT
        print("\nExtracting policy from text via LLM ...")
        policy = extractor.extract_text(text)

    print(f"\nLLM extraction result:")
    print(f"  Domain  : {extractor.schema.domain}")
    print(f"  Backend : {type(extractor.backend).__name__}")
    print(f"  Dims    : {policy.dim}")
    for name, val, conf in zip(policy.dimension_names, policy.vector, policy.confidence):
        print(f"  {name:<22} = {val:.3f}  (confidence {conf:.2f})")
    print(f"  lag     : {policy.lag}")

    return policy, SimConfig(opinion_dim=policy.dim)


def build_policy_embedding(args):
    """
    Tier 2: corpus PCA embedding extraction.

    Returns
    -------
    (Policy, SimConfig)
    """
    from policyswarm.extraction_embedding import EmbeddingPolicyExtractor

    if not args.encoder:
        print(
            "ERROR: --policy-source embedding requires --encoder "
            "(path to a fitted .pkl encoder).\n"
            "Fit one with:\n"
            "  python -m policyswarm.tools.fit_encoder "
            "--corpus-dir <dir> --output models/encoder.pkl"
        )
        sys.exit(1)

    extractor = EmbeddingPolicyExtractor.load(args.encoder)

    if args.policy_doc:
        print(f"\nEncoding policy from PDF: {args.policy_doc}")
        policy = extractor.extract(args.policy_doc)
    else:
        text = args.policy_text or POLICY_TEXT
        print("\nEncoding policy from text ...")
        policy = extractor.extract_text(text)

    print(f"\nEmbedding extraction result:")
    print(f"  Encoder : {extractor.encoder.model_name}")
    print(f"  Dims    : {policy.dim}")
    evr = extractor.encoder._pca.explained_variance_ratio_
    for i, (val, conf, sal) in enumerate(
        zip(policy.vector, policy.confidence, policy.dimension_salience)
    ):
        label = (
            extractor.encoder.dimension_labels[i][:50]
            if extractor.encoder.dimension_labels else ""
        )
        print(
            f"  latent_axis_{i:<2} = {val:.3f}  "
            f"(conf={conf:.3f}, salience={sal:+.3f}, var={evr[i]:.3f})"
        )
        if label:
            print(f"    [{label}]")
    print(f"  lag     : {policy.lag}")

    return policy, SimConfig(opinion_dim=policy.dim)


# ---------------------------------------------------------------------------
# Pre-built policy injection
# ---------------------------------------------------------------------------

def _run_with_prebuilt_policy(
    ps,
    experiments,
    policy,
    sim_config_override,
):
    """
    Run all experiments with a pre-built Policy.

    Mechanism
    ---------
    1. Replace policyswarm.extraction.policy_from_text at the module level
       with a lambda that returns copy.copy(policy).  Every experiment's
       run() method calls policy_from_text(self.policy_text), so it
       transparently receives a fresh copy of our pre-built policy.

    2. Pass sim_config=sim_config_override to ps.run_experiment() so each
       experiment uses the correct SimConfig.opinion_dim.

    3. Restore the original function in a finally block — guaranteed even
       if an experiment raises.

    Parameters
    ----------
    ps : PolicySwarm
    experiments : list of str
    policy : Policy
    sim_config_override : SimConfig or None

    Returns
    -------
    dict  name → report dict
    """
    _original_fn = _policyswarm_extraction_module.policy_from_text
    _policyswarm_extraction_module.policy_from_text = (
        lambda text, lag=10: copy.copy(policy)
    )

    reports = {}
    try:
        for name in experiments:
            print(f"\n{'='*60}\nRunning experiment: {name}\n{'='*60}")
            try:
                kwargs = {}
                if sim_config_override is not None:
                    kwargs["sim_config"] = sim_config_override
                reports[name] = ps.run_experiment(name, **kwargs)
            except Exception as exc:
                print(f"[ERROR] Experiment '{name}' failed: {exc}")
                traceback.print_exc()
                reports[name] = {"error": str(exc)}
    finally:
        # Always restore, even if the loop raises
        _policyswarm_extraction_module.policy_from_text = _original_fn

    return reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="PolicySwarm: AI Governance ABM Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Experiments
-----------
  oversight      Exp 1: Oversight regime phase transitions
  lag            Exp 2: Enforcement lag sensitivity (primary finding)
  media          Exp 3: Competing media x enforcement lag interaction
  counterfactual Exp 4: Counterfactual shock analysis
  centrality     Exp 5: Centrality x shock strength sweep
  geometry       Exp 6: Opinion-space geometry comparison

Policy sources
--------------
  keyword    (default) Keyword extraction from --policy-text
  llm        Tier 1: LLM extraction via --schema + (--policy-text | --policy-doc)
  embedding  Tier 2: PCA embedding via --encoder + (--policy-text | --policy-doc)
""",
    )

    # ── Core args (unchanged from original) ─────────────────────────────
    parser.add_argument(
        "--experiments", nargs="+",
        choices=VALID_EXPERIMENTS,
        default=VALID_EXPERIMENTS,
        help="Experiments to run (default: all).",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int,
        default=list(range(20)),
        help="Random seeds for Monte Carlo runs (default: 0-19, S=20).",
    )
    parser.add_argument(
        "--output", default="policyswarm_output",
        help="Root output directory (default: policyswarm_output).",
    )
    parser.add_argument(
        "--policy-text", default=None,
        help="Raw policy text. Used by keyword and llm sources.",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print keyword extraction summary and exit (keyword source only).",
    )

    # ── Policy source ────────────────────────────────────────────────────
    parser.add_argument(
        "--policy-source",
        choices=["keyword", "llm", "embedding"],
        default="keyword",
        help=(
            "Policy extraction backend. "
            "keyword = legacy keyword matching (default). "
            "llm = Tier 1 LLM structured extraction. "
            "embedding = Tier 2 PCA corpus embedding."
        ),
    )
    parser.add_argument(
        "--policy-doc",
        type=Path,
        default=None,
        help="Path to a PDF policy document (used by llm and embedding sources).",
    )

    # ── Tier 1 (LLM) ─────────────────────────────────────────────────────
    llm_group = parser.add_argument_group("Tier 1 (LLM) options")
    llm_group.add_argument(
        "--schema",
        type=Path,
        default=None,
        help=(
            "Path to a schema YAML file (e.g. schemas/ai_policy.yaml). "
            "Required for --policy-source llm."
        ),
    )
    llm_group.add_argument(
        "--llm-backend",
        choices=["ollama", "huggingface"],
        default="ollama",
        help="LLM inference backend. Default: ollama.",
    )
    llm_group.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help=(
            "Model name/tag. "
            "Ollama default: llama3.2:3b. "
            "HuggingFace default: microsoft/Phi-3-mini-4k-instruct."
        ),
    )

    # ── Tier 2 (Embedding) ────────────────────────────────────────────────
    emb_group = parser.add_argument_group("Tier 2 (Embedding) options")
    emb_group.add_argument(
        "--encoder",
        type=Path,
        default=None,
        help=(
            "Path to a fitted CorpusEncoder .pkl file. "
            "Required for --policy-source embedding. "
            "Fit with: python -m policyswarm.tools.fit_encoder"
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# LaTeX table generation (unchanged from original)
# ---------------------------------------------------------------------------

def generate_latex_tables(experiment_name: str, output_root: str) -> int:
    """Generate and write LaTeX tables for a completed experiment.

    Returns the number of tables successfully written.
    """
    exp_dir = Path(output_root) / experiment_name

    if experiment_name == "geometry":
        stats_files = list(exp_dir.glob("*_stats_*.csv"))
        if not stats_files:
            raise ValueError(f"No geometry stats CSV found in {exp_dir}")
        df = pd.read_csv(stats_files[-1])
        GEOMETRY_RESULTS_SCHEMA.validate(df)
        latex = summary_table_to_latex(
            df,
            caption=(
                "Geometry comparison across opinion spaces "
                "(mean $\\pm$ 95\\% CI, $S=20$)."
            ),
            label="tab:geometry",
        )
        (exp_dir / "geometry_table.tex").write_text(latex)
        return 1

    stats_files = list(exp_dir.glob("*_stats_*.csv"))
    if not stats_files:
        raise ValueError(f"No stats CSV found in {exp_dir}")
    stats_df = pd.read_csv(stats_files[-1])
    STATS_SCHEMA.validate(stats_df)
    latex = stat_table_to_latex(
        stats_df,
        caption=(
            f"{experiment_name.capitalize()} results "
            f"($S=20$, paired $t$-test, two-sided)."
        ),
        label=f"tab:{experiment_name}",
    )
    (exp_dir / f"{experiment_name}_table.tex").write_text(latex)
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # ── Policy construction ────────────────────────────────────────────────
    if args.policy_source == "keyword":
        policy_text = args.policy_text or POLICY_TEXT

        if args.describe:
            from policyswarm.extraction import describe_extraction
            print(describe_extraction(policy_text))
            return

        policy, sim_config_override = build_policy_keyword(policy_text)

    elif args.policy_source == "llm":
        policy, sim_config_override = build_policy_llm(args)

    elif args.policy_source == "embedding":
        policy, sim_config_override = build_policy_embedding(args)

    # ── Build PolicySwarm facade ───────────────────────────────────────────
    ps = PolicySwarm(
        output_dir  = args.output,
        seeds       = args.seeds,
        policy_text = args.policy_text or POLICY_TEXT,
    )

    print(f"\nPolicySwarm v1.1.0")
    print(f"Policy source : {args.policy_source}")
    print(f"Seeds         : {args.seeds}")
    print(f"Output dir    : {args.output}")
    print(f"Experiments   : {args.experiments}")
    if policy is not None:
        print(f"Policy dims   : {policy.dim}")
        if sim_config_override and sim_config_override.opinion_dim != 4:
            print(
                f"Note: SimConfig.opinion_dim overridden to {sim_config_override.opinion_dim} "
                f"to match policy dimensionality."
            )
    print()

    # ── Run experiments ────────────────────────────────────────────────────
    if args.policy_source == "keyword":
        # Legacy path: unmodified behaviour
        reports = ps.run_all(experiments=args.experiments)
    else:
        # Tier 1 / Tier 2: inject pre-built policy via module-level monkeypatch
        reports = _run_with_prebuilt_policy(
            ps                  = ps,
            experiments         = args.experiments,
            policy              = policy,
            sim_config_override = sim_config_override,
        )

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 60)

    for name, report in reports.items():
        if "error" in report:
            print(f"  [FAIL] {name}: {report['error']}")
            continue

        print(f"  [OK]   {name}")

        figs = report.get("figure_paths", [])
        if figs:
            print(f"         figures : {len(figs)}")

        try:
            n_tables = generate_latex_tables(name, args.output)
            print(f"         latex   : {n_tables} table written")
        except Exception as e:
            print(f"         latex   : failed ({e})")

    print(f"\nAll outputs saved to: {args.output}/")


if __name__ == "__main__":
    main()
