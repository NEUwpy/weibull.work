# Study01 P8a — Formal Real Data Execution Contract (FROZEN)

**Contract version**: P8a-v1.0-FROZEN
**Freeze date**: 2026-07-25
**Branch**: `study01xu`
**Status**: FROZEN — no changes permitted during formal run
**References**:
- P6 frozen contract: `P6_FROZEN_CONTRACT.md` v1.1-FROZEN-REVISED (content commit `2ee23a8`)
- P7 Codex APPROVE: `coworker/reviews/2026-07-25-study01xu-p7-codex-approve.md` (tip `d619a40`)
- P7 planning: `07-剩余实验目标与规划.md` §4.3

---

## 1. Run Identity

| Field | Value |
|-------|-------|
| `run_id` | `p8a-{generation_commit_short}` |
| `experiment` | `real_data_holdout_validation_p8a_formal` |
| `formal_output_dir` | `artifacts/formal/real_data/nist-6061-t6-fatigue/` |
| `scratch_pattern` | `artifacts/formal/real_data/nist-6061-t6-fatigue/scratch/run_{timestamp}/` |

## 2. Frozen Inputs

### 2.1 Data

| File | SHA256 (LF-normalized) |
|------|------------------------|
| `BIRNSAUN.DAT` | `7814c533818517d8b824c56213abac2b4076786a13a66d85a8481a32bbccf127` |
| `lifetimes.csv` | `43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12` |
| `p6_frozen_config.json` | (computed at runtime, verified in manifest) |

### 2.2 Configuration

| Parameter | Frozen Value |
|-----------|--------------|
| `base_seed` | `20260725` |
| `train_n_values` | `[7, 10, 20]` |
| `n_repeats` | `500` |
| `default_delta` | `0.1` |
| `L2 deltas` | n=7: 0.10, n=10: 0.10, n=20: 0.08 |
| `tie_tolerance` | `1e-9` |
| `failure_D` | `1.0` |
| `delta_grid` | 26-point frozen grid |
| `NN folds` | 5 combo-level folds |
| `NN seeds` | `[42, 2026, 3407]` |
| `NN models` | 15 (5 folds × 3 seeds) |
| `MLP config` | (256,128,64), alpha=1e-4, lr=1e-3, max_iter=300, batch=256, early_stopping=True, val_frac=0.15 |

### 2.3 Training Inputs

| Input | Binding |
|-------|---------|
| Main-grid 45 chunks | `shared_data/chunks/chunk_0000_mdm.csv` through `chunk_0044_mdm.csv` — all 45 validated by preflight |
| E4d manifest | `E4_robustness/manifest_e4d.json` — 5 folds, 3 seeds, 15 models, train-on-main-grid-train-combos-only |
| L2 delta table | `E1_E2_crossfit/selected_deltas.csv` — majority-vote deltas per n |

## 3. Expected Outputs

### 3.1 Expected Row Counts

| Method | n=7 | n=10 | n=20 | Total |
|--------|-----|------|------|-------|
| Default | 500 | 500 | 500 | 1,500 |
| L2 | 500 | 500 | 500 | 1,500 |
| NN (15 models) | 7,500 | 7,500 | 7,500 | 22,500 |
| **All methods** | **8,500** | **8,500** | **8,500** | **25,500** |

### 3.2 Primary Key

`(train_n, repeat_index, method, model_id)`

### 3.3 Output Files

| File | Expected Rows | Description |
|------|--------------|-------------|
| `real_holdout_results.csv` | 25,500 | Per-repeat, per-method results |
| `real_holdout_summary.json` | — | Aggregate metrics, NN distribution |
| `real_nn_model_stability.csv` | 45 | 15 models × 3 train_n |
| `real_data_manifest.json` | — | Full provenance |
| `run_log.txt` | — | Timestamped execution log |

### 3.4 NN Model Stability

- 45 rows: 15 models × 3 train_n values
- Columns: train_n, method, model_id, n_repeats, n_failed, failure_rate, mean_D, median_D, std_D, mean_support_set_violation_rate, n_support_set_unknown, mean_param_dist_beta, mean_param_dist_eta, win_rate_vs_default, win_rate_vs_l2, tie_rate_vs_default, tie_rate_vs_l2

## 4. Transactional Output Protocol

1. **Pre-check**: `check_output_safety(formal_dir)` — fail if any 5 contracted files exist in formal dir.
2. **Scratch**: Write all outputs to `scratch/run_{timestamp}/` under formal dir.
3. **Verify**: After pipeline completes, verify all 5 files exist in scratch and have expected row counts.
4. **Promote**: Move files from scratch to formal dir one at a time.
5. **Clean**: Remove scratch directory.

If the run fails at any point:
- Scratch dir contains partial results — does NOT pollute formal dir.
- Delete scratch dir and re-run from same frozen commit.
- NO partial promotion.

## 5. Generation Environment Requirements

1. **Git tree clean**: `git status --porcelain` must be empty.
2. **P7 APPROVE record exists**: `coworker/reviews/2026-07-25-study01xu-p7-codex-approve.md` must be present.
3. **P8A_FORMAL_AUTHORIZED**: Guard constant must be `True` (narrow, auditable, only in this commit).
4. **Execution commit**: Recorded in manifest as `generation_code_commit`.

## 6. Failure and Recovery Rules

### 6.1 Run Failure

If the formal run fails:
1. Log the failure with full traceback.
2. Preserve scratch directory for diagnosis.
3. **Do NOT** change data, seeds, models, metrics, failure rules, or any contract term.
4. Determine if safe re-run is possible from the same frozen commit.
5. If safe: delete scratch, re-run.
6. If unsafe (e.g., data corruption, environmental issue): trigger hard stop.

### 6.2 Partial Output

- Formal directory must NEVER contain partial results.
- If scratch promotion is interrupted, manually clean up and re-run.
- The transactional protocol ensures formal dir is all-or-nothing.

### 6.3 Restart

- Always restart from the frozen generation commit.
- Delete any scratch directories before restarting.
- Re-verify git cleanliness before each attempt.

## 7. Manifest Requirements

Manifest must record:
- `experiment`: `real_data_holdout_validation_p8a_formal`
- `contract_version`: `P8a-v1.0-FROZEN`
- `p6_contract_version`: `P6-v1.1-FROZEN-REVISED`
- `p6_content_commit`: `2ee23a8`
- `p7_approve_tip`: `d619a40`
- `generation_code_commit`: (actual commit at run time)
- `git_dirty`: `false` (verified before run)
- `config_hash`: deterministic SHA256 of all frozen params
- `frozen_config_sha256`: SHA256 of p6_frozen_config.json
- `data_sha256`: BIRNSAUN.DAT + lifetimes.csv
- `versions`: Python, numpy, scikit-learn
- `nn_training`: 15 selectors with per-fold P99 failure penalty
- `exact_command`: the CLI invocation used
- `start_time`, `end_time`, `elapsed_seconds`
- `recovery_attempts`: 0 if first attempt succeeded
- `output_hashes`: SHA256 of each output file

## 8. Hard Stop Conditions

1. Git tree not clean at generation time.
2. Input SHA256 mismatch.
3. Admission gate failure.
4. Preflight validation failure (chunks, E4d manifest, L2 table).
5. Formal output directory already contains results.
6. Data leakage detected (real data in training/scaler).
7. Fewer than 15 NN selectors trained.
8. Row count mismatch after pipeline completion.
9. Primary key duplicates.
10. Run failure that cannot be safely recovered.

## 9. What Is NOT in This Contract

- Results interpretation or claims
- Method comparison conclusions
- P8b independent review
- P9/P10 subsequent phases
- Amendment of P6 scientific contract
- Adding new seeds, datasets, models, or metrics
