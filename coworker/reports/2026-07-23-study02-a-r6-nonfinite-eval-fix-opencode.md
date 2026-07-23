# Study02-A R6 Non-Finite Evaluation Fix Report

> Date: 2026-07-23
> Executor: OpenCode (qwen3.8-max-preview)
> Branch: `codex/study02-a-preflight-20260721`
> Fix commit: `c7333b69`

## Context

After the Dataset/Batch fix (`12c16b5`), Codex discovered that scoring real r2
checkpoint G3-fit-0000 produced `selection_score=NaN`. Of 2000 point records, 61
had non-finite L_param (59 Inf, 2 NaN). Root cause: `_decode_param_columns` uses
`np.exp()` which overflows to Inf for large model outputs; downstream
`parameter_errors` and L_param computation propagate Inf/NaN into selection.

## Changes Made

### evaluation.py

In both `evaluate_rows` and `evaluate_rows_per_sample`: after computing component
errors and L_param for a row that passes `_legal()`, check finiteness of all
component errors and L_param. If any is non-finite (overflow from huge-but-finite
estimates), demote the row to failure penalty 10. `np.errstate(over="ignore",
invalid="ignore")` suppresses the expected overflow warning without clipping.

### formal_executor.py

Added `_require_finite_evaluation(fit_id, scalar, point_records)` fail-closed gate
called before FitEvaluation enters selection aggregation. Raises ValueError if
selection_score or any point record numeric field is non-finite.

### What Was NOT Changed

- Checkpoint content or model forward/decode logic
- Selection rule or failure penalty constant (10.0)
- Point evidence schema
- Target/anchor/collate/cache
- Matrix/plan/journal/authority contract
- Scientific metrics

## r2 Run Integrity Audit (read-only)

| Check | Result |
|-------|--------|
| Structure (claims/events/outputs/receipts) | 141/283/141/141 |
| Event chain (283 events, hash + sequence) | VALID |
| Claim fit_ids == succeeded fit_ids | OK |
| Receipt fit_ids == succeeded fit_ids | OK |
| 141 x 3 output files present, non-empty | OK |
| Receipt SHA (checkpoint/fit_status/evidence) | ALL VERIFIED |
| Plan 349 rows, first 141 == succeeded | OK |
| scheduler_state: 141/208/0/0 | OK |
| test_access_count | 0 |
| authority_sha256 | 8c5ff931...7725 |

Note: `_rebuild_authority` code-drift check is expected to fail (current code is
`c7333b69`, r2 manifest binds `3beb9f11`). This does not affect checkpoint integrity.

## 141-Checkpoint Read-Only Scoring Results

| Metric | Value |
|--------|-------|
| Checkpoints scored | 141/141 |
| All selection_scores finite | True |
| All point record numerics finite | True |
| scalar == mean(records) for all | True |
| Total point records | 1,480,800 |
| Failure records (penalty=10) | 42,833 (2.9%) |
| Fits with >0 failure records | 30/141 |
| selection_score range | [0.201045, 6.57e307] |
| Elapsed | 1600.4s |
| Results SHA256 | 08099d03abe2dfa9fe00b0e519f40b94af7dd1c485863c529a8c3f46d4740fc0 |

The 42,833 failure records are validation samples where the model's exp-decode
overflowed to Inf, correctly demoted to penalty=10 by the R6 fix. The 30 affected
fits are predominantly early-training checkpoints with unstable weights.

## Verification

| Check | Result |
|-------|--------|
| 384 non-slow study02a tests | PASSED |
| 13 evaluation tests (incl. 10 R6) | PASSED |
| compileall | PASSED |
| verify_frozen_hashes | PASSED |
| git diff --check | clean |

### Pinned Dependency Versions

| Package | Version |
|---------|---------|
| Python | 3.11.15 |
| numpy | 2.1.1 |
| scipy | 1.14.1 |
| pandas | 2.2.3 |
| torch | 2.11.0+cpu |

## Old Run Disposition

- r1 `A-E1-formal-20260721-154250`: permanently blocked/aborted (39 succeeded)
- r2 `A-E1-formal-r2-20260722-233648`: permanently blocked/aborted (141 succeeded)
- No checkpoints migrated. No selection artifacts published. No new formal started.

## Next Steps (Codex Decision)

- APPROVE R6 fix -> establish new run-id -> restart A-E1 formal from scratch.
- Both old runs remain as evidence only.
