# Verification Review Report, round 4 (2026-10-19)

*Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models.* Revised `6d39dc2` against round-3 `2152d2b`. Venue: JASSS (arXiv first).

Simulated review by an AI model; role-separated, not independent; NOT_CALIBRATED.

## Judge Record
- **Mode:** three-gate re-review, one fenced subagent per gate, run in sequence:
  1. criteria, written without seeing the revision;
  2. verdicts, written without seeing the response letter;
  3. claim matching, with the letter revealed.
- **Disclosure:** `[CONTRACT-ARTIFACTS-UNAVAILABLE: round 1 ran without the sprint contract; decision derived by hand, no checker replay]`.
- **Roadmap** (`round4/roadmap.json`): 24 items. It holds every round-3 item that was not fully addressed, at its round-3 residual class, plus round-3 NEW-4 to NEW-9.
  - C2 and C4 were dropped: the author declined them (no new experiments).
  - R2 and S5 (the DOI) are deferred by the author; they are still verified.
- **Inputs:** `round4/manifest.json`.
- **Routing:** card_mapped (EIC 5, R1 12, R2 1, R3 1).
- **Artifacts:** `phase1_criteria.json` (19 records), `phase2a_verdicts.json`, `phase2b_matrix.json`.
- **Judge family:** Claude, the same family that drafted and revised the paper. This verification round ran on the same model family that drove the revisions; over-optimization to this judge's latent biases is possible (Ren et al. 2026, arXiv:2607.13104 §8.1.2).
- **Response-letter anchors:** all 39 machine-checked before gate 3.

## Decision
**Major Revision.** `reject_recommended: false`.
- **Step 1 (gates):** no dissents, no adjustments, nothing pending.
- **Step 2 (base rule):** B1–B3 do not fire. **B4 fires**, because R2 and R13 are PARTIALLY_ADDRESSED with a must_fix residual. → **Major.**
- **Step 3 (floors):** none.

## Revision Response Checklist
| Class | Fully | Partly | Not |
|---|---|---|---|
| must_fix (2) | 0 | 2 | 0 |
| should_fix (17) | 7 | 9 | 1 (S5, DOI) |
| consider (5) | 2 | 2 | 1 |

should_fix addressed rate: 16/17 = 94%.

**Fully addressed this round:**
- should_fix: R1, R6, R11, R14, NEW-5, NEW-8, NEW-9;
- consider: S4, S14.

### must_fix
- **R2:**
  - The DOI is a placeholder (deferred by the author).
  - The PolicySwarm ODD appendix still lacks the case's ε and matched thresholds, the influence-weight function, the bias weights, whether trust is static, and the general perception formula with the trust target.
- **R13:**
  - The secondary outcomes have no per-cell CIs; only medians and counts are given.
  - The case equivalence margin is described as "fixed before this analysis", but it was set after the round-2 interval it now tests had been reported. That is a disclosure gap.
  - One pooled count remains: "32 of 36" calibration cases in §4.1.
  - "The start-matched version gives almost the same interaction (+0.032 against +0.034)" is a new no-difference claim without an equivalence test.

### should_fix, partly addressed
- **R3, NEW-7:** "a window that ends before most opinion groups have formed" (100 rounds) is asserted without support.
- **R5:** Schweighofer 2020 and Baumann 2021 still sit in a list. "These studies show that the shape of the confidence region matters" contradicts the Fortunato result in the preceding sentence, whose consensus thresholds were close to the one-dimensional ones.
- **R12:** only the 4 cells not equivalent on fresh seeds are flagged. Cells whose pilot error sits at the tolerance, or whose evaluation gap exceeds 0.005, are not.
- **S1:** the run-matched crossing table has no radial-spread row, and no reason is given.
- **S2:** no policy ABM that scales a signal by trust is cited. Gestefeld & Lorenz 2023 is accurately described.
- **NEW-3:** the response-curve experiment is described only in the Fig. 2 caption, not in §4.1.
- **NEW-4:** the settled-tolerance problem is disclosed but not quantified. The pooled unsettled shares in §5 still mix unit and centred runs, which the new sentence itself calls not comparable.
- **NEW-6:** the trust rows of Fig. 4 are named, but the text does not say what each isolates.

### consider
- **Partly addressed:** S10 (lag-20 effects), S15 (the clipping entry in the box).
- **Not addressed:** C5. The letter says "not pursued", while the roadmap records the author's will_address.

## New Issues (frozen at gate 2; all minor)
| # | Attribution | Issue |
|---|---|---|
| NEW-10 | regression | `tab:secondary` prints a median log₂ gap of −21.96 for shared-threshold directional dispersion (cosine): the log of a near-zero dispersion. Confirmed in `figures/table_secondary.tex`. |
| NEW-11 | indeterminate | The radial-spread and dispersion definitions do not say in which coordinates they are measured (they measure from the origin). The tables call the measure both "radial spread" and "radial var". |
| NEW-12 | regression | Caption slips. `tab:secondary` says "in brackets" but prints parentheses, and says "after 2,000 rounds" though convergence time runs to 4,000. The Fig. 2 caption states the grid twice. |

## Response letter (gate 3)
**27 checkable claims: 24 accurate, 3 overstated** (round 3: 11 overstated; round 2: about 25). The three overstatements:
- **R13:** "every headline summary … separately". §4.1 still pools 32 of 36.
- **R11:** "22 cells positive, 14 negative". These counts are in the letter, not the manuscript, and they pool both geometries.
- **R5:** "the paragraph says how they bear on this note". Huet has no tie, and the "shape matters" sentence contradicts Fortunato.

## Decision Rationale
- **Round 4 closed most of what round 3 left open:**
  - the extreme-cell error, the intro overstatement, terminology and interval methods;
  - the cosine/angular split, and equivalence tests for the "one gate" and "common ruler" claims.
- **Major remains for two reasons:**
  - **R2:** the DOI, which the author has deferred, and the case parameters still missing from the ODD appendix.
  - **R13:** secondary-outcome CIs, one pooled count, the timing of the case margin, and the new "almost the same" claim.
- **Every residual except the DOI is a writing or reporting fix:**
  - write the missing ODD parameters;
  - add CIs for the secondary outcomes (from existing results);
  - un-pool the last count;
  - disclose when the margin was set;
  - test or soften "almost the same";
  - fix the −21.96 artefact and the caption slips.
- **One decision for the author:** whether "before most opinion groups have formed" can be supported from saved checkpoints or should be softened.

## Residual Issues
- **Must fix:**
  - R2: DOI; the case parameters in the PolicySwarm ODD.
  - R13: secondary-outcome CIs; un-pool "32 of 36"; disclose the margin timing; equivalence test for, or softening of, "almost the same interaction".
- **Should fix:** R3/NEW-7, R5, R12, S1, S2, NEW-3, NEW-4, NEW-6, NEW-10 to NEW-12.

## Sprint contract status
The review did not run under a sprint contract. The three gates followed the withholding matrix by instruction to fenced subagents; nothing enforced it mechanically.

## Attachment: Acronym Check (advisory, #849)
Not checked: `check_acronyms.py` accepts Markdown or plain text, and the manuscript is LaTeX.
