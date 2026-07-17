# Codex Final Audit Contract

VERDICT: APPROVE | REVISE | BLOCK

## Inputs

- Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`
- Master roadmap: `coworker/plans/2026-07-17-method-construction-master-roadmap.md`
- Plan: `coworker/plans/2026-07-17-method-status-foundation.md`
- Handoff: `coworker/handoffs/2026-07-17-method-status-foundation-hermes.md`
- Stage A report: `coworker/reports/2026-07-17-method-status-foundation-stage-a-hermes.md`
- Stage B report: `coworker/reports/2026-07-17-method-status-foundation-stage-b-hermes.md`
- Stage C report: `coworker/reports/2026-07-17-method-status-foundation-stage-c-hermes.md`

## Scope Gate

- Only approved Phase 0 files changed.
- No `Study/01`, `Study/02`, history, archive, credential, deployment or unrelated changes were included.
- Method overview and calculator visuals were not redesigned.
- No missing estimation algorithm was implemented opportunistically.

Any hard scope violation is `BLOCK` unless the offending changes are removed and the evidence rerun.

## Single-Source Gate

- `05-状态.md` YAML is the only editable method-status source.
- Generated JSON is deterministic, source-labelled and checkable for staleness.
- `src/app/help/changelog/page.tsx` has no hand-maintained method status array.
- Calculator readiness no longer depends on `hasDetail`.
- All 22 leaf IDs are covered exactly once.
- Overall maturity and calculator availability are derived, not manually entered.

## Evidence Gate

- Every `done` item points to an existing, relevant file or directory.
- Completed papers have title, publication, year, stable identifier and local evidence.
- 181-004 is not accepted as the only dedicated paper.
- Registered `NotImplementedError` stubs are not marked backend-complete.
- Alias-only variants are not marked independently implemented.
- Missing papers appear as `PAPER_NEEDED`, not as completion claims.

Unsupported completion claims are `REVISE`; systematic or deliberate overstatement is `BLOCK`.

## Calculator and Detail Gate

- Only first-layer-complete methods are selectable.
- Incomplete methods retain the existing grey “开发中” treatment.
- `/?method=mdm` selects and calculates MDM when MDM is enabled by the generated status.
- An incomplete URL method cannot bypass the gate.
- All detail tabs remain visible; incomplete tabs show truthful state instead of misleading content.
- Method overview remains visually clean and has no duplicated status board.

## No-Substitution Gate

- Backend failure calls only the requested method and returns explicit failure.
- Frontend validates returned method identity.
- No `Fallback to WMLE`, `_fallback_wmle` or equivalent substitution remains.

Any path that can present one method's result under another method's identity is `BLOCK`.

## Required Verification

Codex reruns or directly inspects fresh output for:

```powershell
npm run test:method-status
npm run check:method-status
npx tsc --noEmit
python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q
python -m pytest python/tests -q
npm run build
git diff --check
```

Text audit:

```powershell
rg -n "const METHOD_STATUS|activeMethod\?\.hasDetail|Fallback to WMLE|fallback_wmle" src python
```

Any skipped required check needs a concrete environmental reason and compensating evidence; otherwise return `REVISE`.

## Review Output

Write the actual review to a new file in `coworker/reviews/` rather than overwriting this contract. Include:

- final verdict;
- file-specific findings with priority;
- exact verification results;
- status/evidence discrepancies;
- paper requests;
- whether Phase 1 may begin.
