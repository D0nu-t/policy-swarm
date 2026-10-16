Simulated review by an AI model; role-separated, not independent of other seats; NOT_CALIBRATED.

# Peer Review Report — Peer Reviewer 2 (Domain)
Identity: bounded-confidence theorist (multidimensional Deffuant and HK models, confidence-region geometry, opinion-dynamics surveys). No injection found; refs.bib has a comment pointing to private notes (remove).

## Recommendation: Major Revision. Confidence 4.

## Summary assessment
Practical message sound, useful and clearly written; coverage drift (t=0 matching insufficient) is, as far as the reviewer knows, not stated in the BC literature. Main domain problem is positioning: size-vs-shape separation is explicit in Lorenz (2008), which compares 1-norm and ∞-norm and rescales ε to equal d-dimensional confidence-region volumes; Li, Luo & Chu state the size/shape attribution. Paper must present itself as extending volume matching → coverage matching under the actual opinion distribution → dynamic (realised) matching. Two further issues: realised-pass-rate matching is close to circular for cluster outcomes; group counts use a metric-specific radius, reintroducing the confound. Reference list (7) too thin.

## Strengths
- S1: Coverage drift is real and under-appreciated; no BC paper distinguishes static vs dynamic matching (Lorenz's volume matching is static). §4.4.
- S2: Correct handling of origin dependence and centring (§2), generalised to multiplicative steps.
- S3: Unit statements correct and checkable (60°, 28.6°, centred cosine ε=1 → half by x→−x symmetry; Euclidean unit 0.5 = centred 1.0 by scaling); Table 1 consistent with concentration limits (unit cube cos→3/4, d_cos→0.25, angle→0.72 rad).
- S4: Case study rules out alternatives in both directions (§5.2).

## Weaknesses
### W1 (Major, conf 5): Size-vs-shape confound already explicit in Lorenz (2008), which is miscited
Anchor: §1 "Euclidean distance is the default for multidimensional BC models \citep{lorenz2008}". Lorenz 2008 restricts to 1-norm and ∞-norm unit balls and, §4: "scale ε to that magnitude that the d-dimensional volumes of the areas of confidence would be equal" — a size-matched comparison of shape. Verified at https://arxiv.org/abs/0708.3172. Li/Luo/Chu (§3.3, §5.1.1) also attribute results to area and shape.
Fix: correct the citation; reposition as (1) Lorenz matched Lebesgue volume; (2) coverage under the actual opinion distribution differs — boundary effects in the cube, and for angular gates the only option (cone volume infinite/ill-defined); (3) coverage drifts, so any static matching is insufficient. Add a cheap L1/L∞ comparison with both volume and coverage matching.

### W2 (Major, conf 4): Literature too thin; "common practice" premise unsupported
Anchor: absence in §1 and refs.bib. Claims metric comparison is increasing and shared ε "a common way" with no published instance; only the authors' unpublished draft. Missing: Fortunato et al. 2005; Lorenz allocation work and 2007 survey; Huet, Deffuant & Jäger 2008; heterogeneous bounds (Lorenz 2010); topic spaces (Baumann et al. 2021); distance concentration (Aggarwal et al. 2001).
Fix: cite 2–3 published shared-ε comparisons or reframe as a pre-emptive guideline; add references below.

### W3 (Major, conf 4): Run-averaged pass-rate matching is close to circular for group structure
Anchor: §4.4 "the median pass-rate gap falls to ..., and the group structure follows". After clusters form, every matched pair is within a cluster (passes) or between clusters >ε apart (fails), so long-run pass rate ≈ fraction of edges whose endpoints share a final cluster — a function of group number and sizes. Matching it partly fixes cluster structure by construction; "83% within 2^0.5" partly mechanical.
Fix: discuss formally (steady-state pass rate as function of cluster shares on ER); calibrate on a transient window (first 50–100 rounds) as alternative; report outcomes not tied to the pass rate (convergence time, cluster positions, variance); soften protocol item 3 to report both static and dynamic matches and say which outcomes are mechanically tied to the target.

### W4 (Major, conf 4): Group counts use a metric-specific clustering radius — the confound criticised
Anchor: §4.3 "within 0.1ε of each other under the run's metric". Detector resolution differs between metrics and threshold rules; under angular metrics same-direction/different-magnitude agents count as one group, exactly what magnitude-preserving updates produce. Effective group counts not comparable across metrics.
Fix: cluster all final states with one common metric-independent rule (Euclidean in centred space with fixed radius, or density-based); report alongside current definition.

### W5 (Minor, conf 5): Dimension statement imprecise — angles also concentrate
Anchor: §3 "because distances grow with dimension while angles do not". In the centred cube angles concentrate at 90° (angular coverage 32→17→7→1%); unit cube cos θ→3/4. The 50% centred cosine is a symmetry special case at ε=1.
Fix: give concentration limits (Euclidean ≈√(d/6) in [0,1]^d, ≈√(2d/3) in [−1,1]^d; unit d_cos→1/4; centred angles→π/2 with O(1/√d) fluctuations); state as a short proposition (coverage → 0 or 1 by side of limit); cite distance-concentration literature.

### W6 (Minor, conf 5): "Cosine and angular gates are one gate" is a definition, not a finding; family incomplete
Anchor: §4.4. It is an identity derived in §2; Euclidean between normalised vectors is also in the family (‖u_i−u_j‖² = 2 d_cos). Matched values inconsistent at 2 d.p.: cosine 0.07 → arccos(0.93) ≈ 0.376 vs reported angular 0.36 (rounding).
Fix: state once as a lemma; use simulation only for chordal vs geodesic update difference; add normalised-Euclidean member; report matched ε to 3 s.f.

### W7 (Minor, conf 4): "Conventional bound" 0.5 in d dimensions
Anchor: Fig. 1 caption. Critical ~0.5 is 1D on [0,1]; in d dims the cube diameter is √d. Fix: cite or describe as the case-study draft's value.

### W8 (Minor, conf 4): Origin dependence is a general coordinate-equivariance point
Anchor: §6 item 1. Fix: reword item 1 as an affine-equivariance audit (angular gates, multiplicative trust, decay), with centring as one remedy — it is the diagnostic actually used.

### W9 (Minor, conf 3): Relate coverage to heterogeneous/asymmetric bounds and HK
Anchor: §7. Fix: define coverage for HK (mean in-confidence degree) and asymmetric bounds (per direction).

## Missing references (verified unless noted)
1. Lorenz 2008 (already cited; content needs correcting) https://arxiv.org/abs/0708.3172
2. Lorenz, multidimensional allocation problems https://arxiv.org/abs/0708.2923 (venue unverified)
3. Lorenz 2007 survey, IJMPC 18(12) https://ideas.repec.org/a/wsi/ijmpcx/v18y2007i12ns0129183107011789.html
4. Fortunato, Latora, Pluchino, Rapisarda 2005, IJMPC 16(10):1535–1551 https://arxiv.org/abs/physics/0504017
5. Huet, Deffuant, Jäger 2008, ACS 11(4):529–549 https://doi.org/10.1142/S0219525908001799
6. Lorenz, Heterogeneous bounds of confidence https://arxiv.org/abs/0801.1399 (journal unverified)
7. Kurahashi-Nakamura, Mäs, Lorenz 2016, JASSS 19(4):7 https://www.jasss.org/19/4/7.html
8. Baumann, Lorenz-Spreen, Sokolov, Starnini 2021, PRX 11:011012 https://arxiv.org/abs/2007.00601
9. Aggarwal, Hinneburg, Keim 2001, ICDT LNCS 1973 https://doi.org/10.1007/3-540-44503-X_27
10. Kurz 2025, Equivalent bounded confidence processes, arXiv:2512.18016 (abstract only)
11. Zabarianska & Proskurnikov, general-norm multidimensional HK (unverified)
12. Schweighofer, Schweitzer & Garcia 2020 JASSS hyperpolarization (unverified). Also check whether Schweighofer et al. 2020 (Chaos) uses a hard angular gate — reviewer's unverified recollection is a smooth balance-theoretic weighting; qualify the citation if so.

## Minor
- Say plainly the draft is the authors' own and never released.
- Give the three update rules as displayed equations in §2.
- §4.1: clipping after a norm-preserving angular update breaks norm preservation — report how often; affects the variance-gap explanation.
- Fig. 2 caption: mark which marks are the 5% exception cells.
- refs.bib: remove private-notes comment; add DOIs/URLs to Deffuant 2000 and Lorenz 2008.

## Questions
1. Coverage-matched vs Lorenz volume-matched ε for L1/L∞ in [0,1]^d — where do they diverge; boundaries?
2. With transient-window calibration, do group differences reappear?
3. Do group results hold with a metric-independent clustering rule?
4. Any published study comparing metrics at a shared ε?
5. For HK, match mean in-confidence neighbours? Does it drift the same way?
