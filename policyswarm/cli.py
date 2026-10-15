"""
policyswarm.cli
===============
Command-line entry point for the PolicySwarm framework
(``python run_all.py ...``, ``python -m policyswarm.cli ...`` or the
``policyswarm`` console script).

Usage
-----
    # Keyword extraction (default)
    python run_all.py
    python run_all.py --experiments lag geometry
    python run_all.py --seeds 0 1 2 3 4 --output my_results
    python run_all.py --describe

    # A saved run description (experiment parameters, SimConfig overrides)
    python run_all.py --spec my_run.json

    # Tier 1: LLM extraction (Ollama backend) from text or a PDF
    python run_all.py --policy-source llm \\
        --schema policyswarm/schemas/ai_policy.yaml \\
        --policy-doc data/eu_ai_act.pdf --llm-backend ollama --llm-model llama3.2:3b

    # Tier 2: embedding extraction (fit the encoder first)
    python -m policyswarm.tools.fit_encoder \\
        --corpus-dir data/policy_corpus/ --n-dims 6 --output models/encoder.pkl
    python run_all.py --policy-source embedding \\
        --encoder models/encoder.pkl --policy-doc data/new_regulation.pdf

Policy injection for Tier 1/2
-----------------------------
With ``--policy-source llm`` or ``embedding`` the extracted ``Policy`` object
is passed to every experiment explicitly (``BaseExperiment(policy=...)``), and
``SimConfig.opinion_dim`` is set to the policy's dimensionality.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .config import Policy, RunSpec
from .experiments.params import ParamError
from .extraction import DEFAULT_POLICY_TEXT, describe_extraction
from .facade import PolicySwarm
from .latex import centrality_table_to_latex, stat_table_to_latex, summary_table_to_latex
from .registry import EXPERIMENTS, policy_from_spec, validate_run_spec
from .schema import CENTRALITY_SCHEMA, GEOMETRY_RESULTS_SCHEMA, STATS_SCHEMA

__all__ = ["main", "parse_args", "generate_latex_tables"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    experiment_help = "\n".join(
        f"  {name:<15}{cls.title}" for name, cls in EXPERIMENTS.items()
    )
    parser = argparse.ArgumentParser(
        prog="policyswarm",
        description="PolicySwarm: AI Governance ABM Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Experiments
-----------
{experiment_help}

Policy sources
--------------
  keyword    (default) Keyword extraction from --policy-text
  llm        Tier 1: LLM extraction via --schema + (--policy-text | --policy-doc)
  embedding  Tier 2: PCA embedding via --encoder + (--policy-text | --policy-doc)
""",
    )

    parser.add_argument(
        "--spec", type=Path, default=None,
        help="Path to a RunSpec JSON file. Overrides --experiments, --seeds, "
             "--output and --policy-text, and can set experiment parameters.",
    )
    parser.add_argument(
        "--experiments", nargs="+", choices=list(EXPERIMENTS), default=list(EXPERIMENTS),
        help="Experiments to run (default: all).",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=list(range(30)),
        help="Random seeds for Monte Carlo runs (default: 0-29).",
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
        "--policy-source", choices=["keyword", "llm", "embedding"], default="keyword",
        help="Policy extraction backend: keyword (default), llm (Tier 1) or "
             "embedding (Tier 2).",
    )
    parser.add_argument(
        "--policy-doc", type=Path, default=None,
        help="Path to a PDF policy document (used by llm and embedding sources).",
    )

    # ── Tier 1 (LLM) ─────────────────────────────────────────────────────
    llm_group = parser.add_argument_group("Tier 1 (LLM) options")
    llm_group.add_argument(
        "--schema", type=Path, default=None,
        help="Path to a schema YAML file (e.g. policyswarm/schemas/ai_policy.yaml). "
             "Required for --policy-source llm.",
    )
    llm_group.add_argument(
        "--llm-backend", choices=["ollama", "huggingface"], default="ollama",
        help="LLM inference backend. Default: ollama.",
    )
    llm_group.add_argument(
        "--llm-model", type=str, default=None,
        help="Model name/tag. Ollama default: llama3.2:3b. "
             "HuggingFace default: microsoft/Phi-3-mini-4k-instruct.",
    )

    # ── Tier 2 (Embedding) ────────────────────────────────────────────────
    emb_group = parser.add_argument_group("Tier 2 (Embedding) options")
    emb_group.add_argument(
        "--encoder", type=Path, default=None,
        help="Path to a fitted CorpusEncoder .pkl file. Required for "
             "--policy-source embedding. Fit with: python -m policyswarm.tools.fit_encoder",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Policy construction (Tier 1 / Tier 2)
# ---------------------------------------------------------------------------

def build_policy_llm(args: argparse.Namespace) -> Policy:
    """Tier 1: schema-driven LLM extraction."""
    from .extraction_llm import LLMPolicyExtractor

    if not args.schema:
        sys.exit("ERROR: --policy-source llm requires --schema "
                 "(e.g. policyswarm/schemas/ai_policy.yaml)")

    extractor = LLMPolicyExtractor.from_yaml(
        schema_path = args.schema,
        backend     = args.llm_backend,
        model       = args.llm_model,
    )

    if args.policy_doc:
        print(f"\nExtracting policy from PDF: {args.policy_doc}")
        policy = extractor.extract(args.policy_doc)
    else:
        print("\nExtracting policy from text via LLM ...")
        policy = extractor.extract_text(args.policy_text or DEFAULT_POLICY_TEXT)

    print("\nLLM extraction result:")
    print(f"  Domain  : {extractor.schema.domain}")
    print(f"  Backend : {type(extractor.backend).__name__}")
    print(f"  Dims    : {policy.dim}")
    for name, val, conf in zip(policy.dimension_names, policy.vector, policy.confidence):
        print(f"  {name:<22} = {val:.3f}  (confidence {conf:.2f})")
    print(f"  lag     : {policy.lag}")
    return policy


def build_policy_embedding(args: argparse.Namespace) -> Policy:
    """Tier 2: corpus PCA embedding extraction."""
    from .extraction_embedding import EmbeddingPolicyExtractor

    if not args.encoder:
        sys.exit("ERROR: --policy-source embedding requires --encoder "
                 "(path to a fitted .pkl encoder).\nFit one with:\n"
                 "  python -m policyswarm.tools.fit_encoder "
                 "--corpus-dir <dir> --output models/encoder.pkl")

    extractor = EmbeddingPolicyExtractor.load(args.encoder)

    if args.policy_doc:
        print(f"\nEncoding policy from PDF: {args.policy_doc}")
        policy = extractor.extract(args.policy_doc)
    else:
        print("\nEncoding policy from text ...")
        policy = extractor.extract_text(args.policy_text or DEFAULT_POLICY_TEXT)

    print("\nEmbedding extraction result:")
    print(f"  Encoder : {extractor.encoder.model_name}")
    print(f"  Dims    : {policy.dim}")
    evr = extractor.encoder._pca.explained_variance_ratio_
    labels = extractor.encoder.dimension_labels
    for i, (val, conf, sal) in enumerate(
        zip(policy.vector, policy.confidence, policy.dimension_salience)
    ):
        print(f"  latent_axis_{i:<2} = {val:.3f}  "
              f"(conf={conf:.3f}, salience={sal:+.3f}, var={evr[i]:.3f})")
        if labels:
            print(f"    [{labels[i][:50]}]")
    print(f"  lag     : {policy.lag}")
    return policy


_POLICY_BUILDERS = {"llm": build_policy_llm, "embedding": build_policy_embedding}


# ---------------------------------------------------------------------------
# LaTeX table generation
# ---------------------------------------------------------------------------

def generate_latex_tables(experiment_name: str, output_root: str, n_seeds: int) -> int:
    """Write the LaTeX table for a completed experiment from its latest stats CSV.

    Returns the number of tables written.
    """
    exp_dir = Path(output_root) / experiment_name
    stats_files = sorted(exp_dir.glob("*_stats_*.csv"))
    if not stats_files:
        raise ValueError(f"No stats CSV found in {exp_dir}")
    stats_df = pd.read_csv(stats_files[-1])
    label = f"tab:{experiment_name}"

    if experiment_name == "geometry":
        GEOMETRY_RESULTS_SCHEMA.validate(stats_df)
        latex = summary_table_to_latex(
            stats_df, label=label,
            caption=f"Geometry comparison across opinion spaces "
                    f"(mean $\\pm$ 95\\% CI, $S={n_seeds}$).",
        )
    elif experiment_name == "centrality":
        CENTRALITY_SCHEMA.validate(stats_df)
        latex = centrality_table_to_latex(
            stats_df, label=label,
            caption=f"Centrality $\\times$ shock strength "
                    f"(mean [95\\% CI], $S={n_seeds}$).",
        )
    else:
        STATS_SCHEMA.validate(stats_df)
        latex = stat_table_to_latex(
            stats_df, label=label,
            caption=f"{experiment_name.capitalize()} results "
                    f"($S={n_seeds}$, paired $t$-test, two-sided).",
        )

    (exp_dir / f"{experiment_name}_table.tex").write_text(latex, encoding="utf-8")
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _run_spec_from_args(args: argparse.Namespace) -> RunSpec:
    if args.spec is not None:
        return RunSpec.load(args.spec)
    return RunSpec(
        experiments = list(args.experiments),
        seeds       = list(args.seeds),
        output_dir  = args.output,
        policy_text = args.policy_text,
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI. Returns a process exit code (1 if any experiment failed)."""
    # Summaries contain non-ASCII symbols; Windows pipes default to cp1252.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = parse_args(argv)

    if args.describe:
        print(describe_extraction(args.policy_text or DEFAULT_POLICY_TEXT))
        return 0

    try:
        spec = _run_spec_from_args(args)
        validate_run_spec(spec)
    except (ParamError, ValueError, OSError) as exc:
        print(f"ERROR: invalid run description: {exc}", file=sys.stderr)
        return 2

    policy = None
    if args.policy_source in _POLICY_BUILDERS:
        if spec.opinion_space is not None:
            print("ERROR: the run description defines an opinion_space, which cannot be "
                  f"combined with --policy-source {args.policy_source}", file=sys.stderr)
            return 2
        policy = _POLICY_BUILDERS[args.policy_source](args)

    from . import __version__
    print(f"\nPolicySwarm v{__version__}")
    print(f"Policy source : {args.policy_source}")
    print(f"Seeds         : {spec.seeds}")
    print(f"Output dir    : {spec.output_dir}")
    print(f"Experiments   : {spec.experiments}")
    if policy is not None:
        print(f"Policy dims   : {policy.dim} (SimConfig.opinion_dim set to match)")
    if spec.opinion_space is not None:
        custom = policy_from_spec(spec)
        print("Opinion space : custom")
        for name, value in zip(custom.dimension_names, custom.vector):
            print(f"  {name:<24} policy position = {value:+.3f}")
    print()

    reports = PolicySwarm.run_spec(spec, policy=policy)

    print("\n" + "=" * 60)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 60)

    failed = False
    for name, report in reports.items():
        if "error" in report:
            failed = True
            print(f"  [FAIL] {name}: {report['error']}")
            continue

        print(f"  [OK]   {name}")
        figs = report.get("figure_paths", [])
        if figs:
            print(f"         figures : {len(figs)}")
        try:
            n_tables = generate_latex_tables(name, spec.output_dir, len(spec.seeds))
            print(f"         latex   : {n_tables} table written")
        except Exception as exc:
            print(f"         latex   : failed ({exc})")

    print(f"\nAll outputs saved to: {spec.output_dir}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
