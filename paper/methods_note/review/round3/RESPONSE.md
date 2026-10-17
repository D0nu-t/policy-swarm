# Response to the round-2 verification review

*Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models*, revision 2 (2026-10-17). Round-2 report: `review/round2/VERIFICATION_REPORT.md`.

**How to read this letter.** Each answer names where the change is, as a LaTeX label (`sec:…`, `tab:…`, `fig:…`, `app:…`), a citation key (`cite:…`) or a number macro (`\V…`) that `numbers.tex` defines. `python review/check_response.py review/round3/RESPONSE.md` checks that every named label exists, every named key is cited, every named macro is defined and every `refs.bib` entry prints. An item that is not done says so.

## What changed since round 2
- **Terms fixed in a glossary** (`GLOSSARY.md` in the repository) and used throughout: geometry, gate, update step, coverage, pass rate, shared / start-matched / run-matched / early-matched threshold, trust target, settled, shock effect, relative shock effect, lag contrast, lag index, interaction.
- **One quantity behind both case numbers.** The lag index is now computed on the relative shock effect, the quantity the interaction uses; the draft's index on the absolute effect is quoted only where the draft is reproduced (`sec:case`).
- **Sign corrected.** The round-2 text and Fig. 4 described the interaction as "Euclidean's lag contrast minus cosine's". It is cosine's minus Euclidean's; shock effects are negative, so a positive value still means cosine attenuates (`sec:case`, `fig:interaction`).
- **Two new runs:** an early-matched threshold rule (first 100 rounds; `sec:matching`), and the gate × update-step crossing repeated with run-matched cosine gates (`tab:crossing-run`).
- **Bootstrap made order-independent.** All intervals in rounds 1 and 2 drew from one shared random generator, so each interval depended on how many had been computed before it. Each interval now uses its own fixed-seed generator, and rebuilding twice gives identical numbers. One reported count changed: run-matched pass rates are equivalent to Euclidean's in 32 of 36 cases (`\VRunPassEquiv`), not 34.
- **Three sentences of the draft were wrong and are corrected:**
  - pilot-seed precision (`\VPilotSEMax`; `sec:matching`);
  - the cost of run-matching (`\VCalCostShare`; `sec:protocol`);
  - the justification of the pass-rate margin (`sec:matching`).

## Required items left open in round 2

| Item | Status | What changed | Where |
|---|---|---|---|
| R2 citable case model | Partly | ODD summary of the parts of PolicySwarm the case uses; pre-audit commit `50a42e5` restored in the disclosure; citation metadata named. **The Zenodo DOI is still a placeholder**: the author creates it. | `app:policyswarm`, `sec:case`, `cite:policyswarm` |
| R5 related work | Done | New Related work section. Every refs.bib entry is now cited, including the four that did not print in round 2: `cite:fortunato2005`, `cite:huet2008`, `cite:kurahashi2016`, `cite:baumann2021`. Also `cite:flache2017` (now cited, not dropped) and `cite:grimm2020` (ODD). | `sec:related` |
| R13 statistics | Done | Per-cell gaps with 95% intervals and equivalence marks, cosine and angular in separate rows, for the pass rate and the primary outcome under all four rules. Both margins are justified in the text. The case-study "no difference" claim now uses an equivalence test on the interaction, with margin `\VInterMargin` fixed before the analysis: the own-target interaction is equivalent to zero, 90% interval `\VTCentredRunOwnCINinety`. Null cells are split into `\VCaseEquivalent` equivalent and `\VCaseInconclusive` inconclusive. | `tab:cells-pass`, `tab:cells-groups`, `sec:matching`, `sec:case` |

## Items partly addressed in round 2 (residual should_fix)

| Item | What changed | Where |
|---|---|---|
| R1 prevalence | The uncited "rarely reach a methods section" is gone. The introduction says the note is a pre-emptive audit list and does not estimate how often choices go unreported. | `sec:related`, Introduction |
| R3 outcome-independent calibration | New early-matched rule on the first 100 rounds, a window that ends before most groups form. Results: pass-rate gap `\VEarlyPassGap` (`\VEarlyPassEquiv` equivalent), group gap `\VEarlyGroupGap` (`\VEarlyGroupEquiv` equivalent). | `sec:matching`, `fig:curves` |
| R6 which items are new | Each audit-list item is marked new, extended or standard, with its source. | `sec:protocol`, `sec:related` |
| R10 settling | "Settled" is defined. Unsettled shares and median convergence time are given per cell and geometry (worst cell `\VUnsettledMaxCell` after 2,000 rounds). | `sec:ruler`, `tab:settled` |
| R11 outcomes | Effective groups reported (`\VRunEffGroupsGap`, `\VRunEffGroupsEquiv` equivalent) with why they are secondary. Convergence time reported (`\VRunConvGap`), censored for `\VConvCensored` of runs. The text says the primary outcome was chosen after round 1. | `sec:matching` |
| R12 calibration | Bisection limits stated (30 steps, tolerance 0.005). Pilot precision reported honestly (median `\VPilotSEMed`, worst `\VPilotSEMax`, above the tolerance). Every run-matched threshold checked on the 100 evaluation seeds with a 95% interval (`\VCalEvalEquiv` equivalent). | `sec:matching`, `tab:calibration` |
| R14 isolating the threshold | New paragraph: the centred cells vary only the threshold rule, and with the anchor pull the interaction barely moves (`\VFCentredRawAnchorInter`, `\VFCentredRunAnchorInter`). In the unit cube it moves a lot (`\VFUnitRawGatedInter` to `\VFUnitRunGatedInter`). | `sec:case` |

## Suggested items

| Item | Status | Where |
|---|---|---|
| S1 define geometry; crossing at run-matched gates | Done. "Geometry" is defined. The rerun shows the variance result holds (`\VXRCosEucVar` vs `\VXRCosCosVar`). The directional result does **not** hold cleanly (`\VXRCosEucDisp` vs `\VXRCosCosDisp`), and the text now says so. | `sec:background`, `sec:matching`, `tab:crossing-run` |
| S2 policy-ABM literature | Done: `cite:gilbert2018`, `cite:windrum2007` (both checked against the JASSS pages). | `sec:related` |
| S4 signed gaps | Done: signed per-cell gaps in the appendix. | `tab:cells-pass`, `tab:cells-groups` |
| S5 persistent identifier | Not done: DOI pending (see R2). | — |
| S8 housekeeping | Partly. "Manifold" is explained as the code's name for the angular geometry. The single-author "we" is kept as house style. | `sec:background` |
| S9 CIs on lag indices | Done. | `tab:trust`, `tab:anchors` |
| S10 absolute effects | Done: lag-0 relative shock effects per geometry in both tables. The draft's absolute-effect indices are quoted (`\VCDraftEucAbsIdx`, `\VCDraftCosAbsIdx`). | `tab:trust`, `tab:anchors`, `sec:case` |
| S13 Proposition consequence clause | Done: Euclidean coverage tends to 0 at a fixed threshold, since only $d_E/\sqrt d$ converges. | `prop:concentration` |
| S14 ε to 3 s.f. | Done. | `sec:threshold`, `tab:calibration` |
| S15 box of origin-dependent operations | Done. | `sec:background` |
| S16 case calibration scope and cost | Done. | `sec:case` |
| S17 sign of the shock effect; bias shrinkage | Done: shocks lower variance, so the effects are negative. Trust scales the bias as well as the policy; the text says this is the model's assumption. | `sec:case` |

## New issues from round 2

| Issue | What changed | Where |
|---|---|---|
| NEW-1 relative shock effect undefined; index vs interaction | Both terms are defined. The index now uses the same quantity as the interaction. The text explains when the two can point different ways: the index is a proportional change within a geometry, and cosine's lag-0 effect is less than half Euclidean's. The own-target cell is worked through. Claims rest on the interaction. | `sec:case`, `tab:anchors` |
| NEW-2 Fig. 4 labels | Rows are labelled in words ("draft engine + cosine step, …"; "centred gate, run-matched, anchor pull, trust to centre"). The equivalence margin is drawn on the figure. | `fig:interaction` |
| NEW-3 response-curve experiment undocumented | Grid, seeds and rounds stated in the caption, with 95% bands. | `fig:curves` |

## Consider items
- **C2:** HK, clustered starts, μ, population size, network and asymmetric thresholds are now named in Limitations; still not run.
- **C4:** the horizon is kept at 4,000 rounds (author's choice); Limitations states the unsettled share at the end (`\VUnsettledFourAll`).
- **C5:** the cost of applying the audit list is stated under the list (`sec:protocol`).
- **C1, C3:** declined, as in round 2.

## Corrections to the round-2 response letter
The round-2 letter claimed about 25 things the manuscript did not contain. This letter replaces it. The checked anchors above are the record of what the manuscript now contains.
