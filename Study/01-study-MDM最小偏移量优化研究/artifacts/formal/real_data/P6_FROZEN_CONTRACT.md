# Study01 P6 — Real Data Holdout Validation Contract (FROZEN)

**Contract version**: P6-v1.0-FROZEN
**Freeze date**: 2026-07-25
**Branch**: `study01xu`
**Freeze commit**: `00b282d` (post-P6-preflight-audit)
**Status**: FROZEN — no changes permitted before P7 implementation + P8a run
**Per**: `07-剩余实验目标与规划.md` §4.3, phases P6–P8b

---

## 1. Data Source (FROZEN)

### 1.1 Identity

| Field | Value |
|-------|-------|
| `dataset_id` | `nist-6061-t6-fatigue` |
| Name | NIST 6061-T6 Aluminum Fatigue Life (Birnbaum & Saunders 1958) |
| Source URL | `https://itl.nist.gov/div898/handbook/eda/section4/eda4291.htm` |
| Version | NIST/SEMATECH e-Handbook of Statistical Methods, §1.4.2.9.1 |
| Access date | 2026-07-25 |
| Original file | `BIRNSAUN.DAT` |
| Original SHA256 (LF-normalized) | `7814c533818517d8b824c56213abac2b4076786a13a66d85a8481a32bbccf127` |

### 1.2 License

| Field | Value |
|-------|-------|
| License | NIST Public Domain (U.S. Government work, 17 U.S.C. § 105) |
| License URL | `https://www.nist.gov/open/license` |
| Redistribution | Permitted; data values are factual and not copyrightable |
| Storage in repo | Stored as `lifetimes.csv` and `BIRNSAUN.DAT` in `artifacts/formal/real_data/nist-6061-t6-fatigue/` |

### 1.3 Data Characteristics

| Field | Value |
|-------|-------|
| Material | 6061-T6 aluminum alloy sheeting (rectangular strips) |
| Test condition | Periodic loading, max stress 21,000 psi |
| Stress level | Single constant-amplitude stress level |
| Failure mode | Fatigue rupture (all specimens to complete failure) |
| Units | Thousands of cycles to rupture |
| Total observations | 101 |
| Complete failures | 101 (100%) |
| Censored/runouts | 0 |
| Min lifetime | 370 (thousand cycles) |
| Max lifetime | 2440 |
| Median lifetime | 1416 |

### 1.4 Homogeneity Assessment

| Criterion | Status |
|-----------|--------|
| Same material | ✅ All 6061-T6 aluminum alloy sheeting |
| Same test condition | ✅ Periodic loading, identical waveform |
| Same stress level | ✅ 21,000 psi max stress, single level |
| Single failure mode | ✅ Fatigue rupture only |
| No censoring/runouts | ✅ All 101 are complete failures |
| No mixed stress levels | ✅ Single stress level — NO stratification needed |

### 1.5 Inclusion/Exclusion

- **Inclusion**: All 101 observations. Single stress level, single batch, single failure mode.
- **Exclusion**: None. Zero observations excluded.
- **Transform**: Raw values (thousands of cycles) → `lifetimes.csv` `failure_time` column as-is. No normalization, no unit conversion, no filtering.

### 1.6 Original Reference

> Birnbaum, Z. W. and Saunders, S. C. (1958), "A Statistical Model for Life-Length of Materials", *Journal of the American Statistical Association*, 53(281), pp. 151–160.

### 1.7 Conversion: BIRNSAUN.DAT → lifetimes.csv

**Deterministic, tested conversion**:
1. Parse all numeric tokens from BIRNSAUN.DAT (skip header lines).
2. Extract 101 integer values.
3. Write single-column CSV with header `failure_time`.
4. SHA256 of resulting `lifetimes.csv` (LF-normalized): `43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12`

---

## 2. Admission Gate (FROZEN)

### 2.1 Gate Thresholds

| Parameter | Frozen Value |
|-----------|--------------|
| `MIN_UNCENSORED_LIFETIMES` | 60 |
| `WEIBULL_FIT_MIN_N` | 10 |
| `WEIBULL_FIT_MIN_R2` | 0.70 |
| Weibull fit method | OLS (Bernard ranks, 2-parameter fit, gamma=0) |

### 2.2 Gate Result (Pre-recorded, before any method comparison)

| Metric | Value |
|--------|-------|
| Gate passed | ✅ YES |
| n_loaded | 101 |
| Weibull OLS β̂ | 4.033 |
| Weibull OLS η̂ | 1545.3 |
| Weibull OLS R² | 0.9951 |
| Threshold R² | 0.70 |

### 2.3 Gate Failure Protocol

If gate fails: write `dataset-ineligible.md` and **STOP**. Do not run Default/L2/NN comparison. Do not interpret as selector failure. Do not change data to chase positive results.

---

## 3. Experimental Design (FROZEN)

### 3.1 Training Sample Sizes

```
train_n ∈ {7, 10, 20}
```

### 3.2 Repeated Holdout Splits

| Parameter | Frozen Value |
|-----------|--------------|
| Repeats per `train_n` | **500** |
| Sampling | Without replacement within each repeat |
| Split key | `(train_n, repeat_index)` |
| RNG | `numpy.random.default_rng` |
| Seed namespace | `real_data_holdout_rng_seed` |

### 3.3 Seed Namespace

```
# Frozen seed derivation:
base_seed = 20260725  # P6 freeze date
# For each (train_n, repeat_index):
#   seed = base_seed + train_n * 10000 + repeat_index
# This ensures deterministic, reproducible splits.

rng_seed_train_n_7  = 20260725 + 7  * 10000 = 20260725 + 70000
rng_seed_train_n_10 = 20260725 + 10 * 10000 = 20260725 + 100000
rng_seed_train_n_20 = 20260725 + 20 * 10000 = 20260725 + 200000
```

### 3.4 Identical Splits Guarantee

All three methods (Default, L2, NN) and all 15 NN selector models **must** use the **exact same** (train, holdout) split for each `(train_n, repeat_index)` pair. The split is drawn once; the resulting indices are passed to all methods.

### 3.5 Holdout Definition

| Parameter | Frozen Value |
|-----------|--------------|
| Holdout | All 101 − train_n observations not selected for training |
| Minimum holdout fraction | Not enforced separately — holdout = complement of train sample |
| Holdout for n=7 | 94 observations |
| Holdout for n=10 | 91 observations |
| Holdout for n=20 | 81 observations |

### 3.6 Large-Sample Reference

- Fit Weibull (OLS) to all 101 lifetimes.
- This is the **empirical reference** (β_ref, η_ref), never called "true parameters."
- Used only for auxiliary metric: parameter distance of small-sample estimates from reference.

---

## 4. Methods (FROZEN)

### 4.1 Default (δ = 0.1)

| Parameter | Frozen Value |
|-----------|--------------|
| δ | 0.1 (fixed, no selection) |
| Estimator | `MDM(data).run(offset=0.1)` → (β̂, η̂, γ̂, R², status) |
| Implementation | `python/methods/mdm.py` production code |

### 4.2 L2 (Main-Grid per-n Lookup)

| n | Frozen δ_L2 | Source |
|---|-------------|--------|
| 7 | **0.10** | E1/E2 cross-fit, majority vote across 5 folds (4/5 folds pick 0.10, fold 3 picks 0.08) |
| 10 | **0.10** | E1/E2 cross-fit, unanimous across 5 folds |
| 20 | **0.08** | E1/E2 cross-fit, unanimous across 5 folds |

These values are from main-grid pooled optimization and are frozen. They are **not** re-optimized on real data. The cross-fit analysis is in `artifacts/formal/E1_E2_crossfit/selected_deltas.csv`.

### 4.3 NN (15 E4d-Contract Selectors)

| Parameter | Frozen Value |
|-----------|--------------|
| Architecture | MLP: 3 hidden layers (256, 128, 64) |
| Training data | Main-grid train combos only (not boundary/off-grid/real data) |
| Folds | 5 combo-level folds |
| Seeds | 42, 2026, 3407 |
| Total models | 5 × 3 = **15 selectors** |
| MLP config | alpha=0.0001, lr=0.001, max_iter=300, batch=256, early_stopping=True, val_frac=0.15, n_iter_no_change=20 |
| Input features | 13: n, x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2 |
| Output | 26-dim J1 risk curve over frozen delta grid |
| Scaler | Per-fold from **main-grid train folds only** |

**Critical constraints**:
- All 15 selectors are used. No cherry-picking by E4d results, real data results, or any post-hoc criterion.
- Real small-sample data and holdout data **must not** participate in model training, scaler fitting, or hyperparameter tuning.
- Scalers are frozen from main-grid train folds and applied to real data features without refitting.
- E4d contract: `artifacts/formal/E4_robustness/manifest_e4d.json`

---

## 5. Evaluation Metrics (FROZEN)

### 5.1 Primary Metric: Holdout ECDF Distance

```
D_max = max_x | F_hat_model(x) - F_hat_holdout(x) |
```

where:
- `F_hat_model(x)` = Weibull CDF(β̂, η̂, γ̂) evaluated at all unique observation points
- `F_hat_holdout(x)` = empirical CDF of the holdout sample
- `x` ranges over all unique points in model + holdout combined
- Smaller is better

### 5.2 Auxiliary Metrics

| # | Metric | Definition |
|---|--------|------------|
| M2 | Support-set violation | Indicator: any holdout lifetime < γ̂ (estimated location parameter exceeds minimum observation in holdout). Binary per-repeat. |
| M3 | Parameter distance (β) | \|β̂ − β_ref\| / β_ref |
| M4 | Parameter distance (η) | \|η̂ − η_ref\| / η_ref |
| M5 | Paired win rate (Default vs L2) | Fraction of repeats where L2 D_max < Default D_max |
| M6 | Paired win rate (NN vs L2) | Fraction of repeats where NN median-model D_max < L2 D_max |
| M7 | Paired win rate (NN vs Default) | Fraction of repeats where NN median-model D_max < Default D_max |

### 5.3 Aggregation Rules

- **Within-repeat**: 15 selector predictions → first aggregate by model (median across 500 repeats for that model), then report distribution across 15 models.
- **Cross-repeat**: Each repeat is one paired observation for Default vs L2 vs NN.
- **NO**: treating 15 × 500 = 7,500 predictions as independent observations.
- **NO**: pseudo p-values or significance tests treating repeated splits as independent samples.
- **NO**: calling the full-sample fit "true parameters."

---

## 6. Output Specification (FROZEN)

### 6.1 Output Directory

```
artifacts/formal/real_data/nist-6061-t6-fatigue/
```

### 6.2 Output Files

| File | Content |
|------|---------|
| `real_holdout_results.csv` | Per-repeat, per-method rows with D_max, β̂, η̂, γ̂, support-set violation, etc. |
| `real_holdout_summary.json` | Aggregate metrics across all repeats |
| `real_nn_model_stability.csv` | Per-model (15 rows) aggregated metrics |
| `real_data_manifest.json` | Provenance: config hash, data SHA256, gate result, commit refs |
| `run_log.txt` | Timestamped execution log |

### 6.3 Manifest Requirements

Manifest must record:
- Freeze commit of this contract
- Execution commit at run time
- Data source SHA256 (lifetimes.csv + BIRNSAUN.DAT)
- Gate result (must be pre-recorded)
- Config hash (deterministic hash of all frozen parameters)
- Git dirty status at run time
- Python/sklearn/numpy versions

---

## 7. Stop Conditions (FROZEN)

Execution must stop and report BLOCKER if:

1. Gate fails (n_uncensored < 60, Weibull R² < 0.70, etc.) → `dataset-ineligible`
2. Data source SHA256 does not match frozen manifest
3. Missing required input (source.json, lifetimes.csv, E4d manifest, L2 delta table)
4. Any formal E1/E2/E3/E4/R1/R2 artifact would be overwritten
5. Real data leaks into scaler fitting, model training, or hyperparameter tuning
6. Fewer than 15 E4d selectors available

---

## 8. What Is NOT in This Contract

- ❌ Method comparison results (Default vs L2 vs NN) — deferred to P8a
- ❌ Engineering life quantile metrics — out of scope per §4.3
- ❌ Pseudo p-values or significance tests on repeated splits
- ❌ Claims that full-sample reference = true parameters
- ❌ P7 pipeline implementation — this contract only freezes what to implement
- ❌ New data sources — only nist-6061-t6-fatigue is frozen
- ❌ Continuous parameter space generalization claims
- ❌ Selector deployment claims

---

## 9. Machine-Readable Config

See companion file: `artifacts/formal/real_data/p6_frozen_config.json`

---

## 10. Amendment Rules

- No amendment after P7 implementation begins without a new gate review.
- If a BLOCKER is found during P7, the contract is revised with a new version number and re-frozen before any formal run.
- Changing data source requires a new freeze from scratch.
