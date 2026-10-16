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


# --- Revision round (see analysis_v2.py for the statistics) ----------------

SERIES_ORDER = ("euclidean", "cosine", "manifold")
MODE_TEXT = {"raw": "shared ε", "t0": "matched at start", "run": "matched over run"}


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
                ax.plot(s.pass_rate, s[a2.PRIMARY], STYLES[m], color=COLOURS[m], label=LABELS[m], lw=1.6)
            pts = runs[(runs.space == space) & (runs.d == d) & (runs.target == 0.15)]
            for (m, mode), g in pts.groupby(["metric", "mode"]):
                if mode == "raw":
                    continue
                marker = "o" if mode == "t0" else ("s" if mode == "run" else "D")
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
                ax.set_xlabel("realised pass rate", fontsize=8)
            if c == 0:
                ax.set_ylabel("opinion groups (≥1%)", fontsize=8)
    axes[0, 2].legend(frameon=False, fontsize=7, labelcolor=INK, loc="upper right")
    fig.text(0.5, 0.005, "markers at 15% starting coverage: diamond = Euclidean, circle = matched at start, "
                         "square = matched over run", ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
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
    ax.set_yticks(y, [c.replace("pre-audit fixes: ", "pre-audit ") for c in order.cell], fontsize=6)
    ax.set_xlabel("interaction: Euclidean's lag contrast minus cosine's (positive: cosine attenuates)", fontsize=8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, "fig4_interaction_all_cells")
    plt.close(fig)


def table(path: str, header: list, rows: list, colspec: str):
    lines = [rf"\begin{{tabular}}{{{colspec}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(str(c) for c in row) + r" \\" for row in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    (FIGURES / path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def revision():
    """Every revision-round figure, table and number (needs the *_v2 results)."""
    runs = a2.load_minimal()
    gaps = a2.minimal_gaps(runs)
    gaps.to_csv(RESULTS / "minimal_gaps_v2.csv", index=False)
    prim = gaps[gaps.outcome == a2.PRIMARY]
    for mode, tag in (("raw", "Raw"), ("t0", "Tzero"), ("run", "Run")):
        g = prim[prim["mode"] == mode]
        p = gaps[(gaps.outcome == "pass_rate") & (gaps["mode"] == mode)]
        numbers[f"V{tag}GroupGap"] = f"{g['mean'].abs().median():.2f}"
        numbers[f"V{tag}GroupEquiv"] = f"{int(g.equivalent.sum())}"
        numbers[f"V{tag}PassGap"] = f"{p['mean'].abs().median():.3f}"
        numbers[f"V{tag}PassEquiv"] = f"{int(p.equivalent.sum())}"
    numbers["VCases"] = str(len(prim[prim["mode"] == "run"]))
    for col, tag in (("variance", "Var"), ("radial_var", "Radial"), ("dispersion", "Disp")):
        g = gaps[(gaps.outcome == col) & (gaps["mode"] == "run")]
        numbers[f"VRun{tag}Gap"] = f"{g['mean'].abs().median():.2f}"
        numbers[f"VRun{tag}Equiv"] = f"{int(g.equivalent.sum())}"

    ang = runs[(runs.checkpoint == 2000) & runs.metric.isin(["cosine", "manifold"])]
    numbers["VClipMean"] = f"{100 * ang.clip_rate.mean():.1f}\\%"
    numbers["VClipMax"] = f"{100 * ang.clip_rate.max():.1f}\\%"

    cva = a2.cos_vs_angular(runs)
    cva.to_csv(RESULTS / "cos_vs_angular_v2.csv", index=False)
    t0 = cva[cva["mode"] == "t0"]
    numbers["VCosAngPassMax"] = f"{t0[t0.outcome == 'pass_rate']['mean'].abs().max():.3f}"
    for k, tag in (("clusters", "Own"), ("groups_common", "Common")):
        numbers[f"VCosAng{tag}"] = f"{t0[t0.outcome == k]['mean'].abs().median():.2f}"
        numbers[f"VCosAng{tag}Max"] = f"{t0[t0.outcome == k]['mean'].abs().max():.2f}"

    horizon = a2.horizon_table()
    horizon.to_csv(RESULTS / "horizon_v2.csv", index=False)
    ref = horizon[horizon["mode"] == "reference"].set_index("checkpoint")["unsettled"]
    words = {500: "Five", 1000: "One", 2000: "Two", 4000: "Four"}      # macro names: letters only
    for cp in (500, 2000, 4000):
        numbers[f"VUnsettled{words[cp]}"] = pct(ref.get(cp, float("nan")))
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
    table("table_calibration.tex", ["space", "$d$", "cov.", "metric", r"$\varepsilon$", "error", "iter.", "ok"],
          [[r.space, r.d, f"{r.target:.2f}", LABELS[r.metric], f"{r.eps:.3f}", f"{r.error:+.3f}",
            r.iterations, "yes" if r.within_tol else "no"] for r in cal.itertuples()], "lrrlrrrl")

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
    table("table_crossing.tex", ["gate", "update", "outcome", "log$_2$ gap to Euclidean/Euclidean [95\\% CI]"],
          [[LABELS[r.gate], LABELS[r.step], r.outcome.replace("_", " "), fmt_ci(r._asdict())]
           for r in cross[cross.outcome.isin(["variance", "dispersion", "radial_var", "groups_common"])].itertuples()],
          "lllr")

    if have("minimal_curves_v2.csv"):
        curves_figure(a2.curves(), runs)

    cells = a2.case_cells()
    cells.to_csv(RESULTS / "case_cells_v2.csv", index=False)
    case_forest(cells)
    numbers["VCaseCells"] = str(len(cells))
    numbers["VCasePositive"] = str(int((cells.ci_low > 0).sum()))
    numbers["VCaseNegative"] = str(int((cells.ci_high < 0).sum()))
    numbers["VCaseNull"] = str(int(((cells.ci_low <= 0) & (cells.ci_high >= 0)).sum()))

    def cell(source, text):
        r = cells[(cells.source == source) & (cells.cell == text)]
        return r.iloc[0] if len(r) else None

    named = {
        "Draft": ("backward", "pre-audit fixes: cos=0 rng=0 split=30 trust_centre=0"),
        "DraftFixed": ("backward", "pre-audit fixes: cos=1 rng=1 split=40 trust_centre=0"),
        "DraftTrust": ("backward", "pre-audit fixes: cos=0 rng=0 split=40 trust_centre=1"),
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
            numbers[f"VC{tag}{gtag}Zero"] = f"{r[f'{geom}_effect0']:.4f}"

    # Every trust/anchor cell of the draft's setting and the recommended one.
    import re
    for r in cells[cells.source == "forward"].itertuples():
        mt = re.fullmatch(r"(unit|centred)/(raw|run)/(gated|anchor)/trust:(\w+)", r.cell)
        if not mt or (mt[2], mt[3]) not in (("raw", "gated"), ("run", "anchor")):
            continue
        tag = "VT" + mt[1].title() + mt[2].title() + mt[4].title().replace("_", "")
        numbers[f"{tag}Inter"] = f"{r.interaction:+.3f}"
        numbers[f"{tag}CI"] = f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
        for geom, gtag in (("euclidean", "Euc"), ("cosine", "Cos")):
            numbers[f"{tag}{gtag}Idx"] = f"{getattr(r, geom + '_index40'):.0f}"
            numbers[f"{tag}{gtag}IdxCI"] = (f"[{getattr(r, geom + '_index_lo'):.0f}, "
                                           f"{getattr(r, geom + '_index_hi'):.0f}]")

    trust_cells = cells[cells.cell.str.contains("trust:") & cells.cell.str.startswith(("unit/raw/gated", "centred/raw/gated"))]
    table("table_trust.tex", ["gate", "trust shrinks toward", "Euclidean", "cosine", "interaction [95\\% CI]"],
          [[r.cell.split("/")[0], r.cell.split("trust:")[1].replace("_", " "),
            f"{r.euclidean_index40:.0f}", f"{r.cosine_index40:.0f}",
            f"{r.interaction:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]"] for r in trust_cells.itertuples()],
          "llrrr")
    anchor_cells = cells[cells.cell.str.startswith("centred/run/anchor")]
    table("table_anchors.tex", ["trust shrinks toward", "Euclidean", "cosine", "interaction [95\\% CI]"],
          [[r.cell.split("trust:")[1].replace("_", " "), f"{r.euclidean_index40:.0f}",
            f"{r.cosine_index40:.0f}", f"{r.interaction:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]"]
           for r in anchor_cells.itertuples()], "lrrr")
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
    text = (HERE / "main.tex").read_text(encoding="utf-8")
    used = set(re.findall(r"\\((?:Unit|Centred|Match|V)[A-Za-z0-9]+)", text))
    missing = sorted(used - set(numbers))
    if missing:
        raise SystemExit(f"main.tex uses undefined number macros: {missing}")
    todo = re.findall(r"\\(RESULTS\{[a-z]+\}|ABSTRACT\b|CODEDATA\b)", text)
    if todo:
        print(f"note: main.tex still has placeholders: {todo}")


def main():
    FIGURES.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    coverage_figure()
    print(coverage_table().round(3).to_string(index=False))
    if (RESULTS / "minimal_runs_v2.csv").exists():
        revision()
    write_numbers()


if __name__ == "__main__":
    main()
