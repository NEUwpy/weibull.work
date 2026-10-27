# P4 Duplex REVISE Response — Round 1

**Tip**: `ddc9e593d0fa8dadb651071e9aba820947e054c6`
**Branch**: `study01-p4-formal-compare`
**Tests**: 203 passed, 1 warning (P4 suite: 73 passed)
**P4_FORMAL_AUTHORIZED**: False
**Status**: READY_FOR_INDEPENDENT_REVIEW

## Finding → Commit → Files → Evidence

| Finding | Commit | Changed Files | Targeted Evidence |
|---------|--------|---------------|-------------------|
| P4-R1 | ddc9e593 | run_p4_formal_compare.py | `_execute_track_main`, `_execute_track_p2`, `_execute_track_extrap` implement all 4 tracks × 6 methods. `main()` calls `verify_authorization_contract()` then executes all tracks. |
| P4-R2 | ddc9e593 | run_p4_formal_compare.py, p4_config.py | `verify_authorization_contract()` checks: authorized, clean worktree, APPROVED_PARENT_COMMIT set, output dir absent. `acquire_run_lock()`/`release_run_lock()` for exclusive access. |
| P4-R3 | ddc9e593 | run_p4_formal_compare.py, tests | `verify_sample_keys_identical()` on evaluation layer: all methods keyed by (fold, seed, sample_key). Cross-type alignment enforced. Per-fold seed consistency. Negative tests: `test_cross_type_disjoint_detected`, `test_per_fold_seed_consistency`. |
| P4-R4 | ddc9e593 | run_p4_formal_compare.py, tests | `paired_comparison()` indexes by (sample_key, fold, seed) — no ambiguity. `test_learning_traditional_exact_pairs` asserts 3×15=45 pairs. |
| P4-R5 | ddc9e593 | run_p4_formal_compare.py, p4_config.py, tests | Two-layer: `ESTIMATION_COLUMNS` (no loss) + `EVALUATION_COLUMNS` (with loss/penalty). `build_evaluation_layer()` broadcasts traditional to fold×seed. `ROW_COUNT_CONTRACT` has estimation + evaluation counts. Tests: `TestTwoLayerSchema`. |
| P4-R6 | ddc9e593 | p4_config.py, run_p4_formal_compare.py, tests | `TRACK_SEED_NAMESPACE`: main/extrap=`study01_v1`, param/n=`study01_p2_v1`. `rebuild_mdm_params()` takes namespace. Tests: `TestTrackSeedNamespaces` (5 tests). |
| P4-R7 | ddc9e593 | run_p4_formal_compare.py, tests | `check_prediction_validity()`: finite, beta>0, eta>0, gamma>=0. Applied in all method paths. Tests: `TestPredictionValidity` (6 tests: NaN, Inf, negative beta, zero eta, negative gamma, valid). |
| P4-R8 | ddc9e593 | run_p4_formal_compare.py, tests | `seal_recursive()`: exact allowlist, rejects missing/extra. Atomic writes use PID-unique temps. Checkpoint binds 4 fields (git, input_sha256, authorized, script_sha256). Run lock. Tests: `TestNegativeSealOutputs`, `TestNegativeCheckpointMissing`. |
| P4-R9 | ddc9e593 | run_p4_formal_compare.py, tests | `compute_result_tables()`: Bias/RMSE/MAE, loss quantiles, failure rates, stratification by n/beta, paired win/loss/diff. Tests: `TestResultTables` (2 tests). |
| P4-R10 | ddc9e593 | tests | 73 tests total. Non-vacuous model-first test (`test_model_first_j1_not_merged_j1` uses random losses, asserts median_J1 ≠ pooled). Cross-type disjoint, per-fold seed, prediction validity, two-layer schema, namespace, result table tests added. |

## Deviations

- Track 2/3 fold penalties use placeholder value (2.0) since P2 does not have
  per-fold P99 from 26-delta training losses in the same format as E3b. At formal
  authorization time, the correct penalty source must be bound. This is documented
  in the code and does not affect the execution chain validation.
- Smoke script (`run_p4_smoke.py`) not re-run this round — it uses the legacy
  `run_p3_fair_compare` path which is unchanged. The new two-layer code is tested
  via 73 unit tests. A production-path smoke with the new `main()` requires
  authorization (which remains False).

## Remaining Work for Authorization

1. Set `APPROVED_PARENT_COMMIT` to the reviewed tip in a dedicated authorization commit.
2. Bind Track 2/3 fold penalty source (P2 per-fold P99 or equivalent).
3. Run authorized tiny-fixture end-to-end test (requires temporary authorization toggle in test).
4. Re-run warehouse-outside smoke with new code path (post-authorization or via test fixture).
