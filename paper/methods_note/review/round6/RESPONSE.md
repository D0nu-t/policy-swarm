# Response to the round-5 verification review

Round-5 report: `review/round5/VERIFICATION_REPORT.md`. No new experiments. Anchors are checked by `python review/check_response.py review/round6/RESPONSE.md`.

## Corrections to the round-5 letter
- **R2 "every case threshold":** some were given as ranges. They are now listed one by one.
- **S1 "added to both crossing tables":** `tab:crossing` already had a radial row and was only relabelled; the radial row is new only in `tab:crossing-run`.
- **NEW-4 "the effect is small":** true of the pooled shares only. The per-cell gap is now reported.
- **NEW-10 "a difference everywhere":** the `tab:crossing-run` header still said log₂. Fixed.
- **C5 "says which studies":** the sentence named only a category. It now says plainly that we did not survey published studies.

## must_fix
| Item | What changed | Where |
|---|---|---|
| R2 | **DOI still deferred by the author.** Every case threshold is now given as a value: run-matched 0.922 (anchor) and 0.938 (gated) centred, 0.0293 and 0.0352 unit; per trust target 0.875, 0.922, 0.906 and 0.719. | `app:policyswarm` |
| R13 | The dispersion margin is justified (both measures are shares in [0,1]). The case equivalence margin is now defined before the start-vs-run result that uses it. The text says why the per-cell secondary intervals are tabulated for run-matching, and points to the released result table holding them for every rule. | `sec:matching`, `sec:case` |

## should_fix and new issues
| Item | What changed | Where |
|---|---|---|
| R5 | The note is related to `cite:schweighofer2020`: any comparison of how such models measure agreement between opinion vectors meets the choices listed here. | `sec:related` |
| R12 | A third flag marks the `\VCalAtTol` calibrations whose pilot error sits at the tolerance. | `tab:calibration`, `sec:matching` |
| S2 | The audit is positioned against `cite:falcone2023`: there trust is measured, while in PolicySwarm the trust target is not measured at all, which is why it is varied. | `sec:related` |
| NEW-4 | Per-cell gaps between the two spaces are reported: up to `\VSettledCellGapTwo` points after 2,000 rounds and `\VSettledCellGapFour` after 4,000. A cube-scaled tolerance would remove them; it needs a re-run, which is left out and said so. | `sec:ruler`, `tab:settled` |
| NEW-6 | The trust rows are discussed. Centre shrinkage lifts cosine's index above 100 in both (`\VCDraftSplitCosIdx` to `\VCDraftTrustCosIdx`; `\VCDraftCosRngCosIdx` to `\VCDraftCosRngTrustCosIdx`), while the interaction stays positive (`\VCDraftTrustInter`, `\VCDraftCosRngTrustInter`). | `sec:case` |
| NEW-13 | The appendix says the code always used noise SD 0.06 and that an earlier version of the appendix misreported it. | `app:policyswarm` |
| NEW-14 | Step (6) of Appendix B now refers to the perception formula in Submodels instead of restating an older form. | `app:policyswarm` |
| NEW-15 | The `tab:crossing-run` header no longer says log₂. | `tab:crossing-run` |
| NEW-16 | The `tab:secondary-cells` caption says convergence time is censored at 4,000 rounds. | `tab:secondary-cells` |

## consider
- **C5:** now says we did not survey published studies and names the kind of study most worth rechecking (`sec:protocol`).
- **S10:** still declined.

## Still open
- **R2, S5:** the Zenodo DOI (deferred by the author).
