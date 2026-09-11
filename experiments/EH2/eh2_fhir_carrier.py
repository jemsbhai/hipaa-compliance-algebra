"""EH2 addendum -- FHIR R4 carrier exercise for compliance opinions.

Camera-ready addition for IEEE HealthCom 2026 (reviewer 2 asked how a
Subjective Logic opinion is represented inside FHIR R4).

For each Synthea FHIR R4 bundle (same 100 bundles as EH2 Phase A):
  1. Recompute the PHI Classification opinion of the Patient resource
     exactly as Phase A does (scan_patient_identifiers ->
     identifiers_to_opinions -> phi_classification).
  2. Attach that opinion to the Bundle (Bundle.meta.extension) and to
     the Patient resource (Patient.meta.extension) with
     fhir_attach_compliance_opinion(regime="HIPAA").
  3. Serialize the whole bundle to JSON text, parse it back, and read
     both opinions with fhir_read_compliance_opinion.
  4. Compare every component with the original opinion.

Hypotheses (falsifiable, decided by this script):
  H-C1  Round trip is exact: max |component_read - component_original| == 0
        for all bundles, at both attachment points, after JSON text.
  H-C2  Attachment is non-destructive: removing the added extension from
        the reloaded bundle yields a dict equal to the original bundle.

Also recorded (descriptive, no hypothesis): size of the extension in
compact JSON bytes, and the relative growth of the serialized bundle.

Outputs:
  experiments/results/eh2_fhir_carrier_results.json (+ timestamped archive)
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EH2_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH2_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_JSONLDEX_ROOT = _REPO_ROOT.parent / "jsonld-ex"
_PKG_SRC = _JSONLDEX_ROOT / "packages" / "python" / "src"

for p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT), str(_EH2_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jsonld_ex.hipaa_compliance import phi_classification
from jsonld_ex.fhir_interop import (
    FHIR_COMPLIANCE_EXTENSION_URL,
    fhir_attach_compliance_opinion,
    fhir_read_compliance_opinion,
)

from eh2_core import (
    PATIENT_IDENTIFIER_FIELDS,
    _SYNTHEA_DIR,
    identifiers_to_opinions,
    scan_patient_identifiers,
)


def load_bundles(max_bundles: int = 100) -> list[tuple[str, dict[str, Any]]]:
    """Load whole Synthea bundles (same file order and count as EH2)."""
    out: list[tuple[str, dict[str, Any]]] = []
    for bf in sorted(_SYNTHEA_DIR.glob("*.json"))[:max_bundles]:
        try:
            with open(bf, "r", encoding="utf-8") as f:
                out.append((bf.name, json.load(f)))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return out


def phi_opinion_for_patient(patient: dict[str, Any]):
    """Exactly the Phase A computation for one Patient resource."""
    presence = scan_patient_identifiers(patient)
    opinions = identifiers_to_opinions(presence)
    applicable = {
        k: v for k, v in opinions.items()
        if presence.get(k, False) or k in PATIENT_IDENTIFIER_FIELDS
    }
    return phi_classification(list(applicable.values()))


def _strip_compliance_extension(resource: dict[str, Any]) -> None:
    """Remove the compliance extension (and an empty meta we created) in place."""
    meta = resource.get("meta")
    if not isinstance(meta, dict):
        return
    kept = [
        e for e in meta.get("extension", [])
        if not (isinstance(e, dict) and e.get("url") == FHIR_COMPLIANCE_EXTENSION_URL)
    ]
    if kept:
        meta["extension"] = kept
    else:
        meta.pop("extension", None)
    if not meta:
        resource.pop("meta", None)


def run_all(max_bundles: int = 100) -> dict[str, Any]:
    out_dir = _EXPERIMENTS_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    assessed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    bundles = load_bundles(max_bundles)
    print(f"=== EH2 addendum: FHIR R4 compliance opinion carrier ===")
    print(f"  Bundles loaded: {len(bundles)}")

    per_bundle: list[dict[str, Any]] = []
    max_abs_diff = 0.0
    all_nondestructive = True
    ext_bytes: list[int] = []
    growth_pct: list[float] = []

    for name, bundle in bundles:
        patient_idx = next(
            (i for i, e in enumerate(bundle.get("entry", []))
             if e.get("resource", {}).get("resourceType") == "Patient"),
            None,
        )
        if patient_idx is None:
            per_bundle.append({"file": name, "skipped": "no Patient resource"})
            continue

        original = copy.deepcopy(bundle)
        patient = bundle["entry"][patient_idx]["resource"]
        op = phi_opinion_for_patient(patient)

        # Attach at both levels: Bundle.meta and Patient.meta
        annotated = fhir_attach_compliance_opinion(bundle, op, regime="HIPAA", assessed_at=assessed_at)
        annotated["entry"][patient_idx]["resource"] = fhir_attach_compliance_opinion(
            annotated["entry"][patient_idx]["resource"], op, regime="HIPAA", assessed_at=assessed_at
        )

        # JSON text round trip of the whole bundle
        text = json.dumps(annotated)
        reloaded = json.loads(text)

        diffs: dict[str, float] = {}
        for label, res in (("bundle", reloaded), ("patient", reloaded["entry"][patient_idx]["resource"])):
            carrier = fhir_read_compliance_opinion(res)
            assert carrier is not None, f"{name}: no carrier read back at {label}"
            got = carrier.opinion
            diffs[label] = max(
                abs(got.belief - op.belief),
                abs(got.disbelief - op.disbelief),
                abs(got.uncertainty - op.uncertainty),
                abs(got.base_rate - op.base_rate),
            )
            assert carrier.regime == "HIPAA", f"{name}: regime not preserved at {label}"
            assert carrier.assessed_at == assessed_at, f"{name}: assessedAt not preserved at {label}"
        bundle_max = max(diffs.values())
        max_abs_diff = max(max_abs_diff, bundle_max)

        # Non-destructiveness: strip what we added and compare to the original
        stripped = copy.deepcopy(reloaded)
        _strip_compliance_extension(stripped)
        _strip_compliance_extension(stripped["entry"][patient_idx]["resource"])
        nondestructive = stripped == original
        all_nondestructive = all_nondestructive and nondestructive

        ext = next(e for e in annotated["meta"]["extension"] if e.get("url") == FHIR_COMPLIANCE_EXTENSION_URL)
        ext_size = len(json.dumps(ext, separators=(",", ":")).encode("utf-8"))
        before = len(json.dumps(original, separators=(",", ":")).encode("utf-8"))
        after = len(json.dumps(annotated, separators=(",", ":")).encode("utf-8"))
        ext_bytes.append(ext_size)
        growth_pct.append(100.0 * (after - before) / before)

        per_bundle.append({
            "file": name,
            "patient_id": patient.get("id"),
            "phi_opinion": [op.belief, op.disbelief, op.uncertainty, op.base_rate],
            "max_abs_diff_bundle_level": diffs["bundle"],
            "max_abs_diff_patient_level": diffs["patient"],
            "nondestructive": nondestructive,
            "extension_bytes": ext_size,
            "bundle_bytes_before": before,
            "bundle_bytes_after": after,
        })

    n_ok = sum(1 for r in per_bundle if "phi_opinion" in r)
    results = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "assessed_at": assessed_at,
        "extension_url": FHIR_COMPLIANCE_EXTENSION_URL,
        "n_bundles_loaded": len(bundles),
        "n_bundles_annotated": n_ok,
        "max_abs_diff_all": max_abs_diff,
        "extension_bytes_min": min(ext_bytes) if ext_bytes else None,
        "extension_bytes_max": max(ext_bytes) if ext_bytes else None,
        "bundle_growth_pct_max": max(growth_pct) if growth_pct else None,
        "hypothesis_results": {
            "H_C1_round_trip_exact": max_abs_diff == 0.0 and n_ok == len(bundles),
            "H_C2_nondestructive": all_nondestructive and n_ok == len(bundles),
        },
        "per_bundle": per_bundle,
    }

    print(f"  Bundles annotated: {n_ok}/{len(bundles)}")
    print(f"  Max |read - original| over all components, both levels: {max_abs_diff:.3e}")
    print(f"  Extension size (compact JSON): {results['extension_bytes_min']} to {results['extension_bytes_max']} bytes")
    print(f"  Max bundle growth: {results['bundle_growth_pct_max']:.4f}%")
    for h, v in results["hypothesis_results"].items():
        print(f"  {h}: {'ACCEPTED' if v else 'REJECTED'}")

    for path in [out_dir / "eh2_fhir_carrier_results.json",
                 out_dir / f"eh2_fhir_carrier_results_{results['timestamp']}.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved: {path}")
    return results


if __name__ == "__main__":
    run_all()
