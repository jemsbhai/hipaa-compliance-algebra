"""EH5 -- Sensitivity of the HIPAA compliance algebra to assumed confidences.

Pre-registered design and hypotheses: experiments/EH5_DESIGN.md.
Every quantity is computed through the implemented jsonld-ex operators.

Outputs: results/eh5_results.json (+ timestamped archive).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

_EH5_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH5_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_PKG_SRC = _REPO_ROOT.parent / "jsonld-ex" / "packages" / "python" / "src"
for _p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from jsonld_ex.compliance_algebra import ComplianceOpinion  # noqa: E402
from jsonld_ex.hipaa_compliance import (  # noqa: E402
    SAFE_HARBOR_IDENTIFIERS,
    baa_trust_chain,
    dual_regime_composition,
    expert_determination_assessment,
    phi_classification,
    safe_harbor_assessment,
)

_RESULTS_DIR = _EXPERIMENTS_ROOT / "results"
_E5_PATH = _RESULTS_DIR / "eh2_phase_e_results.json"

EXPERT_BELIEF = 0.90
EXPERT_TRUST = 0.85
GRID_P = [0.80, 0.85, 0.90, 0.95, 0.99, 0.999]
GRID_Q = [0.90, 0.95, 0.99, 0.999]
BASE_RATES = [0.1, 0.3, 0.5, 0.7, 0.9]


# ---------------------------------------------------------------- opinion builders

def _opinion(l: float, v_cap: float, base_rate: float = 0.5) -> ComplianceOpinion:
    """Opinion with belief l and disbelief min(v_cap, (1 - l)/2).

    Reproduces the EH2 constructions exactly at their nominal values
    (for example l = 0.95, v_cap = 0.02 gives (0.95, 0.02, 0.03)) and keeps
    l + v + u = 1 with u >= 0 for any sampled l in (0, 1).
    """
    l = float(l)
    v = min(v_cap, (1.0 - l) / 2.0)
    u = 1.0 - l - v
    return ComplianceOpinion(belief=l, disbelief=v, uncertainty=u, base_rate=base_rate)


def removal_opinions(n_present: int, p: float, q: float, base_rate: float = 0.5) -> list[ComplianceOpinion]:
    """Phase B Safe Harbor construction: n_present categories removed with
    belief p (disbelief 0.02), the remaining 18 - n_present never present
    with belief q (disbelief 0.005)."""
    ops = [_opinion(p, 0.02, base_rate) for _ in range(n_present)]
    ops += [_opinion(q, 0.005, base_rate) for _ in range(18 - n_present)]
    return ops


def expert_pair(base_rate: float = 0.5) -> tuple[ComplianceOpinion, ComplianceOpinion]:
    expert = ComplianceOpinion(belief=EXPERT_BELIEF, disbelief=0.05,
                               uncertainty=1.0 - EXPERT_BELIEF - 0.05, base_rate=base_rate)
    trust = ComplianceOpinion(belief=EXPERT_TRUST, disbelief=0.05,
                              uncertainty=1.0 - EXPERT_TRUST - 0.05, base_rate=base_rate)
    return expert, trust


def beta_params(mean: float, kappa: float) -> tuple[float, float]:
    """Beta(a, b) with the given mean and concentration kappa = a + b."""
    return mean * kappa, (1.0 - mean) * kappa


# ---------------------------------------------------------------- A. grid sweep

def grid_sweep(ps: list[float] = GRID_P, qs: list[float] = GRID_Q, n_present: int = 6) -> list[dict[str, Any]]:
    l_ed = expert_determination_assessment(*expert_pair()).belief
    rows: list[dict[str, Any]] = []
    for p in ps:
        for q in qs:
            l_sh = safe_harbor_assessment(removal_opinions(n_present, p, q)).belief
            rows.append({
                "p": p, "q": q, "l_sh": l_sh, "l_ed": l_ed,
                "t_star": l_sh / EXPERT_BELIEF,
                "expert_wins_at_0_85": bool(l_ed > l_sh),
            })
    return rows


# ---------------------------------------------------------------- B. heterogeneous removal confidences

def monte_carlo_deident(n_draws: int, mean_p: float, mean_q: float, kappa: float, seed: int,
                        n_present: int = 6) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    a_p, b_p = beta_params(mean_p, kappa)
    a_q, b_q = beta_params(mean_q, kappa)
    P = rng.beta(a_p, b_p, size=(n_draws, n_present))
    Q = rng.beta(a_q, b_q, size=(n_draws, 18 - n_present))
    l_ed = expert_determination_assessment(*expert_pair()).belief
    l_sh = np.empty(n_draws)
    for i in range(n_draws):
        ops = [_opinion(x, 0.02) for x in P[i]] + [_opinion(x, 0.005) for x in Q[i]]
        l_sh[i] = safe_harbor_assessment(ops).belief
    return {
        "n_draws": n_draws, "mean_p": mean_p, "mean_q": mean_q, "kappa": kappa, "seed": seed,
        "l_ed": float(l_ed),
        "l_sh_mean": float(l_sh.mean()),
        "l_sh_median": float(np.median(l_sh)),
        "l_sh_p05": float(np.percentile(l_sh, 5)),
        "l_sh_p95": float(np.percentile(l_sh, 95)),
        "t_star_median": float(np.median(l_sh) / EXPERT_BELIEF),
        "expert_wins_fraction": float(np.mean(l_ed > l_sh)),
    }


# ---------------------------------------------------------------- C. heterogeneous presence

def presence_rates_from_profiles(path: Path = _E5_PATH) -> dict[str, float]:
    """Empirical presence frequency of each identifier category across the
    seven FHIR resource-type profiles saved by EH2 E5."""
    with open(path, "r", encoding="utf-8") as f:
        profiles = json.load(f)["e5_cross_resource"]["profiles"]
    n = len(profiles)
    return {
        name: sum(1 for pr in profiles if name in pr["identifiers_present"]) / n
        for name in SAFE_HARBOR_IDENTIFIERS
    }


def heterogeneous_phi(n_draws: int, kappa: float, seed: int,
                      mean_present: float = 0.05, mean_absent: float = 0.95) -> dict[str, Any]:
    rates = presence_rates_from_profiles()
    rate_vec = np.array([rates[name] for name in SAFE_HARBOR_IDENTIFIERS])
    rng = np.random.default_rng(seed)
    a_pr, b_pr = beta_params(mean_present, kappa)
    a_ab, b_ab = beta_params(mean_absent, kappa)
    present = rng.random(size=(n_draws, 18)) < rate_vec
    L_present = rng.beta(a_pr, b_pr, size=(n_draws, 18))
    L_absent = rng.beta(a_ab, b_ab, size=(n_draws, 18))
    l_phi = np.empty(n_draws)
    n_present = present.sum(axis=1)
    for i in range(n_draws):
        ops = []
        for j in range(18):
            if present[i, j]:
                l = float(L_present[i, j])
                v = (1.0 - l) * (0.90 / 0.95)      # (0.05, 0.90, 0.05) at the nominal value
                ops.append(ComplianceOpinion(belief=l, disbelief=v, uncertainty=1.0 - l - v, base_rate=0.5))
            else:
                ops.append(_opinion(L_absent[i, j], 0.02))   # (0.95, 0.02, 0.03) at the nominal value
        l_phi[i] = phi_classification(ops).belief
    return {
        "n_draws": n_draws, "kappa": kappa, "seed": seed,
        "presence_rates": rates,
        "n_present_min": int(n_present.min()), "n_present_max": int(n_present.max()),
        "n_present_mean": float(n_present.mean()),
        "l_phi_median": float(np.median(l_phi)),
        "l_phi_p95": float(np.percentile(l_phi, 95)),
        "l_phi_max": float(l_phi.max()),
    }


# ---------------------------------------------------------------- D. base rates

def base_rate_sweep(base_rates: list[float] = BASE_RATES) -> dict[str, Any]:
    def scenarios(a: float) -> dict[str, ComplianceOpinion]:
        source = ComplianceOpinion(belief=0.95, disbelief=0.03, uncertainty=0.02, base_rate=a)
        link = (ComplianceOpinion(belief=0.90, disbelief=0.05, uncertainty=0.05, base_rate=a),
                ComplianceOpinion(belief=0.95, disbelief=0.03, uncertainty=0.02, base_rate=a))
        hipaa = ComplianceOpinion(belief=0.652, disbelief=0.30, uncertainty=0.048, base_rate=a)
        gdpr = ComplianceOpinion(belief=0.450, disbelief=0.250, uncertainty=0.300, base_rate=a)
        return {
            "safe_harbor": safe_harbor_assessment(removal_opinions(6, 0.95, 0.99, a)),
            "expert": expert_determination_assessment(*expert_pair(a)),
            "baa_chain": baa_trust_chain(source, [link, link, link]),
            "dual_regime": dual_regime_composition(hipaa, gdpr),
        }

    per_a = {a: scenarios(a) for a in base_rates}
    out: dict[str, Any] = {"base_rates": base_rates, "scenarios": {}}
    for name in ["safe_harbor", "expert", "baa_chain", "dual_regime"]:
        lvu = np.array([[per_a[a][name].belief, per_a[a][name].disbelief, per_a[a][name].uncertainty]
                        for a in base_rates])
        out["scenarios"][name] = {
            "lvu_at_first_base_rate": lvu[0].tolist(),
            "max_abs_diff_lvu": float(np.abs(lvu - lvu[0]).max()),
            "projected_probabilities": [float(per_a[a][name].projected_probability()) for a in base_rates],
        }
    return out


# ---------------------------------------------------------------- runner

def run_all() -> dict[str, Any]:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== EH5: sensitivity to assumed confidences ===")

    grid = grid_sweep()
    h1_low = all(r["expert_wins_at_0_85"] for r in grid if r["p"] <= 0.95)
    h1_rev = any(not r["expert_wins_at_0_85"] for r in grid if r["p"] == 0.99)
    print(f"  A. grid: {len(grid)} points; expert wins at all p<=0.95: {h1_low}; a reversal at p=0.99: {h1_rev}")
    for r in grid:
        if not r["expert_wins_at_0_85"]:
            print(f"     reversal at p={r['p']}, q={r['q']}: l_sh={r['l_sh']:.3f} > l_ed={r['l_ed']:.3f}")

    mc = {str(k): monte_carlo_deident(10_000, 0.95, 0.99, k, seed=42) for k in (20, 100)}
    for k, r in mc.items():
        print(f"  B. kappa={k}: l_sh median {r['l_sh_median']:.3f} [{r['l_sh_p05']:.3f}, {r['l_sh_p95']:.3f}], "
              f"expert wins {100*r['expert_wins_fraction']:.1f}%")
    h2 = mc["100"]["expert_wins_fraction"] > 0.95

    het = heterogeneous_phi(10_000, kappa=100, seed=42)
    print(f"  C. presence: n_present {het['n_present_min']}..{het['n_present_max']} (mean {het['n_present_mean']:.2f}); "
          f"l_phi median {het['l_phi_median']:.3e}, p95 {het['l_phi_p95']:.3e}, max {het['l_phi_max']:.3e}")
    h3 = het["l_phi_median"] < 1e-3 and het["l_phi_p95"] < 0.10

    br = base_rate_sweep()
    h4 = all(s["max_abs_diff_lvu"] < 1e-12 for s in br["scenarios"].values())
    print(f"  D. base rates: max |delta (l,v,u)| = "
          f"{max(s['max_abs_diff_lvu'] for s in br['scenarios'].values()):.2e}; P varies: "
          + ", ".join(f"{n}: {min(s['projected_probabilities']):.3f}..{max(s['projected_probabilities']):.3f}"
                      for n, s in br["scenarios"].items()))

    results = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "grid": grid,
        "monte_carlo": mc,
        "heterogeneous_presence": het,
        "base_rate_sweep": br,
        "hypothesis_results": {
            "H_EH5_1": bool(h1_low and h1_rev),
            "H_EH5_2": bool(h2),
            "H_EH5_3": bool(h3),
            "H_EH5_4": bool(h4),
        },
    }
    for h, v in results["hypothesis_results"].items():
        print(f"  {h}: {'ACCEPTED' if v else 'REJECTED'}")
    for path in [_RESULTS_DIR / "eh5_results.json",
                 _RESULTS_DIR / f"eh5_results_{results['timestamp']}.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved: {path}")
    return results


if __name__ == "__main__":
    run_all()
