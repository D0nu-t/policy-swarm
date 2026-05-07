"""
policyswarm.metrics
===================
Outcome metric computations for the policy simulation framework.

All metrics operate on NumPy arrays and are deliberately stateless functions
(not methods) so they can be used independently of the Simulation class.

Metric catalogue
----------------
┌──────────────────────┬────────────────────────────────────────────────────────┐
│ Metric               │ Definition                                             │
├──────────────────────┼────────────────────────────────────────────────────────┤
│ opinion_variance     │ mean(var(opinions, axis=0))                            │
│ polarization_index   │ mean pairwise L2 distance                              │
│ bifurcation_index    │ number of local maxima in KDE of 1D opinion projection │
│ cascade_breadth      │ max geodesic distance in influence graph from top hub  │
│ phase_transition_tick│ first tick where rolling std(variance) < threshold     │
│ causal_centrality    │ per-node out-strength in influence graph               │
│ delta_variance       │ variance_post - variance_pre                           │
│ effect_size          │ mean(treat_delta) - mean(control_delta)                │
└──────────────────────┴────────────────────────────────────────────────────────┘

References
----------
- Deffuant et al. (2000) — bounded confidence, variance as convergence metric
- Goel et al. (2016)    — cascade breadth (structural virality)
- Design document §Outcome Metrics
"""

from __future__ import annotations

from typing import List, Optional, Dict, Tuple
import numpy as np
import networkx as nx
from scipy.stats import gaussian_kde


# ---------------------------------------------------------------------------
# 1. Opinion Variance
# ---------------------------------------------------------------------------

def opinion_variance(opinions: np.ndarray) -> float:
    """Mean variance across all opinion dimensions.

    Parameters
    ----------
    opinions : np.ndarray, shape (n_agents, dim)

    Returns
    -------
    float
        Mean of per-dimension variances. Low = consensus or suppression.
        High = heterogeneous opinion distribution.
    """
    return float(np.mean(np.var(opinions, axis=0)))


# ---------------------------------------------------------------------------
# 2. Polarization Index
# ---------------------------------------------------------------------------

def polarization_index(
    opinions   : np.ndarray,
    max_pairs  : int = 5000,
) -> float:
    """Mean pairwise L2 distance across the agent population.

    High polarization is distinct from high variance: two tight clusters at
    opposite poles produce high polarization but low within-cluster variance.

    Parameters
    ----------
    opinions : np.ndarray, shape (n_agents, dim)
    max_pairs : int
        If n_agents > 100, sample max_pairs pairs instead of computing
        the full O(n²) matrix. Default 5000.

    Returns
    -------
    float
    """
    n = len(opinions)
    if n * (n - 1) // 2 > max_pairs:
        rng = np.random.default_rng(0)
        i_idx = rng.integers(0, n, size=max_pairs)
        j_idx = rng.integers(0, n, size=max_pairs)
        mask  = i_idx != j_idx
        diffs = opinions[i_idx[mask]] - opinions[j_idx[mask]]
        return float(np.mean(np.linalg.norm(diffs, axis=1)))

    dists = []
    for i in range(n):
        for j in range(i + 1, n):
            dists.append(np.linalg.norm(opinions[i] - opinions[j]))
    return float(np.mean(dists)) if dists else 0.0


# ---------------------------------------------------------------------------
# 3. Bifurcation Index
# ---------------------------------------------------------------------------

def bifurcation_index(
    opinions   : np.ndarray,
    dim        : int   = 0,
    bandwidth  : float = 0.08,
    n_eval     : int   = 200,
) -> int:
    """Count local maxima in the KDE of a 1D projection of opinions.

    BI = 1 → consensus (unimodal distribution)
    BI ≥ 2 → polarization (bimodal or multimodal)

    Parameters
    ----------
    opinions : np.ndarray, shape (n_agents, opinion_dim)
    dim : int
        Opinion dimension to project onto. Default 0 (deployment_cap).
    bandwidth : float
        KDE bandwidth. Default 0.08.
    n_eval : int
        Number of evaluation points for the KDE. Default 200.

    Returns
    -------
    int
        Number of local maxima (peaks) in the estimated density.
    """
    x    = opinions[:, dim]
    grid = np.linspace(0, 1, n_eval)
    try:
        kde  = gaussian_kde(x, bw_method=bandwidth)
        dens = kde(grid)
    except np.linalg.LinAlgError:
        # Degenerate case: all agents identical
        return 1

    # Local maxima: interior points higher than both neighbours
    is_max = (
        np.concatenate([[False], dens[1:] > dens[:-1]])
        & np.concatenate([dens[:-1] > dens[1:], [False]])
    )
    n_peaks = int(is_max.sum())
    return max(n_peaks, 1)  # at least 1 to avoid zero-peak pathology


# ---------------------------------------------------------------------------
# 4. Cascade Breadth
# ---------------------------------------------------------------------------

def cascade_breadth(
    influence_graph  : nx.DiGraph,
    base_graph       : nx.Graph,
    opinions         : np.ndarray,
    initial_opinions : np.ndarray,
    delta            : float = 0.1,
) -> int:
    """Maximum geodesic distance from the top hub to any significantly shifted agent.

    CB is computed on the causal influence graph, not the base interaction
    graph. This ensures we measure actual influence propagation, not
    structural reachability (Iteration 4 design note).

    Parameters
    ----------
    influence_graph : nx.DiGraph
        Directed causal influence graph maintained by Simulation.
    base_graph : nx.Graph
        Base interaction network (for hub identification).
    opinions : np.ndarray, shape (n_agents, dim)
        Final opinion matrix.
    initial_opinions : np.ndarray, shape (n_agents, dim)
        Opinion matrix at tick 0.
    delta : float
        Minimum L2 opinion shift to count an agent as "affected". Default 0.1.

    Returns
    -------
    int
        Maximum geodesic distance. 0 if no agents were affected or the hub
        is not in the influence graph.
    """
    # Identify affected agents (opinion shift > delta)
    shifts   = np.linalg.norm(opinions - initial_opinions, axis=1)
    affected = set(int(i) for i in np.where(shifts > delta)[0])

    if not affected:
        return 0

    # Top hub: highest-degree node in base graph
    seed_node = max(dict(base_graph.degree()), key=lambda x: base_graph.degree(x))

    if seed_node not in influence_graph:
        return 0

    try:
        lengths = nx.single_source_shortest_path_length(influence_graph, seed_node)
    except nx.NetworkXError:
        return 0

    reachable = [lengths[n] for n in affected if n in lengths]
    return max(reachable) if reachable else 0


# ---------------------------------------------------------------------------
# 5. Phase Transition Tick
# ---------------------------------------------------------------------------

def phase_transition_tick(
    history   : List[np.ndarray],
    window    : int   = 5,
    threshold : float = 0.01,
) -> float:
    """First tick at which opinion variance has stabilised.

    Stabilisation criterion: rolling standard deviation of variance over the
    preceding ``window`` ticks falls below ``threshold``.  Returns ``inf``
    if the system never converges within the simulation horizon.

    This is more robust than a raw threshold on variance level, which
    triggers on transient dips (Iteration 4 design note).

    Parameters
    ----------
    history : list of np.ndarray
    window : int
        Rolling window size. Default 5.
    threshold : float
        Stabilisation threshold on rolling std. Default 0.01.

    Returns
    -------
    float
        Tick index or inf.
    """
    variances = np.array([opinion_variance(h) for h in history])
    for t in range(window, len(variances)):
        if np.std(variances[t - window : t]) < threshold:
            return float(t)
    return float("inf")


# ---------------------------------------------------------------------------
# 6. Causal Centrality
# ---------------------------------------------------------------------------

def causal_centrality(influence_graph: nx.DiGraph) -> Dict[int, float]:
    """Per-node out-strength in the causal influence graph.

    Out-strength = sum of edge weights for all edges leaving a node.
    Identifies agents that were causally responsible for the most opinion change.

    Parameters
    ----------
    influence_graph : nx.DiGraph

    Returns
    -------
    dict mapping node index (int) → out-strength (float)
        Only includes integer-indexed agent nodes (excludes 'shock',
        'media_pro', 'media_anti', 'policy' source nodes).
    """
    centrality: Dict[int, float] = {}
    for node in influence_graph.nodes():
        if not isinstance(node, int):
            continue
        weight = sum(
            d.get("weight", 1.0)
            for _, _, d in influence_graph.out_edges(node, data=True)
        )
        centrality[node] = float(weight)
    return centrality


# ---------------------------------------------------------------------------
# 7. Delta Variance and Effect Size
# ---------------------------------------------------------------------------

def delta_variance(
    pre_opinions  : np.ndarray,
    post_opinions : np.ndarray,
) -> float:
    """Variance change across the policy split point.

    Parameters
    ----------
    pre_opinions : np.ndarray, shape (n_agents, dim)
        Agent opinions just before the policy split tick.
    post_opinions : np.ndarray, shape (n_agents, dim)
        Agent opinions at the final tick.

    Returns
    -------
    float
        opinion_variance(post) - opinion_variance(pre).
        Negative → policy reduced disagreement.
    """
    return opinion_variance(post_opinions) - opinion_variance(pre_opinions)


def effect_size(
    control_deltas  : np.ndarray,
    treatment_deltas: np.ndarray,
) -> float:
    """Paired effect size: mean(treat_delta) - mean(control_delta).

    Used in the paired counterfactual design (Iteration 10). Positive =
    treatment increased variance relative to control.

    Parameters
    ----------
    control_deltas : np.ndarray, shape (n_seeds,)
    treatment_deltas : np.ndarray, shape (n_seeds,)

    Returns
    -------
    float
    """
    return float(np.mean(treatment_deltas) - np.mean(control_deltas))


# ---------------------------------------------------------------------------
# 8. Convenience: compute all metrics for a completed Simulation
# ---------------------------------------------------------------------------

def compute_all_metrics(sim) -> Dict[str, float]:
    """Compute the full metric suite for a completed Simulation.

    Parameters
    ----------
    sim : Simulation
        A fully run Simulation instance (sim.run() has been called).

    Returns
    -------
    dict
        Keys: variance, polarization, bifurcation_index, cascade_breadth,
              phase_transition_tick, delta_variance
    """
    final = sim.final_opinions
    return {
        "variance"           : opinion_variance(final),
        "polarization"       : polarization_index(final),
        "bifurcation_index"  : bifurcation_index(final),
        "cascade_breadth"    : cascade_breadth(
            sim.influence_graph,
            sim.graph,
            final,
            sim.initial_opinions,
        ),
        "phase_transition_tick": phase_transition_tick(sim.history),
        "delta_variance"     : delta_variance(sim.pre_opinions, sim.post_opinions),
    }
