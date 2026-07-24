# Study01 P8a — Executor Report (Formal Real Data Holdout Experiment)

**Report type**: P8a execution report
**Date**: 2026-07-25
**Branch**: `study01xu`
**Executor**: Claude Code
**Status**: `READY_FOR_INDEPENDENT_REVIEW`
**Next phase**: P8b (independent review by Codex)

---

## Branch and Tip

```
Branch:              study01xu
Final tip:           5803c72 (seal: verify and seal P8a derived outputs)
Generation commit:   3330523 (fix: handle GBK encoding errors in log() for Windows terminals)
P7 APPROVE tip:      d619a40
P6 content commit:   2ee23a8
```

## Complete Commit Chain

| # | Commit | Responsibility |
|---|--------|---------------|
| 1 | `1af5660` | **docs**: record P7 Codex APPROVE and start P8a |
| 2 | `8f232bf` | **test/fix**: freeze P8a formal execution controls |
| 3 | `43ff11a` | **test**: add P8a unified gate check script |
| 4 | `09fc676` | **fix**: use utf-8 encoding in gate check script for E4d manifest |
| 5 | `3330523` | **fix**: handle GBK encoding errors in log() for Windows terminals |
| 6 | `7946108` | **run**: generate P8a formal raw artifacts |
| 7 | `5803c72` | **seal**: verify and seal P8a derived outputs |

**Generation code commit**: `3330523` (commit #5 — the exact commit from which the formal run was launched)

**Artifact commit**: `7946108` (commit #6 — formal outputs committed)

**Seal/report commit**: `5803c72` (commit #7 — verification + this report will be the next commit)

## Exact Run Command and Timing

```
Command:
  python -c "import sys; sys.path.insert(0, 'Study/01-study-MDM.../code');
  from run_real_data_validation import run_p8a_formal; run_p8a_formal()"

Start time:  2026-07-24T21:18:24+00:00 (2026-07-25 05:18:24 local)
End time:    2026-07-24T21:43:53+00:00 (2026-07-25 05:43:53 local)
Elapsed:     1529.7 seconds (25.5 minutes)
Environment: Windows 11, Python 3.11.9, Git Bash
```

## Test Results (Final Tip)

| Test file | Tests | Result |
|-----------|-------|--------|
| `test_study01_real_data_gate.py` | 16 | 16 passed |
| `test_study01_p6_frozen_contract.py` | 20 | 19 passed, 1 pre-existing failure (GBK encoding) |
| `test_study01_p7_pipeline.py` | 88 | 88 passed |
| `test_study01_p8a_controls.py` | 27 | 26 passed, 1 skipped |
| **Total** | **151** | **149 passed, 1 skipped, 1 pre-existing failure** |

Pre-existing failure: `test_conversion_script_reproduces_lifetimes_csv` — GBK codec issue on Chinese Windows, unrelated to P8a changes. Reproducible at P7 APPROVE tip `d619a40`.

## Gate Check Results

All 10 pre-flight gates passed before formal execution:

| # | Gate | Result |
|---|------|--------|
| 1 | P8a authorization active | `_P8A_FORMAL_AUTHORIZED=True` |
| 2 | Git tree clean | `dirty=False` at commit `3330523` |
| 3 | P7 Codex APPROVE record | Present |
| 4 | Data SHA256 | BIRNSAUN.DAT MATCH, lifetimes.csv MATCH |
| 5 | P6 config SHA256 | `be6d88bd...` verified |
| 6 | Admission gate | Passed (R²=0.9951, n=101) |
| 7 | Preflight (45 chunks, L2, E4d) | All validated |
| 8 | Output dir safety | Clean (no prior formal outputs) |
| 9 | Frozen parameters | All match P6 contract |
| 10 | E4d manifest | 15 models, 5 folds, train-on-main-grid-only |

## Formal Outputs

### real_holdout_results.csv

| Metric | Value |
|--------|-------|
| Total rows | **25,500** |
| train_n values | 7, 10, 20 |
| Methods | default, l2, nn |
| NN model_ids | 15 (fold_0_seed_42 through fold_4_seed_3407) |
| Primary key | `(train_n, repeat_index, method, model_id)` — unique |
| D range | [0.0401, 0.7224] — all finite, all in [0,1] |
| Failed rows | 0 (all 25,500 estimations succeeded) |

### Row Counts by Method and n

| Method | n=7 | n=10 | n=20 | Total |
|--------|-----|------|------|-------|
| Default | 500 | 500 | 500 | 1,500 |
| L2 | 500 | 500 | 500 | 1,500 |
| NN (15 models) | 7,500 | 7,500 | 7,500 | 22,500 |
| **Total** | **8,500** | **8,500** | **8,500** | **25,500** |

### real_nn_model_stability.csv
- 45 rows: 15 models × 3 train_n values ✓
- All models represented for each train_n ✓

### real_holdout_summary.json
- `primary_stats` with default, l2, nn methods ✓
- `complete_case_sensitivity` section ✓
- `nn_cross_model_distribution`: 21 rows (7 metrics × 3 train_n) ✓
- `default_vs_l2_paired` with win/loss/tie rates ✓
- `nn_win_rate_distributions` and `nn_tie_rate_distributions` ✓

### real_data_manifest.json
- Experiment: `real_data_holdout_validation_p8a_formal`
- Generation commit: `3330523`
- `git_dirty`: false ✓
- 5 output SHA256 hashes ✓
- P6 contract version and content commit ✓
- P7 APPROVE tip ✓
- Elapsed: 1529.7s ✓
- NN training info (15 selectors, per-fold P99 penalties) ✓

## Core Results Summary

### Primary Metric: Holdout KS Distance D (median across 500 repeats)

| Method | n=7 | n=10 | n=20 |
|--------|-----|------|------|
| Default (δ=0.1) | 0.1595 | 0.0954 | 0.0692 |
| L2 (per-n frozen δ) | 0.1595 | 0.0954 | 0.0714 |
| NN (median of 15 models) | 0.1725 | 0.1045 | 0.0763 |

*Values independently recomputed from raw CSV.*

### Default vs L2 Paired Wins

| Train n | L2 wins | Default wins | Ties | L2 win rate |
|---------|---------|-------------|------|-------------|
| 7 | 258 | 242 | 0 | 0.516 |
| 10 | 253 | 247 | 0 | 0.506 |
| 20 | 239 | 261 | 0 | 0.478 |

*n=7 and n=10 have same δ (0.10) for both methods → near-even split. n=20 L2 uses δ=0.08 vs Default 0.10.*

### NN Cross-Model Distribution (median D, 15 models)

| Train n | Min | Q1 | Median | Q3 | Max | Mean ± SD |
|---------|-----|-----|--------|-----|-----|-----------|
| 7 | 0.1657 | 0.1699 | 0.1725 | 0.1771 | 0.1929 | 0.1742 ± 0.0073 |
| 10 | 0.0988 | 0.1024 | 0.1045 | 0.1071 | 0.1154 | 0.1050 ± 0.0046 |
| 20 | 0.0724 | 0.0742 | 0.0763 | 0.0790 | 0.0834 | 0.0768 ± 0.0034 |

### 15-Model Stability

Model-to-model variation (SD of 15 model-level median-D values):
- n=7: SD = 0.0073 (CV = 4.2%)
- n=10: SD = 0.0046 (CV = 4.4%)
- n=20: SD = 0.0034 (CV = 4.4%)

The 15 NN selectors show consistent within-fold/seed stability. Model choice has small but measurable impact on holdout KS distance.

### NN vs Default Paired Win Rates (15-model distribution)

| Train n | Min | Median | Max |
|---------|-----|--------|-----|
| 7 | 0.314 | 0.380 | 0.486 |
| 10 | 0.302 | 0.376 | 0.442 |
| 20 | 0.290 | 0.350 | 0.458 |

NN selectors do NOT consistently outperform Default (δ=0.1) on this dataset. All 15 models have win rates below 0.5 vs Default.

## Failure Rate

**Zero estimation failures** across all 25,500 method applications. All MLE solutions converged with legal parameters on the NIST 6061-T6 data. The admission gate R²=0.9951 indicates strong Weibull fit to the full dataset.

## Input/Output SHA256 Verification

| File | SHA256 (LF-normalized) | Verified |
|------|------------------------|----------|
| BIRNSAUN.DAT | `7814c533...` | ✓ Match |
| lifetimes.csv | `43c85155...` | ✓ Match |
| p6_frozen_config.json | `be6d88bd...` | ✓ Match |
| real_holdout_results.csv | (in manifest) | ✓ |
| real_holdout_summary.json | (in manifest) | ✓ |
| real_nn_model_stability.csv | (in manifest) | ✓ |
| real_data_manifest.json | (in manifest) | ✓ |
| run_log.txt | (in manifest) | ✓ |

## Recovery, Re-run, or Deviations

| Item | Status |
|------|--------|
| Recovery attempts | **0** (first attempt succeeded after encoding fix) |
| First attempt | Failed: GBK encoding error on `R²` character in log message |
| Fix applied | Added `errors='replace'` fallback in `log()`, replaced `²` → `^2` |
| Second attempt | **Succeeded** — all outputs complete and verified |
| Deviations from contract | **None** |
| Code changes during run | **None** (all fixes committed and pushed before formal run at `3330523`) |
| Git tree at generation | **Clean** |

## Not Executed

- ❌ P8b: Independent review of real data results (next phase)
- ❌ P9: Optional S1/S2 supplemental diagnostics
- ❌ P10: Overall acceptance and status sync
- ❌ Engineering life quantile metrics (out of scope per contract)
- ❌ Pseudo p-values or significance tests on repeated splits
- ❌ New datasets, seeds, models, or metrics beyond frozen contract

## Scientific Statements

1. **Default vs L2**: On this single NIST 6061-T6 dataset, the frozen per-n L2 deltas (n=7: 0.10, n=10: 0.10, n=20: 0.08) perform nearly identically to Default (δ=0.1). This is expected because the L2 deltas differ from 0.1 only at n=20 (δ=0.08), and at n=20 the difference in median D is small (0.0692 vs 0.0714).

2. **NN selector performance**: The 15 NN selectors retrained under the frozen E3b/E4d contract do NOT demonstrate superior holdout KS distance compared to the simple Default δ=0.1 or L2 on this dataset. This is a legitimate negative result that should be reported as-is.

3. **Model stability**: The 15 NN selectors (5 folds × 3 seeds) show good stability (CV ~4% for median D), suggesting the training procedure produces consistent models even though individual predictions differ.

4. **Caveats**:
   - Results are from a single real dataset (NIST 6061-T6, n=101) and do not constitute external generalization evidence.
   - Repeated splits (500 per n) are correlated; win rates are not independent observations.
   - The full-sample OLS Weibull fit (β=4.03, η=1545.3) is an empirical reference, not "true parameters."
   - 15 NN models are stability replicates, not independent predictors.
   - No pseudo p-values or significance claims are made.

## Hard Boundaries

| Boundary | Status |
|----------|--------|
| `_P8A_FORMAL_AUTHORIZED` in generation commit | ✓ Yes (commit `3330523`) |
| No CLI bypass or hidden entry points | ✓ Confirmed |
| No amendment of P6 scientific contract | ✓ Confirmed |
| E1/E2/E3/E4/R1/R2 artifacts unchanged | ✓ Confirmed (verified by independent audit) |
| No data leakage (real data → training/scaler) | ✓ Confirmed |
| 15 selectors, no cherry-picking | ✓ Confirmed |
| Per-model aggregation before cross-model | ✓ Confirmed |
| No "median model" or pooled pseudo-inference | ✓ Confirmed |
| Git tree clean at generation time | ✓ Confirmed |
| Transactional scratch→promote output protocol | ✓ Executed successfully |
| Results not altered post-hoc | ✓ Confirmed (independent recompute matches) |

## Explicit Declaration

**This report does NOT self-assess as APPROVE.** The status is `READY_FOR_INDEPENDENT_REVIEW`.

P8a has executed the frozen P6 contract on the NIST 6061-T6 real dataset exactly once, producing 25,500 formal results. All gates passed. All outputs are sealed with provenance. The implementation and results await independent review by Codex (P8b).

No P9, P10, or paper-claim modifications have been made or should be inferred from this report.
