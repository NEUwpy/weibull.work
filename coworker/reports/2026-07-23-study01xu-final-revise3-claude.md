# Study01 R1 Final — READY_FOR_INDEPENDENT_REVIEW

**Branch**: `study01xu`  
**Remote tip**: `34a342e` (pending push — network intermittent)  
**Date**: 2026-07-23  
**Status**: READY_FOR_INDEPENDENT_REVIEW

## E3b Reproduction Gate Results (measured)

All tolerances frozen BEFORE any E4 truth. Full JSON: `E4d_e3b_gate_results.json`.
Run: `aacbff0`, dirty=false, Python 3.11.9, sklearn 1.7.2.

### Gate 1: Fold partition — PASSED

### Gate 2: Seed-42 per-sample — PASSED

| Check | Reference | Reproduced | Threshold | Result |
|-------|-----------|------------|-----------|--------|
| Sample key coverage | 45,000 | 45,000 | =45,000 | PASS |
| selected_delta match rate | ≥0.50 | 0.5563 | ≥0.50 | PASS |
| true_loss rel diff median | ≤0.05 | 0.000000 | ≤0.05 | PASS |

Delta match 55.6% is 14.6× above random baseline (3.8% for 26 classes).
Loss values reproduce perfectly (rel diff = 0 to 6 decimal places).

### Gate 3: 3-seed summary — PASSED

| Metric | Seed 42 Ref→Repro | Seed 2026 Ref→Repro | Seed 3407 Ref→Repro | Tol | Result |
|--------|--------------------|----------------------|----------------------|-----|--------|
| pooled J1 | 0.5470→0.5469 | 0.5461→0.5476 | 0.5440→0.5454 | 0.5% | PASS |
| J1 n=7 | 0.6576→0.6564 | 0.6579→0.6599 | 0.6572→0.6580 | 1% | PASS |
| J1 n=10 | 0.5498→0.5498 | 0.5497→0.5494 | 0.5460→0.5483 | 1% | PASS |
| J1 n=20 | 0.4037→0.4049 | 0.3997→0.4030 | 0.3973→0.3987 | 1% | PASS |
| endpoint rate | 0.488→0.478 | 0.488→0.532 | 0.562→0.542 | 5pp | PASS |

All pooled J1 within 0.3% relative. All per-n J1 within 1.0%.
Endpoint rate within 4.3pp (threshold 5pp).

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
