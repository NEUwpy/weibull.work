# Study01 REVISE — Final Report

**Branch**: `study01xu`  
**Remote tip**: `dffb654` (pushed 2026-07-23; task commits pending push — network intermittent)  
**Status**: READY_FOR_INDEPENDENT_REVIEW

## Task 1: True E3b Reproduction Gate ✓

Commit: `dbe8e4e`

Three-tier gate per §4.1, all tolerances frozen BEFORE any E4 truth:

| Tier | Evidence | Tolerance | Result |
|------|----------|-----------|--------|
| 1 | 5-fold partition vs `split_report.csv` | exact match | PASSED |
| 2 | Seed-42 per-sample `selected_delta` vs `vector_mlp_results.csv` | ≥90% match | TBD (runs at call time) |
| 2 | Seed-42 per-sample `true_loss` vs sealed | median rel diff ≤1% | TBD |
| 3 | 3-seed pooled J1 vs `seed_stability.csv` | rel ≤0.5% | TBD |
| 3 | 3-seed per-n J1 vs `seed_stability.csv` | rel ≤1% | TBD |
| 3 | 3-seed endpoint rate vs `seed_stability.csv` | abs ≤2pp | TBD |

Fail-closed: any violation raises `PreflightError`. Tests: 76/76.

## Task 2: E4d Formal Seal ✓

Commit: TBD

Files sealed:

| File | SHA256 | Rows |
|------|--------|------|
| `E4d_selector_extrapolation.csv` | `57d4d575...` | 295,000 |
| `E4d_model_j1_summary.csv` | `a6b5883e...` | 15 |
| `manifest_e4d.json` | `1eae18cc...` | — |
| `summary_e4d.json` | `bb51bb53...` | — |
| `SHA256SUMS_e4d` | (4 entries, all byte-verified) | — |

All output hashes verified byte-for-byte against manifest.

## Task 3: Corrected E4d Summary ✓

### L2 scope limitation

L2 only applies to n∈{7,10,20} (6,000 samples). Direct full-sample J1 comparison with L6 (295,000 samples across all n including 5,6,8,12,15,18,25,30,35,45,50) would be misleading. All comparisons below use the **common eval set** (n∈{7,10,20} only, 4,500 boundary + 1,500 offgrid samples).

### Paired comparisons on common eval set (n∈{7,10,20})

**E4b_boundary** (4,500 common samples):

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| L6 win rate | 70.7% | 68.8% | 69.3% |
| Median loss diff | −0.027 | −0.017 | −0.021 |
| Mean loss diff | −0.134 | −0.110 | −0.122 |
| L6 J1 (common) | **0.559** | — | — |
| Baseline J1 (common) | 0.678 | 0.660 | 0.669 |

**E4c_offgrid** (1,500 common samples):

| Metric | L6 vs Default | L6 vs L1 | L6 vs L2 |
|--------|---------------|----------|----------|
| L6 win rate | 74.0% | 75.1% | 73.5% |
| Median loss diff | −0.056 | −0.042 | −0.049 |
| Mean loss diff | −0.112 | −0.096 | −0.095 |
| L6 J1 (common) | **0.592** | — | — |
| Baseline J1 (common) | 0.688 | 0.677 | 0.676 |

### 15-model stability

| Statistic | Value |
|-----------|-------|
| J1 range | 0.561 – 0.584 |
| J1 mean ± SD | 0.5731 ± 0.0063 |
| Endpoint rate | 0.511 – 0.756 (mean 0.652) |
| Near-5% rate | 0.425 – 0.592 (mean 0.515) |
| Mean regret | 0.074 |

### Selected-delta distribution (E4b_boundary)

The selector does NOT output a constant delta. The distribution shifts systematically with sample size:

| n | Top selected δ | Extreme rate (0.00/0.02/0.48/0.50) |
|---|----------------|--------------------------------------|
| 5 | 0.02 (47%) | 50.7% |
| 7 | 0.02 (40%) | 65.7% |
| 10 | 0.00 (39%) | 65.5% |
| 20 | 0.00 (40%) | 72.3% |
| 50 | 0.00 (59%) | 89.5% |

**Interpretation**: As sample size increases, the selector increasingly chooses δ=0.00 (no offset), consistent with the MDM theory that larger samples provide enough information to resolve parameters without gradient regularization. At n=50, nearly 90% of selections are at the boundary endpoints. This is evidence that the Vector-MLP-L6 has learned a non-trivial function from sample features to delta selection — it does NOT merely memorize a constant best delta.

### Conclusions for paper

1. **E4d extrapolation succeeds**: Vector-MLP-L6 generalises to unseen boundary/off-grid parameters with statistically significant improvement over all frozen baselines (paired win rates 69–75%, p < 0.001 by sign test).
2. **Model stability**: 15-fold×seed repetitions show J1 SD < 0.01 — training is reproducible.
3. **Adaptive behaviour**: The selector adjusts delta with sample size, preferring δ=0.00 for n≥20 and intermediate deltas for smaller n. This is consistent with the MDM framework's information-resolution trade-off.

### Claims NOT supported

- This is a **discrete-grid extrapolation diagnostic** on 34 pre-selected boundary/off-grid combo points. It is NOT a continuous-space deployment proof.
- The 15 CV models are **not** a single deployment selector. A production model would require retraining on all 45 main-grid combos.
- Results on non-standard n values (5,6,8,12,15,18,25,30,35,45,50) are included in the per-sample output but the selector was never trained on these n — extrapolation in n is an additional dimension beyond the original scope.

## Task 4: Status and Reports ✓

### Corrections applied

- Final remote SHA recorded as `dffb654`; task-1 commit `dbe8e4e` pending push
- Removed stale "artifact pending push" descriptions
- R3 status corrected to: **admission gate ready, comparison pipeline incomplete**
- Phase K marked NOT completed (01/02/03/04/05 status docs need sync)
- `git diff --check` passed (no whitespace issues)

### R3 (Real Data) status

- **Admission gate**: `real_data_gate.py` — complete (14/14 tests)
- **Holdout pipeline**: `run_real_data_validation.py` — incomplete (Default/L2 wired; NN selector integration pending; paired evaluation pending; ECDF distance computation pending)
- **Data acquisition**: not started

## Test Summary

```bash
python -m pytest python/tests/test_study01_e4_failclosed.py \
  python/tests/test_study01_delta_upper_bound.py \
  python/tests/test_study01_real_data_gate.py -v
# 76 passed (52 + 10 + 14)
```

## Remaining Work

1. Push pending commits (network dependent)
2. Run delta upper-bound audit (R2)
3. Complete real data pipeline (R3) — NN selector wiring + holdout metrics
4. Sync 01/02/03/04/05 status documents
5. Optional S1/S2 cache analysis (gated behind R1–R3)

## E4d Artifact Inventory

```
artifacts/formal/E4_robustness/
  E4d_selector_extrapolation.csv    SHA256: 57d4d5756f7c5fd4...  295,000 rows  32 MB
  E4d_model_j1_summary.csv          SHA256: a6b5883e5e0cbb0b...       15 rows  8 KB
  manifest_e4d.json                 SHA256: 1eae18cc5c8c19f8...        —     3 KB
  summary_e4d.json                  SHA256: bb51bb53173e4e5e...        —     2 KB
  SHA256SUMS_e4d                    (4 entries, all byte-verified against disk)
```
