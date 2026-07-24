# Study01 R2 (P5a) — Delta Upper-Bound Audit Execution Report

**Branch**: `study01xu` (mainline, no worktree)
**Execution tip**: `76906a986e38ab81638ca7c380ac05b1f55d043d` (MDM formal run — the expensive computation)
**Analysis code tip**: `bc589e396f2799f990690c2c21d19c49b08996f3` (merge_and_analyze with tie-breaking; this report)
**Generation code tip**: `76906a986e38ab81638ca7c380ac05b1f55d043d`
**Seal method**: SHA256 from LF-normalised git blob bytes (after CRLF→LF), verified to match reviewer independent computation
**Tie-breaking**: `migrated = (extended_best_delta > 0.50) AND (loss_improvement > 1e-12)` — frozen in `merge_and_analyze()`, tested
**Date**: 2026-07-24 (re-run ~14:26 UTC; sealed ~15:30 UTC)
**Status**: P5a COMPLETE (REVISED) — AWAITING P5b INDEPENDENT REVIEW

## Revision Note

The first formal run (commit `5059ce2`) was **BLOCKED** by independent review. Root cause: `MDM.run()` returns a 5-tuple `(beta, eta, gamma, r_squared, status)` but the audit script called `.get()` on it as if it were a dict, producing 79,425 × `AttributeError`. `dropna(loss)` then silently dropped all failures, fabricating 0% migration. Fixes: correct tuple unpacking, fail-closed NaN guard, 3 new production-MDM integration tests. This report covers the **re-run** from commit `76906a9` where all 79,425 extended runs succeeded (100% success, 100% convergence).

## Plan Reference

Per `07-剩余实验目标与规划.md` §4.2 and phase P5a.

## Formal Run Receipt

```
Run receipt: commit=76906a9 dirty=False python=3.11.9 sklearn=1.7.2
Started:    2026-07-24T14:26:31+00:00
Completed:  2026-07-24T15:15:03+00:00
Duration:   ~2,912s (~48 min 32s)
Rate:       28.0 runs/s
```

### Extension Grid

`[0.52, 0.54, 0.56, ..., 1.00]` — 25 new delta values, step 0.02.

### Cohorts (frozen before extended MDM)

| Cohort | N samples | % of 45K MC sample set | SHA256 (sample key set) |
|--------|-----------|------------------------|--------------------------|
| δ=0.50 | 2,958 | 6.6% | `e7f61db3...` |
| δ=0.48 | 219 | 0.5% | `2347539a...` |

Note: "45,000" is the number of unique parameter-combination × sample-size × repeat-id samples in the 1.17M-row MC cache. The 1.17M figure counts risk-curve data rows (45,000 samples × 26 deltas on average), not independent samples.

### MDM Execution

| Cohort | Samples | Deltas | Runs | Duration | Rate |
|--------|---------|--------|------|----------|------|
| δ=0.50 | 2,958 | 25 | 73,950 | 2,642.1s | 28.0/s |
| δ=0.48 | 219 | 25 | 5,475 | 198.7s | 27.6/s |
| **Total** | **3,177** | 25 | **79,425** | **2,840.8s** | 28.0/s |

### MDM Health

| Cohort | Runs | Success | Success rate | Converged |
|--------|------|---------|-------------|-----------|
| δ=0.50 | 73,950 | 73,950 | **100.0%** | 73,950 |
| δ=0.48 | 5,475 | 5,475 | **100.0%** | 5,475 |

All 79,425 extended-MDM runs succeeded with convergence. No status=`failure`, no `error:` prefix.

## Results

### Headline

**δ=0.50 is NOT a sufficient upper bound for the endpoint cohort.** 94.7% of samples whose original-grid optimum was δ=0.50 find a meaningfully lower loss at some δ > 0.50 when the grid is extended to 1.00. The near-endpoint cohort (δ=0.48) is essentially unchanged.

### Cohort Summary

| Metric | δ=0.50 cohort | δ=0.48 cohort |
|--------|---------------|---------------|
| N samples | 2,958 | 219 |
| N migrated | **2,800** | 3 |
| Migration rate | **94.7%** (94.66%) | 1.4% |
| Full-cohort mean loss improvement | **0.0310** | 0.0006 |
| Full-cohort median loss improvement | **0.0115** | 0.0000 |
| Full-cohort mean rel improvement | 32.9% | 0.5% |
| Migrated-ONLY mean loss improvement | **0.0328** | 0.0421 |
| Migrated-ONLY median loss improvement | **0.0134** | 0.0171 |
| Migrated-ONLY mean rel improvement | 34.7% | 39.1% |
| Migrated mean new δ | 0.772 | 0.787 |
| Migrated median new δ | 0.76 | 0.78 |

Tie-breaking (frozen in code at `merge_and_analyze()`): `migrated = (extended_best_delta > 0.50) AND (loss_improvement > 1e-12)`. Two δ=0.50-endpoint samples have improvement ≈1.4×10⁻¹⁶ — correctly classified as non-migrated by the code alone, no CSV post-processing needed.

### Selected Delta Distribution (δ=0.50 cohort, extended best)

The new-best-delta distribution for the δ=0.50 cohort shows a broad rightward spread across the entire extension grid, with a concentration at the far edge:

| δ range | Count | Notes |
|---------|-------|-------|
| 0.50 (unchanged) | 158 | Original optimum still best after tie-breaking |
| 0.52–0.60 | 752 | Small extensions dominate early |
| 0.62–0.80 | 875 | Broad mid-range spread |
| 0.82–0.98 | 430 | Tapering toward grid edge |
| **1.00** | **743** | Grid-edge concentration (25.1% of all cohort samples) |

The 743 samples landing at δ=1.00 represent a potential boundary artifact: their true optimum may lie beyond 1.00, but the extension grid stops there. This strongly suggests that the δ=1.00 upper bound itself may be constraining.

### Interpretation

- The current δ=0.50 selection upper bound **does** truncate risk curves for the δ=0.50-endpoint cohort — the opposite of the fabricated "0% migration" in the first (buggy) run.
- 94.7% (2,800/2,958 after tie-breaking) of δ=0.50-endpoint samples achieve lower loss at some δ > 0.50. Across the full cohort: mean loss improvement 0.0310 (median 0.0115), mean relative improvement 32.9%. Among migrated samples only: mean 0.0328 (median 0.0134), mean relative 34.7%. These effect sizes are meaningful relative to the typical per-sample loss scale.
- The δ=0.48 near-endpoint cohort is stable (1.4% migration, negligible effect size), suggesting the truncation problem primarily affects samples at the existing grid boundary.
- All claims are **conditioned on** the sample's original-grid best delta being exactly 0.50 (or 0.48). These are targeted cohort audits, not full-population estimates.

## Contract Compliance (§4.2)

| Requirement | Status |
|-------------|--------|
| Original 0.00–0.50 grid products unchanged | ✓ |
| Extension fixed to 0.52–1.00, step 0.02 | ✓ |
| Cohort defined from frozen E2/E4 artifact sample key sets with SHA256 | ✓ |
| Target cohort: δ=0.50 (primary) + δ=0.48 (auxiliary) | ✓ |
| Same production mdm.py used | ✓ |
| Original 0.00–0.50 curves merged with 0.52–1.00 extension per sample | ✓ |
| Migration rate, new delta distribution, improvement magnitude computed | ✓ |
| All claims conditioned on "original best delta = target cohort delta" | ✓ |
| No whole-grid sufficiency claims without full population extension | ✓ |
| New directory, no overwrite of E1/E2/E4 sealed evidence | ✓ |
| Manifest records generation commit, execution commit, file SHA256 | ✓ |
| SHA256 are 64-char hex (not git blob OID SHA-1); verified by automated test | ✓ |
| Input chunks SHA256 from git blobs at c70c5d4, matches independent computation | ✓ |
| Fail-closed: mandatory 25/25 coverage per sample before any dropna | ✓ |
| MDM health stats (success/convergence/failure) reported per cohort | ✓ |
| Per-delta failure logging uses per-delta counts (not cohort-level) | ✓ |
| Production MDM integration tests pass (3 new) | ✓ |
| Auto-verification SHA256 test added (10 tests, test_study01_r2_sha256_verify.py) | ✓ |
| Tie-breaking implemented in code and tested (2 unit tests) | ✓ |
| All tests pass (99/99, including 10 R2-SHA verification tests) | ✓ |

## Artifact Inventory

Output directory: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/delta_upper_bound_audit/`

| File | Rows | Git blob bytes | SHA256 (first 16 chars) |
|------|------|---------------|--------------------------|
| `extended_results.csv` | 79,425 | 10,996,264 | `cd46f72153654568...` |
| `merged_curves.csv` | 3,177 | 348,994 | `2528518562c077bb...` |
| `cohort_summary.csv` | 2 | 966 | `6716e653f8e60668...` |
| `manifest.json` | — | — | `(self — exclude from seal)` |
| `run_log.txt` | — | 6,302 | `449d6b916eaa8a24...` |

All SHA256 are 64-char hex from `sha256sum(git show HEAD:<path>)` (LF-normalised Git blob bytes). Full values recorded in manifest.json. Auto-verified by `python/tests/test_study01_r2_sha256_verify.py` (10 tests).

### Provenance

| Key | Value |
|-----|-------|
| generation_code_commit | `76906a986e38ab81638ca7c380ac05b1f55d043d` (MDM formal run code) |
| execution_commit | `76906a986e38ab81638ca7c380ac05b1f55d043d` (HEAD at MDM execution) |
| analysis_code_commit | `bc589e396f2799f990690c2c21d19c49b08996f3` (merge_and_analyze + sealing) |
| workspace_dirty | `false` |
| Python | 3.11.9 |
| sklearn | 1.7.2 |

## Tests

```bash
pytest python/tests/test_study01_e4_failclosed.py \
       python/tests/test_study01_delta_upper_bound.py \
       python/tests/test_study01_real_data_gate.py \
       python/tests/test_study01_e4d_sha256_verify.py \
       python/tests/test_study01_r2_sha256_verify.py -v
# 99 passed
```

Breakdown: E4d fail-closed 42, delta upper bound 15 (incl. 2 tie-breaking + 3 integration), real data gate 17, E4d SHA verify 4, R2 SHA verify 10, other 11. Total 99.

## Files Changed

```
new/modified:   Study/.../code/run_delta_upper_bound_audit.py  (tuple unpacking, fail-closed, tie-breaking)
modified:       python/tests/test_study01_delta_upper_bound.py  (+5 tests: 3 integration + 2 tie-breaking)
new:            python/tests/test_study01_r2_sha256_verify.py   (10 SHA verification tests)
new:            Study/.../artifacts/formal/delta_upper_bound_audit/
                ├── cohort_summary.csv       (regenerated from code)
                ├── extended_results.csv     (79,425 MDM results)
                ├── merged_curves.csv         (regenerated from code)
                ├── manifest.json             (provenance + SHA256)
                └── run_log.txt               (execution log)
new/modified:   coworker/reports/2026-07-24-study01xu-r2-p5a-execution.md  (this file)
```

## Gate Status: AWAITING P5b REVIEW

P5a is complete. This report is the executor deliverable. Next step per the plan:

> **P5b** — 独立审查并记录上界 gate 决议 (APPROVE / REVISE / BLOCK)

The independent reviewer should verify:
- MDM health: 100% success / 100% convergence across all 79,425 runs (not 0%);
- 94.7% migration rate is computed from valid data (not `dropna` fabrication);
- Cohort identification correctness against frozen shared_data chunks;
- 743 samples at δ=1.00 (grid-edge concentration) — whether this warrants a further extension to δ=1.50 or similar;
- Manifest provenance completeness (both commits, file SHA256, input chunk hash);
- Conditional claim framing correct (endpoint/near-endpoint cohorts only, not full population);
- No E1/E2/E4 sealed evidence overwritten.

**Executor does NOT self-APPROVE.** Stop and await P5b reviewer verdict.

## Claims Supported (corrected)

- The δ=0.50 selection upper bound materially truncates risk curves for the **δ=0.50-endpoint cohort**: 94.7% of those 2,958 samples achieve lower loss at some δ > 0.50.
- The mean loss improvement among migrated samples (2,800) is 0.0328 (median 0.0134), with a mean relative improvement of 34.7% over the original-grid optimum. Full-cohort figures: mean 0.0310, median 0.0115, mean relative 32.9%.
- 25% (743/2,958) of the δ=0.50-endpoint cohort lands at δ=1.00, the far edge of the extension grid — this may indicate the 1.00 bound itself is constraining.
- The δ=0.48 near-endpoint cohort is stable (1.4% migration, negligible effect size), suggesting the truncation issue is specific to the δ=0.50 boundary.

## Claims NOT Supported

- This is a targeted audit of two endpoint/near-endpoint cohorts (3,177 out of 45,000 MC samples), not a full-population extension.
- The δ=0.48 cohort stability does not generalize to other interior delta values.
- The result does not prescribe a specific new upper bound; the broad distribution and grid-edge concentration require scientific interpretation.
- No p-values or confidence intervals are reported; this is a census of the cohort, not a population inference.
