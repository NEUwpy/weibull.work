# Study/01 E4 — Step 4 Feature Ablation Report

> Date: 2026-07-10
> Executor: Hermes (executor role)
> Plan: `coworker/plans/2026-07-10-study01-e4-staged-execution.md`
> Step 3 report: `coworker/reports/2026-07-10-study01-e4-step3-reference-analysis-hermes.md`
> Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`

---

## Verdict: APPROVE Step 4 evidence for mainline consolidation

E4a feature ablation completed successfully. 60 runs (4 groups × 5 folds × 3 seeds) all produced valid results. Zero NaN/Inf. Sealed artifacts verified untouched. E4b/E4c outputs from Step 3 confirmed intact.

---

## 1. Pre-Execution: Smoke Test

Before the formal run, a smoke test was conducted with 1 fold × 1 group (full) × 1 seed (42) to validate the pipeline end-to-end:

- **J1 = 0.528518**, n_samples = 9000, n_iter = 59 (early stopping)
- **NaN/Inf check**: PASS (no NaN in J1)
- **Elapsed**: 34.2s for single run
- **Estimated full run**: ~34 min (rough smoke extrapolation; invalidated by the formal run)

Smoke test script (`_smoke_e4a.py`) was deleted after validation; not committed.

---

## 2. Command and Execution

**Command:**
```
cd /d/weibull && PYTHONUNBUFFERED=1 python "Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py" --tracks e4a
```

**Exit code:** 0

**Start time:** 2026-07-10 ~23:40 (local)
**End time:** 2026-07-11 06:27 (local)
**Total elapsed:** 24,845.0 seconds (414.1 minutes / 6.9 hours)

**Branch:** `study01-e4-validation`
**Git commit:** `0147baa-dirty` (dirty due to concurrent uncommitted workspace modifications to draft files; E4 execution files unchanged relative to `0147baa`)

**Note on runtime:** The actual runtime (6.9 hours) far exceeded the smoke test estimate (34 min). The smoke test MLP converged in 59 iterations (34s), but formal runs varied from 11s to 1001s per training depending on fold/group/seed. The `shape` group (4 features) was paradoxically the slowest, likely due to optimization landscape differences. This is a known sklearn MLPRegressor characteristic on CPU — training time is not monotonic with feature count.

---

## 3. Output Files

| File | Size | Rows |
|------|------|------|
| E4a_feature_ablation.csv | 13,314 bytes | 60 |
| split_report.csv | 1,153 bytes | 45 |
| cost_report.csv | 4,693 bytes | 63 (61 E4a + 2 E4b/E4c restored) |
| manifest_e4a.json | 7,940 bytes | — |
| summary_e4a.json | 1,422 bytes | — |
| run_log_e4a.txt | 7,243 bytes | — |

All files in: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`

---

## 4. Row Count Verification

### E4a_feature_ablation.csv

| Check | Expected | Actual | Status |
|---|---|---|---|
| Data rows | 4 groups × 5 folds × 3 seeds = 60 | 60 | PASS |
| Feature groups | full, n, scale_quantile, shape | full, n, scale_quantile, shape | PASS |
| Folds | combo_fold_1 through combo_fold_5 | All 5 present | PASS |
| Seeds | 42, 2026, 3407 | All 3 present | PASS |
| pooled_J1 NaN | 0 | 0 | PASS |
| pooled_J1 Inf | 0 | 0 | PASS |

### split_report.csv

| Check | Expected | Actual | Status |
|---|---|---|---|
| Data rows | 45 combos (9 per fold × 5 folds) | 45 | PASS |

---

## 5. Manifest Verification

| Field | Value | Status |
|---|---|---|
| status | FORMAL | PASS |
| tracks_requested | ["e4a"] | PASS |
| is_full_run | false | PASS |
| track_status.e4a | {requested: true, status: "completed"} | PASS |
| track_status.e4b | {requested: false, status: "not_requested"} | PASS |
| track_status.e4c | {requested: false, status: "not_requested"} | PASS |
| track_status.e4d | {requested: false, status: "not_requested"} | PASS |
| git_commit | 0147baa-dirty | PASS (dirty flag correctly detected) |
| output_files | 6 files, all actually produced | PASS |

---

## 6. Feature Ablation Results

### Per-group mean J1 (across 5 folds × 3 seeds = 15 runs per group)

| Group | Features | n_features | Mean J1 | Std J1 | Min J1 | Max J1 |
|---|---|---|---|---|---|---|
| **full** | x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, n, CV, g1, g2 | 13 | **0.5456** | 0.0102 | 0.5261 | 0.5599 |
| **scale_quantile** | n + z-score features (x_min...s) | 10 | **0.5506** | 0.0119 | 0.5313 | 0.5671 |
| **shape** | n, CV, g1, g2 | 4 | **0.5816** | 0.0211 | 0.5437 | 0.6056 |
| **n_only** | n | 1 | **0.6378** | 0.0195 | 0.6045 | 0.6654 |

### Key observations

1. **Within-E4a performance ordering holds** (lower J1 is better): full (0.546), scale_quantile (0.551), shape (0.582), then n_only (0.638).

2. **Scale/quantile features appear to carry most of the observed signal**: Removing shape features (CV, g1, g2) from the full set changes mean J1 by 0.005 (0.546 → 0.551). This is a descriptive ablation result, not a formal causal or significance claim.

3. **Shape features alone are useful but limited**: Using only n, CV, g1, g2 (4 features) gives J1=0.582, substantially better than n_only (0.638) but worse than scale_quantile (0.551).

4. **n alone has nonzero predictive power**: J1=0.638 for n_only, which is comparable to L2 (per-n) oracle performance on the main grid. This is expected — n is the primary stratification variable.

5. **Combined fold-and-seed dispersion is limited**: The reported standard deviation pools all 15 fold × seed runs per group and is ≤0.021. It must not be described as seed-only variability.

6. **Endpoint rate**: The `full` group has mean endpoint_rate=0.513 (51.3% of predictions select extreme deltas), while `n_only` has endpoint_rate=0.0 (single feature cannot distinguish delta preferences enough to select extremes). This confirms that shape/scale features are needed to differentiate sample-specific delta preferences.

### Boundary of comparison with E4b

E4a is evaluated on the existing main grid, whereas E4b is evaluated on a different boundary distribution. Their pooled J1 values are therefore not directly rank-comparable. In particular, E4a full-MLP J1=0.546 cannot be used to claim that the model exceeds an E4b boundary oracle. E4a supports only the within-main-grid feature-ablation ordering above; E4b retains its separate boundary-reference interpretation from Step 3.

---

## 7. Safety Checks

| Check | Result |
|---|---|
| Sealed E1/E2/E3a/E3b artifacts | UNTOUCHED — git diff HEAD = EMPTY |
| Ch1-Ch6 / README / 00-05 | Not modified by Step 4 |
| E4b/E4c executed? | NO — track_status shows not_requested |
| E4d executed? | NO — track_status shows not_requested |
| Ch7 written? | NO |

---

## 8. Cost Report

| Track | Elapsed | Note |
|---|---|---|
| E4a | 24,843.6s (6.9h) | feature ablation (60 MLP trainings) |
| E4b | 10.2s | boundary reference evaluation (Step 3, restored) |
| E4c | 6.1s | offgrid reference evaluation (Step 3, restored) |

E4a per-run elapsed ranged from 11.2s (n_only, fold 1, seed 2026) to 1001.4s (shape, fold 5, seed 42). The variance is due to sklearn MLPRegressor convergence behavior on different data subsets.

---

## 9. Operational Notes

- **cost_report.csv overwrite**: The `--tracks e4a` run overwrote the shared `cost_report.csv` with E4a-only data. The 2 E4b/E4c rows were restored exactly from the tracked Step 3 version in commit `0147baa`. The combined file now has 63 rows (2 E4b/E4c + 1 E4a summary + 60 E4a per-run). The script still needs a preservation fix before any future subset-track run such as E4d.

- **Workspace dirty**: Manifest correctly records `0147baa-dirty`. The dirty state is due to concurrent uncommitted modifications to draft/figure files, NOT to the E4 execution files.

- **Step 3 artifacts intact**: During Step 4 execution, E4b/E4c files temporarily disappeared because the single working tree switched from `study01-e4-validation` to `main` at 00:15, then reappeared when it switched back at 00:30. Git reflog confirms this sequence. All Step 3 files are tracked by `0147baa` and match that commit; this was not a path-encoding loss.

---

## 10. Recommendation: APPROVE Step 4 evidence and consolidate to main

Step 4 (E4a feature ablation) is complete. The results show:

1. Clear feature importance hierarchy: full > scale_quantile > shape > n_only.
2. Scale/quantile features carry most predictive power; shape features add marginal improvement.
3. E4a and E4b use different evaluation distributions and must remain separate evidence statements.
4. Manifest and track-status fields are coherent; the combined cost artifact is coherent after exact restoration of the Step 3 rows.

Current next step:
- Consolidate the completed E4 branch and the concurrent manuscript work into `main` with scoped commits.
- Do not start E4d in this pass. Before any future subset-track run, fix the shared `cost_report.csv` overwrite behavior with a regression test.
