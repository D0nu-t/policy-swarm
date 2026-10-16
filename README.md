# PolicySwarm

**PolicySwarm** is an agent-based simulation framework for studying how AI governance policies propagate through networked populations. It models opinion formation, regulatory interventions, media influence, and enforcement mechanisms to evaluate how different governance strategies affect collective outcomes.

The framework accompanies research on the interaction between **network topology**, **opinion-space geometry**, and **regulatory policy**, providing a reproducible experimental pipeline with paired statistical analysis.

---

## Features

* Agent-based simulation of AI governance dynamics
* Multiple intervention mechanisms:

  * Regulatory oversight
  * Enforcement lag
  * Media influence
  * Exogenous shocks
* Configurable social networks and opinion geometries
* Paired Monte Carlo experimental design
* Automatic statistical analysis
* Publication-ready figures and LaTeX tables
* Reproducible experiment pipeline

---

## Methods note (draft)

`paper/methods_note/` holds a short methods paper: comparing distance measures in a bounded-confidence model at one shared threshold compares different interaction rates, and threshold matching has to use realised coverage, not coverage at the start. It includes a minimal Deffuant model, a PolicySwarm case study that traces the draft paper's withdrawn geometry "reversal" to its causes, and a reporting protocol. `make_figures.py` rebuilds every figure and every number in `main.tex` from `results/`; the run scripts (`run_minimal.py`, `run_policyswarm.py`, `diagnose_reversal.py`) regenerate the results. The two engine switches it uses (`SimConfig.gate_space`, `SimConfig.policy_pull`) default to the audited model and are hidden from the dashboard.

---

## Model Overview

PolicySwarm represents a population of bounded-rational agents interacting on a social network.

Each simulation evolves through repeated interactions between agents while optional governance mechanisms modify the underlying dynamics.

### Agents

Each agent maintains a continuous opinion state and updates its beliefs according to:

* peer influence
* media signals
* regulatory enforcement
* external events

### Networks

Multiple network structures are supported, enabling experiments on how topology influences governance outcomes.

Examples include:

* homogeneous networks
* heterogeneous degree distributions
* centrality-driven interventions

### Opinion Geometry

Opinion similarity can be measured using different embedding geometries, allowing direct comparison between Euclidean and cosine-based interaction spaces.

Opinions live in the centred cube [-1, 1]^d, where 0 is neutral on every dimension, so angular (cosine / manifold) similarity measures ideological alignment rather than distance from "no regulation". A single raw ε means very different interaction coverage under each metric, so geometry experiments calibrate ε per geometry to admit the same fraction of network-neighbour pairs (`policyswarm.geometry.matched_epsilons`) and record the realised gate pass rate of every run. Geometry × lag claims are tested with `analysis.lag_geometry_interaction`, not per-cell significance.

---

# Experimental Pipeline

The repository contains eight independent experiments.

| Experiment         | Purpose                                              |
| ------------------ | ---------------------------------------------------- |
| **Oversight**      | Phase transitions under different regulatory regimes |
| **Lag**            | Sensitivity to delayed enforcement                   |
| **Media**          | Interaction between media exposure and regulation    |
| **Counterfactual** | Comparison of different external shock models        |
| **Topology**       | Counterfactual geometry × lag grid on SBM networks   |
| **Epsilon**        | Raw vs coverage-matched threshold sensitivity        |
| **Centrality**     | Influence of network position on policy outcomes     |
| **Geometry**       | Effects of opinion-space geometry                    |

Each experiment can be executed independently or through a single orchestration script.

---

# Paired Experimental Design

PolicySwarm uses a matched-seed experimental methodology.

For every random seed:

1. A control simulation is generated.
2. A treatment simulation is generated using the **identical initialization**.
3. Outcomes are compared pairwise.

This design removes variance introduced by stochastic initialization and substantially increases statistical power.

Reported statistics include:

* paired mean difference
* paired t-test
* 95% confidence interval

For an effect estimate

```
Δ = mean(treatment − control)
```

the framework reports

```
Δ
95% CI
paired p-value
```

Example:

```
lag = 20

Δ = -0.00319
95% CI = [-0.00392, -0.00246]
p = 2.1e-08
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/D0nu-t/policy-swarm.git
cd policy-swarm
```

Create a virtual environment:

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -e ".[dev]"
```

This installs the core package plus the test, lint and dashboard dependencies. Optional extraction tiers are separate extras: `.[nlp]`, `.[llm]`, `.[huggingface]`, `.[embedding]` (see `pyproject.toml`).

Run the tests:

```bash
pytest -m "not slow"     # seconds
pytest                   # also re-runs every experiment against tests/golden/ (minutes)
```

---

# Running Experiments

Run every experiment using the default configuration:

```bash
python run_all.py
```

Run selected experiments:

```bash
python run_all.py --experiments lag counterfactual geometry
```

Specify the Monte Carlo seeds:

```bash
python run_all.py --seeds 0 1 2 3 4
```

Choose a custom output directory:

```bash
python run_all.py --output results_s5
```

Change experiment parameters with a run description (a `RunSpec` JSON file):

```json
{
  "experiments": ["lag", "geometry"],
  "seeds": [0, 1, 2],
  "output_dir": "my_run",
  "sim_config": {"n_agents": 200},
  "params": {
    "lag": {"lags": [0, 10, 30]},
    "geometry": {"geometries": ["euclidean", "cosine"], "epsilon_mode": "raw"}
  }
}
```

```bash
python run_all.py --spec my_run.json
```

Each experiment declares the parameters it accepts in its `PARAMS` attribute (`policyswarm/experiments/`); unknown names and out-of-range values are rejected before anything runs.

A run description can also replace the opinion space itself: the dimensions, the policy's position on them, and the keyword rules that derive that position from the policy text. All values are on the simulation's scale, −1 to 1 with 0 neutral.

```json
{
  "experiments": ["lag"],
  "seeds": [0, 1, 2],
  "opinion_space": {
    "dimensions": [
      {"name": "openness", "ideology_sensitivity": -0.2},
      {"name": "oversight", "ideology_sensitivity": 0.3, "tightening": 0.2}
    ],
    "violator_dimension": "openness",
    "violator_threshold": 0.6,
    "keywords": [{"keyword": "open source", "dimension": "openness", "delta": 0.5}],
    "position": null
  }
}
```

Set `position` to `{"openness": -0.4, "oversight": 0.7}` to fix the policy by hand instead of deriving it from the text. Without `opinion_space`, the built-in four AI-governance dimensions and keyword table are used (`policyswarm/opinion_space.py`).

---

# Dashboard

A local web dashboard runs the same experiments from a form, with live progress, and shows the resulting tables and figures.

```bash
python -m policyswarm.gui
```

Then open http://127.0.0.1:8000. Besides experiment parameters, simulation settings and the policy text, the "Opinion space" section edits the dimensions, the policy position and the keyword rules, with a preview of the resulting position. Each run is written to `runs/<run id>/` together with the `run.json` that reproduces it (`python run_all.py --spec runs/<run id>/run.json`). The server binds to loopback only and has no authentication; do not expose it to a network.

**Watch one simulation.** The second section of the dashboard runs a single scenario and replays it tick by tick.

- Each tick plays in the engine's own order (shock, media, conversations, policy). Every conversation attempt is drawn from speaker to listener with its outcome: blocked by the deployment cap, ignored because the two opinions are further apart than ε, or heard (the listener moves; the speaker does not).
- **Compare geometries.** Tick two or three geometries to run the same scenario side by side from the same seed: same network, same starting opinions, same shocks, only the distance measure differs. By default each geometry gets the ε that lets the same share of neighbour pairs talk (`match_epsilon`), because one raw ε means a different amount of talking in each geometry.
- **Three views of opinion space:** a 2-D slice of two dimensions; a 3-D plot you can drag to rotate (with a "directions only" option that shows what the angular geometries compare); and a distance map that places agents so that on-screen distance approximates the geometry's own distance over all dimensions (classical multidimensional scaling; the page reports how much of the true distances the flat picture keeps).
- **Distance histograms** show, per geometry and tick, how far apart network neighbours are and what share fall within ε.
- A per-tick log, a timeline, and details for any agent you click.

It takes the simulation settings, opinion space and policy text from the form, plus its own scenario settings. Limits: 400 agents, 300 ticks, and 60,000 for agents × ticks × geometries. The data comes from `policyswarm/trace.py` (`record_trace`), which records a run without changing it.

**Adding a geometry.** Each geometry is one `GeometrySpec` in `policyswarm/geometry.py`: its distance and step functions plus the text the dashboard shows. Add a member to `config.Geometry`, write the two functions, and call `register_geometry`; the engine, the ε calibration and the viewer pick it up.

**Suggest an opinion space from text.** Inside the opinion-space editor, "Suggest from text" drafts dimensions and keyword rules (`policyswarm/suggest.py`):

1. *Topics → dimensions* (`pip install -e ".[topics]"`, scikit-learn). NMF on TF-IDF groups the sentences of the policy text, plus an optional folder of documents, into topics. You name each topic and describe what its positive end means.
2. *Decision model → keyword rules* (`pip install -e ".[decision]"`, [Laya](https://huggingface.co/convaiinnovations/laya)). Topic terms are first filtered (policy boilerplate, terms spread across topics, words found all over the text, and single words contained in a kept phrase are dropped). For each remaining term that occurs in the policy text, the model answers three fixed questions: which dimension, raises or lowers, how strongly. **Experimental.**

   Measured with `python -m policyswarm.tools.eval_suggest` on `tests/data/keyword_benchmark.json` (208 phrases over four policy domains; two domains for tuning, two held out; Laya 0.3.29 zero-shot on CPU, 2026-10-12):

   | Held-out domains (104 phrases) | Precision | Recall | Generic phrases given a rule |
   |---|---|---|---|
   | Laya, default questions | 0.68 | 0.49 | 0.17 |
   | Word-overlap baseline (no model) | 0.56 | 0.48 | 0.29 |
   | Bar set beforehand for "useful" | 0.75 | 0.50 | 0.15 |

   It beats the baseline and misses the bar on all three. Rewording the questions did not help: on the tuning domains, showing the model each dimension's two ends, or asking one yes/no or three-way question per dimension, made it give a rule to nearly every phrase (precision 0.25 to 0.32 against 0.56). Those variants remain selectable in `suggest.rate_keywords(strategy=...)`. **How far to trust the labels.** They were drafted by an AI assistant. The author labelled a random 40 of them independently (re-checking 12 doubtful answers) and agreed on 26 (65%); on a 30-item sample of the training set the agreement was 23 (77%). The dimensions overlap ("public register" is both transparency and auditing), so for the 14 benchmark disagreements both readings now count as correct (`also_accept`); the table above uses that rule. With people agreeing only about two thirds of the time, the 0.75 precision bar may be above what any model can reach against these labels.

   **Head-only fine-tuning was tried and did not help** (2026-10-12; 603 newly labelled phrases in ten other policy domains, `tests/data/keyword_training.json`; encoder frozen, CPU). On the tuning domains, zero-shot scored 0.56 precision / 0.38 recall. With Laya's default training objective two runs left 102 to 104 of 104 decisions unchanged. With plain cross-entropy the model picked the right dimension more often but almost stopped answering "none", scoring 0.41 / 0.46 after 6 epochs and 0.35 / 0.39 after 12. No checkpoint beat zero-shot, so none was scored on the held-out domains and the default model is unchanged. Details and the commands are in `policyswarm/tools/finetune_data.py`; a fine-tuned checkpoint can be tried in the dashboard with `python -m policyswarm.gui --decider-checkpoint <folder>`. Full fine-tuning (encoder included) has not been run.

Suggestions are marked in the editor and nothing is applied until you keep it. Neither model runs during a simulation: the result is an ordinary `opinion_space` in the run description, so a saved `run.json` reproduces the run without either library.

---

# TUI

The repository also includes an interactive terminal dashboard built with **React**, **Ink**, and **TypeScript**.

The TUI launches `run_all.py`, visualizes experiment progress, streams logs, and displays failures in real time.

Build the interface:

```bash
cd policyswarm/tui

npm install
npm run build
```

Launch:

```bash
node dist/index.js
```

The dashboard accepts the same arguments as `run_all.py`:

```bash
node dist/index.js --experiments lag
```

```bash
node dist/index.js --seeds 0 1 2 3 4
```

```bash
node dist/index.js --output results_s5
```

---

# Output

Results are organized by experiment.

```
results_s20/
├── oversight/
├── lag/
├── media/
├── counterfactual/
├── centrality/
└── geometry/
```

Each directory may contain:

* raw simulation outputs
* summary statistics
* figures
* CSV files
<!-- * LaTeX tables -->

Example:

```
lag/

lag_results.csv
lag_stats.csv
phase_diagram.png
<!-- lag_table.tex -->
```

---

<!-- # LaTeX Integration

Publication-ready tables are generated automatically.

Example:

```latex
\input{results_s20/lag/lag_table.tex}
\input{results_s20/geometry/geometry_table.tex}
```

Each table contains

* effect sizes
* confidence intervals
* p-values

and is formatted for direct inclusion in academic manuscripts. -->

---

# Reproducibility

PolicySwarm is designed for deterministic experimentation.

The default workflow provides:

* fixed random seeds (0–29)
* paired treatment/control runs
* deterministic execution per seed
* timestamped outputs
* centralized experiment orchestration
* reproducible statistical analysis

---

# Repository Structure

```
policy-swarm/

├── run_all.py            thin entry point for policyswarm/cli.py
├── pyproject.toml
├── policyswarm/
│   ├── config.py         SimConfig, GovernanceConfig, Policy, RunSpec
│   ├── dynamics.py       simulation engine
│   ├── geometry.py       opinion-space distances and threshold calibration
│   ├── network.py, shocks.py, extraction*.py
│   ├── metrics.py, analysis.py, visualization.py, latex.py
│   ├── experiments/      one class per experiment, events, params
│   ├── registry.py       experiment registry and RunSpec validation
│   ├── facade.py, cli.py
│   ├── trace.py          tick-by-tick record of one simulation (dashboard viewer)
│   ├── projection.py     distance map (classical MDS, Procrustes alignment)
│   ├── suggest.py        draft an opinion space from text (topics, decision model)
│   ├── gui/              FastAPI + SSE dashboard
│   ├── schemas/          policy schema YAMLs for LLM extraction
│   └── tui/              Ink terminal UI
├── tests/                unit tests and golden results
└── policyswarm_output_*/ committed result sets
```

---

# Summary of Findings

Across the benchmark experiments:

* enforcement delays consistently reduce regulatory effectiveness
* opinion-space geometry substantially changes polarization dynamics
* manifold-constrained interaction suppresses bifurcation compared with Euclidean embeddings
* network topology strongly moderates governance interventions
* external shocks interact nonlinearly with both topology and geometry

---

<!-- # Citation

If you use PolicySwarm in academic work, please cite:

```text
Krishnasai Addala.
PolicySwarm: Agent-Based Analysis of AI Governance Dynamics.
2026.
``` -->
