# Executor Handoff

Role: executor

Plan: `coworker/plans/2026-07-17-method-status-foundation.md` (Stage C / Tasks 7–8)

Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

Master roadmap: `coworker/plans/2026-07-17-method-construction-master-roadmap.md`

Report: `coworker/reports/2026-07-17-method-status-foundation-stage-c-hermes.md`

Approved Stage B inputs:

- report: `coworker/reports/2026-07-17-method-status-foundation-stage-b-hermes.md`
- review: `coworker/reviews/2026-07-17-method-status-foundation-stage-b-codex.md` (`REVISE`)
- re-review: `coworker/reviews/2026-07-17-method-status-foundation-stage-b-codex-r2.md` (`APPROVE`)

## Goal

Complete Phase 0 by removing silent method substitution, validating calculation identity end to end, synchronizing authority documents, and running the final verification suite.

Execute only **Stage C / Tasks 7–8**. Stop after the Stage C report and wait for Codex. Do not enter Phase 1 or begin method-by-method construction.

## Current Facts

- Approved implementation baseline is `409b925`; record the actual dispatch/start commit in the report.
- `05-状态.md` remains the only editable method-status source; generated JSON covers 22 methods.
- Only MDM is calculator-enabled.
- `python/main.py::_run_calculation_method()` still silently falls back to WMLE.
- `src/hooks/useWeibullCalculation.ts` does not yet reject a response whose method differs from the requested method.
- The active Python environment lacks `torch`, and `python/requirements.txt` does not declare it although `python/main.py` imports it at module scope. This is a pre-existing AI/dependency issue, not Stage C scope.

## Required Reading

Read `README.md`, `02-规则.md`, the plan's Stage C section, this handoff, the approved Stage B report/re-review, and the current implementations/tests directly involved in Tasks 7–8.

Follow the `coworker` protocol and use implementation autonomy within this contract.

## Allowed Work

### Task 7 — Method identity safety

- Add `python/tests/test_calculation_api.py`.
- Change `python/main.py` so a failed requested method is called once and returns a clear HTTP 422 error; never call or label WMLE as fallback.
- Change `src/hooks/useWeibullCalculation.ts` so the backend response method must equal the requested method after normalization; return the validated method identity.
- Cover failure, success identity, call count, requested ID in the error, and absence of WMLE substitution.

### Task 8 — Authority synchronization

- Update `README.md` to route detailed method construction status to `05-状态.md` and remove/correct the stale manually maintained backend-count claim without introducing another synchronized count.
- Update `02-规则.md` to define `05-状态.md` as the sole editable method-capability source and generated JSON as derived data.
- Update `06-模块.md` with first-layer calculator gating and shared-core/independent-variant rules.
- Update `08-更新日志.md` only after implementation checks pass.
- Keep detailed per-method status out of these documents; it belongs in `05-状态.md`.

## Hard Boundaries

- Do not implement, repair, or validate estimation algorithms beyond the identity-safety change.
- Do not alter method statuses, paper statuses, calculator availability, generated status data, or the existing UI design.
- Do not add/install `torch`, modify `python/requirements.txt`, or refactor AI routes/import architecture under this stage. A test-local isolation of the optional AI import is allowed if needed to test the calculation helper. If focused tests cannot run without production dependency/AI changes, stop and report the blocker.
- Do not touch `Study/01`, `Study/02`, `docs/history/`, `_archive/`, credentials, deployment, or unrelated files.
- Do not push, merge, deploy, or enter Phase 1.

## Verification Gates

Task 7 focused checks:

```powershell
python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
npx tsc --noEmit
```

Final Stage C checks:

```powershell
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
python -m pytest python/tests -q
npm run build
git diff --check
```

Text audit:

```powershell
rg -n "const METHOD_STATUS|activeMethod\?\.hasDetail|Fallback to WMLE|fallback_wmle" src python
```

Expected: no status hardcode, calculator `hasDetail` gate, or WMLE fallback remains. List any remaining `hasDetail` references and prove they are legacy content lookup only.

Confirm the committed scope excludes all forbidden paths. Any skipped check needs the exact environmental reason and compensating evidence; do not report success from partial output.

## Paper Stop Rule

Do not change the existing MLE, MMLE, or LRE `PAPER_NEEDED` records. Stage C needs no new paper. If a new paper dependency unexpectedly appears, report it and continue only with work independent of that paper.

## Report and Stop

Write the Stage C report at the path above with:

- start/end commits and changed files grouped by task;
- exact verification output, failures, retries, and environment accommodations;
- proof that failed requests never call WMLE and successful responses preserve method identity;
- authority-document changes and confirmation that detailed status was not duplicated;
- current calculator-enabled methods, remaining `hasDetail` references, paper blockers, deviations, and skipped checks.

Commit the scoped Task 7 work, scoped Task 8 work, and report separately. Then stop. Stage C and Phase 0 are complete only after Codex returns `APPROVE`.
