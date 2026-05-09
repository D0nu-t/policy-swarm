---
# PolicySwarm: Agent-Based Simulation of AI Governance Dynamics

PolicySwarm is an experimental framework for studying **policy diffusion, enforcement dynamics, and opinion formation** in networked populations. It implements a modular ABM with controlled interventions (e.g., enforcement lag, media influence, shocks) and evaluates outcomes using **paired within-seed statistical tests**.

The repository accompanies a research study on how **governance mechanisms interact with social topology and opinion geometry**.
---

## Core Design

### Model
- Agents: bounded-rational actors with continuous opinion states
- Network: configurable graph structures (homogeneous / centrality-driven)
- Dynamics:
  - Peer influence
  - Media signals
  - Enforcement mechanisms (with lag)
  - Exogenous shock

### Key Feature: Paired Experimental Design
All experiments use **matched seeds**:
- Control and treatment share identical initial conditions
- Statistical test: **paired t-test**
- Eliminates variance from stochastic initialization

---

## Experiments

| ID | Name | Description |
|----|------|-------------|
| Exp 1 | Oversight | Phase transitions under regulatory regimes |
| Exp 2 | Lag | Enforcement lag sensitivity |
| Exp 3 | Media | Media × enforcement interaction |
| Exp 4 | Counterfactual | Shock-type comparison |
| Exp 5 | Centrality | Network centrality effects |
| Exp 6 | Geometry | Opinion-space geometry |

---

## Installation

```bash
git clone https://github.com/D0nu-t/policy-swarm.git
cd policy-swarm

python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

pip install -r requirements.txt
````

---

## Usage

### Run all experiments (default S=20)

```bash
python run_all.py
```

### Run specific experiments

```bash
python run_all.py --experiments lag counterfactual geometry
```

### Custom seeds (Monte Carlo size S)

```bash
python run_all.py --seeds 0 1 2 ... 19
```

### Custom output directory

```bash
python run_all.py --output results_s20
```

---

## Output Structure

```
results_s20/
  lag/
    *_results_*.csv
    *_stats_*.csv
    phase_diagram.png
    lag_table.tex
  counterfactual/
    ...
  geometry/
    geometry_table.tex
```

---

## Statistical Reporting

### Effect Estimates

* Reported as:

  ```
  Δ = mean(treatment − control)
  95% CI via t-distribution
  paired t-test (two-sided)
  ```

### Example

```
lag=20  Δ=-0.00319  p=2.1e-08  CI=[-0.00392, -0.00246]
```

---

## LaTeX Integration

Generated automatically:

```latex
\input{results_s20/lag/lag_table.tex}
\input{results_s20/geometry/geometry_table.tex}
```

Tables include:

* Effect sizes
* 95% confidence intervals
* p-values

---

## Reproducibility Checklist

* Fixed seeds (default: 0–19)
* Deterministic pipeline per seed
* Outputs saved with timestamps
* Single entrypoint: `run_all.py`
* No hidden state outside config

---

## Repository Structure

```
policyswarm/
  experiments/
  analysis.py
  dynamics.py
  metrics.py
  network.py
  latex.py

run_all.py
config.py
```

---

## Key Results (Summary)

* Enforcement lag consistently destabilizes system equilibrium
* Euclidean geometry amplifies polarization relative to cosine
* Manifold-constrained opinion space suppresses bifurcation
* Shock type interacts strongly with geometry

---

## Citation

If used in research, cite as:

```
Krishnasai Addala, "PolicySwarm: Agent-Based Analysis of AI Governance Dynamics", 2026.
```

---



