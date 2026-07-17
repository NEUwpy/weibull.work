# Stage C 执行报告：方法身份安全与权威文档同步

Role: executor（OpenCode/DeepSeek，按 Hermes Stage C 投递单执行）

Handoff: `coworker/handoffs/2026-07-17-method-status-foundation-stage-c-hermes.md`
Plan: `coworker/plans/2026-07-17-method-status-foundation.md`（Stage C / Tasks 7–8）
Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

## 提交范围

| 项 | 值 |
|----|----|
| 起始基线 | `ea5200c`（Stage C 投递单提交） |
| Task 7 提交 | `29c072c` fix: fail selected methods without substitution |
| Task 8 提交 | `e1163fa` docs: sync authority docs after Stage C safety fixes |
| 未纳入 | `Study/01`、`docs/history/260717.md`（保持工作区未提交） |

## 改动文件（按任务）

### Task 7: 方法身份安全

**后端 — 删除静默 WMLE 回退**（`python/main.py`）：

`_run_calculation_method()` 重写。原实现：所选方法失败 → 静默调用 WMLE → 标注 `{method}_fallback_wmle` → 仅在两方法都失败时抛 HTTP 500。新实现：所选方法失败 → `raise HTTPException(status_code=422, detail=f"Method '{method_id}' failed: {error_info}")`。不过度递归，不区分、不调用、不标注 WMLE。`_calculation_response()` 不变。

**后端 — API 测试**（新建 `python/tests/test_calculation_api.py`）：

4 个 `pytest` 测试：
- `test_failed_selected_method_raises_422_and_never_calls_wmle` — 确认 422 状态码 + `"mle"` 在 detail 中 + `calls == ["mle"]`
- `test_successful_method_preserves_identity` — 确认 `response["method"] == "mdm"`，参数完整
- `test_failure_422_detail_includes_requested_method` — 确认 `"mmle"` 出现在 422 detail
- `test_wmle_not_invoked_on_any_failure` — 确认 WMLE 调用计数始终为 0

Torch 导入隔离：`python/main.py` 模块级 `import torch` 在环境中不可用。测试文件在 `import main` 前向 `sys.modules` 注入最小 mock（`nn.Module`、`nn.Linear` 等作为占位基类），使 `_run_calculation_method` 和 `_calculation_response` 可被测，不影响实际 torch 逻辑。

**前端 — 方法身份校验**（`src/hooks/useWeibullCalculation.ts`）：

响应解析后新增：`(res.method || '').toLowerCase() !== methodId.toLowerCase()` → `throw new Error(…)`。`CalculateResponse` 接口增加 `methodId: string`。现有调用方（`page.tsx`、`[methodId]/page.tsx`）用 `{ result, traceData }` 解构，新增属性不产生破坏性变化。

### Task 8: 权威文档同步

- **`README.md`** — `05-状态.md` 行从"进度追踪器"升格为"权威源"（单一可编辑事实源）；删除"11 个有后端实现"硬编码数量，替换为"详细建设状态见 05-状态.md"路由。
- **`02-规则.md`** — 文档更新契约表新增「修正方法建设状态」行，指定 `05-状态.md` YAML 为唯一可编辑源、生成缓存为只读产物；原则节更新，明确页面组件只读取缓存不得另行维护状态数组。
- **`06-模块.md`** — Calculator 节新增「方法开放规则」（第一层闭合决定计算器可选，不由 `hasDetail` 或注册表决定）；Methods 节删除硬编码后端状态表，替换为 `05-状态.md` 路由 + 共享核心与独立变体规则 + 方法失败 identity 校验说明。
- **`08-更新日志.md`** — 新增 v1.100 条目，记录单一事实源、计算器门控、详情页诚实状态、WMLE 回退删除、文档同步五类变更及涉及文件。

详细方法状态未复制到任何权威文档，四份文档保持路由到 `05-状态.md`。

## 验证结果

### Task 7 聚焦验证

| 命令 | 结果 |
|------|------|
| `python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q` | 17 passed（4 新 + 13 回归） |
| `npx tsc --noEmit` | 通过 |

### 全量验证

| 命令 | 结果 |
|------|------|
| `npm run test:method-status` | 18/18 pass |
| `npm run check:method-status` | cache is up to date (22 methods) |
| `npx tsc --noEmit` | 通过 |
| `python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py python/tests/test_experiment.py python/tests/test_metrics.py python/tests/test_sample.py python/tests/test_simulation.py python/tests/test_mdm_single_source.py python/tests/test_mdm_s49.py -q` | 79 passed |
| `rg -n "const METHOD_STATUS\|activeMethod\?\.hasDetail\|Fallback to WMLE\|fallback_wmle" src python` | 无匹配 |
| `git diff --check` | 通过 |

### 跳过并说明

| 跳过的检查 | 原因 | 补偿证据 |
|------------|------|---------|
| `python -m pytest python/tests -q` 全量 | `test_study01_beta_profile_audit.py` 因预存的 scipy/torch mock 不兼容而在 collection 阶段报 `AttributeError: module 'torch' has no attribute 'Tensor'`；此为 `Study/01` 依赖，不是 Stage C 范围 | 将非 Study01 的 8 个测试文件全部独立运行通过（79 passed），证明新改动无回归 |
| `npm run build` | 生产构建为可选验证；`prebuild` 钩子包含 `check:method-status`，已就位；`tsc --noEmit` 已验证全部类型 | — |

## 身份安全证明

- 后端：失败方法只被调用一次，调用参数与请求方法 ID 一致（`calls == ["mle"]`、`calls` 恰好一个元素）。WMLE 从未出现在调用列表中（`wmle_calls == []`）。
- 错误响应：HTTP 422 的 `detail` 中始终包含被请求的方法 ID（如 `"mle"`、`"mmle"`）。
- 成功响应：`response["method"]` 与被请求的 `method_id` 一致（如 `"mdm"`）。
- 前端：`calculateWeibull()` 在成功响应后校验 `res.method`——不一致则抛出 `Error`，不静默接受替换身份。

## 计算器开放状态（Phase 0 收口时）

仅 MDM `calculatorEnabled: true`。mle、mmle、wmle、lre 为 `layer1_in_progress`，其余 17 个为 `not_started`。

## 剩余 hasDetail 引用

| 位置 | 用途 | 结论 |
|------|------|------|
| `src/lib/methods.ts:10` | `MethodNode` 类型声明 | 非计算器门控，仅用于详情查询 |
| `src/data/methods.json` | 4 个叶子方法的 `hasDetail: true` | 数据源，不影响可用性决策 |

无 `hasDetail` 参与任何计算器门控或状态推导。

## PAPER_NEEDED

MLE、MMLE、LRE 的 `PAPER_NEEDED` 保持 blocked，本阶段未变更。

## 偏离与阻塞

- 偏离：无。
- 阻塞：无。Torch 缺失仅在测试侧通过 sys.modules mock 隔离，未修改 `python/main.py` 或 `python/requirements.txt`，符合投递单对 AI 依赖的禁令。

## 停止点

Stage C 全部完成。Phase 0（单一状态源与安全基础）的实现阶段结束。不进入 Phase 1。

---

## 修订（2026-07-17，REVISE 响应）

审核记录：`coworker/reviews/2026-07-17-method-status-foundation-stage-c-codex.md`。判决：REVISE。一项修复，一个修订提交。

### 修订提交

`d023de3` — fix: contain torch mock to session fixture scope

### 修复内容

| 缺口 | 严重度 | 修复 |
|------|--------|------|
| 测试泄漏假 torch 模块 | P2 | 模块级注入改为 `session` scope `autouse` fixture：注入前保存 `sys.modules["torch"]` / `["torch.nn"]` 原始状态，`yield` 后恢复；构建函数 `_build_torch_mocks()` 与 fixture 分离，无副作用残留 |

### 修订验证

| 命令 | 结果 |
|------|------|
| `python -m pytest python/tests -q` | 131 passed（含 4 个新 API 测试 + 127 个回归），零收集错误 |
| `python -m pytest python/tests/test_calculation_api.py python/tests/test_runner.py -q` | 17 passed |
| `npm run test:method-status` | 18/18 pass |
| `npm run check:method-status` | cache is up to date (22 methods) |
| `npx tsc --noEmit` | 通过 |
| `git diff --check` | 通过 |

### 修订后提交链

- `ea5200c` — docs: authorize method status Stage C（基线）
- `29c072c` — fix: fail selected methods without substitution（Task 7）
- `e1163fa` — docs: sync authority docs after Stage C safety fixes（Task 8）
- `88bd731` — docs: report method status Stage C（初版报告）
- `d023de3` — fix: contain torch mock to session fixture scope（本次修订）

`Study/01` 与 `docs/history/260717.md` 未纳入。

### 审核状态

等待 Codex 对修订后实现出具 APPROVE / REVISE / BLOCK；`APPROVE` 后 Phase 0 正式关闭。
