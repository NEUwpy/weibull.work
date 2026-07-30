# Study01 P4 Preflight Executor Report

**Executor**: OpenCode (qwen3.8-max-preview)
**Date**: 2026-07-30
**Status**: READY_FOR_P4_FORMAL_AUTHORIZATION

---

## 1. Baseline and Branch

| Item | Value |
|------|-------|
| Repository | D:\weibull |
| Baseline branch | main |
| Baseline commit | fde26eaa9613a0e79c8b8cced134d0e240625635 |
| Work branch | study01-p4-formal-compare |
| Final tip | (see commit chain below) |

## 2. Commit Chain

| # | Hash | Responsibility |
|---|------|----------------|
| 1 | 6219b33a | docs: sync P3 approved+merged status, P4 not yet authorized (6 files) |
| 2 | 52937bca | feat: P4 input audit and run matrix (p4_config.py, 319 lines) |
| 3 | d88ab877 | feat: minimal P4 execution adapter (run_p4_formal_compare.py, 508 lines) |
| 4 | 490731a9 | test: P4 fail-closed contract tests (38 tests, test_p4_formal_compare.py) |
| 5 | 2fd458bf | feat: P4 real smoke script (run_p4_smoke.py, 398 lines) |
| 6 | (this) | docs: final executor report |

## 3. Modified Files per Commit

### Commit 1 (6219b33a) — Status Document Sync
- `README.md` — Study01 status snapshot
- `Study/01-study-MDM最小偏移量优化研究/README.md` — current status block
- `Study/01-study-MDM最小偏移量优化研究/01-证据索引.md` — P3 entry + gap list
- `Study/01-study-MDM最小偏移量优化研究/02-实验协议.md` — protocol status
- `Study/01-study-MDM最小偏移量优化研究/07-剩余实验目标与规划.md` — status line
- `08-更新日志.md` — v2.15 entry

### Commit 2 (52937bca) — Input Audit
- `Study/01-study-MDM最小偏移量优化研究/code/p4_config.py` (new)

### Commit 3 (d88ab877) — Execution Adapter
- `Study/01-study-MDM最小偏移量优化研究/code/run_p4_formal_compare.py` (new)

### Commit 4 (490731a9) — Fail-Closed Tests
- `Study/01-study-MDM最小偏移量优化研究/tests/test_p4_formal_compare.py` (new)
- `Study/01-study-MDM最小偏移量优化研究/code/p4_config.py` (fix: ancestor path detection)

### Commit 5 (2fd458bf) — Smoke Script
- `Study/01-study-MDM最小偏移量优化研究/code/run_p4_smoke.py` (new)

### Commit 6 — This Report
- `coworker/reports/2026-07-30-study01-p4-preflight-opencode.md` (new)

## 4. Track × Method Reuse/Missing Matrix

### Track 1: main_holdout (45 combos × 5 folds holdout)

| Method | Sample Key Source | Reusable Artifact | Missing Compute | Folds/Seeds | Penalty Source | Expected Rows |
|--------|------------------|-------------------|-----------------|-------------|----------------|---------------|
| MDM-Default | E3b sample_features.csv | E3b risk_curves.csv (delta=0 → MDM params) | None (read-only reuse) | N/A | E3b fold P99 | 45×5=225 per fold |
| MDM-Vector-MLP | E3b sample_features.csv | E3b risk_curves.csv + E4 trained model | None (read-only reuse) | 5×3=15 | E3b fold P99 | 225 per model |
| Direct-MLP | E3b sample_features.csv | P3 frozen model architecture | Fresh eval on 45k test samples | 5×3=15 | E3b fold P99 | 225 per model |
| MLE | E3b sample_features.csv | None | Fresh MLE estimation on 45k samples | N/A | E3b fold P99 | 225 per fold |
| LSE | E3b sample_features.csv | None | Fresh LSE estimation on 45k samples | N/A | E3b fold P99 | 225 per fold |
| WMLE | E3b sample_features.csv | None | Fresh WMLE estimation on 45k samples | N/A | E3b fold P99 | 225 per fold |

### Track 2: param_interp (24 combos, P2 v2 approved)

| Method | Sample Key Source | Reusable Artifact | Missing Compute | Folds/Seeds | Penalty Source | Expected Rows |
|--------|------------------|-------------------|-----------------|-------------|----------------|---------------|
| MDM-Default | P2 v2 per_sample.csv | P2 baseline results | None | N/A | P2 fold penalty | 24×repeats |
| MDM-Vector-MLP | P2 v2 per_sample.csv | P2 vector results | None | 5×3=15 | P2 fold penalty | 24×repeats per model |
| Direct-MLP | P2 v2 sample keys | P3 frozen model | Fresh eval (frozen weights) | 5×3=15 | P2 fold penalty | 24×repeats per model |
| MLE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 24×repeats |
| LSE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 24×repeats |
| WMLE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 24×repeats |

### Track 3: n_interp (15 combos, P2 v2 approved)

| Method | Sample Key Source | Reusable Artifact | Missing Compute | Folds/Seeds | Penalty Source | Expected Rows |
|--------|------------------|-------------------|-----------------|-------------|----------------|---------------|
| MDM-Default | P2 v2 per_sample.csv | P2 baseline results | None | N/A | P2 fold penalty | 15×repeats |
| MDM-Vector-MLP | P2 v2 per_sample.csv | P2 vector results | None | 5×3=15 | P2 fold penalty | 15×repeats per model |
| Direct-MLP | P2 v2 sample keys | P3 frozen model | Fresh eval (frozen weights) | 5×3=15 | P2 fold penalty | 15×repeats per model |
| MLE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 15×repeats |
| LSE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 15×repeats |
| WMLE | P2 v2 sample keys | None | Fresh estimation | N/A | P2 fold penalty | 15×repeats |

### Track 4: extrap_diag (E4d extrapolation combos)

| Method | Sample Key Source | Reusable Artifact | Missing Compute | Folds/Seeds | Penalty Source | Expected Rows |
|--------|------------------|-------------------|-----------------|-------------|----------------|---------------|
| MDM-Default | E4d combo grid | None | Fresh sample gen + MDM | N/A | E4d fold penalty | combos×repeats |
| MDM-Vector-MLP | E4d combo grid | E4d selected_delta | Fresh MDM with E4d deltas | 5×3=15 | E4d fold penalty | combos×repeats per model |
| Direct-MLP | E4d combo grid | P3 frozen model | Fresh eval (frozen weights) | 5×3=15 | E4d fold penalty | combos×repeats per model |
| MLE | E4d combo grid | None | Fresh estimation | N/A | E4d fold penalty | combos×repeats |
| LSE | E4d combo grid | None | Fresh estimation | N/A | E4d fold penalty | combos×repeats |
| WMLE | E4d combo grid | None | Fresh estimation | N/A | E4d fold penalty | combos×repeats |

## 5. Input SHA256 and Approved Commits

| Input | SHA256 | Approved Commit |
|-------|--------|-----------------|
| E3b risk_curves.csv | 4b3ad2a3121af616f991b6d91cf15ede1b3f8670f9b97b6baf5527da9ac71ca5 | E3b sealed |
| E3b sample_features.csv | 75bb9a0619f1e04fc8e1cd80451fd5c5a199953f67793740edad06a5ea909e32 | E3b sealed |
| P2 baseline per_sample.csv | 09f419f02304011556d2640eaf794e00ba8ebf1b7bda2f5574d691d00ec94770 | P2 v2 approved |
| P2 vector per_sample.csv | a882034bca1721141f7b4883b4c121efbd4f78f4c66bbc2256477993dc9fab66 | P2 v2 approved |
| P3 config hash | 3a72188c2f39f9903fb7c199b283a7e6a002081102fc8f4308ad1ef3f23e53f2 | P3 approved (ec263120) |

## 6. Test Results

**Command**: `python -m pytest tests/test_p4_formal_compare.py -v`
**Result**: 38 passed in 4.51s

Coverage:
- Six methods sample keys identical (2 tests)
- No valid-only survivor filtering (3 tests)
- Model-first aggregation, 15 models not merged (4 tests)
- Failure penalty consistent with J1 formula (2 tests)
- True params/combo_id/repeat_id not in learning input (4 tests)
- Formal directory not writable when unauthorized (3 tests)
- Smoke path not inside/equal/parent of formal dir (4 tests)
- Existing formal artifacts not overwritable (4 tests)
- Manifest completeness (3 tests)
- Checkpoint drift detection (4 tests)
- Atomic write (3 tests)
- Paired comparison (2 tests)

## 7. Smoke Test Results

**Command**: `python run_p4_smoke.py`
**Output directory**: `D:\weibull-local-artifacts\study01-p4-smoke`
**Total elapsed**: 594.4s
**Direct-MLP training**: 268.0s (59 iterations)
**Vector-MLP training**: 269.4s

### Per-Method Summary (1 fold, 1 seed, 5 test repeats)

| Method | Rows | Failures | Median J1 | Notes |
|--------|------|----------|-----------|-------|
| Direct-MLP | 45 | 0 | 0.4221 | Real PyTorch training + inference |
| MDM-Vector-MLP | 45 | 0 | 0.5399 | Real risk curve → delta → MDM re-estimation |
| MDM-Default | 45 | 0 | 0.5703 | Production MDM (delta=0) |
| WMLE | 45 | 0 | 0.6883 | Production WMLE |
| LSE | 45 | 0 | 1.1730 | Production LSE |
| MLE | 45 | 10 | 1.4870 | Production MLE (10 convergence failures) |

### Smoke Contract Checks (all PASS)
- All six methods present
- Sample key alignment (270 rows, 45 per method)
- No coverage gaps
- failure_penalty > 0 for all rows
- Direct-MLP output constraints (beta>0, eta>0, gamma>=0)
- Model-first aggregation structure (fold/seed populated, model_first_aggregate works)
- Vector-MLP beta correlation: 0.487 (not random noise)
- Full model scale equivariance (c=5.0)
- Atomic write + SHA256 independent verification

### Smoke Output SHA256

| File | SHA256 |
|------|--------|
| p4_smoke_per_sample.csv | af2afff5d22c52197e3569e938acdd15344956f32b9d63f554a762f746c0eca1 |
| p4_smoke_result.json | 2d4a12f3f587f640ab67af502373f638fb462a3d7a2edaa3091319227c9c7933 |

## 8. Environment Versions

| Package | Version |
|---------|---------|
| Python | 3.11.15 |
| numpy | 2.1.1 |
| scipy | 1.14.1 |
| scikit-learn | 1.9.0 |
| torch | 2.11.0+cpu |
| Platform | Windows (win32) |

## 9. Deviations from Protocol

1. **Smoke model-first check**: The formal `verify_model_first_not_merged` requires exactly 15 (fold, seed) groups. Smoke uses 1 fold × 1 seed, so the smoke script verifies structural correctness (fold/seed columns populated, model_first_aggregate returns valid result) instead of the 15-model count. This is a smoke-appropriate adaptation, not a contract change.

No other deviations.

## 10. Items Not Executed

| Item | Reason |
|------|--------|
| P4 formal full run | Not authorized (P4_FORMAL_AUTHORIZED=False) |
| Track 2/3/4 smoke | Smoke validates execution chain on Track 1 only; Tracks 2-4 reuse same code paths |
| Paper result writeback | Out of scope (P5/P6/P7) |
| External paper v0.3 modification | Forbidden by hard boundary |

## 11. Residual Risks

1. **MLE high failure rate**: 10/45 failures in smoke (22%). This is expected behavior for MLE on small-n Weibull estimation and is handled by the failure contract (P99 penalty). Formal run will show whether this pattern holds across all folds.
2. **Track 4 input not yet sealed**: E4d extrapolation combo grid SHA256 is marked "compute at runtime" in p4_config.py. This must be sealed before formal authorization.
3. **CPU-only torch**: Training takes ~270s per model. Full formal run (15 models × 2 learning methods) will require significant compute time (~2+ hours for training alone).

## 12. Hard Boundary Compliance

- [x] P4_FORMAL_AUTHORIZED = False (verified in code and smoke output)
- [x] No formal P4 run started
- [x] No writes to artifacts/formal P4 directory
- [x] P2, E3b, E4d, P8 artifacts unmodified (SHA256 verified)
- [x] No network architecture/seed/method pool/parameter space/metric changes
- [x] No P5/P6/P7 work
- [x] No external paper modification
- [x] No contract adjustment based on smoke direction
- [x] No self-APPROVE

## 13. Declaration

**P4 formal experiments have NOT been run.** This report documents preflight preparation only: status sync, input audit, execution adapter, contract tests, and a minimal real smoke test validating the execution chain. The smoke results do NOT constitute formal comparison conclusions.

## 14. Final Status

**READY_FOR_P4_FORMAL_AUTHORIZATION**

Awaiting Codex independent review and explicit authorization before any formal P4 run.
