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
P8b REVISE tip:      (this commit — fixes applied, no re-run)
Previous final tip:  b66a549 (SUPERSEDED — report statistics incorrect)
Artifact commit:     7946108 (raw outputs — UNCHANGED, not re-generated)
Generation commit:   3330523 (code at formal run time)
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
| 5 | `3330523` | **fix**: handle GBK encoding errors → **GENERATION CODE COMMIT** |
| 6 | `7946108` | **run**: generate P8a formal raw artifacts (25,500 rows) |
| 7 | `b66a549` | **docs**: P8a executor report v1 (SUPERSEDED — report errors) |
| 8 | *(this commit)* | **fix/docs**: P8b REVISE — correct report, close auth, fix manifest seal, fix GBK test |

**Generation code commit**: `3330523` — unchanged, no re-run.
**Artifact commit**: `7946108` — raw outputs unchanged. CSV, summary JSON, stability CSV, run log are bit-identical to the original formal run.
**Changed in REVISE**: manifest (`recovery_attempts`, output_hashes), new `SHA256SUMS_p8a`, report corrections, test updates, authorization closed.

## Exact Run Command and Timing

**`exact_command_recorded: false`** — the original terminal command was not preserved verbatim. The command below is reconstructed from the run log and code path; it is not claimed as the exact original invocation.

```
Reconstructed command:
  python -c "import sys; sys.path.insert(0, 'Study/01-study-MDM.../code');
  from run_real_data_validation import run_p8a_formal; run_p8a_formal()"

Code path: run_real_data_validation.run_p8a_formal()
           -> run_pipeline(data_dir=..., output_dir=scratch_dir, chunks_dir=...)
```

This is recorded as a provenance deviation: the formal run was launched via a background shell command whose exact text was not logged. The run log, manifest, and output hashes independently confirm what code was executed and what outputs were produced. Future formal runs should capture the exact CLI invocation in the manifest.

| Field | Value |
|-------|-------|
| Start time | 2026-07-24T21:18:24+00:00 (2026-07-25 05:18:24 local) |
| End time | 2026-07-24T21:43:53+00:00 (2026-07-25 05:43:53 local) |
| Elapsed | 1529.7 seconds (25.5 minutes) |
| Environment | Windows 11, Python 3.11.9, Git Bash |
```

## Test Results (Final Tip)

| Test file | Tests | Result |
|-----------|-------|--------|
| `test_study01_real_data_gate.py` | 16 | 16 passed |
| `test_study01_p6_frozen_contract.py` | 20 | 20 passed |
| `test_study01_p7_pipeline.py` | 89 | 89 passed |
| `test_study01_p8a_controls.py` | 28 | 28 passed |
| **Total** | **153** | **153 passed, 0 failed, 0 skipped** |

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

*All values independently recomputed from `real_holdout_results.csv` using `numpy.median()` and paired-difference logic; not taken from the summary JSON or any production aggregation function.*

### Primary Metric: Holdout KS Distance D (median across 500 repeats)

| Method | n=7 | n=10 | n=20 |
|--------|-----|------|------|
| Default (δ=0.1) | 0.1881 | 0.1630 | 0.1276 |
| L2 (per-n frozen δ) | 0.1881 | 0.1630 | 0.1263 |
| NN (median of 15 model-level medians) | 0.2024 | 0.1727 | 0.1361 |

### Default vs L2 Paired Wins

n=7 and n=10 have δ=0.10 for both methods, so they are identical — all 500 pairs are ties.

| Train n | L2 wins | Default wins | Ties |
|---------|---------|-------------|------|
| 7 | 0 | 0 | 500 |
| 10 | 0 | 0 | 500 |
| 20 | 211 | 190 | 99 |

At n=20, L2 δ=0.08 vs Default δ=0.10: L2 wins 211, Default wins 190, 99 ties.

### NN Cross-Model Distribution (median D, 15 models)

| Train n | Min | Q1 | Median | Q3 | Max | Mean ± SD |
|---------|-----|-----|--------|-----|-----|-----------|
| 7 | 0.1916 | 0.1976 | 0.2024 | 0.2104 | 0.2128 | 0.2029 ± 0.0076 |
| 10 | 0.1676 | 0.1706 | 0.1727 | 0.1763 | 0.1785 | 0.1733 ± 0.0036 |
| 20 | 0.1313 | 0.1359 | 0.1361 | 0.1371 | 0.1376 | 0.1360 ± 0.0016 |

### 15-Model Stability

Model-to-model variation (SD of 15 model-level median-D values):
- n=7: SD = 0.0076 (CV = 3.74%)
- n=10: SD = 0.0036 (CV = 2.08%)
- n=20: SD = 0.0016 (CV = 1.21%)

The 15 NN selectors show adequate within-contract stability. Model choice has measurable but limited impact on holdout KS distance.

### NN vs Default Paired Win Rates (15-model distribution)

| Train n | Min | Median | Max |
|---------|-----|--------|-----|
| 7 | 0.038 | 0.204 | **0.512** |
| 10 | 0.068 | 0.234 | 0.432 |
| 20 | 0.214 | 0.338 | 0.400 |

At n=7, one model achieves a 51.2% win rate vs Default; the median model wins 20.4% of repeats. At n=10 and n=20, all 15 models have win rates below 0.5.

### Auxiliary: Holdout Support-Set Violation Rate

| Method | n=7 | n=10 | n=20 |
|--------|-----|------|------|
| Default (δ=0.1) | 0.764 | 0.754 | 0.724 |
| L2 (per-n frozen δ) | 0.764 | 0.754 | 0.680 |
| NN (median of 15 models) | 0.908 | 0.904 | 0.802 |

Support-set violation rates are high across all methods, particularly for NN selectors. The fitted γ̂ frequently exceeds the smallest holdout observation. This is an important auxiliary result per frozen contract §5.2 (M2).

## Failure Rate

**Zero MDM estimation failures** across all 25,500 method applications. All MDM runs converged with legal parameters on the NIST 6061-T6 data. The admission gate R²=0.9951 indicates strong Weibull fit to the full dataset.

Note: "No estimation failures" means MDM did not fail to converge. The high support-set violation rates (above) are a separate auxiliary metric — they reflect the fitted model's γ̂ relative to holdout data, not MDM convergence failure.

## Input/Output SHA256 Verification

### Input Hashes

| File | SHA256 (LF-normalized) | Verified |
|------|------------------------|----------|
| BIRNSAUN.DAT | `7814c533818517d8b824c56213abac2b4076786a13a66d85a8481a32bbccf127` | ✓ Match |
| lifetimes.csv | `43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12` | ✓ Match |
| p6_frozen_config.json | `be6d88bd761c849b...` | ✓ Match (in manifest) |

### Output Hashes (from SHA256SUMS_p8a seal file)

The manifest's `output_hashes` records 4 data files (CSV, summary JSON, stability CSV, run log). The manifest itself is excluded from `output_hashes` to avoid the self-reference problem. All 5 files — including the manifest — are bound by the external `SHA256SUMS_p8a` seal file, which is the authoritative hash registry for this experiment.

| File | SHA256 (LF-normalized) | Source |
|------|------------------------|--------|
| real_holdout_results.csv | `82b05bfe...` | manifest + SHA256SUMS_p8a |
| real_holdout_summary.json | `01675a1e...` | manifest + SHA256SUMS_p8a |
| real_nn_model_stability.csv | `e0816244...` | manifest + SHA256SUMS_p8a |
| run_log.txt | `387fe458...` | manifest + SHA256SUMS_p8a |
| real_data_manifest.json | `ef2f0bdb...` | SHA256SUMS_p8a only |

## Recovery, Re-run, or Deviations

| Item | Status |
|------|--------|
| Total attempts | **2** |
| **Attempt 1** | **Failed** — GBK encoding error on `²` character in log message at gate phase (1s elapsed). Scratch directory preserved. |
| Fix applied | Committed `3330523`: `errors='replace'` fallback in `log()`, `²` → `^2`, `β/η/γ` → ASCII |
| **Attempt 2** | **Succeeded** — from clean tree at `3330523`, 1529.7s elapsed, all outputs verified |
| Recovery attempts | **1** (attempt 1 failed → code fixed → attempt 2 succeeded) |
| Deviations from P6 contract | **None** |
| Code changes during run | **None** (all fixes committed and pushed before generation commit `3330523`) |
| Git tree at generation | **Clean** (verified at `3330523`) |
| Exact run command | `python -c "import sys; sys.path.insert(0, 'Study/01-study-MDM.../code'); from run_real_data_validation import run_p8a_formal; run_p8a_formal()"` (path abbreviated for display; the code directory is `Study/01-study-MDM最小偏移量优化研究/code/`) |

## Not Executed

- ❌ P8b: Independent review (Codex) — **in progress (REVISE issued, this is the response)**
- ❌ P9: Optional S1/S2 supplemental diagnostics
- ❌ P10: Overall acceptance and status sync
- ❌ Engineering life quantile metrics (out of scope per contract)
- ❌ Pseudo p-values or significance tests on repeated splits
- ❌ New datasets, seeds, models, or metrics beyond frozen contract
- ❌ P8a formal re-run (not needed — raw artifacts are correct, only report/seal/manifest needed fixing)

## Scientific Statements

1. **Default vs L2**: At n=7 and n=10 both methods use δ=0.10, producing identical results (500 ties). At n=20, L2 δ=0.08 vs Default δ=0.10 yields L2 wins 211, Default wins 190, ties 99. L2's advantage at n=20 is modest.

2. **NN selector performance**: The 15 NN selectors do NOT demonstrate consistent superiority over Default (δ=0.1) on this dataset. At n=7 the best model achieves 51.2% win rate vs Default; the median model wins only 20.4%. At n=10 and n=20 all 15 models have win rates below 0.5. The NN method's higher support-set violation rates (median 0.80–0.91) are a notable auxiliary concern.

3. **Model stability**: The 15 NN selectors show adequate stability (CV 2–4% for median D). Model choice has limited impact on aggregate metrics.

4. **Support-set violations**: Violation rates are high across all methods (0.68–0.91), particularly for NN selectors. This reflects the difficulty of estimating a 3-parameter Weibull location parameter from small samples — γ̂ often exceeds some holdout observations.

5. **Caveats**:
   - Results are from a single real dataset (NIST 6061-T6, n=101) and do not constitute external generalization evidence.
   - Repeated splits (500 per n) are correlated; win rates are not independent observations.
   - The full-sample OLS Weibull fit (β=4.03, η=1545.3) is an empirical reference, not "true parameters."
   - 15 NN models are stability replicates, not independent predictors.
   - No pseudo p-values or significance claims are made.
   - All estimates are MDM (minimum displacement method), not MLE.

## Hard Boundaries

| Boundary | Status |
|----------|--------|
| `_P8A_FORMAL_AUTHORIZED` = True in generation commit `3330523` | ✓ Verified |
| `_P8A_FORMAL_AUTHORIZED` = False in final tip (sealed state) | ✓ Verified |
| No CLI bypass or hidden entry points | ✓ Confirmed |
| No amendment of P6 scientific contract | ✓ Confirmed |
| E1/E2/E3/E4/R1/R2 artifacts unchanged | ✓ Confirmed |
| No data leakage (real data → training/scaler) | ✓ Confirmed |
| 15 selectors, no cherry-picking | ✓ Confirmed |
| Per-model aggregation before cross-model | ✓ Confirmed |
| No "median model" or pooled pseudo-inference | ✓ Confirmed |
| Git tree clean at generation time | ✓ Confirmed |
| Transactional scratch→promote output protocol | ✓ Executed |
| Manifest self-hash excluded (SHA256SUMS_p8a seal) | ✓ Fixed in REVISE |
| Raw artifacts NOT re-generated | ✓ Confirmed (CSV/stability/summary/log bit-identical to `7946108`) |
| P8a formal run NOT re-executed | ✓ Confirmed |

## Explicit Declaration

**This report does NOT self-assess as APPROVE.** The status is `READY_FOR_INDEPENDENT_REVIEW`.

P8a has executed the frozen P6 contract on the NIST 6061-T6 real dataset exactly once, producing 25,500 formal results. All gates passed. All outputs are sealed with provenance. The implementation and results await independent review by Codex (P8b).

No P9, P10, or paper-claim modifications have been made or should be inferred from this report.
