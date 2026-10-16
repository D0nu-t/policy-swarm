# Revision plan after round-2 re-review (2026-10-16)

Source: `VERIFICATION_REPORT.md` (Major Revision) and `phase2b_matrix.json`. Goal: every remaining must_fix fully addressed, should_fix items closed or declined with stated reasons, and a response letter whose every claim points to text in the manuscript.

**Ground rule for this round:** nothing goes in the response letter unless it can be found in the manuscript. The letter is written last, and a script checks that each section, table and figure it cites exists and that each cited key prints.

## Work packages

### A. Make the case model citable (R2, S5): must_fix
1. **You:** create the Zenodo DOI (GitHub release `v1.2.0` → Zenodo). Then I put it in `\ArchiveDOI`, `refs.bib`, `CITATION.cff` and the README.
2. A short ODD appendix for the parts of PolicySwarm the case uses: agents and state, network, the order of steps in a tick, peer gate and step, media, shocks, policy pull and trust perception, the lag/shock experiment, and the outcome. About one page.
3. Restore the pre-audit commit reference (`50a42e5`) in the disclosure.

### B. Position the paper (R5, R1, R6, S2): must_fix
1. A related-work section (about 0.75 pages):
   - multidimensional BC and metric choice: Lorenz 2007/2008, Schweighofer 2020, Li 2026, Fortunato 2005, Huet 2008, Kurahashi-Nakamura 2016, Baumann 2021;
   - model docking and replication: Axtell 1996, Wilensky & Rand 2007;
   - concentration of distances: Aggarwal 2001;
   - policy-ABM validation and trust (S2): two or three references, **checked by web search before citing**.
   Every key in `refs.bib` is either cited or removed; drop flache2017; restore grimm2020 for ODD.
2. R1: say plainly that the note is a pre-emptive audit list, not evidence of how common the problem is; remove or support "rarely reach a methods section".
3. R6: mark which audit-list items are new (coverage over the run, the ruler, the origin audit) and which restate existing advice (interaction tests: Gelman & Stern; equivalence tests: Lakens).

### C. Statistics reporting (R13, R11, R12, R10, S4, S9, S10, S14): must_fix
All from existing results; no new runs.
1. Appendix table: per-cell gaps to Euclidean with 95% CIs and the TOST result, **cosine and angular separately**, for the pass rate and the primary outcome under all three threshold rules, with signed gaps (S4).
2. Justify the margins in one sentence each: ±0.02 is a share of conversations; ±0.25 log₂ is about a 19% ratio. Also add a sensitivity line: how the counts of equivalent cases change at ±0.15 and ±0.35.
3. Case "no difference" claims (own-opinion target, the null cells): replace "indistinguishable from zero" with an equivalence test on the interaction, against a margin fixed before looking (proposed: ±0.01, about a third of the recommended design's effect), or reword as "not significantly different".
4. R11: report convergence time (`converged_at`) and effective groups (as a secondary outcome, with why it is not primary); state honestly that the primary outcome was chosen after round 1.
5. R12: CIs on the calibration error (bootstrap over pilot seeds), the bisection's max_iter, and a line on pilot size.
6. R10: unsettled share per cell and metric in an appendix table; define "settled".
7. S9, S10: CIs on every index in Tables 2–3; absolute lag-0 and lag-40 effects as columns.
8. S14: ε to 3 significant figures.

### D. Fix what the revision introduced (NEW-1, NEW-2, NEW-3, S1, S13, S17)
1. **NEW-1 (major):**
   - Define the relative shock effect (shock effect divided by the control run's variance) and the lag index (mean effect at lag 40 over the mean at lag 0).
   - Then explain the own-opinion case, where the indices differ (134 vs 150) but the interaction is null: the index is a ratio of means, while the interaction is a per-seed contrast of relative effects. **I check this numerically first.** If the two measures genuinely disagree, the paper says which one carries the claim and why.
2. **NEW-2:** relabel Fig. 4's rows in words ("draft engine", "+ cosine fix", "+ all fixes", "+ trust at centre") so they map onto the text, and check every value the text quotes against the plotted dot.
3. **NEW-3:** a design paragraph for the response curves (grid of 10 coverages, 50 seeds, 2,000 rounds, seed offset), with bootstrap bands in Fig. 2.
4. **S1:** define "geometry" (gate + update rule) where it is first used. Either rerun the crossing with thresholds matched over the run, or restate it as explaining the gap at matched-at-start thresholds. **Decision for you (see below).**
5. **S13:** fix the Proposition's consequence clause for Euclidean distance (only d_E/√d has a limit).
6. **S17:** state the sign of the shock effect, and say that trust scales the bias too, and that this is the model's assumption.

### E. Remaining should-fix and consider items
- **R3:** an outcome-independent calibration. **Decision for you (see below).**
- **R14:** one paragraph naming the centred rows of Fig. 4 as the comparison that holds centring fixed and varies the threshold.
- **S8:** "I" vs "we"; one sentence on the code's "manifold" being the paper's "angular".
- **S15:** a box listing origin-dependent operations: angular gates, multiplicative shrinkage, decay, clipping, zero initialisation, ratio outcomes.
- **S16:** scope, pilot count and cost of the case calibration.
- **C5:** two sentences on what the audit list costs to apply.
- **C4:** optional 8,000-round runs (see below).
- **C1–C3:** stay declined; Limitations adds μ, n and asymmetric bounds.

### F. Response letter, rebuilt (last)
- Rewrite `RESPONSE.md` from the round-2 matrix: one row per item, each with a manuscript anchor (section, table or figure label), and items not done marked "Declined" or "Partly" with a reason.
- A check script verifies:
  - every `\ref` and `\cite` the letter names exists and prints;
  - every number it quotes appears in `numbers.tex` or a table.
- Section "Changes since round 2" lists the overstatements found and how each was corrected.

## Decisions needed from you
1. **R3, outcome-independent calibration:** (a) new runs that match ε on the pass rate over an early window (the first 100 rounds), reported as a third matched point; about 1–1.5 h of compute; (b) decline, with the argument that any dynamic matching uses an endogenous rate, and say so as a limitation.
2. **S1, crossing:** (a) rerun with thresholds matched over the run, about 25 min; (b) restate the claim at matched-at-start thresholds only.
3. **C4, horizon:** (a) run 8,000 rounds for the factorial's Euclidean and t0 cells, about 2 h; (b) keep 4,000 and state the 13% unsettled share as a limitation.
4. **Zenodo:** you create the DOI before I finish package A.
5. **Round 3:** after this round, run another re-review (same three-gate procedure), or stop and read the paper yourself first.

## Order and effort
| Step | Packages | Compute | Rough time |
|---|---|---|---|
| 1 | D1 numerical check (decides NEW-1's wording) | none | 15 min |
| 2 | Runs you choose in decisions 1–3, in the background | 0–4 h | |
| 3 | C, D2–D6, E (tables, text, figures) | existing results | 2–3 h |
| 4 | B (related work; web-check new references) | none | 1 h |
| 5 | A (after your DOI) | none | 45 min |
| 6 | Rebuild figures and numbers; ruff; tests; LaTeX static checks | | 20 min |
| 7 | F (response letter + check script) | | 45 min |
| 8 | Optional round-3 re-review | | 30–40 min |

Out of scope: HK variant, clustered starts, L1/L∞ (declined); building the PDF (needs your LaTeX install).
