# Study/02 G3 — point_evidence relocation (Codex option a) executor report

Branch: `claude/study02-a-20260715`. Authoritative start: `origin/claude/study02-a-20260715 @ 1e4edd1`. This棒
implements the Codex verdict on the CRITICAL point_evidence-vs-scheduler blocker.

## Codex verdict (this棒's contract)

- point_evidence blocker root cause: **APPROVE**.
- **APPROVE option (a)** — relocate the selection evidence out of the scheduler-authority fit output dir.
- **BLOCK** any scheduler allowed-extra, snapshot exclusion, or output-dir relaxation.
- No more pure-design棒; implement directly per the revised contract.
- Stop after commit/push; await Codex re-review. No A-E3/A-E2 / accredit-authorize / test unseal / real
  formal / 9d / G4; no self-claimed formal APPROVE.

## The fix (option a — relocate; scheduler authority model UNCHANGED)

`build_module_selection` now writes each fit's point evidence to a **selection-owned** directory,
`run_dir/selection/point_evidence/{fit_id}.json`, instead of co-locating it under `outputs/{fit_id}/`. The
selection candidate IS determined by the frozen matrix (so it is known at claim time), but point evidence is a
**post-selection lifecycle** artifact: it cannot be a pre-training-success output that must exist in the fit
output dir before training has produced a checkpoint. Relocating it (not relaxing the scheduler) keeps
`outputs/{fit_id}/` exactly equal to the frozen `expected_outputs`, so `_validate_success_files` passes on any
post-selection `_rebuild_authority` / `status_run`.

**Production changes (commit `4d5c9cd`):**

- **`formal_executor.build_module_selection`** (`code/study02a/formal_executor.py`): the write target moves to
  `run_dir/selection/point_evidence/{fit_id}.json`; `_publish_bytes_no_replace` already `mkdir(parents=True,
  exist_ok=True)` + no-replace, so no new I/O logic. A new `_validate_selection_point_evidence_dir` runs after
  the write: the dir must hold **exactly** the expected `{fit_id}.json` (one per `evaluations_by_fit` key);
  missing / extra / duplicate / alias (symlink/reparse/hardlink) / non-file / nested / unknown-fit all
  **fail-closed**. point evidence canonical content, content SHA (`point_evidence_sha256`), supporting hash,
  trace/receipt binding, and the checkpoint-independent rebuild (`rebuild_selection_point_provenance`, which
  reads `outputs/{fit_id}/checkpoint.pt`) are all unchanged. The pre-unseal bundle is path-agnostic
  (`point_evidence_paths` dict) and needed no change.
- **`run_study02a.accredit_build`** (`code/run_study02a.py`): rewritten.
  - Derives the expected selection fit_id set from the **frozen matrix** via `build_decision_specs` (the same
    `evaluations_by_fit` key set the publisher uses), **not** a directory scan of `outputs/`. (For A-E1: the 4
    architecture/stage2 decisions → 144 search_stage1 + search_stage2 fits.)
  - Reads relocated point evidence from `selection/point_evidence/{fit_id}.json`; `evidence.json` /
    `checkpoint.pt` still read by `fit_id` from `outputs/{fit_id}/`.
  - **Fixes the `plan_row["n"]` KeyError**: the plan carries `n_mode`/`fixed_n` (the matrix `n` is renamed at
    plan-build time; the plan has no `n`). `_recover_selection_n` recovers the concrete n (a selection candidate
    is always concrete-n; shared_n / missing fixed_n fail-closed). The value is not written back into the plan.
  - **A failed selection fit is never silently skipped.** Three independent sources must agree, else
    fail-closed: the scheduler terminal receipt (`receipts/{fit_id}.{succeeded|failed}.json` → `_fit_terminal_receipt`
    returns `(state, failure_code)`), the point-evidence failure record (`evaluation.failed`), and the training
    evidence file (`evidence.json` present iff succeeded). A failed fit (no `evidence.json`) gets a failure
    fit_status from `failure_code` + the frozen penalty; it cannot vanish from accreditation because its
    `evidence.json` is absent.
- **`formal_scheduler.py` output-dir validation UNCHANGED** (constraint 2). No change to frozen matrix / plan
  schema / `_PLAN_FIELDS` / selection rule / artifact-trace-receipt-bundle version / scientific metrics.

## Checks and exact results

```
$ python -m compileall -q code/ python/                 # exit 0
$ git diff --check                                      # clean
$ verify_frozen_hashes(STUDY_ROOT)                      # OK (frozen configs unchanged)
$ matrix sha256                                         # fad701af... == frozen FROZEN_MATRIX_SHA256
$ python -m pytest python/tests/test_study02a_*.py -q -m "not slow" \
    --deselect ...::test_staged_full_chain_smoke \
    --deselect ...::test_post_selection_authority_rebuilds_with_relocated_point_evidence
356 passed, 6 deselected                                # (was 350 + 6 new; the prior 35 "dirty code" gates
                                                        #  resolved once the implementation was committed)
```

New unit tests (`python/tests/test_study02a_formal_executor.py`):
- `test_formal_accredit_build_generates_sealed_bundle` (rewritten on the **real** A-E1 matrix, 144 candidates):
  contract 1 (no `outputs/{fit_id}/point_evidence.json` after selection; `selection/point_evidence/` holds
  exactly the 144), contract 3 (relocated content byte-identical to `serialize_point_evidence`), contract 6
  (fit_status covers all candidates; `n` recovered from `n_mode`/`fixed_n`, no `plan_row['n']`); plus the
  bundle + accredit-authorize chaining (synthetic, no real test unseal of study data).
- `test_accredit_build_failed_selection_fit_is_not_silently_skipped`: contract 7 — one failed candidate
  produces a failure fit_status row (`failure_penalty=10.0`, `failure_message=dead_identity_no_outputs`,
  empty checkpoint/validation_score); every candidate still present (none vanished).
- `test_validate_selection_point_evidence_dir_fail_closed[missing|extra|unknown_fit|nested|wrong_suffix]`:
  contract 5 — the new dir validator rejects each defect.

Restored / new slow tests:
- `test_post_selection_authority_rebuilds_with_relocated_point_evidence` (focused, 17 s, **passes**): real
  scheduler (materialize + claim + `_write_outputs` + `record_fit_succeeded`, 5 fits) → `build_module_selection`
  publishes relocated point evidence → the **real** `status_run`/`_rebuild_authority` succeed post-selection,
  `test_access_count == 0`, `outputs/{fit_id}/` holds no point evidence, `selection/point_evidence/` holds 144.
  This is the blocker-fix verification on a real scheduler (contracts 2 + 8).
- `test_staged_full_chain_smoke`: final check **restored to the real** `status_run`/`_rebuild_authority` (no
  `scheduler_state.json` read workaround) — contract 8/9. **PASSED**: 8019 s (2 h 13 min), 349/349 fits,
  699 events, `runner_saw_fits: 349` (no placeholder), `selected_F2_or_V: "F2"`, staged ledger chained,
  **`test_access_count: 0`** read via the real post-selection `status_run`/`_rebuild_authority` (the
  relocation is what lets that replay succeed).

Existing fast slow tests (`test_smoke_a_e1_one_fit_end_to_end`,
`test_run_module_defers_selection_dependent_fits`, `test_run_a_e1_staged_executes_real_fits_via_scheduler`):
3 passed in 39.6 s — no regression.

## Documentation corrections (per contract)

- The prior "claim time cannot know the candidate" framing is corrected to: the candidate IS determined by the
  frozen matrix (known at claim time), but point evidence is a post-selection lifecycle artifact and cannot be a
  pre-training-success output — hence relocate, not relax (design doc §2 updated).
- The direct `scheduler_state.json` read is no longer called a complete sealed-status verification: the 349-smoke
  final check now calls the real `status_run`/`_rebuild_authority` (the workaround code + comment are removed).
- `00-A-执行状态.md`, `03-A-实验计划.md`, and the relay handoff updated to the real final tip (`4d5c9cd`) and
  the resolved-blocker state.

## Boundary held

No `formal_scheduler.py` output-dir validation change; no frozen matrix / plan schema / `_PLAN_FIELDS` /
selection rule / artifact-trace-receipt-bundle version / scientific metric change; no production
`score_fit(fit_id, plan_row)` contract change; no `fit_kind`/`n` written back into the plan; no test read
(`test_access_count == 0` throughout, including the focused real-scheduler post-selection check); no real formal
A-E1 launch; no oracle approval; no `formal-accredit-authorize`; no A-E3/A-E2 / test unseal / real formal / 9d /
G4. point_evidence relocated, scheduler untouched.

## Status & next

- **point_evidence vs scheduler output-dir validation — RESOLVED (option a relocate, `4d5c9cd`, awaiting Codex
  re-review).** Relocated to `selection/point_evidence/{fit_id}.json`; scheduler authority model unchanged;
  `accredit_build` derives the selection set from the frozen matrix, recovers n from `n_mode`/`fixed_n`, and
  never silently skips a failed fit. Post-selection `_rebuild_authority`/`status_run` pass on a real scheduler
  (focused slow test, 17 s); 356 non-slow tests pass.
- **349-fit smoke** — restored to the real final check; **PASSED** (8019 s / 2 h 13 min: 349/349 fits, 699
  events, no placeholder reached the runner, stage1/stage2/final receipts + chained ledger, `selected_F2_or_V:
  "F2"`, `test_access_count: 0` read via the real post-selection `status_run`/`_rebuild_authority`).
- **staged source-of-truth** — FIXED (prior棒 `10d6fcf`).
- **A-E1 formal — NOT authorized.**

— Claude (executor), 2026-07-20
