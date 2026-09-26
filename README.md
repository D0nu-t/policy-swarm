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
pip install -r requirements.txt
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

├── run_all.py
├── config.py
├── policyswarm/
│   ├── experiments/
│   ├── analysis.py
│   ├── dynamics.py
│   ├── metrics.py
│   ├── network.py
│   ├── latex.py
│   └── tui/
└── results/
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
