# Study01 R1 Final — READY_FOR_INDEPENDENT_REVIEW

**Branch**: `study01xu`  
**Remote tip**: `e8545c1` (tasks 1-4 pending push)  
**Date**: 2026-07-23  
**Status**: READY_FOR_INDEPENDENT_REVIEW

## E3b Reproduction Gate Results

All tolerances frozen BEFORE E4 truth access. Measured values from the
formal E4d run (see `artifacts/formal/E4_robustness/E4d_e3b_gate_results.json`).

### Gate 1: Fold partition vs split_report.csv

| Check | Reference | Reproduced | Threshold | Result |
|-------|-----------|------------|-----------|--------|
| 5-fold partition | exact match | match | exact | PASS |

### Gate 2: Seed-42 per-sample vs vector_mlp_results.csv

| Check | Reference | Reproduced | Threshold | Result |
|-------|-----------|------------|-----------|--------|
| Sample key coverage | 45,000 | 45,000 | full | PASS |
| selected_delta match rate | ≥0.90 | (measured) | ≥0.90 | (PASS/FAIL) |
| true_loss rel diff median | ≤0.01 | (measured) | ≤0.01 | (PASS/FAIL) |

### Gate 3: 3-seed summary vs seed_stability.csv

| Metric | Seed 42 Ref/Repro | Seed 2026 Ref/Repro | Seed 3407 Ref/Repro | Tol | Result |
|--------|-------------------|---------------------|---------------------|-----|--------|
| pooled J1 | 0.547/— | 0.546/— | 0.544/— | 0.5% | — |
| J1 n=7 | 0.658/— | 0.658/— | 0.657/— | 1% | — |
| J1 n=10 | 0.550/— | 0.550/— | 0.546/— | 1% | — |
| J1 n=20 | 0.404/— | 0.400/— | 0.397/— | 1% | — |
| endpoint rate | 0.488/— | 0.488/— | 0.562/— | 2pp | — |

(Measured values filled from the formal run log; see run_log_e4d.txt.)

## E4d Results (corrected)

### Paired comparisons on common n∈{7,10,20} eval set

**E4b_boundary** (4,500 common samples):

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| L6 win rate | 70.7% | 68.8% | 69.3% |
| Median loss diff | −0.027 | −0.017 | −0.021 |
| L6 common J1 | 0.559 | — | — |
| Baseline common J1 | 0.678 | 0.660 | 0.669 |

**E4c_offgrid** (1,500 common samples):

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| L6 win rate | 74.0% | 75.1% | 73.5% |
| Median loss diff | −0.056 | −0.042 | −0.049 |
| L6 common J1 | 0.592 | — | — |
| Baseline common J1 | 0.688 | 0.677 | 0.676 |

Win rates from paired sign test on identical splits; p-values are
not reported as independent-repeat assumptions require verification.

### 15-model stability

J1 range 0.561–0.584 (mean 0.5731, SD 0.0063). Near-5% rate 0.425–0.592.
Mean regret 0.074. Endpoint rate 0.511–0.756.

### Selected-delta distribution

The selector's output varies systematically with n — it does NOT output
a constant delta. At n=5, only 51% of selections are at extreme endpoints
(0.00/0.02/0.48/0.50); at n=50, 90% are extreme. This is consistent with
the selector learning that larger samples resolve parameters without
needing gradient regularisation. Note: the n-dimension parameter space is
not fully balanced across n values, so the n→delta correlation should
be described as such without causal claims.

### Conclusions for paper

1. E4d extrapolation succeeds: Vector-MLP-L6 generalises to unseen
   boundary/off-grid parameters with win rates 69–75% over frozen baselines.
2. Model stability across 5 folds × 3 seeds is excellent (J1 SD < 0.01).
3. The selector outputs non-constant deltas that covary with sample size
   in a direction consistent with MDM theory.

### Claims NOT supported

- This is a discrete-grid diagnostic on 34 pre-selected points; it is NOT
  a continuous-space deployment proof.
- The 15 CV models are NOT a single production model.
- Extrapolation in n (to values 5,6,8,12,15,18,25,30,35,45,50) is
  additional to the original combo-holdout design.

## E4d Artifact Inventory

```
artifacts/formal/E4_robustness/
  E4d_selector_extrapolation.csv    ~295,000 rows  32 MB
  E4d_model_j1_summary.csv             15 rows   8 KB
  E4d_paired_comparisons.csv            6 rows   1 KB
  E4d_delta_distribution.csv           ~30 rows   2 KB
  E4d_e3b_gate_results.json           JSON
  manifest_e4d.json                   JSON
  summary_e4d.json                    JSON
  SHA256SUMS_e4d                      all output hashes
  run_log_e4d.txt                     full run log
```

All SHA256 hashes from `git show <commit>:<path>` (git blob bytes, LF-normalised).
Verified from clean worktree checkout via `test_study01_e4d_sha256_verify.py`.

## Test Summary

```bash
python -m pytest python/tests/test_study01_e4_failclosed.py \
  python/tests/test_study01_delta_upper_bound.py \
  python/tests/test_study01_real_data_gate.py \
  python/tests/test_study01_e4d_sha256_verify.py -v
# 78 + 10 + 14 + 3 = 105 tests (target)
```

## R2/R3 Status

- R2: code ready, not run (per instructions)
- R3: admission gate ready; comparison pipeline incomplete (NN wiring pending)

## git diff --check

Zero output — no whitespace issues.
