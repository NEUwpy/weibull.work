# Study01 P6 — Codex APPROVE Record

**Review type**: Independent review (Codex)
**Date**: 2026-07-25
**Branch**: `study01xu`
**Approval tip**: `cc1269c` (docs: REVISE v3 — sync all doc references)
**Contract content commit**: `2ee23a8` (REVISE v2 — KS name, piecewise CDF, median-model removal)
**Reviewer**: Codex
**Verdict**: **APPROVE** ✅

---

## Review Scope

P6: Freeze real data source, sampling contract, evaluation metrics, and 15 E3b-contract retrained selectors; no method comparison run.

Per `07-剩余实验目标与规划.md` §4.3 and frozen contract `P6_FROZEN_CONTRACT.md` (v1.1-FROZEN-REVISED).

## Items Verified

| # | Item | Status |
|---|------|--------|
| 1 | Data source identity (NIST 6061-T6, Birnbaum & Saunders 1958) | ✅ |
| 2 | Original `BIRNSAUN.DAT` SHA256 verified (`7814c533...`) | ✅ |
| 3 | Converted `lifetimes.csv` SHA256 verified (`43c85155...`) | ✅ |
| 4 | Admission gate: 101 lifetimes, OLS R² = 0.995 > 0.70 | ✅ |
| 5 | License: NIST-hosted factual data, not copyrightable, cite source | ✅ |
| 6 | Experiment design: n ∈ {7, 10, 20}, 500 repeats, no replacement | ✅ |
| 7 | Seed namespace: `base_seed=20260725 + train_n*10000 + repeat_index` | ✅ |
| 8 | Default δ=0.1, L2 per-n frozen deltas from E1/E2 cross-fit | ✅ |
| 9 | NN: 15 E4d-contract selectors (5 folds × 3 seeds), no cherry-picking | ✅ |
| 10 | Primary metric: one-sample two-sided KS distance with piecewise CDF | ✅ |
| 11 | Failure handling: D=1 for failures, no silent drops | ✅ |
| 12 | NN aggregation: per-model first → cross-model distribution | ✅ |
| 13 | Output spec: 5 files, manifest with provenance, config hash | ✅ |
| 14 | Stop conditions: gate failure, SHA256 mismatch, data leakage, < 15 selectors | ✅ |
| 15 | REVISE v1 issues (6 items) addressed in `123355f` | ✅ |
| 16 | REVISE v2 issues (3 items) addressed in `2ee23a8` | ✅ |
| 17 | 36 contract self-tests passing | ✅ |
| 18 | `_P6_PLACEHOLDER_GUARD` active — prevents accidental placeholder execution | ✅ |
| 19 | Conversion script self-verifying (SHA256 check) | ✅ |
| 20 | No method comparison results generated | ✅ |

## Resolution

P6 freeze is formally complete. The contract, data source, admission gate, evaluation metrics, and 15-selector commitment are all frozen and locked.

## Conditions for P7

- P7 must implement against the frozen P6 contract without amendment.
- `_P6_PLACEHOLDER_GUARD` must remain enabled until P7 passes independent review.
- P7 must not run P8a formal comparison; only implement and test.
- If a BLOCKER is found during P7, contract must be revised and re-frozen.

## Signature

Codex APPROVE, tip `cc1269c`, 2026-07-25.
