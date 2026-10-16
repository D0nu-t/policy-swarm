"""
policyswarm.gui.audit
=====================
A "hidden choices" report for a finished batch run.

The methods note (paper/methods_note) found five choices that can manufacture
or hide an effect without anyone noticing: a threshold shared across distance
measures, when coverage is matched, where trust shrinks the perceived policy,
which statistical test is read, and how groups are counted. This module reads
what a run saved and reports the first three plus the test, in plain language:

* the hidden choices the run used (and whether they are the defaults);
* for each experiment that compares geometries: the ε and the realised gate
  pass rate per geometry, and a warning when they differ a lot;
* the geometry x lag interaction test, next to how many single cells were
  "significant", so a reader does not mistake per-cell tests for the
  comparison itself.

Everything is read from files; nothing is recomputed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from ..config import SimConfig

#: The SimConfig hidden choices and their audited defaults.
_HIDDEN = ("gate_space", "policy_pull", "trust_anchor")
#: A realised pass-rate difference (in points) worth flagging.
PASS_GAP_WARNING = 0.10


def _latest(directory: Path, pattern: str):
    files = sorted(directory.glob(pattern))
    return pd.read_csv(files[-1]) if files else None


def _experiment(directory: Path, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"name": name, "geometries": [], "warnings": [], "interaction": None}
    results = _latest(directory, "*_results_*.csv")
    if results is None or "geometry" not in results.columns:
        return out
    pass_col = next((c for c in ("gate_pass_ctrl", "gate_pass_rate") if c in results.columns), None)
    for geom, g in results.groupby("geometry"):
        row = {"geometry": geom,
               "epsilon": float(g["epsilon"].mean()) if "epsilon" in g.columns else None,
               "pass_rate": float(g[pass_col].mean()) if pass_col else None}
        out["geometries"].append(row)

    rates = [g["pass_rate"] for g in out["geometries"] if g["pass_rate"] is not None]
    if len(rates) > 1 and max(rates) - min(rates) > PASS_GAP_WARNING:
        out["warnings"].append(
            f"The geometries' realised gate pass rates differ by {100 * (max(rates) - min(rates)):.0f} "
            "points, so part of any difference between them may come from how often agents "
            "can talk, not from the geometry.")
    eps = {round(g["epsilon"], 6) for g in out["geometries"] if g["epsilon"] is not None}
    if len(out["geometries"]) > 1 and len(eps) == 1:
        out["warnings"].append(
            "Every geometry used the same ε number. A shared ε lets a different share of pairs "
            "talk under each distance measure, so it is not a like-for-like comparison.")
    if params.get("epsilon_mode") == "raw" and len(eps) != 1:
        out["warnings"].append("ε mode was 'raw' (shared).")

    inter = _latest(directory, "lag_geometry_interaction.csv")
    if inter is not None and len(inter):
        rel = inter[inter["value"] == "rel_delta"] if "value" in inter.columns else inter
        r = rel.iloc[0]
        stats = _latest(directory, "*_stats_*.csv")
        cells = None
        if stats is not None and "p_value" in stats.columns:
            cells = {"significant": int((stats["p_value"] < 0.05).sum()), "total": int(len(stats))}
        out["interaction"] = {
            "pair": f"{r.get('geometry_a', '')} − {r.get('geometry_b', '')}",
            "estimate": float(r.get("interaction", float("nan"))),
            "ci_low": float(r.get("interaction_ci_low", float("nan"))),
            "ci_high": float(r.get("interaction_ci_high", float("nan"))),
            "p_value": float(r.get("p_value", float("nan"))),
            "cells": cells,
        }
    return out


def build_audit(directory: Path, spec) -> Dict[str, Any]:
    """The hidden-choices report for one run (``spec`` is its RunSpec)."""
    defaults = SimConfig()
    overrides = spec.sim_config or {}
    choices: List[Dict[str, Any]] = []
    for name in _HIDDEN:
        value = overrides.get(name, getattr(defaults, name))
        choices.append({"name": name, "value": value, "default": value == getattr(defaults, name)})
    experiments = []
    for name in spec.experiments:
        exp = _experiment(directory / name, name, (spec.params or {}).get(name, {}))
        if exp["geometries"] or exp["interaction"]:
            experiments.append(exp)
    warnings = [w for e in experiments for w in e["warnings"]]
    gate = next(c["value"] for c in choices if c["name"] == "gate_space")
    if gate == "unit":
        eps = overrides.get("epsilon", defaults.epsilon)
        warnings.insert(0, f"The gate measured from the cube's corner, where ε is read in unit-cube "
                           f"units: ε = {eps:g} here is a Euclidean gate of {2 * eps:g} in the usual "
                           "centred units. If you meant the same gate as a centred run, halve ε.")
    if any(not c["default"] for c in choices):
        warnings.insert(0, "This run changed at least one hidden choice from the audited default "
                           "(see the list above). Results are not comparable with default runs.")
    return {"choices": choices, "experiments": experiments, "warnings": warnings}
