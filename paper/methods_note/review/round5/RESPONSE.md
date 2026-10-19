# Response to the round-4 verification review

Round-4 report: `review/round4/VERIFICATION_REPORT.md`. Revised manuscript of 2026-10-19; no new experiments. Every anchor is checked by `python review/check_response.py review/round5/RESPONSE.md`.

## Corrections to the round-4 letter
- **R13:** the letter said every headline summary was split. One pooled count, the calibration check "32 of 36", remained. It is now split (below).
- **R11:** the letter quoted "22 cells positive, 14 negative" for radial spread. Those counts were never in the manuscript, and they pooled the two geometries. The manuscript says only that the radial gap runs in both directions, with per-cell intervals in `tab:secondary-cells`.
- **R5:** the letter said every cited study was tied to the note. Huet had no tie, and "these studies show that the shape matters" contradicted the Fortunato result. Both are fixed (below).

## must_fix
| Item | What changed | Where |
|---|---|---|
| R2 citable model | **The DOI is still deferred by the author.** The PolicySwarm ODD summary now gives every case threshold (Euclidean and cosine, all rules, all trust targets), the influence weight (degree over largest degree), the policy point, the bias weights, the fixed trust, and the general perception formula with each trust target and the level-shift control. The noise standard deviation is corrected to 0.06 on every dimension; the round-3 text said 0.06–0.12, which does not hold for this policy. | `app:policyswarm` |
| R13 statistics | Per-cell 95% intervals for every run-matched secondary outcome (new table). The last pooled count is split: `\VCalEvalEquivCos` cosine and `\VCalEvalEquivAng` angular cells of 18. The case margin is disclosed as set after the round-2 own-target interval had been reported, so that test reads as confirmatory, not pre-registered. "Almost the same interaction" is replaced by an equivalence result: paired difference `\VRunVsStartDiff`, 90% interval `\VRunVsStartCI`, within the margin though not zero. | `tab:secondary-cells`, `sec:matching`, `sec:case` |

## should_fix and new issues
| Item | What changed | Where |
|---|---|---|
| R3, NEW-7 early window | "Ends before most opinion groups have formed" is withdrawn: no saved checkpoint supports it (the earliest is round 500). The window is now described as early and fixed in advance. | `sec:matching` |
| R5 roles | `cite:huet2008` is tied to the note (a change to the interaction rule, not the distance, moved a group count, as the update step does in our crossing). `cite:schweighofer2020` is described from its abstract. The contradiction is removed: shape matters for some outcomes and not others (`cite:fortunato2005`: thresholds unchanged, cluster arrangement follows the space). | `sec:related` |
| R12 flags | A second flag marks the `\VCalEvalBeyondTol` evaluation gaps larger than the pilot tolerance, as well as the `\VCalEvalMiss` that are not equivalent. | `tab:calibration`, `sec:matching` |
| S1 radial row | Radial spread added to both crossing tables. The run-matched result is reported: `\VXRCosEucRadial` for the cosine gate with the Euclidean step. | `tab:crossing`, `tab:crossing-run`, `sec:matching` |
| S2 trust literature | Added `cite:falcone2023`, an agent-based model in which survey-estimated trust in institutions drives acceptance of public-health restrictions (checked against the journal record). No model found discounts a policy signal by trust exactly as PolicySwarm does; the text does not claim one. | `sec:related` |
| NEW-3 curves design | The response-curve design (grid, seeds, rounds, band) is now in the Design section; the caption refers to it instead of repeating it. | `sec:matching`, `fig:curves` |
| NEW-4 settled tolerance | Quantified by space: `\VUnsettledTwoUnit` of unit-cube and `\VUnsettledTwoCentred` of centred Euclidean runs are unsettled after 2,000 rounds (`\VUnsettledFourUnit` and `\VUnsettledFourCentred` after 4,000). The effect is small. | `sec:ruler` |
| NEW-6 trust rows | The text says what each of the two trust rows isolates. | `sec:case` |
| NEW-10 −21.96 artefact | Directional dispersion is a share that can be near zero, so it is now compared as a difference with the pass-rate margin (±0.02) everywhere: text, crossing tables and the secondary tables. The run-matched dispersion results change scale, not direction; the crossing claims were rechecked on the new scale. | `sec:matching`, `tab:secondary`, `tab:crossing` |
| NEW-11 coordinates and names | Radial spread and dispersion are stated to be computed in each run's own coordinates, so in the unit cube they measure from the corner; they are treated as secondary for that reason. Tables use one name per measure. | `sec:matching`, `tab:crossing` |
| NEW-12 captions | `tab:secondary`: parentheses, convergence time censored at 4,000 rounds, and which outcome is a difference. The duplicated grid is removed from the Fig. 2 caption. | `tab:secondary`, `fig:curves` |

## consider
- **S15:** the clipping entry in the box now says why clipping depends on the origin (`sec:background`).
- **C5:** one sentence says which published studies are most worth rechecking against the list (`sec:protocol`).
- **S10:** lag-20 effects are not added; tables give lags 0 and 40.

## Still open
- **R2, S5:** the Zenodo DOI (deferred by the author).
