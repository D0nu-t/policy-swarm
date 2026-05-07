#!/usr/bin/env python3
"""
run_all.py
==========
Command-line entrypoint for the PolicySwarm framework.
"""

import argparse
import sys
import os
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from policyswarm import PolicySwarm
from policyswarm.latex import stat_table_to_latex, summary_table_to_latex


POLICY_TEXT = """
The government introduces strict AI safety regulations requiring transparency audits,
limiting deployment of high-risk systems, and enforcing penalties for non-compliance.
The policy prioritises public safety over innovation risks.
"""


VALID_EXPERIMENTS = [
    "oversight",
    "lag",
    "media",
    "counterfactual",
    "centrality",
    "geometry",
]


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="PolicySwarm: AI Governance ABM Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--experiments", nargs="+",
        choices=VALID_EXPERIMENTS,
        default=VALID_EXPERIMENTS,
    )

    parser.add_argument(
        "--seeds", nargs="+", type=int,
        default=list(range(20)),
    )

    parser.add_argument(
        "--output", default="policyswarm_output",
    )

    parser.add_argument(
        "--policy-text", default=POLICY_TEXT,
    )

    parser.add_argument(
        "--describe", action="store_true",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------
# LaTeX generation
# ---------------------------------------------------------------------

def generate_latex_tables(experiment_name: str, output_root: str):
    exp_dir = Path(output_root) / experiment_name

    # -------------------------------
    # GEOMETRY → summary table only
    # -------------------------------
    if experiment_name == "geometry":
        results_files = list(exp_dir.glob("*_results_*.csv"))
        if not results_files:
            raise ValueError("No geometry results CSV found")

        df = pd.read_csv(results_files[-1])

        latex = summary_table_to_latex(
            df,
            caption="Geometry comparison across opinion spaces (mean ± 95\\% CI, S=20).",
            label="tab:geometry"
        )

        with open(exp_dir / "geometry_table.tex", "w") as f:
            f.write(latex)

        return 1  # number of tables generated

    # -------------------------------
    # ALL OTHER EXPERIMENTS → stat tables
    # -------------------------------
    stats_files = list(exp_dir.glob("*_stats_*.csv"))
    if not stats_files:
        raise ValueError("No stats CSV found")

    stats_df = pd.read_csv(stats_files[-1])

    # sanity check: ensure required columns exist
    required_cols = {"effect", "effect_ci_low", "effect_ci_high", "p_value"}
    if not required_cols.issubset(set(stats_df.columns)):
        raise ValueError(f"Missing required stat columns: {required_cols}")

    latex = stat_table_to_latex(
        stats_df,
        caption=f"{experiment_name.capitalize()} results (S=20, paired t-test).",
        label=f"tab:{experiment_name}"
    )

    with open(exp_dir / f"{experiment_name}_table.tex", "w") as f:
        f.write(latex)

    return 1


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    args = parse_args()

    ps = PolicySwarm(
        output_dir=args.output,
        seeds=args.seeds,
        policy_text=args.policy_text,
    )

    if args.describe:
        ps.describe_policy(args.policy_text)
        return

    print(f"PolicySwarm v1.0.0")
    print(f"Seeds        : {args.seeds}")
    print(f"Output dir   : {args.output}")
    print(f"Experiments  : {args.experiments}")
    print()

    reports = ps.run_all(experiments=args.experiments)

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
            print(f"         figures: {len(figs)}")

        try:
            n_tables = generate_latex_tables(name, args.output)
            print(f"         latex: {n_tables} table generated")
        except Exception as e:
            print(f"         latex: failed ({e})")

    print(f"\nAll outputs saved to: {args.output}/")


if __name__ == "__main__":
    main()