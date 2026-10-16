"""
Regenerate every figure and every number in the methods note.

    python make_figures.py

Reads ``results/*.csv`` (written by run_minimal.py and run_policyswarm.py),
computes the coverage curves directly, and writes ``figures/*.pdf`` and
``numbers.tex`` (one LaTeX macro per number quoted in the text, so nothing
in the prose is typed by hand).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import coverage as cov  # noqa: E402

HERE = Path(__file__).parent
RESULTS = HERE / "results"
FIGURES = HERE / "figures"

# Categorical slots 1-3 of the reference palette (validated, light mode).
# Aqua is below 3:1 on the surface, so every series also gets a direct label
# and its own line style.
COLOURS = {"euclidean": "#2a78d6", "cosine": "#eb6834", "manifold": "#1baf7a"}
STYLES = {"euclidean": "-", "cosine": "--", "manifold": ":"}
LABELS = {"euclidean": "Euclidean", "cosine": "cosine", "manifold": "angular"}
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
# Where each direct label sits: (height on the curve, side of the curve).
LABEL_SPOTS = {
    "unit": {"cosine": (0.6, "right"), "manifold": (0.9, "left"), "euclidean": (0.15, "right")},
    "centred": {"cosine": (0.6, "left"), "manifold": (0.9, "right"), "euclidean": (0.15, "right")},
}

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 2, "figure.dpi": 150,
})

numbers: dict[str, str] = {}


def _save(fig, name: str):
    """PDF for the paper, PNG for previews."""
    fig.savefig(FIGURES / f"{name}.pdf")
    fig.savefig(FIGURES / f"{name}.png", dpi=200)


def pct(x: float) -> str:
    return f"{100 * x:.0f}\\%"


# --- Figure 1 and Table 1: coverage --------------------------------------

def coverage_figure():
    """Pass fraction against eps for d = 4, unit and centred spaces."""
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.6), sharey=True)
    for ax, space in zip(axes, cov.SPACES):
        top = 2.2 if space == "unit" else 3.2
        grid = np.linspace(0, top, 221)
        for m in cov.METRICS:
            y = cov.pass_curve(m, space, 4, grid, n_pairs=200_000, seed=0)
            ax.plot(grid, y, STYLES[m], color=COLOURS[m], label=LABELS[m])
            height, side = LABEL_SPOTS[space][m]
            k = int(np.argmin(np.abs(y - height)))
            ax.annotate(LABELS[m], (grid[k], y[k]), xytext=(5 if side == "right" else -5, 0),
                        textcoords="offset points", color=INK, fontsize=8, va="center",
                        ha="left" if side == "right" else "right")
        ref = 0.5 if space == "unit" else 1.0
        ax.axvline(ref, color=MUTED, lw=0.8)
        ax.set_title(f"{'unit cube $[0,1]^4$' if space == 'unit' else 'centred cube $[-1,1]^4$'}",
                     color=INK, fontsize=9)
        ax.set_xlabel(r"threshold $\varepsilon$ (in each metric's own units)")
        ax.set_xlim(0, top)
        ax.set_ylim(0, 1.02)
    axes[0].set_ylabel("share of pairs within $\\varepsilon$")
    axes[1].legend(loc="lower right", frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    _save(fig, "fig1_coverage")
    plt.close(fig)


def coverage_table():
    """Share of pairs admitted at one shared eps, by space and dimension."""
    rows = []
    for space, eps in (("unit", 0.5), ("centred", 1.0)):
        for d in (2, 4, 8, 16):
            row = {"space": space, "d": d, "eps": eps}
            for m in cov.METRICS:
                row[m] = cov.pass_fraction(m, space, d, eps, n_pairs=400_000, seed=0)
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "coverage_table.csv", index=False)
    u4 = df[(df.space == "unit") & (df.d == 4)].iloc[0]
    numbers.update(UnitFourEuc=pct(u4.euclidean), UnitFourCos=pct(u4.cosine),
                   UnitFourAng=pct(u4.manifold))
    u16 = df[(df.space == "unit") & (df.d == 16)].iloc[0]
    numbers.update(UnitSixteenEuc=f"{100 * u16.euclidean:.1f}\\%",
                   UnitSixteenCos=f"{100 * u16.cosine:.1f}\\%")
    c = df[df.space == "centred"]
    numbers.update(CentredCosMin=pct(c.cosine.min()), CentredCosMax=pct(c.cosine.max()),
                   CentredEucTwo=pct(c[c.d == 2].euclidean.iloc[0]),
                   CentredEucEight=f"{100 * c[c.d == 8].euclidean.iloc[0]:.1f}\\%")
    # Thresholds that admit 15% of pairs, d = 4.
    for space, tag in (("unit", "Unit"), ("centred", "Centred")):
        for m, mtag in (("euclidean", "Euc"), ("cosine", "Cos"), ("manifold", "Ang")):
            numbers[f"Match{tag}{mtag}"] = f"{cov.matched_epsilon(m, space, 4, 0.15, 400_000):.2f}"
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"space & $\varepsilon$ & $d$ & Euclidean & cosine & angular \\", r"\midrule"]
    for r in df.itertuples():
        lines.append(f"{r.space} & {r.eps:g} & {r.d} & {pct(r.euclidean)} & "
                     f"{pct(r.cosine)} & {pct(r.manifold)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (FIGURES / "table1_coverage.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return df


# --- Minimal model --------------------------------------------------------

MODES = ("raw", "t0", "run")
MODE_LABELS = {"raw": "same\nnumber", "t0": "matched\nat $t=0$", "run": "matched\nover run"}
OUTCOMES = {"pass_rate": "realised pass rate", "variance": "final variance",
            "eff_clusters": "effective no. of groups"}
CELL = ["space", "d", "target"]


def minimal_gaps(runs: pd.DataFrame) -> pd.DataFrame:
    """Per cell, metric and rule: mean paired gap to Euclidean, with a t-test.

    pass_rate gaps are differences; variance and group-count gaps are log2
    ratios, so a gap of 1 means twice Euclidean's value.
    """
    from scipy.stats import ttest_1samp

    euc = runs[runs.metric == "euclidean"].set_index(CELL + ["seed"])
    rows = []
    for (space, d, target, metric, mode), g in runs[runs.metric != "euclidean"].groupby(
            CELL + ["metric", "mode"]):
        g = g.set_index(CELL + ["seed"])
        base = euc.loc[g.index]
        row = {"space": space, "d": d, "target": target, "metric": metric, "mode": mode,
               "eps": g["eps"].iloc[0], "pass_rate": g["pass_rate"].mean(),
               "pass_rate_euc": base["pass_rate"].mean()}
        for col in OUTCOMES:
            if col == "pass_rate":
                diff = g[col] - base[col]
            else:
                diff = np.log2(g[col].clip(lower=1e-12) / base[col].clip(lower=1e-12))
            row[f"gap_{col}"] = diff.mean()
            row[f"p_{col}"] = ttest_1samp(diff, 0.0).pvalue if diff.std() > 0 else 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def minimal_figure(gaps: pd.DataFrame):
    """Strip plot: gap to Euclidean under each threshold rule, one dot per cell."""
    fig, axes = plt.subplots(1, len(OUTCOMES), figsize=(6.8, 2.6))
    rng = np.random.default_rng(0)
    for ax, (col, title) in zip(axes, OUTCOMES.items()):
        for k, mode in enumerate(MODES):
            for j, metric in enumerate(("cosine", "manifold")):
                y = gaps[(gaps["mode"] == mode) & (gaps.metric == metric)][f"gap_{col}"]
                x = k + (j - 0.5) * 0.3 + rng.uniform(-0.06, 0.06, len(y))
                ax.plot(x, y, "o" if metric == "cosine" else "^", ms=3.5, alpha=0.8,
                        color=COLOURS[metric], mec="#fcfcfb", mew=0.5,
                        label=LABELS[metric] if k == 0 else None)
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.set_xticks(range(len(MODES)), [MODE_LABELS[m] for m in MODES], fontsize=8)
        ax.set_ylabel("difference" if col == "pass_rate" else "log$_2$ ratio", fontsize=8)
        ax.set_title(title, color=INK, fontsize=9)
        ax.grid(axis="x", visible=False)
    fig.suptitle("Gap to Euclidean, one mark per cell", fontsize=9, color=INK, y=0.99)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    _save(fig, "fig2_minimal_gaps")
    plt.close(fig)


def minimal_numbers(gaps: pd.DataFrame):
    names = {"raw": "Raw", "t0": "Tzero", "run": "Run"}
    for mode in MODES:
        g = gaps[gaps["mode"] == mode]
        n = names[mode]
        numbers[f"Min{n}PassGap"] = f"{g['gap_pass_rate'].abs().median():.2f}"
        numbers[f"Min{n}VarGap"] = f"{g['gap_variance'].abs().median():.2f}"
        numbers[f"Min{n}GroupGap"] = f"{g['gap_eff_clusters'].abs().median():.2f}"
        numbers[f"Min{n}GroupGapMax"] = f"{g['gap_eff_clusters'].abs().max():.1f}"
        numbers[f"Min{n}VarGapMin"] = f"{g['gap_variance'].min():+.2f}"
        numbers[f"Min{n}VarGapMax"] = f"{g['gap_variance'].max():+.2f}"
        # Share of (cell, metric) rows whose group-count gap is under a third (|log2| < 0.5).
        numbers[f"Min{n}GroupClose"] = pct((g['gap_eff_clusters'].abs() < 0.5).mean())
    numbers["MinCells"] = str(gaps.groupby(CELL).ngroups)
    # Matched cosine vs angular: same pairs at t = 0, so differences are the update rule's.
    t0 = gaps[gaps["mode"] == "t0"].pivot_table(index=CELL, columns="metric",
                                               values=["pass_rate", "gap_variance"])
    numbers["MinCosAngPassDiff"] = (
        f"{(t0['pass_rate']['cosine'] - t0['pass_rate']['manifold']).abs().max():.3f}")
    ex = gaps[(gaps.space == "centred") & (gaps.d == 4) & (gaps.target == 0.15)
              & (gaps["mode"] == "t0") & (gaps.metric == "cosine")].iloc[0]
    numbers.update(DriftEuc=pct(ex.pass_rate_euc), DriftCos=pct(ex.pass_rate))
    numbers["MinCosAngVarDiff"] = (
        f"{(t0['gap_variance']['cosine'] - t0['gap_variance']['manifold']).abs().median():.2f}")


# --- PolicySwarm case -----------------------------------------------------

CASE_MODES = ("raw", "matched", "run")
CASE_MODE_LABELS = {"raw": "shared", "matched": "$t{=}0$", "run": "run"}
CASE_TABLE_LABELS = {"raw": "shared", "matched": "matched $t{=}0$", "run": "matched run"}


def load_case():
    """Runs and interaction tables from the main factorial and the run-matched arm."""
    runs = [pd.read_csv(f) for f in sorted(RESULTS.glob("policyswarm_runs*.csv"))]
    inter = [pd.read_csv(f) for f in sorted(RESULTS.glob("policyswarm_interactions*.csv"))]
    return pd.concat(runs, ignore_index=True), pd.concat(inter, ignore_index=True)


def case_summary(runs: pd.DataFrame, inter: pd.DataFrame) -> pd.DataFrame:
    """One row per corner: the draft's lag index, realised pass rates, interaction."""
    keys = ["gate_space", "eps_mode", "policy_pull"]
    rows = []
    for key, g in runs.groupby(keys):
        row = dict(zip(keys, key))
        for geom, gg in g.groupby("geometry"):
            m = gg.groupby("lag")["delta"].mean()
            row[f"{geom}_index40"] = 100 * abs(m[40]) / abs(m[0])
            row[f"{geom}_pass"] = gg["gate_pass_ctrl"].mean()
            row[f"{geom}_eps"] = gg["epsilon"].iloc[0]
        it = inter[(inter["value"] == "rel_delta")
                   & (inter[keys] == pd.Series(row)[keys]).all(axis=1)].iloc[0]
        row.update({c: it[c] for c in ("euclidean_contrast", "cosine_contrast", "euclidean_trend",
                                       "cosine_trend", "interaction", "ci_low", "ci_high",
                                       "p_value")})
        rows.append(row)
    return pd.DataFrame(rows)


def case_figure(summary: pd.DataFrame):
    """Lag index (draft's measure: |shock effect| at lag 40, lag 0 = 100) per corner."""
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.8), sharey=True)
    for ax, space in zip(axes, ("unit", "centred")):
        groups = [(m, p) for m in CASE_MODES for p in ("gated", "anchor")]
        for k, (mode, pull) in enumerate(groups):
            row = summary[(summary.gate_space == space) & (summary.eps_mode == mode)
                          & (summary.policy_pull == pull)]
            if row.empty:
                continue
            row = row.iloc[0]
            for j, metric in enumerate(("euclidean", "cosine")):
                ax.bar(k + (j - 0.5) * 0.38, row[f"{metric}_index40"] - 100, bottom=100,
                       width=0.36, color=COLOURS[metric],
                       label=LABELS[metric] if (k == 0 and space == "centred") else None)
        ax.axhline(100, color="#c3c2b7", lw=1)
        ax.set_xticks(range(len(groups)),
                      [f"{CASE_MODE_LABELS[m]}\n{p}" for m, p in groups], fontsize=7)
        ax.set_title("pre-audit space (unit)" if space == "unit" else "centred space",
                     color=INK, fontsize=9)
        ax.set_xlabel("threshold (shared / matched at $t{=}0$ / matched over run)\n"
                      "and policy pull (gated / anchor)", fontsize=7, color=MUTED)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("shock effect at lag 40\n(lag 0 = 100)")
    axes[1].legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    _save(fig, "fig3_case_factorial")
    plt.close(fig)


def case_table(summary: pd.DataFrame):
    lines = [r"\begin{tabular}{lllrrrrl}", r"\toprule",
             r"space & $\varepsilon$ & pull & \multicolumn{2}{c}{pass rate (E / C)} & "
             r"\multicolumn{2}{c}{lag-40 index (E / C)} & interaction [95\% CI] \\", r"\midrule"]
    order = {"unit": 0, "centred": 1, "raw": 0, "matched": 1, "run": 2, "gated": 0, "anchor": 1}
    rows = summary.sort_values(["gate_space", "eps_mode", "policy_pull"],
                               key=lambda c: c.map(order))
    for r in rows.itertuples():
        lines.append(
            f"{r.gate_space} & {CASE_TABLE_LABELS[r.eps_mode]} & {r.policy_pull} & "
            f"{r.euclidean_pass:.2f} & {r.cosine_pass:.2f} & "
            f"{r.euclidean_index40:.0f} & {r.cosine_index40:.0f} & "
            f"{r.interaction:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}] \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (FIGURES / "table2_case.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def case_numbers(summary: pd.DataFrame):
    tags = {"unit": "Unit", "centred": "Centred", "raw": "Raw", "matched": "Tzero", "run": "Run",
            "gated": "Gated", "anchor": "Anchor"}
    for r in summary.itertuples():
        t = f"Case{tags[r.gate_space]}{tags[r.eps_mode]}{tags[r.policy_pull]}"
        numbers[f"{t}EucIdx"] = f"{r.euclidean_index40:.0f}"
        numbers[f"{t}CosIdx"] = f"{r.cosine_index40:.0f}"
        numbers[f"{t}EucPass"] = pct(r.euclidean_pass)
        numbers[f"{t}CosPass"] = pct(r.cosine_pass)
        numbers[f"{t}Inter"] = f"{r.interaction:+.3f}"
        numbers[f"{t}P"] = f"{r.p_value:.2g}"


# --- Diagnosis on the pre-audit engine ------------------------------------

def diagnosis_numbers():
    """Lag-40 index under each combination of undone fixes (diagnose_reversal.py)."""
    files = [RESULTS / "diagnosis_lag_index.csv", RESULTS / "diagnosis_lag_index_trust.csv"]
    if not all(f.exists() for f in files):
        return
    d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    if "trust_centre" not in d:
        d["trust_centre"] = 0
    d["trust_centre"] = d["trust_centre"].fillna(0).astype(int)

    def idx(fc, fr, sp, tc, geom):
        r = d[(d.fix_cosine == fc) & (d.fix_rng == fr) & (d.split_tick == sp)
              & (d.trust_centre == tc) & (d.geometry == geom)]
        return float(r["lag40"].iloc[0])

    numbers.update(
        DiagOrigEuc=f"{idx(0, 0, 40, 0, 'euclidean'):.0f}",
        DiagOrigCos=f"{idx(0, 0, 40, 0, 'cosine'):.0f}",
        DiagTrustEuc=f"{idx(0, 0, 40, 1, 'euclidean'):.0f}",
        DiagTrustCos=f"{idx(0, 0, 40, 1, 'cosine'):.0f}",
        DiagAllEuc=f"{idx(1, 1, 30, 1, 'euclidean'):.0f}",
        DiagAllCos=f"{idx(1, 1, 30, 1, 'cosine'):.0f}",
    )
    fixes = d[d.trust_centre == 0]
    cos, euc = fixes[fixes.geometry == "cosine"], fixes[fixes.geometry == "euclidean"]
    numbers.update(DiagFixCosLo=f"{cos.lag40.min():.0f}", DiagFixCosHi=f"{cos.lag40.max():.0f}",
                   DiagFixEucLo=f"{euc.lag40.min():.0f}", DiagFixEucHi=f"{euc.lag40.max():.0f}")


def write_numbers():
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(numbers.items())]
    (HERE / "numbers.tex").write_text("% Written by make_figures.py; do not edit.\n"
                                      + "\n".join(lines) + "\n", encoding="utf-8")
    # Every number macro the text uses must be one this script defines.
    import re
    text = (HERE / "main.tex").read_text(encoding="utf-8")
    used = set(re.findall(r"\\((?:Unit|Centred|Match|Min|Drift|Case|Diag)[A-Za-z]+)", text))
    missing = sorted(used - set(numbers))
    if missing:
        raise SystemExit(f"main.tex uses undefined number macros: {missing}")


def main():
    FIGURES.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    coverage_figure()
    print(coverage_table().round(3).to_string(index=False))
    if (RESULTS / "minimal_runs.csv").exists():
        gaps = minimal_gaps(pd.read_csv(RESULTS / "minimal_runs.csv"))
        gaps.to_csv(RESULTS / "minimal_gaps.csv", index=False)
        minimal_figure(gaps)
        minimal_numbers(gaps)
    if (RESULTS / "policyswarm_interactions.csv").exists():
        summary = case_summary(*load_case())
        summary.to_csv(RESULTS / "policyswarm_summary.csv", index=False)
        print(summary.round(3).to_string(index=False))
        case_figure(summary)
        case_table(summary)
        case_numbers(summary)
    diagnosis_numbers()
    write_numbers()


if __name__ == "__main__":
    main()
