"""EH4 -- Comparison with Binary HIPAA Compliance Approaches.

Constructs 5 clinically motivated scenarios where binary compliance
assessment collapses distinct epistemic states that our algebra
distinguishes. For each scenario, computes:
  - Binary assessment (pass/fail or percentage)
  - Our algebra's opinion (l, v, u, a)
  - What decision each supports
  - Why the distinction matters clinically
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_EH4_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH4_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_JSONLDEX_ROOT = _REPO_ROOT.parent / "jsonld-ex"
_PKG_SRC = _JSONLDEX_ROOT / "packages" / "python" / "src"

for p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jsonld_ex.compliance_algebra import ComplianceOpinion, jurisdictional_meet
from jsonld_ex.confidence_decay import decay_opinion
from jsonld_ex.hipaa_compliance import (
    baa_trust_chain,
    dual_regime_composition,
)


def _opinion_dict(op: ComplianceOpinion) -> dict[str, float]:
    return {
        "l": round(op.belief, 6),
        "v": round(op.disbelief, 6),
        "u": round(op.uncertainty, 6),
        "a": round(op.base_rate, 6),
        "P": round(op.projected_probability(), 6),
    }


def scenario_1_conflicting_evidence() -> dict[str, Any]:
    """Two auditors: one finds compliance, one finds violations."""
    auditor_a = ComplianceOpinion(belief=0.85, disbelief=0.05, uncertainty=0.10, base_rate=0.5)
    auditor_b = ComplianceOpinion(belief=0.10, disbelief=0.80, uncertainty=0.10, base_rate=0.5)
    fused = jurisdictional_meet(auditor_a, auditor_b)
    return {
        "name": "Conflicting Audit Evidence",
        "context": "Two independent auditors assess same entity. A finds compliance, B finds violations.",
        "binary": "50% / INCONCLUSIVE",
        "algebra": _opinion_dict(fused),
        "distinction": (
            f"Binary hides conflict. Algebra: l={fused.belief:.3f}, v={fused.disbelief:.3f}, "
            f"u={fused.uncertainty:.3f} reveals strong conflicting evidence. "
            "Response: investigate discrepancy, not coin flip."
        ),
    }


def scenario_2_absence_of_evidence() -> dict[str, Any]:
    """New vendor with zero compliance history vs known violator."""
    vacuous = ComplianceOpinion(belief=0.0, disbelief=0.0, uncertainty=1.0, base_rate=0.5)
    known_violator = ComplianceOpinion(belief=0.0, disbelief=1.0, uncertainty=0.0, base_rate=0.5)
    return {
        "name": "New Vendor (No History)",
        "context": "New cloud vendor for PHI storage. No audit history, no breach history.",
        "binary": "FAIL (both new vendor and known violator)",
        "algebra_vendor": _opinion_dict(vacuous),
        "algebra_violator": _opinion_dict(known_violator),
        "distinction": (
            f"Binary: both get FAIL. Algebra: vendor (l=0, v=0, u=1, P={vacuous.projected_probability():.1f}) "
            f"vs violator (l=0, v=1, u=0, P={known_violator.projected_probability():.1f}). "
            "Vendor needs evidence gathering; violator needs blocking."
        ),
    }


def scenario_3_baa_chain() -> dict[str, Any]:
    """Hospital -> Lab -> Billing with mixed compliance levels."""
    hospital = ComplianceOpinion(belief=0.92, disbelief=0.03, uncertainty=0.05, base_rate=0.5)
    lab_tau = ComplianceOpinion(belief=0.75, disbelief=0.10, uncertainty=0.15, base_rate=0.5)
    lab_pi = ComplianceOpinion(belief=0.85, disbelief=0.05, uncertainty=0.10, base_rate=0.5)
    billing_tau = ComplianceOpinion(belief=0.50, disbelief=0.25, uncertainty=0.25, base_rate=0.5)
    billing_pi = ComplianceOpinion(belief=0.60, disbelief=0.20, uncertainty=0.20, base_rate=0.5)

    after_lab = baa_trust_chain(hospital, [(lab_tau, lab_pi)])
    after_billing = baa_trust_chain(hospital, [(lab_tau, lab_pi), (billing_tau, billing_pi)])

    deg_lab = (1 - after_lab.belief / hospital.belief) * 100
    deg_billing = (1 - after_billing.belief / hospital.belief) * 100

    return {
        "name": "BAA Chain (3 Organizations)",
        "context": "Hospital (strong) -> Lab (moderate) -> Billing (weak).",
        "binary": "FAIL (any weak link fails entire chain)",
        "algebra_hospital": _opinion_dict(hospital),
        "algebra_after_lab": _opinion_dict(after_lab),
        "algebra_after_billing": _opinion_dict(after_billing),
        "degradation_lab_pct": round(deg_lab, 1),
        "degradation_billing_pct": round(deg_billing, 1),
        "distinction": (
            f"Binary: FAIL with no guidance. Algebra: l degrades "
            f"{hospital.belief:.3f} -> {after_lab.belief:.3f} (lab) -> "
            f"{after_billing.belief:.3f} (billing). "
            f"Billing link is primary risk driver ({deg_billing:.0f}% total degradation)."
        ),
    }


def scenario_4_stale_assessment() -> dict[str, Any]:
    """2-year-old assessment with no reassessment."""
    fresh = ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=0.5)
    half_life = 365.0
    intervals = [
        (0, "Day 0 (fresh)"),
        (180, "6 months"),
        (365, "1 year"),
        (730, "2 years"),
        (1095, "3 years"),
    ]

    decay_curve = []
    for days, label in intervals:
        if days == 0:
            op = fresh
        else:
            decayed = decay_opinion(fresh, elapsed=float(days), half_life=half_life)
            op = ComplianceOpinion(
                belief=decayed.belief, disbelief=decayed.disbelief,
                uncertainty=decayed.uncertainty, base_rate=decayed.base_rate,
            )
        decay_curve.append({
            "period": label, "days": days,
            "l": round(op.belief, 4), "v": round(op.disbelief, 4),
            "u": round(op.uncertainty, 4),
        })

    return {
        "name": "Stale Assessment (2 Years Old)",
        "context": "Strong assessment 2 years ago (l=0.90). No reassessment since.",
        "binary": "PASS (unchanged, no expiration mechanism)",
        "decay_curve": decay_curve,
        "distinction": (
            f"Binary: PASS forever. Algebra: l decays "
            f"{decay_curve[0]['l']:.3f} -> {decay_curve[3]['l']:.3f} over 2 years, "
            f"u grows {decay_curve[0]['u']:.3f} -> {decay_curve[3]['u']:.3f}. "
            "Triggers reassessment when u exceeds threshold."
        ),
    }


def scenario_5_dual_regime() -> dict[str, Any]:
    """US-EU clinical trial: strong HIPAA, uncertain GDPR."""
    hipaa = ComplianceOpinion(belief=0.88, disbelief=0.04, uncertainty=0.08, base_rate=0.5)
    gdpr_uncertain = ComplianceOpinion(belief=0.40, disbelief=0.15, uncertainty=0.45, base_rate=0.3)
    gdpr_violation = ComplianceOpinion(belief=0.05, disbelief=0.90, uncertainty=0.05, base_rate=0.3)

    dual_uncertain = dual_regime_composition(hipaa, gdpr_uncertain)
    dual_violation = dual_regime_composition(hipaa, gdpr_violation)

    return {
        "name": "Multinational Clinical Trial (HIPAA + GDPR)",
        "context": "US hospital + EU partner. Strong HIPAA, uncertain GDPR.",
        "binary": "FAIL (both 'uncertain' and 'violation' get same FAIL)",
        "algebra_dual_uncertain": _opinion_dict(dual_uncertain),
        "algebra_dual_violation": _opinion_dict(dual_violation),
        "distinction": (
            f"Binary: both FAIL. Algebra: uncertain dual "
            f"(l={dual_uncertain.belief:.3f}, u={dual_uncertain.uncertainty:.3f}) vs "
            f"violation dual (l={dual_violation.belief:.3f}, v={dual_violation.disbelief:.3f}). "
            "Uncertain: proceed with monitoring. Violation: halt processing."
        ),
    }


def run_all() -> dict[str, Any]:
    out = Path(__file__).resolve().parent.parent / "results"
    out.mkdir(parents=True, exist_ok=True)

    print("=== EH4: Comparison with Binary HIPAA Compliance ===\n")

    scenarios = [
        scenario_1_conflicting_evidence(),
        scenario_2_absence_of_evidence(),
        scenario_3_baa_chain(),
        scenario_4_stale_assessment(),
        scenario_5_dual_regime(),
    ]

    for i, s in enumerate(scenarios, 1):
        print(f"--- Scenario {i}: {s['name']} ---")
        print(f"  Binary: {s['binary']}")
        if "algebra" in s:
            a = s["algebra"]
            print(f"  Algebra: l={a['l']:.3f}, v={a['v']:.3f}, u={a['u']:.3f}")
        print(f"  {s['distinction'][:100]}")
        print()

    # Summary table
    print("=" * 90)
    print("COMPARISON TABLE (Paper-Ready)")
    print("=" * 90)
    print(f"{'Scenario':<32s} | {'Binary':<20s} | {'Algebra (l,v,u)':<20s} | Key Insight")
    print("-" * 100)

    rows = [
        (scenarios[0]["name"], scenarios[0]["binary"],
         scenarios[0]["algebra"], "Conflict visible"),
        (scenarios[1]["name"], "FAIL (both cases)",
         scenarios[1]["algebra_vendor"], "Ignorance != violation"),
        (scenarios[2]["name"], "FAIL (any link)",
         scenarios[2]["algebra_after_billing"], "Degradation quantified"),
        (scenarios[3]["name"], "PASS (no decay)",
         {"l": scenarios[3]["decay_curve"][3]["l"],
          "v": scenarios[3]["decay_curve"][3]["v"],
          "u": scenarios[3]["decay_curve"][3]["u"]},
         "Staleness quantified"),
        (scenarios[4]["name"], "FAIL (both cases)",
         scenarios[4]["algebra_dual_uncertain"], "Uncertainty != violation"),
    ]

    for name, binary, alg, insight in rows:
        alg_str = f"({alg['l']:.3f},{alg['v']:.3f},{alg['u']:.3f})"
        print(f"{name:<32s} | {binary:<20s} | {alg_str:<20s} | {insight}")

    print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {"timestamp": timestamp, "scenarios": scenarios}

    for path in [out / "eh4_results.json", out / f"eh4_results_{timestamp}.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Saved: {path}")

    return results


if __name__ == "__main__":
    run_all()
