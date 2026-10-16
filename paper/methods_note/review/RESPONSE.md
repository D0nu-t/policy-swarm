# Response to Reviewer Comments

## Manuscript Information
- **Title (revised)**: Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models
- **Title (round 1)**: An unmatched confidence threshold manufactures geometry effects
- **Review round**: round 1 → revision 1 (simulated review, `EDITORIAL_DECISION.md`, 2026-10-16)
- **Status of this letter**: draft, all results in (2026-10-16).

---

## Summary of Changes

The reviewers agreed on three blocking problems: matching over the run was presented as a fix although it fixes the outcome partly by construction (B1); the residual geometry effect was understated, and by the paper's own interaction test the draft's "reversal" was an attenuation (B2); and group counts used a metric-specific ruler (B3). All three were valid. Fixing them changed what the paper is about.

The revised note is organised around **five hidden choices** in comparisons of distance measures, each one of which we met in our own work: the threshold value, when coverage is matched, where the origin sits, which test is read, and how outcomes are counted (ruler and stopping time). The minimal-model evidence was rerun from scratch and the case study re-analysed and extended.

### Major Changes
1. **Matching is now an estimand, not a correction (B1, DA C2).** Three threshold rules (shared, matched at the start, matched over the run) are reported side by side, with whole ε-response curves (Figure 2) instead of one matched point. "Removes the gap" is gone: matched over the run, the pass rates agree in 34 of 36 cases but the primary group outcome is equivalent in only 11.
2. **The interaction is reported in every case cell (B2, DA C1).** A new forest figure and table give the lag × geometry interaction with 95% CIs across all forward, backward, trust and anchor cells. Of 30 configurations, the interaction is positive (cosine attenuates the lag effect) in 25, null in 2 and negative in 3. In the draft's own engine it is +0.034 [+0.025, +0.044], the same sign as in the recommended design (+0.034 [+0.027, +0.042]). The negatives are the two unit-cube gated cells with a matched threshold, and the draft setting with trust shrinking toward each agent's own opinion; under that target the recommended design's interaction is null (+0.001 [−0.004, +0.007]). So the sign of the comparison holds across every engine version and every fix, but not across every trust target, and the paper now says so.
3. **One ruler for every metric (B3).** The primary outcome, named before analysis, is the number of groups holding at least 1% of agents, counted with one Euclidean radius in centred coordinates. A radius sweep shows that metric-specific rulers made cosine and angular gates that admit the same pairs look different (median log₂ gap 0.12, up to 1.36) when under the common ruler they agree (median 0.00).
4. **New experiments**: ε-response curves (6 spaces × 3 metrics × 10 coverages × 50 seeds); a gate × update-rule crossing (7,200 runs); a 4,000-round horizon with checkpoints; a trust-anchor 2×2 with a level-shift control; a shrinkage-target sweep (corner, centre, status quo, own opinion).
5. **Statistics**: paired bootstrap 95% CIs throughout; equivalence by TOST with margins fixed before analysis (±0.02 pass rate, ±0.25 log₂); cosine and angular reported separately; calibration error reported per cell.

### Structural Changes
- New title and abstract; introduction rebuilt around the five choices; Lorenz (2008) → coverage → over-the-run matching set out as a ladder.
- §2 states the update rules as equations, the cosine/angular/normalised-Euclidean identity as a lemma, and the origin as an affine-equivariance point.
- §3 replaces the wrong "angles do not concentrate" sentence with a proposition giving the concentration limits.
- §4 (when coverage is matched), §5 (ruler and stopping time), §6 (origin and test, in the governance model), §7 audit list of six items, appendix tables for calibration and the crossing.

### New Content
- References added: Axtell et al. 1996; Wilensky & Rand 2007; Gelman & Stern 2006; Lakens 2017; Lorenz 2007; Fortunato 2005; Huet et al. 2008; Kurahashi-Nakamura et al. 2016; Baumann et al. 2021; Aggarwal et al. 2001.
- Code: `trust_anchor`, `gate_space` and `policy_pull` switches in PolicySwarm (default unchanged; golden tests pass), `CITATION.cff`, a Zenodo archive (DOI pending), a dashboard audit of every batch run.

---

## Devil's Advocate CRITICALs

### C1: the sign story conflicts with protocol item 5
> The interaction keeps the same sign everywhere… The "threshold = size, origin = sign" decomposition does not hold; the withdrawn claim may be "attenuates" rather than "reverses".

**Author Response**: We agree. Reading each geometry's lag index against 100 is exactly the per-condition test our own item 5 warns against. The draft's "reversal" was the cosine index crossing 100 while the comparison with Euclidean kept its sign.

**Changes Made**: §6 now leads with the interaction in every cell (Figure 4, Tables 3–4). The "size vs sign" decomposition and "neither layer is a property of geometry" are removed. Choice 4 ("which test is read") is one of the paper's five choices, with this case as its example: the draft's cosine index (78 [73, 83]) fell below 100 while the interaction kept its sign.

### C2: run-matching equalises the group outcome by construction
> Matching on the realised pass rate largely fixes the group outcome by construction… and removes a genuine mediating pathway.

**Author Response**: Partly agree. With the effective number of groups as the outcome, the coupling is close to mechanical, and that outcome produced the round-1 "removal". With the ≥1%-groups outcome under a common ruler, matching over the run does *not* remove the gap (median |log₂| 0.70; 11 of 36 equivalent). We now present the two matched points as two estimands, one including and one excluding the metric's effect on how often agents interact, and show the whole response curve so a reader can see where each sits.

**Changes Made**: §4 "Matching over the run fixes the interaction rate, not the group structure"; Figure 2; protocol item 3. The over-the-run calibration window is the first 2,000 rounds, chosen in advance; we did not add a separate early-window calibration, because the curves show the comparison at every coverage level.

---

## Response to Required Revisions

| # | Required revision | Status | Response summary | Location |
|---|---|---|---|---|
| R1 | Survey published comparisons or reframe; drop "A common way" | Partially addressed | Reframed as a pre-emptive audit; prevalence claim removed. We did not run a systematic survey of how published studies set ε (named as a limitation of scope) | §1 |
| R2 | Recast §5 on a documented, archived model; short disclosure + stakes | Completed (DOI pending) | Case rests on PolicySwarm 1.2.0, archived with a DOI and described in an ODD-style summary; the draft is a two-sentence disclosure | §6, Code and data |
| R3 | Run-matching as an estimand; t=0 and run side by side | Completed | Three rules side by side; ε-response curves; "removes the gap" dropped | §4, Fig. 2 |
| R4 | Interaction in every cell; residual effect in abstract and §5.3 | Completed | Forest figure over 30 cells (25 positive, 2 null, 3 negative); residual effect 189 vs 161, interaction +0.034, in abstract and §6 | §6, Fig. 4 |
| R5 | Related work | Completed | References above; flache2017 dropped | §1–2 |
| R6 | Position: volume → coverage → dynamic matching | Completed | Ladder in §1; protocol says which items are new | §1, §7 |
| R7 | Correct the Lorenz 2008 citation | Completed | Now cited for L1/L∞ volume matching | §1 |
| R8 | Narrow general claims | Completed | Claims tied to the tested design; limitations list untested choices | §1, Limitations |
| R9 | One metric-independent ruler / radius sweep; cosine vs angular | Completed | Common ruler primary; radius sweep 0.01–0.2 ε | §5, Fig. 3a |
| R10 | Unconverged share; "exceptions" sentence; convergence time | Completed | Unsettled share at 500 / 2,000 / 4,000 rounds (44% / 26% / 13% Euclidean); gaps stable | §5, Fig. 3b |
| R11 | Report all outcomes; name the primary | Completed | Primary named; variance, radial and directional spread, effective groups reported | §4 |
| R12 | Calibration error per cell; max-iter / monotonicity | Completed | 36/36 within 0.005; all monotone; table | App. Table A1 |
| R13 | Paired bootstrap CIs; TOST; cosine and angular separately | Completed | Throughout | §4 |
| R14 | Isolate threshold from centring, or restate "size"; explain 478 | Completed | "Size" claim withdrawn; 478 explained by a small lag-0 effect (−0.0026), with absolute effects | §6 |
| R15 | Trust 2×2 + level-shift control | Completed | Corner trust + unit gate reproduces the draft (123 / 78 vs the draft engine's 126 / 77); with a centred gate cosine is 103 [98, 110]. The uniform shift moves cosine only to 107 and leaves Euclidean at 161: most of the corner's effect comes from shifting distrustful agents further, not from the mean | §6, table |
| R16 | Shrinkage target as a parameter; ≥1 alternative | Completed | Four targets. Status quo ≈ centre; corner puts cosine at 100 [97, 103] even in the recommended design; own opinion makes the interaction null (recommended) or negative (draft setting). Euclidean's lag index ranges 117–191 across targets | §6, table |

## Response to Suggested Revisions

| # | Suggestion | Status | Response summary |
|---|---|---|---|
| S1 | Define "geometry"; radial vs directional; gate × update crossing | Adopted | Crossing run: the update rule drives most of the variance increase, the gate drives directional spread; radial spread does not split cleanly |
| S2 | Policy-ABM / trust / validation literature | Partially adopted | Docking/alignment literature added; policy-ABM validation literature kept brief for length |
| S3 | Retitle | Adopted | New title names the five choices |
| S4 | "Median absolute gap" with signs | Adopted | Wording fixed; signed values in tables |
| S5 | Persistent identifier | Adopted (DOI pending) | `CITATION.cff`; Zenodo |
| S6 | Merge/rank protocol items; soften "never share" | Adopted | Six items; "do not rely on a shared threshold value" |
| S7 | Cite or relabel "conventional bound" | Adopted | Removed |
| S8 | Housekeeping | Adopted | refs.bib comment, date, Li et al. entry, angular naming |
| S9 | CIs on lag indices and figure | Adopted | Indices reported with bootstrap CIs |
| S10 | Absolute shock effects next to the ratio | Adopted | Lag-0 effects reported beside indices |
| S11 | 9 independent Euclidean cells, not 18 | Adopted | |
| S12 | Clipping frequency after angular steps | Adopted | Recorded per run (`clip_rate`); reported in text |
| S13 | Concentration limits as a proposition | Adopted | Proposition 1 |
| S14 | Lemma; ε to 3 s.f. | Adopted | Lemma 1 |
| S15 | Origin / affine-equivariance audit | Adopted | Protocol item 1; §2 "The origin" |
| S16 | Calibration scope, pilot count, cost | Adopted | 50 pilot seeds, bisection, tolerance 0.005 |
| S17 | Interaction sign convention; is bias shrinkage intended? | Adopted | Sign stated (Euclidean minus cosine lag contrast); trust shrinks perceived policy and bias together, now an explicit parameter |
| C1 | L1/L∞ under volume vs coverage | Not adopted | Out of scope for a short note |
| C2 | HK, clustered starts, μ, n, network | Not adopted | Named in Limitations |
| C3 | Coverage for HK / asymmetric bounds | Not adopted | Named in Limitations |
| C4 | Horizon 500–8,000 | Partially adopted | 500–4,000; gaps stable over that range |
| C5 | Protocol cost; which results to revisit | Partially adopted | Cost noted in the protocol |

---

## Index of reviewer weaknesses → revision items

| Reviewer item | Addressed by |
|---|---|
| EIC W1 practice not shown common | R1 |
| EIC W2 case on an unpublished draft | R2 |
| EIC W3 remedy conditions on an endogenous quantity | R3, C2 above |
| EIC W4 residual geometry effects | R4, C1 above |
| EIC W5 thin literature | R5 |
| EIC W6 narrow evidence | R8 |
| EIC W7–W9 title, median wording, identifier | S3, S4, S5 |
| R1 W1 cluster outcome not invariant | R9 |
| R1 W2 ≥1% group outcome unreported | R11 |
| R1 W3 non-convergence | R10 |
| R1 W4 calibration under-powered | R12 |
| R1 W5 no uncertainty or equivalence standard | R13 |
| R1 W6 "size, not sign" not shown | R14, C1 above |
| R1 W7 trust 2×2 and level shift | R15 |
| R1 W8 variance is Cartesian | S1 (radial vs directional reported separately) |
| R2 W1 Lorenz 2008 miscited | R6, R7 |
| R2 W2 literature, prevalence | R1, R5 |
| R2 W3 run-matching circular | R3 |
| R2 W4 metric-specific radius | R9 |
| R2 W5 angles also concentrate | S13 |
| R2 W6 "one gate" is a definition | S14 (stated as a lemma, not a finding) |
| R2 W7 conventional bound | S7 |
| R2 W8 coordinate equivariance | S15 |
| R2 W9 heterogeneous bounds, HK | C3 (Limitations) |
| R3 W1 centring is an assumption | R16, S15 |
| R3 W2 clear residual effect | R4 |
| R3 W3 general lesson buried | New framing (five hidden choices) |
| R3 W4 protocol cost | C5 |
| R3 W5 policy stakes | R2 (disclosure) |
| R3 W6 policy-ABM literature | S2 |
| DA M1 threshold not isolated as source of size | R14 |
| DA M2 group count not comparable | R9 |
| DA M3 no gate × update crossing | S1 |
| DA M4 t=0 coverage a weak proxy | R3 (t=0 is one estimand; realised pass rates reported) |
| DA M5 prevalence | R1 |
| DA M6 overgeneralisation | R8 |

---

## Closing Statement

The review changed the paper's argument, not only its details. Two things we had presented as findings (that matching over the run removes the geometry gap, and that the origin decided the sign of a geometry effect) did not survive the reviewers' own tests, and the revision now reports them as examples of the choices it warns about. What we could not do within a short note (a survey of published practice, Hegselmann–Krause and clustered starting opinions) is stated in the limitations.
