#!/usr/bin/env python3
"""
run_all.py
==========
Command-line entrypoint for the PolicySwarm framework.

Usage
-----
    python run_all.py                          # run all 6 experiments
    python run_all.py --experiments lag media  # specific experiments
    python run_all.py --seeds 0 1 2 3 4        # custom seed list
    python run_all.py --output my_results      # custom output directory
    python run_all.py --describe               # print KG extraction only

All outputs (CSVs, stats tables, PNGs) are written to --output/<experiment_name>/.
"""

import argparse
import sys
import os

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


def parse_args():
    parser = argparse.ArgumentParser(
        description="PolicySwarm: AI Governance ABM Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Experiments
-----------
  oversight      Exp 1: Oversight regime phase transitions (NONE→PROHIBITIVE)
  lag            Exp 2: Enforcement lag sensitivity sweep (strongest finding)
  media          Exp 3: Competing media × enforcement lag interaction
  counterfactual Exp 4: Counterfactual shock analysis (coordinating vs polarizing)
  centrality     Exp 5: Centrality × shock strength sweep (hub vs random)
  geometry       Exp 6: Opinion-space geometry (Euclidean vs cosine vs manifold)
""",
    )
    parser.add_argument(
        "--experiments", nargs="+",
        choices=VALID_EXPERIMENTS,
        default=VALID_EXPERIMENTS,
        help="Experiments to run (default: all).",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int,
        default=list(range(20)),
        help="Random seeds for Monte Carlo runs (default: 0 1 2 3 4 5 6 7 8 9 10 11 12 13 141 15 16 17 18 19).",
    )
    parser.add_argument(
        "--output", default="policyswarm_output",
        help="Root output directory (default: policyswarm_output).",
    )
    parser.add_argument(
        "--policy-text", default=POLICY_TEXT,
        help="Policy text to ingest (default: canonical design-doc text).",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print KG extraction summary for the policy text and exit.",
    )
    return parser.parse_args()

from pathlib import Path
import pandas as pd


def generate_latex_tables(report, experiment_name, output_root):
    exp_dir = Path(output_root) / experiment_name
    # ---------- STAT TABLE ----------
    stats_files = list(exp_dir.glob("*_stats_*.csv"))
    if stats_files:
        stats_df = pd.read_csv(stats_files[-1])  
        stats_df = stats_df.sort_values(by=stats_df.columns.tolist())

        latex = stat_table_to_latex(
            stats_df,
            caption=f"{experiment_name.capitalize()} results (S=20, paired t-test).",
            label=f"tab:{experiment_name}"
        )

        with open(exp_dir / f"{experiment_name}_table.tex", "w") as f:
            f.write(latex)

    # ---------- SUMMARY TABLE (geometry only) ----------
    if experiment_name == "geometry":
        results_files = list(exp_dir.glob("*_results_*.csv"))
        if results_files:
            df = pd.read_csv(results_files[-1])

            latex = summary_table_to_latex(
                df,
                caption="Geometry comparison across opinion spaces (mean ± 95\\% CI, S=20).",
                label="tab:geometry"
            )

            with open(exp_dir / "geometry_table.tex", "w") as f:
                f.write(latex)
def main():
    args = parse_args()

    ps = PolicySwarm(
        output_dir  = args.output,
        seeds       = args.seeds,
        policy_text = args.policy_text,
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
        else:
            print(f"  [OK]   {name}")
            figs = report.get("figure_paths", [])
            if figs:
                print(f"         figures: {len(figs)}")
        try:
            generate_latex_tables(report, name, args.output)
            print(f"         latex: 1 table generated")
        except Exception as e:
            print(f"         latex: failed ({e})")
    print(f"\nAll outputs saved to: {args.output}/")


if __name__ == "__main__":
    main()
