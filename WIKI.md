# PolicySwarm — LLM Wiki

> **Version:** 1.0.0  
> **Stack:** Python 3.10+ · NumPy · SciPy · NetworkX · Pandas · Matplotlib  
> **Repository:** github.com/krishnasai-addala/policy-swarm  
> **Period:** December 2025 – May 2026  

---

## Table of Contents

1. [What This Framework Is (and Is Not)](#1-what-this-framework-is-and-is-not)
2. [Architecture Overview](#2-architecture-overview)
3. [Module Reference](#3-module-reference)
   - [config](#31-policyswarmconfig)
   - [extraction](#32-policyswarmextraction)
   - [network](#33-policyswarmnetwork)
   - [shocks](#34-policyswarmshocks)
   - [dynamics](#35-policyswarmydynamics)
   - [metrics](#36-policyswarmmetrics)
   - [analysis](#37-policyswarmanalysis)
   - [visualization](#38-policyswarmvisualization)
   - [experiments](#39-policyswarmexperiments)
4. [Configuration Reference](#4-configuration-reference)
5. [Experiment Catalogue](#5-experiment-catalogue)
6. [Key Findings Reference](#6-key-findings-reference)
7. [Design Decisions and Trade-offs](#7-design-decisions-and-trade-offs)
8. [Known Limitations and Open Questions](#8-known-limitations-and-open-questions)
9. [Usage Examples](#9-usage-examples)
10. [Development History (Iteration Log)](#10-development-history-iteration-log)
11. [Glossary](#11-glossary)
12. [References](#12-references)

---

## 1. What This Framework Is (and Is Not)

PolicySwarm is a **mechanism exploration tool** for AI governance policy analysis. It operationalises a specific question that standard policy analysis tools handle poorly:

> *Given a proposed governance intervention, what are its second-order effects on public discourse, opinion distribution, and the structure of influence networks?*

### What it can answer

Questions of the form: *"Under what parameter regimes does this structural phenomenon occur?"*

- Does enforcement timing matter more than enforcement severity?
- Do competing media outlets amplify or suppress the effects of governance delays?
- Does the topology of the social network govern how far a policy shock propagates?
- Do agents in echo-chamber structures converge differently than those in scale-free networks?

### What it cannot answer

*"What will public opinion on the EU AI Act look like in 2026?"*

Without calibration to empirical data, the simulator produces structurally plausible but unvalidated trajectories. The core epistemological framing is mechanism exploration, not prediction. Any publication-level use of this system must make this distinction explicit.

### Intellectual lineage

The framework sits at the intersection of three traditions:

| Tradition | Key reference | Contribution to PolicySwarm |
|---|---|---|
| Agent-based modelling | Axelrod (1984) | Bounded-confidence interaction rules |
| Computational social science | Deffuant et al. (2000) | Opinion dynamics mathematics |
| Computational policy analysis | CAMEL-AI OASIS | Scale-free network + media agent design |

---

## 2. Architecture Overview

```
Input: Policy Text
       │
       ▼
┌────────────────────────────────────────────┐
│  extraction.py  (KG Pipeline)              │
│  spaCy NER + keyword fallback              │
│  → entities → knowledge graph             │
│  → Policy object (4-D regulatory vector)  │
│  → narrative framing scores               │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│  dynamics.py  (Simulation)                             │
│                                                        │
│  Agents: opinions ∈ R⁴, ideology, trust, influence    │
│  Network: Barabási–Albert or Stochastic Block Model    │
│                                                        │
│  Per-tick step():                                      │
│    1. Time-varying policy update (once, at split tick) │
│    2. Shock application (hub / random targets)         │
│    3. Media broadcast (ideology-aligned, directional)  │
│    4. Peer interactions (bounded-confidence update)    │
│    5. Perceived-policy pull (trust-weighted)           │
│    6. Causal logging → influence_graph                 │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│  experiments/  (Experiment Runner)                     │
│  Paired counterfactual (shared shock schedule)         │
│  Grid: lag × geometry × seed                          │
│  Pre/post split at policy_split_tick                  │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│  metrics.py + analysis.py + visualization.py           │
│  Variance, Polarization, BI, CB, PTT                  │
│  Paired t-tests, effect sizes                         │
│  Phase diagrams, scatter plots, causal heatmaps       │
└────────────────────────────────────────────────────────┘
```

---

## 3. Module Reference

### 3.1 `policyswarm.config`

All configuration lives here as dataclasses. Nothing in this module has side effects.

#### `SimConfig`

Mechanical parameters of the ABM.

| Field | Type | Default | Description |
|---|---|---|---|
| `n_agents` | int | 120 | Population size |
| `n_ticks` | int | 60 | Simulation duration |
| `interactions` | int | 150 | Peer interaction attempts per tick |
| `shock_prob` | float | 0.2 | Per-tick shock probability |
| `mu` | float | 0.15 | Opinion update step size (convergence rate) |
| `epsilon` | float | 0.5 | Confidence radius (bounded-confidence threshold) |
| `network_type` | NetworkType | BA | Topology selection |
| `ba_m` | int | 3 | BA attachment edges per node |
| `sbm_n_communities` | int | 3 | SBM community count |
| `sbm_p_in` | float | 0.20 | SBM within-community edge probability |
| `sbm_p_out` | float | 0.02 | SBM cross-community edge probability |
| `opinion_dim` | int | 4 | Opinion vector dimensionality |
| `policy_split_tick` | int | 40 | Pre/post measurement split and policy update tick |

#### `GovernanceConfig`

Regulatory regime parameters. The primary independent variables in most experiments.

| Field | Type | Default | Description |
|---|---|---|---|
| `oversight_regime` | OverlapRegime or None | None | Categorical regime (auto-populates cap and severity) |
| `deployment_rate_cap` | float | 0.5 | Probability any peer interaction is permitted per tick |
| `penalty_severity` | float | 0.3 | Influence reduction for violator agents |
| `enforcement_lag` | int | 10 | Ticks before penalties activate |
| `enable_media` | bool | True | Whether competing media broadcast is active |
| `media_strength` | float | 0.1 | Scalar on media push magnitude |

**Regime presets** (`REGIME_PARAMS`):

| Regime | `deployment_rate_cap` | `penalty_severity` |
|---|---|---|
| NONE | 1.0 | 0.0 |
| VOLUNTARY | 0.8 | 0.1 |
| MANDATORY | 0.5 | 0.5 |
| PROHIBITIVE | 0.2 | 0.9 |

#### `Policy`

The 4-D regulatory object produced by the KG extraction layer.

| Field | Type | Default | Description |
|---|---|---|---|
| `deployment_cap` | float | 0.5 | AI deployment permissiveness |
| `transparency` | float | 0.5 | Disclosure requirement stringency |
| `enforcement` | float | 0.5 | Penalty intensity (pulls agent opinions) |
| `audit_intensity` | float | 0.5 | Monitoring depth |
| `lag` | int | 10 | Enforcement lag (mirrors GovernanceConfig.enforcement_lag) |
| `narrative` | dict | 0.5 each | Framing weights: safety, innovation, transparency |

`Policy.as_vector()` returns `np.array([deployment_cap, transparency, enforcement, audit_intensity])`.

#### `ShockConfig`

| Field | Type | Default | Description |
|---|---|---|---|
| `shock_prob` | float | 0.2 | Per-tick probability |
| `min_strength` | float | 0.1 | Minimum magnitude |
| `max_strength` | float | 0.4 | Maximum magnitude |
| `mode` | ShockMode | COORDINATING | Directional character |
| `n_targets` | int | 10 | Agents targeted per event |

#### Enumerations

```python
class OverlapRegime(str, Enum):
    NONE, VOLUNTARY, MANDATORY, PROHIBITIVE

class NetworkType(str, Enum):
    BARABASI_ALBERT = "ba"
    STOCHASTIC_BLOCK = "sbm"

class Geometry(str, Enum):
    EUCLIDEAN = "euclidean"   # default, highest polarization
    COSINE    = "cosine"      # lowest polarization
    MANIFOLD  = "manifold"    # geodesic on S^(d-1)

class ShockMode(str, Enum):
    COORDINATING = "coordinating"  # mean-reverting toward 0.5
    POLARIZING   = "polarizing"    # centrifugal push
    DIRECTIONAL  = "directional"   # pull toward policy vector
```

---

### 3.2 `policyswarm.extraction`

Policy-text → Knowledge Graph → Policy object pipeline.

#### `policy_from_text(text, lag=10) → Policy`

Full pipeline in one call. Invokes `extract_entities()` → `policy_from_kg()`.

```python
from policyswarm import policy_from_text
policy = policy_from_text("strict AI regulation with transparency audits")
print(policy.as_vector())  # array([0.6, 0.8, 0.95, 0.8])
```

#### `extract_entities(text) → List[str]`

Attempts spaCy NER (`en_core_web_sm`) with keyword fallback. The keyword ontology maps 25 domain terms to the four policy dimensions. spaCy is optional; the keyword fallback covers all tokens used in the design-document examples.

#### `extract_narrative_scores(text) → Dict[str, float]`

Returns framing weights for `safety`, `innovation`, `transparency` in [0, 1]. Used by `policy_from_kg()` to populate `Policy.narrative`.

#### `build_kg(entities) → nx.Graph`

Constructs a fully-connected entity graph (all pairs get `related_to` edges). This is an abstracted proxy for the MiroFish-Offline KG builder — in the full pipeline this would carry typed relations (e.g., `enforces`, `restricts`, `enables`).

#### `perceived_policy(policy_vector, ideology, trust, noise_scale=0.05) → np.ndarray`

Implements the Iteration 6/8 ideological distortion model. Anti-regulation agents (ideology < 0) underweight enforcement; low-trust agents discount the policy signal globally.

```python
# Same policy text → heterogeneous effective policies across population
pp_pro_reg  = perceived_policy(vec, ideology=0.8,  trust=0.9)
pp_anti_reg = perceived_policy(vec, ideology=-0.7, trust=0.3)
```

**Dimension-specific ideology biases (4-D):**
- `deployment_cap` : −0.3 × ideology (anti-reg agents see more permissive deployment)
- `transparency`   : +0.1 × ideology
- `enforcement`    : +0.2 × ideology
- `audit_intensity`: +0.15 × ideology

#### `describe_extraction(text) → str`

Pretty-prints extraction results for debugging new policy documents.

---

### 3.3 `policyswarm.network`

Social network topology constructors. All return NetworkX graphs plus pre-computed influence arrays.

#### `build_network(config, seed) → (Graph, influence, community_labels)`

Factory dispatcher. Returns the appropriate network for `config.network_type`.

- **BA graph:** `community_labels` is all zeros.
- **SBM graph:** `community_labels` contains community membership per agent.

#### `compute_influence(graph) → np.ndarray`

Normalised degree-based influence in [0, 1]. Division by `max_degree + ε` prevents edge cases on isolated-node graphs. Grounds "influence" in structural position rather than arbitrary assignment (Iteration 3 design note).

#### `top_hub_indices(graph, k=10) → List[int]`

Returns the k highest-degree node indices. Used by hub-targeted shock mechanism.

---

### 3.4 `policyswarm.shocks`

Exogenous shock schedule generation.

#### `generate_shocks(config, n_ticks, seed=0) → ShockSchedule`

Generates a reproducible list of shock events. Using the same seed across paired control/treatment runs is the mechanism that enables causal validity in the counterfactual design.

```python
shocks = generate_shocks(ShockConfig(), n_ticks=60, seed=42)
# → [{"tick": 3, "strength": 0.27, "type": "hub", "mode": "coordinating"}, ...]
```

#### `override_strength(schedule, strength, target_type=None) → ShockSchedule`

Returns a copy of a schedule with uniform strength. Used in Exp 5 (centrality sweep) to vary shock magnitude while keeping the tick schedule fixed. The original schedule is not mutated.

#### `apply_shock_to_opinions(opinions, targets, shock, policy_vector, rng) → delta`

Applies one shock event to specific agents. Exposed for unit testing without a full Simulation.

**Shock mode implementations:**

| Mode | Update rule |
|---|---|
| COORDINATING | `opinions[i] += s * (0.5 - opinions[i])` |
| POLARIZING | `opinions[i] += s * sign(opinions[i] - 0.5)` |
| DIRECTIONAL | `opinions[i] += s * (policy_vector - opinions[i])` |

**Critical note:** COORDINATING is the default and models crisis-induced consensus convergence. It is NOT equivalent to a destabilising event. Use POLARIZING for wedge-event dynamics.

---

### 3.5 `policyswarm.dynamics`

The core ABM engine.

#### `Simulation`

```python
sim = Simulation(
    sim_config   = SimConfig(),
    gov_config   = GovernanceConfig(),
    policy       = policy_from_text(text),
    shocks       = generate_shocks(ShockConfig(), 60, seed=0),
    apply_shocks = True,
    seed         = 0,
    geometry     = Geometry.EUCLIDEAN,
)
history = sim.run()
```

**Per-tick step order** (fixed, matches architecture diagram):

1. `_check_policy_update()` — one-time policy tightening at `policy_split_tick`
2. `_shock_step()` — exogenous perturbation
3. `_media_step()` — ideology-aligned media broadcast
4. `_peer_step()` — bounded-confidence interaction
5. `_policy_pull_step()` — trust-weighted perceived-policy pull

**The `_policy_applied` flag:** Uses `self._policy_applied: bool = False` (not `hasattr`). The `hasattr` approach fails silently when the attribute exists but evaluates to False, causing repeated policy application — the bug documented in Iteration 9 that distorted early results.

**Geometry implementations:**

| Geometry | Distance | Update direction | Retraction |
|---|---|---|---|
| EUCLIDEAN | L2 norm | `op_j - op_i` | `clip([0,1])` |
| COSINE | `1 - cosine_similarity` | `op_j/‖j‖ - op_i/‖i‖` | `clip([0,1])` |
| MANIFOLD | Geodesic on S^(d-1) | Tangent vector | Project to sphere, map to [0,1] |

**Violator definition:** An agent is a violator if `opinions[i, 0] > 0.8` (dimension 0 = deployment_cap). This is a crude proxy for an extreme pro-AI stance. Violators have their effective influence multiplied by `(1 - penalty_severity)` post-lag.

**Influence graph logging:** Every peer interaction, media push, shock application, or policy pull that causes opinion change > 0.01 is logged as a directed edge in `sim.influence_graph` with `weight` (cumulative) and `tick` (first occurrence) attributes.

**Key attributes after `.run()`:**

| Attribute | Type | Description |
|---|---|---|
| `sim.history` | `List[np.ndarray]` | One opinion snapshot per tick |
| `sim.influence_graph` | `nx.DiGraph` | Causal influence graph |
| `sim.initial_opinions` | `np.ndarray` | Snapshot at tick 0 |
| `sim.final_opinions` | `np.ndarray` | Last tick opinions |
| `sim.pre_opinions` | `np.ndarray` | Opinions just before `policy_split_tick` |
| `sim.community_labels` | `np.ndarray` | Community membership (SBM only) |

---

### 3.6 `policyswarm.metrics`

All metric functions operate on NumPy arrays and are stateless.

#### Metric definitions

| Function | Signature | Description |
|---|---|---|
| `opinion_variance(opinions)` | `→ float` | `mean(var(opinions, axis=0))`. Low = consensus or suppression. |
| `polarization_index(opinions)` | `→ float` | Mean pairwise L2 distance. High ≠ high variance. |
| `bifurcation_index(opinions)` | `→ int` | KDE local maxima count. BI=1 = unimodal; BI≥2 = polarized. |
| `cascade_breadth(ig, bg, ops, init_ops)` | `→ int` | Max geodesic in causal influence graph from top hub to affected agents. |
| `phase_transition_tick(history)` | `→ float` | First tick where rolling std(variance) < threshold. Returns `inf` if non-convergent. |
| `causal_centrality(influence_graph)` | `→ Dict[int, float]` | Per-agent out-strength in influence graph. |
| `delta_variance(pre, post)` | `→ float` | `variance(post) - variance(pre)`. Negative = policy reduced disagreement. |
| `effect_size(control_deltas, treat_deltas)` | `→ float` | `mean(treat) - mean(control)`. |
| `compute_all_metrics(sim)` | `→ Dict` | Runs all metrics for a completed Simulation. |

#### Important distinctions

**Variance vs polarization:** Two tight clusters at opposite poles of opinion space produce *high polarization* but *low within-cluster variance*. These are distinct phenomena and should not be treated as interchangeable.

**Cascade breadth:** Computed on the **causal influence graph** (who actually changed whom), not the base interaction graph (who can talk to whom). This is a critical distinction — using the base graph would conflate structural reachability with actual influence propagation.

**Phase transition tick:** Uses rolling standard deviation, not a raw threshold on variance level. A raw threshold triggers on transient dips; rolling std correctly identifies stable convergence.

---

### 3.7 `policyswarm.analysis`

Statistical analysis utilities for the experiment DataFrames.

#### `paired_ttest(control_vals, treatment_vals) → (t, p, effect)`

Core statistical test. Paired because control and treatment share the same seed (same initial conditions, same shock schedule), eliminating variance from initial conditions.

#### `stat_test_table(df, groupby_cols, control_col, treatment_col) → pd.DataFrame`

Runs paired t-tests for each group and returns a results table with columns: `t_stat`, `p_value`, `effect`, `significant`.

#### `group_summary(df, groupby_cols, value_cols) → pd.DataFrame`

Grouped means, standard deviations, and n per cell.

#### `executive_summary(stats_df, experiment, metric_col, p_col) → str`

Formats a human-readable summary. Marks significant results with `**`.

#### `cohens_d(a, b) → float`

Cohen's d effect size for unpaired comparisons (e.g., regime comparisons).

---

### 3.8 `policyswarm.visualization`

All plot functions accept a DataFrame + output directory, write a PNG, and return the file path. Uses `matplotlib.use("Agg")` for headless compatibility.

| Function | Input DataFrame columns | Output file |
|---|---|---|
| `plot_phase_diagram` | geometry, lag, delta | `phase_diagram.png` |
| `plot_cb_vs_lag` | lag, cascade_breadth, enable_media | `cb_vs_lag.png` |
| `plot_variance_timeline` | history (list), shocks | `variance_timeline.png` |
| `plot_variance_comparison` | two histories, shocks | `variance_comparison.png` |
| `plot_opinion_scatter` | opinions array, community_labels | `opinion_scatter.png` |
| `plot_causal_heatmap` | base_graph, influence_graph | `causal_heatmap.png` |
| `plot_centrality_sweep` | shock_strength, target_type, delta | `centrality_sweep.png` |
| `plot_geometry_comparison` | geometry, polarization, variance | `geometry_comparison.png` |
| `plot_oversight_phase` | regime, cascade_breadth, variance | `oversight_phase.png` |
| `plot_variance_shift` | lag, enable_media, delta_variance | `variance_shift.png` |

---

### 3.9 `policyswarm.experiments`

Six experiment classes, each extending `BaseExperiment`.

#### `BaseExperiment` interface

Every experiment exposes:

```python
exp.run()     → pd.DataFrame       # raw results, one row per seed × condition
exp.analyse() → pd.DataFrame       # statistical summaries
exp.plot()    → List[str]          # figure file paths
exp.report()  → dict               # runs all three, saves CSV/PNG, prints summary
```

#### Experiment classes

| Class | Experiment | Key grid |
|---|---|---|
| `OversightPhaseExperiment` | Exp 1: Oversight regime phase transitions | regime × seed |
| `EnforcementLagExperiment` | Exp 2: Enforcement lag sensitivity | lag × seed |
| `MediaInteractionExperiment` | Exp 3: Media × enforcement lag | lag × enable_media × seed |
| `CounterfactualShockExperiment` | Exp 4: Counterfactual shock analysis | lag × geometry × seed |
| `CentralitySweepExperiment` | Exp 5: Centrality × shock strength | target_type × strength × seed |
| `GeometryExperiment` | Exp 6: Opinion-space geometry | geometry × alpha × seed |

---

## 4. Configuration Reference

### Pairing control and treatment runs

The paired counterfactual design is implemented at the `generate_shocks()` / `Simulation` interface, not inside the Simulation class:

```python
# Generate ONCE — both runs share this schedule
shocks = generate_shocks(shock_config, n_ticks=60, seed=seed)

# Control: shocks scheduled but not applied
sim_c = Simulation(..., shocks=shocks, apply_shocks=False, seed=seed)

# Treatment: same shocks applied
sim_t = Simulation(..., shocks=shocks, apply_shocks=True,  seed=seed)
```

The `seed` argument to `Simulation` controls agent initialisation (opinions, ideology, trust); the `seed` argument to `generate_shocks` controls the shock schedule. Using the same integer for both ensures identical initial conditions AND identical timing of exogenous events — the minimum requirement for a valid within-seed comparison.

### Choosing a network topology

| Topology | Use when | Caveat |
|---|---|---|
| BA (default) | Studying hub dynamics, cascade breadth, influence propagation | Low clustering coefficient; does not produce echo chambers |
| SBM | Studying community structure, echo-chamber effects, cross-community bridges | Community memberships visible in `sim.community_labels` |

### Choosing a geometry

Default to **EUCLIDEAN** for comparability with the existing literature. Run **COSINE** as a robustness check. **MANIFOLD** is most theoretically defensible but computationally equivalent.

Euclidean consistently produces 2–3× higher polarization than cosine at comparable variance levels (Experiment 6 finding). Do not treat geometries as interchangeable.

---

## 5. Experiment Catalogue

### Experiment 1: Oversight Regime Phase Transitions

**Question:** Does the oversight regime produce qualitatively different cascade dynamics?

**Design:** Regime ∈ {NONE, VOLUNTARY, MANDATORY, PROHIBITIVE}, paired control/treatment, shared shock schedule.

**Key metric:** Cascade breadth (CB) — how far influence propagated through the causal graph.

**Expected finding:** Phase transition in CB at the VOLUNTARY/MANDATORY boundary. Under MANDATORY, penalty costs suppress hub agent posting frequency, flattening the effective degree distribution and reducing CB by ~34%. The effect is topological (restructures the cascade network), not belief-level (does not simply reduce variance uniformly).

**Output files:** `oversight_phase.png`, `variance_timeline_regime_<name>.png` (×4), results CSV, stats CSV.

---

### Experiment 2: Enforcement Lag Sensitivity

**Question:** Does enforcement timing matter more than enforcement severity?

**Design:** Lag ∈ {0, 5, 10, 20, 40}, penalty severity fixed at 0.5, paired control/treatment.

**Key metric:** Δ variance (treatment − control), bifurcation index.

**Expected finding (strongest result of the project):** Enforcement lag has a LARGER effect on final opinion distributions than penalty severity. Runs with lag ≥ 20 show significantly higher bifurcation index even at maximum penalty severity. 

**Mechanistic interpretation:** Policy announcements without enforcement create an expectation window during which high-influence agents position their expression to maximise downstream influence before the regime activates. Clusters formed during this window prove stable under the bounded-confidence update rule.

**Policy relevance:** Implementation speed matters more than penalty intensity.

---

### Experiment 3: Media × Enforcement Lag Interaction

**Question:** Does ideologically aligned competing media amplify the effects of enforcement delays?

**Design:** Lag ∈ {0, 20, 40} × enable_media ∈ {True, False}, paired.

**Key finding:**

```
Lag  0:  effect_size = +0.009 (p < 0.001)
Lag 20:  effect_size = +0.010 (p < 0.001)
Lag 40:  effect_size = +0.013 (p < 0.001)
```

Competing media consistently amplifies residual disagreement, with the effect modestly increasing at higher lag. Media does NOT prevent enforcement from operating but creates persistent polarised clusters that enforcement cannot dissolve.

**Output files:** `cb_vs_lag.png`, `variance_shift.png`.

---

### Experiment 4: Counterfactual Shock Analysis

**Question:** Do exogenous coordinating shocks reduce opinion variance? Does governance delay weaken this effect?

**Design:** Lag ∈ {0, 20, 40} × geometry ∈ {euclidean, cosine}, paired.

**Expected finding:**

```
Lag  0:  ΔVariance = -0.0135 (p = 0.0018)
Lag 20:  ΔVariance = -0.0128 (p = 0.0029)
Lag 40:  ΔVariance = -0.0115 (p = 0.0051)
```

Coordinating shocks reduce variance significantly. The weakening effect at higher lag is a real and theoretically interpretable signal: governance delays reduce the stabilising impact of coordinating shocks.

**CRITICAL interpretation note:** The default COORDINATING shock models crisis-induced consensus (mean-reverting toward 0.5). This produces *negative* ΔVariance (shocks reduce disagreement). The sign is correct; initial results in the design-document development were misread as positive. Use `ShockMode.POLARIZING` to study the destabilising regime.

**Output files:** `phase_diagram.png`, `variance_comparison_exp4.png`.

---

### Experiment 5: Centrality × Shock Strength Sweep

**Question:** Is network centrality necessary for shock propagation, or can sufficient strength compensate?

**Design:** target_type ∈ {hub, random} × strength ∈ linspace(0.05, 0.60, 8), shared tick schedule, DIRECTIONAL shock mode.

**Three hypotheses:**
- **H1 (centrality necessary):** Hub line consistently above random at all strengths
- **H2 (critical threshold):** Curves converge above some strength — topology irrelevant at high energy
- **H3 (crossover):** Centrality advantages in low-energy regime; strength dominates at high energy

The crossover is theoretically most interesting and connects to the Watts-Dodds (2007) debate between threshold contagion models and linear influence models.

**Note on shock mode:** Uses DIRECTIONAL (toward policy vector) rather than COORDINATING, because this experiment studies coherent signal propagation, not noise convergence. These are separate experimental regimes; results should not be compared directly across experiments.

**Output files:** `centrality_sweep.png`.

---

### Experiment 6: Geometry of Opinion Space

**Question:** Does the choice of opinion-space metric materially affect simulation outcomes?

**Design:** geometry ∈ {euclidean, cosine, manifold} × alpha ∈ {0.0, 0.05, 0.10, 0.15}.

**Key finding (representative result):**

| geometry | alpha | variance | polarization | phase_t |
|---|---|---|---|---|
| euclidean | 0.00 | 0.050 | 0.531 | 53 |
| euclidean | 0.05 | 0.047 | 0.498 | 61 |
| cosine | 0.00 | 0.045 | 0.150 | 38 |
| cosine | 0.05 | 0.043 | 0.144 | 41 |
| manifold | 0.00 | 0.048 | 0.312 | 47 |

Variance is broadly similar across geometries; polarization differs substantially. Euclidean: highest polarization. Cosine: lowest. Manifold: intermediate.

**Modelling implication:** Papers using Euclidean opinion dynamics — the vast majority of ABM work — should either justify this choice explicitly or demonstrate robustness to alternatives. The geometry choice is not a technical default; it is a substantive theoretical commitment about how beliefs relate to each other in opinion space.

**Output files:** `geometry_comparison.png`.

---

## 6. Key Findings Reference

| Finding | Experiment | Effect | p-value | Interpretation |
|---|---|---|---|---|
| Enforcement lag > severity | Exp 2 | Lag=40: Δ−0.005, Lag=0: Δ−0.002 | 0.005–0.010 | Implementation speed matters more than penalty intensity |
| Media amplifies polarisation | Exp 3 | +0.009 to +0.013 | p < 0.001 | Media creates persistent post-enforcement clusters |
| Coordinating shocks reduce variance | Exp 4 | −0.013 to −0.012 | 0.002–0.005 | Effect weakens at higher enforcement lag |
| MANDATORY regime flattens CB | Exp 1 | −34% CB vs NONE | — | Topological effect, not belief-level |
| Euclidean polarisation 3.5× cosine | Exp 6 | 0.531 vs 0.150 | — | Geometry is a substantive modelling commitment |

---

## 7. Design Decisions and Trade-offs

### D1: Influence ∝ network degree (not assigned)

Grounding "influence" in structural position rather than assigning it arbitrarily (Iteration 3). This means that influence and network topology are coupled — changing the network changes influence distributions. In real social systems, there is imperfect but non-zero correlation between network centrality and influence.

**Trade-off:** Overcounts influence for nodes that are central but inactive; undercounts for low-degree but widely read accounts (e.g., journalists with small follower counts but high downstream reach).

### D2: Shared shock schedule for paired comparison

The paired counterfactual requires generating shocks *once* and sharing the schedule across both runs. This ensures that any difference in outcomes is attributable to shock application, not to different timing or magnitude of events.

**Trade-off:** The shock schedule is the same for all geometry and lag conditions within a seed. If the research question involves shock-schedule variance, a different design is needed.

### D3: `_policy_applied` flag (not `hasattr` check)

The single-application gate uses `self._policy_applied: bool = False`. Using `hasattr` fails when the attribute exists but evaluates to False — this was the Iteration 9 bug that caused policy tightening to apply on every tick after the split, distorting results.

### D4: Media is directional toward/away from policy vector (not averaging)

The Iteration 7 media model used averaging (media agents pushed targets toward their own opinion), producing near-zero net effect. The Iteration 8 redesign uses ideology-aligned directional pulls. This is mechanistically correct for real media ecosystems and produces statistically detectable effects.

### D5: Violator threshold at `opinion[0] > 0.8`

A crude proxy for extreme pro-AI deployment stance. Chosen for computational simplicity; in a calibrated model, this would be fit to data. The threshold affects which agents receive influence penalties.

### D6: spaCy optional with keyword fallback

The extraction module degrades gracefully when spaCy is unavailable. The keyword ontology covers all tokens from the design-document policy examples and most common AI governance terms.

---

## 8. Known Limitations and Open Questions

### Endogeneity of initial conditions

`GovernanceConfig` parameters are serialised into the policy document that seeds the KG, coupling governance parameters to initial agent beliefs. A decoupling experiment (fixed KG, varied simulation rules only) is needed to isolate the two pathways. This remains an open methodological gap.

### Static network topology

The interaction network does not evolve during simulation. Endogenous network evolution — activity-based degree changes, echo-chamber reinforcement, selective unfollowing — is a high-priority extension. Real social platforms exhibit structural dynamics on the same timescale as policy discourse.

### Symmetric media reach

Pro- and anti-policy media affect equal fractions of the population. Real media ecosystems are asymmetric in reach, credibility, and temporal dynamics. Claims about media effects should be interpreted against this simplification.

### Shock model polarity

The current shock taxonomy covers COORDINATING (consensus-inducing) and POLARIZING (wedge) events, but does not model their co-occurrence or sequencing. Real policy discourse typically involves mixtures of both over the policy lifecycle.

### LLM agent coherence (for full MiroFish-Offline integration)

The full design-document architecture includes qwen2.5:32b via Ollama for agent post content generation. LLM agents exhibit sycophancy (Perez et al., 2022) and opinion drift under conversational pressure (Sharma et al., 2023). A triangulation study comparing rule-based, LLM, and hybrid agent populations is needed before publication.

### No calibration to empirical data

The model has not been fit to real policy discourse data. Without calibration, structural results are plausible but unvalidated. The real-world pipeline sketched in the design document (GDELT ingestion → shock distribution fitting → agent prior initialisation from discourse) would address this.

### Identification problem

Multiple parameter sets can fit the same macro-level output. The model's simulation-based inference loop requires additional identifying restrictions or empirical anchors to resolve this.

---

## 9. Usage Examples

### Minimal: run one experiment

```python
from policyswarm import PolicySwarm

ps = PolicySwarm(output_dir="results", seeds=list(range(10)))
report = ps.run_experiment("lag")

print(report["stats_df"])
# lag   t_stat  p_value    effect  significant
#   0  1.594   0.252  -0.0018        False
#  10  9.696   0.010  -0.0037         True
#  40 14.734   0.005  -0.0051         True
```

### Run a single Simulation manually

```python
from policyswarm import (
    SimConfig, GovernanceConfig, Geometry,
    policy_from_text, generate_shocks, Simulation,
    compute_all_metrics, ShockConfig, ShockMode,
)

policy  = policy_from_text("strict AI regulation with transparency and audit requirements")
shock_c = ShockConfig(mode=ShockMode.COORDINATING)
shocks  = generate_shocks(shock_c, n_ticks=60, seed=0)

sim = Simulation(
    sim_config   = SimConfig(n_agents=200, n_ticks=80),
    gov_config   = GovernanceConfig(enforcement_lag=15, enable_media=True),
    policy       = policy,
    shocks       = shocks,
    apply_shocks = True,
    seed         = 0,
    geometry     = Geometry.EUCLIDEAN,
)

history = sim.run()
metrics = compute_all_metrics(sim)
print(metrics)
# {'variance': 0.038, 'polarization': 0.41, 'bifurcation_index': 2,
#  'cascade_breadth': 5, 'phase_transition_tick': 47.0, 'delta_variance': -0.004}
```

### Custom policy text

```python
from policyswarm import PolicySwarm, describe_extraction

eu_ai_act_text = """
The EU AI Act introduces a risk-based regulatory framework classifying AI systems
into prohibited, high-risk, limited-risk, and minimal-risk categories. High-risk
AI systems must undergo conformity assessment, maintain technical documentation,
implement human oversight mechanisms, and register with the EU database.
Penalties for non-compliance can reach 35 million euros or 7% of global annual turnover.
"""

# Inspect what the KG extracts before running
PolicySwarm.describe_policy(eu_ai_act_text)

# Run the full experiment suite
ps = PolicySwarm(
    output_dir  = "eu_ai_act_results",
    seeds       = list(range(20)),     # more seeds for publication
    policy_text = eu_ai_act_text,
)
reports = ps.run_all()
```

### Paired counterfactual manually

```python
from policyswarm import (
    SimConfig, GovernanceConfig, Policy,
    generate_shocks, Simulation, ShockConfig,
    opinion_variance, delta_variance,
)
import numpy as np

policy  = Policy(deployment_cap=0.4, transparency=0.8, enforcement=0.7, audit_intensity=0.6, lag=10)
config  = SimConfig()
gov     = GovernanceConfig(enforcement_lag=10, penalty_severity=0.5)
shocks  = generate_shocks(ShockConfig(), n_ticks=60, seed=42)

sim_c   = Simulation(config, gov, policy, shocks, apply_shocks=False, seed=42)
sim_t   = Simulation(config, gov, policy, shocks, apply_shocks=True,  seed=42)

sim_c.run(); sim_t.run()

dv_c = delta_variance(sim_c.pre_opinions, sim_c.final_opinions)
dv_t = delta_variance(sim_t.pre_opinions, sim_t.final_opinions)
print(f"Control ΔVar: {dv_c:.4f}")
print(f"Treat   ΔVar: {dv_t:.4f}")
print(f"Effect:       {dv_t - dv_c:.4f}")
```

### Geometry robustness check

```python
from policyswarm import GeometryExperiment, Geometry

exp = GeometryExperiment(
    output_dir = "geometry_check",
    seeds      = list(range(10)),
    geometries = [Geometry.EUCLIDEAN, Geometry.COSINE, Geometry.MANIFOLD],
    alphas     = [0.05, 0.10, 0.15],
)
report = exp.report()
```

### CLI

```bash
# All experiments with default settings
python run_all.py

# Specific experiments, custom seeds, custom output
python run_all.py --experiments lag media geometry --seeds 0 1 2 3 4 5 6 7 8 9 --output pub_results

# Just the KG extraction summary
python run_all.py --describe
```

---

## 10. Development History (Iteration Log)

The framework was built in 12 major iterations, each motivated by a specific research question or modelling gap. This section documents the chain of reasoning.

| Iteration | What was added | Key design decision |
|---|---|---|
| 1 | Minimal 1D opinion model (NumPy only) | Validated that bounded-confidence dynamics produce interesting structure before investing in infrastructure |
| 2 | Monte Carlo experiment runner | Fixed seeds (`list(range(n))`) for exact reproducibility and direct cross-config comparison |
| 3 | Barabási–Albert network topology | Grounds influence in structural position (degree) rather than arbitrary assignment |
| 4 | Cascade Breadth (CB) and Phase Transition Tick (PTT) | Measures temporal and structural dynamics that variance discards; introduces explicit policy pull |
| 5 | Multi-dimensional opinions + enforcement lag | Lag addition generates the strongest empirical finding; 4D enables dimension-specific disagreement |
| 6 | KG extraction pipeline + perceived_policy | Same text → heterogeneous effective policies via ideological distortion |
| 7 | SBM community structure + initial media | Discovered symmetric-media averaging bug (E[effect] ≈ 0); SBM produces echo-chamber clusters |
| 8 | Ideology-aligned competing media (fixed) | Directional media → statistically detectable polarisation amplification |
| 9 | Time-varying policy + pre/post measurement | Fixed `_policy_applied` attribute bug; enables measuring whether enforcement actually changes trajectory |
| 10 | Paired counterfactual + 4D policy + shocks | Shared shock schedule is the key causal validity mechanism; resolved sign-of-effect misinterpretation |
| 11 | Centrality × shock strength sweep | Tests H1/H2/H3 regarding centrality-vs-strength trade-off; uses DIRECTIONAL shock mode |
| 12 | Geometry comparison (Euclidean / cosine / manifold) | Demonstrates that geometry is a substantive modelling commitment, not a technical default |

---

## 11. Glossary

| Term | Definition |
|---|---|
| **ABM** | Agent-based model. A simulation where macro-level phenomena emerge from local interaction rules between heterogeneous agents. |
| **Bounded confidence** | Interaction rule where agent i updates toward j only when their opinion distance is below i's confidence radius ε. |
| **Cascade breadth (CB)** | Maximum geodesic distance in the causal influence graph from the top hub to any significantly-affected agent. Measures how far influence propagated. |
| **Bifurcation index (BI)** | Count of local maxima in the KDE of the final opinion distribution. BI=1 = consensus; BI≥2 = polarisation. |
| **Causal influence graph** | Directed graph where edge (i→j, weight=w) means agent i caused opinion change of magnitude w in agent j. Not the same as the interaction network. |
| **Confidence radius (ε)** | Distance threshold below which two agents will interact. |
| **Deployment rate cap** | Per-tick probability that any peer interaction is permitted. GovernanceConfig.deployment_rate_cap. |
| **Enforcement lag** | Ticks between simulation start (policy announcement) and penalty activation (enforcement onset). Key variable in Exp 2. |
| **Euclidean dynamics** | Opinion-space dynamics using L2 norm as distance metric. Default and dominant in the literature. Highest polarisation. |
| **Hub targeting** | Shock variant that perturbs the top-k highest-degree nodes rather than random agents. |
| **Ideology** | Agent attribute in [-1, 1]. +1 = strongly pro-regulation. -1 = strongly anti-regulation. Sampled from Uniform(-1,1). |
| **Influence** | Normalised degree-based score in [0,1] for each agent. Used as update magnitude in peer interactions. |
| **KG** | Knowledge graph. Entity-relation graph extracted from policy text. |
| **Mean-reverting shock** | COORDINATING shock mode. Pulls opinions toward 0.5. Models crisis-induced consensus. |
| **Monte Carlo run** | One full simulation under fixed seeds. Research claims require distributions over runs (multiple seeds). |
| **Opinion variance** | `mean(var(opinions, axis=0))`. Mean across dimensions of per-dimension variance. |
| **Paired counterfactual** | Experimental design where control and treatment share seed and shock schedule. Eliminates initial-condition variance. |
| **Phase transition tick (PTT)** | First tick where rolling std of variance < 0.01. Measures convergence speed. Returns inf if non-convergent. |
| **Polarisation index** | Mean pairwise L2 distance. Captures bimodal clustering that variance misses. |
| **Policy pull** | Weak directional force (0.04–0.05) applied each tick pulling agent opinions toward the perceived policy vector. |
| **Perceived policy** | Agent-specific distortion of the raw policy vector via ideology and institutional trust. Same text → different effective policies. |
| **Scale-free network** | Network with power-law degree distribution. Produced by Barabási–Albert preferential attachment. A small number of hubs dominate propagation. |
| **SBM** | Stochastic Block Model. Community-structured network where within-community edge probability >> cross-community probability. |
| **Trust** | Agent attribute in [0,1]. Beta(2,2) distributed. Scales the perceived-policy pull. Low trust = policy signal discounted. |
| **Violator** | Agent with `opinions[0] > 0.8`. Receives influence penalty post-enforcement lag. |

---

## 12. References

- Axelrod, R. (1984). *The Evolution of Cooperation*. Basic Books.
- Converse, P.E. (1964). The nature of belief systems in mass publics. In Apter, D.E. (ed.), *Ideology and Discontent*. Free Press.
- Deffuant, G., Neau, D., Amblard, F., & Weisbuch, G. (2000). Mixing beliefs among interacting agents. *Advances in Complex Systems*, 3(01n04), 87–98.
- Goel, S., Anderson, A., Hofman, J., & Watts, D.J. (2016). The structural virality of online diffusion. *Management Science*, 62(1), 180–196.
- Kahan, D.M. et al. (2017). Motivated numeracy and enlightened self-government. *Behavioural Public Policy*, 1(1), 54–86.
- Lorenz, J. (2007). Continuous opinion dynamics under bounded confidence. *International Journal of Modern Physics C*, 18(12), 1819–1838.
- Perez, E. et al. (2022). Discovering Language Model Behaviors with Model-Written Evaluations. arXiv:2212.09251.
- Sharma, M. et al. (2023). Towards Understanding Sycophancy in Language Models. arXiv:2310.13548.
- Watts, D.J., & Dodds, P.S. (2007). Influentials, networks, and public opinion formation. *Journal of Consumer Research*, 34(4), 441–458.
- OASIS: Open Agent Social Interaction Simulations. CAMEL-AI. https://github.com/camel-ai/oasis
- MiroFish-Offline. nikmcfly. https://github.com/nikmcfly/MiroFish-Offline
- West, J.D., & Bergstrom, C.T. (2021). Misinformation in and about science. *PNAS*, 118(15).

---

*PolicySwarm v1.0.0 · github.com/krishnasai-addala/policy-swarm*
