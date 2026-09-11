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
