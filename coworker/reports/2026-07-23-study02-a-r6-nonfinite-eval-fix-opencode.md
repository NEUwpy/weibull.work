# Study02-A R6 Non-Finite Evaluation Fix Report

> Date: 2026-07-23
> Executor: OpenCode (qwen3.8-max-preview)
> Branch: `codex/study02-a-preflight-20260721`
> Fix commits: `c7333b69` (evaluation + executor gate) + `47bbaa23` (selection-layer gate + attack tests)

## Context

After the Dataset/Batch fix (`12c16b5`), Codex discovered that scoring real r2
checkpoint G3-fit-0000 produced `selection_score=NaN`. Of 2000 point records, 61
had non-finite L_param (59 Inf, 2 NaN). Root cause: `_decode_param_columns` uses
`np.exp()` which overflows to Inf for large model outputs; downstream
`parameter_errors` and L_param computation propagate Inf/NaN into selection.

## Changes Made

### evaluation.py (c7333b69)

In both `evaluate_rows` and `evaluate_rows_per_sample`: after computing component
errors and L_param for a row that passes `_legal()`, check finiteness of all
component errors and L_param. If any is non-finite (overflow from huge-but-finite
estimates, or non-finite decoded estimates), demote the row to failure penalty 10.
`np.errstate(over="ignore", invalid="ignore")` suppresses the expected overflow
warning without clipping results.

### formal_executor.py (c7333b69)

Added `_require_finite_evaluation(fit_id, scalar, point_records)` fail-closed gate
called before FitEvaluation enters selection aggregation. Raises ValueError if
selection_score or any point record numeric field is non-finite.

### selection.py (47bbaa23)

Added `_validate_evaluation_finite(evaluation)` called in
`candidate_supporting_evidence` for every evaluation BEFORE any aggregate, hash,
or ranking computation. Validates:
- succeeded fit: selection_score finite
- failed fit: failure_penalty finite
- all point record numeric fields (l_param, e_beta, e_eta, e_gamma) finite
- aggregate result itself finite (post-computation check)

Both the `score_fit` callback path and the default checkpoint scorer path are
protected by this gate.

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
`47bbaa23`, r2 manifest binds `3beb9f11`). This does not affect checkpoint integrity.

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
| selection_score range | [0.20104490530132632, 6.568274390921318e150] |
| Elapsed | 1600.4s |
| Results SHA256 | 08099d03abe2dfa9fe00b0e519f40b94af7dd1c485863c529a8c3f46d4740fc0 |

The 42,833 failure records are validation samples where the decoded estimate was
non-finite (exp-decode overflow to Inf) or where the resulting component error or
L_param computation produced a non-finite value. All were correctly demoted to
penalty=10 by the R6 fix. No inference is made about which training epoch or
checkpoint stability caused them.

## In-Memory Stage1 Selection Build (F2 route, read-only)

Using the 141 real r2 checkpoints, the F2 route stage1 selection was built
entirely in memory (no artifacts written to r2):

| Metric | Value |
|--------|-------|
| Route | F2 |
| Decision | architecture:A-E1:F2:n10 |
| Candidates | 12 (m01-m12) |
| All aggregates finite | True |
| Winner | m10 (aggregate=0.274154) |
| Top4 | [m10, m06, m02, m12] |
| Selection rule | lowest_aggregate |
| Scoring elapsed | 650.6s |

V route stage1 fits (G3-fit-0227..0262) are in the pending 208 and cannot be
scored from r2.

## Verification

| Check | Result |
|-------|--------|
| 392 non-slow study02a tests | PASSED |
| 21 evaluation tests (incl. 9 R6 + 8 R6 REVISE) | PASSED |
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
