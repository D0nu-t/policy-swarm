Simulated review by an AI model; role-separated, not independent of other seats; NOT_CALIBRATED.

# Peer Review Report — Peer Reviewer 1 (Methodology)
Identity: simulation-methods researcher (ABM experimental design, sensitivity analysis, calibration, paired CRN designs, statistical reporting). Recomputed claims from saved CSVs; no reruns.

## Recommendation: Major Revision. Confidence 4.

## Summary
Careful engineering: proper seed pairing, generated numbers, coordinate-invariance check; backward ablation a model of self-audit. But: cluster rule (0.1·ε in each metric's units) not invariant under the cosine↔angle transform (gaps up to 2^2.7 between "one gate"); the ≥1%-group count is defined but unreported and its median gap is larger under run-matching (0.66) than shared (0.42); non-convergence far more widespread than stated; run calibration misses its tolerance in several cells; the forward design does not show "size, not sign" (matching worsens unit-cube disagreement, centring removes most of it, the geometry×lag interaction changes sign across corners); trust mechanism rests on one switch with the key 2×2 cell missing. All fixable by re-analysis and modest extra runs.

## Strengths
- S1: Paired CRN design; equivalence check verified — max |Δ delta| between unit-0.5 and centred-1.0 Euclidean runs = 1.0e-16, identical pass rates.
- S2: Backward ablation closure stronger than stated: seed-level lag-40 deltas correlate r = 0.99 (Euclidean), 1.00 (cosine); control variances differ by exactly the predicted factor 4 (0.0197 vs 0.0788); bootstrap 95% CIs for index differences [−2, +5] (E) and [0, +1] (C). Report this paired check.
- S3: Reproducible pipeline (macros, saved thresholds, separate pilot seeds 1000–1009, published patch).
- S4: t0-matching-insufficient confirmed (median |pass gap| 0.16; centred d=4 15%: 0.62 vs 0.33).

## Weaknesses
### W1 (Major, conf 5): Cluster outcome not invariant to the monotone transform
Anchor: §4.3 "within 0.1ε of each other under the run's metric". d_cos ≈ θ²/2, so 0.1·ε_cos ≈ angle 0.32θ vs angular 0.1θ — cosine groups ~3× wider in angle even when gates admit identical pairs. Under t0 matching (pass rates within 0.006), mean log2 effective-group ratio cosine/angular: −2.66 (centred d=2 5%), −2.75 (unit d=2 5%), −0.4 (both d=2 15%); run-matched d=2 5%: ~12 vs ~81 effective groups. Euclidean-vs-angular group comparisons likewise lack common meaning.
Fix: one metric-independent group rule (Euclidean on final opinions, or coverage-matched radius), or a sweep (0.01, 0.05, 0.1, 0.2 of ε plus a fixed absolute radius); report cosine-vs-angular group gaps.

### W2 (Major, conf 5): A defined group outcome is unreported and contradicts the headline
Anchor: §4.3 "number of opinion groups holding at least 1% of agents". Recomputed median |log2 gap| (pooled cosine+angular): ≥1% group count — shared 0.42, t0 1.07, run 0.66 (run-matched up to 2.1, centred d=8 5%); directional dispersion — shared 3.56, t0 1.10, run 0.32. Effective count dominated by stragglers (d=2 5%: Euclidean median 146 effective groups vs 11 groups ≥1%), so it measures singletons and is horizon-sensitive.
Fix: report every §4.3 outcome (incl. dispersion, convergence time); pre-name the primary outcome; discuss why the two group measures disagree.

### W3 (Major, conf 5): Non-convergence at 2,000 rounds is widespread
Anchor: §4.4 "The exceptions all have the lowest reference coverage (5%) and low dimension". Share with converged_at == 2000: Euclidean unit d=4 5% 91%; centred d=4 5% 92%; centred d=2 15% 82%; unit d=2 15% 74%; cosine run-matched centred d=2 15% 92%; centred d=8 5% 87%; cosine t0 centred d=2 15% 100%. Fixed-horizon outcomes mix convergence speed with end state; pairing at equal horizon does not remove this.
Fix: report unconverged share per cell; horizon sensitivity (500/1,000/2,000/8,000) or run to convergence with cap; report convergence time; correct the "exceptions" sentence.

### W4 (Major, conf 5): Run calibration under-powered relative to tolerance; fails silently
Anchor: results/minimal_gaps.csv mode=run gap_pass_rate. 10-seed pilot mean with tol 0.005, but between-seed SD up to 0.148 (pilot SE ~0.047, ~10× tol); calibrate_run_average does not check monotonicity and returns the last midpoint silently at max_iter. Systematic misses: 17/18 centred gaps ≤ 0; largest −0.053 (centred d=2 30% cosine), −0.060 (centred d=8 15% angular), −0.036; gap still significant (p<0.05) in 67% of run-matched cells. "Falls to 0.01" is a median hiding unmatched cells.
Fix: ≥50 pilot seeds or stochastic root-finding (Robbins–Monro / fitted monotone curve); monotonicity check; report achieved calibration error per cell with CI, flag out-of-tolerance cells; protocol advice on pilot size vs between-seed SD.

### W5 (Major, conf 5): "Report sizes because everything is significant" applied without uncertainty or equivalence standard
Anchor: §4.4 "almost every gap differs significantly from zero, so we report sizes". Fig. 2 has no intervals; medians pool near-duplicate cosine and angular (double counting); "within 2^0.5" is post hoc; the claim is false under run-matching (67% of pass gaps and 72% of effective-group gaps significant). "Removes the gap"/"behave as one" are equivalence claims.
Fix: per-cell 95% CIs (paired bootstrap); pre-specified equivalence margins (e.g. |Δpass| < 0.01, |log2| < 0.25) with TOST; report cosine and angular separately or one only; correct the sentence.

### W6 (Major, conf 4): Forward factorial does not show "shared threshold changed the size, not the sign"
Anchor: Table 2. Centred: shared ≈ run-matched (gated E 160 vs C 138 shared / 143 run; anchor 189 vs 161 both). Unit: matching worsens disagreement (cosine 363 t0, 478 run vs E 160). Interaction changes sign across corners: +0.018 unit/shared/gated vs −0.057 [−0.071, −0.043] unit/run/gated; significant +0.034 in centred run-matched. Bootstrap lag-40 index CIs: unit/shared/gated E 160 [145,179], C 124 [120,128]; centred/run/gated E 160 [144,179], C 143 [133,154] — modest difference. In the original engine the large gap (134 vs 78) is mostly accounted for by the trust switch (→169 vs 117). Unit run-matched gated lag-0 cosine delta is small (−0.0021 ± 0.0002), so the 478 ratio is unstable.
Fix: restate in terms of the interaction (item 5); CIs on Fig. 3 and lag indices; explain the 478 blow-up; consider whether realised-coverage matching suffices in an uncentred space (caveat on item 3).

### W7 (Major, conf 4): Trust attribution rests on one intervention; key 2×2 cell missing; level-shift explanation not ruled out
Anchor: §5.3 "Making only this change in the original engine ... removes the reversal". Trust-centring run only in original and all-fixes configs (cosine 78 [73,82] → 117 [108,128]). The mechanistic story ("because the angular gate measured directions from the same corner") is an interaction claim needing corner-trust + centred-gate cell. The switch also shifts the mean perceived-policy level by ~0.5·(1−τ) toward the middle (trust ~ Beta(2,2)), which may act via how far agents are pulled toward the corner (small norms, ill-defined directions) rather than origin "meaning". Switch found post hoc by code comparison.
Fix: 2×2 (trust centre corner/neutral) × (gate centre corner/neutral), 100 seeds, CIs; a level-shift control with the same mean shift but unchanged shrinkage point; report share of agents near the corner / mean opinion norms; soften to "a single switch removes the reversal".

### W8 (Minor, conf 4): Variance gap called "genuine geometric" but variance is Cartesian
Anchor: §4.4 "This is a genuine geometric difference". Angular updates keep norm by construction, so variance gap near-definitional; directional dispersion under run-matching has median |log2 gap| 0.32 (cells −2.5 to +1.3), unreported.
Fix: report radial (variance of ‖x‖) and directional dispersion separately.

## Detailed comments
- Matching scheme gives matchings well below maximal; report mean matching size (sets the time scale).
- Clipping after norm-preserving angular steps changes the norm; report frequency.
- Euclidean unit and centred cells are exact rescalings (confirmed identical effective groups and pass rates), so 9 independent Euclidean cells, not 18; state this.
- Case calibration: control runs only, lag 20 only, cosine only, applied to all lags and treatment; report realised pass rates by lag and arm. Lag index acceptable since delta sign constant (all negative) but report CIs.
- Add sensitivity to μ, n and network type in a reduced design.
- Protocol: item 3 needs pilot-size and calibration-error advice; item 5 should be applied to the paper's own case.

## Questions
1. Was effective group count chosen before or after seeing the ≥1% results?
2. Did any calibrate_run_average call hit max_iter without meeting tolerance? Which cells?
3. Reversal with corner-shrinking trust and a centred gate?
4. Why 478 in unit run-matched gated — near-zero lag-0 effect or agents collapsing toward the corner?
5. Do conclusions survive a metric-independent cluster rule?
6. Why do draft indices (143/72) differ from the saved S=30 run (131/75)?

## Minor
- §4.4 "no smaller than under a shared bound": t0 group gap (0.78) is larger than shared (0.68); say so.
- §4.4 cosine/angular paragraph: report group-count difference too.
- Fig. 2: jitter and pooling hide cells; use a cell-labelled dot plot with CIs.
- Fig. 3: no error bars; Euclidean bars repeat by design — say so in caption.
- §5.2: note the ~0.01 pilot-to-main mismatch.
- Give MC standard error for coverage (~0.1 pp at 2×10^5 pairs).

## Criterion judgements (NOT_CALIBRATED)
Methodological rigor PARTLY_MEETS; Evidence sufficiency PARTLY_MEETS; Argument coherence PARTLY_MEETS; Writing MEETS; others NOT_ASSESSED. No reviewer-directed text in manuscript.
