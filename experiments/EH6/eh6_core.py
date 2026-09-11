"""EH6 -- Two-auditor scenario under three combination rules.

Camera-ready addition for IEEE HealthCom 2026 (both reviewers asked for a
comparison with other uncertainty-aware methods). The two auditor opinions
are those of EH4 scenario 1: A = (0.85, 0.05, 0.10), B = (0.10, 0.80, 0.10).

Rules compared on the same two inputs:
  1. Jurisdictional Meet (the paper's operator; EH4 result (0.085, 0.810, 0.105)).
  2. Dempster's rule of combination on the binary frame {T, F}, with
     m({T}) = l, m({F}) = v, m(Theta) = u. Conflict mass
     K = m_A(T) m_B(F) + m_A(F) m_B(T) is discarded and the remainder is
     renormalized by 1 - K.
  3. Subjective Logic cumulative fusion (jsonld-ex cumulative_fuse).
  4. Interval probability view [l, l + u] of each input, reported
     descriptively (the two intervals are disjoint).

Hypotheses (falsifiable, decided by this script):
  H-EH6.1  Dempster's rule discards a conflict mass K > 0.5 and returns
           a result whose largest component favors lawfulness (m(T) > m(F))
           with m(Theta) < 0.05, whereas J_meet returns v > 0.5.
  H-EH6.2  Cumulative fusion also removes the conflict (u < 0.10 with
           b and d within 0.1 of each other), so the difference between the
           paper's operator and evidence-accumulation rules is the treatment
           of conflict, not the choice of Subjective Logic as such.

Outputs: results/eh6_results.json (+ timestamped archive).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_EH6_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH6_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_PKG_SRC = _REPO_ROOT.parent / "jsonld-ex" / "packages" / "python" / "src"
for _p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from jsonld_ex.compliance_algebra import ComplianceOpinion, jurisdictional_meet  # noqa: E402
from jsonld_ex.confidence_algebra import cumulative_fuse  # noqa: E402

_RESULTS_DIR = _EXPERIMENTS_ROOT / "results"

AUDITOR_A = ComplianceOpinion(belief=0.85, disbelief=0.05, uncertainty=0.10, base_rate=0.5)
AUDITOR_B = ComplianceOpinion(belief=0.10, disbelief=0.80, uncertainty=0.10, base_rate=0.5)


def to_mass(opinion: ComplianceOpinion) -> dict[str, float]:
    """Belief-function mass on the binary frame {T, F}: m(T) = l, m(F) = v, m(Theta) = u."""
    return {"T": opinion.belief, "F": opinion.disbelief, "Theta": opinion.uncertainty}


def dempster_combine(m1: dict[str, float], m2: dict[str, float]) -> dict[str, float]:
    """Dempster's rule of combination on {T, F}.

    Raises ValueError under total conflict (K = 1), where the rule is undefined.
    """
    conflict = m1["T"] * m2["F"] + m1["F"] * m2["T"]
    if conflict >= 1.0:
        raise ValueError("total conflict: Dempster's rule is undefined (K = 1)")
    norm = 1.0 - conflict
    t = (m1["T"] * m2["T"] + m1["T"] * m2["Theta"] + m1["Theta"] * m2["T"]) / norm
    f = (m1["F"] * m2["F"] + m1["F"] * m2["Theta"] + m1["Theta"] * m2["F"]) / norm
    theta = (m1["Theta"] * m2["Theta"]) / norm
    return {"T": t, "F": f, "Theta": theta, "conflict": conflict}


def run_two_auditor_contrast(a: ComplianceOpinion = AUDITOR_A,
                             b: ComplianceOpinion = AUDITOR_B) -> dict[str, Any]:
    meet = jurisdictional_meet(a, b)
    demp = dempster_combine(to_mass(a), to_mass(b))
    fused = cumulative_fuse(a, b)
    return {
        "inputs": {
            "auditor_A": [a.belief, a.disbelief, a.uncertainty, a.base_rate],
            "auditor_B": [b.belief, b.disbelief, b.uncertainty, b.base_rate],
        },
        "jmeet": {"l": meet.belief, "v": meet.disbelief, "u": meet.uncertainty},
        "dempster": demp,
        "cumulative_fusion": {"b": fused.belief, "d": fused.disbelief, "u": fused.uncertainty},
        "interval_probability": {
            "auditor_A": [a.belief, a.belief + a.uncertainty],
            "auditor_B": [b.belief, b.belief + b.uncertainty],
            "intersection_empty": bool(max(a.belief, b.belief) > min(a.belief + a.uncertainty,
                                                                     b.belief + b.uncertainty)),
        },
    }


def run_all() -> dict[str, Any]:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== EH6: two-auditor scenario under three combination rules ===")
    r = run_two_auditor_contrast()
    j, d, f = r["jmeet"], r["dempster"], r["cumulative_fusion"]
    print(f"  J_meet:            l={j['l']:.3f} v={j['v']:.3f} u={j['u']:.3f}")
    print(f"  Dempster:          T={d['T']:.3f} F={d['F']:.3f} Theta={d['Theta']:.3f} (conflict K={d['conflict']:.3f} discarded)")
    print(f"  Cumulative fusion: b={f['b']:.3f} d={f['d']:.3f} u={f['u']:.3f}")
    print(f"  Intervals: A {r['interval_probability']['auditor_A']}, B {r['interval_probability']['auditor_B']}, "
          f"disjoint={r['interval_probability']['intersection_empty']}")
    h1 = d["conflict"] > 0.5 and d["T"] > d["F"] and d["Theta"] < 0.05 and j["v"] > 0.5
    h2 = f["u"] < 0.10 and abs(f["b"] - f["d"]) < 0.10
    r["hypothesis_results"] = {"H_EH6_1": bool(h1), "H_EH6_2": bool(h2)}
    r["timestamp"] = datetime.now().strftime("%Y%m%d_%H%M%S")
    for h, v in r["hypothesis_results"].items():
        print(f"  {h}: {'ACCEPTED' if v else 'REJECTED'}")
    for path in [_RESULTS_DIR / "eh6_results.json",
                 _RESULTS_DIR / f"eh6_results_{r['timestamp']}.json"]:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2)
        print(f"Saved: {path}")
    return r


if __name__ == "__main__":
    run_all()
