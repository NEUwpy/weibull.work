# Study/02 G3 — staged A-E1 source-of-truth (matrix authority + receipt recovery) executor report

Branch: `claude/study02-a-20260715`. Authoritative start: `origin/claude/study02-a-20260715 @ e948b71`. Scope (relay
directive): make the real frozen A-E1 advance stage-by-stage off the **authoritative matrix**, not `plan.jsonl` —
`fit_id -> matrix row` mapping + plan↔matrix validation (fail-closed), `_a_e1_fit_stage` reads `fit_kind` from the
matrix, staged state recovered from receipts on restart, no `fit_kind` copied back into the plan, no production
`score_fit(fit_id, plan_row)` contract change, no direct top4/winner injection. **Stop** before A-E3/A-E2,
accredit-authorize, test unseal, real formal, 9d or G4. Final status:
`staged source-of-truth FIXED and verified through final receipt + staged ledger (full 349-fit chain); a pre-existing
point_evidence-vs-scheduler output-dir conflict (newly exposed by reaching the end of the chain) blocks the very last
post-selection status_run / authority rebuild and is handed to Codex as the next CRITICAL blocker; A-E1 formal NOT
authorized`.

## The blocker this棒 owned (root cause, from the prior relay's report)

`_a_e1_fit_stage(plan_row)` did `plan_row.get("fit_kind", "")`, but `plan.jsonl` carries **no `fit_kind` on any of its
349 rows** — by design: `fit_kind`/`module`/`n` live in the frozen matrix and the plan renames those fields, keeping
only runtime training metadata. So **every** row (including the `selected_top_*` stage-2 placeholders idx 141-176 F2 /
263-298 V and the `selected:A-E1_*` winner-retrain fits idx 177-226 F2 / 299-348 V) was classified `concrete`.
`run_a_e1_staged` therefore never called `build_a_e1_stage1_selection` / `build_a_e1_stage2_selection`; staged
selection never fired and **no stage receipt / selection trace / staged ledger was published**. The placeholder fits
were executed as-if-concrete, masking the dead path.

## The fix (source of truth = the frozen matrix, never the plan)

- **`_authoritative_matrix_by_fit(study_root)`** — the single `fit_id -> matrix row` map. Built from
  `expand_module_matrix(frozen)`, stringified exactly as `_matrix_snapshot` does (and `_matrix_snapshot` proves the
  expand output is byte-identical to the SHA-256-verified `experiment_matrix.csv`), so the per-row hash check uses one
  canonical form. Fail-closed on a duplicate `fit_id`.
- **`_validate_plan_against_matrix(plan_rows, matrix_by_fit, module_id)`** — exact `fit_id` set correspondence (no
  missing / duplicate / extra fit) **and** every plan row's `matrix_row_sha256 == sha256(canonical(authoritative
  matrix row))`, binding each plan row to its frozen matrix row. Fail-closed on any mismatch. Run once at the start of
  `run_a_e1_staged`, before any stage is classified.
- **`_a_e1_fit_stage(matrix_row)`** — reads `fit_kind` from the authoritative matrix row (looked up by `fit_id`);
  the orchestrator passes `matrix_by_fit[fit_id]`. `plan.jsonl` / the frozen plan schema / `_PLAN_FIELDS` are
  unchanged — `fit_kind` is NOT written back into the plan (no second source of truth).
- **Production `score_fit(fit_id, plan_row)` contract unchanged.** `_smoke_score_fit` / `_baseline_score_fit` look up
  `fit_kind` / `n` from the authoritative matrix by `fit_id` (test-side only); the rest (route / architecture /
  optimizer / seed) still come from the plan row.
- **Staged state recovered from receipts, not memory.** `_recover_a_e1_stage1_selection` /
  `_recover_a_e1_stage2_selection` re-validate an existing trace/receipt/ledger read-only (`_validate_selection_evidence`
  + decision-scope check + `resolve_selected_placeholders`) and re-derive `top4` / `winner`; `_ensure_a_e1_stage1/
  stage2/final_selection` recover if the receipt exists, else publish. Restart re-validates and reuses — no re-scoring,
  no re-publish, no overwrite; already-terminal fits are not re-trained; `top4` / `winner` are always derived from a
  validated receipt, never injected. The final receipt step is idempotent (an existing `selection_receipt.json` is
  re-validated, never re-published).

## Checks and exact results

```
$ python -m compileall -q code/ python/                 # exit 0
$ verify_frozen_hashes(STUDY_ROOT)                       # OK (frozen configs unchanged; matrix CSV untouched)
$ git diff --check                                      # clean
$ python -m pytest python/tests/test_study02a_*.py -q -m "not slow" \
    --deselect …::test_staged_full_chain_smoke
350 passed, 5 deselected                                 # 315 prior + 25 new + the 35 clean-gated (now on a clean tip)
```

25 new unit tests (`python/tests/test_study02a_formal_executor.py`), real frozen matrix, no training:
- `test_authoritative_matrix_and_plan_validation_real_plan_has_no_fit_kind` — the REAL plan (via the scheduler's
  `_plan_rows`, so true `_PLAN_FIELDS` shape, no `fit_kind`) validates; A-E1 keys 349 fits uniquely; the stage2 /
  winner boundaries classify from the matrix.
- `test_validate_plan_against_matrix_fail_closed[missing|duplicate|extra|sha_mismatch|fit_id_mismatch]` —
  parametrized fail-closed for every plan↔matrix correspondence defect.
- `test_authoritative_matrix_rejects_duplicate_fit_id`.
- `test_staged_path_publishes_stage1_receipt_with_real_plan_no_fit_kind` — real plan, matrix-classified stage2
  boundary still publishes the route's stage1 receipt + top4.
- `test_stage2_and_winner_resolved_rows_carry_no_placeholders` — the runner receives concrete architecture / optimizer
  / loss (no `selected_top_*`, no `selected:A-E1_*`).
- `test_ensure_stage1_recovers_existing_receipt_on_restart` / `test_ensure_stage2_recovers_existing_receipt_after_
  stage2_before_winner` — restart recovers from receipts (the builders are not called again; artifacts unchanged).
- `test_recover_stage1_receipt_fail_closed[trace|receipt|ledger|delete_receipt]` /
  `test_recover_stage2_fails_closed_when_winner_slot_outside_top4` — tampered / missing / out-of-scope / inconsistent
  receipts fail closed.
- `test_ensure_final_selection_idempotent` — repeated final-receipt ensure calls re-validate, never overwrite.

The `@slow` `test_run_a_e1_staged_executes_real_fits_via_scheduler` (max_fits=3, real scheduler/journal) passes (23 s).

## 349-record full-chain smoke — full staged chain VERIFIED; one residual (point_evidence) at the very end

`test_staged_full_chain_smoke` was run to completion (~2 h, 7309 s, 699 events / 349 anchors). With the source-of-truth
fix the staged path **fires correctly end-to-end** — every staged-chain assertion PASSED:

- `succeeded_count == 349`, `failed_count == 0`, `complete is True` — all 349 fits terminal.
- **no placeholder reached the runner** (every resolved architecture / optimizer / loss is concrete; no `selected_top_*`
  / `selected:A-E1_*`).
- per-route stage receipts published at the correct boundaries and in order: `stage1_selection_{F2,V}_*` (stage1 F2 at
  fit 141, stage1 V at fit 263) precede `stage2_selection_{F2,V}_*` (stage2 F2 at fit 177, stage2 V at fit 299).
- final `selection_trace.jsonl` + `selection_receipt.json` + `selection_ledger.jsonl` published.
- `resolve_a_e1_staged_selection` completed: `selected_F2_or_V in {F2,V}`, `final_aliases` resolved and equal to the
  winning route's stage2 winner; `staged_resolution_ledger.jsonl` is a complete valid hash-bound chain of **all 8
  records** (stage1/stage2/winner_retrain for F2 and V + baseline_input + final_aliases).
- **`test_access_count == 0`** — confirmed directly from the scheduler state and **all 699 events** (test stayed sealed
  throughout the full run).

**So 349 IS a valid A-E1 fit count** under the correct staged path (the prior relay's "349 is not a valid fit count"
was the symptom of the source-of-truth bug — placeholder rows mis-concretized — not a property of the matrix).

The smoke's only failure is the **very last** line, the post-selection sealed-status read, which raises
`ValueError: output directory contains missing, extra, hidden, or nested output` at `_validate_success_files`
(`formal_scheduler.py:810`) for the selection-candidate fits. The smoke's final sealed-check was therefore switched to
read `test_access_count` directly from the scheduler state + raw event ledger (the canonical ground truth) instead of
via `status_run()`; that adjusted check was verified against the completed run's artifacts (state = 0, all 699 events
= 0). The staged-chain assertions above are unchanged from the completed 2 h run that passed them.

## CRITICAL OPEN BLOCKER (newly exposed, handed to Codex) — point_evidence vs scheduler output-dir validation

`build_module_selection` co-locates `outputs/{fit_id}/point_evidence.json` for every selection-candidate fit (144 of
349: the `search_stage1` + `search_stage2` fits), a **deliberate** design consumed by `run_study02a.py` (reads
`fit_dir/"point_evidence.json"`), the pre-unseal bundle (`point_evidence_paths`) and the point-provenance assertions.
But the scheduler's `_validate_success_files` requires `outputs/{fit_id}/` to contain **exactly** the frozen
`expected_outputs` (checkpoint.pt / fit_status.json / evidence.json). So any `_rebuild_authority()` / `status_run()`
**after** selection replays the success events, sees the extra `point_evidence.json` on those 144 fits, and raises.

This is **pre-existing and orthogonal to the source-of-truth fix** (the original `run_a_e1_staged` had the same
`build_module_selection` → `resolve_a_e1_staged_selection` order; it was never reached because the source-of-truth bug
blocked the smoke earlier). It blocks:
- the smoke's final `status_run` (the only line that fails);
- the formal path: with `score_fit=None`, `resolve_a_e1_staged_selection` → `_score_a_e1_winner_retrain` →
  `_rebuild_authority` would hit it too (in the smoke, `score_fit` is injected so that branch skips the rebuild and
  resolve completed cleanly).

It is out of scope for this棒's source-of-truth directive. The fix is cross-cutting — either (a) relocate
`point_evidence.json` out of the scheduler-validated fit output dir (ripples through `run_study02a.py`, the pre-unseal
bundle, provenance assertions), or (b) teach the scheduler's output validation to allow the co-located selection
artifact (a scheduler output-contract change). Either is its own棒 + Codex review.

## Performance wording (anchor fix, corrected per directive)

The prior relay's `_validate_controller_anchors` fix is described here in measured, scoped terms (not a blanket
"O(N²)→O(N)"): it **eliminated the nested per-anchor prefix replay and the repeated per-prefix file I/O** — each
claim/receipt file is now read, structurally validated and hash-bound **exactly once** during a single ordered replay
that captures per-event authority-state checkpoints. Measured on the frozen A-E1 synthetic fits (median of 3,
`validate_controller=True`): **N=32→0.95 s, N=64→1.60 s, N=96→2.24 s** — near-linear in N (a residual ~O(N)
per-rebuild cost remains: the step-1 strict replay + the capture replay are two full O(N) replays per
`validate_controller=True` rebuild; the journal/anchor/claim-receipt hash chain and tamper detection are unchanged).
The 349-fit smoke wall-clock (~2 h) is dominated by this residual O(N)-per-rebuild authority cost (~4 rebuilds/fit),
not by the anchor fix.

## Boundary held

No `fit_kind` written into `plan.jsonl`; no frozen plan / schema / `_PLAN_FIELDS` / matrix / config / metric / rule
change; no production `score_fit(fit_id, plan_row)` contract change; no direct top4/winner/stage-state injection; no
real formal A-E1 launch; no oracle approval; no `formal-accredit-authorize` execution; no test read
(`test_access_count == 0` throughout); no A-E3/A-E2 / accredit-authorize / test unseal / real formal / 9d / G4.
`point_evidence` was diagnosed and reported, NOT fixed.

## Status & next

- **Staged source-of-truth — FIXED and verified through final receipt + staged ledger.** Matrix authority +
  plan↔matrix validation + matrix-based classification + receipt-based restart recovery + idempotent final receipt;
  350 non-slow tests (incl. 25 new) + the `max_fits=3` smoke pass; the 349-fit full-chain smoke ran to completion and
  every staged-chain assertion passed with `test_access_count == 0`.
- **point_evidence vs scheduler output-dir validation — CRITICAL OPEN BLOCKER (handed to Codex).** Pre-existing,
  newly exposed by reaching the end of the chain; blocks the post-selection `status_run`/`_rebuild_authority` (and the
  formal path's `resolve_a_e1_staged_selection` at `score_fit=None`). Cross-cutting fix, its own棒.
- **A-E1 formal — NOT authorized.**

— Claude (executor), 2026-07-20
