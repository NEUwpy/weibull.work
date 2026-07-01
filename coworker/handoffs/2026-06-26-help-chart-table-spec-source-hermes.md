Role: executor
Plan: `coworker/plans/2026-06-26-help-specs-as-data.md`
Controller report: `coworker/reports/2026-06-26-help-specs-as-data-controller.md`
Report: `coworker/reports/2026-06-26-help-chart-table-spec-source-hermes.md`

Follow the coworker protocol. Start with `git status --short --branch`, then read `README.md`, the plan, and the controller report.

Micro-scope: chart/table spec source only.

Goal:
Create a small typed chart/table display-spec source for `/help/charts`, so the next slice can render from it instead of keeping chart/table rules inside `page.tsx`.

Allowed edits:
- Add a pure data/type module under `src/app/help/charts/`, preferably `charts-spec.ts`.
- Cover chart paradigms, table paradigms, visual/color semantics, development norms, component keys, and registry relationship.
- Optionally add a short responsibility comment in `chart-registry.ts`.

Do not:
- Do not rewrite `/help/charts/page.tsx` in this slice.
- Do not edit README/02/06/07/08 docs.
- Do not modify algorithms, experiments, training, data generation, or business pages.
- Do not remove existing `chartRegistry` instances.

Stop and report if this requires broad business-page migration or runtime behavior changes.

Verification:
Run `git diff --check`.
Run `npx tsc --noEmit` if the TypeScript edit makes that reasonable.

Final terminal reply: only the report path.
