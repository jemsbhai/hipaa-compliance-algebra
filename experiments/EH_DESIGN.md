# HIPAA Compliance Algebra — Mathematical Design Document

**For:** IEEE HealthCom 2026
**Date:** 2026-06-01
**Author:** Muntaser Syed, Marius Silaghi

This document defines 4 HIPAA-specific compliance operators, their formal
properties, and required proofs. All operators reuse existing SL primitives
from jsonld-ex. The mathematical structure mirrors the GDPR compliance
algebra (compliance_algebra.md) — same algebraic foundations, HIPAA-specific
parameterizations and semantic mappings.

**Scope caveat (carried from GDPR algebra):** We are computer scientists
proposing a formal model, not legal scholars providing authoritative HIPAA
interpretation. All mappings from HIPAA provisions to algebraic operations
involve interpretive choices. We frame these as proposals, not legal mandates.

---

## Preliminaries

We reuse the Compliance Opinion from the GDPR algebra:

**Definition 1 (Compliance Opinion).** ω = (l, v, u, a) where:
- l = lawfulness (belief of compliance)
- v = violation (belief of violation)
- u = uncertainty (absence of evidence)
- a = base rate (prior compliance probability)
- Constraint: l + v + u = 1, all components ∈ [0, 1]
- Projected probability: P(ω) = l + a·u

**Reused operators:**
- J_⊓ (Jurisdictional Meet): conjunction of compliance opinions
- Compliance Propagation: propagation through derivation chains
- trust_discount: transitive trust → uncertainty on target proposition
- decay_opinion: temporal degradation of evidence

All definitions, theorems, and proofs for these operators are in
compliance_algebra.md §5–§9. We do not reproduce them here.

---

## Operator H1: PHI Classification Confidence

### Regulatory Basis

HIPAA §164.514(b)(2) defines the Safe Harbor method for de-identification
by enumerating 18 categories of identifiers. Protected Health Information
(PHI) is individually identifiable health information — data that identifies
or could reasonably be used to identify an individual.

The 18 HIPAA Safe Harbor identifier categories are:
 1. Names
 2. Geographic subdivisions smaller than a state
 3. Dates (except year) directly related to an individual
 4. Phone numbers
 5. Fax numbers
 6. Email addresses
 7. Social Security numbers
 8. Medical record numbers
 9. Health plan beneficiary numbers
10. Account numbers
11. Certificate/license numbers
12. Vehicle identifiers and serial numbers
13. Device identifiers and serial numbers
14. Web URLs
15. IP addresses
16. Biometric identifiers (fingerprints, voiceprints)
17. Full-face photographs and comparable images
18. Any other unique identifying number, characteristic, or code

### Formal Definition

**Definition 2 (Identifier Absence Opinion).** For each identifier category
i ∈ {1, ..., 18}, the identifier absence opinion is:

  ω_i = (l_i, v_i, u_i, a_i)

where l_i is belief that identifier i is absent or properly handled,
v_i is belief that identifier i is present (PHI risk), and u_i is
uncertainty about the identifier's status.

**Definition 3 (PHI Classification).** Given identifier absence opinions
ω_1, ..., ω_n (where n ≤ 18), the PHI classification opinion is:

  PHI(ω_1, ..., ω_n) = J_⊓(ω_1, ..., ω_n)

with components:
  l_PHI = ∏ᵢ lᵢ
  v_PHI = 1 − ∏ᵢ(1 − vᵢ)
  u_PHI = ∏ᵢ(1 − vᵢ) − ∏ᵢ lᵢ
  a_PHI = ∏ᵢ aᵢ

### Semantic Justification

Data is PHI-free only if ALL identifiers are absent — a conjunction.
The presence of ANY identifier makes the data identifiable. J_⊓ is
the correct operator because:

1. Lawfulness (PHI-free status) requires satisfying ALL absence conditions
2. Violation (PHI presence) follows from ANY identifier presence
3. This is structurally identical to multi-jurisdictional compliance

### Theorem H1 (PHI Classification Properties)

**(a) Constraint and non-negativity:** l_PHI + v_PHI + u_PHI = 1, all ≥ 0.

*Proof:* Inherited from Theorem 1(a-b) of the GDPR algebra. ∎

**(b) Monotonic restriction:** l_PHI ≤ min(l₁, ..., lₙ).

*Proof:* l_PHI = ∏ lᵢ ≤ lⱼ for any j (since all lᵢ ≤ 1). ∎

**(c) Monotonic violation:** v_PHI ≥ max(v₁, ..., vₙ).

*Proof:* v_PHI = 1 − ∏(1−vᵢ) ≥ 1 − (1−vⱼ) = vⱼ for any j. ∎

**(d) Exponential degradation:** With uniform lᵢ = p, l_PHI = p^n.

*Proof:* ∏ᵢ lᵢ = p^n by direct computation. ∎

Numerical illustration (p = per-identifier confidence, n = 18):
| p    | l_PHI = p^18 |
|------|-------------|
| 0.99 | 0.835       |
| 0.95 | 0.397       |
| 0.90 | 0.150       |
| 0.80 | 0.018       |

Even 99% confidence per identifier yields only 83.5% aggregate confidence.
This quantifies the intuition that PHI classification is hard when many
identifier categories must be simultaneously controlled.

**(e) Commutativity and associativity:** Inherited from Theorem 1(e-f). ∎

**(f) Single-identifier dominance:** If any vᵢ = 1, then v_PHI = 1.

*Proof:* v_PHI = 1 − ∏(1−vᵢ). If vⱼ = 1, then factor (1−vⱼ) = 0,
so the product is 0 and v_PHI = 1. This is the annihilator property
(Theorem 1(h)). ∎

**(g) Partial coverage:** If only m < 18 identifiers are assessed (the rest
have vacuous opinions ω_V = (0,0,1,a)), then l_PHI = 0 (since l_V = 0).

*Proof:* Any vacuous factor contributes lᵢ = 0 to the product. ∎

**Implication of (g):** You MUST assess all relevant identifiers. Leaving any
unassessed (vacuous) drives aggregate lawfulness to zero. This is
mathematically correct — you cannot claim data is PHI-free if you haven't
checked all identifier categories. In practice, not all 18 apply to every
resource type; the set of applicable identifiers should be determined per
resource type.

### FHIR R4 Mapping

For each FHIR R4 resource type, the applicable HIPAA identifiers differ:

| FHIR Resource | Applicable Identifiers (examples) |
|--------------|----------------------------------|
| Patient      | 1(names), 2(geography), 3(dates), 4(phone), 6(email), 7(SSN), 8(MRN), 9(health plan) |
| Observation  | 3(dates), 8(MRN — via subject ref) |
| Condition    | 3(dates), 8(MRN — via subject ref) |
| MedicationRequest | 3(dates), 8(MRN — via subject ref) |

The FHIR bridge infers ω_i from resource field presence/absence:
- Field present with valid data → l_i low (identifier present → risk)
- Field absent → l_i high (identifier absent → safe)
- Field present but masked/redacted → l_i depends on redaction quality

---

## Operator H2: De-identification Assessment

### Regulatory Basis

HIPAA §164.514 provides two methods for de-identification:

**Safe Harbor (§164.514(b)(2)):** Remove all 18 identifier categories AND
the covered entity has no actual knowledge that remaining information could
identify an individual.

**Expert Determination (§164.514(b)(1)):** A qualified statistical or
scientific expert determines that the risk of identifying an individual
is "very small."

### Formal Definition

**Definition 4 (Safe Harbor Assessment).** Given removal opinions
ω_r1, ..., ω_r18 where ω_ri = (l_ri, v_ri, u_ri, a_ri) represents
confidence that identifier i has been successfully removed:

  DeidentSH(ω_r1, ..., ω_r18) = J_⊓(ω_r1, ..., ω_r18)

This is mathematically identical to PHI Classification but with different
semantic content: PHI Classification asks "is PHI present?", while
Safe Harbor asks "has PHI been successfully removed?"

**Definition 5 (Expert Determination Assessment).** Given the expert's
de-identification opinion ω_expert and trust in the expert ω_trust:

  DeidentED(ω_expert, ω_trust) = trust_discount(ω_trust, ω_expert)

where trust_discount is Jøsang's standard operator (SL §10.2):
  l_ED = t · l_expert
  v_ED = t · v_expert  (Note: trust discount does NOT produce disbelief)

**Correction:** Standard trust discount produces:
  b_discounted = t · b_expert
  d_discounted = t · d_expert  
  u_discounted = 1 − t·(b_expert + d_expert)

So: l_ED = t · l_expert, v_ED = t · v_expert, u_ED = 1 − t·(l_expert + v_expert)

### Theorem H2 (De-identification Properties)

**(a) Safe Harbor constraint + non-negativity:** Inherited from J_⊓. ∎

**(b) Safe Harbor exponential degradation:** l_SH = ∏ l_ri. With uniform
removal confidence p: l_SH = p^18.

*Proof:* Same as Theorem H1(d). ∎

**(c) Expert Determination scaling:** l_ED = t · l_expert (linear in trust).

*Proof:* Direct from trust discount definition. ∎

**(d) Method comparison:**
  - Safe Harbor is more conservative when ∏ l_ri < t · l_expert
  - Expert Determination is more conservative when t · l_expert < ∏ l_ri
  - In general, neither dominates the other

*Proof:* Both methods produce valid compliance opinions, but about different
propositions (exhaustive removal vs statistical unidentifiability). Direct
comparison of projected probabilities gives the stated condition. ∎

**(e) Expert trust threshold:** For Safe Harbor with uniform p across 18
identifiers, Expert Determination gives higher confidence when:
  t > p^18 / l_expert

*Proof:* l_ED > l_SH iff t · l_expert > p^18, i.e., t > p^18 / l_expert. ∎

Numerical example: if p = 0.95 (per-identifier removal confidence),
l_expert = 0.90 (expert's assessment), then threshold t > 0.397/0.90 = 0.441.
Any expert trusted above 44.1% gives higher confidence than Safe Harbor.
This quantifies why Expert Determination is preferred when available —
a single trusted expert can outperform 18 individual checks.

**(f) No knowledge condition:** Safe Harbor additionally requires "no actual
knowledge" of re-identification risk. We model this as an additional factor:

  DeidentSH_full(ω_r1, ..., ω_r18, ω_knowledge) = J_⊓(ω_r1, ..., ω_r18, ω_knowledge)

where ω_knowledge represents confidence that no re-identification knowledge exists.

---

## Operator H3: Minimum Necessary Rule

### Regulatory Basis

HIPAA §164.502(b): "When using or disclosing protected health information
or when requesting protected health information from another covered entity
or business associate, a covered entity or business associate must make
reasonable efforts to limit protected health information to the minimum
necessary to accomplish the intended purpose."

Three independent conditions must hold:
1. The requestor has a legitimate role
2. The purpose is valid (treatment, payment, operations — TPO)
3. The data scope is minimized

### Formal Definition

**Definition 6 (Minimum Necessary Assessment).** Given:
- ω_role = (l_r, v_r, u_r, a_r): legitimacy of requestor's role
- ω_purpose = (l_p, v_p, u_p, a_p): validity of stated purpose
- ω_scope = (l_s, v_s, u_s, a_s): adequacy of scope limitation

  MinNec(ω_role, ω_purpose, ω_scope) = J_⊓(ω_role, ω_purpose, ω_scope)

Components:
  l_MN = l_r · l_p · l_s
  v_MN = 1 − (1−v_r)(1−v_p)(1−v_s)
  u_MN = (1−v_r)(1−v_p)(1−v_s) − l_r · l_p · l_s
  a_MN = a_r · a_p · a_s

### FHIR R4 Mapping

For FHIR R4 resources, the three components can be inferred:

**Role inference (ω_role):**
- Practitioner with valid specialty → high l_r
- Unspecified requestor → high u_r
- Role mismatch (cardiologist accessing psychiatric records) → low l_r

**Purpose inference (ω_purpose):**
- Encounter-linked request (treatment) → high l_p
- Billing-linked request (payment) → high l_p
- Research request without consent → low l_p

**Scope inference (ω_scope):**
- Requesting specific Observation → high l_s
- Requesting entire patient record → low l_s
- Requesting with date range filter → moderate l_s

### Theorem H3 (Minimum Necessary Properties)

**(a) Constraint and non-negativity:** Inherited from J_⊓. ∎

**(b) Monotonic restriction:** l_MN ≤ min(l_r, l_p, l_s).

*Proof:* l_MN = l_r · l_p · l_s ≤ l_r · 1 · 1 = l_r, and symmetrically
for l_p, l_s. ∎

**(c) Weakest-link sensitivity:** l_MN = 0 whenever any component has l = 0.

*Proof:* Product includes a zero factor. ∎

**Practical implication of (c):** If role legitimacy is completely unknown
(l_r = 0), no amount of purpose validity or scope limitation can rescue
the composite assessment. All three conditions must be addressed.

**(d) Scope relaxation effect:** Removing the scope requirement
(setting ω_scope = ω_identity = (1,0,0,1)) gives:
  MinNec(ω_role, ω_purpose, ω_identity) = J_⊓(ω_role, ω_purpose)
with l_relaxed ≥ l_MN (equality iff l_s = 1).

*Proof:* Removing a factor ≤ 1 from a product can only increase it. ∎

This quantifies the compliance cost of not enforcing minimum necessary scope.

---

## Operator H4: BAA Trust Chain

### Regulatory Basis

HIPAA §164.502(e): A covered entity may disclose PHI to a business
associate and allow the business associate to create, receive, maintain,
or transmit PHI on behalf of the covered entity, provided the covered
entity obtains satisfactory assurances (via a Business Associate Agreement)
that the BA will appropriately safeguard the information.

§164.504(e): The BAA must include provisions for:
- Permitted uses and disclosures
- Safeguards to prevent unauthorized use
- Reporting of security incidents
- Ensuring subcontractors agree to same restrictions

This creates a CHAIN: Covered Entity → BA → Sub-BA → ...
Each link adds compliance uncertainty.

### Formal Definition

**Definition 7 (BAA Link Opinion).** For each business associate
relationship in the chain, we define:
- τ_i = (t_i, f_i, u_τi, a_τi): trust that the BA's safeguards are adequate
  (maps to "satisfactory assurances" requirement)
- π_i = (p_i, q_i, u_πi, a_πi): trust that the BA's use is purpose-compatible
  (maps to "permitted uses and disclosures" requirement)

**Definition 8 (BAA Trust Chain).** Given source entity compliance ω_S and
a chain of n business associate links [(τ₁,π₁), ..., (τₙ,πₙ)]:

  BAAChain(ω_S, [(τ₁,π₁), ..., (τₙ,πₙ)]) = Propₙ ∘ ... ∘ Prop₁(ω_S)

where Propᵢ(ω) = J_⊓(τᵢ, πᵢ, ω) is the Compliance Propagation operator.

Components at step n:
  l_Dₙ = l_S · ∏ᵢ₌₁ⁿ (tᵢ · pᵢ)
  v_Dₙ = 1 − (1−v_S) · ∏ᵢ₌₁ⁿ (1−fᵢ)(1−qᵢ)

### FHIR R4 Mapping

In a clinical context, BAA chains arise naturally:
- Hospital (covered entity) → Lab (BA) → Cloud storage (sub-BA)
- Hospital → Billing service (BA) → Clearinghouse (sub-BA)
- Hospital → Telehealth platform (BA) → AI analytics provider (sub-BA)

For each link, τ and π can be inferred from:
- BAA provisions completeness → τ
- Purpose specification clarity → π
- Historical audit results → evidence for τ, π

### Theorem H4 (BAA Trust Chain Properties)

**(a) Constraint and non-negativity:** Inherited from repeated J_⊓. ∎

**(b) Degradation monotonicity:** l_Dₙ ≤ l_S (equality iff all t_i = p_i = 1).

*Proof:* l_Dₙ = l_S · ∏(tᵢ · pᵢ) with each factor tᵢ · pᵢ ≤ 1. ∎

**(c) Multiplicative chain decay:**

  l_Dₙ = l_S · ∏ᵢ₌₁ⁿ (tᵢ · pᵢ)

With uniform t, p across all links: l_Dₙ = l_S · (t·p)^n.

*Proof:* By induction on n. Base: l_D₁ = l_S · t₁ · p₁.
Step: l_D_{n+1} = l_Dₙ · t_{n+1} · p_{n+1} = l_S · ∏ᵢ₌₁ⁿ⁺¹ (tᵢ·pᵢ). ∎

Numerical illustration (l_S = 0.95, uniform t = 0.9, p = 0.95):
| Chain depth n | l_Dₙ              |
|--------------|-------------------|
| 0 (source)   | 0.950             |
| 1 (1 BA)     | 0.812             |
| 2 (sub-BA)   | 0.694             |
| 3            | 0.593             |
| 5            | 0.434             |

HIPAA requires BAA chains for a reason — each link genuinely
degrades compliance confidence.

**(d) Identity link:** τ_id = (1,0,0,1), π_id = (1,0,0,1) gives
Prop(τ_id, π_id, ω_S) = ω_S. A perfect BA adds no risk.

*Proof:* l_D = l_S · 1 · 1 = l_S. ∎

**(e) Violation annihilation:** If any τᵢ = (0,1,0,0) (known safeguard
failure) or πᵢ = (0,1,0,0) (known purpose violation), then v_Dₙ = 1.

*Proof:* Factor (1−fᵢ) = 0, making the non-violation product 0, so v = 1. ∎

**(f) Chain associativity:** Grouping doesn't matter — the result is the
same whether we propagate step-by-step or batch.

*Proof:* The product ∏(tᵢ·pᵢ) is associative. ∎

**(g) Provenance chain:** Each propagation step appends to the audit chain
Π = [(ω_S, t₀), (τ₁,π₁,t₁), ..., (τₙ,πₙ,tₙ)]. This chain is the
required documentation under §164.530(j) (6-year retention).

---

## Operator H5: Dual-Regime Composition

### Regulatory Basis

Multinational health systems (e.g., US hospital network with EU operations,
or EU pharmaceutical company conducting US clinical trials) must comply
with BOTH HIPAA and GDPR simultaneously. Composite compliance requires
satisfying all requirements of all applicable regimes.

### Formal Definition

**Definition 9 (Dual-Regime Composition).** Given HIPAA compliance opinion
ω_HIPAA and GDPR compliance opinion ω_GDPR for the same data processing:

  DualRegime(ω_HIPAA, ω_GDPR) = J_⊓(ω_HIPAA, ω_GDPR)

This is the Jurisdictional Meet applied across regulatory frameworks,
which is exactly the operator's designed purpose.

### Theorem H5 (Dual-Regime Properties)

All properties of Theorem 1 (GDPR algebra) apply directly:

**(a) Constraint and non-negativity:** l_dual + v_dual + u_dual = 1, all ≥ 0. ∎

**(b) Composite ≤ individual:** l_dual = l_HIPAA · l_GDPR ≤ min(l_HIPAA, l_GDPR).

*Proof:* Product of factors ∈ [0,1] is ≤ each factor. ∎

**(c) Strictest regime dominates:** If ω_GDPR has low l_GDPR (strict regime),
it pulls the composite down regardless of ω_HIPAA.

**(d) Regulatory vacuum:** If one regime opinion is vacuous (ω = (0,0,1,a)),
the composite l_dual = 0. Complete uncertainty about one regime prevents
confident composite compliance.

*Proof:* l_dual = l_HIPAA · 0 = 0. ∎

**(e) Commutativity:** HIPAA-first and GDPR-first yield identical results.

*Proof:* J_⊓ is commutative (Theorem 1(e)). ∎

### Practical Significance

This is, to our knowledge, the first formal framework for computing
dual-regime compliance with uncertainty quantification. Binary approaches
use AND (compliant with both) but cannot distinguish:
- "probably compliant with both" (l_dual high, u_dual low)
- "uncertain about one regime" (l_dual moderate, u_dual moderate)
- "conflicting evidence about one regime" (v_dual elevated)

---

## Summary of Operators

| Operator | HIPAA Basis | SL Mechanism | Key Property |
|----------|------------|-------------|-------------|
| H1: PHI Classification | §164.514(b)(2) | J_⊓ over 18 identifiers | Exponential degradation: l = p^n |
| H2: De-identification | §164.514(b)(1-2) | J_⊓ (Safe Harbor), trust_discount (Expert) | Method comparison theorem |
| H3: Minimum Necessary | §164.502(b) | J_⊓(role, purpose, scope) | Weakest-link sensitivity |
| H4: BAA Trust Chain | §164.502(e) | Compliance Propagation | Multiplicative chain decay |
| H5: Dual-Regime | Cross-regulation | J_⊓(ω_HIPAA, ω_GDPR) | Composite ≤ min(individual) |

### Relationship to Existing jsonld-ex Operators

| New Operator | Reuses | What's New |
|-------------|--------|-----------|
| H1 | J_⊓ | HIPAA identifier mapping, FHIR bridge |
| H2 (SH) | J_⊓ | 18-way removal composition, comparison theorem |
| H2 (ED) | trust_discount | Expert trust semantics for de-identification |
| H3 | J_⊓ | Role/purpose/scope triple, FHIR inference |
| H4 | Compliance Propagation | BAA semantics, HIPAA audit chain requirements |
| H5 | J_⊓ | Cross-framework composition |

The contribution is NOT new mathematics — it's the identification that these
specific regulatory provisions map to specific algebraic operations, the
formal proofs of domain-relevant properties, and the FHIR R4 implementation
enabling practical clinical use.

---

## Independence Assumptions and Bias Directions

**PHI Classification (H1):** Assumes independent identifier presence.
In practice, identifiers may co-occur (e.g., name often appears with MRN).
Positive correlation means true PHI risk EXCEEDS our estimate. Bias:
**non-conservative** (underestimates risk).

**De-identification Safe Harbor (H2):** Assumes independent removal success.
In practice, removing one identifier doesn't help remove another, so
independence is more defensible here than in H1.

**Minimum Necessary (H3):** Assumes role, purpose, and scope are assessed
independently. In practice, certain roles have implicit purpose (e.g.,
treating physician → treatment purpose). Independence may overstate
uncertainty. Bias: **conservative** (overestimates risk) because the
assessment ignores beneficial correlations.

**BAA Trust Chain (H4):** Assumes chain links are independent. In practice,
a parent organization with poor governance may select similarly poor BAs
(positive correlation). Bias: **non-conservative** (underestimates risk
in poorly governed organizations).

**Dual-Regime (H5):** Assumes HIPAA and GDPR compliance are assessed
independently. This is defensible — they are structurally different
regulations assessed by different standards. Positive correlation
(organizations that comply with one tend to comply with both) means
our estimate is **non-conservative**.

We document all bias directions explicitly, following the same honesty
principle established in the GDPR algebra.
