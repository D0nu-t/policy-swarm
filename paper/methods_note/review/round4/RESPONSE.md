# Response to the round-3 verification review (in progress)

Round-3 report: `review/round3/VERIFICATION_REPORT.md`. This letter grows item by item as the round-3 residuals are fixed; items not listed here are still open. Anchors follow the same rules as round 3 and are checked by `python review/check_response.py review/round4/RESPONSE.md`.

## R13: pooled summaries, and the two "no difference" claims (must_fix)

**Round-3 residual.** The headline medians and equivalence counts pooled cosine and angular, so a count out of 36 counted near-duplicate cases twice. "One gate" and "one common ruler removes the difference" rested on maxima and medians.

**What changed.**
- **Pooled counts split.** Every headline summary in the abstract and §4 now gives cosine and angular separately, each out of 18 cells (`\VCellsPerGeom`), for the pass rate and the primary outcome under all four threshold rules, and for the run-matched secondary outcomes. For example:
  - run-matched pass rates are equivalent in `\VRunPassEquivCos` and `\VRunPassEquivAng` of 18 cells;
  - run-matched group counts are equivalent in `\VRunGroupEquivCos` and `\VRunGroupEquivAng`.

  The design paragraph says why: the lemma makes the two one gate only when start-matched, and their run- and early-matched thresholds are calibrated separately (`sec:matching`, `lem:monotone`). The split changes no conclusion.
- **"One gate" is now an equivalence result.** Start-matched cosine and angular runs are equivalent in pass rate in `\VCosAngPassEquiv` of `\VCosAngCells` cells and in group count under the common ruler in `\VCosAngCommonEquiv` of `\VCosAngCells`. The maximum and median stay as description (`sec:matching`).
- **"The common ruler removes the difference" is now an equivalence result.** With each geometry's own ruler the two are equivalent in only `\VCosAngOwnEquiv` cells; with the common ruler, in `\VCosAngCommonEquiv`. This is stated in the abstract and in §5 (`sec:ruler`).
- **New appendix table.** Per-cell cosine-vs-angular gaps with 95% intervals and equivalence marks, for the pass rate, the common ruler and the own ruler (`tab:cos-ang`).
- Both tests use the paper's existing margins (±0.02 pass rate, ±0.25 log₂), fixed before analysis.

## Other round-3 residuals (no new experiments)

| Item | What changed | Where |
|---|---|---|
| R1 uncited "most BC studies" | Uniform independent starts are now attributed to the original models (`cite:deffuant2000`, `cite:hegselmann2002`). | `sec:threshold` |
| R3 secondary outcomes; recommended design | New appendix table of variance, radial spread, directional dispersion, effective groups and convergence time under all four rules, for each geometry. A paragraph says why the design is "recommended" (it removes both of the draft's couplings) and gives the start-matched result: `\VFCentredMatchedAnchorInter` against `\VFCentredRunAnchorInter`. The outcome-independent calibration added in round 3 is unchanged. | `tab:secondary`, `sec:case` |
| R5 roles of cited studies | `cite:fortunato2005` is now described as comparing confidence-region shapes for two-dimensional opinions in the Hegselmann–Krause model, not as evidence that Euclidean distance is the default. `cite:huet2008` and `cite:kurahashi2016` are described by what they show, and the paragraph says how they bear on this note. All descriptions were checked against the papers' abstracts. | `sec:related` |
| R6 tag for audit item 4 | Marked "a known identity, stated here as a lemma". | `sec:protocol` |
| R11, S1 radial spread; dispersion undefined | Radial spread and directional dispersion are defined. The run-matched radial gap is reported (`\VRunRadialGapCos`, `\VRunRadialGapAng`) with the fact that it goes in both directions (22 cells positive, 14 negative). | `sec:matching` |
| R12 flags; pilot guidance | The `\VCalEvalMiss` calibrations not equivalent on the evaluation seeds are flagged in the table. Audit item 3 now gives pilot-size guidance. | `tab:calibration`, `sec:protocol` |
| R14 extreme cell | The wrong sentence is replaced. Cosine's effect grows from `\VCUnitRunGatedCosZero` to `\VCUnitRunGatedCosForty`, nearly tripling; Euclidean's grows from `\VCUnitRunGatedEucZero` to `\VCUnitRunGatedEucForty`. This is a large change on the shared scale too. | `sec:case` |
| S2 trust literature | `cite:gestefeld2023` (trust in government, calibrated to survey data) is cited as a possible source of evidence on the trust target. Checked against the JASSS page. | `sec:related` |
| S4 signed gaps | Signed medians for all secondary outcomes. The signed variance gap is positive in all 36 cases. | `tab:secondary`, `sec:matching` |
| S10 later-lag effects | Tables 2 and 3 give each geometry's relative shock effect at lags 0 and 40. | `tab:trust`, `tab:anchors` |
| S14 significant figures | ε printed to 3 significant figures with trailing zeros; integer iteration counts. | `tab:calibration`, `sec:threshold` |
| S15 audit item 1 | "Affine change of coordinates (shift and rescale)". | `sec:protocol` |
| NEW-3 Fig. 2 method | The caption gives the ten coverage values, the pass-rate window (the 2,000 rounds) and the band (mean ± 1.96 standard errors). | `fig:curves` |
| NEW-4 settled tolerance | Without new runs, the text states that the tolerance is not rescaled with the cube, so unit-cube runs settle earlier than the identical centred runs, and that settled shares compare only within a space. The data agree: Euclidean unit cells are settled at least as often as their centred twins. | `sec:ruler` |
| NEW-5 stopping time | The introduction no longer says the stopping time changed the differences; it says it could have and here did not. | Introduction, `sec:ruler` |
| NEW-6 backward trust rows | The design now names the two combinations in which the trust step was switched. | `sec:case`, `fig:interaction` |
| NEW-7 early-matched calibration | All `\VEarlyCalTotal` early-matched calibrations met their tolerance (largest error `\VEarlyCalMaxErr`). | `sec:matching` |
| NEW-8 interval methods | Lag indices: paired bootstrap. Interaction: $t$ interval over 100 paired seeds. Stated in the design and the Fig. 4 caption. | `sec:case`, `fig:interaction` |
| NEW-9 terms | "Policy pull" (toward the policy) and "perceived-policy pull" are separate terms in the glossary, the case description and Appendix B. "Corner" no longer names design combinations. | `sec:case`, `app:policyswarm` |
| Bug found while revising | A number macro printed without a following space ("18cells") in ten places, all introduced by the R13 edit; all fixed, and a scan for the pattern now finds none. | `sec:matching` |

## Still open
- **R2, S5:** the Zenodo DOI. Deferred by the author.
- **C2, C4, C5:** not pursued; no new experiments this round.
