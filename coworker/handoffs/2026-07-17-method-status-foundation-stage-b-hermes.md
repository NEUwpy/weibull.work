# Executor Handoff

Role: executor

Plan: `coworker/plans/2026-07-17-method-status-foundation.md`

Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

Master roadmap: `coworker/plans/2026-07-17-method-construction-master-roadmap.md`

Report: `coworker/reports/2026-07-17-method-status-foundation-stage-b-hermes.md`

Stage A report (approved baseline): `coworker/reports/2026-07-17-method-status-foundation-stage-a-hermes.md`
Stage A review records: `coworker/reviews/2026-07-17-method-status-foundation-stage-a-codex.md` (REVISE), `coworker/reviews/2026-07-17-method-status-foundation-stage-a-codex-r2.md` (APPROVE)

## Task

Execute only **Stage B / Tasks 4–6** of the plan: add typed TypeScript accessors, render the dashboard from generated status, gate the calculator by first-layer completion, honor `?method=` URL selection, and expose truthful incomplete states in method detail pages.

Stop after Stage B. Do not begin Stage C (WMLE fallback removal, backend identity validation, authority doc sync). Codex must review Stage B before a new handoff authorizes Stage C.

## Current State (Stage A Output)

- `src/data/method-status.generated.json` exists with 22 methods.
- Only MDM is `calculatorEnabled: true` (layer1 complete).
- MLE at `layer1_in_progress`（missing paper）。
- MMLE at `layer1_in_progress`（missing paper, tests）。
- WMLE at `layer1_in_progress`（missing tests）。
- LRE at `layer1_in_progress`（missing paper, calculator, theory, process）。
- 17 methods at `not_started`.
- `src/lib/method-status.ts` does NOT exist yet.

## Required Reading

1. `README.md`
2. `02-规则.md`
3. `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`
4. `coworker/plans/2026-07-17-method-status-foundation.md` (Stage B / Tasks 4–6)
5. `05-状态.md`
6. `coworker/reports/2026-07-17-method-status-foundation-stage-a-hermes.md`
7. `src/data/method-status.generated.json`

Also read before modifying:
- `src/app/help/changelog/page.tsx` — current dashboard with hardcoded `METHOD_STATUS`
- `src/components/calculator/MethodSelector.tsx` — uses `method.hasDetail` as calculator gate
- `src/app/page.tsx` — initial method selection and URL handling
- `src/app/methods/[methodId]/page.tsx` — detail page tab rendering and apply link

Follow the `coworker` protocol. Use implementation autonomy inside the plan boundaries and execute tasks in order with tests before implementation where specified.

## Hard Boundaries

- Do not implement missing algorithms.
- Do not redesign the method overview page layout.
- Do not redesign the calculator selector layout, labels or animation.
- Do not add construction badges to `/methods` overview.
- Do not preserve calculator availability with a `hasDetail` legacy override.
- Do not remove legacy `hasDetail` property from `methods.json` or type definitions (it may still serve content-lookup in unmodified codepaths).
- Do not touch `Study/01`, `Study/02`, `docs/history/`, `_archive/` or credentials.
- Do not push, merge or deploy.

## Task Summary

### Task 4: Typed accessors + dashboard migration

Create `src/lib/method-status.ts` with `MethodCapability`, `AtomicStatus`, `MethodLevel` types and `getMethodCapability()`, `isCalculatorEnabled()`, `getEnabledMethodIds()`, `getMethodCapabilities()`. Module must only read the generated JSON.

Replace `METHOD_STATUS` constant and local method-status interface in `src/app/help/changelog/page.tsx`. Render all 22 methods from `getMethodCapabilities()` with the existing table visual language plus derived level and first-layer readiness.

Verify: `check:method-status` + `npx tsc --noEmit` pass; `METHOD_STATUS` constant fully removed.

### Task 5: Calculator gate + `?method=` selection

In `src/components/calculator/MethodSelector.tsx`, replace every `method.hasDetail` readiness check with `isCalculatorEnabled(method.id)`. Keep `hasDetail` intact on the type for legacy content-lookup (do not remove from `methods.json` or interfaces).

In `src/app/page.tsx`: read `searchParams.get('method')`, accept only if `isCalculatorEnabled`, fall back to `getEnabledMethodIds()[0]`, handle no-enabled case without defaulting to MLE. When an enabled requested method exists, calculate through `calculateWeibull()` instead of reusing the local MLE result under another method ID. Preserve `caseId` behavior.

Verify: `check:method-status` + `npx tsc --noEmit` + `git diff --check`.

### Task 6: Method detail status

Create `src/components/methods/MethodBuildStatus.tsx` — shared panel accepting `label`, `status`, `reason?`, `evidence?`. Render:
- `todo` → "未开始"
- `in_progress` → "进行中"
- `blocked` → "受阻" with `reason`
- `done` → (not rendered; tab body shows real content instead)
- `not_applicable` → "不适用" with `reason` when `exception_approved: true`, else treated as blocked

In `src/app/methods/[methodId]/page.tsx`: keep all tabs visible. Before rendering each tab body, read its atomic status from `getMethodCapability()`. If status is not `done`, render `MethodBuildStatus` instead of empty viewer. Gate the apply link: retain for first-layer complete methods, otherwise render disabled "开发中" in the same visual position.

Verify: `npx tsc --noEmit` + `git diff --check`.

## Verification Gates

After each task:

```powershell
npm run check:method-status
npx tsc --noEmit
git diff --check
```

After Task 5, also manually verify `?method=mdm` works and `?method=mps` is blocked.

## Paper Stop Rule

PAPER_NEEDED items from Stage A remain blocked. Do not alter paper status.

## Report Back

Write the Stage B report at the path above. Include:

- start and end commits
- changed files grouped by task
- exact TypeScript compilation and method-status check results
- which methods are calculator-enabled after Tasks 4–5
- which tabs render `MethodBuildStatus` per method
- remaining `hasDetail` references and their purpose
- skipped checks, blockers and deviations

Do not mark Stage B complete in project docs until Codex returns `APPROVE`.
