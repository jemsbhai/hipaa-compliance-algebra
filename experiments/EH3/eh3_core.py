"""EH3 -- Privacy-Preserving Compliance Aggregation via Homomorphic Encryption.

Proof-of-concept: CKKS-encrypted Jurisdictional Meet for multi-department
HIPAA compliance aggregation without revealing individual scores.

Hypotheses (all falsifiable):
  H-EH3.1: CKKS-encrypted J_sqcap within epsilon=0.001 of plaintext
  H-EH3.2: Post-normalization restores b+d+u=1 within epsilon=0.0001
  H-EH3.3: Encrypted 2-party meet < 100ms (excluding keygen)
  H-EH3.4: Noise budget supports depth-3 chains before epsilon > 0.01

Protocol:
  1. Encrypt ComplianceOpinion components as CKKS scalars
  2. Compute J_sqcap in encrypted space using only + and *
  3. Decrypt, normalize, compare to plaintext result
  4. Benchmark latency across 1000 trials
  5. Test chain depths 1-5 for noise accumulation

Library: TenSEAL (Python wrapper around Microsoft SEAL, BSD-3)
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

# -- Path setup ---------------------------------------------------------------
_EH3_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_ROOT = _EH3_DIR.parent
_REPO_ROOT = _EXPERIMENTS_ROOT.parent
_JSONLDEX_ROOT = _REPO_ROOT.parent / "jsonld-ex"
_PKG_SRC = _JSONLDEX_ROOT / "packages" / "python" / "src"

for p in [str(_PKG_SRC), str(_EXPERIMENTS_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from jsonld_ex.compliance_algebra import ComplianceOpinion, jurisdictional_meet

# -- TenSEAL import with clear error -----------------------------------------
try:
    import tenseal as ts
    TENSEAL_AVAILABLE = True
except ImportError:
    TENSEAL_AVAILABLE = False
    print("WARNING: TenSEAL not installed. Install with: pip install tenseal")
    print("  If installation fails on Windows, use WSL.")
    print("  Falling back to theoretical analysis only.")


# =============================================================================
# CKKS Context Factory
# =============================================================================

def create_ckks_context(
    mult_depth: int = 3,
) -> "ts.Context":
    """Create a CKKS context with sufficient multiplication depth.

    Args:
        mult_depth: Required number of sequential multiplications.
            Each J_sqcap requires 1 multiplication level.
            Chain of n meets requires n levels.

    Returns:
        TenSEAL CKKS context.
    """
    # Choose poly_modulus_degree based on required depth
    # Rule of thumb: need (mult_depth + 1) primes in coeff_mod_bit_sizes
    # and poly_modulus_degree >= 2 * total_bit_size for security
    if mult_depth <= 2:
        poly_mod = 8192
        # [scale_prime, mult_primes..., scale_prime]
        coeff_sizes = [60] + [40] * mult_depth + [60]
    elif mult_depth <= 5:
        poly_mod = 16384
        coeff_sizes = [60] + [40] * mult_depth + [60]
    else:
        poly_mod = 32768
        coeff_sizes = [60] + [40] * mult_depth + [60]

    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=poly_mod,
        coeff_mod_bit_sizes=coeff_sizes,
    )
    context.global_scale = 2 ** 40
    context.generate_galois_keys()
    context.generate_relin_keys()

    return context


# =============================================================================
# Encrypted Jurisdictional Meet
# =============================================================================

def encrypt_opinion(
    ctx: "ts.Context",
    opinion: ComplianceOpinion,
) -> tuple:
    """Encrypt a ComplianceOpinion as 4 CKKS scalars.

    Returns (enc_l, enc_v, enc_u, enc_a) where each is a CKKSVector
    of length 1.
    """
    enc_l = ts.ckks_vector(ctx, [opinion.belief])
    enc_v = ts.ckks_vector(ctx, [opinion.disbelief])
    enc_u = ts.ckks_vector(ctx, [opinion.uncertainty])
    enc_a = ts.ckks_vector(ctx, [opinion.base_rate])
    return (enc_l, enc_v, enc_u, enc_a)


def encrypted_jurisdictional_meet(
    enc_w1: tuple,
    enc_w2: tuple,
) -> tuple:
    """Compute Jurisdictional Meet in CKKS encrypted space.

    J_sqcap equations:
        l_meet = l1 * l2
        v_meet = v1 + v2 - v1 * v2
        u_meet = 1 - l_meet - v_meet  (constraint enforcement)
        a_meet = a1 * a2

    All operations are additions and multiplications, which CKKS supports.

    Args:
        enc_w1: (enc_l1, enc_v1, enc_u1, enc_a1)
        enc_w2: (enc_l2, enc_v2, enc_u2, enc_a2)

    Returns:
        (enc_l_meet, enc_v_meet, enc_u_meet, enc_a_meet)
    """
    enc_l1, enc_v1, enc_u1, enc_a1 = enc_w1
    enc_l2, enc_v2, enc_u2, enc_a2 = enc_w2

    # l_meet = l1 * l2  (depth +1)
    enc_l_meet = enc_l1 * enc_l2

    # v_meet = v1 + v2 - v1*v2  (depth +1 for the multiply)
    enc_v1v2 = enc_v1 * enc_v2
    enc_v_meet = enc_v1 + enc_v2 - enc_v1v2

    # u_meet = 1 - v_meet - l_meet
    # This uses the constraint l+v+u=1, computed from encrypted l and v
    # Plaintext constant 1.0 added to ciphertext (no depth increase)
    enc_u_meet = enc_l_meet.neg() - enc_v_meet + [1.0]

    # a_meet = a1 * a2  (depth +1)
    enc_a_meet = enc_a1 * enc_a2

    return (enc_l_meet, enc_v_meet, enc_u_meet, enc_a_meet)


def decrypt_opinion(
    enc_opinion: tuple,
) -> tuple[float, float, float, float]:
    """Decrypt an encrypted opinion tuple.

    Returns (l, v, u, a) as plain floats.
    """
    l = enc_opinion[0].decrypt()[0]
    v = enc_opinion[1].decrypt()[0]
    u = enc_opinion[2].decrypt()[0]
    a = enc_opinion[3].decrypt()[0]
    return (l, v, u, a)


def normalize_opinion(
    raw: tuple[float, float, float, float],
) -> ComplianceOpinion:
    """Normalize decrypted values to enforce l+v+u=1.

    CKKS approximate arithmetic may slightly violate the constraint.
    We normalize by distributing the error proportionally.

    Args:
        raw: (l, v, u, a) from decryption.

    Returns:
        Valid ComplianceOpinion with l+v+u=1.
    """
    l, v, u, a = raw
    # Clamp negatives (CKKS noise can produce small negative values)
    l = max(0.0, l)
    v = max(0.0, v)
    u = max(0.0, u)
    a = max(0.0, min(1.0, a))

    total = l + v + u
    if total > 0:
        l /= total
        v /= total
        u /= total
    else:
        # Degenerate: fall back to vacuous
        l, v, u = 0.0, 0.0, 1.0

    return ComplianceOpinion(belief=l, disbelief=v, uncertainty=u, base_rate=a)


# =============================================================================
# Accuracy Benchmark
# =============================================================================

@dataclass
class AccuracyResult:
    """Result of one accuracy comparison."""
    plaintext_l: float
    plaintext_v: float
    plaintext_u: float
    encrypted_l: float
    encrypted_v: float
    encrypted_u: float
    normalized_l: float
    normalized_v: float
    normalized_u: float
    error_l: float
    error_v: float
    error_u: float
    error_l_normalized: float
    error_v_normalized: float
    error_u_normalized: float
    constraint_violation_raw: float
    constraint_violation_normalized: float


def run_accuracy_benchmark(
    n_trials: int = 1000,
    seed: int = 42,
    mult_depth: int = 1,
) -> dict[str, Any]:
    """Compare plaintext vs encrypted J_sqcap accuracy.

    For n_trials random opinion pairs:
      1. Compute plaintext J_sqcap
      2. Encrypt, compute encrypted J_sqcap, decrypt
      3. Normalize decrypted result
      4. Measure error at each stage
    """
    print(f"\n  Running accuracy benchmark: {n_trials} trials, depth={mult_depth}")

    ctx = create_ckks_context(mult_depth=mult_depth)
    rng = np.random.default_rng(seed)

    results: list[AccuracyResult] = []

    for i in range(n_trials):
        # Generate random opinions
        l1 = rng.uniform(0.05, 0.95)
        v1 = rng.uniform(0.0, 1.0 - l1 - 0.01)
        u1 = 1.0 - l1 - v1
        a1 = rng.uniform(0.1, 0.9)

        l2 = rng.uniform(0.05, 0.95)
        v2 = rng.uniform(0.0, 1.0 - l2 - 0.01)
        u2 = 1.0 - l2 - v2
        a2 = rng.uniform(0.1, 0.9)

        w1 = ComplianceOpinion(belief=l1, disbelief=v1, uncertainty=u1, base_rate=a1)
        w2 = ComplianceOpinion(belief=l2, disbelief=v2, uncertainty=u2, base_rate=a2)

        # Plaintext result
        pt_result = jurisdictional_meet(w1, w2)

        # Encrypted result
        enc_w1 = encrypt_opinion(ctx, w1)
        enc_w2 = encrypt_opinion(ctx, w2)
        enc_result = encrypted_jurisdictional_meet(enc_w1, enc_w2)
        raw = decrypt_opinion(enc_result)
        normalized = normalize_opinion(raw)

        # Errors
        error_l = abs(raw[0] - pt_result.belief)
        error_v = abs(raw[1] - pt_result.disbelief)
        error_u = abs(raw[2] - pt_result.uncertainty)

        error_l_norm = abs(normalized.belief - pt_result.belief)
        error_v_norm = abs(normalized.disbelief - pt_result.disbelief)
        error_u_norm = abs(normalized.uncertainty - pt_result.uncertainty)

        constraint_raw = abs(raw[0] + raw[1] + raw[2] - 1.0)
        constraint_norm = abs(
            normalized.belief + normalized.disbelief + normalized.uncertainty - 1.0
        )

        results.append(AccuracyResult(
            plaintext_l=pt_result.belief,
            plaintext_v=pt_result.disbelief,
            plaintext_u=pt_result.uncertainty,
            encrypted_l=raw[0],
            encrypted_v=raw[1],
            encrypted_u=raw[2],
            normalized_l=normalized.belief,
            normalized_v=normalized.disbelief,
            normalized_u=normalized.uncertainty,
            error_l=error_l,
            error_v=error_v,
            error_u=error_u,
            error_l_normalized=error_l_norm,
            error_v_normalized=error_v_norm,
            error_u_normalized=error_u_norm,
            constraint_violation_raw=constraint_raw,
            constraint_violation_normalized=constraint_norm,
        ))

        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{n_trials} trials complete")

    # Aggregate statistics
    errors_l = [r.error_l for r in results]
    errors_v = [r.error_v for r in results]
    errors_u = [r.error_u for r in results]
    errors_l_norm = [r.error_l_normalized for r in results]
    errors_v_norm = [r.error_v_normalized for r in results]
    constraint_raw_vals = [r.constraint_violation_raw for r in results]
    constraint_norm_vals = [r.constraint_violation_normalized for r in results]

    stats = {
        "n_trials": n_trials,
        "mult_depth": mult_depth,
        "raw_error": {
            "l_mean": float(np.mean(errors_l)),
            "l_max": float(np.max(errors_l)),
            "l_p99": float(np.percentile(errors_l, 99)),
            "v_mean": float(np.mean(errors_v)),
            "v_max": float(np.max(errors_v)),
            "u_mean": float(np.mean(errors_u)),
            "u_max": float(np.max(errors_u)),
        },
        "normalized_error": {
            "l_mean": float(np.mean(errors_l_norm)),
            "l_max": float(np.max(errors_l_norm)),
            "v_mean": float(np.mean(errors_v_norm)),
            "v_max": float(np.max(errors_v_norm)),
        },
        "constraint_violation": {
            "raw_mean": float(np.mean(constraint_raw_vals)),
            "raw_max": float(np.max(constraint_raw_vals)),
            "normalized_mean": float(np.mean(constraint_norm_vals)),
            "normalized_max": float(np.max(constraint_norm_vals)),
        },
        "hypothesis_results": {
            "H_EH3_1": float(np.max(errors_l)) < 0.001,
            "H_EH3_2": float(np.max(constraint_norm_vals)) < 0.0001,
        },
    }

    return stats


# =============================================================================
# Latency Benchmark
# =============================================================================

def run_latency_benchmark(
    n_trials: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Measure latency of encrypted J_sqcap operations.

    Separately times: keygen, encryption, computation, decryption.
    Reports p50, p95, p99 with bootstrap CIs.
    """
    print(f"\n  Running latency benchmark: {n_trials} trials")

    rng = np.random.default_rng(seed)

    # Keygen (once)
    t0 = time.perf_counter()
    ctx = create_ckks_context(mult_depth=2)
    keygen_ms = (time.perf_counter() - t0) * 1000

    encrypt_times = []
    compute_times = []
    decrypt_times = []
    total_times = []

    # Warm-up
    for _ in range(10):
        w1 = ComplianceOpinion(belief=0.5, disbelief=0.3, uncertainty=0.2, base_rate=0.5)
        w2 = ComplianceOpinion(belief=0.6, disbelief=0.2, uncertainty=0.2, base_rate=0.5)
        enc_w1 = encrypt_opinion(ctx, w1)
        enc_w2 = encrypt_opinion(ctx, w2)
        enc_r = encrypted_jurisdictional_meet(enc_w1, enc_w2)
        decrypt_opinion(enc_r)

    for i in range(n_trials):
        l1 = rng.uniform(0.05, 0.95)
        v1 = rng.uniform(0.0, 1.0 - l1 - 0.01)
        u1 = 1.0 - l1 - v1
        a1 = rng.uniform(0.1, 0.9)
        l2 = rng.uniform(0.05, 0.95)
        v2 = rng.uniform(0.0, 1.0 - l2 - 0.01)
        u2 = 1.0 - l2 - v2
        a2 = rng.uniform(0.1, 0.9)

        w1 = ComplianceOpinion(belief=l1, disbelief=v1, uncertainty=u1, base_rate=a1)
        w2 = ComplianceOpinion(belief=l2, disbelief=v2, uncertainty=u2, base_rate=a2)

        # Encrypt
        t_enc_start = time.perf_counter()
        enc_w1 = encrypt_opinion(ctx, w1)
        enc_w2 = encrypt_opinion(ctx, w2)
        t_enc_end = time.perf_counter()

        # Compute
        t_comp_start = time.perf_counter()
        enc_result = encrypted_jurisdictional_meet(enc_w1, enc_w2)
        t_comp_end = time.perf_counter()

        # Decrypt + normalize
        t_dec_start = time.perf_counter()
        raw = decrypt_opinion(enc_result)
        _ = normalize_opinion(raw)
        t_dec_end = time.perf_counter()

        encrypt_times.append((t_enc_end - t_enc_start) * 1000)
        compute_times.append((t_comp_end - t_comp_start) * 1000)
        decrypt_times.append((t_dec_end - t_dec_start) * 1000)
        total_times.append((t_dec_end - t_enc_start) * 1000)

        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{n_trials} trials complete")

    def percentiles(data):
        arr = np.array(data)
        return {
            "mean": float(arr.mean()),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "min": float(arr.min()),
            "max": float(arr.max()),
        }

    stats = {
        "n_trials": n_trials,
        "keygen_ms": keygen_ms,
        "encrypt_ms": percentiles(encrypt_times),
        "compute_ms": percentiles(compute_times),
        "decrypt_ms": percentiles(decrypt_times),
        "total_ms": percentiles(total_times),
        "hypothesis_results": {
            "H_EH3_3": float(np.percentile(total_times, 50)) < 100,
        },
    }

    return stats


# =============================================================================
# Noise Budget / Chain Depth Study
# =============================================================================

def run_depth_study(
    max_depth: int = 5,
    n_trials: int = 100,
    seed: int = 42,
) -> dict[str, Any]:
    """Test accuracy degradation across chain depths.

    For each depth d in 1..max_depth:
      1. Create d+1 random opinions
      2. Compute plaintext chain: J_sqcap(w1, J_sqcap(w2, ...))
      3. Compute encrypted chain
      4. Measure error at each depth
    """
    print(f"\n  Running depth study: depths 1-{max_depth}, {n_trials} trials each")

    rng = np.random.default_rng(seed)
    depth_results = []

    for depth in range(1, max_depth + 1):
        print(f"    Depth {depth}...")
        ctx = create_ckks_context(mult_depth=depth)
        errors_l = []
        errors_v = []
        constraint_violations = []
        successes = 0
        failures = 0

        for trial in range(n_trials):
            try:
                # Generate opinions
                opinions = []
                for _ in range(depth + 1):
                    l = rng.uniform(0.1, 0.9)
                    v = rng.uniform(0.0, min(0.8, 1.0 - l - 0.01))
                    u = 1.0 - l - v
                    a = rng.uniform(0.2, 0.8)
                    opinions.append(ComplianceOpinion(
                        belief=l, disbelief=v, uncertainty=u, base_rate=a,
                    ))

                # Plaintext chain
                pt_result = opinions[0]
                for j in range(1, len(opinions)):
                    pt_result = jurisdictional_meet(pt_result, opinions[j])

                # Encrypted chain
                enc_current = encrypt_opinion(ctx, opinions[0])
                for j in range(1, len(opinions)):
                    enc_next = encrypt_opinion(ctx, opinions[j])
                    enc_current = encrypted_jurisdictional_meet(enc_current, enc_next)

                raw = decrypt_opinion(enc_current)
                normalized = normalize_opinion(raw)

                error_l = abs(normalized.belief - pt_result.belief)
                error_v = abs(normalized.disbelief - pt_result.disbelief)
                constraint_viol = abs(raw[0] + raw[1] + raw[2] - 1.0)

                errors_l.append(error_l)
                errors_v.append(error_v)
                constraint_violations.append(constraint_viol)
                successes += 1

            except Exception as e:
                failures += 1
                if failures <= 3:
                    print(f"      Trial {trial} failed at depth {depth}: {e}")

        if errors_l:
            depth_results.append({
                "depth": depth,
                "successes": successes,
                "failures": failures,
                "error_l_mean": float(np.mean(errors_l)),
                "error_l_max": float(np.max(errors_l)),
                "error_l_p99": float(np.percentile(errors_l, 99)),
                "error_v_mean": float(np.mean(errors_v)),
                "error_v_max": float(np.max(errors_v)),
                "constraint_violation_mean": float(np.mean(constraint_violations)),
                "constraint_violation_max": float(np.max(constraint_violations)),
                "within_epsilon_001": float(np.mean([e < 0.001 for e in errors_l])) * 100,
                "within_epsilon_01": float(np.mean([e < 0.01 for e in errors_l])) * 100,
            })
        else:
            depth_results.append({
                "depth": depth,
                "successes": 0,
                "failures": failures,
                "error_l_mean": None,
                "note": "All trials failed",
            })

    # H-EH3.4: depth-3 chains within epsilon=0.01
    depth_3 = next((d for d in depth_results if d["depth"] == 3), None)
    h_eh3_4 = False
    if depth_3 and depth_3.get("error_l_max") is not None:
        h_eh3_4 = depth_3["error_l_max"] < 0.01

    return {
        "max_depth": max_depth,
        "n_trials_per_depth": n_trials,
        "depth_results": depth_results,
        "hypothesis_results": {
            "H_EH3_4": h_eh3_4,
        },
    }


# =============================================================================
# Plaintext Baseline Latency (for honest comparison)
# =============================================================================

def run_plaintext_baseline(
    n_trials: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """Measure plaintext J_sqcap latency for honest overhead comparison."""
    print(f"\n  Running plaintext baseline: {n_trials} trials")

    rng = np.random.default_rng(seed)
    times = []

    for _ in range(n_trials):
        l1 = rng.uniform(0.05, 0.95)
        v1 = rng.uniform(0.0, 1.0 - l1 - 0.01)
        u1 = 1.0 - l1 - v1
        a1 = rng.uniform(0.1, 0.9)
        l2 = rng.uniform(0.05, 0.95)
        v2 = rng.uniform(0.0, 1.0 - l2 - 0.01)
        u2 = 1.0 - l2 - v2
        a2 = rng.uniform(0.1, 0.9)

        w1 = ComplianceOpinion(belief=l1, disbelief=v1, uncertainty=u1, base_rate=a1)
        w2 = ComplianceOpinion(belief=l2, disbelief=v2, uncertainty=u2, base_rate=a2)

        t0 = time.perf_counter()
        _ = jurisdictional_meet(w1, w2)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    arr = np.array(times)
    return {
        "n_trials": n_trials,
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
    }


# =============================================================================
# Main Runner
# =============================================================================

def run_all() -> dict[str, Any]:
    """Run all EH3 benchmarks."""
    if not TENSEAL_AVAILABLE:
        print("\nERROR: TenSEAL not available. Cannot run EH3.")
        print("Install: pip install tenseal")
        print("Or use WSL: wsl pip install tenseal")
        return {"error": "tenseal_not_installed"}

    out = _EXPERIMENTS_ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)

    print("=== EH3: Privacy-Preserving Compliance Aggregation ===")

    # Plaintext baseline first (for honest comparison)
    print("\n--- Plaintext Baseline ---")
    baseline = run_plaintext_baseline()
    print(f"  Plaintext J_sqcap: p50={baseline['p50_ms']:.4f}ms, "
          f"p99={baseline['p99_ms']:.4f}ms")

    # Accuracy at depth 1
    print("\n--- Accuracy Benchmark (depth=1) ---")
    accuracy = run_accuracy_benchmark(n_trials=1000, mult_depth=1)
    print(f"  Raw error l: mean={accuracy['raw_error']['l_mean']:.2e}, "
          f"max={accuracy['raw_error']['l_max']:.2e}")
    print(f"  Normalized error l: mean={accuracy['normalized_error']['l_mean']:.2e}, "
          f"max={accuracy['normalized_error']['l_max']:.2e}")
    print(f"  Constraint violation (raw): max={accuracy['constraint_violation']['raw_max']:.2e}")
    print(f"  Constraint violation (normalized): max={accuracy['constraint_violation']['normalized_max']:.2e}")
    print(f"  H-EH3.1 (error < 0.001): {accuracy['hypothesis_results']['H_EH3_1']}")
    print(f"  H-EH3.2 (constraint < 0.0001): {accuracy['hypothesis_results']['H_EH3_2']}")

    # Latency
    print("\n--- Latency Benchmark ---")
    latency = run_latency_benchmark(n_trials=1000)
    overhead = latency['total_ms']['p50'] / max(baseline['p50_ms'], 1e-6)
    print(f"  Keygen: {latency['keygen_ms']:.1f}ms")
    print(f"  Encrypt: p50={latency['encrypt_ms']['p50']:.2f}ms")
    print(f"  Compute: p50={latency['compute_ms']['p50']:.2f}ms")
    print(f"  Decrypt: p50={latency['decrypt_ms']['p50']:.2f}ms")
    print(f"  Total:   p50={latency['total_ms']['p50']:.2f}ms, "
          f"p99={latency['total_ms']['p99']:.2f}ms")
    print(f"  Overhead vs plaintext: {overhead:.0f}x")
    print(f"  H-EH3.3 (total p50 < 100ms): {latency['hypothesis_results']['H_EH3_3']}")

    # Depth study
    print("\n--- Chain Depth Study ---")
    depth = run_depth_study(max_depth=5, n_trials=100)
    for dr in depth['depth_results']:
        if dr.get('error_l_mean') is not None:
            print(f"  Depth {dr['depth']}: "
                  f"error_l_mean={dr['error_l_mean']:.2e}, "
                  f"error_l_max={dr['error_l_max']:.2e}, "
                  f"within 0.001={dr['within_epsilon_001']:.0f}%, "
                  f"within 0.01={dr['within_epsilon_01']:.0f}%")
        else:
            print(f"  Depth {dr['depth']}: ALL FAILED")
    print(f"  H-EH3.4 (depth-3 error < 0.01): {depth['hypothesis_results']['H_EH3_4']}")

    # Summary
    print("\n=== HYPOTHESIS SUMMARY ===")
    all_results = {
        "H-EH3.1 (accuracy < 0.001)": accuracy['hypothesis_results']['H_EH3_1'],
        "H-EH3.2 (constraint < 0.0001)": accuracy['hypothesis_results']['H_EH3_2'],
        "H-EH3.3 (latency p50 < 100ms)": latency['hypothesis_results']['H_EH3_3'],
        "H-EH3.4 (depth-3 < 0.01)": depth['hypothesis_results']['H_EH3_4'],
    }
    for name, result in all_results.items():
        status = "ACCEPTED" if result else "REJECTED"
        print(f"  {name}: {status}")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "timestamp": timestamp,
        "tenseal_version": ts.__version__ if TENSEAL_AVAILABLE else None,
        "baseline": baseline,
        "accuracy": accuracy,
        "latency": latency,
        "depth_study": depth,
        "overhead_factor": overhead,
        "hypothesis_summary": all_results,
    }

    primary = out / "eh3_results.json"
    archive = out / f"eh3_results_{timestamp}.json"
    for path in [primary, archive]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nSaved: {path}")

    return results


if __name__ == "__main__":
    run_all()
