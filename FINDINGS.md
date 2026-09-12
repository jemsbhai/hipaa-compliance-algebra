# FINDINGS.md — IEEE HealthCom 2026

**Paper:** Privacy-Preserving Confidence-Aware FHIR R4 Exchange
**Started:** 2026-06-01
**Append-only:** New findings go at the bottom. Never delete or modify earlier entries.

---

<!-- Findings will be appended below this line as experiments complete -->

## EH1 -- HIPAA Operator Property Verification

**Date:** 2026-06-01
**Status:** ACCEPTED (all properties verified)

33/33 property-based tests pass. Theorems H1-H5 verified computationally
across 10,000+ random opinions with zero counterexamples. Constraint
l+v+u=1 holds within epsilon=1e-9 for every composition tested.

## EH2 -- Clinical HIPAA Compliance Pipeline (Run 1)

**Date:** 2026-06-01
**Status:** ALL PHASES PASS, numbers verified against theory

### Phase A: PHI Classification
- 100 patients, all have exactly 6 identifiers present
  (names, geographic_subdivisions, dates, phone_numbers,
   social_security_numbers, other_unique_identifiers)
- l_PHI = 8.44e-9 (verified: 0.05^6 * 0.95^12)
- v_PHI = 0.9999992 (verified: 1 - 0.10^6 * 0.98^12)
- Bootstrap CI: zero variance (all patients identical)
- FINDING: Synthea generates uniform identifier profiles.
  This is an honest limitation of the data source, not the algebra.

### Phase B: De-identification Assessment
- Safe Harbor l = 0.6516 (verified: 0.95^6 * 0.99^12)
- Expert l = 0.765 (verified: 0.85 * 0.90)
- Expert exceeds SH: 100/100 patients (100%)
- Trust threshold = 0.724 (verified: 0.6516 / 0.90)
- FINDING: Expert Determination consistently yields higher confidence
  than Safe Harbor. Theorem H2(e) threshold formula validated.

### Phase C: BAA Trust Chain
- Source l=0.950, Depth 1: l=0.812, Depth 2: l=0.694, Depth 3: l=0.594
- Theoretical final l = 0.593775, Actual = 0.593775, EXACT MATCH
- Degradation: 14.5%, 26.9%, 37.5% at depths 1, 2, 3
- FINDING: Theorem H4(c) multiplicative chain decay verified exactly.

### Phase D: Dual-Regime Composition
- HIPAA l = 8.44e-9 (from Phase A raw data)
- Dual l = 7.60e-11 (HIPAA * GDPR identifier * lawful basis * minimization)
- Composite <= min: 100/100 (Theorem H5(b) verified)
- FINDING: Raw patient data produces trivially near-zero compliance.
  This is correct but uninformative for demonstrating dual-regime.

### Issues Identified for Improvement
1. Zero variance across patients (Synthea uniformity)
2. Phase A/D produce l near 0 for raw data (correct but trivial)
3. Need additional scenarios: partial de-identification, post-deident
   dual-regime, varying identifier counts
4. Bug found and fixed: projected_probability is a method (not property)
   on Opinion; must call with parentheses
5. Bug found and fixed: Phase D GDPR opinion construction via arbitrary
   scaling violated b+d+u=1 constraint; replaced with first-principles
   _build_gdpr_opinion_from_presence()

## EH2 Phase E -- Rigorous Degradation Analysis

**Date:** 2026-06-01
**Status:** ALL FIVE ANALYSES PASS

### E1: Theoretical Degradation Table
- 57 cells (n=0..18 x p=0.90,0.95,0.99), zero mismatches
- Key finding: even at p=0.99, n=6 present identifiers gives l=1.38e-8
- At n=0 (no identifiers): l ranges 0.150 (p=0.90) to 0.834 (p=0.99)
- At n=18 (all identifiers): l = 3.81e-24 regardless of p
- Theorem H1(c) exponential degradation confirmed across full grid

### E2: Progressive De-identification Curve
- Each identifier removal boosts l by ~19x (replacing 0.05 with 0.95)
- Recovery: 8.44e-9 -> 1.60e-7 -> 3.05e-6 -> 5.79e-5 -> 1.10e-3 -> 2.09e-2 -> 3.97e-1
- Final l = 0.3972 matches 0.95^18 exactly
- Demonstrates: progressive de-identification has quantifiable, monotonic benefit

### E3: Post-De-identification Dual-Regime
- Scenario A (Safe Harbor): HIPAA l=0.652, GDPR l=0.450, Dual l=0.293
  -> Dual drops 55% below HIPAA, 35% below GDPR
- Scenario B (Expert): HIPAA l=0.765, GDPR l=0.550, Dual l=0.421
  -> Expert method yields higher compliance in both regimes
- Scenario C (Raw): HIPAA l=8.44e-9, GDPR l=0.009, Dual l=7.60e-11
  -> Trivially near-zero, confirms raw data is non-compliant
- Theorem H5(b) verified: composite <= min(individual) in ALL scenarios

### E4: Trust Threshold Sensitivity
- Theoretical crossover (all 18): t > 0.4413
- Empirical crossover (all 18): t = 0.45 (first step above threshold)
- Theoretical crossover (Synthea 6): t > 0.7240
- Empirical crossover (Synthea 6): t = 0.75 (first step above threshold)
- Clean sweep validates Theorem H2(e) across full trust range

### E5: Cross-Resource-Type PHI Profiles
- Condition (2 IDs): l=1.10e-3 (moderate risk)
- Observation (3 IDs): l=5.79e-5
- MedicationRequest (3 IDs): l=5.79e-5
- DiagnosticReport (5 IDs): l=1.60e-7
- ImagingStudy (5 IDs): l=1.60e-7
- Patient (6 IDs): l=8.44e-9
- Claim (8 IDs): l=2.34e-11 (highest PHI risk)
- All theoretical predictions match
- FINDING: Resource types with more identifiers have dramatically
  lower compliance confidence, as expected from exponential degradation

## EH3 -- Privacy-Preserving Compliance Aggregation (HE PoC)

**Date:** 2026-06-01
**Status:** ALL FOUR HYPOTHESES ACCEPTED

### Accuracy (H-EH3.1)
- 1000 random opinion pairs at depth 1
- Raw error l: mean=3.24e-08, max=1.19e-07
- That is 10,000x better than the 0.001 threshold
- CKKS is essentially exact for single-level J_sqcap

### Constraint Preservation (H-EH3.2)
- Raw constraint violation max: 6.70e-13 (near machine epsilon)
- Normalized constraint violation max: 2.22e-16 (double precision limit)
- l+v+u=1 maintained to extraordinary precision even without normalization

### Latency (H-EH3.3)
- Keygen: 204.1ms (one-time cost)
- Encrypt: p50=19.26ms
- Compute: p50=6.06ms
- Decrypt: p50=1.93ms
- Total: p50=27.34ms, p99=29.90ms (well under 100ms threshold)
- Overhead vs plaintext: 15,186x
- HONEST REPORTING: 15K overhead is substantial but operation
  completes in 27ms, which is acceptable for compliance assessment
  (not a real-time control loop)
- Plaintext baseline: p50=0.0018ms (1.8 microseconds)

### Chain Depth (H-EH3.4)
- Depth 1: error_l_max=1.07e-07, 100% within 0.001
- Depth 2: error_l_max=4.27e-07, 100% within 0.001
- Depth 3: error_l_max=3.97e-06, 100% within 0.001
- Depth 4: error_l_max=1.95e-06, 100% within 0.001
- Depth 5: error_l_max=2.65e-06, 100% within 0.001
- ALL depths 1-5 maintain 100% of trials within epsilon=0.001
- FINDING: CKKS noise management far exceeds expectations.
  Auto-adjusted poly_modulus_degree and relinearization keys
  keep error sub-microsecond even at depth 5.

### Summary for Paper
- Encrypted J_sqcap is feasible: accurate (1e-7), fast (27ms), deep (5 levels)
- Overhead is 15,186x but operation is 27ms (acceptable for compliance)
- The contribution is a feasibility proof, not a claim of practical efficiency
- All results reported honestly including the 15K overhead factor

## EH4 -- Comparison with Binary HIPAA Compliance

**Date:** 2026-06-01
**Status:** COMPLETE, 5 scenarios paper-ready

| Scenario | Binary | Algebra (l,v,u) | Key Insight |
|----------|--------|-----------------|-------------|
| Conflicting audit evidence | 50% / INCONCLUSIVE | (0.085, 0.810, 0.105) | Conflict visible |
| New vendor (no history) | FAIL (both cases) | (0.000, 0.000, 1.000) | Ignorance != violation |
| BAA chain (3 orgs) | FAIL (any link) | (0.176, 0.502, 0.322) | Degradation quantified |
| Stale assessment (2yr) | PASS (no decay) | (0.225, 0.013, 0.762) | Staleness quantified |
| HIPAA+GDPR uncertain | FAIL (both cases) | (0.352, 0.184, 0.464) | Uncertainty != violation |

Key findings:
- Scenario 2 is the strongest distinction: binary treats complete
  ignorance (u=1) and known violation (v=1) identically as FAIL.
  The algebra gives P(vendor)=0.5 vs P(violator)=0.0.
- Scenario 4 demonstrates temporal decay: l drops from 0.900 to 0.225
  over 2 years while u grows from 0.050 to 0.762. Binary gives PASS forever.
- Scenario 3 quantifies supply chain risk: billing link causes 80.9%
  total compliance degradation.

## Camera-ready verification pass (2026-09-11)

**Status:** read-only checks of the accepted PDF against experiments/results/*.json

- Theorem 2 as printed (t* = p^n / l_expert) gives 0.817 for n = 6, p = 0.95, as
  Reviewer 2 computed. The printed 0.724 is 0.95^6 * 0.99^12 / 0.90, the Synthea
  scenario in eh2_phase_e_results.json (e4: threshold_synthea_theoretical =
  0.72397), which uses q = 0.99 for the 12 never-present categories. The
  theorem statement had dropped q. Corrected in the paper; the numbers were right.
- Table VI 6-month row printed (0.636, 0.035, 0.329, P 0.800); eh4_results.json
  scenario 4 (base_rate 0.5, half_life 365 d, elapsed 180 d) gives
  (0.6394, 0.0355, 0.3251) and P = 0.802. 3-year P printed 0.554; exact
  0.1125 + 0.5 * 0.8812 = 0.5531 -> 0.553. Both corrected.
- V-C crossing sentence: P(1 yr) = 0.713 > 0.70, P(2 yr) = 0.606 < 0.70, so the
  crossing is between one and two years, not between six months and one year.
- Conclusion HE claim: depths 3 to 5 have max errors 3.97e-6, 1.95e-6, 2.65e-6, so
  "within 1e-7 across depths up to five" was wrong; now stated per single operation
  (1.19e-7) and across depths (4.0e-6).
- Workflow Step 4 composite printed (0.293, 0.474, 0.233); e3 scenario A gives
  (0.2934, 0.4750, 0.2316). Corrected to (0.293, 0.475, 0.232).
- Workflow Step 1 P = 8.45e-9 is correct (e3 raw scenario pp = 8.446e-9).
- Regulatory quote "review and modify ... as needed" is 45 CFR 164.306(e)
  (Security Rule), not 164.530(i). Corrected, with the Privacy Rule sections
  164.502(e) and 164.514 now cited to the Privacy Rule entry.
- Tables I, II, III, V, VII and Fig. 1 and Fig. 3 spot-checked: match.

## EH2 addendum -- FHIR R4 compliance opinion carrier

**Date:** 2026-09-11
**Status:** COMPLETE (results/eh2_fhir_carrier_results.json)
**Library:** jsonld-ex commit 15ca423 (fhir_attach_compliance_opinion /
fhir_read_compliance_opinion, 23 unit tests, 423 tests passing in the touched suites)

- Carrier: complex extension in Resource.meta.extension, URL
  https://jsonld-ex.github.io/ns/fhir/compliance-opinion, sub-extensions
  belief / disbelief / uncertainty / baseRate (valueDecimal), optional regime
  (valueCode) and assessedAt (valueDateTime). Distinct from the clinical
  carrier URL .../fhir/opinion, which attaches to the qualified element.
- Exercise: PHI Classification opinion of each of the 100 Synthea bundles
  attached at Bundle.meta and Patient.meta, serialized to JSON text, reloaded,
  read back.
- H-C1 round trip exact: ACCEPTED (max |read - original| = 0.0 over all
  components, both levels, 100/100 bundles).
- H-C2 non-destructive: ACCEPTED (stripping the extension restores the
  original bundle dict, 100/100).
- Extension size 393 bytes (compact JSON, with regime and assessedAt);
  bundle growth at most 1.0993% (two attachments per bundle).

## EH5 -- Sensitivity to assumed confidences

**Date:** 2026-09-11
**Status:** COMPLETE (results/eh5_results.json); design pre-registered in EH5_DESIGN.md
**Tests:** experiments/tests/test_eh5_eh6.py (11 passed)

- A. Grid (p in {0.80..0.999} x q in {0.90..0.999}, 24 points): Expert Determination
  at t = 0.85 (l_ED = 0.765) beats Safe Harbor at every p <= 0.95; reversals only
  at p >= 0.99 with q >= 0.99 (l_SH = 0.835 at 0.99/0.99, 0.930 at 0.99/0.999,
  0.881 at 0.999/0.99, 0.982 at 0.999/0.999). H-EH5.1 ACCEPTED.
- B. Heterogeneous removal confidences (Beta around 0.95 / 0.99, 10,000 draws,
  seed 42): kappa = 100: l_SH median 0.653, p05 0.580, p95 0.721, expert wins
  99.8%; kappa = 20: median 0.656, p05 0.494, p95 0.798, expert wins 88.9%.
  H-EH5.2 ACCEPTED.
- C. Heterogeneous presence (Bernoulli per category at the empirical rates of the
  7 E5 profiles; dates 7/7, MRN 6/7, ...): n_present 1 to 11 (mean 4.55);
  l_PHI median 4.997e-7, p95 5.823e-4, max 3.987e-2. H-EH5.3 ACCEPTED.
- D. Base rates in {0.1, 0.3, 0.5, 0.7, 0.9}: (l, v, u) identical to the last bit
  for Safe Harbor, Expert, BAA chain, dual regime (max diff 0.0); P ranges
  0.652..0.679, 0.784..0.938, 0.594..0.673, 0.296..0.481. H-EH5.4 ACCEPTED.

## EH6 -- Two-auditor scenario under three combination rules

**Date:** 2026-09-11
**Status:** COMPLETE (results/eh6_results.json)

- Inputs: A = (0.85, 0.05, 0.10), B = (0.10, 0.80, 0.10) (EH4 scenario 1).
- J_meet: (0.085, 0.810, 0.105) (matches EH4).
- Dempster's rule on {T, F}: conflict mass K = 0.685 discarded; result
  (0.571, 0.397, 0.032): favors lawfulness with 3% uncertainty. H-EH6.1 ACCEPTED.
- SL cumulative fusion: (0.500, 0.447, 0.053): conflict also normalized away.
  H-EH6.2 ACCEPTED. Lesson: the paper's conservative treatment of conflict comes
  from choosing the meet (conjunction) rather than an evidence-accumulation rule,
  not from Subjective Logic as such.
- Interval probabilities [0.85, 0.95] and [0.10, 0.20] are disjoint: conflict is
  visible but no combined value exists.

## EH4 addendum -- traceability of Table VI and workflow Step 3

**Date:** 2026-09-11
**Status:** COMPLETE (results/eh4_addendum_results.json; first run 20260911_164012)

- Table VI recomputed through decay_opinion (fresh (0.90, 0.05, 0.05, a = 0.5),
  half-life 365 d): day 180 (0.6394, 0.0355, 0.3251, P 0.8020); day 365
  (0.4500, 0.0250, 0.5250, 0.7125); day 730 (0.2250, 0.0125, 0.7625, 0.6063);
  day 1095 (0.1125, 0.0063, 0.8812, 0.5531). All printed values within 0.0005.
- H-A1 (exact three-decimal equality) REJECTED at one cell: u(730 d) = 0.7625 is a
  rounding tie; Python round() on the double gives 0.763, the paper prints 0.762
  (half-even; row sums to 1.000; same value in Table VII and the accepted PDF).
  Printed value kept. Post-hoc criterion H-A1b (within half a printed unit)
  added and labeled as post hoc in the script; second run pending.
- First day with P < 0.70: day 397 (1.09 years). Added to V-C.
- Step 3: l_source = 0.6516, l_D1 = 0.5571 (14.5% degradation), l_D2 = 0.3551.
  H-A2 ACCEPTED; printed 0.557 and 0.355 now trace to a saved result.
