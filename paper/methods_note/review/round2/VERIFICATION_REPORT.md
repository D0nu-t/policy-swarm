# Verification Review Report, round 2 (2026-10-16)

*Hidden Choices: How Thresholds, Origins and Tests Manufacture and Hide Effects in Bounded-Confidence Models.* Revised manuscript `09057cf` against original `ed82ab6`. Venue: JASSS (arXiv first).

Simulated review by an AI model; role-separated, not independent; NOT_CALIBRATED.

## Judge Record
- **Mode:** re-review, three-gate orchestration: criteria (revision-blind) → evidence (persuasion-blind) → claims (letter revealed). One fenced subagent per gate, run in sequence.
- **Disclosure:** `[CONTRACT-ARTIFACTS-UNAVAILABLE: round 1 ran without the sprint contract; decision derived by hand, no checker replay]`. There is no `revision-roadmap/1.0` core, author-adjudication sidecar or revision-evidence bundle; the roadmap was transcribed from `EDITORIAL_DECISION.md` (`round2/roadmap.json`), and the git diff `ed82ab6..09057cf` stands in for the patch chain. `scripts/check_re_review_synthesis.py` was not run.
- **Inputs:** `round2/manifest.json` (30 files, SHA-256).
- **Reviewer configuration:** frozen round-1 identities, taken from each report's Identity line. No field re-analysis.
- **Routing:** card_mapped. EIC 10 items, R1 14, R2 6, R3 3; consider items go to EIC.
- **Pre-committed criteria:** `round2/phase1_criteria.json` (33 records; sha256 `c54ce955…`). Evidence: `round2/phase2a_verdicts.json` (`19db4463…`). Matrix: `round2/phase2b_matrix.json`.
- **Judge family:** Claude (same family that drafted and revised the paper). Round-1 panel provenance: not available as a typed artifact; all axes unknown.
- **Cross-model:** not active. This verification round ran on the same model family that drove the revisions; over-optimization to this judge's latent biases is possible (Ren et al. 2026, arXiv:2607.13104 §8.1.2).

## Decision
**Major Revision.** `reject_recommended: false`.

Three dissents fell on must_fix items (R1, R5, R13). That tripped the adjudication bound, and with cross-model off they went to the author (gate G2a). The author approved the replacement criteria (`replacement_approved`, 2026-10-16), which closed the deferral. The derivation below shows the decision would be Major under either ruling.
- **Base B4 applies whatever the dissents decide:** R2, R5 and R13 are partly addressed, and the gap left in each is itself a must_fix.
- **If the original criteria are upheld:** R1, R5 and R13 become MADE_WORSE must_fix items, so B3 applies, giving Major again. B1 does not apply, because none of the driving findings was critical in round 1. B2 does not apply either: only 3 of 16 items would be in {NOT_ADDRESSED, MADE_WORSE}, below the 50% threshold.
- **No silent verdict changes (G1):** zero adjustments, and every final verdict equals its gate-2 verdict.

## Revision Response Checklist
| Class | Fully | Partly | Not | Made worse |
|---|---|---|---|---|
| must_fix (16) | 6 | 10 | 0 | 0 |
| should_fix (17) | 5 | 10 | 2 | 0 |
| consider (5) | 0 | 2 | 3 | — |

should_fix addressed rate: 15/17 = 88%, above the 80% bar.

### must_fix
- **Fully addressed:**
  - **R4, R7, R8:** interaction in every cell; Lorenz citation corrected; claims narrowed.
  - **R9 (blocking B3):** one common ruler.
  - **R15, R16:** trust 2×2 with level shift; trust-target sweep.
- **Partly addressed, gap is must_fix:**
  - **R2:** archive DOI is a placeholder; PolicySwarm has no documented specification beyond prose (only the minimal model has an ODD); the pre-audit commit reference was dropped.
  - **R5:** no related-work section; Fortunato 2005, Huet 2008, Kurahashi-Nakamura 2016 and Baumann 2021 are in `refs.bib` but never cited, so they won't print; flache2017 is still in `refs.bib`; the grimm2020 ODD citation was removed.
  - **R13:** per-cell intervals are referred to "result tables" that are not in the manuscript; cosine and angular are pooled; the TOST margins are not justified; new "no difference" claims in the case study rest on non-significance.
- **Partly addressed, gap is should_fix:**
  - **R1:** no survey and no explicit "pre-emptive guideline" statement; a new uncited prevalence claim says these choices "rarely reach a methods section".
  - **R3 (blocking B1):** estimand framing done; the outcome-independent calibration the criterion asked for is missing. The curves use the realised pass rate, which is itself endogenous.
  - **R6:** the audit list doesn't say which items are new and which restate existing practice.
  - **R10:** unsettled shares only pooled for Euclidean; no per-cell shares; no convergence time.
  - **R11:** convergence time and effective groups not reported; "statistics fixed before the runs were analysed" sits uneasily with a primary outcome that changed after round 1.
  - **R12:** no CIs on the calibration error, no max_iter, no pilot-size guidance.
  - **R14:** the comparison that isolates the threshold from centring is only implicit in Fig. 4.

### should_fix
- **Fully addressed:** S3, S6, S7, S11, S12.
- **Not addressed:**
  - **S2:** no policy-ABM, trust or validation literature.
  - **S5:** no persistent identifier in the manuscript.
- **Partly addressed, gap is should_fix:**
  - **S1:** "geometry" still undefined; the crossing uses thresholds matched at the start but is read as explaining what remains after matching over the run.
- **Partly addressed, gap is consider:**
  - **S4:** signed gaps absent.
  - **S8:** "we" and manifold/angular naming not reconciled.
  - **S9:** no CIs in Tables 2–3.
  - **S10:** absolute effects not tabulated.
  - **S13:** the Proposition's consequence clause is imprecise for Euclidean distance.
  - **S14:** ε not given to 3 s.f.
  - **S15:** no box of origin-dependent operations.
  - **S16:** case calibration scope and cost not stated.
  - **S17:** sign of the shock effect, and whether bias should shrink with trust, not stated.

### consider (decision-inert)
- **C1, C3, C5:** not addressed. C1 and C3 were declined by the author; C5 was meant to be addressed, but no cost note exists.
- **C2, C4:** partly addressed. The horizon stops at 4,000 rounds, with 13% of Euclidean runs still unsettled.

## Dissents (adjudicated by the author: replacement_approved)
DIS-1 (R1), DIS-2 (R5), DIS-3 (R13), all `criterion_ambiguous`. In each case the committed criteria for "partly addressed" and "made worse" both hold, and the protocol gives no rule for which wins. The verifier applied "partly addressed", and the author approved that reading on 2026-10-16, so the gate-2 verdicts stand with no adjustment. Upholding the original criteria would have made each MADE_WORSE; the decision would have been Major either way.

## New Issues (frozen at gate 2)
| # | Severity | Attribution | Issue |
|---|---|---|---|
| NEW-1 | major | previously missed (cannot move the decision) | "Relative shock effect" is never defined, and the interaction is not reconciled with the lag index (own-opinion target: index 134 vs 150 yet interaction +0.001) |
| NEW-2 | minor | regression | Fig. 4 row labels (split=30/40) and the caption's 1/0 coding cannot be mapped consistently onto the text's "draft" and "all fixes" values |
| NEW-3 | minor | regression | The response-curve experiment, offered in the abstract as the answer, is undocumented (grid, seeds) and has no uncertainty bands |

## Response letter: overstatements (gate 3)
`RESPONSE.md` claims more than the manuscript shows in about 25 places. Every pointer was followed and none located missed evidence, so there are 0 adjustments. The most consequential:
- **R2:** "archived with a DOI and described in an ODD-style summary". The DOI is a placeholder, and the ODD covers the minimal model only.
- **R5 / Summary of Changes:** lists Fortunato, Huet, Kurahashi-Nakamura and Baumann as added references; none is cited.
- **R3, R10, R11, R12:** marked "Completed" with the requested elements missing. R11's "effective groups and radial spread reported" is not true of the text.
- **R13:** says CIs are reported throughout and cosine and angular separately; they are pooled, and the per-cell tables are not in the manuscript.
- **R14:** says the "size" claim was withdrawn; a size/sign split survives in §1.
- **R6, S1, S2, S3–S5, S8–S10, S14–S17, C2, C3, C5:** claimed elements absent, or the wording claims more than the text shows. S3: the title names three choices, not five.
The full list is in `phase2b_matrix.json` → `letter_overstatements`.

## Decision Rationale
- **What the revision achieved:** the three round-1 blockers that were about the science are resolved or substantially resolved. The interaction is now reported in every cell (B2). Matching is reframed as a choice of estimand (B1, apart from the calibration). The common ruler is in place (B3). The new trust experiments directly answer R15 and R16.
- **Why it is still Major:**
  - **Citable model (R2):** not achieved; the DOI and a documented specification are missing.
  - **Literature positioning (R5):** missing; the added references never print.
  - **Statistical reporting (R13):** the CIs, separate cosine/angular results and equivalence testing that the "no difference" claims depend on are not in the manuscript.
  - **Response letter:** it overstates the changes widely, which a real editor would treat as a credibility problem in its own right.
- **Size of the remaining work:** mostly writing and tables, not new simulations. The exception is an outcome-independent calibration (R3), plus optional runs for R10 and C4.

## Residual Issues
- **Must fix:**
  - R2: DOI, a specification of the case model, the pre-audit commit reference.
  - R5: a related-work section; cite or drop the added references; flache2017; grimm2020.
  - R13: per-cell CI tables, cosine and angular separately, justified margins, equivalence tests for the "no difference" claims.
- **Should fix:** R1, R3, R6, R10–R12, R14, S1, S2, S5; NEW-1 (define the relative shock effect; reconcile the interaction with the index).
- **Response letter:** rewrite RESPONSE.md so that each claim matches the manuscript.

## Sprint contract status
Not run under a sprint contract (round 1 used the standard synthesis protocol). The three gates followed the withholding matrix of `re_review_mode_protocol.md` by instruction to fenced subagents. This was not mechanically enforced.

## Attachment: Acronym Check (advisory, #849)
Not checked: `check_acronyms.py` accepts Markdown or plain text only, and the manuscript is LaTeX.
