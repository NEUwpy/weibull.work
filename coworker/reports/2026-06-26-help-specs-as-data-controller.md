# Controller Report — help-specs-as-data

Executor status: Hermes attempted, then Codex controller stabilized Checkpoint A.

## Checkpoint A — Metrics

Changed files:

| File | Change |
|------|--------|
| `src/app/help/metrics/metrics-spec.ts` | Added structured metric/formula source with metric IDs, formulas, variable definitions, categories, perspectives, implementation references, perspective definitions, status definitions, deprecated metrics, and dev norms. |
| `src/app/help/metrics/page.tsx` | Converted metrics page into a thin renderer over `metrics-spec.ts`; renders metric variables, category, perspectives, and implementation references. |
| `src/lib/metrics.ts` | Updated maintenance comment to point to `metrics-spec.ts` as the readable spec source and `/help/metrics` as the rendered view. |
| `python/studies/common/metrics.py` | Updated maintenance comment with the same source/view split. |

## Hermes Control Notes

- A short Hermes sanity probe succeeded: `hermes --skills coworker -z "Reply exactly OK"` returned `OK`.
- The longer metrics checkpoint dispatch timed out after 4 minutes.
- The hung Hermes command left no report and left a partial TypeScript edit: `PerspectiveDef.variables` was required but `PERSPECTIVES` entries did not define it.
- Codex stopped only the hung checkpoint process chain, not the long-running Hermes gateway process.
- Recent Hermes logs show repeated MiMo streaming failures: `peer closed connection without sending complete message body (incomplete chunked read)` followed by `response.content invalid (not a non-empty list)`.

## Checks

| Check | Result |
|-------|--------|
| `git diff --check` | Pass; line-ending warnings only for touched files. |
| `npx tsc --noEmit` | Pass. |

## Deviations

- This is not the full second-stage report. Charts/table specs, README/02/06/07/08 doc口径同步, and changelog cleanup are not yet complete.
- Because Hermes/MiMo is unstable on larger streaming turns, further delegation should use isolated micro-checkpoints or be completed locally by Codex.

## Next Slice Recommendation

Do not reuse the same long Hermes session. If Hermes is used again, assign only one narrow task at a time, for example:

1. chart/table spec source only, no docs sync;
2. `/help/charts` renderer only;
3. README/02/06/07/08 wording sync only;
4. final report/checks only.

---

## Final Controller Update — Completed by Codex

Status: completed locally by Codex after two Hermes micro-dispatch attempts timed out.

### Hermes Attempts

| Attempt | Handoff | Result |
|---------|---------|--------|
| 1 | `coworker/handoffs/2026-06-26-help-chart-table-spec-source-hermes.md` | Timed out after 300s; no report file; no chart diff. |
| 2 | `coworker/handoffs/2026-06-26-help-chart-table-spec-source-mini-hermes.md` | Timed out after 240s; no report file; no chart diff. |

Codex stopped only the timed-out `hermes --skills coworker -z ...` execution chains. The Hermes gateway `gateway run` processes were left running.

### Completed Changes

| File | Change |
|------|--------|
| `src/app/help/charts/charts-spec.ts` | Added structured chart/table display spec source: chart paradigms, table paradigms, usage map, visual semantics, development norms, and registry relationship. |
| `src/app/help/charts/page.tsx` | Converted chart groups, table patterns, usage map, color semantics, and dev norms to render from `charts-spec.ts`; preserved `chart-registry.ts` instance expansion behavior. |
| `src/app/help/charts/chart-registry.ts` | Added responsibility comment: registry owns real instances, data sources, and props; `charts-spec.ts` owns display rules. |
| `README.md` | Clarified `/help/metrics` and `/help/charts` as rendered views; routed metric/chart changes to `metrics-spec.ts`, `charts-spec.ts`, `chart-registry.ts`, and shared implementations. |
| `02-规则.md` | Updated development rules and sync matrix to distinguish spec source, registry, and Help rendered views. |
| `04-目标与待办.md` | Reworded completed Help items from "embedded in page" to "migrated to structured spec source". |
| `06-模块.md` | Preserved module-definition authority while marking §6.3/§6.4 as design references and pointing current spec truth to structured sources. |
| `07-用户手册.md` | Updated user-facing authority note to spec/registry/rendered-view split. |
| `08-更新日志.md` | Removed v1.71 contradiction that described `06-模块.md` as Help's authoritative data source; added Help spec-as-data completion note. |

### Source/View Relationship

| Area | Structured/readable source | Executable/instance source | Help page role |
|------|----------------------------|----------------------------|----------------|
| Metrics/formulas | `src/app/help/metrics/metrics-spec.ts` | `src/lib/metrics.ts`, `python/studies/common/metrics.py` | `/help/metrics` renders only. |
| Charts/tables | `src/app/help/charts/charts-spec.ts` | `src/app/help/charts/chart-registry.ts` + chart components | `/help/charts` renders specs and expandable real instances. |

### Consistency Notes

- No metric/formula inconsistency was newly found in this final slice.
- Chart/table spec is descriptive and did not require business-page migration.
- Existing `/help/charts` instance expansion still reads `chartRegistry[name]` and uses `InstanceCard`/`InstanceChart` as before.

### Verification

| Check | Result |
|-------|--------|
| `git diff --check` | Pass; line-ending warnings only. |
| `npx tsc --noEmit` | Pass. |
| `npm run build` | Pass; Next.js build completed. Browserslist/caniuse-lite outdated warning only. |
| Production HTTP smoke check | Pass: `http://127.0.0.1:3000/help/charts` returned 200, `http://127.0.0.1:3000/help/metrics` returned 200 after `next start`. |
| `rg -n "CORE_METRICS|const chartGroups|新增图表 → 必须先更新本页面|图表类型、用途、配色规范已嵌入规范页|06-模块.*权威数据源" src/app/help README.md 02-规则.md 04-目标与待办.md 06-模块.md 07-用户手册.md 08-更新日志.md` | No matches; command exited 1 as expected for no results. |

### Deviations

- Hermes/MiMo could not complete even the mini chart/table spec source task, so Codex implemented and verified the remaining stage locally.
- Two Hermes handoff files remain as coordination evidence because they explain the attempted dispatch boundaries.
- A first `npm run dev` smoke-check attempt listened on port 3000 but did not return HTTP responses, so Codex stopped that local dev chain, rebuilt, and verified with `next start` instead.

### Open Questions

- None blocking for this stage.
