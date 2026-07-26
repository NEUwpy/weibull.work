# Study01 P7 — Codex APPROVE Record

**Review type**: Independent review (Codex)
**Date**: 2026-07-25
**Branch**: `study01xu`
**Approval tip**: `d619a40` (fix(study01): P7 final fixes — monkeypatch cross-model test + report consistency)
**P6 contract commit**: `2ee23a8` (P6_FROZEN_CONTRACT.md v1.1-FROZEN-REVISED)
**Reviewer**: Codex
**Verdict**: **APPROVE** ✅

---

## Review Scope

P7: Real data holdout validation pipeline implementation per frozen P6 contract (`P6_FROZEN_CONTRACT.md` v1.1-FROZEN-REVISED).

Per `07-剩余实验目标与规划.md` §4.3, phase P7.

## Items Verified

| # | Item | Status |
|---|------|--------|
| 1 | Seed & split infrastructure: frozen seed derivation, 500 without-replacement splits, identical splits across methods | ✅ |
| 2 | Metrics: one-sample two-sided KS distance with piecewise 3P Weibull CDF | ✅ |
| 3 | Failure handling: 5 frozen criteria, D=1 imputation, no silent drops | ✅ |
| 4 | Default method: δ=0.1 fixed | ✅ |
| 5 | L2 method: frozen per-n deltas (n=7: 0.10, n=10: 0.10, n=20: 0.08) | ✅ |
| 6 | NN method: 15 E4d-contract retrained selectors, per-fold P99 failure penalty, 13 features, no leakage | ✅ |
| 7 | Aggregation: per-model first → cross-model distribution, no median model, no pooled pseudo-inference | ✅ |
| 8 | Output protection: fail-closed, no bypass, no --bypass-guard or --skip-nn flags | ✅ |
| 9 | Pre-flight validation: all 45 chunks validated, chunk identity mapping, deep input gate | ✅ |
| 10 | Manifest: config hash, versions, NN training info, git porcelain status | ✅ |
| 11 | Frozen config SHA256: deterministic, independently verifiable | ✅ |
| 12 | Support-set violation NaN for NN prediction failures | ✅ |
| 13 | Summary: primary stats, complete-case sensitivity, paired wins, NN distribution | ✅ |
| 14 | 5 contracted output files only (no 6th file) | ✅ |
| 15 | Cross-model distribution in summary JSON (survives production write path) | ✅ |
| 16 | `_P6_PLACEHOLDER_GUARD` active | ✅ |
| 17 | No formal P8a comparison run executed | ✅ |
| 18 | 88 P7 pipeline tests + 16 gate tests + 20 P6 contract tests = 124 total, all passing | ✅ |
| 19 | E1/E2/E3/E4/R1/R2 artifacts unchanged | ✅ |
| 20 | No data/metric/network/seed/failure/aggregation contract changed | ✅ |

## REVISE History

| Round | Commit | Issues | Resolution |
|-------|--------|--------|------------|
| REVISE v1 | `079b979` | 6 issue groups | Fixed |
| REVISE v2 | `3a52ff9`, `3947235` | 4 additional issues | Fixed |
| REVISE v3 | `06cfd02a` | 4 remaining issues | Fixed |
| Final | `d619a40`, `c5e3309` | Cross-model test + report consistency | Fixed |

## Resolution

P7 pipeline implementation is complete, tested, and approved. All P6 frozen contract requirements are satisfied. The `_P6_PLACEHOLDER_GUARD` remains active.

## Conditions for P8a

- P8a must run against the frozen P6 contract without amendment.
- P8a must use this approved P7 pipeline code (generation commit `d619a40` or later P8a-specific commit).
- `_P6_PLACEHOLDER_GUARD` must be released only via narrow, auditable P8a authorization.
- P8a results must be independently reviewed (P8b) before any claim is made.
- If a BLOCKER is found during P8a, stop and report; do not amend the contract.

## Explicit Exclusion

P7 APPROVE authorizes entry into P8a formal run only. It does NOT:
- Pre-approve P8a results
- Authorize changing the P6 frozen contract
- Authorize changing data, seeds, models, metrics, or failure rules
- Authorize cherry-picking results post-hoc

## Signature

Codex APPROVE, tip `d619a40`, 2026-07-25.
