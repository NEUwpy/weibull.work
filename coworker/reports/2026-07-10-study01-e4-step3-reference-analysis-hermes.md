# Study/01 E4 — Step 3 Reference Analysis Report

> Date: 2026-07-10
> Executor: Hermes (executor role)
> Plan: `coworker/plans/2026-07-10-study01-e4-staged-execution.md`
> Codex review: `coworker/reviews/2026-07-10-study01-e4-step2-mc-generation-hermes.md` — APPROVE Step 3
> Status/Handoff: `Study/01-study-MDM最小偏移量优化研究/E4-validation-suite-状态交接.md`

---

## Verdict: APPROVE for Step 4+ review

E4b/E4c reference analysis completed successfully. All 8 output files produced. Row counts exact. Zero NaN/Inf. Sealed artifacts verified untouched. E4a/E4d correctly skipped (not_requested, not skipped).

---

## 1. Pre-Execution Cleanup

Two non-blocking cleanup items from Codex's APPROVE review were completed before Step 3:

1. **[P2] Input-gate test isolation**: Extracted `preflight_check_inputs()` + `PreflightError` from inline logic. Rewrote input-gate tests to use `tmp_path` instead of renaming real formal CSVs. Added 2 new tests (e4d multi-input-missing, all-present passes). Total: 17 contract tests.

2. **[P3] Handoff provenance**: Distinguished Step 2 generation version (`8103587`) from Step 3 analysis code version (`b65eba7`→`831a8b4`).

Cleanup commit: `831a8b4`.

---

## 2. Command and Execution

**Command:**
```
cd /d/weibull && PYTHONUNBUFFERED=1 python "Study/01-study-MDM最小偏移量优化研究/code/run_E4_formal_validation.py" --tracks e4b,e4c
```

**Exit code:** 0

**Start time:** 21:40:04 (2026-07-10)
**End time:** 21:40:22 (2026-07-10)
**Total elapsed:** 18.4 seconds

**Branch:** `study01-e4-validation`
**Git commit:** `831a8b4-dirty` (dirty due to concurrent uncommitted workspace modifications; the three E4 execution files are unchanged relative to `831a8b4`)

---

## 3. Output Files

| File | Size | Rows |
|------|------|------|
| E4b_boundary_reference.csv | 6,815,760 bytes (6.5 MB) | 70,000 |
| E4c_offgrid_reference.csv | 4,923,987 bytes (4.7 MB) | 49,000 |
| endpoint_diagnostics.csv | 393 bytes | 14 |
| near_optimal_diagnostics.csv | 1,192 bytes | 14 |
| cost_report.csv | 126 bytes | 2 |
| manifest_e4b_e4c.json | 8,040 bytes | — |
| summary_e4b_e4c.json | 7,420 bytes | — |
| run_log_e4b_e4c.txt | 1,757 bytes | — |

All files in: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness/`

---

## 4. Row Count Verification

### E4b_boundary_reference.csv

| Check | Expected | Actual | Status |
|---|---|---|---|
| Data rows | 20 combos × 500 repeats × 7 models = 70,000 | 70,000 | PASS |
| Models | Default, L1, L2, L3, L4, L5, L6-hindsight | All 7 present | PASS |
| Track values | E4b only | E4b only | PASS |
| true_loss NaN | 0 | 0 | PASS |
| true_loss Inf | 0 | 0 | PASS |

### E4c_offgrid_reference.csv

| Check | Expected | Actual | Status |
|---|---|---|---|
| Data rows | 14 combos × 500 repeats × 7 models = 49,000 | 49,000 | PASS |
| Models | Default, L1, L2, L3, L4, L5, L6-hindsight | All 7 present | PASS |
| Track values | E4c only | E4c only | PASS |
| true_loss NaN | 0 | 0 | PASS |
| true_loss Inf | 0 | 0 | PASS |

---

## 5. Manifest Verification

| Field | Value | Status |
|---|---|---|
| status | FORMAL | PASS |
| tracks_requested | ["e4b", "e4c"] | PASS |
| is_full_run | false | PASS |
| track_status.e4a | {requested: false, status: "not_requested"} | PASS |
| track_status.e4b | {requested: true, status: "completed"} | PASS |
| track_status.e4c | {requested: true, status: "completed"} | PASS |
| track_status.e4d | {requested: false, status: "not_requested"} | PASS |
| git_commit | 831a8b4-dirty | PASS (dirty flag correctly detected) |
| output_files | 8 files, all actually produced | PASS |
| No e4d_skipped field | Absent | PASS (replaced by track_status) |

---

## 6. Summary J1 Results

### E4b (Boundary, 20 combos)

| Model | Pooled J1 | n_samples | Mean Regret |
|---|---|---|---|
| Default | 0.6864 | 10000 | 0.1892 |
| L1 | 0.6464 | 10000 | 0.1360 |
| L2 | 0.6269 | 10000 | 0.1112 |
| L3 | 0.6074 | 10000 | 0.0870 |
| L4 | 0.5918 | 10000 | 0.0683 |
| L5 | 0.5868 | 10000 | 0.0624 |
| L6-hindsight | 0.5309 | 10000 | 0.0000 |

Key observation: Oracle hierarchy holds at boundary. L1 improves on Default by 5.8%, L5 improves on Default by 14.5%, L6 (hindsight ceiling) improves on Default by 22.7%.

### E4c (Off-grid, 14 combos)

| Model | Pooled J1 | n_samples | Mean Regret |
|---|---|---|---|
| Default | 0.6219 | 7000 | 0.1709 |
| L1 | 0.6014 | 7000 | 0.1458 |
| L2 | 0.5450 | 7000 | 0.0812 |
| L3 | 0.5450 | 7000 | 0.0812 |
| L4 | 0.5450 | 7000 | 0.0812 |
| L5 | 0.5450 | 7000 | 0.0812 |
| L6-hindsight | 0.4646 | 7000 | 0.0000 |

Key observation: L2=L3=L4=L5 on off-grid. This is because the off-grid combos have unique (beta, gamma_over_eta, n) triplets — per-n stratification (L2) already captures all available information. This is a structural artifact of the off-grid combo design, not a method failure.

---

## 7. Safety Checks

| Check | Result |
|---|---|
| Sealed E1/E2/E3a/E3b artifacts | UNTOUCHED — git diff HEAD = EMPTY |
| Ch1-Ch6 / README / 00-05 | Not modified by Step 3 (analysis script only writes CSVs/JSON/TXT to E4_robustness/) |
| E4a/E4d executed? | NO — track_status shows not_requested for both |
| E4d_skip_reason.md written? | NO — E4d was not requested, not skipped |
| split_report.csv written? | NO — E4a was not requested |
| Ch7 written? | NO |

---

## 8. Cost Report

| Track | Elapsed (s) | Note |
|---|---|---|
| E4b | 10.2 | boundary reference evaluation |
| E4c | 6.1 | offgrid reference evaluation |
| Total | 18.4 | (including data loading + metadata write) |

Actual `time.time()` measurements, not hardcoded values.

---

## 9. Operational Notes

- **Branch drift check**: Verified `git branch --show-current` = `study01-e4-validation` immediately before launch.
- **Workspace dirty**: Manifest correctly records `831a8b4-dirty`. The dirty state is due to concurrent uncommitted modifications to draft/figure files in the workspace, NOT to the three E4 execution files. The E4 scripts (`run_E4_mc_generation.py`, `run_E4_formal_validation.py`, `utils.py`) are unchanged relative to `831a8b4`.
- **Input data integrity**: `mc_scan_raw.csv` (1,170,000 rows), `boundary_risk_curves.csv` (260,000 rows), `offgrid_risk_curves.csv` (182,000 rows) all loaded successfully.

---

## 10. Recommendation: APPROVE Step 4+

Step 3 (E4b/E4c reference analysis) is complete. The results show:

1. Oracle hierarchy holds at boundary (E4b): Default → L1 → L2 → L3 → L4 → L5 → L6 monotonically improves.
2. Off-grid (E4c) shows L2=L3=L4=L5 collapse due to unique (beta, goe, n) triplets.
3. Boundary J1 values (0.53–0.69) are higher than main-grid values, confirming boundary conditions are genuinely harder.
4. All track_status, manifest, and cost fields are semantically correct.

Next steps in the staged execution plan:
- **Step 4** (E4a feature ablation): Uses main-grid MC data, requires MLP training.
- **Step 5** (E4d selector extrapolation): Optional diagnostic.
- **Step 6** (Consolidation report): Assemble final formal E4 report.
