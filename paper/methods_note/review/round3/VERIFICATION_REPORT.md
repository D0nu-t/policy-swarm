# Verification Review Report, round 3 (2026-10-17)

*Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models.* The revised manuscript (working tree of 2026-10-17, frozen in `round3/revised/`) is compared with the round-2 version (`09057cf`, in `round3/original/`). Venue: JASSS (arXiv first).

Simulated review by an AI model; role-separated, not independent; NOT_CALIBRATED.

## Judge Record
- **Mode:** re-review in three gates, one fenced subagent per gate, run in sequence:
  1. criteria, written without seeing the revision;
  2. verdicts, written without seeing the response letter;
  3. claim matching, with the letter revealed.
- **Disclosure:** `[CONTRACT-ARTIFACTS-UNAVAILABLE: round 1 ran without the sprint contract; decision derived by hand, no checker replay]`.
  - The round-3 roadmap (`round3/roadmap.json`) holds the 28 round-2 items that were not fully addressed, each graded at its round-2 residual class (C1 and C3 dropped, as the author declined them), plus round-2 NEW-1 to NEW-3, which the author chose to treat as should_fix.
  - The diff of `main.tex` stands in for the patch chain.
- **Inputs:** `round3/manifest.json` (SHA-256 of every input).
- **Reviewer configuration:** frozen round-1 identities. Routing: card_mapped (EIC 5, R1 9, R2 1, R3 1).
- **Artifacts:** criteria `round3/phase1_criteria.json` (16 records); evidence `round3/phase2a_verdicts.json`; matrix `round3/phase2b_matrix.json`.
- **Judge family:** Claude, the same family that drafted and revised the paper. This verification round ran on the same model family that drove the revisions; over-optimization to this judge's latent biases is possible (Ren et al. 2026, arXiv:2607.13104 §8.1.2).
- **Response-letter anchors:** all 58 machine-checked before gate 3 by `review/check_response.py` (labels exist, keys are cited, macros are defined).

## Decision
**Major Revision.** `reject_recommended: false`. No dissents, so there is no deferral.
- **Step 1 (gates):** manifest complete. One adjustment (S8), typed, so no silent verdict change. Nothing pending.
- **Step 2 (base rule):**
  - B1, B2 and B3 do not fire: no must_fix item is NOT_ADDRESSED or MADE_WORSE, and no regression is major.
  - **B4 fires.** R2 and R13 are PARTIALLY_ADDRESSED with a must_fix residual. → **Major.**
- **Step 3 (floors):** no escalation exceptions, so the decision stays Major.

## Revision Response Checklist
| Class | Fully | Partly | Not |
|---|---|---|---|
| must_fix (3) | 0 | 3 | 0 |
| should_fix (13) | 3 | 9 | 1 |
| consider (12) | 5 | 7 | 0 |

should_fix addressed rate: 12/13 = 92%.

### must_fix
- **R2, citable case model (residual must_fix):**
  - The DOI is still a placeholder.
  - The PolicySwarm ODD appendix lacks the case's ε values and some parameters.
- **R5, related work (residual should_fix):** the section exists and every reference prints. But Fortunato 2005 is cited for "Euclidean is the usual default", whereas that paper itself compares confidence-range shapes; and several references sit in a list without a stated role.
- **R13, statistics (residual must_fix):**
  - The headline medians and equivalence counts still pool cosine and angular.
  - "One gate" and "one common ruler removes the difference" rest on maxima and medians, not on equivalence tests.

### should_fix
- **Fully addressed:** R10, NEW-1, NEW-2.
- **Not addressed:** S5 (persistent identifier).
- **Partly addressed:**
  - **R1:** "how most BC studies start" is uncited.
  - **R3:** secondary outcomes are shown only for run-matching, and the "recommended" design is not justified.
  - **R6:** audit item 4 has no new/standard tag.
  - **R11, S1:** the run-matched radial gap (computed, 1.48) is not reported, and "directional dispersion" is undefined.
  - **R12:** no flags on the four cases that are not equivalent on the evaluation seeds; no pilot-size guidance in the audit list.
  - **R14:** the sentence explaining the extreme cell is wrong by its own numbers. Cosine's lag-40 relative effect changes by about −0.081 against Euclidean's −0.025, so the change is not "modest".
  - **S2:** no policy-ABM literature on trust or credibility.
  - **NEW-3:** the method behind the Fig. 2 bands, the pass-rate window and the grid values are not stated.

### consider (decision-inert)
- **Fully addressed:** S8 (via adjustment ADJ-1), S9, S13, S16, S17.
- **Partly addressed:**
  - **S4:** no signed variance gaps.
  - **S10:** effects at lags 20 and 40 are not tabulated.
  - **S14:** trailing zeros are lost (1.1, 0.43) and iteration counts print as "13.0".
  - **S15:** item 1 says "affine shift" rather than "shift and rescale".
  - **C2, C4, C5.**

## New Issues (frozen at gate 2; all minor)
| # | Attribution | Issue |
|---|---|---|
| NEW-4 | regression | "Settled" uses an absolute 10⁻⁴ tolerance that is not rescaled with the cube, so Euclidean unsettled shares differ between paired unit and centred cells that are meant to be the same dynamics |
| NEW-5 | previously missed | §1 says the stopping time changed the size of differences; §5 says the gaps barely move with run length |
| NEW-6 | previously missed | "then the trust step" in the backward design does not match the two trust rows in Fig. 4 |
| NEW-7 | regression | the calibration error of the early-matched thresholds is not reported |
| NEW-8 | regression | the case intervals no longer say how they are computed (t-based for the interaction, bootstrap for indices) |
| NEW-9 | regression | "policy pull" means different moves in the glossary and in Appendix B; "corner" is reused for design cells |

The regressions are all minor, so they can only set a Minor floor; the decision is already Major.

## Response letter (gate 3)
- **56 claims verified accurate, 11 overstated** (round 2: about 25 overstated).
- **Every anchor resolves.** The remaining overstatements are claims of "Done" where gate 2 found a residual gap: R5, R6, R13, S1, S2, S4, S10, S14, S15.
- **Two further overstatements:**
  - "glossary terms used throughout" (NEW-9);
  - "a window that ends before most groups form", which the manuscript asserts without numbers.

## Decision Rationale
- **Round 3 closed most of what round 2 left open.** Every reference now prints. Per-cell intervals are reported, cosine and angular separately in the appendix. The case claims rest on the interaction, with an equivalence test. NEW-1 and NEW-2 are fixed, and the letter is far more accurate.
- **Major remains for two reasons:**
  - **R2:** the case model is still not citable, and only the author can supply the DOI.
  - **R13:** the paper's headline summaries still pool cosine and angular, and two "no difference" claims lack equivalence tests.
- **Two findings deserve attention beyond the grade:**
  - NEW-4 is a real measurement artefact in the settled share.
  - R14's sentence about the extreme cell is wrong as written.

## Residual Issues
- **Must fix:**
  - R2: DOI; the ε values and remaining parameters in the PolicySwarm ODD.
  - R13: report cosine and angular medians and counts separately in the text, or justify pooling them; add equivalence tests for the "one gate" and "common ruler" claims.
- **Should fix:**
  - **Text and literature:**
    - R1: cite or soften the "most BC studies" sentence.
    - R5: correct the role of Fortunato 2005 and tie the listed references to the argument.
    - R6: tag audit item 4.
    - S2: add trust and credibility literature.
  - **Reporting:**
    - R3: show secondary outcomes under every rule and justify the recommended design.
    - R11 and S1: report the radial gap and define dispersion.
    - R12: flag the four non-equivalent calibration cases.
    - NEW-3: state the band method, the pass-rate window and the grid.
  - **Corrections:** R14 (fix the sentence on the extreme cell); NEW-4 (a scale-free settled tolerance, then recompute); NEW-5 to NEW-9.

## Sprint contract status
The review did not run under a sprint contract. The three gates followed the withholding matrix by instruction to fenced subagents; nothing enforced it mechanically.

## Attachment: Acronym Check (advisory, #849)
Not checked: `check_acronyms.py` accepts Markdown or plain text, and the manuscript is LaTeX.
