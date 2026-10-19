# PolicySwarm

An agent-based model of how a population's views on a policy respond to the policy itself, to media and to shocks, and the methods work on comparing distance measures in bounded-confidence opinion models.

## Opinion dynamics

**Geometry**:
The pair of a distance measure, used by the gate, and the update step that goes with it (Euclidean, cosine, angular).
_Avoid_: Metric, manifold (for the angular geometry)

**Distance measure**:
The quantity the gate compares with the threshold: Euclidean distance, cosine distance or angle.
_Avoid_: Metric (cosine distance is not a metric)

**Gate**:
The rule that lets two agents converse only when their distance is at most the threshold ε.
_Avoid_: Confidence bound, filter

**Update step**:
How a listener's opinion moves toward a speaker's after a conversation passes the gate.
_Avoid_: Update rule (when the gate is meant), step function

**Threshold**:
The value ε the gate compares distances with, in the units of its distance measure.
_Avoid_: Bound, confidence level

**Coverage**:
The share of opinion pairs within the threshold at one moment.
_Avoid_: Realised coverage (for the pass rate)

**Pass rate**:
The share of attempted conversations in a run that pass the gate.
_Avoid_: Realised coverage, interaction rate

**Settled**:
A run is settled from the first round after which no conversing pair's opinion moves by more than 10⁻⁴; a later larger move unsettles it.
_Avoid_: Converged

**Convergence time**:
The round at which a run became settled.

## Threshold rules

**Shared threshold**:
Every geometry uses the same number as Euclidean's threshold.
_Avoid_: Raw ε

**Start-matched threshold**:
Each geometry's threshold gives the same coverage at the start of a run.
_Avoid_: t0-matched, matched at t = 0

**Run-matched threshold**:
Each geometry's threshold gives the same pass rate over the run as Euclidean's.
_Avoid_: Matched over the run (in labels), dynamic matching

**Early-matched threshold**:
Each geometry's threshold gives the same pass rate over the first 100 rounds as Euclidean's.

## Policy and trust

**Perceived policy**:
The policy as one agent sees it, after trust, bias and noise.

**Trust target**:
The point a low-trust agent's perceived policy is pulled toward (centre, corner, status quo or own opinion).
_Avoid_: Trust anchor, shrinkage target, origin

**Policy pull**:
The move of each agent toward the policy itself; gated (only after a conversation that passes the gate) or anchor (every agent, every tick).

**Perceived-policy pull**:
From the enforcement lag on, the move of each agent toward its perceived policy.

**Level shift**:
The control in which every agent's perceived policy is moved by the same amount, the average shift the corner trust target would give.

## Case-study outcomes

**Shock effect**:
The change in final opinion variance that a schedule of shocks causes, from paired runs with and without shocks; negative when shocks lower variance.

**Relative shock effect**:
The shock effect divided by the variance of the run without shocks.
_Avoid_: Normalised effect

**Lag contrast**:
The per-seed change in the relative shock effect from enforcement lag 0 to lag 40, with its sign; negative when lag enlarges a variance-lowering shock effect.
_Avoid_: Lag effect (ambiguous about sign)

**Lag index**:
The mean relative shock effect at lag 40 as a percentage of its mean at lag 0, by size; above 100 means lag enlarges the effect.

**Interaction**:
Cosine's lag contrast minus Euclidean's, paired by seed; with variance-lowering shock effects, positive means lag enlarges the effect less under cosine (cosine attenuates).
_Avoid_: Reversal (for a change in one geometry's lag index)
