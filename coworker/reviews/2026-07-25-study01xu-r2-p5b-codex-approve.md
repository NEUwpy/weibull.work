# Study01 R2 (P5b) — Delta Upper-Bound Audit Independent Review

**Reviewer**: Codex
**Verdict**: ✅ **APPROVE**
**Date**: 2026-07-25
**Subject**: P5a execution report + full artifact chain for R2 delta upper-bound audit
**Branch**: `study01xu`
**Reviewed commit**: `7d6e99f2519a9b079d50cf838e14b271cff14255` (P5a executor report, final)
**Execution commit**: `76906a986e38ab81638ca7c380ac05b1f55d043d` (MDM formal run)
**Analysis commit**: `bc589e396f2799f990690c2c21d19c49b08996f3` (merge_and_analyze + sealing)

## Review Scope

Per `07-剩余实验目标与规划.md` §4.2 and phase P5b gate checklist:

1. MDM health: 100% success / 100% convergence across all 79,425 runs
2. 94.7% migration rate computed from valid data (not dropna fabrication)
3. Cohort identification correctness against frozen shared_data chunks
4. 743 samples at δ=1.00 — whether this warrants further extension
5. Manifest provenance completeness
6. Conditional claim framing correctness
7. No E1/E2/E4 sealed evidence overwritten

## Verification Summary

| Check | Status |
|-------|--------|
| MDM health: 79,425/79,425 success, 100% convergence | ✅ |
| Migration rate: 2,800/2,958 = 94.66%, tie-breaking frozen in code | ✅ |
| Cohort SHA256 from frozen shared_data chunks, independently verifiable | ✅ |
| δ=1.00 grid-edge: 743 samples (25.1%), reported as potential boundary artifact | ✅ |
| Manifest: generation commit, execution commit, file SHA256, input chunk hash all present | ✅ |
| Claims conditioned on "original best delta = target cohort delta" | ✅ |
| New directory `delta_upper_bound_audit/`, zero E1/E2/E4 overwrite | ✅ |
| Fail-closed: mandatory 25/25 coverage, NaN guard, tuple unpacking fix verified | ✅ |
| Tests: 100/100 pass, including 11 R2-SHA verification tests | ✅ |
| Tie-breaking: 2 unit tests + code-level implementation | ✅ |

## Scientific Resolutions

Per the review, the following scientific conclusions are formally recorded:

### Resolution 1: R2 Formally Passes

The delta upper-bound audit experiment (R2) is formally complete and accepted. All contract requirements per §4.2 are satisfied. The first-run BLOCK (commit `5059ce2`, fabricated 0% migration via `AttributeError` + `dropna`) was correctly diagnosed, fixed, and re-run. The re-run (commit `76906a9`) produced valid results with 100% MDM success across all 79,425 extended runs.

### Resolution 2: δ ≤ 0.50 Is Insufficient for the Endpoint Cohort

The current `δ ∈ [0.00, 0.50]` selection grid materially truncates risk curves for samples whose original-grid optimum lies at the δ = 0.50 boundary. Among the 2,958 samples in the δ = 0.50 endpoint cohort, 2,800 (94.66%) achieve a meaningfully lower loss at some δ > 0.50 when the grid is extended to 1.00. The mean loss improvement is 0.0310 (median 0.0115), with a mean relative improvement of 32.9% over the original-grid optimum.

This conclusion is **conditional**: it applies to the δ = 0.50 endpoint cohort specifically, not to the full 45,000-sample population. The δ = 0.48 near-endpoint cohort is stable (1.4% migration, negligible effect size), confirming the truncation is boundary-specific.

### Resolution 3: 2,800 / 2,958 Migration, 94.66%

After tie-breaking (`migrated = extended_best_delta > 0.50 AND loss_improvement > 1e-12`, frozen in `merge_and_analyze()`), exactly 2,800 of the 2,958 δ = 0.50-endpoint samples migrate to a delta > 0.50. Two samples with improvement ≈ 1.4 × 10⁻¹⁶ are correctly classified as non-migrated by the code. The migration rate is 94.66%.

### Resolution 4: δ = 1.00 Has 743 Samples at Grid Edge

Of the 2,958 δ = 0.50 endpoint cohort samples, 743 (25.1%) select δ = 1.00 as their extended-grid optimum — the far edge of the extension grid. The extended-best-delta distribution is broad (0.52–1.00) with a concentration at the grid edge, consistent with a boundary artifact: the true optimum for these samples may lie beyond 1.00. This is reported as an observation requiring scientific interpretation, not as evidence that δ = 1.00 is sufficient.

### Resolution 5: No Further Extension in This Round

This round (R2) does **not** extend the grid beyond δ = 1.00. The 743-sample grid-edge concentration is recorded as a known open question. If future work seeks to determine a new sufficient upper bound (e.g., extending to δ = 1.50 or conducting a full-population extension), that work must be established under a **separate frozen contract** with its own gate, cohort definitions, and stop conditions. The current R2 audit is a targeted cohort audit; its results do not automatically authorize or pre-commit to any specific follow-up extension.

## Gate Resolution

**R2 is formally APPROVED.** The P5b gate is cleared. The delta upper-bound audit experiment is complete and its scientific conclusions are frozen as stated above.

## Next Step

Per `07-剩余实验目标与规划.md` §3: proceed to **P6** — freeze real data source and sampling contract.

---

*This review records the Codex APPROVE verdict for P5b. It does not constitute a new independent re-review by the executor. The five scientific resolutions above are binding conclusions from this gate.*
