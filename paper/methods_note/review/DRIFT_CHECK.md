# Objective-drift check (2026-10-19, after round 5)

This compares what the paper set out to be, by the author's own choices, with what five review rounds have made it.

## What the author asked for
| Choice (date) | Source |
|---|---|
| A methods note, posted to arXiv and then submitted to JASSS (15 Oct) | planning answers |
| Framing: "how hidden choices manufacture and hide effects" (16 Oct) | revision choices |
| **Format: a short methods piece with narrowed claims** (16 Oct) | revision choices |
| Whole ε-response curves rather than one matched point; the case study on an archived PolicySwarm | revision choices |
| No new experiments, and the DOI left for later (19 Oct) | instructions |

## What held
- **Framing and structure.** The title, the five-choice spine and the audit list are intact. Each review round sharpened them rather than replacing them.
- **The claims got narrower, as asked.**
  - "Run-matching removes the gap" became an estimand choice.
  - "Reversal" became "attenuation".
  - "Attenuates everywhere" became conditional on the trust target.
  - "One gate" and "the common ruler" are now backed by equivalence tests.
- **The abstract matches the current numbers.**

## Where it drifted
1. **The short piece is no longer short.**

   | Commit | Body words | Appendix words | Appendix tables | Citations |
   |---|---|---|---|---|
   | ed82ab6 (v1) | 4,034 | 296 | 0 | 6 |
   | 09057cf (round 1 revision) | 4,655 | 325 | 2 | 12 |
   | 2152d2b (round 3) | 5,839 | 862 | 6 | 20 |
   | 9f81c43 (now) | 7,108 | 1,214 | 9 | 22 |

   - That is +76% in the body, 4× in the appendix, and 9 appendix tables. One older JASSS page gives "normally 5,000 to 8,000 words" ([source](https://jasss.soc.surrey.ac.uk/), dated listing; current guideline **unverified**). At about 8,300 words with the appendix, the paper is at or past that range and is no longer a short piece.
   - Most of the growth is reporting added to satisfy the reviewers (per-cell intervals, flags, margins, positioning sentences), not argument.
2. **The review loop now mostly fixes its own fixes.** New issues raised per round:

   | Round | New issues | Introduced by our revision | Already in the paper |
   |---|---|---|---|
   | 2 | 3 | 2 | 1 |
   | 3 | 6 | 4 | 2 |
   | 4 | 3 | 2 | 0 (1 undetermined) |
   | 5 | 4 | 3 | 0 (1 undetermined) |

   - **11 of 16 new issues were introduced by revisions.** All issues after round 2 are minor.
   - The response letters show the same pattern: each round partly corrects the previous letter.
   - This is the point at which more rounds add length and churn faster than they add correctness.
3. **The judge and the author are the same model family.** Every round, the review skill printed the warning that a revision loop judged by the model that drives it can converge on what that judge likes. The loop rewards completeness, flags and qualification. It does not measure what a JASSS reader needs: brevity, a clear thread, and readable results sections.
4. **No human has read the paper since round 1.**
   - The wiki still records that the author had not read the draft.
   - The one PDF build (17 Oct, 15:13) predates three revision rounds.
   - Five review rounds have run on a paper its author has not read.
   - This is the largest drift risk: the objective is the author's paper, not the simulated panel's.
5. **The remaining external steps have not moved:** the DOI, a PDF build of the current text, and arXiv endorsement. Only the author can take them.

## What did not drift (checked)
- **Numbers:** a double rebuild gives identical `numbers.tex`, and every macro, reference and citation resolves.
- **Defaults:** the golden tests show the engine is unchanged.
- **Corrections made along the way are real ones**, not judge-pleasing:
  - the order-dependent bootstrap (34 → 32 of 36);
  - the lag-index quantity;
  - the sign convention;
  - the noise-SD description;
  - five citation descriptions, checked against abstracts.

## Recommendation
1. **Stop the review loop.** With the DOI in place, round 5 says Minor Revision. Another round would mostly find the effects of the last one.
2. **The author reads the current PDF** (rebuild first) and decides what the paper is for.
3. **Then one cutting pass toward the chosen format:**
   - move the per-cell appendix tables to an online supplement or the released CSVs;
   - target about 5,500 body words, keeping the five choices, Figs 1–4 and the audit list;
   - check JASSS's current length rule on its site before cutting.
4. **Create the DOI**, then post to arXiv. JASSS reviewers, not this panel, are the review that counts.
