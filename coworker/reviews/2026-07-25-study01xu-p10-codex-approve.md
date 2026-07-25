# Study01 P10 — Codex APPROVE Record

**Review type**: Independent review (Codex P10)
**Date**: 2026-07-25
**Branch**: `study01xu`
**Approval tip**: `8ef74b8` (fix/docs: P10 REVISE v2 — consistent E3b wording + precise commit references)
**Approval baseline**: `1d11a6a` (P8b Codex APPROVE)
**Reviewer**: Codex
**Verdict**: **APPROVE** ✅

---

## Review Scope

P10: Study01 final evidence summary table, status synchronization, and closure documentation.

## Items Verified

| # | Item | Status |
|---|------|--------|
| 1 | E3b J1=0.547 correctly positioned (between L5 and L6, not L3-L4) | ✅ |
| 2 | R2 conclusion correct (94.66% migration, not "few") | ✅ |
| 3 | Provenance: 4 data files unchanged, manifest edited, SHA256SUMS_p8a added | ✅ |
| 4 | All status documents synced (planning, evidence index, submission tracker, changelog) | ✅ |
| 5 | Closing language precise ("experiment + evidence chain closed", not "Study01 complete") | ✅ |
| 6 | Product table with actual commit hashes, split into artifact/approval columns | ✅ |
| 7 | P9 correctly marked as optional, not a closure blocker | ✅ |
| 8 | Unsupported claims explicitly listed with reasons | ✅ |
| 9 | G5-G7 remaining work acknowledged | ✅ |

## Conditions for G5-G7 (Paper Writing)

- All formal experiments are sealed and independently reviewed.
- P10 evidence summary is the authoritative claim-to-artifact map.
- No new experiments, data, or model training may be introduced.
- Paper must use the 5-part structure, not the internal 9-chapter skeleton.
- Each claim must trace to a specific sealed artifact and approval commit.
- Unsupported claims (continuous-space, arbitrary-n, single production model, multi-dataset) must not enter the paper.

## Signature

Codex APPROVE, tip `8ef74b8`, 2026-07-25.
