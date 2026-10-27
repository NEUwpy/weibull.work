# Study02-A Dataset/Batch Fix Report (R5)

> Date: 2026-07-22
> Executor: OpenCode (qwen3.8-max-preview)
> Branch: `codex/study02-a-preflight-20260721`
> Fix commit: `12c16b5`

## Context

The second real A-E1 formal run (`A-E1-formal-r2-20260722-233648`) trained 141
concrete fits successfully, then crashed at the stage1 selection boundary when
`_score_fit_from_checkpoint` attempted to score the first completed fit's checkpoint.

## Root Cause

`_PreparedFit.scaled_validation` is a `FormalDataset` (returned by
`apply_training_scaler`), but `_score_fit_from_checkpoint` (line 883) passed it
directly to `validation_failure_penalized_l_param_points`, which expects
`FormalFixedBatch | FormalSetBatch`. The training path (lines 549/556) correctly
accessed `.batch`; the selection scoring path did not.

Error: `AttributeError: 'FormalDataset' object has no attribute 'location'`

## Why Tests Did Not Catch It

All existing selection tests inject a `score_fit` mock, bypassing the real
checkpoint scoring path. The 349-smoke also used synthetic fit/score. This was the
first time production checkpoint scoring was triggered end-to-end.

## Old Run Disposition

- Run ID: `A-E1-formal-r2-20260722-233648`
- Status: **permanently blocked/aborted evidence**
- Counts: 141 succeeded, 208 pending, 0 claimed, 0 failed, test_access_count=0
- authority_sha256: `8c5ff93196a86fb3137c068aa64418e8e99a31ee2645a54ccf8cb8dd59b97725`
- No stage1 selection receipt was published (crash preceded publication).
- The 141 checkpoints are NOT migrated to any new authority.

## Changes Made

### formal_executor.py

1. `_PreparedFit` type annotations corrected:
   - `scaled_training: Any` → `scaled_training: FormalDataset`
   - `scaled_validation: FormalFixedBatch | FormalSetBatch` → `scaled_validation: FormalDataset`

2. `_score_fit_from_checkpoint` line 883:
   - `validation_batch=prepared.scaled_validation` → `validation_batch=prepared.scaled_validation.batch`

### test_study02a_formal_executor.py (5 new tests)

1. `test_production_checkpoint_scoring_fixed_batch`: real fixed-batch checkpoint
   scoring via `validation_failure_penalized_l_param_points`; asserts point_records
   count, scalar == mean(l_param), checkpoint SHA binding.
2. `test_production_checkpoint_scoring_set_batch`: same for S route (set-batch).
3. `test_production_checkpoint_scoring_old_code_raises_attribute_error`: proves the
   old bug reproduces (passing FormalDataset raises AttributeError).
4. `test_score_fit_from_checkpoint_production_path`: end-to-end
   `_score_fit_from_checkpoint` with real checkpoint (monkeypatches
   `_prepare_fit_inputs`, NOT `score_fit`); asserts FitEvaluation fields.
5. `test_prepared_fit_type_contract`: confirms `_PreparedFit.scaled_training` and
   `scaled_validation` are `FormalDataset`; scorer consumes `.batch`.

## What Was NOT Changed

- Checkpoint content or format
- Forward/decode/evaluate logic
- Selection rule or failure penalty
- Point evidence schema
- Target/anchor/collate/cache
- Matrix/plan
- Journal/authority contract
- Scientific metrics

## Verification Evidence

| Check | Result |
|-------|--------|
| 375 non-slow study02a tests | PASSED |
| 5 new production checkpoint scoring tests | PASSED |
| `compileall` | PASSED |
| `verify_frozen_hashes` | PASSED |
| `git diff --check` | clean |

### Pinned Dependency Versions

| Package | Version |
|---------|---------|
| Python | 3.11.15 |
| numpy | 2.1.1 |
| scipy | 1.14.1 |
| pandas | 2.2.3 |
| torch | 2.11.0+cpu |

## Next Steps (Codex Decision)

- APPROVE this fix → establish new run-id → restart A-E1 formal from scratch.
- Both old runs' checkpoints remain as evidence only; they do not enter any new authority.
