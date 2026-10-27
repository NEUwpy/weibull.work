# Executor Handoff

Role: executor

Plan: `coworker/plans/2026-07-17-method-status-foundation.md`

Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

Master roadmap: `coworker/plans/2026-07-17-method-construction-master-roadmap.md`

Report: `coworker/reports/2026-07-17-method-status-foundation-stage-a-hermes.md`

## Task

Execute only **Stage A / Tasks 1–3** of the plan: add parser tests, implement the validator/generator, migrate `05-状态.md` conservatively, and produce the generated cache.

Stop after Stage A. Do not begin the dashboard, calculator, detail-page or backend tasks in this run. Codex must review Stage A before a new handoff authorizes Stage B.

## Required Reading

1. `README.md`
2. `02-规则.md`
3. `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`
4. `coworker/plans/2026-07-17-method-status-foundation.md`
5. `05-状态.md`

Follow the `coworker` protocol. Use implementation autonomy inside the plan boundaries and execute tasks in order with tests before implementation where specified.

## Hard Boundaries

- Do not implement missing algorithms in this phase.
- Do not redesign the method overview or calculator.
- Do not preserve calculator availability with a legacy override.
- Do not mark papers complete from 181-004 alone.
- Do not touch `Study/01`, `Study/02`, `docs/history/`, `_archive/` or credentials.
- Do not push, merge or deploy.

## Paper Stop Rule

If a method needs a dedicated paper, record `PAPER_NEEDED` in the report and keep that paper status blocked. Continue independent infrastructure work; do not substitute a review, blog or 181-004.

## Report Back

Write the Stage A report at the path above. Include changed files, start/end commits, exact parser/generator verification results, status counts, derived calculator-enabled methods, conservative downgrades, paper requests, skipped checks, blockers and deviations.
