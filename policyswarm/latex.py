import pandas as pd

def format_ci(mean, low, high, precision=4):
    return f"{mean:.{precision}f} [{low:.{precision}f}, {high:.{precision}f}]"

def stat_table_to_latex(df: pd.DataFrame, caption: str, label: str) -> str:
    cols = [c for c in df.columns if c not in ["t_stat", "significant"]]

    lines = []
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\begin{tabular}{lccc}")
    lines.append("\\toprule")

    # header
    header = " & ".join(["Condition", "Effect", "95\\% CI", "p-value"]) + " \\\\"
    lines.append(header)
    lines.append("\\midrule")

    for _, row in df.iterrows():
        cond_parts = []
        for col in df.columns:
            if col in ["effect", "p_value", "effect_ci_low", "effect_ci_high", "t_stat", "significant"]:
                continue
            cond_parts.append(f"{col}={row[col]}")

        cond = ", ".join(cond_parts)

        effect = row["effect"]
        ci = f"[{row['effect_ci_low']:.4f}, {row['effect_ci_high']:.4f}]"
        p = row["p_value"]

        lines.append(f"{cond} & {effect:.4f} & {ci} & {p:.2e} \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append("\\end{table}")

    return "\n".join(lines)


def summary_table_to_latex(df: pd.DataFrame, caption: str, label: str) -> str:
    lines = []
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("\\toprule")

    lines.append("Condition & Variance & Polarization & Bifurcation & Phase T \\\\")
    lines.append("\\midrule")

    for _, row in df.iterrows():
        cond = f"{row['geometry']}, α={row['alpha']}"

        var = format_ci(row["variance_mean"], row["variance_ci_low"], row["variance_ci_high"])
        pol = format_ci(row["polarization_mean"], row["polarization_ci_low"], row["polarization_ci_high"])
        bif = format_ci(row["bifurcation_index_mean"], row["bifurcation_index_ci_low"], row["bifurcation_index_ci_high"])
        phase = format_ci(row["phase_t_mean"], row["phase_t_ci_low"], row["phase_t_ci_high"])

        lines.append(f"{cond} & {var} & {pol} & {bif} & {phase} \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append("\\end{table}")

    return "\n".join(lines)


"""
latex = stat_table_to_latex(
    stats_df,
    caption="Effect of enforcement lag on system stability (S=20, paired t-test).",
    label="tab:lag"
)

with open(output_dir / "lag_table.tex", "w") as f:
    f.write(latex)


latex = summary_table_to_latex(
    summary_df,
    caption="Geometry comparison across opinion manifolds (S=20, mean ± 95\\% CI).",
    label="tab:geometry"
)

with open(output_dir / "geometry_table.tex", "w") as f:
    f.write(latex)

\input{results_s20/lag/lag_table.tex}
\input{results_s20/geometry/geometry_table.tex}
"""