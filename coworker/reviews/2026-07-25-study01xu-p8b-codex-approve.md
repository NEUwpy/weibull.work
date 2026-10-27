# Study01 P8b — Codex APPROVE Record

**Review type**: Independent review (Codex P8b)
**Date**: 2026-07-25
**Branch**: `study01xu`
**Approval tip**: `1d11a6a` (fix/docs: P8b REVISE v2 — correct NN distribution, sync test counts, exact-command honesty)
**P8a generation commit**: `3330523`
**P8a artifact commit**: `7946108` (raw outputs — unchanged)
**Reviewer**: Codex
**Verdict**: **APPROVE** ✅

---

## Review Scope

P8b: Independent review of P8a formal real-data holdout experiment on NIST 6061-T6.

Covers:
- P8a formal execution (generation commit `3330523`, 25,500 rows, 1529.7s)
- P8a artifact integrity (CSV, summary, stability, run log bit-identical to `7946108`)
- P8a seal structure (SHA256SUMS_p8a binds all 5 files; manifest excluded from self-hash)
- P8a authorization lifecycle (`True` only in generation commit, `False` in final tip)
- P8a executor report statistics (independently recomputed from raw CSV)

## Items Verified

| # | Item | Status |
|---|------|--------|
| 1 | 25,500 rows, primary key unique, D in [0,1] | ✅ |
| 2 | 15 NN models, 45 stability rows | ✅ |
| 3 | Generation commit `3330523` clean tree, `_P8A_FORMAL_AUTHORIZED=True` | ✅ |
| 4 | Final tip `_P8A_FORMAL_AUTHORIZED=False` | ✅ |
| 5 | Raw artifacts bit-identical to `7946108` (not re-generated) | ✅ |
| 6 | SHA256SUMS_p8a: all 5 file hashes verified byte-for-byte | ✅ |
| 7 | Manifest self-hash excluded; `output_hashes` covers 4 data files | ✅ |
| 8 | `recovery_attempts=1` accurately recorded | ✅ |
| 9 | Primary median D values independently recomputed | ✅ |
| 10 | Default/L2 paired win/loss/tie independently verified | ✅ |
| 11 | NN cross-model distribution: all 15 models verified per train_n | ✅ |
| 12 | Support-set violation rates included | ✅ |
| 13 | Exact command gap honestly documented (`exact_command_recorded: false`) | ✅ |
| 14 | All 153 tests pass | ✅ |
| 15 | E1/E2/E3/E4/R1/R2 artifacts untouched | ✅ |
| 16 | No P8a re-run | ✅ |
| 17 | No P6 contract amendment | ✅ |

## REVISE History

| Round | Tip | Issues | Resolution |
|-------|-----|--------|------------|
| REVISE v1 (P8b) | `38d4351` | 5 blocking: self-hash, auth open, report stats, provenance, aux results | Fixed |
| REVISE v2 (P8b) | `1d11a6a` | 3 narrow: NN distribution, test counts, exact command | Fixed |
| **APPROVE** | `1d11a6a` | — | All issues resolved |

## Conditions for P10 (Study01 Closure)

- P8a/P8b is formally closed. No re-run, no amendment.
- P10 may summarize the full Study01 evidence chain.
- P9 (optional S1/S2 diagnostics) remains optional — not a blocker for Study01 closure.
- Study01 can now proceed to paper writing.

## Signature

Codex APPROVE, tip `1d11a6a`, 2026-07-25.
