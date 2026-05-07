"""
policyswarm.shocks
==================
Exogenous shock schedule generation.

A shock schedule is a list of shock-event dicts, each with keys:
    tick     : int   – tick at which the event fires
    strength : float – magnitude of the opinion perturbation
    type     : str   – "hub" or "random" (targeting strategy)
    mode     : str   – ShockMode value (directional character)

Generating the schedule separately from applying it (via Simulation) is the
key design decision enabling the paired counterfactual experiment (Iteration
10): both the control and treatment simulations share the *same* schedule;
only ``apply_shocks`` differs.

Shock modes
-----------
COORDINATING : opinions[i] += strength * (0.5 - opinions[i])
               Mean-reverting toward the centre of opinion space. Models
               crisis-induced consensus, emergency coordinated messaging.

POLARIZING   : direction = sign(opinions[i] - 0.5)
               opinions[i] += strength * direction
               Centrifugal. Models wedge events, disinformation campaigns.

DIRECTIONAL  : opinions[i] += strength * (policy_vector - opinions[i])
               Pulls toward the current policy position. Used in Experiment 5
               (centrality sweep) to study coherent signal propagation.
               Requires the simulation to supply its policy_vector at apply time.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import numpy as np

from .config import ShockConfig, ShockMode


# Type alias for a single shock event
ShockEvent = Dict[str, Any]
ShockSchedule = List[ShockEvent]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_shocks(
    config  : ShockConfig,
    n_ticks : int,
    seed    : int = 0,
) -> ShockSchedule:
    """Generate a reproducible exogenous shock schedule.

    Parameters
    ----------
    config : ShockConfig
        Parameters governing the shock process.
    n_ticks : int
        Simulation duration. Shocks are sampled over [0, n_ticks).
    seed : int
        Random seed. Using the same seed across paired runs guarantees
        identical shock timing and magnitude. Default 0.

    Returns
    -------
    list of dict
        Each dict has keys: tick, strength, type, mode.
    """
    rng = np.random.default_rng(seed)
    schedule: ShockSchedule = []

    for t in range(n_ticks):
        if rng.random() < config.shock_prob:
            target_type = rng.choice(["hub", "random"])
            strength    = rng.uniform(config.min_strength, config.max_strength)
            schedule.append({
                "tick"    : int(t),
                "strength": float(strength),
                "type"    : str(target_type),
                "mode"    : config.mode.value,
            })

    return schedule


def override_strength(
    schedule  : ShockSchedule,
    strength  : float,
    target_type: Optional[str] = None,
) -> ShockSchedule:
    """Return a copy of schedule with all strengths replaced.

    Used in Experiment 5 (centrality sweep) to vary shock magnitude while
    keeping the tick schedule fixed (Iteration 11 design).

    Parameters
    ----------
    schedule : ShockSchedule
    strength : float
        New uniform strength value.
    target_type : str, optional
        If provided, also overrides the 'type' field. Use "hub" or "random".

    Returns
    -------
    ShockSchedule (new list, original unmodified)
    """
    result = []
    for ev in schedule:
        new_ev = dict(ev)
        new_ev["strength"] = strength
        if target_type is not None:
            new_ev["type"] = target_type
        result.append(new_ev)
    return result


# ---------------------------------------------------------------------------
# Application helpers (called by Simulation)
# ---------------------------------------------------------------------------

def apply_shock_to_opinions(
    opinions       : np.ndarray,
    targets        : List[int],
    shock          : ShockEvent,
    policy_vector  : Optional[np.ndarray] = None,
    rng            : Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Apply a single shock event to specified target agents.

    This function is called by Simulation.apply_shock() for each event.
    It is exposed here so unit tests can exercise the shock logic without
    instantiating a full Simulation.

    Parameters
    ----------
    opinions : np.ndarray, shape (n_agents, dim)
        Current opinion matrix. Modified in-place.
    targets : list of int
        Agent indices to perturb.
    shock : ShockEvent
        Shock event dict from the schedule.
    policy_vector : np.ndarray, optional
        Required when shock['mode'] == 'directional'.
    rng : np.random.Generator, optional
        Used for POLARIZING mode to add small noise. Default numpy global.

    Returns
    -------
    np.ndarray
        Delta array (opinions_after - opinions_before) for causal logging.
    """
    strength = shock["strength"]
    mode     = shock.get("mode", ShockMode.COORDINATING.value)
    dim      = opinions.shape[1]

    before = opinions[targets].copy()

    if mode == ShockMode.COORDINATING.value:
        # Mean-reverting: pull toward 0.5
        opinions[targets] += strength * (0.5 - opinions[targets])

    elif mode == ShockMode.POLARIZING.value:
        # Centrifugal: push away from 0.5
        directions = np.sign(opinions[targets] - 0.5)
        directions[directions == 0] = 1.0  # break ties outward
        opinions[targets] += strength * directions

    elif mode == ShockMode.DIRECTIONAL.value:
        if policy_vector is None:
            raise ValueError(
                "policy_vector must be provided for DIRECTIONAL shock mode."
            )
        opinions[targets] += strength * (policy_vector - opinions[targets])

    else:
        raise ValueError(f"Unknown shock mode: {mode!r}")

    # Clamp to [0, 1]
    opinions[targets] = np.clip(opinions[targets], 0.0, 1.0)

    return opinions[targets] - before


# ---------------------------------------------------------------------------
# Convenience summary
# ---------------------------------------------------------------------------

def summarise_schedule(schedule: ShockSchedule) -> Dict[str, Any]:
    """Return descriptive statistics of a shock schedule.

    Parameters
    ----------
    schedule : ShockSchedule

    Returns
    -------
    dict with keys: n_shocks, mean_strength, std_strength, n_hub, n_random, ticks
    """
    if not schedule:
        return {"n_shocks": 0}

    strengths  = [ev["strength"] for ev in schedule]
    n_hub      = sum(1 for ev in schedule if ev["type"] == "hub")
    n_random   = len(schedule) - n_hub

    return {
        "n_shocks"      : len(schedule),
        "mean_strength" : float(np.mean(strengths)),
        "std_strength"  : float(np.std(strengths)),
        "n_hub"         : n_hub,
        "n_random"      : n_random,
        "ticks"         : [ev["tick"] for ev in schedule],
    }
