# EH5 -- Sensitivity of the HIPAA Compliance Algebra to Assumed Confidences

**For:** IEEE HealthCom 2026 camera-ready (Reviewer 2: "the Synthea experiments
use assumed per-identifier confidence values ... at least more comprehensive
simulations are needed")
**Date:** 2026-09-11
**Status:** pre-registered before any code was written

## Purpose

EH2 fixes four per-identifier confidences: present identifier belief 0.05,
absent identifier belief 0.95 (PHI classification) or 0.99 (Safe Harbor
never-present categories), removal belief 0.95, and expert belief 0.90 at
trust 0.85. EH5 asks how the paper's conclusions move when those values move.

## Methods (all run through the implemented operators, never closed forms)

A. Grid sweep. Removal confidence p in {0.80, 0.85, 0.90, 0.95, 0.99, 0.999}
   and never-present absence confidence q in {0.90, 0.95, 0.99, 0.999}.
   For the Synthea profile (6 present, 12 absent) compute l_SH with
   safe_harbor_assessment using the Phase B opinion construction
   (present: (p, 0.02, 1 - p - 0.02); absent: (q, 0.005, 1 - q - 0.005)),
   l_ED at expert 0.90 and trust 0.85 (0.765), and t* = l_SH / 0.90.
B. Heterogeneous removal confidences. Per identifier, removal belief
   p_i ~ Beta(mean 0.95, concentration kappa) and absence belief
   q_i ~ Beta(mean 0.99, kappa), kappa in {20, 100}; disbelief kept at
   min(0.02, (1 - l)/2) for removed and min(0.005, (1 - l)/2) for absent
   so that the constraint always holds. 10,000 draws per kappa, seed 42.
   Report median and 5th/95th percentiles of l_SH, and the fraction of
   draws with l_ED > l_SH.
C. Heterogeneous presence. Per draw, each of the 18 categories is present
   with probability equal to its empirical frequency across the 7 FHIR
   resource-type profiles of EH2 E5 (results/eh2_phase_e_results.json);
   present belief ~ Beta(mean 0.05, kappa 100), absent belief ~ Beta(mean
   0.95, kappa 100). 10,000 draws, seed 42. Report the distribution of
   n_present and the median and 95th percentile of l_PHI from
   phi_classification.
D. Base rates. For the Safe Harbor, Expert, BAA chain, and dual-regime
   scenarios of the paper, set every base rate to a in {0.1, 0.3, 0.5,
   0.7, 0.9} and record (l, v, u) and P.

## Pre-registered hypotheses (falsifiable)

- H-EH5.1 The Expert Determination advantage at t = 0.85 (l_ED = 0.765 >
  l_SH) holds for every grid point with p <= 0.95, and fails for at least
  one grid point with p = 0.99 (since 0.99^18 = 0.834 > 0.765).
- H-EH5.2 With kappa = 100 the Expert advantage holds in more than 95% of
  draws; the kappa = 20 fraction is reported descriptively.
- H-EH5.3 Under heterogeneous presence the median l_PHI is below 1e-3 and
  the 95th percentile is below 0.10 (any present identifier keeps
  lawfulness near the present-identifier belief).
- H-EH5.4 Base rates leave (l, v, u) of all four operators unchanged
  (max abs difference below 1e-12 across the sweep) and change only P.

## Outputs

results/eh5_results.json (+ timestamped archive), FINDINGS.md entry,
one sentence in the paper (Section V) with the H-EH5.1 boundary and the
H-EH5.2 fractions.
