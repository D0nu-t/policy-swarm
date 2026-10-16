"""
policyswarm.registry
====================
The single list of runnable experiments, and the bridge from a JSON run
description (``RunSpec``) to constructed experiment objects.

Every front end goes through this module: the CLI for ``--experiments``
choices and ``--spec`` files, the ``PolicySwarm`` facade, and the dashboard
for the forms it renders (``describe``).
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any, Dict, List, Optional, Tuple, Type

from .config import GATE_SPACES, POLICY_PULLS, TRUST_ANCHORS, Policy, RunSpec, SimConfig
from .experiments import (
    CentralitySweepExperiment,
    CounterfactualShockExperiment,
    EnforcementLagExperiment,
    EpsilonCalibrationExperiment,
    GeometryExperiment,
    MediaInteractionExperiment,
    OversightPhaseExperiment,
    TopologyValidationExperiment,
)
from .experiments.base import BaseExperiment
from .experiments.params import ParamError, ParamSpec, parse_params, specs_from_dataclass
from .extraction import DEFAULT_POLICY_TEXT
from .opinion_space import OpinionSpace, presets

#: Experiment name -> class, in canonical run order.
EXPERIMENTS: Dict[str, Type[BaseExperiment]] = {
    cls.name: cls
    for cls in (
        OversightPhaseExperiment,
        EnforcementLagExperiment,
        MediaInteractionExperiment,
        CounterfactualShockExperiment,
        TopologyValidationExperiment,
        EpsilonCalibrationExperiment,
        CentralitySweepExperiment,
        GeometryExperiment,
    )
}

_SIM_CONFIG_HELP = {
    "n_agents"          : "Number of agents.",
    "n_ticks"           : "Simulation length in ticks.",
    "interactions"      : "Peer interaction attempts per tick.",
    "mu"                : "Peer convergence rate.",
    "epsilon"           : "Bounded-confidence threshold (Euclidean reference).",
    "policy_anchor_rate": "Per-tick pull of every agent toward the policy.",
    "network_type"      : "ba = Barabasi-Albert, sbm = stochastic block model.",
    "ba_m"              : "Edges added per new node (BA).",
    "sbm_n_communities" : "Number of communities (SBM).",
    "sbm_p_in"          : "Within-community edge probability (SBM).",
    "sbm_p_out"         : "Cross-community edge probability (SBM).",
    "policy_split_tick" : "Tick at which the policy tightens.",
}
#: Form labels and sections for the SimConfig fields (dashboard only).
_SIM_CONFIG_LABELS = {
    "n_agents"          : ("Agents", "Population and time"),
    "n_ticks"           : ("Ticks", "Population and time"),
    "interactions"      : ("Conversations per tick", "Population and time"),
    "mu"                : ("Convergence rate μ", "Interaction"),
    "epsilon"           : ("Confidence threshold ε", "Interaction"),
    "policy_anchor_rate": ("Policy anchor rate", "Interaction"),
    "policy_split_tick" : ("Policy tightening tick", "Interaction"),
    "network_type"      : ("Network type", "Network"),
    "ba_m"              : ("BA edges per new node", "Network"),
    "sbm_n_communities" : ("SBM communities", "Network"),
    "sbm_p_in"          : ("SBM within-community probability", "Network"),
    "sbm_p_out"         : ("SBM cross-community probability", "Network"),
}

_SIM_CONFIG_MINIMUM = {"n_agents": 10, "n_ticks": 6, "interactions": 1, "ba_m": 1,
                       "sbm_n_communities": 1}

#: SimConfig fields a run may override. ``opinion_dim`` is set by the policy
#: and ``shock_prob`` is unused by the engine, so neither is offered.
#: The "hidden choices" (see paper/methods_note): defaults are the audited
#: model, so leaving them alone changes nothing.
HIDDEN_CHOICE_PARAMS: Tuple[ParamSpec, ...] = (
    ParamSpec("gate_space", "choice", "centred", choices=GATE_SPACES,
              label="Gate measured from", group="Hidden choices",
              help="Where the confidence gate measures from. centred: angles are measured "
                   "from the neutral point. unit: from the corner where every dimension is "
                   "at its minimum (the pre-audit space). With unit, ε is read in unit-cube "
                   "units: halve it (0.5 for the default 1.0) to keep the same Euclidean gate."),
    ParamSpec("policy_pull", "choice", "anchor", choices=POLICY_PULLS,
              label="Policy pull", group="Hidden choices",
              help="anchor: every agent is pulled a little toward the policy each tick. "
                   "gated: only after a conversation that passed the gate, so the pull "
                   "grows with how many pairs can talk (the pre-audit coupling)."),
    ParamSpec("trust_anchor", "choice", "centre", choices=TRUST_ANCHORS,
              label="Low trust perceives", group="Hidden choices",
              help="What a low-trust agent perceives instead of the policy. centre: "
                   "neutral. corner: no regulation at all. status_quo: the population's "
                   "starting average. own: its own view. level_shift: a control that "
                   "moves everyone by corner's average amount."),
)

SIM_CONFIG_PARAMS: Tuple[ParamSpec, ...] = tuple(
    dataclasses.replace(spec, minimum=_SIM_CONFIG_MINIMUM.get(spec.name, spec.minimum),
                        label=_SIM_CONFIG_LABELS[spec.name][0],
                        group=_SIM_CONFIG_LABELS[spec.name][1])
    for spec in specs_from_dataclass(SimConfig, _SIM_CONFIG_HELP)
    if spec.name in _SIM_CONFIG_HELP
) + HIDDEN_CHOICE_PARAMS


def get_experiment(name: str) -> Type[BaseExperiment]:
    """Look up an experiment class by registry name."""
    try:
        return EXPERIMENTS[name]
    except KeyError:
        raise ParamError(
            f"Unknown experiment: {name!r}. Choose from: {list(EXPERIMENTS)}"
        ) from None


def build_sim_config(overrides: Optional[Dict[str, Any]], base: Optional[SimConfig] = None) -> SimConfig:
    """Apply validated JSON overrides to a SimConfig (default: ``SimConfig()``)."""
    parsed = parse_params(SIM_CONFIG_PARAMS, overrides)
    return dataclasses.replace(base or SimConfig(), **parsed)


def build_experiment(
    name        : str,
    output_dir  : str,
    seeds       : List[int],
    policy_text : Optional[str]            = None,
    policy      : Optional[Policy]         = None,
    sim_config  : Optional[SimConfig]      = None,
    params      : Optional[Dict[str, Any]] = None,
) -> BaseExperiment:
    """Construct one experiment from JSON-level parameters.

    ``params`` is validated against the experiment's ``PARAMS``; omitted
    parameters keep the constructor defaults.
    """
    cls = get_experiment(name)
    kwargs: Dict[str, Any] = parse_params(cls.PARAMS, params)
    if policy_text is not None:
        kwargs["policy_text"] = policy_text
    return cls(output_dir=output_dir, seeds=seeds, policy=policy,
               sim_config=sim_config, **kwargs)


def validate_run_spec(spec: RunSpec) -> None:
    """Raise ``ParamError`` if ``spec`` could not be run. Constructs nothing on disk."""
    if not spec.experiments:
        raise ParamError("experiments: choose at least one experiment")
    if not spec.seeds:
        raise ParamError("seeds: at least one seed is required")
    if any(isinstance(s, bool) or not isinstance(s, int) or s < 0 for s in spec.seeds):
        raise ParamError("seeds: expected non-negative integers")
    if len(set(spec.seeds)) != len(spec.seeds):
        raise ParamError("seeds: duplicate seeds would double-count runs")
    stray = sorted(set(spec.params) - set(spec.experiments))
    if stray:
        raise ParamError(f"params given for experiments that are not selected: {stray}")
    build_sim_config(spec.sim_config)
    for name in spec.experiments:
        parse_params(get_experiment(name).PARAMS, spec.params.get(name))
    if spec.opinion_space is not None:
        OpinionSpace.from_dict(spec.opinion_space)


def policy_from_spec(spec: RunSpec) -> Optional[Policy]:
    """The Policy a custom ``spec.opinion_space`` defines, or None if it has none.

    None means the experiments extract the policy from the text themselves,
    on the built-in dimensions.
    """
    if spec.opinion_space is None:
        return None
    space = OpinionSpace.from_dict(spec.opinion_space)
    return space.build_policy(spec.policy_text or DEFAULT_POLICY_TEXT)


def experiments_from_spec(spec: RunSpec, policy: Optional[Policy] = None) -> List[BaseExperiment]:
    """Construct every experiment in ``spec``, each writing to ``<output_dir>/<name>``.

    ``policy`` (a pre-built LLM / embedding policy) and ``spec.opinion_space``
    are two sources of the same thing and may not both be given.
    """
    validate_run_spec(spec)
    if policy is not None and spec.opinion_space is not None:
        raise ParamError("opinion_space cannot be combined with a pre-built policy")
    if policy is None:
        policy = policy_from_spec(spec)
    sim_config = build_sim_config(spec.sim_config)
    if policy is not None:
        sim_config = dataclasses.replace(sim_config, opinion_dim=policy.dim)
    return [
        build_experiment(
            name,
            output_dir  = os.path.join(spec.output_dir, name),
            seeds       = list(spec.seeds),
            policy_text = spec.policy_text,
            policy      = policy,
            sim_config  = sim_config,
            params      = spec.params.get(name),
        )
        for name in spec.experiments
    ]


def describe() -> Dict[str, Any]:
    """JSON-serialisable catalogue of experiments and their parameters."""
    return {
        "experiments": [
            {
                "name"  : name,
                "title" : cls.title,
                "class" : cls.__name__,
                "params": [p.to_dict() for p in cls.PARAMS],
            }
            for name, cls in EXPERIMENTS.items()
        ],
        "sim_config": [p.to_dict() for p in SIM_CONFIG_PARAMS],
        "opinion_space": {
            "default": OpinionSpace.default().to_dict(),
            "presets": {name: space.to_dict() for name, space in presets().items()},
        },
        "default_policy_text": DEFAULT_POLICY_TEXT,
    }
