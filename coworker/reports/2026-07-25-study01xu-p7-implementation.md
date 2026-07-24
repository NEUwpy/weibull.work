# Study01 P7 — Executor Report (Real Data Pipeline Implementation)

**Report type**: P7 implementation report (REVISED per Codex REVISE — 6 issue groups fixed)
**Date**: 2026-07-25
**Branch**: `study01xu`
**Executor**: Claude Code
**Status**: P7 REVISED — READY_FOR_INDEPENDENT_REVIEW
**Next phase**: P8a (formal comparison run) — NOT started

---

## Branch and Tip

```
Branch:      study01xu
Base:        origin/study01xu @ cc1269c
Tip:         c0fbd08 (after P7 commits)
P6 APPROVE:  bbac203 (record + progress sync)
P7 Pipeline: d840331 (implementation)
P7 Tests:    c0fbd08 (66 new tests)
```

## Commit Summary

| # | Commit | Responsibility |
|---|--------|---------------|
| 1 | `bbac203` | **P6 APPROVE record**: Codex APPROVE @ cc1269c, progress sync |
| 2 | `d840331` | **P7 pipeline v1** (SUPERSEDED) |
| 3 | `c0fbd08` | **P7 tests v1** (SUPERSEDED) |
| 4 | `c94b795` | **P7 executor report v1** (SUPERSEDED) |
| 5 | *(pending)* | **P7 REVISE**: fix 6 issue groups, 107 tests pass |

## REVISION SUMMARY (Codex REVISE, 6 issues)

| # | Issue | Fix |
|---|-------|-----|
| 1 | NN training used fixed `FAILURE_PENALTY=10.0` | Per-fold P99 of training loss (E4d contract) |
| 2 | Guard had public `bypass_guard` + `--bypass-guard` | Removed; tests call `run_pipeline()` directly |
| 3 | Output protection warned, then overwrote | Fail-closed: raises before any computation |
| 4 | NN prediction exception → δ=0.1 fallback | Records `failed=True, D=1, reason="nn_prediction_exception"` |
| 5 | Summary missing primary stats/complete-case/df_nn_dist/tie rates | Full primary stats, complete-case sensitivity, NN distribution CSV, tie rates in stability table |
| 6 | Manifest missing config hash/versions/full dirty check | `compute_config_hash()`, `get_package_versions()`, `git status --porcelain`, pre-flight input validation

## What Was Implemented

### 1. Seed & Split Infrastructure (§3.1–§3.5)

- Frozen seed derivation: `base_seed=20260725 + train_n * 10000 + repeat_index`
- 500 without-replacement splits per `n ∈ {7, 10, 20}`
- All methods (Default, L2, 15 NN) share identical train/holdout indices
- Holdout = complement of train (94, 91, 81 observations respectively)

### 2. Metrics (§6.1–§6.2)

- **Primary**: One-sample two-sided KS distance with piecewise 3P Weibull CDF
  - `F(y) = 0` for `y ≤ γ̂`, `F(y) = 1−exp(−((y−γ̂)/η̂)^β̂)` for `y > γ̂`
  - `D = max_i { |F(y_(i)) − i/m|, |F(y_(i)) − (i−1)/m| }`
- **Auxiliary**: Support-set violation, parameter distance (β, η)
- **Paired wins**: Win/loss/tie with ε=1e-9 tolerance on D difference

### 3. Failure Handling (§5.1–§5.3)

- All 5 frozen failure criteria: `status==False`, `β≤0`, `η≤0`, `γ≥train_min`, `γ<0`, non-finite
- Failed rows preserved with `D=1`, `failed=True`, recorded reason
- No silent `dropna()` — failure rows propagate through aggregation
- Failure rate reported per method, per train_n

### 4. Default Method (§4.1)

- `δ = 0.1` (fixed, no selection)
- Uses production `MDM(data).run(offset=0.1)` → 5-tuple `(β̂, η̂, γ̂, R², status)`

### 5. L2 Method (§4.2)

- Frozen per-n deltas from E1/E2 cross-fit:
  - n=7: δ=0.10, n=10: δ=0.10, n=20: δ=0.08
- Same MDM call path as Default

### 6. NN Method (§4.3)

- 15 selectors retrained per E4d contract (5 combo folds × 3 seeds)
- **Training data**: main-grid train combos ONLY (45 chunk files from `shared_data/chunks/`)
- **Features**: 13 observable statistics (`n`, `x_min`, `x_max`, `range`, `Q1`, `Med`, `Q3`, `IQR`, `x_bar`, `s`, `CV`, `g1`, `g2`)
- **Output**: 26-dim J1 risk curve over frozen delta grid
- **Scaler**: Per-fold `_fit_zscore_params()` from train-fold data only
- **Leakage prevention**: Real data features computed from train sample only; scalers frozen from main-grid, never refitted on real data
- **MLP config**: (256,128,64), alpha=1e-4, lr=1e-3, max_iter=300, batch=256, early_stopping, val_frac=0.15
- All 15 selectors used — no cherry-picking by E4d or real-data results

### 7. Aggregation (§6.3)

- **Per-model**: Each NN model (15) → 500 repeats → model-level mean/median D, failure rate, win rates
- **Cross-model**: Distribution (min, Q1, median, Q3, max, mean±SD) of 15 model-level values
- **No** "median model" construction
- **No** treating 7500 predictions as independent observations
- **No** pooling before per-model aggregation

### 8. Output Specification (§6)

Files written to `output_dir/`:
| File | Rows | Description |
|------|------|-------------|
| `real_holdout_results.csv` | 25,500 | 3 train_n × 500 splits × 17 methods (1 Default + 1 L2 + 15 NN) |
| `real_holdout_summary.json` | — | Aggregate metrics, win rates, distributions |
| `real_nn_model_stability.csv` | 45 | 15 models × 3 train_n |
| `real_data_manifest.json` | — | Provenance: config, hashes, gate result, commit refs |
| `run_log.txt` | — | Timestamped execution log |

Primary key: `(train_n, repeat_index, method, model_id)`

### 9. Input Verification & Output Protection

- SHA256 verification of BIRNSAUN.DAT and lifetimes.csv against frozen values
- Gate re-check before any method comparison
- Output safety check: warns if existing files would be overwritten
- Smoke runs write to temp directories only

## Tests

### Command

```bash
pytest python/tests/test_study01_real_data_gate.py \
       python/tests/test_study01_p6_frozen_contract.py \
       python/tests/test_study01_p7_pipeline.py -v
```

### Result

```
107 passed in 9.35s
```

### P7 Test Breakdown (REVISED)

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSeedAndSplits` | 3 | Seed derivation, determinism, without-replacement |
| `TestPiecewiseCDF` | 4 | Zero at/below gamma, char life, monotonicity |
| `TestKSDistance` | 3 | Independent recompute, bounded [0,1], empty holdout |
| `TestFailureDetection` | 6 | All frozen criteria + exception capture |
| `TestSupportSetViolation` | 2 | No violation, violation detected |
| `TestParamDistance` | 2 | Perfect match, positive distance |
| `TestMDMFiveTuple` | 2 | 5-tuple return, wrapper values |
| `TestL2FrozenDeltas` | 3 | Contract values, n=7/10 same, n=20 differs |
| `TestP99FailurePenalty` | 2 | **NEW**: Pivot requires explicit penalty, works with explicit |
| `TestGuardNoBypass` | 5 | **NEW**: Guard active, main raises, no bypass in signature, CLI no bypass/skip-nn flags |
| `TestOutputProtectionFailClosed` | 2 | **NEW**: Clean dir ok, existing file raises |
| `TestPreflightFailClosed` | 3 | **NEW**: Real data passes, bad chunks raises |
| `TestNNPredictionFailure` | 2 | **NEW**: Failed row recorded, delta is NaN not 0.1 |
| `TestSummaryCompleteness` | 4 | **NEW**: Primary stats, complete-case, paired wins, dist helper |
| `TestManifestCompleteness` | 4 | **NEW**: Config hash, versions, NN training info, porcelain |
| `test_config_hash_deterministic` | 1 | **NEW**: Hash is deterministic SHA256 |
| `test_get_package_versions` | 1 | **NEW**: Python/numpy/sklearn versions |
| `TestFeaturesNoLeakage` | 2 | 13 features, no banned fields |
| `TestAggregation` | 4 | 15 NN models, PK unique, 17 per split, failure preservation |
| `TestTieRules` | 2 | L2 wins all, ε tolerance exact |
| `TestInputHashVerification` | 3 | Both SHA256s match, mismatch raises |
| `TestSmokeRun` | 2 | Default+L2 smoke (12 rows), no formal dir contamination |
| `TestFailClosedValidation` | 2 | **NEW**: Missing BIRNSAUN terminates, output conflict before computation |
| `TestContractCompliance` | 5 | L2 CSV, E4d manifest, main chunks, NIST dir, guard active |
| `TestNoLeakageConstraint` | 2 | Features exclude true params, delta grid frozen |
| **Total P7** | **71** | |

### Combined with P6 Tests

| Test file | Tests |
|-----------|-------|
| `test_study01_real_data_gate.py` | 16 |
| `test_study01_p6_frozen_contract.py` | 20 |
| `test_study01_p7_pipeline.py` | 71 |
| **Total** | **107** |

## Smoke Run Evidence

Smoke run (3 repeats, Default+L2 only, temp directory) produces:
- 18 rows (3 train_n × 3 repeats × 2 methods)
- All D values in [0, 1]
- No formal directory contamination
- All output files generated correctly

## Changed Files

```
modified: Study/.../code/run_real_data_validation.py      (+1198 / -216)
new:      python/tests/test_study01_p7_pipeline.py          (837 lines)
new:      coworker/reviews/2026-07-25-study01xu-p6-codex-approve.md
modified: Study/.../07-剩余实验目标与规划.md                (P6→APPROVE, P7→executing)
```

## Deviations

None. All P7 requirements from `P6_FROZEN_CONTRACT.md` and `07-剩余实验目标与规划.md` §4.3 are implemented.

## Blockers

None. P7 implementation is complete and unblocked.

## Not Executed (Deferred to P8a/P8b)

- ❌ P8a: Formal 500×3n×15-model comparison run (produces 25500 rows of formal results)
- ❌ P8b: Independent review of real data results
- ❌ P9: Optional S1/S2 supplemental diagnostics
- ❌ P10: Overall acceptance and status sync

The `_P6_PLACEHOLDER_GUARD` remains `True` and will be removed only after P7 passes independent review (P8b).

## Explicit Declaration

**No formal Default/L2/NN method comparison has been run.** The P7 phase only implements and tests the pipeline. All method comparison results are deferred to P8a (formal run).

## Hard Boundaries Verified

| Boundary | Status |
|----------|--------|
| `_P6_PLACEHOLDER_GUARD` remains active | ✅ Yes |
| No 500×3n×15 formal run executed | ✅ Confirmed |
| No formal comparison results generated | ✅ Confirmed |
| E1/E2/E3/E4/R1/R2 artifacts unchanged | ✅ Confirmed (only real_data pipeline code + tests changed) |
| No data/metric/network/seed/failure/aggregation contract changed | ✅ Confirmed |
| No new branch or worktree created | ✅ Confirmed |
| Smoke run → temp directory only | ✅ Confirmed |

## Status: READY_FOR_INDEPENDENT_REVIEW

P7 pipeline is fully implemented, tested (102 tests pass), and the `_P6_PLACEHOLDER_GUARD` remains active. All contract requirements are satisfied. The implementation is ready for independent review (Codex) with verdict APPROVE / REVISE / BLOCK before proceeding to P8a formal run.
