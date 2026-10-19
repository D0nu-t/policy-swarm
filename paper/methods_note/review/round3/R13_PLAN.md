# Plan: close R13 (2026-10-17)

R13 residual (round 3): the headline medians and equivalence counts pool cosine and angular, and the "one gate" and "one common ruler removes the difference" claims rest on maxima and medians, not equivalence tests.

**Author's choices:**
- Report cosine and angular side by side everywhere in the main text.
- Scope: R13 only. R14, NEW-4 and the other round-3 residuals get their own plan.

No new runs: the per-geometry gaps and the cosine-vs-angular equivalence tests already exist in `results/minimal_gaps_v2.csv` and `results/cos_vs_angular_v2.csv`.

## Steps
1. **Macros** (`make_figures.py`):
   - For every headline summary (the pass rate and the primary outcome under the shared, start-, run- and early-matched rules; the secondary run-matched outcomes: variance, directional spread, effective groups, convergence time), give the median absolute gap and the equivalent count out of 18, separately for cosine and angular. Example: `\VRunGroupEquivCos`, `\VRunGroupEquivAng`.
   - Cosine vs angular, start-matched: equivalence counts for the pass rate, the common ruler and each geometry's own ruler.
   - Pooled "of 36" macros stay only where an appendix table needs them.
2. **Appendix table** `table_cos_ang.tex`: per cell (18 rows), start-matched cosine-vs-angular gaps with 95% CIs and equivalence marks, for the pass rate, groups under the common ruler, and groups under the own ruler (0.1ε).
3. **`main.tex`:**
   - Abstract: run-matched pass rates and group counts given for cosine and angular out of 18 each. "One common ruler removes the difference" gets its count (18 of 18, against 10 of 18 with each geometry's own ruler).
   - §4 Design: one sentence on why cosine and angular are reported separately. The lemma makes them one gate only when start-matched; their run- and early-matched thresholds are calibrated separately.
   - §4 Results: each "x of 36" becomes "cosine a of 18, angular b of 18".
   - §4 "one gate" paragraph: leads with the equivalence counts (pass rate and groups 18 of 18); the maximum and median stay as description.
   - §5 ruler paragraph: equivalence counts for the own ruler vs the common ruler.
4. **Checks:**
   - Rebuild twice, with identical `numbers.tex`.
   - The macro check in `make_figures.py`, plus the static LaTeX checks.
   - ruff and pytest.
5. **Round-4 response entry for R13,** with every anchor checked by `review/check_response.py`.

The paper stays at Major Revision until R2 (the Zenodo DOI) is done.
