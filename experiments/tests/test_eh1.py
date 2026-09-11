"""
RED-phase tests for HIPAA Compliance Algebra operators.

These tests encode Theorems H1–H5 from EH_DESIGN.md as executable
assertions. Property-based testing via Hypothesis generates 10,000+
random opinions per property.

Status: RED — hipaa_compliance module does not exist yet.
Expected failure: ImportError on `from jsonld_ex.hipaa_compliance import ...`
"""

from __future__ import annotations

import math
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Imports that will FAIL until implementation exists (RED phase)
# ---------------------------------------------------------------------------
from jsonld_ex.compliance_algebra import ComplianceOpinion, jurisdictional_meet
from jsonld_ex.hipaa_compliance import (
    phi_classification,
    safe_harbor_assessment,
    expert_determination_assessment,
    minimum_necessary,
    baa_trust_chain,
    dual_regime_composition,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

ABS_TOL = 1e-9  # Floating-point tolerance


@st.composite
def compliance_opinions(draw: st.DrawFn) -> ComplianceOpinion:
    """Generate a random valid ComplianceOpinion."""
    # Generate l, v in [0, 1] such that l + v <= 1
    l = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    v = draw(st.floats(min_value=0.0, max_value=1.0 - l, allow_nan=False, allow_infinity=False))
    u = 1.0 - l - v
    a = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    return ComplianceOpinion(belief=l, disbelief=v, uncertainty=u, base_rate=a)


@st.composite
def opinion_lists(draw: st.DrawFn, min_size: int = 2, max_size: int = 18):
    """Generate a list of random ComplianceOpinions."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(compliance_opinions()) for _ in range(n)]


# ═══════════════════════════════════════════════════════════════════
# THEOREM H1 — PHI Classification Properties
# ═══════════════════════════════════════════════════════════════════


class TestTheoremH1_PHIClassification:
    """Verify Theorem H1(a)–(g) from EH_DESIGN.md."""

    @given(opinions=opinion_lists(min_size=2, max_size=18))
    @settings(max_examples=2000)
    def test_h1a_constraint(self, opinions: list[ComplianceOpinion]):
        """H1(a): l + v + u = 1, all >= 0."""
        result = phi_classification(opinions)
        assert result.belief >= -ABS_TOL, f"l={result.belief} < 0"
        assert result.disbelief >= -ABS_TOL, f"v={result.disbelief} < 0"
        assert result.uncertainty >= -ABS_TOL, f"u={result.uncertainty} < 0"
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL, f"l+v+u={total} != 1"

    @given(opinions=opinion_lists(min_size=2, max_size=18))
    @settings(max_examples=2000)
    def test_h1b_monotonic_restriction(self, opinions: list[ComplianceOpinion]):
        """H1(b): l_PHI <= min(l_i)."""
        result = phi_classification(opinions)
        min_l = min(o.belief for o in opinions)
        assert result.belief <= min_l + ABS_TOL, (
            f"l_PHI={result.belief} > min(l_i)={min_l}"
        )

    @given(opinions=opinion_lists(min_size=2, max_size=18))
    @settings(max_examples=2000)
    def test_h1c_monotonic_violation(self, opinions: list[ComplianceOpinion]):
        """H1(c): v_PHI >= max(v_i)."""
        result = phi_classification(opinions)
        max_v = max(o.disbelief for o in opinions)
        assert result.disbelief >= max_v - ABS_TOL, (
            f"v_PHI={result.disbelief} < max(v_i)={max_v}"
        )

    @given(
        p=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        n=st.integers(min_value=2, max_value=18),
    )
    @settings(max_examples=1000)
    def test_h1d_exponential_degradation(self, p: float, n: int):
        """H1(d): With uniform l_i = p, l_PHI = p^n."""
        # Create n opinions with identical l = p, v = (1-p)/2, u = (1-p)/2
        remainder = 1.0 - p
        v = remainder / 2.0
        u = remainder - v
        opinions = [
            ComplianceOpinion(belief=p, disbelief=v, uncertainty=u, base_rate=0.5)
            for _ in range(n)
        ]
        result = phi_classification(opinions)
        expected_l = p ** n
        assert abs(result.belief - expected_l) < ABS_TOL * 100, (
            f"l_PHI={result.belief} != p^n={expected_l} (p={p}, n={n})"
        )

    @given(opinions=opinion_lists(min_size=2, max_size=6))
    @settings(max_examples=1000)
    def test_h1e_commutativity(self, opinions: list[ComplianceOpinion]):
        """H1(e): PHI(ω₁,...,ωₙ) = PHI(ωₙ,...,ω₁) (order invariant)."""
        result_forward = phi_classification(opinions)
        result_reverse = phi_classification(list(reversed(opinions)))
        assert abs(result_forward.belief - result_reverse.belief) < ABS_TOL
        assert abs(result_forward.disbelief - result_reverse.disbelief) < ABS_TOL
        assert abs(result_forward.uncertainty - result_reverse.uncertainty) < ABS_TOL

    @given(base_opinions=opinion_lists(min_size=1, max_size=5))
    @settings(max_examples=500)
    def test_h1f_single_identifier_dominance(self, base_opinions):
        """H1(f): If any v_i = 1, then v_PHI = 1."""
        # Add a definite violation opinion
        violation = ComplianceOpinion(belief=0.0, disbelief=1.0, uncertainty=0.0, base_rate=0.5)
        opinions = base_opinions + [violation]
        result = phi_classification(opinions)
        assert abs(result.disbelief - 1.0) < ABS_TOL, (
            f"v_PHI={result.disbelief} != 1.0 despite a definite violation"
        )

    @given(base_opinions=opinion_lists(min_size=1, max_size=5))
    @settings(max_examples=500)
    def test_h1g_vacuous_drives_l_to_zero(self, base_opinions):
        """H1(g): Vacuous opinion (l=0) drives l_PHI to 0."""
        vacuous = ComplianceOpinion(belief=0.0, disbelief=0.0, uncertainty=1.0, base_rate=0.5)
        opinions = base_opinions + [vacuous]
        result = phi_classification(opinions)
        assert abs(result.belief) < ABS_TOL, (
            f"l_PHI={result.belief} != 0.0 despite vacuous opinion"
        )


# ═══════════════════════════════════════════════════════════════════
# THEOREM H2 — De-identification Properties
# ═══════════════════════════════════════════════════════════════════


class TestTheoremH2_DeIdentification:
    """Verify Theorem H2(a)–(f) from EH_DESIGN.md."""

    @given(removals=opinion_lists(min_size=2, max_size=18))
    @settings(max_examples=2000)
    def test_h2a_safe_harbor_constraint(self, removals):
        """H2(a): Safe Harbor result satisfies l+v+u=1, all >= 0."""
        result = safe_harbor_assessment(removals)
        assert result.belief >= -ABS_TOL
        assert result.disbelief >= -ABS_TOL
        assert result.uncertainty >= -ABS_TOL
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL

    @given(
        p=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        n=st.integers(min_value=2, max_value=18),
    )
    @settings(max_examples=1000)
    def test_h2b_safe_harbor_exponential(self, p: float, n: int):
        """H2(b): With uniform removal confidence p, l_SH = p^n."""
        remainder = 1.0 - p
        v = remainder / 2.0
        u = remainder - v
        removals = [
            ComplianceOpinion(belief=p, disbelief=v, uncertainty=u, base_rate=0.5)
            for _ in range(n)
        ]
        result = safe_harbor_assessment(removals)
        expected_l = p ** n
        assert abs(result.belief - expected_l) < ABS_TOL * 100, (
            f"l_SH={result.belief} != p^n={expected_l}"
        )

    @given(
        expert=compliance_opinions(),
        trust=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h2c_expert_scaling(self, expert, trust):
        """H2(c): l_ED = t · l_expert (linear in trust)."""
        result = expert_determination_assessment(expert, trust)
        expected_l = trust.belief * expert.belief
        assert abs(result.belief - expected_l) < ABS_TOL, (
            f"l_ED={result.belief} != t*l_expert={expected_l}"
        )

    @given(
        expert=compliance_opinions(),
        trust=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h2c_expert_constraint(self, expert, trust):
        """H2(c): Expert result satisfies l+v+u=1, all >= 0."""
        result = expert_determination_assessment(expert, trust)
        assert result.belief >= -ABS_TOL
        assert result.disbelief >= -ABS_TOL
        assert result.uncertainty >= -ABS_TOL
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL

    @given(
        p=st.floats(min_value=0.5, max_value=0.99, allow_nan=False),
        l_expert=st.floats(min_value=0.5, max_value=0.99, allow_nan=False),
        t=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
    )
    @settings(max_examples=1000)
    def test_h2e_expert_trust_threshold(self, p: float, l_expert: float, t: float):
        """H2(e): Expert gives higher confidence when t > p^18 / l_expert."""
        n = 18
        l_sh = p ** n
        l_ed = t * l_expert
        threshold = l_sh / l_expert if l_expert > 0 else float("inf")

        if t > threshold + ABS_TOL:
            assert l_ed > l_sh - ABS_TOL, (
                f"Expert (l_ED={l_ed}) should exceed Safe Harbor (l_SH={l_sh}) "
                f"when t={t} > threshold={threshold}"
            )


# ═══════════════════════════════════════════════════════════════════
# THEOREM H3 — Minimum Necessary Properties
# ═══════════════════════════════════════════════════════════════════


class TestTheoremH3_MinimumNecessary:
    """Verify Theorem H3(a)–(d) from EH_DESIGN.md."""

    @given(
        role=compliance_opinions(),
        purpose=compliance_opinions(),
        scope=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h3a_constraint(self, role, purpose, scope):
        """H3(a): l+v+u=1, all >= 0."""
        result = minimum_necessary(role, purpose, scope)
        assert result.belief >= -ABS_TOL
        assert result.disbelief >= -ABS_TOL
        assert result.uncertainty >= -ABS_TOL
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL

    @given(
        role=compliance_opinions(),
        purpose=compliance_opinions(),
        scope=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h3b_monotonic_restriction(self, role, purpose, scope):
        """H3(b): l_MN <= min(l_role, l_purpose, l_scope)."""
        result = minimum_necessary(role, purpose, scope)
        min_l = min(role.belief, purpose.belief, scope.belief)
        assert result.belief <= min_l + ABS_TOL

    @given(
        purpose=compliance_opinions(),
        scope=compliance_opinions(),
    )
    @settings(max_examples=1000)
    def test_h3c_weakest_link(self, purpose, scope):
        """H3(c): l_MN = 0 when any component has l = 0."""
        zero_role = ComplianceOpinion(
            belief=0.0, disbelief=0.5, uncertainty=0.5, base_rate=0.5
        )
        result = minimum_necessary(zero_role, purpose, scope)
        assert abs(result.belief) < ABS_TOL, (
            f"l_MN={result.belief} != 0 despite zero-belief role"
        )

    @given(
        role=compliance_opinions(),
        purpose=compliance_opinions(),
        scope=compliance_opinions(),
    )
    @settings(max_examples=1000)
    def test_h3d_scope_relaxation(self, role, purpose, scope):
        """H3(d): Removing scope constraint increases l."""
        identity = ComplianceOpinion(belief=1.0, disbelief=0.0, uncertainty=0.0, base_rate=1.0)
        result_full = minimum_necessary(role, purpose, scope)
        result_relaxed = minimum_necessary(role, purpose, identity)
        assert result_relaxed.belief >= result_full.belief - ABS_TOL, (
            f"Relaxed l={result_relaxed.belief} < full l={result_full.belief}"
        )


# ═══════════════════════════════════════════════════════════════════
# THEOREM H4 — BAA Trust Chain Properties
# ═══════════════════════════════════════════════════════════════════


class TestTheoremH4_BAATrustChain:
    """Verify Theorem H4(a)–(f) from EH_DESIGN.md."""

    @given(
        source=compliance_opinions(),
        tau=compliance_opinions(),
        pi=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h4a_constraint(self, source, tau, pi):
        """H4(a): Result satisfies l+v+u=1, all >= 0."""
        result = baa_trust_chain(source, [(tau, pi)])
        assert result.belief >= -ABS_TOL
        assert result.disbelief >= -ABS_TOL
        assert result.uncertainty >= -ABS_TOL
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL

    @given(
        source=compliance_opinions(),
        chain=st.lists(
            st.tuples(compliance_opinions(), compliance_opinions()),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=1000)
    def test_h4b_degradation_monotonicity(self, source, chain):
        """H4(b): l_Dₙ <= l_S."""
        result = baa_trust_chain(source, chain)
        assert result.belief <= source.belief + ABS_TOL, (
            f"l_D={result.belief} > l_S={source.belief}"
        )

    @given(
        source=compliance_opinions(),
        t=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        p=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        n=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=1000)
    def test_h4c_multiplicative_decay(self, source, t: float, p: float, n: int):
        """H4(c): l_Dₙ = l_S · (t·p)^n with uniform links."""
        remainder_t = 1.0 - t
        tau = ComplianceOpinion(
            belief=t, disbelief=remainder_t / 2, uncertainty=remainder_t / 2, base_rate=0.5
        )
        remainder_p = 1.0 - p
        pi = ComplianceOpinion(
            belief=p, disbelief=remainder_p / 2, uncertainty=remainder_p / 2, base_rate=0.5
        )
        chain = [(tau, pi)] * n
        result = baa_trust_chain(source, chain)
        expected_l = source.belief * (t * p) ** n
        assert abs(result.belief - expected_l) < ABS_TOL * 100, (
            f"l_D={result.belief} != l_S*(t*p)^n={expected_l}"
        )

    @given(source=compliance_opinions())
    @settings(max_examples=500)
    def test_h4d_identity_link(self, source):
        """H4(d): Identity link preserves source compliance."""
        identity_tau = ComplianceOpinion(belief=1.0, disbelief=0.0, uncertainty=0.0, base_rate=1.0)
        identity_pi = ComplianceOpinion(belief=1.0, disbelief=0.0, uncertainty=0.0, base_rate=1.0)
        result = baa_trust_chain(source, [(identity_tau, identity_pi)])
        assert abs(result.belief - source.belief) < ABS_TOL
        assert abs(result.disbelief - source.disbelief) < ABS_TOL
        assert abs(result.uncertainty - source.uncertainty) < ABS_TOL

    @given(
        source=compliance_opinions(),
        good_links=st.lists(
            st.tuples(compliance_opinions(), compliance_opinions()),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=500)
    def test_h4e_violation_annihilation(self, source, good_links):
        """H4(e): Known safeguard failure in any link → v = 1."""
        violation_tau = ComplianceOpinion(
            belief=0.0, disbelief=1.0, uncertainty=0.0, base_rate=0.0
        )
        any_pi = ComplianceOpinion(belief=0.5, disbelief=0.2, uncertainty=0.3, base_rate=0.5)
        chain = good_links + [(violation_tau, any_pi)]
        result = baa_trust_chain(source, chain)
        assert abs(result.disbelief - 1.0) < ABS_TOL, (
            f"v_D={result.disbelief} != 1.0 despite violation link"
        )

    @given(
        source=compliance_opinions(),
        chain=st.lists(
            st.tuples(compliance_opinions(), compliance_opinions()),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=500)
    def test_h4f_constraint_through_chain(self, source, chain):
        """H4(f): Constraint l+v+u=1 preserved through arbitrary chains."""
        result = baa_trust_chain(source, chain)
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL, f"l+v+u={total} != 1 after chain"


# ═══════════════════════════════════════════════════════════════════
# THEOREM H5 — Dual-Regime Composition Properties
# ═══════════════════════════════════════════════════════════════════


class TestTheoremH5_DualRegime:
    """Verify Theorem H5(a)–(e) from EH_DESIGN.md."""

    @given(
        hipaa=compliance_opinions(),
        gdpr=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h5a_constraint(self, hipaa, gdpr):
        """H5(a): l+v+u=1, all >= 0."""
        result = dual_regime_composition(hipaa, gdpr)
        assert result.belief >= -ABS_TOL
        assert result.disbelief >= -ABS_TOL
        assert result.uncertainty >= -ABS_TOL
        total = result.belief + result.disbelief + result.uncertainty
        assert abs(total - 1.0) < ABS_TOL

    @given(
        hipaa=compliance_opinions(),
        gdpr=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h5b_composite_leq_individual(self, hipaa, gdpr):
        """H5(b): l_dual <= min(l_HIPAA, l_GDPR)."""
        result = dual_regime_composition(hipaa, gdpr)
        min_l = min(hipaa.belief, gdpr.belief)
        assert result.belief <= min_l + ABS_TOL

    @given(hipaa=compliance_opinions())
    @settings(max_examples=500)
    def test_h5d_regulatory_vacuum(self, hipaa):
        """H5(d): Vacuous GDPR opinion → l_dual = 0."""
        vacuous_gdpr = ComplianceOpinion(
            belief=0.0, disbelief=0.0, uncertainty=1.0, base_rate=0.5
        )
        result = dual_regime_composition(hipaa, vacuous_gdpr)
        assert abs(result.belief) < ABS_TOL, (
            f"l_dual={result.belief} != 0 despite vacuous GDPR"
        )

    @given(
        hipaa=compliance_opinions(),
        gdpr=compliance_opinions(),
    )
    @settings(max_examples=2000)
    def test_h5e_commutativity(self, hipaa, gdpr):
        """H5(e): HIPAA-first and GDPR-first yield identical results."""
        result_hg = dual_regime_composition(hipaa, gdpr)
        result_gh = dual_regime_composition(gdpr, hipaa)
        assert abs(result_hg.belief - result_gh.belief) < ABS_TOL
        assert abs(result_hg.disbelief - result_gh.disbelief) < ABS_TOL
        assert abs(result_hg.uncertainty - result_gh.uncertainty) < ABS_TOL


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES — Hand-crafted scenarios
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Hand-crafted edge cases beyond property-based testing."""

    def test_full_phi_confidence(self):
        """All 18 identifiers confirmed absent → l_PHI = 1."""
        full_confidence = ComplianceOpinion(
            belief=1.0, disbelief=0.0, uncertainty=0.0, base_rate=1.0
        )
        opinions = [full_confidence] * 18
        result = phi_classification(opinions)
        assert abs(result.belief - 1.0) < ABS_TOL

    def test_safe_harbor_18_way_degradation(self):
        """18 identifiers at 95% each → l_SH = 0.95^18 ≈ 0.397."""
        opinions = [
            ComplianceOpinion(belief=0.95, disbelief=0.025, uncertainty=0.025, base_rate=0.5)
        ] * 18
        result = safe_harbor_assessment(opinions)
        expected = 0.95 ** 18
        assert abs(result.belief - expected) < 1e-6, (
            f"l_SH={result.belief} != 0.95^18={expected}"
        )

    def test_expert_vs_safe_harbor_comparison(self):
        """Expert with 50% trust beats Safe Harbor at p=0.95, n=18."""
        # Safe Harbor: 0.95^18 ≈ 0.397
        removals = [
            ComplianceOpinion(belief=0.95, disbelief=0.025, uncertainty=0.025, base_rate=0.5)
        ] * 18
        sh_result = safe_harbor_assessment(removals)

        # Expert: trust=0.50, expert_belief=0.90 → l_ED = 0.45
        expert = ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=0.5)
        trust = ComplianceOpinion(belief=0.50, disbelief=0.25, uncertainty=0.25, base_rate=0.5)
        ed_result = expert_determination_assessment(expert, trust)

        assert ed_result.belief > sh_result.belief, (
            f"Expert (l={ed_result.belief}) should exceed "
            f"Safe Harbor (l={sh_result.belief}) at these parameters"
        )

    def test_baa_three_org_scenario(self):
        """Hospital → Lab → Billing: 3-org chain degrades compliance."""
        source = ComplianceOpinion(belief=0.95, disbelief=0.02, uncertainty=0.03, base_rate=0.5)
        tau = ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=0.5)
        pi = ComplianceOpinion(belief=0.95, disbelief=0.02, uncertainty=0.03, base_rate=0.5)
        chain = [(tau, pi)] * 3

        result = baa_trust_chain(source, chain)
        expected_l = source.belief * (tau.belief * pi.belief) ** 3
        assert abs(result.belief - expected_l) < 1e-6
        assert result.belief < source.belief, "Chain must degrade compliance"

    def test_dual_regime_stricter_wins(self):
        """Strict GDPR + lenient HIPAA → composite near GDPR."""
        strict_gdpr = ComplianceOpinion(belief=0.3, disbelief=0.5, uncertainty=0.2, base_rate=0.3)
        lenient_hipaa = ComplianceOpinion(belief=0.9, disbelief=0.05, uncertainty=0.05, base_rate=0.7)

        result = dual_regime_composition(strict_gdpr, lenient_hipaa)
        assert result.belief < strict_gdpr.belief + ABS_TOL, (
            "Composite must not exceed stricter regime"
        )
        assert result.disbelief > strict_gdpr.disbelief - ABS_TOL, (
            "Composite violation must meet or exceed stricter regime"
        )

    def test_minimum_necessary_all_strong(self):
        """All three conditions strong → high composite."""
        strong = ComplianceOpinion(belief=0.95, disbelief=0.02, uncertainty=0.03, base_rate=0.5)
        result = minimum_necessary(strong, strong, strong)
        expected_l = 0.95 ** 3
        assert abs(result.belief - expected_l) < 1e-6

    def test_minimum_necessary_one_weak(self):
        """One weak condition dominates."""
        strong = ComplianceOpinion(belief=0.95, disbelief=0.02, uncertainty=0.03, base_rate=0.5)
        weak = ComplianceOpinion(belief=0.20, disbelief=0.60, uncertainty=0.20, base_rate=0.5)
        result = minimum_necessary(strong, strong, weak)
        assert result.belief < 0.20 + ABS_TOL, (
            f"l_MN={result.belief} should be pulled down by weak scope"
        )
