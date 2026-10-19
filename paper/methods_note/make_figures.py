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
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import analysis_v2 as a2  # noqa: E402
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


def linkedin_figure():
    """A single-panel, phone-sized version of Fig. 1 (unit cube, d = 4) for posting.

    Same Monte Carlo as Fig. 1; the marked values at eps = 0.5 are computed, not typed."""
    eps, d = 0.5, 4
    grid = np.linspace(0, 1.6, 161)
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100)          # 1080 x 1350 px
    ax = fig.add_axes((0.17, 0.11, 0.77, 0.62))
    at = {}
    for m in ("euclidean", "manifold", "cosine"):
        y = cov.pass_curve(m, "unit", d, grid, n_pairs=200_000, seed=0)
        ax.plot(grid, y, STYLES[m], color=COLOURS[m], lw=4.5 if m != "manifold" else 3.5, label=LABELS[m])
        at[m] = cov.pass_fraction(m, "unit", d, eps, n_pairs=400_000, seed=0)
        ax.plot([eps], [at[m]], "o", ms=16, color=COLOURS[m], mec="#fcfcfb", mew=3, zorder=5)
    ax.axvline(eps, color=MUTED, lw=2)
    ax.text(eps + 0.02, 1.03, "threshold = 0.5", color=MUTED, fontsize=24, va="bottom")
    # angular's label sits in the empty lower right, joined to its point by a leader line
    for m, x, y, ha in (("cosine", eps + 0.05, at["cosine"] - 0.02, "left"),
                        ("manifold", 1.0, at["manifold"], "left"),
                        ("euclidean", eps + 0.05, at["euclidean"] - 0.02, "left")):
        ax.annotate(f"{LABELS[m]}: {100 * at[m]:.0f}%", (eps, at[m]), xytext=(x, y),
                    color=INK, fontsize=32, fontweight="bold" if m != "manifold" else "normal",
                    va="center", ha=ha,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=1.5) if m == "manifold" else None)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.07), ncol=3, frameon=False, fontsize=22,
              labelcolor=INK, handlelength=2.6, columnspacing=1.6)
    ax.set_xlim(0, 1.6)
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xticks([0, 0.5, 1.0, 1.5])
    ax.tick_params(labelsize=24, length=0, pad=10)
    ax.set_xlabel("threshold (each measure in its own units)", fontsize=26, labelpad=14, color=INK)
    ax.set_ylabel("share of pairs allowed to interact", fontsize=26, labelpad=14, color=INK)
    ax.grid(axis="y", color=GRID, lw=1.2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.07, 0.94, "Same threshold, different rules", fontsize=38, fontweight="bold", color=INK)
    fig.text(0.07, 0.897, "One threshold number lets a very different share of", fontsize=25, color=INK)
    fig.text(0.07, 0.867, "opinion pairs interact, depending on how distance", fontsize=25, color=INK)
    fig.text(0.07, 0.837, "is measured (random opinions in four dimensions).", fontsize=25, color=INK)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    fig.savefig(FIGURES / "linkedin_coverage.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    return at


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
            numbers[f"Match{tag}{mtag}"] = f"{cov.matched_epsilon(m, space, 4, 0.15, 400_000):#.3g}"
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"space & $\varepsilon$ & $d$ & Euclidean & cosine & angular \\", r"\midrule"]
    for r in df.itertuples():
        lines.append(f"{r.space} & {r.eps:g} & {r.d} & {pct(r.euclidean)} & "
                     f"{pct(r.cosine)} & {pct(r.manifold)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (FIGURES / "table1_coverage.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return df


# --- Revision round (see analysis_v2.py for the statistics) ----------------

SERIES_ORDER = ("euclidean", "cosine", "manifold")
MODE_TEXT = {"raw": "shared", "t0": "start-matched", "run": "run-matched", "early": "early-matched"}
MODE_TAGS = (("raw", "Raw"), ("t0", "Tzero"), ("run", "Run"), ("early", "Early"))


OUTCOME_LABELS = {"variance": "variance", "radial_var": "radial spread", "dispersion": "directional dispersion",
                  "groups_common": "groups (common ruler)", "eff_groups_common": "effective groups",
                  "converged_at": "convergence time", "pass_rate": "pass rate"}


def fmt_ci(st, digits=2):
    return f"{st['mean']:+.{digits}f} [{st['lo95']:+.{digits}f}, {st['hi95']:+.{digits}f}]"


def curves_figure(curv: pd.DataFrame, runs: pd.DataFrame):
    """Figure 2: primary outcome against realised pass rate, with matched points."""
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.6), sharey=False)
    for r, space in enumerate(("unit", "centred")):
        for c, d in enumerate((2, 4, 8)):
            ax = axes[r, c]
            for m in SERIES_ORDER:
                s = curv[(curv.space == space) & (curv.d == d) & (curv.metric == m)].sort_values("pass_rate")
                ax.fill_between(s.pass_rate, s.groups_lo, s.groups_hi, color=COLOURS[m], alpha=0.15, lw=0)
                ax.plot(s.pass_rate, s[a2.PRIMARY], STYLES[m], color=COLOURS[m], label=LABELS[m], lw=1.6)
            pts = runs[(runs.space == space) & (runs.d == d) & (runs.target == 0.15)]
            for (m, mode), g in pts.groupby(["metric", "mode"]):
                if mode == "raw":
                    continue
                marker = {"t0": "o", "run": "s", "early": "^"}.get(mode, "D")
                ax.plot(g.pass_rate.mean(), g[a2.PRIMARY].mean(), marker, ms=5, color=COLOURS[m],
                        mec="#fcfcfb", mew=0.8)
            ax.set_title(f"{space}, d = {d}", fontsize=8, color=INK)
            ax.set_yscale("log")
            top = ax.get_ylim()[1]
            ax.set_yticks([t for t in (1, 2, 3, 5, 10, 20) if t <= top * 1.05])
            ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
            ax.tick_params(labelsize=7)
            if r == 1:
                ax.set_xlabel("pass rate", fontsize=8)
            if c == 0:
                ax.set_ylabel("opinion groups (≥1%)", fontsize=8)
    axes[0, 2].legend(frameon=False, fontsize=7, labelcolor=INK, loc="upper right")
    fig.text(0.5, 0.005, "markers at 15% starting coverage: diamond = Euclidean, circle = start-matched,\n"
                         "square = run-matched, triangle = early-matched; bands: 95% CI",
             ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    _save(fig, "fig2_response_curves")
    plt.close(fig)


def ruler_figure(cva: pd.DataFrame, horizon: pd.DataFrame):
    """Figure 3: (a) cosine vs angular group gap by ruler; (b) gap and unsettled share by run length."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.7))
    t0 = cva[cva["mode"] == "t0"]
    names = {"clusters_r0.01": "0.01ε", "clusters_r0.05": "0.05ε", "clusters": "0.1ε",
             "clusters_r0.2": "0.2ε", "groups_common": "common"}
    vals = [t0[t0.outcome == k]["mean"].abs().median() for k in names]
    a.bar(range(len(names)), vals, color=COLOURS["euclidean"], width=0.6)
    for k, v in enumerate(vals):
        a.text(k, v + 0.005, f"{v:.2f}", ha="center", fontsize=7, color=INK)
    a.set_xticks(range(len(names)), list(names.values()), fontsize=7)
    a.set_ylabel("median |log₂ gap|, cosine vs angular", fontsize=7)
    a.set_title("(a) one gate, five rulers", fontsize=8, color=INK)
    a.grid(axis="x", visible=False)
    for mode in ("t0", "run"):
        h = horizon[(horizon["mode"] == mode) & (horizon.metric == "cosine")].sort_values("checkpoint")
        b.plot(h.checkpoint, h.median_abs_gap, STYLES["cosine"] if mode == "t0" else "-",
               color=COLOURS["cosine"] if mode == "t0" else COLOURS["manifold"], label=MODE_TEXT[mode])
    e = horizon[(horizon["mode"] == "reference")].sort_values("checkpoint")
    b2 = b.twinx()
    b2.plot(e.checkpoint, e.unsettled, ":", color=MUTED, label="Euclidean runs not settled")
    b2.set_ylim(0, 1)
    b2.set_ylabel("share not settled", fontsize=7, color=MUTED)
    b2.tick_params(labelsize=7, colors=MUTED)
    b.set_xscale("log")
    b.set_xticks([500, 1000, 2000, 4000], ["500", "1k", "2k", "4k"], fontsize=7)
    b.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    b.set_ylim(0, max(1.0, b.get_ylim()[1]))
    b.set_xlabel("rounds", fontsize=8)
    b.set_ylabel("median |log₂ gap| in groups", fontsize=7)
    b.set_title("(b) the stopping time", fontsize=8, color=INK)
    lines = b.get_lines() + b2.get_lines()
    b.legend(lines, [ln.get_label() for ln in lines], frameon=False, fontsize=7,
             labelcolor=INK, loc="lower left")
    fig.tight_layout()
    _save(fig, "fig3_ruler_horizon")
    plt.close(fig)


RULE_WORDS = {"raw": "shared", "matched": "start-matched", "run": "run-matched"}


def cell_label(source: str, cell: str) -> str:
    """Plain-language label for a case configuration."""
    if source == "backward":
        f = dict(kv.split("=") for kv in cell.replace("pre-audit fixes: ", "").split())
        parts = [name for key, on, name in (("cos", "1", "cosine step"), ("rng", "1", "random streams"),
                                             ("split", "40", "tightening tick"),
                                             ("trust_centre", "1", "trust at centre"))
                 if f.get(key) == on]
        return "draft engine" + (" + " + ", ".join(parts) if parts else "")
    space, rule, pull, trust = cell.split("/")
    return (f"{space} gate, {RULE_WORDS.get(rule, rule)}, {pull} pull, "
            f"trust to {trust.split(':')[1].replace('_', ' ')}")


def case_forest(cells: pd.DataFrame):
    """Figure 4: the geometry x lag interaction in every configuration."""
    cells = cells.copy()
    fig, ax = plt.subplots(figsize=(7.0, 0.22 * len(cells) + 1.0))
    order = cells.sort_values(["source", "cell"]).reset_index(drop=True)
    y = np.arange(len(order))[::-1]
    colour = {"forward": COLOURS["euclidean"], "backward": COLOURS["cosine"]}
    for yi, (_, r) in zip(y, order.iterrows()):
        ax.plot([r.ci_low, r.ci_high], [yi, yi], "-", color=colour.get(r.source, MUTED), lw=1.5)
        ax.plot(r.interaction, yi, "o", color=colour.get(r.source, MUTED), ms=4)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(y, [cell_label(r.source, r.cell) for r in order.itertuples()], fontsize=6)
    for lim in (-a2.INTERACTION_MARGIN, a2.INTERACTION_MARGIN):
        ax.axvline(lim, color=MUTED, lw=0.6, ls=":")
    ax.set_xlabel("interaction: cosine's lag contrast minus Euclidean's\n(positive: cosine attenuates the lag effect)",
                  fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, "fig4_interaction_all_cells")
    plt.close(fig)


def table(path: str, header: list, rows: list, colspec: str):
    lines = [rf"\begin{{tabular}}{{{colspec}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(str(c) for c in row) + r" \\" for row in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    (FIGURES / path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def cells_tables(gaps: pd.DataFrame):
    """Appendix: per-cell gaps to Euclidean with 95% CIs, cosine and angular apart."""
    modes = [m for m, _ in MODE_TAGS if (gaps["mode"] == m).any()]
    for outcome, name, digits in (("pass_rate", "table_cells_pass.tex", 3),
                                  (a2.PRIMARY, "table_cells_groups.tex", 2)):
        g = gaps[gaps.outcome == outcome].set_index(a2.CELL + ["metric", "mode"])
        rows = []
        for (space, d, target, metric), _ in g.groupby(level=[0, 1, 2, 3]):
            row = [space, d, f"{target:.2f}", LABELS[metric]]
            for m in modes:
                st = g.loc[(space, d, target, metric, m)]
                row.append(fmt_ci(st, digits) + ("$^{=}$" if st.equivalent else ""))
            rows.append(row)
        table(name, ["space", "$d$", "cov.", "geometry"] + [MODE_TEXT[m] for m in modes], rows,
              "lrrl" + "r" * len(modes))


def secondary_table(gaps: pd.DataFrame):
    """Appendix: secondary outcomes under every threshold rule, cosine and angular
    apart: median signed gap to Euclidean (log2) and cells equivalent to zero."""
    modes = [m for m, _ in MODE_TAGS if (gaps["mode"] == m).any()]
    names = {"variance": "variance", "radial_var": "radial spread", "dispersion": "directional dispersion",
             "eff_groups_common": "effective groups", "converged_at": "convergence time"}
    rows = []
    for outcome, label in names.items():
        for geom in ("cosine", "manifold"):
            g = gaps[(gaps.outcome == outcome) & (gaps.metric == geom)]
            row = [label, LABELS[geom]]
            for m in modes:
                gm = g[g["mode"] == m]
                row.append(f"{gm['mean'].median():+.2f} ({int(gm.equivalent.sum())})")
            rows.append(row)
    table("table_secondary.tex", ["outcome", "geometry"] + [MODE_TEXT[m] for m in modes], rows,
          "ll" + "r" * len(modes))


def secondary_cells_table(gaps: pd.DataFrame):
    """Appendix: per-cell run-matched secondary outcomes with 95% CIs."""
    cols = ["variance", "radial_var", "dispersion", "eff_groups_common", "converged_at"]
    g = gaps[(gaps["mode"] == "run") & gaps.outcome.isin(cols)].set_index(a2.CELL + ["metric", "outcome"])
    rows = []
    for (space, d, target, metric), _ in g.groupby(level=[0, 1, 2, 3]):
        row = [space, d, f"{target:.2f}", LABELS[metric]]
        for o in cols:
            st = g.loc[(space, d, target, metric, o)]
            row.append(fmt_ci(st, 2) + ("$^{=}$" if st.equivalent else ""))
        rows.append(row)
    table("table_secondary_cells.tex", ["space", "$d$", "cov.", "geometry"] + [OUTCOME_LABELS[o] for o in cols],
          rows, "lrrl" + "r" * len(cols))


def settled_table():
    """Appendix: share of runs not settled after 2,000 and 4,000 rounds, and
    median convergence time (censored at 4,000 rounds)."""
    runs = pd.read_csv(RESULTS / "minimal_runs_v2.csv")
    r = runs[runs["mode"].isin(["reference", "run"]) & runs.checkpoint.isin([2000, 4000])]
    u = r.pivot_table(index=a2.CELL + ["metric"], columns="checkpoint", values="settled",
                      aggfunc=lambda x: 1 - x.mean())
    conv = r[r.checkpoint == 4000].groupby(a2.CELL + ["metric"]).converged_at.median()
    rows = []
    for (space, d, target), _ in u.groupby(level=[0, 1, 2]):
        row = [space, d, f"{target:.2f}"]
        for m in SERIES_ORDER:
            k = (space, d, target, m)
            row.append(f"{pct(u.loc[k, 2000])} / {pct(u.loc[k, 4000])}")
        row += [f"{conv.loc[(space, d, target, m)]:.0f}" for m in SERIES_ORDER]
        rows.append(row)
    table("table_settled.tex", ["space", "$d$", "cov."]
          + [f"unsettled {LABELS[m]}" for m in SERIES_ORDER]
          + [f"conv. {LABELS[m]}" for m in SERIES_ORDER], rows, "lrr" + "r" * 6)
    last = r[r.checkpoint == 4000]
    numbers["VUnsettledMaxCell"] = pct(u[2000].max())
    numbers["VUnsettledFourAll"] = pct(1 - last.settled.mean())
    numbers["VConvCensored"] = pct((~last.settled.astype(bool)).mean())


GEOM_TAGS = (("cosine", "Cos"), ("manifold", "Ang"))


def revision():
    """Every revision-round figure, table and number (needs the *_v2 results)."""
    runs = a2.load_minimal()
    gaps = a2.minimal_gaps(runs)
    gaps.to_csv(RESULTS / "minimal_gaps_v2.csv", index=False)
    prim = gaps[gaps.outcome == a2.PRIMARY]
    for mode, tag in MODE_TAGS:
        if not (prim["mode"] == mode).any():
            continue
        g = prim[prim["mode"] == mode]
        p = gaps[(gaps.outcome == "pass_rate") & (gaps["mode"] == mode)]
        numbers[f"V{tag}GroupGap"] = f"{g['mean'].abs().median():.2f}"
        numbers[f"V{tag}GroupEquiv"] = f"{int(g.equivalent.sum())}"
        numbers[f"V{tag}PassGap"] = f"{p['mean'].abs().median():.3f}"
        numbers[f"V{tag}PassEquiv"] = f"{int(p.equivalent.sum())}"
        for geom, gtag in GEOM_TAGS:
            gg, pg = g[g.metric == geom], p[p.metric == geom]
            numbers[f"V{tag}GroupGap{gtag}"] = f"{gg['mean'].abs().median():.2f}"
            numbers[f"V{tag}GroupEquiv{gtag}"] = f"{int(gg.equivalent.sum())}"
            numbers[f"V{tag}PassGap{gtag}"] = f"{pg['mean'].abs().median():.3f}"
            numbers[f"V{tag}PassEquiv{gtag}"] = f"{int(pg.equivalent.sum())}"
    numbers["VCases"] = str(len(prim[prim["mode"] == "run"]))
    numbers["VCellsPerGeom"] = str(len(prim[(prim["mode"] == "run") & (prim.metric == "cosine")]))
    for col, tag in (("variance", "Var"), ("radial_var", "Radial"), ("dispersion", "Disp"),
                     ("eff_groups_common", "EffGroups"), ("converged_at", "Conv")):
        g = gaps[(gaps.outcome == col) & (gaps["mode"] == "run")]
        numbers[f"VRun{tag}Gap"] = f"{g['mean'].abs().median():.2f}"
        numbers[f"VRun{tag}Equiv"] = f"{int(g.equivalent.sum())}"
        for geom, gtag in GEOM_TAGS:
            gg = g[g.metric == geom]
            numbers[f"VRun{tag}Gap{gtag}"] = f"{gg['mean'].abs().median():.2f}"
            numbers[f"VRun{tag}Equiv{gtag}"] = f"{int(gg.equivalent.sum())}"

    ang = runs[(runs.checkpoint == 2000) & runs.metric.isin(["cosine", "manifold"])]
    numbers["VClipMean"] = f"{100 * ang.clip_rate.mean():.1f}\\%"
    numbers["VClipMax"] = f"{100 * ang.clip_rate.max():.1f}\\%"

    cva = a2.cos_vs_angular(runs)
    cva.to_csv(RESULTS / "cos_vs_angular_v2.csv", index=False)
    t0 = cva[cva["mode"] == "t0"]
    numbers["VCosAngPassMax"] = f"{t0[t0.outcome == 'pass_rate']['mean'].abs().max():.3f}"
    for k, tag in (("clusters", "Own"), ("groups_common", "Common"), ("pass_rate", "Pass")):
        if tag != "Pass":
            numbers[f"VCosAng{tag}"] = f"{t0[t0.outcome == k]['mean'].abs().median():.2f}"
            numbers[f"VCosAng{tag}Max"] = f"{t0[t0.outcome == k]['mean'].abs().max():.2f}"
        numbers[f"VCosAng{tag}Equiv"] = str(int(t0[t0.outcome == k].equivalent.sum()))
    numbers["VCosAngCells"] = str(len(t0[t0.outcome == "pass_rate"]))
    ct = t0.set_index(a2.CELL + ["outcome"])
    table("table_cos_ang.tex", ["space", "$d$", "cov.", "pass rate", "groups, common ruler",
                                "groups, own ruler ($0.1" + chr(92) + "varepsilon$)"],
          [[space, d, f"{target:.2f}"]
           + [fmt_ci(ct.loc[(space, d, target, o)], 3 if o == "pass_rate" else 2)
              + ("$^{=}$" if ct.loc[(space, d, target, o)].equivalent else "")
              for o in ("pass_rate", "groups_common", "clusters")]
           for (space, d, target) in sorted({k[:3] for k in ct.index})], "lrrrrr")

    horizon = a2.horizon_table()
    horizon.to_csv(RESULTS / "horizon_v2.csv", index=False)
    ref = horizon[horizon["mode"] == "reference"].set_index("checkpoint")["unsettled"]
    words = {500: "Five", 1000: "One", 2000: "Two", 4000: "Four"}      # macro names: letters only
    for cp in (500, 2000, 4000):
        numbers[f"VUnsettled{words[cp]}"] = pct(ref.get(cp, float("nan")))
    allr = pd.read_csv(RESULTS / "minimal_runs_v2.csv")
    euc = allr[allr.metric == "euclidean"]
    for space, stag in (("unit", "Unit"), ("centred", "Centred")):
        for cp in (500, 2000, 4000):
            sub = euc[(euc.space == space) & (euc.checkpoint == cp)]
            numbers[f"VUnsettled{words[cp]}{stag}"] = pct(1 - sub.settled.mean())
    for cp in (2000, 4000):
        w = euc[euc.checkpoint == cp].pivot_table(index=["d", "target"], columns="space", values="settled",
                                                   aggfunc=lambda x: 1 - x.mean())
        numbers[f"VSettledCellGap{words[cp]}"] = f"{100 * (w.unit - w.centred).abs().max():.0f}"
    for mode, tag in (("t0", "Tzero"), ("run", "Run")):
        h = horizon[(horizon["mode"] == mode) & (horizon.metric == "cosine")].set_index("checkpoint")
        for cp in (500, 4000):
            numbers[f"VHor{tag}{words[cp]}"] = f"{h['median_abs_gap'].get(cp, float('nan')):.2f}"

    ruler_figure(cva, horizon)

    cal = a2.calibration_table()
    numbers["VCalMiss"] = str(int((~cal.within_tol.astype(bool)).sum()))
    numbers["VCalTotal"] = str(len(cal))
    numbers["VCalMaxErr"] = f"{cal['error'].abs().max():.3f}"
    numbers["VCalNonMono"] = str(int((~cal.monotone.astype(bool)).sum()))
    ev = gaps[(gaps.outcome == "pass_rate") & (gaps["mode"] == "run")].set_index(a2.CELL + ["metric"])
    numbers["VCalEvalEquiv"] = str(int(ev.equivalent.sum()))
    allruns = pd.read_csv(RESULTS / "minimal_runs_v2.csv")
    allruns = allruns[(allruns.checkpoint == a2.CHECKPOINT) & allruns["mode"].isin(["run", "reference"])]
    se = allruns.groupby(a2.CELL + ["metric"]).pass_rate.std() / np.sqrt(50)
    numbers["VPilotSEMed"] = f"{se.median():.3f}"
    numbers["VPilotSEMax"] = f"{se.max():.3f}"
    numbers["VCalIterMean"] = f"{cal.iterations.mean():.0f}"
    share = (cal.iterations.sum() * 50 * 2000 + 18 * 50 * 2000) / (12600 * 4000)
    numbers["VCalCostShare"] = pct(share)
    numbers["VCalEvalMax"] = f"{ev['mean'].abs().max():.3f}"
    table("table_calibration.tex", ["space", "$d$", "cov.", "geometry", r"$\varepsilon$", "pilot error",
                                    "iter.", "evaluation gap [95\\% CI]"],
          [[r.space, r.d, f"{r.target:.2f}", LABELS[r.metric], f"{r.eps:#.3g}", f"{r.error:+.3f}",
            int(r.iterations), fmt_ci(ev.loc[(r.space, r.d, r.target, r.metric)], 3)
            + ("" if ev.loc[(r.space, r.d, r.target, r.metric)].equivalent else "$^{\\dagger}$")
            + ("$^{\\ddagger}$" if abs(ev.loc[(r.space, r.d, r.target, r.metric)]["mean"]) > 0.005 else "")
            + ("$^{\\S}$" if abs(r.error) >= 0.0045 else "")]
           for r in cal.itertuples()], "lrrlrrrr")
    t = pd.read_csv(RESULTS / "minimal_thresholds_v2.csv")
    early = t[t["mode"] == "early"]
    numbers["VEarlyCalTotal"] = str(len(early))
    numbers["VEarlyCalMiss"] = str(int((~early.within_tol.astype(bool)).sum()))
    numbers["VEarlyCalMaxErr"] = f"{early['error'].abs().max():.3f}"
    numbers["VCalEvalMiss"] = str(int((~ev.equivalent.astype(bool)).sum()))
    numbers["VCalEvalBeyondTol"] = str(int((ev["mean"].abs() > 0.005).sum()))
    numbers["VCalAtTol"] = str(int((cal["error"].abs() >= 0.0045).sum()))
    for geom, gtag in GEOM_TAGS:
        e = ev.xs(geom, level="metric")
        numbers[f"VCalEvalEquiv{gtag}"] = str(int(e.equivalent.sum()))
    secondary_cells_table(gaps)
    secondary_table(gaps)
    cells_tables(gaps)
    settled_table()

    have = lambda name: (RESULTS / name).exists()  # noqa: E731
    if not have("minimal_crossing_v2.csv"):
        print("note: crossing results not there yet")
        return
    cross = a2.crossing_table()
    cross.to_csv(RESULTS / "crossing_v2.csv", index=False)
    pick = lambda g, s, o: cross[(cross.gate == g) & (cross.step == s) & (cross.outcome == o)].iloc[0]  # noqa: E731
    for g, s, tag in (("cosine", "cosine", "CosCos"), ("cosine", "euclidean", "CosEuc"),
                      ("euclidean", "cosine", "EucCos")):
        for o, otag in (("variance", "Var"), ("radial_var", "Radial"), ("dispersion", "Disp"),
                        ("groups_common", "Groups")):
            numbers[f"VX{tag}{otag}"] = fmt_ci(pick(g, s, o))
    table("table_crossing.tex", ["gate", "update", "outcome", "gap to Euclidean/Euclidean [95\\% CI]"],
          [[LABELS[r.gate], LABELS[r.step], OUTCOME_LABELS[r.outcome], fmt_ci(r._asdict())]
           for r in cross[cross.outcome.isin(["variance", "dispersion", "radial_var", "groups_common"])].itertuples()],
          "lllr")

    if have("minimal_crossing_run_v2.csv"):
        xr = a2.crossing_table("minimal_crossing_run_v2.csv")
        xr.to_csv(RESULTS / "crossing_run_v2.csv", index=False)
        for g, st, tag in (("cosine", "cosine", "CosCos"), ("cosine", "euclidean", "CosEuc")):
            for o, otag in (("variance", "Var"), ("radial_var", "Radial"), ("dispersion", "Disp"),
                            ("groups_common", "Groups")):
                numbers[f"VXR{tag}{otag}"] = fmt_ci(xr[(xr.gate == g) & (xr.step == st) & (xr.outcome == o)].iloc[0])
        table("table_crossing_run.tex", ["gate", "update", "outcome", "gap [95\\% CI]"],
              [[LABELS[r.gate], LABELS[r.step], OUTCOME_LABELS[r.outcome], fmt_ci(r._asdict())]
               for r in xr[xr.outcome.isin(["variance", "radial_var", "dispersion", "groups_common"])].itertuples()],
              "lllr")

    if have("minimal_curves_v2.csv"):
        curves_figure(a2.curves(), runs)

    cells = a2.case_cells()
    cells.to_csv(RESULTS / "case_cells_v2.csv", index=False)
    case_forest(cells)
    numbers["VCaseCells"] = str(len(cells))
    numbers["VCasePositive"] = str(int((cells.ci_low > 0).sum()))
    numbers["VCaseNegative"] = str(int((cells.ci_high < 0).sum()))
    null = (cells.ci_low <= 0) & (cells.ci_high >= 0)
    numbers["VCaseNull"] = str(int(null.sum()))
    numbers["VCaseEquivalent"] = str(int((null & cells.equivalent).sum()))
    numbers["VCaseInconclusive"] = str(int((null & ~cells.equivalent).sum()))
    numbers["VInterMargin"] = f"{a2.INTERACTION_MARGIN:.2f}"
    dm, dlo, dhi, deq = a2.interaction_difference("centred/run/anchor/trust:centre",
                                                  "centred/matched/anchor/trust:centre")
    numbers["VRunVsStartDiff"] = f"{dm:+.3f}"
    numbers["VRunVsStartCI"] = f"[{dlo:+.3f}, {dhi:+.3f}]"
    numbers["VRunVsStartEquiv"] = "equivalent" if deq else "not equivalent"

    def cell(source, text):
        r = cells[(cells.source == source) & (cells.cell == text)]
        return r.iloc[0] if len(r) else None

    named = {
        "Draft": ("backward", "pre-audit fixes: cos=0 rng=0 split=30 trust_centre=0"),
        "DraftFixed": ("backward", "pre-audit fixes: cos=1 rng=1 split=40 trust_centre=0"),
        "DraftTrust": ("backward", "pre-audit fixes: cos=0 rng=0 split=40 trust_centre=1"),
        "DraftSplit": ("backward", "pre-audit fixes: cos=0 rng=0 split=40 trust_centre=0"),
        "DraftCosRng": ("backward", "pre-audit fixes: cos=1 rng=1 split=30 trust_centre=0"),
        "DraftCosRngTrust": ("backward", "pre-audit fixes: cos=1 rng=1 split=30 trust_centre=1"),
        "Recommended": ("forward", "centred/run/anchor/trust:centre"),
        "UnitShared": ("forward", "unit/raw/gated/trust:centre"),
        "UnitRunGated": ("forward", "unit/run/gated/trust:centre"),
    }
    for tag, (src, text) in named.items():
        r = cell(src, text)
        if r is None:
            continue
        numbers[f"VC{tag}Inter"] = f"{r.interaction:+.3f}"
        numbers[f"VC{tag}CI"] = f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
        for geom, gtag in (("euclidean", "Euc"), ("cosine", "Cos")):
            numbers[f"VC{tag}{gtag}Idx"] = (f"{r[f'{geom}_index40']:.0f} "
                                            f"[{r[f'{geom}_index_lo']:.0f}, {r[f'{geom}_index_hi']:.0f}]")
            numbers[f"VC{tag}{gtag}Zero"] = f"{r[f'{geom}_effect0']:.3f}"
            numbers[f"VC{tag}{gtag}AbsIdx"] = f"{r[f'{geom}_abs_index40']:.0f}"
            numbers[f"VC{tag}{gtag}Forty"] = f"{r[f'{geom}_effect40']:.3f}"

    # Forward cells with centre trust: which comparison isolates the threshold (R14).
    for r in cells[(cells.source == "forward") & cells.cell.str.endswith("trust:centre")].itertuples():
        space, rule, pull, _ = r.cell.split("/")
        numbers[f"VF{space.title()}{rule.title()}{pull.title()}Inter"] = f"{r.interaction:+.3f}"

    # Every trust/anchor cell of the draft's setting and the recommended one.
    import re
    for r in cells[cells.source == "forward"].itertuples():
        mt = re.fullmatch(r"(unit|centred)/(raw|run)/(gated|anchor)/trust:(\w+)", r.cell)
        if not mt or (mt[2], mt[3]) not in (("raw", "gated"), ("run", "anchor")):
            continue
        tag = "VT" + mt[1].title() + mt[2].title() + mt[4].title().replace("_", "")
        numbers[f"{tag}Inter"] = f"{r.interaction:+.3f}"
        numbers[f"{tag}CI"] = f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
        numbers[f"{tag}CINinety"] = f"[{r.ci90_low:+.3f}, {r.ci90_high:+.3f}]"
        for geom, gtag in (("euclidean", "Euc"), ("cosine", "Cos")):
            numbers[f"{tag}{gtag}Zero"] = f"{getattr(r, geom + '_effect0'):.3f}"
            numbers[f"{tag}{gtag}Idx"] = f"{getattr(r, geom + '_index40'):.0f}"
            numbers[f"{tag}{gtag}IdxCI"] = (f"[{getattr(r, geom + '_index_lo'):.0f}, "
                                           f"{getattr(r, geom + '_index_hi'):.0f}]")

    def idx(r, geom):
        return (f"{getattr(r, geom + '_index40'):.0f} [{getattr(r, geom + '_index_lo'):.0f}, "
                f"{getattr(r, geom + '_index_hi'):.0f}]")

    def inter(r):
        mark = "$^{=}$" if r.equivalent else ""
        return f"{r.interaction:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]{mark}"

    head = ["Euclidean index", "cosine index", "effect lag 0 / 40, E", "effect lag 0 / 40, C",
            "interaction [95" + chr(92) + "% CI]"]
    trust_cells = cells[cells.cell.str.contains("trust:") & cells.cell.str.startswith(("unit/raw/gated", "centred/raw/gated"))]
    table("table_trust.tex", ["gate", "trust target"] + head,
          [[r.cell.split("/")[0], r.cell.split("trust:")[1].replace("_", " "), idx(r, "euclidean"),
            idx(r, "cosine"), f"{r.euclidean_effect0:.3f} / {r.euclidean_effect40:.3f}",
            f"{r.cosine_effect0:.3f} / {r.cosine_effect40:.3f}", inter(r)]
           for r in trust_cells.itertuples()], "llrrrrr")
    anchor_cells = cells[cells.cell.str.startswith("centred/run/anchor")]
    table("table_anchors.tex", ["trust target"] + head,
          [[r.cell.split("trust:")[1].replace("_", " "), idx(r, "euclidean"), idx(r, "cosine"),
            f"{r.euclidean_effect0:.3f} / {r.euclidean_effect40:.3f}",
            f"{r.cosine_effect0:.3f} / {r.cosine_effect40:.3f}", inter(r)]
           for r in anchor_cells.itertuples()], "lrrrrr")
    numbers["VTargetEucMin"] = f"{anchor_cells.euclidean_index40.min():.0f}"
    numbers["VTargetEucMax"] = f"{anchor_cells.euclidean_index40.max():.0f}"
    for r in anchor_cells.itertuples():
        a = r.cell.split("trust:")[1]
        numbers[f"VAnchor{a.title().replace('_', '')}Inter"] = f"{r.interaction:+.3f}"
    print(cells[["source", "cell", "interaction", "ci_low", "ci_high"]].round(3).to_string(index=False))


def write_numbers():
    bad = [k for k in numbers if not k.isalpha()]
    if bad:
        raise SystemExit(f"number macro names must be letters only: {bad}")
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(numbers.items())]
    (HERE / "numbers.tex").write_text("% Written by make_figures.py; do not edit.\n"
                                      + "\n".join(lines) + "\n", encoding="utf-8")
    # Every number macro the text uses must be one this script defines.
    import re
    for name in ("main.tex", "main_short.tex"):     # full and short versions
        if not (HERE / name).exists():
            continue
        text = (HERE / name).read_text(encoding="utf-8")
        used = set(re.findall(r"\\((?:Unit|Centred|Match|V)[A-Za-z0-9]+)", text))
        missing = sorted(used - set(numbers))
        if missing:
            raise SystemExit(f"{name} uses undefined number macros: {missing}")
        todo = re.findall(r"\\(RESULTS\{[a-z]+\}|ABSTRACT\b|CODEDATA\b)", text)
        if todo:
            print(f"note: {name} still has placeholders: {todo}")


def main():
    FIGURES.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    coverage_figure()
    linkedin_figure()           # post-sized version of Fig. 1
    print(coverage_table().round(3).to_string(index=False))
    if (RESULTS / "minimal_runs_v2.csv").exists():
        revision()
    write_numbers()


if __name__ == "__main__":
    main()
