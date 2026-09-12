"""EH4 addendum -- traceability run for camera-ready numbers.

Every number in the paper must trace to a saved result. Two spots in the
accepted paper were hand arithmetic; this script computes them through the
implemented operators and saves them.

  A. Table VI (temporal decay): (l, v, u) and P = l + a u at 0, 180, 365,
     730, 1095 days for the fresh assessment (0.90, 0.05, 0.05, a = 0.5),
     half-life 365 days, plus the first day on which P < 0.70.
  B. Workflow Step 3 (BAA chain): source = Phase B Safe Harbor opinion of the
     Synthea profile (l = 0.95^6 0.99^12), link 1 (t = 0.90, p = 0.95),
     link 2 (t = 0.75, p = 0.85); l_D1, l_D2, and the Step 1 degradation.

Hypotheses (falsifiable):
  H-A1  Rounded to three decimals the rows equal the camera-ready Table VI:
        (0.900, 0.050, 0.050, 0.925), (0.639, 0.036, 0.325, 0.802),
        (0.450, 0.025, 0.525, 0.713), (0.225, 0.013, 0.762, 0.606),
        (0.113, 0.006, 0.881, 0.553); the 0.70 crossing lies in (365, 730) days.
        RESULT OF FIRST RUN (2026-09-11): REJECTED at the 730-day row only,
        because u = 0.7625 exactly is a rounding tie: Python's round() gives
        0.763 on the binary double, the paper prints 0.762 (half-even, and
        the row sums to 1.000). Kept as stated; see H-A1b.
  H-A1b (post hoc, added after the first run, labeled as such): every printed
        Table VI value lies within 0.0005 (half a unit of the last printed
        digit) of the computed value, and the crossing lies in (365, 730).
  H-A2  l_D1 rounds to 0.557 (14.5% degradation) and l_D2 to 0.355.

Output: results/eh4_addendum_results.json (+ timestamped archive).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_EH4_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH4_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_PKG_SRC = _REPO_ROOT.parent / "jsonld-ex" / "packages" / "python" / "src"
for _p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from jsonld_ex.compliance_algebra import ComplianceOpinion  # noqa: E402
from jsonld_ex.confidence_decay import decay_opinion  # noqa: E402
from jsonld_ex.hipaa_compliance import baa_trust_chain, safe_harbor_assessment  # noqa: E402

from EH5.eh5_core import removal_opinions  # noqa: E402

_RESULTS_DIR = _EXPERIMENTS_ROOT / "results"

EXPECTED_TABLE_VI = {
    0: (0.900, 0.050, 0.050, 0.925),
    180: (0.639, 0.036, 0.325, 0.802),
    365: (0.450, 0.025, 0.525, 0.713),
    730: (0.225, 0.013, 0.762, 0.606),
    1095: (0.113, 0.006, 0.881, 0.553),
}


def table_vi_rows() -> dict:
    fresh = ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=0.5)
    rows = {}
    for days in EXPECTED_TABLE_VI:
        op = decay_opinion(fresh, elapsed=float(days), half_life=365.0)
        rows[days] = {
            "l": op.belief, "v": op.disbelief, "u": op.uncertainty, "a": op.base_rate,
            "P": op.projected_probability(),
        }
    crossing_day = None
    for day in range(0, 2000):
        if decay_opinion(fresh, elapsed=float(day), half_life=365.0).projected_probability() < 0.70:
            crossing_day = day
            break
    return {"rows": rows, "first_day_P_below_0_70": crossing_day}


def step3_chain() -> dict:
    source = safe_harbor_assessment(removal_opinions(6, 0.95, 0.99))
    link1 = (ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=0.5),
             ComplianceOpinion(belief=0.95, disbelief=0.03, uncertainty=0.02, base_rate=0.5))
    link2 = (ComplianceOpinion(belief=0.75, disbelief=0.15, uncertainty=0.10, base_rate=0.5),
             ComplianceOpinion(belief=0.85, disbelief=0.10, uncertainty=0.05, base_rate=0.5))
    d1 = baa_trust_chain(source, [link1])
    d2 = baa_trust_chain(source, [link1, link2])
    return {
        "l_source": source.belief,
        "l_D1": d1.belief, "degradation_D1_pct": 100.0 * (1.0 - d1.belief / source.belief),
        "l_D2": d2.belief, "degradation_D2_pct": 100.0 * (1.0 - d2.belief / source.belief),
    }


def run_all() -> dict:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== EH4 addendum: traceability of Table VI and workflow Step 3 ===")
    tv = table_vi_rows()
    crossing_ok = tv["first_day_P_below_0_70"] is not None and 365 < tv["first_day_P_below_0_70"] < 730
    h_a1 = crossing_ok
    h_a1b = crossing_ok
    for days, exp in EXPECTED_TABLE_VI.items():
        r = tv["rows"][days]
        got = (round(r["l"], 3), round(r["v"], 3), round(r["u"], 3), round(r["P"], 3))
        ok = got == exp
        within = all(abs(x - y) <= 0.0005 + 1e-12 for x, y in zip((r["l"], r["v"], r["u"], r["P"]), exp))
        h_a1 = h_a1 and ok
        h_a1b = h_a1b and within
        print(f"  day {days:5d}: l={r['l']:.4f} v={r['v']:.4f} u={r['u']:.4f} P={r['P']:.4f} -> {got} {'OK' if ok else 'ROUNDING TIE vs ' + str(exp)}; within 0.0005: {within}")
    print(f"  first day with P < 0.70: {tv['first_day_P_below_0_70']}")

    s3 = step3_chain()
    h_a2 = round(s3["l_D1"], 3) == 0.557 and round(s3["degradation_D1_pct"], 1) == 14.5 and round(s3["l_D2"], 3) == 0.355
    print(f"  Step 3: l_source={s3['l_source']:.4f} l_D1={s3['l_D1']:.4f} ({s3['degradation_D1_pct']:.1f}% degradation) l_D2={s3['l_D2']:.4f}")

    results = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "table_vi": tv,
        "step3_chain": s3,
        "hypothesis_results": {"H_A1": bool(h_a1), "H_A1b_post_hoc": bool(h_a1b), "H_A2": bool(h_a2)},
    }
    for h, v in results["hypothesis_results"].items():
        print(f"  {h}: {'ACCEPTED' if v else 'REJECTED'}")
    for path in [_RESULTS_DIR / "eh4_addendum_results.json",
                 _RESULTS_DIR / f"eh4_addendum_results_{results['timestamp']}.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved: {path}")
    return results


if __name__ == "__main__":
    run_all()
