# Editorial Decision Package — methods note (round 1, 2026-10-16)

**Decision: Major Revision.** `calibration_status: NOT_CALIBRATED`.

**Provenance.** academic-paper-reviewer v1.11.1 (academic-research-skills plugin), full mode, standard synthesis protocol (no sprint contract, no scripts, no cross-model check). Five reviewer seats (Journal-Fit/EIC, R1 methodology, R2 domain, R3 policy-modelling perspective, Devil's Advocate) and the synthesizer each ran as a fresh-context subagent that saw only the manuscript, its figures, tables, numbers, code and results — not the author's notes, wiki or conversation. All ran on the same model family (Claude), which also drafted the paper: role-separated, **not independent**; correlated errors likely. Venue: JASSS (author-stated), `criteria_binding_unavailable`. Individual reports: `EIC_journal_fit.md`, `R1_methodology.md`, `R2_domain.md`, `R3_perspective.md`, `DA_devils_advocate.md` in this folder.

## Recommendations
| EIC | R1 | R2 | R3 |
|---|---|---|---|
| Major (conf 4) | Major (conf 4) | Major (conf 4) | Major (conf 4) |

## Consensus
- **CONSENSUS-3 (SC-4):** a residual geometry effect survives every correction (centred, run-matched: interaction +0.034 [+0.027, +0.042], p≈6e-15; indices 189 vs 161). "Somewhat more", "never its sign" (l.228) and "Neither layer is a property of geometry" (l.249) understate it. (EIC W4, R1 W6, R3 W2; DA C1; R2 silent.)
- **CONSENSUS-3 (SC-18):** case lag indices and Fig. 3 need uncertainty intervals.
- **Corroborated (2/4):** prevalence premise unsupported (SC-1); run-matching outcome-coupled (SC-3); update-rule attribution undefined/untested (SC-5); thin literature (SC-6); novelty not positioned vs Lorenz 2008 volume matching and Li et al. (SC-8); evidence too narrow for general claims (SC-10); widespread non-convergence (SC-11); metric-specific cluster rule (SC-19); threshold not isolated as source of "size" (SC-23); ratio-index instability (SC-24); plus minor items.
- **Single-reviewer Major findings retained on their anchors:** Lorenz 2008 miscited (SC-9, R2); ≥1% group outcome unreported and worse under run-matching (SC-20, R1); calibration under-powered and silent on failure (SC-21, R1); no CIs/equivalence margins (SC-22, R1); trust attribution rests on one switch, 2×2 missing (SC-25, R1); "centre at neutral" is itself a substantive assumption (SC-32, R3).

## Disagreements (arbitrated)
- **SC-2, withdrawn-draft narrative.** EIC: recast §5 on a documented, archived model, cut draft history to a footnote. R3: the open account is exemplary; add policy stakes. **Resolution:** §5 must rest on a documented, citable model; keep a short disclosure (author's own, unreleased, caught before external use) plus 2–3 sentences on the averted policy reading.
- **SC-30, generalising the origin audit** (R3 Major, R2 Minor). **Resolution:** should-fix, section cost; R3's Major rating recorded as dissent.

## Devil's Advocate CRITICALs
- **C1 — VALIDATED.** By the paper's own item-5 interaction test, the cosine-minus-Euclidean interaction has the same sign everywhere (+0.026 to +0.037 across all 8 pre-audit fix combinations; +0.018 audited shared unit; +0.034 centred run-matched). The "threshold = size, origin = sign" decomposition does not hold; the withdrawn claim may be "attenuates" rather than "reverses". Corroborated by EIC W4, R1 W6, R3 W2. Required: report the interaction across all backward/forward cells; revise l.228/234/249; state the residual effect in abstract and §5.3.
- **C2 — VALIDATED (as a Major estimand/presentation defect, not fatal).** Matching on the realised pass rate largely fixes the group outcome by construction (DA: Spearman ρ = −0.993; R2's analytic argument; EIC's estimand framing) and removes a genuine mediating pathway. Required: present run-matching as one estimand alongside t=0; report both; add an outcome-independent calibration (transient/early window); drop "removes the gap".

## Blocking issues
| | Issue | Sources | Resolving item |
|---|---|---|---|
| B1 | Run-matching "removal" is outcome-coupled; estimand undefended | EIC W3, R2 W3, DA C2 | R3 |
| B2 | Residual geometry effect understated; l.249 contradicted by own interaction column | EIC W4, R1 W6, R3 W2, DA C1 | R4 |
| B3 | Group-structure outcome not comparable across metrics | R1 W1, R2 W4, DA M2 | R9 |

## Revision roadmap (source order, not priority)
### Required (must fix)
| Ref | Item | Cost |
|---|---|---|
| R1 | Survey published multidimensional-BC metric comparisons (how ε set, coverage reported) or reframe as a pre-emptive guideline; drop "A common way" | section |
| R2 | Recast §5 on a documented, citable, archived model; short disclosure of the draft + policy stakes | section |
| R3 | Run-matching as an estimand; report t=0 and run-matched side by side; add one outcome-independent calibration; state mechanically tied outcomes; remove "removes the gap" | new_data |
| R4 | Report the interaction across all backward/forward cells; quantify the residual effect in abstract and §5.3; revise l.228, 234, 249 | re_analysis |
| R5 | Related-work section (R2's verified references first; model alignment/docking; BC surveys); cite or drop flache2017 | section |
| R6 | Position as static volume matching (Lorenz) → distribution coverage → dynamic matching; say which protocol items are new | section |
| R7 | Correct the Lorenz 2008 citation (l.38) | sentence |
| R8 | Narrow "for any study…" claims to the tested design, or extend (Consider C2) | section |
| R9 | Re-cluster final states with one metric-independent rule or a radius sweep; report cosine-vs-angular group gaps | re_analysis |
| R10 | Report unconverged share per cell; correct the "exceptions" sentence (l.161); report convergence time | re_analysis |
| R11 | Report all §4.3 outcomes (≥1% groups, directional dispersion, convergence time); name the primary outcome | re_analysis |
| R12 | Report achieved calibration error per cell with CIs; flag out-of-tolerance cells; max_iter/monotonicity check; pilot-size guidance | re_analysis |
| R13 | Per-cell paired bootstrap CIs; pre-stated equivalence margins (TOST) for "removes"/"behave as one"; report cosine and angular separately | re_analysis |
| R14 | Show which comparison isolates threshold from centring, or restate the "size" claim; explain the 478 cell | section |
| R15 | 2×2 (trust centre × gate centre) + level-shift control, or soften l.242 to "a single switch removes the reversal" | new_data (or sentence) |
| R16 | Treat the shrinkage target as an explicit assumption/parameter; rerun the case under ≥1 alternative target (status quo, own opinion) | new_data |

### Suggested (should fix)
S1 define "geometry" (gate vs gate + update rule), radial vs directional dispersion, ideally gate × update crossing · S2 policy-ABM / trust / validation literature · S3 retitle to name both mechanisms · S4 "median absolute gap" with signs · S5 archive with a persistent ID · S6 merge/rank protocol items 2–3, soften "never share" · S7 cite or relabel "conventional bound" · S8 housekeeping (refs.bib private comment, draft date, "we", Li et al. entry, manifold/angular) · S9 CIs on lag indices and Fig. 3 · S10 absolute shock effects alongside the ratio index · S11 9 independent Euclidean cells, not 18 · S12 clipping frequency after angular steps · S13 concentration limits as a proposition · S14 cosine/angular identity as a lemma; ε to 3 s.f. · S15 item 1 as an origin/affine-equivariance audit with a box of origin-dependent operations (R3 dissent: Major) · S16 calibration scope, pilot count, cost · S17 interaction sign convention; is bias shrinkage intended?

### Consider
C1 L1/L∞ comparison under volume vs coverage matching · C2 HK variant, clustered starts, runs to convergence, sensitivity to μ, n, network · C3 coverage for HK and asymmetric bounds · C4 horizon sensitivity (500–8,000 rounds) · C5 short discussion: protocol cost; which published results to revisit.
