# Execution Report — docs-as-context-router

**Executor**: Hermes
**Plan**: `coworker/plans/2026-06-26-docs-as-context-router.md`
**Date**: 2026-06-26

---

## Changed Files

| File | Change Summary |
|------|---------------|
| `README.md` | Full rewrite as context router: added「当前状态快照」(method table + AI module table + architecture diagram),「文档权威模型」(Ground Truth hierarchy, document role table, docs-as-data/Help rendering table, document sync matrix). Reading path table simplified. AI conventions section preserved. |
| `02-规则.md` | Added §11「文档更新契约」: change-type → must-sync-authoritative-source mapping table + principle statement |
| `04-目标与待办.md` | M1/M3「已完成」sections annotated with ⚠ "旧原型完成记录，不作为当前正式结论"; fixed "25+" → "22 种"; updated timestamp to 2026-06-26 |
| `05-状态.md` | Demoted to progress tracker: header reworded to declare README as current-state authority; AI methods footnote updated to match README snapshot (M1=旧原型/待重构, M3=原型, M2/M4=待开发) |
| `06-模块.md` | Added authority declaration in header (§6.3/§6.4 as authoritative data source for Help规范页) |
| `07-用户手册.md` | Added reference note pointing to 06-模块.md as authoritative module definition source |
| `08-更新日志.md` | Added v1.71-260626 entry documenting all above changes |

---

## New Document Authority Model

```
README.md  ←  唯一入口 + 当前状态快照（唯一当前态权威源）
  │
  ├── 02-规则.md         ← 开发规范 + 文档更新契约
  ├── 06-模块.md         ← 模块定义权威源 + 指标/图表权威数据
  ├── 04-目标与待办.md   ← 长期目标/路线权威源（Help/todos 渲染源）
  ├── 05-状态.md         ← 开发进度追踪器（不再是当前状态权威源）
  ├── 07-用户手册.md     ← 终端用户文档（引用 06-模块.md 为权威）
  ├── 08-更新日志.md     ← 版本日志（只记事实，不做当前状态判断）
  └── 06-A-架构决策.md   ← 架构决策记录

Ground Truth 层级：源文件 > wiki 副本 > agent 记忆
```

Help 渲染视图（本阶段不改 React 代码）：
- `/help/changelog` → reads `08-更新日志.md`
- `/help/changelog/todos` → reads `04-目标与待办.md`
- `/help/manual` → reads `07-用户手册.md`

---

## Checks Run

| Check | Result |
|-------|--------|
| `git diff --check` | CRLF/LF warnings only (patch tool line-ending normalization), no errors |
| `rg "25\+\|已实现，含 R1\|关系建立原型已完成\|S2R 评价指标体系成为当前唯一\|docs/oldrules\|AI协作协议.md"` on target files | Matches only in `08-更新日志.md` historical entries (recording past events, not current-state claims) and README `docs/oldrules/` as historical-reference mention. No stale current-state claims remain. |

## Manual Verification

- [x] README explains current state, entry point, authority order, and task-based reading paths in < 2 min read
- [x] `04-目标与待办.md` M1/M3 completion sections annotated as old prototype records, not current conclusions
- [x] `05-状态.md` no longer conflicts with README/06/路线图 (explicitly demoted)
- [x] No new hardcoded second-source-of-truth created
- [x] Document sync matrix covers all change types → authoritative sources

## Skipped Checks

- `npx tsc --noEmit`: No code changes, only documentation
- `python -m pytest`: No code changes
- `08-更新日志.md` full content re-read: Changelog append-only operation, no existing content was overwritten

## Deviations

None. All changes within plan boundaries.

## Open Questions

None blocking. Future consideration: the `/help/metrics` and `/help/charts` pages currently have hardcoded content that should eventually be rendered from `06-模块.md` §6.3/§6.4 — this is the next phase (React Help page read-from-authoritative-source), explicitly out of scope for this plan.

---

## Revision — Codex REVISE Correction (2026-06-26)

**Codex review**: `coworker/reviews/2026-06-26-docs-as-context-router-codex-review.md`
**Verdict**: REVISE (3 findings: 2× P2, 1× P3)

### Finding 1 (P2) — Metrics/charts authority assigned to wrong source

**Problem**: README, 02-规则.md, 06-模块.md, 07-用户手册.md all claimed `06-模块.md §6.3/§6.4` is the authoritative source for metrics/charts. Current code says the opposite: `/help/metrics` readable spec + `src/lib/metrics.ts` + `python/studies/common/metrics.py` are the executable metrics spec; `/help/charts` readable spec + `chart-registry.ts` + chart components are the executable charts spec.

**Changed files**:

| File | Change |
|------|--------|
| `README.md` L86 | `/help/metrics`/`/help/charts` authority → code, 06-模块.md → design ref |
| `README.md` L94-95 | Sync matrix: metrics → `src/lib/metrics.ts` + `metrics.py` + `/help/metrics`; charts → `chart-registry.ts` + components + `/help/charts` |
| `README.md` L151-152 | Reading path: authority source → code files |
| `02-规则.md` L300-301 | §11 sync matrix: same correction as README |
| `06-模块.md` L5 | Header authority note: §6.3/§6.4 → design ref, code = executable spec |
| `06-模块.md` L239 | §6.3 purpose: "single source of truth" → "design ref, code is spec" |
| `06-模块.md` L248 | §6.3 rules: "update this doc" → "update /help/metrics + shared functions" |
| `06-模块.md` L274 | §6.4 purpose: same pattern |
| `06-模块.md` L283 | §6.4 rules: "update this doc" → "update /help/charts + registry" |
| `07-用户手册.md` L3 | Authority reference: 06-模块.md §6.3/§6.4 → code |

### Finding 2 (P2) — 04-目标与待办.md stale unchecked items

**Problem**: Items that already exist (`/help/metrics`, `/help/charts`, `metrics.py`, `metrics.ts`) were listed as unchecked `- [ ]`, making them appear as current todos in `/help/changelog/todos`.

**Changed files**:

| File | Change |
|------|--------|
| `04-目标与待办.md` L37-39 | 指标规范: 4 unchecked → 3 completed `[x]` (page exists, defs embedded, authority migrated to code) |
| `04-目标与待办.md` L43-46 | 图表规范: 4 unchecked → 2 completed + 1 remaining (component unification still open) |
| `04-目标与待办.md` L49 | 后端 metrics.py: `- [ ]` → `- [x]` (file exists) |
| `04-目标与待办.md` L57 | 前端 metrics.ts: `- [ ]` → `- [x]` (file exists) |
| Dedup sub-items (L50-54, L58-60) | Kept as `- [ ]` — not verified complete |

### Finding 3 (P3) — 05-状态.md AI table misleading

**Problem**: AI methods table showed ✅ for M1 (relationship) as "formally complete" when it's actually an old prototype needing rebuild. M3 (direct-estimation) showed all ⬜ when prototype pages actually exist.

**Changed files**:

| File | Change |
|------|--------|
| `05-状态.md` L57-59 | Legend: added note that AI methods ✅ = "prototype page exists", not "formal module complete" |
| `05-状态.md` L49 | M3 直接估计 row: 7×⬜ → ✅✅✅⬜✅✅⬜ (theory, algo, data, —, perf, verify, —) |

### Verification

| Check | Result |
|-------|--------|
| `git diff --check` | CRLF/LF warnings only, no errors |
| Grep stale authority claims (`06-模块.*权威数据源`, `唯一定义源`, `single source of truth`) | No matches in target files |
| Grep stale unchecked items (`新建.*metrics.py`, `新建.*metrics.ts`) | No matches in 04-目标与待办.md |

### Deviations from Codex review

None. All three findings addressed as specified. README context-router shape preserved. No unrelated sections rewritten. No React Help page changes.
