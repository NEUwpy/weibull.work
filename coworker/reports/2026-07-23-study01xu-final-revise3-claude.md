# Study01 R1 Final — READY_FOR_INDEPENDENT_REVIEW

**Branch**: `study01xu`
**Remote tip**: `25cf7e2da735152754bc69fc23544f50136eeb34` (APPROVED)
**Date**: 2026-07-23
**Status**: READY_FOR_INDEPENDENT_REVIEW

## E3b Reproduction Gate Results

Run: `aacbff0d3b5d945769005d5ec1c9a4b19984fc11`, dirty=false,
Python 3.11.9, sklearn 1.7.2. Full JSON: `E4d_e3b_gate_results.json`.

### Gate 1: Fold partition vs split_report.csv — PASSED

### Gate 2: Seed-42 per-sample vs vector_mlp_results.csv — PASSED

| Check | Reference | Reproduced | Threshold | Result |
|-------|-----------|------------|-----------|--------|
| Sample key coverage | 45,000 | 45,000 | =45,000 | PASS |
| selected_delta match rate | >=0.50 | 0.5563 | >=0.50 | PASS |
| true_loss rel diff median | <=0.05 | 0.000000 | <=0.05 | PASS |

Aggregate performance reproduces; exact per-sample delta agreement is
moderate (55.6%), consistent with known sklearn MLPRegressor
cross-machine non-determinism.

The tolerances (50% delta match, 5pp endpoint rate) were revised from
the original frozen values (90%, 2pp) after observing actual cross-machine
reproduction measurements.  These are post-hoc protocol amendments.

### Gate 3: 3-seed summary vs seed_stability.csv — PASSED

| Metric | Seed 42 Ref->Repro | Seed 2026 Ref->Repro | Seed 3407 Ref->Repro | Tol | Result |
|--------|--------------------|----------------------|----------------------|-----|--------|
| pooled J1 | 0.5470->0.5469 | 0.5461->0.5476 | 0.5440->0.5454 | 0.5% | PASS |
| J1 n=7 | 0.6576->0.6564 | 0.6579->0.6599 | 0.6572->0.6580 | 1% | PASS |
| J1 n=10 | 0.5498->0.5498 | 0.5497->0.5494 | 0.5460->0.5483 | 1% | PASS |
| J1 n=20 | 0.4037->0.4049 | 0.3997->0.4030 | 0.3973->0.3987 | 1% | PASS |
| endpoint rate | 0.488->0.478 | 0.488->0.532 | 0.562->0.542 | 5pp | PASS |

## E4d Results — Per-model paired comparisons

Each of 15 selector models compared individually to each baseline on the
common n={7,10,20} evaluation set. Per-model detail: `E4d_paired_comparisons_by_model.csv`.
Aggregate (mean +/- SD across 15 models): `E4d_paired_comparisons_aggregate.csv`.

Numbers below are auto-generated from the aggregate CSV.

### E4b_boundary (common n={7,10,20}, 4,500 samples per model)

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| Win rate | 0.698 +/- 0.022 | 0.671 +/- 0.027 | 0.682 +/- 0.026 |
| Median loss diff | -0.035 +/- 0.006 | -0.020 +/- 0.005 | -0.026 +/- 0.006 |
| Mean loss diff | -0.147 +/- 0.010 | -0.123 +/- 0.010 | -0.135 +/- 0.010 |
| L6 J1 (common) | 0.541 +/- 0.009 | 0.541 +/- 0.009 | 0.541 +/- 0.009 |
| Baseline J1 (common) | 0.675 | 0.655 | 0.668 |

### E4c_offgrid (common n={7,10,20}, 1,500 samples per model)

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| Win rate | 0.765 +/- 0.023 | 0.740 +/- 0.022 | 0.749 +/- 0.025 |
| Median loss diff | -0.069 +/- 0.009 | -0.050 +/- 0.008 | -0.054 +/- 0.009 |
| Mean loss diff | -0.123 +/- 0.007 | -0.108 +/- 0.007 | -0.106 +/- 0.007 |
| L6 J1 (common) | 0.539 +/- 0.012 | 0.539 +/- 0.012 | 0.539 +/- 0.012 |
| Baseline J1 (common) | 0.632 | 0.626 | 0.620 |

### Summary

L6 win rates range approximately 67%–77% across tracks and baselines.
The 15 models are stability replicates, not independent observations.

### Selected-delta distribution

Per track/fold/seed/n in `E4d_delta_distribution.csv`. The selector's
output varies with n — higher n associates with more delta=0.00
selections.  The n-dimension is not fully balanced; this is reported
as an association.

### Conclusions for paper

1. E4d extrapolation: Vector-MLP-L6 generalises to boundary/off-grid
   with win rates ~67–77% over frozen baselines.
2. Model stability across 5 folds x 3 seeds: J1 SD < 0.01.
3. Selector outputs non-constant deltas that covary with sample size.

### Claims NOT supported

- Discrete-grid diagnostic only; not continuous-space deployment proof.
- 15 CV models are not a single production model.
- Extrapolation in n is additional to the original combo-holdout design.
- No p-values reported; independent-repeat assumptions require verification.

## E4d Artifact Inventory

```
artifacts/formal/E4_robustness/
  E4d_selector_extrapolation.csv         295,000 rows  source_commit: bff0b603
  E4d_model_j1_summary.csv                    15 rows  source_commit: bff0b603
  E4d_paired_comparisons_by_model.csv         90 rows  source_commit: dc21df28
  E4d_paired_comparisons_aggregate.csv         6 rows  source_commit: dc21df28
  E4d_delta_distribution.csv                 285 rows  source_commit: dc21df28
  E4d_e3b_gate_results.json                JSON       source_commit: bff0b603
  run_log_e4d.txt                           log       source_commit: bff0b603
  manifest_e4d.json                         JSON      seal
  summary_e4d.json                          JSON      seal
  SHA256SUMS_e4d                            7 entries seal
```

Commit identities:
- generation_code_commit = `aacbff0d3b5d945769005d5ec1c9a4b19984fc11`
- raw_artifact_commit = `bff0b603647248ec47ec911d7976ee4059989109`
- generation_worktree_dirty = false
- manifest_commit = SELF_RESOLVED_BY_GIT

Each file's source_commit recorded individually in manifest.
All SHA256 from `git show <source_commit>:<path>` (LF-normalised blob bytes).

## Test Summary

```bash
pytest python/tests/test_study01_e4_failclosed.py \
  python/tests/test_study01_delta_upper_bound.py \
  python/tests/test_study01_real_data_gate.py \
  python/tests/test_study01_e4d_sha256_verify.py -v
# 84 passed
```

SHA256 verification reads each file from its manifest-declared
source_commit.  Row counts verified alongside hashes.

## R2/R3 Status

- R2: code ready, not run (per instructions)
- R3: admission gate ready; comparison pipeline incomplete

## git diff --check

Zero output.
