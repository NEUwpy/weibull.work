Role: executor
Plan: `coworker/plans/2026-06-26-help-specs-as-data.md`
Report: `coworker/reports/2026-06-26-help-chart-table-spec-source-mini-hermes.md`

Follow coworker. First run `git status --short --branch`.

Microtask only:
Add `src/app/help/charts/charts-spec.ts` as a pure typed data source for chart/table display specs.

It should define:
- chart display paradigms
- table display paradigms
- visual/color semantics
- development norms
- how the spec relates to `chart-registry.ts`

Do not edit `page.tsx`, docs, algorithms, experiments, training, data, or business pages.
Run `git diff --check` if possible.
Write the report file. Terminal reply should be only the report path.
