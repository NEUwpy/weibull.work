Role: executor

Plan: `coworker/plans/2026-06-26-help-specs-as-data.md`

Report: `coworker/reports/2026-06-26-help-specs-as-data-hermes.md`

Follow the `coworker` protocol. Start from `README.md`, then read the plan. Use implementation autonomy inside the plan boundaries.

The goal is not to polish Help copy. The goal is to make metrics/formulas and chart/table display rules reusable authority sources that Help pages render from, while shared code remains the executable implementation.

Hard constraints:

- Do not turn TSX pages into the source of truth.
- Do not duplicate the same formula or chart/table rule across Markdown, TSX, and registry without a clear responsibility split.
- Do not refactor algorithms, experiments, training code, or unrelated business pages.
- Preserve existing `/help/charts` instance expansion behavior unless the plan forces a narrower fallback and you report it.
- Stop and report if formulas disagree with shared implementations, or if chart/table registry cleanup requires broad business-page migration.

When finished, write the report at the path above with exact verification results and any deviations.
