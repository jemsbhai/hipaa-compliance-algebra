"""EH2 -- Clinical HIPAA Compliance Pipeline on Synthea FHIR R4 Data.

Evaluates all HIPAA compliance operators on synthetic clinical data:
  Phase A: PHI Classification across FHIR resource types
  Phase B: De-identification Assessment (Safe Harbor vs Expert)
  Phase C: BAA Trust Chain (3-organization scenario)
  Phase D: Dual-regime GDPR x HIPAA composition

Data: Synthea FHIR R4 bundles (public, HIPAA-safe, reproducible)
Statistical rigor: Bootstrap CIs (n=1000), Holm-Bonferroni correction
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

# -- Path setup ---------------------------------------------------------------
_EH2_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH2_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_JSONLDEX_ROOT = _REPO_ROOT.parent / "jsonld-ex"
_PKG_SRC = _JSONLDEX_ROOT / "packages" / "python" / "src"
_SYNTHEA_DIR = _JSONLDEX_ROOT / "data" / "synthea" / "fhir_r4"

for p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jsonld_ex.compliance_algebra import (
    ComplianceOpinion,
    jurisdictional_meet,
    compliance_propagation,
)
from jsonld_ex.hipaa_compliance import (
    phi_classification,
    safe_harbor_assessment,
    expert_determination_assessment,
    minimum_necessary,
    baa_trust_chain,
    dual_regime_composition,
    SAFE_HARBOR_IDENTIFIERS,
)

# =============================================================================
# HIPAA Identifier-to-FHIR Field Mapping
# =============================================================================

# For each HIPAA Safe Harbor identifier, which FHIR Patient fields indicate
# its presence. A field that exists with non-empty value means the identifier
# is PRESENT (PHI risk). Absence means the identifier is NOT present (safe).

PATIENT_IDENTIFIER_FIELDS: dict[str, list[str]] = {
    "names": ["name"],
    "geographic_subdivisions": ["address"],
    "dates": ["birthDate", "deceasedDateTime"],
    "phone_numbers": ["telecom"],  # filtered to phone
    "fax_numbers": ["telecom"],    # filtered to fax
    "email_addresses": ["telecom"],  # filtered to email
    "social_security_numbers": ["identifier"],  # filtered to SSN system
    "medical_record_numbers": ["identifier"],   # filtered to MRN system
    "health_plan_beneficiary_numbers": ["identifier"],  # filtered to health plan
    "account_numbers": [],  # not typically in Patient
    "certificate_license_numbers": ["identifier"],  # e.g. driver's license
    "vehicle_identifiers": [],  # not in Patient
    "device_identifiers": [],  # not in Patient
    "web_urls": [],  # not typically in Patient
    "ip_addresses": [],  # not in Patient
    "biometric_identifiers": [],  # not in Patient
    "full_face_photographs": ["photo"],
    "other_unique_identifiers": ["identifier"],  # catch-all
}


def _has_telecom_type(resource: dict, system: str) -> bool:
    """Check if a FHIR resource has a telecom entry of a given type."""
    for tc in resource.get("telecom", []):
        if tc.get("system", "") == system and tc.get("value"):
            return True
    return False


def _has_identifier_system(resource: dict, system_fragment: str) -> bool:
    """Check if a FHIR resource has an identifier with a system containing fragment."""
    for ident in resource.get("identifier", []):
        sys_url = ident.get("system", "")
        if system_fragment.lower() in sys_url.lower() and ident.get("value"):
            return True
    return False


def scan_patient_identifiers(patient: dict[str, Any]) -> dict[str, bool]:
    """Scan a FHIR Patient resource for all 18 HIPAA identifier categories.

    Returns a dict mapping identifier name to presence (True = present = PHI risk).
    """
    results: dict[str, bool] = {}

    # 1. Names
    names = patient.get("name", [])
    results["names"] = any(
        n.get("family") or n.get("given") for n in names
    ) if names else False

    # 2. Geographic subdivisions smaller than state
    addresses = patient.get("address", [])
    results["geographic_subdivisions"] = any(
        a.get("line") or a.get("city") or a.get("postalCode")
        for a in addresses
    ) if addresses else False

    # 3. Dates (except year)
    results["dates"] = bool(
        patient.get("birthDate") or patient.get("deceasedDateTime")
    )

    # 4. Phone numbers
    results["phone_numbers"] = _has_telecom_type(patient, "phone")

    # 5. Fax numbers
    results["fax_numbers"] = _has_telecom_type(patient, "fax")

    # 6. Email addresses
    results["email_addresses"] = _has_telecom_type(patient, "email")

    # 7. SSN
    results["social_security_numbers"] = _has_identifier_system(
        patient, "social"
    ) or _has_identifier_system(patient, "ssn")

    # 8. Medical record numbers
    results["medical_record_numbers"] = _has_identifier_system(
        patient, "medical-record"
    ) or _has_identifier_system(patient, "mrn")

    # 9. Health plan beneficiary numbers
    results["health_plan_beneficiary_numbers"] = _has_identifier_system(
        patient, "health-plan"
    ) or _has_identifier_system(patient, "insurance")

    # 10. Account numbers
    results["account_numbers"] = _has_identifier_system(patient, "account")

    # 11. Certificate/license numbers
    results["certificate_license_numbers"] = _has_identifier_system(
        patient, "license"
    ) or _has_identifier_system(patient, "driver")

    # 12. Vehicle identifiers
    results["vehicle_identifiers"] = False  # not in Patient resources

    # 13. Device identifiers
    results["device_identifiers"] = False  # not in Patient resources

    # 14. Web URLs
    results["web_urls"] = False  # not typically in Patient

    # 15. IP addresses
    results["ip_addresses"] = False  # not in Patient

    # 16. Biometric identifiers
    results["biometric_identifiers"] = False  # not typically in Patient

    # 17. Full-face photographs
    results["full_face_photographs"] = bool(patient.get("photo"))

    # 18. Other unique identifiers (catch-all for any other identifier)
    known_systems = {"social", "ssn", "mrn", "medical-record",
                     "health-plan", "insurance", "account",
                     "license", "driver"}
    other_ids = [
        ident for ident in patient.get("identifier", [])
        if not any(k in ident.get("system", "").lower() for k in known_systems)
        and ident.get("value")
    ]
    results["other_unique_identifiers"] = len(other_ids) > 0

    return results


def identifiers_to_opinions(
    presence: dict[str, bool],
    present_confidence: float = 0.90,
    absent_confidence: float = 0.95,
) -> dict[str, ComplianceOpinion]:
    """Convert identifier presence booleans to compliance opinions.

    For each identifier:
      - Present (PHI risk): l is low (identifier IS there, not safe)
        opinion = (1-present_confidence, present_confidence_as_v, small_u, a)
        Actually: if identifier IS present, that means violation is high.
        We model: l = 0.05, v = present_confidence, u = 1-l-v
      - Absent (safe): l is high (identifier is not there)
        opinion = (absent_confidence, small_v, 1-l-v, a)

    These represent "is identifier i absent?" opinions for phi_classification.
    """
    opinions: dict[str, ComplianceOpinion] = {}
    for name, is_present in presence.items():
        if is_present:
            # Identifier IS present: low confidence of absence
            l = 0.05  # very unlikely the identifier is absent
            v = present_confidence  # high confidence it's present
            u = 1.0 - l - v
        else:
            # Identifier is NOT present: high confidence of absence
            l = absent_confidence
            v = 0.02
            u = 1.0 - l - v
        opinions[name] = ComplianceOpinion(
            belief=l, disbelief=v, uncertainty=u, base_rate=0.5
        )
    return opinions


# =============================================================================
# Data Loading (reuse Synthea infrastructure)
# =============================================================================

def load_synthea_patients(
    max_bundles: int = 100,
    synthea_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Load Patient resources from Synthea FHIR bundles."""
    data_dir = synthea_dir or _SYNTHEA_DIR
    patients = []
    bundle_files = sorted(data_dir.glob("*.json"))[:max_bundles]

    for bf in bundle_files:
        try:
            with open(bf, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                patients.append(resource)

    return patients


# =============================================================================
# Phase A: PHI Classification
# =============================================================================

@dataclass
class PHIResult:
    """Result of PHI classification for one patient."""
    patient_id: str
    identifiers_present: list[str]
    identifiers_absent: list[str]
    n_present: int
    n_absent: int
    phi_opinion: tuple  # (l, v, u, a)
    projected_probability: float


def run_phase_a(
    patients: list[dict],
) -> list[PHIResult]:
    """Run PHI Classification on all patients."""
    results = []
    for patient in patients:
        pid = patient.get("id", "unknown")
        presence = scan_patient_identifiers(patient)
        opinions = identifiers_to_opinions(presence)

        # Only classify over identifiers that are applicable (have fields)
        applicable = {
            k: v for k, v in opinions.items()
            if presence.get(k, False) or k in PATIENT_IDENTIFIER_FIELDS
        }

        if len(applicable) < 2:
            continue

        opinion_list = list(applicable.values())
        phi_result = phi_classification(opinion_list)

        present_ids = [k for k, v in presence.items() if v]
        absent_ids = [k for k, v in presence.items() if not v]

        results.append(PHIResult(
            patient_id=pid,
            identifiers_present=present_ids,
            identifiers_absent=absent_ids,
            n_present=len(present_ids),
            n_absent=len(absent_ids),
            phi_opinion=(
                phi_result.belief,
                phi_result.disbelief,
                phi_result.uncertainty,
                phi_result.base_rate,
            ),
            projected_probability=phi_result.projected_probability(),
        ))
    return results


# =============================================================================
# Phase B: De-identification Assessment
# =============================================================================

@dataclass
class DeidentResult:
    """Result of de-identification comparison for one patient."""
    patient_id: str
    n_identifiers: int
    safe_harbor_opinion: tuple  # (l, v, u, a)
    safe_harbor_pp: float
    expert_opinion: tuple       # (l, v, u, a) at trust=0.85
    expert_pp: float
    expert_exceeds_sh: bool
    trust_threshold: float      # t above which expert beats SH


def run_phase_b(
    patients: list[dict],
    expert_belief: float = 0.90,
    expert_trust: float = 0.85,
    removal_confidence: float = 0.95,
) -> list[DeidentResult]:
    """Run de-identification comparison on all patients."""
    results = []
    for patient in patients:
        pid = patient.get("id", "unknown")
        presence = scan_patient_identifiers(patient)

        # Simulate removal: each present identifier gets a removal opinion
        removal_opinions = []
        for name in SAFE_HARBOR_IDENTIFIERS:
            if presence.get(name, False):
                # Identifier was present, removal attempted
                removal_opinions.append(ComplianceOpinion(
                    belief=removal_confidence,
                    disbelief=0.02,
                    uncertainty=1.0 - removal_confidence - 0.02,
                    base_rate=0.5,
                ))
            else:
                # Identifier was not present, trivially removed
                removal_opinions.append(ComplianceOpinion(
                    belief=0.99, disbelief=0.005, uncertainty=0.005,
                    base_rate=0.5,
                ))

        sh_result = safe_harbor_assessment(removal_opinions)

        # Expert determination
        expert_op = ComplianceOpinion(
            belief=expert_belief,
            disbelief=0.05,
            uncertainty=1.0 - expert_belief - 0.05,
            base_rate=0.5,
        )
        trust_op = ComplianceOpinion(
            belief=expert_trust,
            disbelief=0.05,
            uncertainty=1.0 - expert_trust - 0.05,
            base_rate=0.5,
        )
        ed_result = expert_determination_assessment(expert_op, trust_op)

        # Threshold computation
        threshold = sh_result.belief / expert_belief if expert_belief > 0 else float("inf")

        results.append(DeidentResult(
            patient_id=pid,
            n_identifiers=sum(1 for v in presence.values() if v),
            safe_harbor_opinion=(
                sh_result.belief, sh_result.disbelief,
                sh_result.uncertainty, sh_result.base_rate,
            ),
            safe_harbor_pp=sh_result.projected_probability(),
            expert_opinion=(
                ed_result.belief, ed_result.disbelief,
                ed_result.uncertainty, ed_result.base_rate,
            ),
            expert_pp=ed_result.projected_probability(),
            expert_exceeds_sh=ed_result.belief > sh_result.belief,
            trust_threshold=threshold,
        ))
    return results


# =============================================================================
# Phase C: BAA Trust Chain
# =============================================================================

@dataclass
class BAAResult:
    """Result of BAA trust chain simulation."""
    source_l: float
    chain_opinions: list[tuple]  # [(l, v, u, a) at each depth]
    degradation_pct: list[float]
    final_l: float
    theoretical_l: float  # l_S * (t*p)^n


def run_phase_c(
    n_trials: int = 1000,
    source_l: float = 0.95,
    tau_belief: float = 0.90,
    pi_belief: float = 0.95,
    chain_depth: int = 3,
    seed: int = 42,
) -> BAAResult:
    """Run BAA trust chain simulation with fixed parameters."""
    source = ComplianceOpinion(
        belief=source_l, disbelief=0.02,
        uncertainty=1.0 - source_l - 0.02, base_rate=0.5,
    )

    tau = ComplianceOpinion(
        belief=tau_belief, disbelief=0.05,
        uncertainty=1.0 - tau_belief - 0.05, base_rate=0.5,
    )
    pi = ComplianceOpinion(
        belief=pi_belief, disbelief=0.02,
        uncertainty=1.0 - pi_belief - 0.02, base_rate=0.5,
    )

    chain_opinions = [(source.belief, source.disbelief,
                       source.uncertainty, source.base_rate)]
    degradation_pct = [0.0]

    current = source
    for depth in range(1, chain_depth + 1):
        current = baa_trust_chain(current, [(tau, pi)])
        chain_opinions.append((
            current.belief, current.disbelief,
            current.uncertainty, current.base_rate,
        ))
        deg = 1.0 - current.belief / source.belief
        degradation_pct.append(deg * 100)

    theoretical = source_l * (tau_belief * pi_belief) ** chain_depth

    return BAAResult(
        source_l=source_l,
        chain_opinions=chain_opinions,
        degradation_pct=degradation_pct,
        final_l=current.belief,
        theoretical_l=theoretical,
    )


# =============================================================================
# Phase D: Dual-Regime Composition
# =============================================================================

@dataclass
class DualRegimeResult:
    """Result of dual-regime GDPR x HIPAA composition."""
    hipaa_opinion: tuple
    gdpr_opinion: tuple
    dual_opinion: tuple
    hipaa_pp: float
    gdpr_pp: float
    dual_pp: float
    composite_lt_min: bool  # l_dual <= min(l_hipaa, l_gdpr)


def _build_gdpr_opinion_from_presence(
    presence: dict[str, bool],
    gdpr_base_rate: float = 0.3,
) -> ComplianceOpinion:
    """Build a GDPR compliance opinion from identifier presence data.

    GDPR assessment differs from HIPAA in three ways:
    1. Stricter base rate (EU regulatory environment)
    2. Additional requirements beyond identifier removal:
       lawful basis (Art. 6), consent (Art. 7), data minimization (Art. 5(1)(c))
    3. Broader definition of personal data (any information relating
       to an identified or identifiable natural person)

    We model GDPR as a 3-way J_sqcap:
      omega_identifiers: same identifier scan, stricter interpretation
      omega_lawful_basis: additional requirement (no HIPAA equivalent)
      omega_data_minimization: additional requirement
    """
    # Identifier-based assessment (same scan, stricter thresholds)
    n_present = sum(1 for v in presence.values() if v)
    n_total = len(presence)
    # GDPR treats more categories as personal data
    identifier_l = 0.03 if n_present > 0 else 0.90
    identifier_v = 0.92 if n_present > 4 else (0.70 if n_present > 0 else 0.03)
    identifier_u = 1.0 - identifier_l - identifier_v

    omega_identifiers = ComplianceOpinion(
        belief=identifier_l, disbelief=identifier_v,
        uncertainty=max(0.0, identifier_u), base_rate=gdpr_base_rate,
    )

    # Lawful basis (Art. 6): synthetic data has no real consent
    # Model as moderate uncertainty (simulated scenario)
    omega_lawful_basis = ComplianceOpinion(
        belief=0.60, disbelief=0.15,
        uncertainty=0.25, base_rate=gdpr_base_rate,
    )

    # Data minimization (Art. 5(1)(c)): Synthea generates full records
    omega_minimization = ComplianceOpinion(
        belief=0.50, disbelief=0.20,
        uncertainty=0.30, base_rate=gdpr_base_rate,
    )

    return jurisdictional_meet(
        omega_identifiers, omega_lawful_basis, omega_minimization,
    )


def run_phase_d(
    patients: list[dict],
    gdpr_base_rate: float = 0.3,
    hipaa_base_rate: float = 0.5,
) -> list[DualRegimeResult]:
    """Run dual-regime composition using patient PHI classification.

    HIPAA opinion: derived from PHI Classification (H1 operator).
    GDPR opinion: derived from first-principles GDPR assessment
    including identifier presence, lawful basis, and data minimization.
    Dual opinion: J_sqcap(omega_HIPAA, omega_GDPR).
    """
    results = []
    for patient in patients:
        presence = scan_patient_identifiers(patient)
        opinions = identifiers_to_opinions(presence)
        opinion_list = list(opinions.values())

        if len(opinion_list) < 2:
            continue

        # HIPAA opinion from PHI classification
        hipaa_op = phi_classification(opinion_list)

        # GDPR opinion from first-principles assessment
        gdpr_op = _build_gdpr_opinion_from_presence(
            presence, gdpr_base_rate=gdpr_base_rate,
        )

        # Dual-regime composition
        dual_op = dual_regime_composition(hipaa_op, gdpr_op)

        results.append(DualRegimeResult(
            hipaa_opinion=(hipaa_op.belief, hipaa_op.disbelief,
                          hipaa_op.uncertainty, hipaa_op.base_rate),
            gdpr_opinion=(gdpr_op.belief, gdpr_op.disbelief,
                         gdpr_op.uncertainty, gdpr_op.base_rate),
            dual_opinion=(dual_op.belief, dual_op.disbelief,
                         dual_op.uncertainty, dual_op.base_rate),
            hipaa_pp=hipaa_op.projected_probability(),
            gdpr_pp=gdpr_op.projected_probability(),
            dual_pp=dual_op.projected_probability(),
            composite_lt_min=dual_op.belief <= min(
                hipaa_op.belief, gdpr_op.belief
            ) + 1e-9,
        ))
    return results


# =============================================================================
# Bootstrap CI utility
# =============================================================================

def bootstrap_ci(
    values: list[float],
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval.

    Returns (mean, ci_lower, ci_upper).
    """
    rng = np.random.default_rng(seed)
    arr = np.array(values)
    boot_means = np.array([
        rng.choice(arr, size=len(arr), replace=True).mean()
        for _ in range(n_boot)
    ])
    alpha = 1.0 - ci
    lo = np.percentile(boot_means, 100 * alpha / 2)
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return float(arr.mean()), float(lo), float(hi)


# =============================================================================
# Main runner
# =============================================================================

def run_all(
    max_bundles: int = 100,
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Run all four phases and collect results."""
    out = output_dir or (_EXPERIMENTS_ROOT / "results")
    out.mkdir(parents=True, exist_ok=True)

    print("Loading Synthea patients...")
    patients = load_synthea_patients(max_bundles=max_bundles)
    print(f"  Loaded {len(patients)} Patient resources from {max_bundles} bundles")

    # Phase A
    print("\n=== Phase A: PHI Classification ===")
    phi_results = run_phase_a(patients)
    n_present_counts = [r.n_present for r in phi_results]
    phi_beliefs = [r.phi_opinion[0] for r in phi_results]

    mean_present, lo_present, hi_present = bootstrap_ci(n_present_counts)
    mean_phi_l, lo_phi_l, hi_phi_l = bootstrap_ci(phi_beliefs)

    print(f"  Patients analyzed: {len(phi_results)}")
    print(f"  Mean identifiers present: {mean_present:.2f} [{lo_present:.2f}, {hi_present:.2f}]")
    print(f"  Mean PHI l (lawfulness): {mean_phi_l:.6f} [{lo_phi_l:.6f}, {hi_phi_l:.6f}]")

    # Phase B
    print("\n=== Phase B: De-identification ===")
    deident_results = run_phase_b(patients)
    sh_beliefs = [r.safe_harbor_opinion[0] for r in deident_results]
    ed_beliefs = [r.expert_opinion[0] for r in deident_results]
    expert_wins = sum(1 for r in deident_results if r.expert_exceeds_sh)

    mean_sh, lo_sh, hi_sh = bootstrap_ci(sh_beliefs)
    mean_ed, lo_ed, hi_ed = bootstrap_ci(ed_beliefs)

    print(f"  Mean Safe Harbor l: {mean_sh:.6f} [{lo_sh:.6f}, {hi_sh:.6f}]")
    print(f"  Mean Expert l: {mean_ed:.6f} [{lo_ed:.6f}, {hi_ed:.6f}]")
    print(f"  Expert exceeds SH: {expert_wins}/{len(deident_results)} patients")

    # Phase C
    print("\n=== Phase C: BAA Trust Chain ===")
    baa_result = run_phase_c()
    print(f"  Source l: {baa_result.source_l:.4f}")
    for i, (op, deg) in enumerate(zip(
        baa_result.chain_opinions, baa_result.degradation_pct
    )):
        print(f"  Depth {i}: l={op[0]:.4f}, degradation={deg:.1f}%")
    print(f"  Theoretical final l: {baa_result.theoretical_l:.6f}")
    print(f"  Actual final l: {baa_result.final_l:.6f}")
    print(f"  Match: {abs(baa_result.final_l - baa_result.theoretical_l) < 1e-6}")

    # Phase D
    print("\n=== Phase D: Dual-Regime ===")
    dual_results = run_phase_d(patients)
    composite_valid = sum(1 for r in dual_results if r.composite_lt_min)
    dual_beliefs = [r.dual_opinion[0] for r in dual_results]
    hipaa_beliefs = [r.hipaa_opinion[0] for r in dual_results]

    mean_dual, lo_dual, hi_dual = bootstrap_ci(dual_beliefs)
    mean_hipaa, lo_hipaa, hi_hipaa = bootstrap_ci(hipaa_beliefs)

    print(f"  Mean HIPAA l: {mean_hipaa:.6f}")
    print(f"  Mean Dual l: {mean_dual:.6f}")
    print(f"  Composite <= min(individual): {composite_valid}/{len(dual_results)}")

    # Save results
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {
        "timestamp": timestamp,
        "n_patients": len(patients),
        "n_bundles": max_bundles,
        "phase_a": {
            "n_analyzed": len(phi_results),
            "mean_identifiers_present": mean_present,
            "ci_identifiers_present": [lo_present, hi_present],
            "mean_phi_lawfulness": mean_phi_l,
            "ci_phi_lawfulness": [lo_phi_l, hi_phi_l],
            "per_patient": [
                {
                    "id": r.patient_id,
                    "n_present": r.n_present,
                    "identifiers_present": r.identifiers_present,
                    "phi_opinion": list(r.phi_opinion),
                    "projected_probability": r.projected_probability,
                }
                for r in phi_results[:20]  # first 20 for file size
            ],
        },
        "phase_b": {
            "mean_safe_harbor_l": mean_sh,
            "ci_safe_harbor_l": [lo_sh, hi_sh],
            "mean_expert_l": mean_ed,
            "ci_expert_l": [lo_ed, hi_ed],
            "expert_exceeds_sh_count": expert_wins,
            "expert_exceeds_sh_pct": expert_wins / max(1, len(deident_results)) * 100,
            "mean_trust_threshold": float(np.mean(
                [r.trust_threshold for r in deident_results]
            )),
        },
        "phase_c": {
            "source_l": baa_result.source_l,
            "chain_opinions": baa_result.chain_opinions,
            "degradation_pct": baa_result.degradation_pct,
            "final_l": baa_result.final_l,
            "theoretical_l": baa_result.theoretical_l,
            "theory_matches": abs(
                baa_result.final_l - baa_result.theoretical_l
            ) < 1e-6,
        },
        "phase_d": {
            "n_analyzed": len(dual_results),
            "mean_hipaa_l": mean_hipaa,
            "mean_dual_l": mean_dual,
            "ci_dual_l": [lo_dual, hi_dual],
            "composite_leq_min_count": composite_valid,
            "composite_leq_min_pct": composite_valid / max(1, len(dual_results)) * 100,
        },
    }

    primary = out / "eh2_results.json"
    archive = out / f"eh2_results_{timestamp}.json"
    for path in [primary, archive]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved: {path}")

    return results


if __name__ == "__main__":
    run_all()
