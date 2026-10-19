"""
Revision-round analyses for the methods note (called by make_figures.py).

Inputs (results/): minimal_runs_v2, minimal_thresholds_v2, minimal_curves_v2,
minimal_crossing_v2, policyswarm_runs{,_run,_trust_v2,_anchors_v2},
diagnosis_runs{,_trust}.

Statistics are fixed before the data are read:
* every gap is paired by seed; 95% CIs are paired bootstrap percentiles
  (2,000 resamples, fixed seed);
* equivalence (TOST at alpha = 0.05) holds when the 90% bootstrap interval
  lies inside the margin: |difference in pass rate| < 0.02, or
  |log2 ratio| < 0.25 for every other outcome;
* the primary minimal-model outcome is the number of opinion groups holding at
  least 1% of agents, counted with ONE ruler for every metric (Euclidean
  distance in centred coordinates, radius 5% of the cube's diagonal), at the
  2,000-round checkpoint (the horizon the run-matching was calibrated on).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from policyswarm.analysis import lag_geometry_interaction

RESULTS = Path(__file__).parent / "results"
CELL = ["space", "d", "target"]
B = 2000
BOOT_SEED = 20261016
MARGIN = {"pass_rate": 0.02, "dispersion": 0.02}
# Shares on [0, 1] that can be near zero are compared as differences, not log ratios.
DIFFERENCE_OUTCOMES = ("pass_rate", "dispersion")
DEFAULT_MARGIN = 0.25
PRIMARY = "groups_common"
CHECKPOINT = 2000
OUTCOMES = ["pass_rate", "groups_common", "eff_groups_common", "clusters", "eff_clusters",
            "variance", "radial_var", "dispersion", "converged_at"]
RULERS = ["clusters_r0.01", "clusters_r0.05", "clusters", "clusters_r0.2", "groups_common"]


def _diff(a, b, col):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if col in DIFFERENCE_OUTCOMES:
        return a - b
    return np.log2(np.clip(a, 1e-9, None) / np.clip(b, 1e-9, None))


def boot(x: np.ndarray):
    """Mean, 95% and 90% paired-bootstrap intervals of a per-seed difference."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return dict(mean=float("nan"), lo95=float("nan"), hi95=float("nan"),
                    lo90=float("nan"), hi90=float("nan"))
    # A fresh, fixed-seed generator per call: an interval depends only on its
    # own data, not on how many intervals were computed before it.
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(x), size=(B, len(x)))
    means = x[idx].mean(axis=1)
    return dict(mean=float(x.mean()),
                lo95=float(np.percentile(means, 2.5)), hi95=float(np.percentile(means, 97.5)),
                lo90=float(np.percentile(means, 5)), hi90=float(np.percentile(means, 95)))


def equivalent(stats, col):
    m = MARGIN.get(col, DEFAULT_MARGIN)
    return bool(-m < stats["lo90"] and stats["hi90"] < m)


# --- minimal model ----------------------------------------------------------

def load_minimal(checkpoint=CHECKPOINT):
    runs = pd.read_csv(RESULTS / "minimal_runs_v2.csv")
    return runs[runs.checkpoint == checkpoint]


def minimal_gaps(runs: pd.DataFrame) -> pd.DataFrame:
    """Per cell x metric x rule x outcome: paired gap to Euclidean, CIs, TOST."""
    euc = runs[runs.metric == "euclidean"].set_index(CELL + ["seed"])
    rows = []
    for key, g in runs[runs.metric != "euclidean"].groupby(CELL + ["metric", "mode"]):
        g = g.set_index(CELL + ["seed"])
        base = euc.loc[g.index]
        for col in OUTCOMES + [r for r in RULERS if r not in OUTCOMES]:
            if col not in g.columns:
                continue
            st = boot(_diff(g[col], base[col], col))
            rows.append({**dict(zip(CELL + ["metric", "mode"], key)), "outcome": col, **st,
                         "equivalent": equivalent(st, col)})
    return pd.DataFrame(rows)


def cos_vs_angular(runs: pd.DataFrame) -> pd.DataFrame:
    """Cosine vs angular under each rule and ruler: their gates admit the same
    pairs once matched, so any gap is the update step or the ruler."""
    rows = []
    for key, g in runs[runs.metric != "euclidean"].groupby(CELL + ["mode"]):
        c = g[g.metric == "cosine"].set_index("seed")
        a = g[g.metric == "manifold"].set_index("seed").loc[c.index]
        for col in RULERS + ["pass_rate"]:
            st = boot(_diff(c[col], a[col], col))
            rows.append({**dict(zip(CELL + ["mode"], key)), "outcome": col, **st,
                         "equivalent": equivalent(st, col)})
    return pd.DataFrame(rows)


def horizon_table() -> pd.DataFrame:
    """Share of runs not yet settled, and the primary gap, at each checkpoint."""
    runs = pd.read_csv(RESULTS / "minimal_runs_v2.csv")
    rows = []
    for cp, r in runs.groupby("checkpoint"):
        unsettled = r.groupby(["metric", "mode"])["settled"].apply(lambda s: 1 - s.mean())
        gaps = minimal_gaps(r)
        prim = gaps[gaps.outcome == PRIMARY]
        for (metric, mode), u in unsettled.items():
            sub = prim[(prim.metric == metric) & (prim["mode"] == mode)]
            rows.append({"checkpoint": cp, "metric": metric, "mode": mode, "unsettled": float(u),
                         "median_abs_gap": float(sub["mean"].abs().median()) if len(sub) else np.nan,
                         "share_equivalent": float(sub.equivalent.mean()) if len(sub) else np.nan})
    return pd.DataFrame(rows)


def calibration_table() -> pd.DataFrame:
    t = pd.read_csv(RESULTS / "minimal_thresholds_v2.csv")
    return t[t["mode"] == "run"][CELL + ["metric", "eps", "achieved", "error", "iterations",
                                         "within_tol", "monotone"]]


def crossing_table(name: str = "minimal_crossing_v2.csv") -> pd.DataFrame:
    """Gate x update rule: gaps to the pure Euclidean pairing, paired by seed.

    A file without Euclidean/Euclidean rows (the run-matched rerun) is compared
    with the base pairing of the start-matched file: the same seeds and cells."""
    x = pd.read_csv(RESULTS / name)
    if not ((x.gate == "euclidean") & (x.step == "euclidean")).any():
        b = pd.read_csv(RESULTS / "minimal_crossing_v2.csv")
        x = pd.concat([x, b[(b.gate == "euclidean") & (b.step == "euclidean")]], ignore_index=True)
    base = x[(x.gate == "euclidean") & (x.step == "euclidean")].set_index(CELL + ["seed"])
    rows = []
    for key, g in x.groupby(["gate", "step"]):
        if key == ("euclidean", "euclidean"):
            continue
        g = g.set_index(CELL + ["seed"])
        b = base.loc[g.index]
        for col in ("variance", "radial_var", "dispersion", "groups_common", "pass_rate"):
            st = boot(_diff(g[col], b[col], col))
            rows.append({"gate": key[0], "step": key[1], "outcome": col, **st,
                         "equivalent": equivalent(st, col)})
    return pd.DataFrame(rows)


def curves() -> pd.DataFrame:
    c = pd.read_csv(RESULTS / "minimal_curves_v2.csv")
    keys = ["space", "d", "metric", "start_coverage"]
    out = c.groupby(keys)[["pass_rate", "groups_common", "eff_groups_common", "variance",
                           "radial_var", "dispersion"]].mean().reset_index()
    sem = c.groupby(keys)["groups_common"].sem().reset_index(drop=True)
    out["groups_lo"] = (out["groups_common"] - 1.96 * sem).clip(lower=1.0)
    out["groups_hi"] = out["groups_common"] + 1.96 * sem
    out["n_seeds"] = c.groupby(keys).size().reset_index(drop=True)
    return out


# --- case study ---------------------------------------------------------------

def _rel(df):
    df = df.copy()
    if "rel_delta" not in df.columns:
        df["rel_delta"] = df["delta"] / df["control_var"]
    return df


def _index_ci(g, lag, col="rel_delta"):
    """Lag-`lag` index (|mean effect| at lag / at lag 0, x100) with a paired bootstrap CI.

    The effect is the relative shock effect by default (the paper's lag index);
    col="delta" gives the draft's index on the absolute shock effect."""
    w = g.pivot_table(index="seed", columns="lag", values=col)
    d0, dl = w[0].to_numpy(), w[lag].to_numpy()
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(d0), size=(B, len(d0)))
    vals = 100 * np.abs(dl[idx].mean(axis=1)) / np.abs(d0[idx].mean(axis=1))
    return (100 * abs(dl.mean()) / abs(d0.mean()), float(np.percentile(vals, 2.5)),
            float(np.percentile(vals, 97.5)), float(d0.mean()), float(dl.mean()))


# Equivalence margin for the case interaction (relative shock effect units),
# fixed before the round-3 analysis: about a third of the recommended design's
# interaction (+0.034).
INTERACTION_MARGIN = 0.01


def _interaction_ci90(g):
    """90% t interval of the paired interaction (cosine's lag contrast minus
    Euclidean's, relative shock effect, lag 40 vs 0), for the equivalence test."""
    from scipy import stats
    w = g.pivot_table(index="seed", columns=["geometry", "lag"], values="rel_delta")
    c = ((w[("cosine", 40)] - w[("cosine", 0)])
         - (w[("euclidean", 40)] - w[("euclidean", 0)])).dropna().to_numpy()
    half = stats.t.ppf(0.95, len(c) - 1) * c.std(ddof=1) / np.sqrt(len(c))
    return float(c.mean() - half), float(c.mean() + half)


def interaction_difference(cell_a: str, cell_b: str):
    """Paired per-seed difference between the interactions of two case cells that
    share seeds (mean, 90% t interval, equivalence within INTERACTION_MARGIN)."""
    from scipy import stats
    f = pd.concat([pd.read_csv(x) for x in sorted(RESULTS.glob("policyswarm_runs*.csv"))], ignore_index=True)
    f = _rel(f)
    if "trust_anchor" not in f.columns:
        f["trust_anchor"] = "centre"
    f["trust_anchor"] = f["trust_anchor"].fillna("centre")
    f = f.drop_duplicates(["gate_space", "eps_mode", "policy_pull", "trust_anchor", "geometry", "lag", "seed"])
    f["cell"] = f.gate_space + "/" + f.eps_mode + "/" + f.policy_pull + "/trust:" + f.trust_anchor

    def per_seed(cell):
        w = f[f.cell == cell].pivot_table(index="seed", columns=["geometry", "lag"], values="rel_delta")
        return (w[("cosine", 40)] - w[("cosine", 0)]) - (w[("euclidean", 40)] - w[("euclidean", 0)])

    d = (per_seed(cell_a) - per_seed(cell_b)).dropna().to_numpy()
    half = stats.t.ppf(0.95, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
    lo, hi = float(d.mean() - half), float(d.mean() + half)
    return float(d.mean()), lo, hi, bool(-INTERACTION_MARGIN < lo and hi < INTERACTION_MARGIN)


def case_cells() -> pd.DataFrame:
    """Every case configuration: lag-40 index per geometry (CI, absolute
    effects) and the paired geometry x lag interaction, signed as Euclidean's lag
    contrast minus cosine's (positive: cosine attenuates the lag effect)."""
    sources = []
    fwd = [pd.read_csv(f) for f in sorted(RESULTS.glob("policyswarm_runs*.csv"))]
    if fwd:
        f = _rel(pd.concat(fwd, ignore_index=True))
        if "trust_anchor" not in f.columns:
            f["trust_anchor"] = "centre"
        f["trust_anchor"] = f["trust_anchor"].fillna("centre")
        f = f.drop_duplicates(["gate_space", "eps_mode", "policy_pull", "trust_anchor",
                               "geometry", "lag", "seed"])
        f["source"] = "forward"
        f["cell"] = (f.gate_space + "/" + f.eps_mode + "/" + f.policy_pull + "/trust:" + f.trust_anchor)
        sources.append(f)
    back = [pd.read_csv(f) for f in sorted(RESULTS.glob("diagnosis_runs*.csv")) if "check" not in f.name]
    if back:
        b = _rel(pd.concat(back, ignore_index=True))
        b["trust_centre"] = b.get("trust_centre", 0)
        b["trust_centre"] = b["trust_centre"].fillna(0).astype(int)
        b["source"] = "backward"
        b["cell"] = ("pre-audit fixes: cos=" + b.fix_cosine.astype(str) + " rng=" + b.fix_rng.astype(str)
                     + " split=" + b.split_tick.astype(str) + " trust_centre=" + b.trust_centre.astype(str))
        sources.append(b)
    rows = []
    for src in sources:
        for (source, cell), g in src.groupby(["source", "cell"]):
            if set(g.geometry) != {"euclidean", "cosine"}:
                continue
            per_g, pair = lag_geometry_interaction(g, "rel_delta")
            p = pair.iloc[0]
            sign = 1 if p["geometry_a"] == "cosine" else -1
            lo90, hi90 = _interaction_ci90(g)
            row = {"source": source, "cell": cell, "interaction": sign * p["interaction"],
                   "ci_low": (p["interaction_ci_low"] if sign > 0 else -p["interaction_ci_high"]),
                   "ci_high": (p["interaction_ci_high"] if sign > 0 else -p["interaction_ci_low"]),
                   "p_value": p["p_value"], "ci90_low": lo90, "ci90_high": hi90,
                   "equivalent": bool(-INTERACTION_MARGIN < lo90 and hi90 < INTERACTION_MARGIN)}
            for geom, gg in g.groupby("geometry"):
                ix, lo, hi, d0, d40 = _index_ci(gg, 40)
                ax, alo, ahi, a0, a40 = _index_ci(gg, 40, "delta")
                row.update({f"{geom}_index40": ix, f"{geom}_index_lo": lo, f"{geom}_index_hi": hi,
                            f"{geom}_effect0": d0, f"{geom}_effect40": d40,
                            f"{geom}_abs_index40": ax, f"{geom}_abs_index_lo": alo,
                            f"{geom}_abs_index_hi": ahi, f"{geom}_abs_effect0": a0,
                            f"{geom}_abs_effect40": a40,
                            f"{geom}_pass": float(gg["gate_pass_ctrl"].mean()) if "gate_pass_ctrl" in gg else np.nan})
            rows.append(row)
    return pd.DataFrame(rows)
