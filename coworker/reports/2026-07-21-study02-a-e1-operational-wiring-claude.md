# Study02 A-E1 — operational wiring executor report

Branch: `codex/study02-a-preflight-20260721`. Baseline: main `c50ad0c1`.

## Goal

Wire `formal-execute --module A-E1` to `run_a_e1_staged()` (the 349-fit staged orchestrator proven in sealed synthetic smoke). A-E3/A-E2 stay on `run_module()`. Add consecutive failure guard matching existing executor.

## Changes

### 1. `run_study02a.py` — CLI dispatch

`formal-execute --module A-E1` now dispatches to `run_a_e1_staged()`. A-E3/A-E2 continue to `run_formal_module()`. All CLI args (`run-id`, `artifact-root`, `cache-root`, `owner-id`, `max-fits`) pass through unchanged.

### 2. `formal_executor.py` — consecutive failure guard

`run_a_e1_staged()` now has `_MAX_CONSECUTIVE_FAILURES = 8` guard, identical to `run_module()`. Eight consecutive scientific failures trigger `RuntimeError` abort. Reset on each success.

### 3. `test_study02a_cli.py` — dispatch tests

- `test_formal_execute_dispatches_a_e1_to_run_a_e1_staged`: monkeypatches both runners, asserts `run_a_e1_staged` called (not `run_formal_module`)
- `test_formal_execute_dispatches_a_e3_a_e2_to_run_module`: asserts `run_formal_module` called for both A-E3 and A-E2 (not `run_a_e1_staged`)

### 4. Status docs

`00-A-执行状态.md` and `03-A-实验计划.md` synced: main reference, merge commit `6c955b6e`, all APPROVE, wiring awaiting review.

## Verification

```
$ python -m compileall -q code/ python/                # exit 0
$ verify_frozen_hashes(STUDY_ROOT)                      # OK
$ python -m pytest python/tests/ -q -m "not slow" -k "study02a"
364 passed, 248 deselected                             # +2 CLI dispatch tests vs prior 362
$ git status --short                                    # clean (committed)
```

## Boundary held

- Frozen matrix/plan/schema/selection rule/scheduler/scientific metrics: UNCHANGED
- Test: sealed (no test read, no test unseal)
- A-E3/A-E2 unchanged (still `run_module()`)
- No 2h13min smoke re-run (no staged/selection logic change)
- No formal A-E1 launch
- No A-E3/A-E2, accredit-authorize, test unseal, 9d, G4

## Next

Await Codex review of operational wiring (`7fff842c`). A-E1 formal NOT authorized.

— Claude (executor), 2026-07-21
