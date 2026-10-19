# Verification Review Report, round 5 (2026-10-19)

*Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models.* Revised `e9fde29` against round-4 `6d39dc2`. Venue: JASSS (arXiv first).

Simulated review by an AI model; role-separated, not independent; NOT_CALIBRATED.

## Judge Record
- **Mode:** three-gate re-review, one fenced subagent per gate, run in sequence:
  1. criteria, written without seeing the revision;
  2. verdicts, written without seeing the response letter;
  3. claim matching, with the letter revealed.
- **Disclosure:** `[CONTRACT-ARTIFACTS-UNAVAILABLE: round 1 ran without the sprint contract; decision derived by hand, no checker replay]`.
- **Roadmap** (`round5/roadmap.json`): 18 items. It holds every round-4 item not fully addressed, at its round-4 residual class, plus NEW-10 to NEW-12.
  - R2 and S5 (DOI) are deferred by the author; S10 is declined. All are still verified.
- **Inputs:** `round5/manifest.json`.
- **Routing:** card_mapped (EIC 4, R1 10, R3 1).
- **Artifacts:** `phase1_criteria.json` (15 records), `phase2a_verdicts.json`, `phase2b_matrix.json`.
- **Judge family:** Claude, the same family that drafted and revised the paper. This verification round ran on the same model family that drove the revisions; over-optimization to this judge's latent biases is possible (Ren et al. 2026, arXiv:2607.13104 §8.1.2).
- **Response-letter anchors:** all 31 machine-checked before gate 3.

## Decision
**Major Revision**, now driven only by the DOI. `reject_recommended: false`.
- **Step 1 (gates):** no dissents, no adjustments, nothing pending.
- **Step 2 (base rule):** B1–B3 do not fire. **B4 fires on R2 alone:** it is PARTIALLY_ADDRESSED with a must_fix residual, the placeholder DOI. → **Major.**
- **If the DOI were in place:** R13's residual is now should_fix, so B5 would fire. → **Minor Revision.**
- **Step 3 (floors):** none.

## Revision Response Checklist
| Class | Fully | Partly | Not |
|---|---|---|---|
| must_fix (2) | 0 | 2 (R2: residual must_fix; R13: residual should_fix) | 0 |
| should_fix (13) | 7 | 5 | 1 (S5, DOI) |
| consider (3) | 1 (S15) | 1 (C5) | 1 (S10, declined) |

should_fix addressed rate: 12/13 = 92%.

**Fully addressed this round:** R3, S1, NEW-3, NEW-7, NEW-10, NEW-11, NEW-12, S15.

### Remaining
- **R2 (must_fix):**
  - The DOI is a placeholder.
  - The ODD appendix is otherwise complete, though it gives the run-matched and per-target thresholds as ranges, not every value.
- **R13 (residual should_fix):**
  - The new ±0.02 dispersion margin is not justified.
  - The start-vs-run equivalence result is printed before the margin it uses is defined.
  - Per-cell CIs for the secondary outcomes cover only the run-matched rule.
- **R5:** the note does not say how it relates to Schweighofer 2020.
- **R12:** the five cells whose pilot error sits exactly at ±0.005 are unmarked.
- **S2:** Falcone & Sapienza is cited accurately, but the trust-target audit is not positioned against how trust is modelled there.
- **NEW-4:**
  - The coding dependence of the settled share is quantified only as pooled shares, which hide per-cell gaps of up to 12 points.
  - No coding-invariant version is reported.
- **NEW-6:** the results of the two trust rows are not discussed in the text.
- **C5:** the sentence names a category of studies to recheck, not specific ones.

## New Issues (frozen at gate 2; all minor)
| # | Attribution | Issue |
|---|---|---|
| NEW-13 | indeterminate | The noise SD in Appendix B changed from "0.06–0.12" to "0.06" with no number changing. (This is a description correction: the code and the runs were unchanged and always used 0.06. The issue is that the text does not say so.) |
| NEW-14 | regression | Appendix B step (6) still describes perception the old way, contradicting the new general formula in Submodels. |
| NEW-15 | regression | The `tab:crossing-run` header still says "log₂ gap", though its dispersion row is now a difference. |
| NEW-16 | regression | The `tab:secondary-cells` caption says "after 2,000 rounds" for convergence time, which is censored at 4,000. |

## Response letter (gate 3)
**31 claims: 26 accurate, 5 overstated** (round 4: 3 of 27; round 3: 11; round 2: about 25). None changes a verdict.
- **R2:** "every case threshold". Some are given as ranges.
- **S1:** "added to both crossing tables". `tab:crossing` already had a radial row and was only relabelled.
- **NEW-4:** "the effect is small". True of the pooled shares; per cell the gap reaches 67% vs 55%.
- **NEW-10:** "a difference everywhere". The `tab:crossing-run` header still says log₂.
- **C5:** "says which studies". It names only a category.

## Decision Rationale
- **The paper is one external step from Minor Revision.** Every scientific item from round 1 is resolved. Of the two must_fix items, only R2's DOI still leaves a must_fix gap; R13's gaps are now should_fix.
- **The remaining should_fix work is short:**
  - justify the dispersion margin and define the margin before its first use;
  - extend the secondary-outcome CIs to the other rules, or say why run-matching only;
  - mark the five at-tolerance calibration cells;
  - a sentence each relating the note to Schweighofer and to Falcone & Sapienza;
  - per-cell settled gaps by space, or a coding-invariant tolerance (the latter needs a re-run);
  - a sentence on the two trust rows;
  - name example studies for C5, or reword it;
  - fix Appendix B step (6), the two headers and captions, and add a note that the noise correction was a description error.

## Residual Issues
- **Must fix:** R2, the Zenodo DOI.
- **Should fix:** R13 residuals, R5, R12, S2, NEW-4, NEW-6, NEW-13 to NEW-16.
- **Consider:** C5.

## Sprint contract status
The review did not run under a sprint contract. The three gates followed the withholding matrix by instruction to fenced subagents; nothing enforced it mechanically.

## Attachment: Acronym Check (advisory, #849)
Not checked: `check_acronyms.py` accepts Markdown or plain text, and the manuscript is LaTeX.
