Simulated review by an AI model; role-separated, not independent of other seats; NOT_CALIBRATED.

# Peer Review Report — Peer Reviewer 3 (Perspective: cross-disciplinary / practical)
Identity: AI-governance and policy-modelling researcher who builds and evaluates ABMs used to inform regulation and public policy.

## Recommendation: Major Revision. Confidence 4.

## Summary assessment
Strongest contribution for policy modellers is the second layer of the case: trust scales perceived policy multiplicatively, so it shrinks toward the coordinate origin, which in a [0,1] coding means "no regulation at all". That is portable to many policy ABMs but is buried in a paper framed around distance metrics; the protocol prescribes centring at "neutral" without acknowledging that "neutral" is itself a substantive assumption; and the corrected model still shows a sizeable, statistically clear geometry difference that the text understates. Reporting the withdrawn result openly, with pre-audit commit and patch, is exemplary.

## Strengths
- S1: Transparent, reproducible account of a withdrawn finding (§5.1 footnote; Code and data).
- S2: Two-directional diagnosis (forward factorial + backward ablation), plus the equivariance check (§5.2).
- S3: The trust-toward-origin mechanism is a transferable insight (§5.3).
- S4: Protocol item 5 (test the interaction directly), applied in Table 2.

## Weaknesses
### W1 (Major, conf 4): Centring "at neutral" swaps one substantive assumption for another, unacknowledged
Anchor: §6 item 1 "put the origin at neutral". The fix shrinks toward the cube centre (patch: 0.5 + trust*(policy+bias-0.5)). For policy dimensions the midpoint has no privileged meaning; a distrustful citizen might perceive the status quo, their own prior, in-group media's version, or "nothing enforced". The corrected model encodes "low trust → policy perceived as moderate". The headline result (both amplify) depends on this anchor.
Fix: reframe item 1 as "make the shrinkage target an explicit, justified parameter and report sensitivity"; rerun Exp 4 under ≥2 alternative targets (status quo, own opinion); say the original reversal was a consequence of an unexamined substantive assumption, not a pure coding artefact.

### W2 (Major, conf 4): The corrected model still shows a clear geometry effect; text says "somewhat more"
Anchor: Table 2 rows centred/matched-run and unit/matched-run/gated. Centred run-matched: indices 189 vs 161 (anchor), 160 vs 143 (gated); interactions +0.034 [+0.027,+0.042] (p≈6e-15) and +0.013 [+0.000,+0.026]. Unit/gated/run-matched: cosine 478 vs 160 with matched realised coverage (57% vs 58%) — coverage matching can leave a threefold gap.
Fix: state the residual geometry effect quantitatively in abstract and "Reading the case"; link the 478 corner to the protocol (matching coverage without fixing the origin can make things worse); make the origin audit a precondition of coverage checks.

### W3 (Major, conf 4): The generalisable lesson is buried under the metric-comparison framing
Anchor: §7 Limitations "the general point (multiplicative steps inherit the meaning of the origin) is not". Most applied policy ABMs never compare metrics but use trust/credibility scaling, decay toward zero, clipping, zero initialisation.
Fix: add a subsection/box "Origin-dependent operations to audit in any policy ABM" (multiplicative scaling, decay/forgetting toward 0, angular/normalised quantities, clipping, zero-initialised states, ratio outcomes) plus a cheap diagnostic: recode the space with an affine shift, rerun a few seeds, flag outcomes that change. Mention in abstract.

### W4 (Minor, conf 4): Protocol's practical cost and scope unspecified
Anchor: §6 item 3. Realised coverage depends on all other parameters (Euclidean pass 0.58 gated vs 0.55 anchor). Unclear whether matching is per cell/condition, on control or treatment. Item 2 "Never share a numerical bound" contradicted by centred PolicySwarm where shared bound gives near-identical realised pass rates (55 vs 56%) and the same indices as matched-run (189/161).
Fix: specify calibration scope, pilot-run count, relative cost; soften item 2 to "acceptable only if realised coverage is shown to match"; consider merging items 2 and 3.

### W5 (Minor, conf 4): Policy stakes of the withdrawn finding never stated
Anchor: absence in §5.1. No statement of what policy conclusion the reversal would have supported, why final-variance shock effect is decision-relevant, or why a lag-40 ratio index is the right summary; ratio indices with small lag-0 denominators can exaggerate (478 corner).
Fix: 2–3 sentences on the averted policy reading; report absolute shock effects alongside the index (appendix table).

### W6 (Minor, conf 3): Policy-ABM literature absent
Anchor: refs.bib has 7 entries, all BC/ODD; nothing on policy/regulatory ABMs, institutional-trust modelling, ABM validation for policy.
Fix: cite representative policy ABMs with multiplicative trust/credibility scaling; position the origin audit relative to existing ABM validation/reporting guidance.

## Detailed comments
- Title/abstract: title says threshold "manufactures geometry effects", but in the headline case the threshold changed only size; the sign came from trust shrinkage. Name both mechanisms. Clarify whether the "unpublished draft" was ever circulated.
- §5: check the interaction-column sign convention — positive interactions coincide with cosine having the lower index (160 vs 124 → +0.018), negative with higher (160 vs 478 → −0.057); consistent with "cosine minus Euclidean" only if the relative shock effect is negative. State the sign of the shock effect or fix the caption.
- §5: the trust formula also shrinks the bias term b_i; the centred patch shrinks (p + b − 0.5). Is bias shrinkage intended? Interacts with W1.
- §5: report seed-level CIs for the 162/124 vs 160/124 comparison.
- §6: needs (a) origin audit generalised beyond angular distances, (b) shrinkage target as a parameter, (c) calibration scope/cost; a worked example or code snippet would help uptake.
- Ethics: say explicitly the error was caught before any external use; avoid implying the audited model is now "correct" — it is one defensible specification.

## Minor issues
- §5.2: the anchor rate is matched to the Euclidean gated pull, so cosine's gated and anchor corners are not symmetric; note this.
- Figure 3: y-axis floor at 100 hides how close bars are to no amplification; add absolute effects or error bars.
- §4: the drift explanation is speculative; label it a hypothesis.

## Questions
1. Under a status-quo or own-opinion shrinkage target, do both geometries still amplify?
2. Was the original reversal ever communicated outside working notes?
3. Was the cosine bound in Exp 4 calibrated on control, treatment, or both, and at which lag?
4. What is the sign of the mean shock effect on final variance, and how does it map onto the interaction column?
5. Were other mechanisms (media pull, shocks) audited for origin dependence beyond the gate equivariance check?
