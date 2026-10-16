# Round-2 re-review plan (2026-10-16)

Skill: `academic-paper-reviewer` v1.11.1, mode `re-review`. Venue frozen: JASSS (arXiv first), `criteria_binding_unavailable`.

## Decisions (author, 2026-10-16)
- **Protocol:** three-gate orchestration (criteria → evidence → letter), run without the formal contract artifacts. Round 1 used the standard synthesis protocol, so there is no `revision-roadmap/1.0` core, `revision-evidence-bundle/1.0` or patch/apply-report chain; these are not reconstructed after the fact. The git diff `ed82ab6..09057cf` is the change record. The decision rules (Steps 1–3 of the protocol) are applied by hand, and `scripts/check_re_review_synthesis.py` is **not** run. The report carries the disclosure `[CONTRACT-ARTIFACTS-UNAVAILABLE: round 1 ran without the sprint contract; decision derived by hand, no checker replay]`.
- **Judge:** single model family (Claude), with the protocol's verbatim correlated-judge disclosure. No cross-model pass.
- **Author triage:** taken from `review/RESPONSE.md`. R1, S2, C4 = will address (partly done); C1, C2, C3 = won't address (out of scope for a short note; named in Limitations); all other items = will address.

## Inputs
| # | Input | Source |
|---|---|---|
| 1 | Round-1 roadmap (R1–R16, S1–S17, C1–C5) | `review/EDITORIAL_DECISION.md`, converted to per-item records |
| 2 | Author triage | as above |
| 3 | Original manuscript | `git show ed82ab6:paper/methods_note/{main.tex,numbers.tex,refs.bib}` + its figures/tables |
| 4 | Revised manuscript | `09057cf`: same files |
| 5 | Change record | `git diff ed82ab6 09057cf -- paper/methods_note/` |
| 6 | Response to reviewers | `review/RESPONSE.md` (withheld until gate 3) |
| 7 | Round-1 decision letter | `review/EDITORIAL_DECISION.md` |
| 8 | Round-1 findings and frozen identities | `review/{EIC_journal_fit,R1_methodology,R2_domain,R3_perspective,DA_devils_advocate}.md` |
| 9 | Input list with SHA-256 of each file | `round2/manifest.json`, written before gate 1 |

## Gates
| Gate | Sees | Does not see | Output |
|---|---|---|---|
| 1. Criteria | roadmap, round-1 reports, decision letter, identities | either manuscript version, diff, response letter | `round2/phase1_criteria.json`, ends `[CONTRACT-ACKNOWLEDGED]` |
| 2. Evidence | + original and revised manuscript, diff | response letter | `round2/phase2a_verdicts.json` + new-issue records, ends `[EVIDENCE-COMMITTED]`; no retry |
| 3. Claims | + response letter | — | `round2/phase2b_matrix.json`; every verdict change carries a typed adjustment record |

- Each must_fix/should_fix item is judged under the persona of the seat that raised it (first non-DA label; consider items → Journal-Fit Reviewer). The DA is never a verifier.
- New issues are frozen at gate 2 and attributed as `regression` (introduced by the revision; can move the decision) or `previously_missed` (reported only).
- One fenced subagent per gate, run in sequence; each gate's output is checked against its schema in `shared/contracts/re_review/` before the next gate starts.

## Decision
Steps 1–3 of `references/re_review_mode_protocol.md` § Decision Derivation, applied by hand and shown in full. Possible outcomes: Accept, Minor Revision, Major Revision, or `user_review_required`.

## Outputs (`review/round2/`)
- `VERIFICATION_REPORT.md`: judge record, decision, item-by-item matrix, new issues, rationale, residual issues, disclosures, acronym-check attachment (`scripts/check_acronyms.py`).
- On Major: a round-2 roadmap. On Minor/Major: optional Socratic revision coaching.

Read-only: no reviewer edits `main.tex` or any other manuscript file.
