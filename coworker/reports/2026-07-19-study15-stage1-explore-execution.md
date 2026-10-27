# Study1.5 Stage 1 — Execution Report (Final)

> **Date**: 2026-07-19 → 2026-07-20
> **Executor**: OpenCode/DeepSeek
> **Contract**: v0.1 frozen
> **Status**: CONFIRMED — both phases complete, analysis finalized

---

## Commit History

| Commit | Purpose |
|--------|---------|
| `f438a9b` | Planning baseline (01/02/03 docs only) |
| `1887b2c` | Initial implementation |
| `306e7f55` | Explore execution code (frozen) |
| `c8c4de6` → `ea52c94` → `ce0f67b` → `d07fd3a` | REVISE fixes (bootstrap, manifest, multi-seed) |
| `2d0e710` | Confirm execution code |
| `61294a0` | Final manifest fix (phase-local only) |
| `5d00c79` | Strip stale ../ entries from phase manifests during analyze |
| `f9cf0e3` → current | Report corrections, evidence packaging |

---

## Execution Summary

| Phase | Seeds | Models | Completed | Failed |
|-------|-------|--------|-----------|--------|
| Explore | 42 | 30 | 30 | 0 |
| Confirm | 2026, 3407 | 60 | 60 | 0 |
| **Total** | 42, 2026, 3407 | **90** | **90** | **0** |

---

## Contract Verification

| Contract | Expected | Actual | Status |
|----------|----------|--------|--------|
| run_status rows | 90 | 90 | PASS |
| selected_predictions rows | 405,000 | 405,000 | PASS |
| metrics_by_target_n rows | 135 (per-n) | 135 | PASS |
| multi_seed_summary rows | 42 | 42 | PASS |
| multi_seed n_seeds | 3 | 3 | PASS |
| J/S/T/L counts | 9/27/27/27 | 9/27/27/27 | PASS |
| Source CSV SHA256 | contract | matched | PASS |
| J1 recomputability | < 1e-12 | 1.1e-16 | PASS |
| Study01 formal unchanged | ✓ | git diff clean | PASS |
| Phase-local manifest | zero stale hashes | zero | PASS |
| Root manifest | 115-file hash match | 115/115 | PASS |
| Tests study15 only | 23/23 | 23 | PASS |
| Tests combined | 34/34 | 34 | PASS |

---

## Key Artifacts

| File | Path | Rows |
|------|------|------|
| run_status.csv | stage1/ | 90 |
| selected_predictions.csv | stage1/ | 405,000 |
| metrics_by_target_n.csv | stage1/ | 135 |
| multi_seed_summary.csv | stage1/ | 42 (n_seeds=3) |
| bootstrap_intervals.csv | stage1/ | 42 |
| representation_comparison.csv | stage1/ | 6 |
| transfer_matrix.csv | stage1/ | 54 |
| report.md | stage1/ | ✓ |
| manifest.json (root) | stage1/ | 115 files, all hashes match |

---

## Stop Declaration

- Both Explore and Confirm complete under frozen v0.1 contract.
- 90/90 models, 0 failures.
- All contract tests pass.
- Scientific conclusions and boundaries documented in `report.md`.
- Study01 source unchanged; Study02 not accessed.
- Not self-assessing APPROVE — waiting for independent reviewer.
