# Codex Final Review — docs-as-context-router

Verdict: REVISE

## Findings

1. P2 — Metrics/charts authority is assigned to the wrong source.

   Evidence:
   - `README.md` says `/help/metrics` and `/help/charts` are views whose authoritative definitions live in `06-模块.md` §6.3/§6.4.
   - `02-规则.md` repeats that metric/chart changes must sync `06-模块.md` §6.3/§6.4.
   - `06-模块.md` §6.3 still lists old AI-oriented metrics such as MSE, MRE, `total_relative_mse`, improvement rate, and old module usage columns.
   - Current code states the opposite: `src/app/help/metrics/page.tsx` is the readable metrics spec, and `src/lib/metrics.ts` / `python/studies/common/metrics.py` are executable implementations. `/help/charts` uses `chart-registry.ts`.

   Required revision:
   - Do not claim `06-模块.md` §6.3/§6.4 are the current authoritative metrics/charts source.
   - For this phase, describe the current truth accurately:
     - Metrics authority: `/help/metrics` readable spec + `src/lib/metrics.ts` + `python/studies/common/metrics.py`.
     - Charts authority: `/help/charts` readable spec + `src/app/help/charts/chart-registry.ts` + chart components.
   - If desired, mark extracting these into Markdown/registry-backed docs as a future phase, not current fact.
   - Update `README.md`, `02-规则.md`, `06-模块.md`, and `07-用户手册.md` consistently.

2. P2 — `04-目标与待办.md` is still stale as the Help todos source.

   Evidence:
   - It now has a 2026-06-26 timestamp, but still lists already-existing work as unchecked: creating `/help/metrics`, creating `/help/charts`, creating `python/studies/common/metrics.py`, creating `src/lib/metrics.ts`.
   - Since `/help/changelog/todos` reads this Markdown, these stale unchecked items become public/current route information.

   Required revision:
   - Make `04-目标与待办.md` truthful as a current long-term goals/todos source.
   - Either mark completed items as completed with concise current wording, or rewrite the section into current next work: docs-as-data extraction, Help read-from-source phase, AI old-prototype migration, method completion, literature/case growth.
   - Keep it compact. Do not expand into a long historical changelog.

3. P3 — `05-状态.md` is demoted but still looks like stale current progress.

   Evidence:
   - Header says it is only a progress tracker, but the table still marks direct-estimation all blank while README/06 call M3 an existing prototype.
   - The AI row for relationship is all mostly complete while the current status is old-prototype/to-rebuild.

   Required revision:
   - Either align the table with the current prototype/development-tracker meaning, or add clear table-level labels that `✅` means "prototype page exists" rather than "current formal module complete."
   - It must not invite readers to infer current formal readiness from the table.

## Checks Already Run

- `git diff --check`: only line-ending warnings, no whitespace errors.
- Stale-text grep: remaining matches are mostly historical log entries, but the deeper source-authority conflict above remains.

## Reviewer Notes

The README direction is good: it is much closer to a context router. Keep that shape. The revision should correct the authority model and stale todo source rather than rewriting everything again.
