Simulated review by an AI model; role-separated, not independent of other seats; NOT_CALIBRATED.

# Peer Review Report — Journal-Fit Reviewer (EIC)
Identity: JASSS associate editor handling opinion-dynamics and model-replication/comparison papers. Venue criteria: criteria_binding_unavailable (field-general; JASSS policy statements unverified).

## Recommendation: Major Revision. Confidence 4.

## Summary assessment
Central point is correct, clearly made and practically useful; coverage numbers striking (94% vs 14%); backward/forward case audit honest and instructive; the trust-toward-origin sign finding is the most interesting result. Not yet a full JASSS research article: it never shows the shared-ε practice is common in published work; literature engagement very thin (six works cited); half its empirical weight rests on correcting an unpublished, inaccessible draft; its headline remedy (match on realised pass rate) conditions on an endogenous quantity so the "removal" is partly true by construction. All fixable.

## Strengths
- S1: Simulation-free demonstration of the confound (§3, Table 1).
- S2: Showing t=0 matching is not enough — coverage drift (Fig. 2 left).
- S3: Transparent two-direction audit; honest "They do not"; exact reproduction 131/75 (§5.3).
- S4: Reproducibility infrastructure: generated macros, pinned commit + patch, ODD appendix.

## Weaknesses
### W1 (Major, conf 4): Never shows the targeted practice is common
Anchor: Abstract "A common way to do so is to run each metric at the same numerical confidence bound"; §3 "conventional bounds". Only published example (Li et al. 2026) already noticed the confound; the only demonstrated victim is the author's unpublished draft.
Fix: short systematic survey of multidimensional BC papers comparing metrics (stated search), reporting how ε was set per metric and whether coverage was reported; if few share ε, reframe around realised-coverage drift and origin-dependence.

### W2 (Major, conf 4): Case study corrects an unpublished, inaccessible draft
Anchor: §5.1 "An earlier draft of our paper reported...". ~1/3 of the paper on a draft readers cannot see; PolicySwarm not cited/archived; footnote admits draft figures differ from saved results.
Fix: recast §5 as a demonstration on a documented model (minimal ODD or cited archive); present "uncentred + shared ε" as a plausible design choice and show how each protocol item catches its artefact; keep draft history to a sentence/footnote; archive with persistent ID.

### W3 (Major, conf 3): Main remedy conditions on an endogenous quantity
Anchor: Abstract "matching on the share admitted over the whole run does...". Realised pass rate is an outcome; matching on it equalises part of the geometry effect; "removes the interaction gap" (0.01) largely by construction; protocol item 3 prescribes it as default.
Fix: state run-matching is an estimand choice ("geometry effect at equal realised interaction") vs t=0 matching ("effect including interaction-rate channel"); recommend reporting both.

### W4 (Major, conf 4): Residual geometry effects contradict "neither layer is a property of geometry"
Anchor: Table 2 centred/matched run/anchor: 189 vs 161, interaction +0.034 [+0.027,+0.042], p≈6e-15; minimal-model variance gap up to 2^2.58. Update rule is part of what modellers mean by "geometry".
Fix: define geometry = gate + update rule vs gate only; state the surviving effect plainly in abstract and conclusion.

### W5 (Major, conf 4): Thin literature engagement
Anchor: absence in Intro/§2. Six works cited; flache2017 in refs.bib but never cited; missing model alignment/docking tradition (e.g. Axtell et al. 1996; Wilensky & Rand 2007, JASSS — details unverified), multidimensional-BC surveys (Lorenz 2007), and "difference between significant and not significant is not itself significant" behind protocol item 5.
Fix: related-work section; cite Flache 2017; state which protocol items are new (1, 3–4 seem new; 2 and 5 restatements).

### W6 (Major, conf 3): Evidence narrow for general claims
Anchor: Abstract "for any study that compares distance measures". Deffuant only, uniform independent starts, n=500 ER, d∈{2,4,8}, three coverage levels, fixed 2,000-round horizon with unsettled runs; one case model.
Fix: (a) narrow claims and submit as a short methods piece if JASSS has one (unverified), or (b) for full article add an HK variant, non-uniform/clustered starts, and runs to convergence for low-coverage cells.

### W7 (Minor, conf 4): Title overstates
Anchor: §5.3 "The gate choices change the size of the effect, never its sign." Title says unmatched bound "manufactures geometry effects".
Fix: title covering both mechanisms, e.g. "Shared thresholds and uncentred origins confound distance-measure comparisons in bounded-confidence models".

### W8 (Minor, conf 4): Medians are of absolute gaps but not stated
Anchor: Fig. 2 — t=0 pass gaps negative, text reports +0.16; group gap "reaching 2^7.1" is actually −7.1.
Fix: write "median absolute gap" and give direction where it matters.

### W9 (Minor, conf 3): No persistent identifier for model/code
Anchor: Code and data "in the PolicySwarm repository". Fix: archive with DOI (CoMSES likely; unverified).

## Detailed comments
- Journal fit: squarely in JASSS scope; ~4,300 words with 3 figures and 2 tables is short for a full article carrying three studies plus protocol; fits better as a short methods/reporting-practice piece unless W1, W5, W6 addressed.
- Originality: core size/shape observation not wholly new (Li et al.); new parts are quantification across centring and dimension, t=0 drift, operational cosine/angular monotone equivalence, origin-dependence of multiplicative steps — lead with these.
- Structure: case's lesson (origin) is a different mechanism from the minimal model's (coverage); §5.4 bridge is loose. Protocol item 5 supported by neither study directly.
- No separate conclusion; add a short discussion (protocol cost; which published results to revisit).

## Questions
1. Can you name published multidimensional BC studies comparing metrics at a shared ε, and would their conclusions change?
2. Why is equal realised pass rate the right estimand rather than equal t=0 coverage? Report both?
3. How should a protocol user report the centred run-matched +0.034 interaction — geometry or update-rule effect?
4. Is PolicySwarm documented/archived anywhere accessible?

## Minor
- Single author but "we"/"our paper"; remove \date{Draft, \today}.
- flache2017 uncited; refs.bib header comment points to a private notes file — remove; Li et al. has both journal DOI and preprint note — settle on one.
- Fig. 3: annotate Table 2 interaction CIs. Table 1 "0%" vs text "0.0%". Fig. 1 caption "conventional bounds" needs citation or rewording.
- Protocol items 2 and 3 overlap; say whether item 2 is the minimum and item 3 preferred.

## Criterion judgements (NOT_CALIBRATED, field-general)
Originality PARTLY_MEETS; Methodological rigor NOT_ASSESSED; Evidence sufficiency PARTLY_MEETS; Argument coherence PARTLY_MEETS; Writing quality MEETS; Literature integration DOES_NOT_MEET; Significance PARTLY_MEETS. Decision-bearing: W1, W4, W5, W6. No text in the manuscript attempted to instruct reviewers.
