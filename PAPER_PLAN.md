# IEEE HealthCom 2026 — Paper Plan

**Working Title:** "Privacy-Preserving Confidence-Aware FHIR R4 Exchange: A HIPAA Compliance Algebra Grounded in Subjective Logic"

**Authors:** Muntaser Syed, Marius Silaghi (+ additional co-authors TBD)
**Target:** IEEE HealthCom 2026, Best Paper
**Conference:** IEEE International Conference on E-health Networking, Application & Services
**Location:** New York City, October 19–21, 2026
**Format:** 6 pages IEEE two-column (10pt), +2 pages at $100/page
**Submission:** EDAS, PDF only
**Deadline:** ~July 15, 2026 (expected extension)

---

## 1. Core Argument

FHIR R4 is the dominant standard for clinical data exchange, yet it has no mechanism
to express assertion-level uncertainty from AI models, nor to represent compliance
assessment as anything other than binary pass/fail. Meanwhile, HIPAA compliance
involves compounding uncertainty across PHI classification, de-identification methods,
minimum necessary rules, and business associate chains — uncertainty that binary
frameworks systematically erase.

We present a HIPAA compliance algebra grounded in Jøsang's Subjective Logic (SL) that:
1. Models HIPAA compliance as uncertain epistemic states (not binary labels)
2. Operates natively on FHIR R4 resources via jsonld-ex
3. Supports dual-regime GDPR × HIPAA composition for multinational health systems
4. Enables privacy-preserving compliance aggregation via homomorphic encryption

---

## 2. Contribution Delineation (Dual-Submission Safety)

### Papers that exist in the pipeline:

| Paper | Venue | Core Topic | HIPAA/HE Content? |
|-------|-------|-----------|-------------------|
| JSON-LD 1.2 | FLAIRS 2026 | Gap analysis + proposals | No |
| jsonld-ex Full | NeurIPS 2026 D&B | ML data exchange tool | EN3.4/EN8.11 as supporting experiments |
| Compliance Algebra IoT | IEEE WFIOT 2026 | Compliance algebra for IoT | Different domain (IoT, not healthcare) |
| CryptEpi | ICDM 2026 | Different scope | Different scope |

### What's EXCLUSIVELY in this HealthCom paper:

| # | Contribution | In NeurIPS? | In FLAIRS? | In WFIOT? |
|---|-------------|-------------|------------|-----------|
| C1 | HIPAA compliance operators (4 new) | No | No | No (IoT focus) |
| C2 | Dual-regime GDPR × HIPAA composition | No | No | No |
| C3 | HE-encrypted Jurisdictional Meet PoC | No | No | No |
| C4 | HIPAA clinical workflow eval on Synthea | No | No | No |

**Key safety rule:** We do NOT re-report EN3.4 or EN8.11 results. We cite the
jsonld-ex library and NeurIPS submission, and run new experiments (EH1–EH4).

---

## 3. Paper Structure (Target: 8 pages = 6 + 2 extra)

### Section 1: Introduction (0.75 pages)
- Clinical AI uncertainty gap in FHIR R4
- HIPAA compliance as uncertain epistemic states
- Contributions C1–C4
- Cite FLAIRS + NeurIPS (anonymized if needed) as foundations

### Section 2: Background and Related Work (0.75 pages)
- 2.1: Subjective Logic (Definition: Opinion ω = (b,d,u,a), key operators)
- 2.2: FHIR R4 uncertainty gap (RiskAssessment.probability is scalar-only)
- 2.3: HIPAA formalization prior work (binary tools, no uncertainty models)
- 2.4: HE for healthcare (surveys exist; none combine HE + SL)

### Section 3: HIPAA Compliance Algebra (2.0 pages) — PRIMARY CONTRIBUTION
- 3.1: Compliance Opinion Model (Definition 2, adapted for HIPAA terminology)
- 3.2: Operator H1 — PHI Classification Confidence
  - 18 HIPAA Safe Harbor identifiers as independent presence opinions
  - PHI risk = disjunction (any identifier present → PHI)
  - Proven: constraint, commutativity, monotonicity
- 3.3: Operator H2 — De-identification Assessment
  - Safe Harbor: J_⊓ over 18 removal opinions → l = ∏ lᵢ (exponential degradation)
  - Expert Determination: trust-discounted expert opinion
  - Proven: degradation monotonicity, Safe Harbor ≤ Expert when trust is high
  - **Strongest individual contribution**
- 3.4: Operator H3 — Minimum Necessary Rule (§164.502(b))
  - Three-way meet: role ∧ purpose ∧ scope
  - Proven: scope restriction monotonicity
- 3.5: Operator H4 — BAA Trust Chain (§164.502(e))
  - Compliance Propagation through business associate chains
  - Proven: chain degradation (multiplicative lawfulness decay)
- 3.6: Dual-regime composition
  - ω_dual = J_⊓(ω_GDPR, ω_HIPAA)
  - Inherits all Theorem 1 properties (commutativity, associativity, monotonicity)
  - Multinational health system scenario

### Section 4: Privacy-Preserving Compliance Assessment (0.75 pages)
- 4.1: Problem — multi-department aggregate compliance without revealing individual scores
- 4.2: CKKS-based encrypted Jurisdictional Meet
  - l_⊓ = l₁·l₂ and v_⊓ = v₁+v₂-v₁·v₂ in encrypted space
  - Post-decryption normalization for b+d+u=1 constraint
- 4.3: Honest overhead and limitations
  - What works: shallow meets (depth ≤ 3)
  - What doesn't: deep chains (noise accumulation)

### Section 5: Evaluation (2.0 pages)
- 5.1: Operator correctness (EH1 — property-based testing, 10K+ opinions)
- 5.2: Clinical compliance pipeline on Synthea (EH2)
  - PHI classification across resource types
  - De-identification assessment (Safe Harbor vs Expert)
  - BAA trust chain (3-org scenario)
  - Dual-regime GDPR × HIPAA
- 5.3: HE overhead benchmarks (EH3)
  - Plaintext vs CKKS accuracy and latency
  - Noise budget vs chain depth
- 5.4: Comparison with binary HIPAA tools (EH4 — table)

### Section 6: Conclusion (0.25 pages)
- Summary, limitations, future work

### References (~0.5 pages)

---

## 4. Experiment Design

### EH1 — HIPAA Operator Property Verification

**Hypotheses (all falsifiable):**
- H-EH1.1: All 4 operators produce valid compliance opinions (l+v+u=1, all ≥ 0)
- H-EH1.2: PHI Classification (disjunctive) is commutative and associative
- H-EH1.3: De-identification Safe Harbor: l = ∏ lᵢ (exponential degradation)
- H-EH1.4: BAA chain: l_Dₙ = l_S · ∏(tᵢ·pᵢ) (multiplicative degradation)
- H-EH1.5: Dual-regime J_⊓(ω_GDPR, ω_HIPAA) satisfies Theorem 1 properties

**Protocol:**
1. Hypothesis framework: 10,000 random opinions per property per operator
2. Edge cases: vacuous, full-belief, annihilator opinions
3. Report: properties verified count, any counterexamples, coverage

**Failure criteria:**
- Any l+v+u ≠ 1 → operator bug, fix before paper
- Any counterexample to proven property → proof error

**Est. time:** 2–3 hours (implementation + verification)

---

### EH2 — Clinical HIPAA Compliance Pipeline

**Hypotheses (all falsifiable):**
- H-EH2.1: PHI Classification identifies ≥16/18 HIPAA identifiers in Synthea Patient resources
- H-EH2.2: De-identification produces distinct confidence profiles: Safe Harbor < Expert (when expert trust > 0.8)
- H-EH2.3: BAA chain with 3 orgs shows measurable degradation (l₃ < l₁, p < 0.01, bootstrap)
- H-EH2.4: Dual-regime composite < min(single-regime) for non-trivial opinions

**Protocol:**
1. 100 Synthea patients, 32 resource types (reuse Synthea infra, NOT reuse EN3.4 results)
2. PHI Classification: scan each resource type for 18 HIPAA identifiers → per-identifier opinion
3. De-identification:
   a. Safe Harbor: 18-way J_⊓ over identifier removal opinions
   b. Expert Determination: trust-discounted expert opinion (trust = 0.85)
   c. Compare profiles: bootstrap CI on difference
4. BAA Trust Chain: 3-org scenario (hospital → lab → billing)
   a. Per-org compliance opinions from resource handling
   b. Propagate, measure degradation, bootstrap CI
5. Dual-regime: same data, compute ω_GDPR + ω_HIPAA → J_⊓ → verify composite < min

**Data:** Synthea synthetic patients (public, HIPAA-safe, reproducible)
**Statistical rigor:** Bootstrap CIs (n=1000), Holm-Bonferroni correction
**Est. time:** 4–6 hours

---

### EH3 — Privacy-Preserving Compliance Aggregation (HE PoC)

**Hypotheses (all falsifiable):**
- H-EH3.1: CKKS-encrypted J_⊓ within ε=0.001 of plaintext result
- H-EH3.2: Post-normalization restores b+d+u=1 within ε=0.0001
- H-EH3.3: Encrypted 2-party meet < 100ms (excluding keygen)
- H-EH3.4: Noise budget supports depth-3 chains before ε > 0.01

**Protocol:**
1. TenSEAL (Python CKKS wrapper around Microsoft SEAL)
2. 10,000 random opinion pairs:
   a. Plaintext J_⊓
   b. Encrypted J_⊓ (encrypt → compute → decrypt → normalize)
   c. Measure absolute error per component
3. Latency: 1000 trials, p50/p95/p99 + bootstrap CI
4. Noise budget: chain depth 1–5, accuracy at each depth

**Failure criteria:**
- ε > 0.01 at depth 1 → tune CKKS parameters
- Latency > 10s → report honestly as limitation
- Constraint violation > 0.01 → normalization needs work

**Honest reporting:** If overhead is 1000×, we report it. The contribution is
feasibility proof, not a claim of practical speed.

**Est. time:** 6–8 hours (TenSEAL setup + implementation + benchmarking)

---

### EH4 — Comparison with Binary HIPAA Tools

**Protocol:**
1. Survey 3–5 existing HIPAA compliance approaches from literature
2. Construct 5 distinguishing scenarios:
   a. Conflicting evidence (high l AND high v)
   b. Absence of evidence (high u) vs assumed compliance
   c. Multi-org BAA chain with mixed compliance
   d. Stale assessment needing temporal decay
   e. Dual-regime GDPR + HIPAA
3. Show our algebra distinguishes epistemic states binary systems collapse
4. Present as comparison table

**Est. time:** 3–4 hours (literature survey + scenario construction)

---

## 5. Implementation Plan

### What goes in jsonld-ex (library code):
- `jsonld_ex/hipaa_compliance.py` — 4 operators + proofs
- `jsonld_ex/fhir_interop/_hipaa.py` — FHIR R4 bridge for HIPAA operators
- `jsonld_ex/he_compliance.py` — CKKS-encrypted Jurisdictional Meet
- Tests for all above

### What goes in this repo (experiments):
- `experiments/EH1/` — Operator verification
- `experiments/EH2/` — Clinical pipeline
- `experiments/EH3/` — HE PoC
- `experiments/EH4/` — Binary comparison
- `experiments/tests/` — RED-phase tests
- `experiments/results/` — JSON output
- `paper/` — LaTeX source
- `figures/` — TikZ/pgfplots figures

### TDD Workflow (for each operator):
1. Write RED-phase test (property-based + edge cases)
2. Implement operator → verify GREEN
3. Add FHIR R4 bridge
4. Write experiment runner
5. Run at full scale
6. Append findings to FINDINGS.md
7. Commit + push

---

## 6. Timeline (Target: July 15, 2026)

| Week | Dates | Tasks | Deliverables |
|------|-------|-------|-------------|
| 1 | Jun 2–8 | HIPAA operator design + TDD implementation (H1–H4) | `hipaa_compliance.py` + tests passing |
| 2 | Jun 9–15 | FHIR bridge + EH1 (operator verification) + EH2 design | `_hipaa.py` + EH1 results |
| 3 | Jun 16–22 | EH2 (clinical pipeline) + EH3 (HE PoC setup) | EH2 results + TenSEAL working |
| 4 | Jun 23–29 | EH3 (HE benchmarks) + EH4 (binary comparison) | EH3 + EH4 results |
| 5 | Jun 30–Jul 6 | Paper writing (all sections) + figures | Draft complete |
| 6 | Jul 7–13 | Polish, verify numbers, co-author review, IEEE PDF eXpress | Submission-ready |
| 7 | Jul 14–15 | Submit via EDAS | SUBMITTED |

---

## 7. Open Questions

1. **Co-authors**: Healthcare domain expert? Would strengthen HIPAA interpretation.
2. **HE scope**: CKKS PoC is valuable but adds engineering risk. If TenSEAL
   proves problematic on Windows, fallback plan = theoretical analysis only
   (which SL operations are HE-compatible, without implementation).
3. **Self-citation**: NeurIPS under review → anonymous self-citation
   (e.g., "anonymous2026jsonldex") with camera-ready restore note.
4. **NYC travel**: Feasible for Oct 19–21 in-person presentation?

---

## 8. What Makes This Best Paper

1. **Formal rigor** rare at HealthCom: 5+ theorems with proofs, property-based testing
2. **Three-world bridge**: healthcare (FHIR) + formal methods (SL) + privacy (HE)
3. **Practical relevance**: HIPAA affects every US healthcare org
4. **Honest science**: reporting HE overhead truthfully, legal caveats, bias directions
5. **Implementation-backed**: pip install jsonld-ex → verify claims
6. **Unique capability**: dual-regime GDPR × HIPAA — nobody has done this
