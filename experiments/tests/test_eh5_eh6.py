"""RED tests for EH5 (sensitivity) and EH6 (Dempster's rule contrast).

Status: RED. Expected failure: ImportError on EH5.eh5_core / EH6.eh6_core.

Run from the repository root:
    python -m pytest experiments\\tests\\test_eh5_eh6.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_EXPERIMENTS_ROOT = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_ROOT))

from jsonld_ex.compliance_algebra import ComplianceOpinion  # noqa: E402

from EH5.eh5_core import (  # noqa: E402
    beta_params,
    grid_sweep,
    heterogeneous_phi,
    monte_carlo_deident,
    presence_rates_from_profiles,
    removal_opinions,
    base_rate_sweep,
)
from EH6.eh6_core import (  # noqa: E402
    dempster_combine,
    run_two_auditor_contrast,
    to_mass,
)

TOL = 1e-9


# ---------------------------------------------------------------- EH5

def test_removal_opinions_reproduce_phase_b_synthea_value():
    from jsonld_ex.hipaa_compliance import safe_harbor_assessment
    ops = removal_opinions(n_present=6, p=0.95, q=0.99)
    assert len(ops) == 18
    l_sh = safe_harbor_assessment(ops).belief
    assert math.isclose(l_sh, 0.6515743311712073, abs_tol=1e-9)   # e4 sh_synthea


def test_grid_sweep_contains_paper_point_and_reversal_point():
    rows = grid_sweep(ps=[0.95, 0.99], qs=[0.99])
    by = {(round(r["p"], 3), round(r["q"], 3)): r for r in rows}
    paper = by[(0.95, 0.99)]
    assert math.isclose(paper["t_star"], 0.7239714790791193, abs_tol=1e-9)
    assert paper["expert_wins_at_0_85"] is True
    reversal = by[(0.99, 0.99)]
    assert math.isclose(reversal["l_sh"], 0.99 ** 18, abs_tol=1e-9)
    assert reversal["expert_wins_at_0_85"] is False


def test_beta_params_match_mean_and_concentration():
    a, b = beta_params(mean=0.95, kappa=20)
    assert math.isclose(a, 19.0) and math.isclose(b, 1.0)
    assert math.isclose(a / (a + b), 0.95)


def test_monte_carlo_is_deterministic_and_well_formed():
    r1 = monte_carlo_deident(n_draws=200, mean_p=0.95, mean_q=0.99, kappa=100, seed=42)
    r2 = monte_carlo_deident(n_draws=200, mean_p=0.95, mean_q=0.99, kappa=100, seed=42)
    assert r1 == r2
    assert 0.0 < r1["l_sh_p05"] <= r1["l_sh_median"] <= r1["l_sh_p95"] < 1.0
    assert 0.0 <= r1["expert_wins_fraction"] <= 1.0
    assert r1["n_draws"] == 200
    assert math.isclose(r1["l_ed"], 0.765, abs_tol=1e-9)


def test_presence_rates_come_from_the_seven_e5_profiles():
    rates = presence_rates_from_profiles()
    assert len(rates) == 18
    assert math.isclose(rates["dates"], 1.0)
    assert math.isclose(rates["medical_record_numbers"], 6 / 7)
    assert math.isclose(rates["names"], 2 / 7)
    assert math.isclose(rates["vehicle_identifiers"], 0.0)


def test_heterogeneous_phi_is_deterministic_and_bounded():
    r = heterogeneous_phi(n_draws=200, kappa=100, seed=42)
    assert r["n_draws"] == 200
    assert 0.0 <= r["l_phi_median"] <= r["l_phi_p95"] <= 1.0
    assert r["n_present_min"] >= 1          # 'dates' is always present
    assert r["n_present_max"] <= 18
    assert r == heterogeneous_phi(n_draws=200, kappa=100, seed=42)


def test_base_rate_sweep_leaves_lvu_unchanged():
    r = base_rate_sweep(base_rates=[0.1, 0.5, 0.9])
    for scenario, rec in r["scenarios"].items():
        assert rec["max_abs_diff_lvu"] < 1e-12, scenario
        assert len(set(round(p, 12) for p in rec["projected_probabilities"])) > 1, scenario


# ---------------------------------------------------------------- EH6

def test_to_mass_maps_opinion_components():
    op = ComplianceOpinion.create(0.85, 0.05, 0.10, 0.5)
    m = to_mass(op)
    assert m == {"T": 0.85, "F": 0.05, "Theta": 0.10}


def test_dempster_combine_two_auditors_hand_computed():
    a = to_mass(ComplianceOpinion.create(0.85, 0.05, 0.10, 0.5))
    b = to_mass(ComplianceOpinion.create(0.10, 0.80, 0.10, 0.5))
    out = dempster_combine(a, b)
    assert math.isclose(out["conflict"], 0.685, abs_tol=TOL)
    assert math.isclose(out["T"], 0.18 / 0.315, abs_tol=TOL)
    assert math.isclose(out["F"], 0.125 / 0.315, abs_tol=TOL)
    assert math.isclose(out["Theta"], 0.01 / 0.315, abs_tol=TOL)
    assert math.isclose(out["T"] + out["F"] + out["Theta"], 1.0, abs_tol=TOL)


def test_dempster_combine_total_conflict_raises():
    a = {"T": 1.0, "F": 0.0, "Theta": 0.0}
    b = {"T": 0.0, "F": 1.0, "Theta": 0.0}
    with pytest.raises(ValueError):
        dempster_combine(a, b)


def test_two_auditor_contrast_reports_all_three_rules():
    r = run_two_auditor_contrast()
    j = r["jmeet"]
    assert math.isclose(j["l"], 0.085, abs_tol=1e-6)      # eh4 scenario 1
    assert math.isclose(j["v"], 0.81, abs_tol=1e-6)
    assert math.isclose(j["u"], 0.105, abs_tol=1e-6)
    d = r["dempster"]
    assert math.isclose(d["conflict"], 0.685, abs_tol=TOL)
    assert math.isclose(d["T"], 0.5714285714, abs_tol=1e-6)
    f = r["cumulative_fusion"]
    assert math.isclose(f["b"], 0.5, abs_tol=1e-9)
    assert math.isclose(f["d"], 0.085 / 0.19, abs_tol=1e-9)
    assert math.isclose(f["u"], 0.01 / 0.19, abs_tol=1e-9)
