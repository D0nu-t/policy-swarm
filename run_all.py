#!/usr/bin/env python3
"""
run_all.py
==========
Command-line entrypoint for the PolicySwarm framework.

Usage
-----
    python run_all.py                              # run all 6 experiments (S=20)
    python run_all.py --experiments lag geometry   # specific experiments
    python run_all.py --seeds 0 1 2 ... 19        # explicit seed list
    python run_all.py --output my_results          # custom output directory
    python run_all.py --describe                   # print KG extraction and exit

All outputs (CSVs, stats tables, PNGs, LaTeX tables) are written to
--output/<experiment_name>/.
"""

import argparse
import sys
import os
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from policyswarm import PolicySwarm
from policyswarm.latex import stat_table_to_latex, summary_table_to_latex
from policyswarm.schema import STATS_SCHEMA, GEOMETRY_RESULTS_SCHEMA


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
        help="Random seeds for Monte Carlo runs (default: 0-19, S=20).",
    )
    parser.add_argument(
        "--output", default="policyswarm_output",
        help="Root output directory (default: policyswarm_output).",
    )
    parser.add_argument(
        "--policy-text", default=POLICY_TEXT,
        help="Policy text to ingest.",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print KG extraction summary and exit.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# LaTeX table generation
# ---------------------------------------------------------------------------

def generate_latex_tables(experiment_name: str, output_root: str) -> int:
    """Generate and write LaTeX tables for a completed experiment.

    Returns the number of tables successfully written.

    Bug fixed: geometry previously read *_results_*.csv (raw per-seed rows)
    instead of *_stats_*.csv (group_summary output). summary_table_to_latex
    requires aggregated columns (variance_mean, variance_ci_low, ...) which
    only exist in the stats CSV.
    """
    exp_dir = Path(output_root) / experiment_name

    # ---------------------------------------------------------------
    # GEOMETRY → summary table from *_stats_*.csv (aggregated)
    # ---------------------------------------------------------------
    if experiment_name == "geometry":
        stats_files = list(exp_dir.glob("*_stats_*.csv"))
        if not stats_files:
            raise ValueError(f"No geometry stats CSV found in {exp_dir}")

        df = pd.read_csv(stats_files[-1])

        # Validate schema before attempting LaTeX generation
        GEOMETRY_RESULTS_SCHEMA.validate(df)

        latex = summary_table_to_latex(
            df,
            caption=(
                "Geometry comparison across opinion spaces "
                "(mean $\\pm$ 95\\% CI, $S=20$)."
            ),
            label="tab:geometry",
        )

        out_path = exp_dir / "geometry_table.tex"
        out_path.write_text(latex)
        return 1

    # ---------------------------------------------------------------
    # ALL OTHER EXPERIMENTS → stat table from *_stats_*.csv
    # ---------------------------------------------------------------
    stats_files = list(exp_dir.glob("*_stats_*.csv"))
    if not stats_files:
        raise ValueError(f"No stats CSV found in {exp_dir}")

    stats_df = pd.read_csv(stats_files[-1])

    # Validate schema
    STATS_SCHEMA.validate(stats_df)

    latex = stat_table_to_latex(
        stats_df,
        caption=(
            f"{experiment_name.capitalize()} results "
            f"($S=20$, paired $t$-test, two-sided)."
        ),
        label=f"tab:{experiment_name}",
    )

    out_path = exp_dir / f"{experiment_name}_table.tex"
    out_path.write_text(latex)
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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