# Stage B 执行报告：方法状态前端消费者

Role: executor（OpenCode/DeepSeek，按 Hermes Stage B 投递单执行）

Handoff: `coworker/handoffs/2026-07-17-method-status-foundation-stage-b-hermes.md`
Plan: `coworker/plans/2026-07-17-method-status-foundation.md`（Stage B / Tasks 4–6）
Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

## 提交范围

| 项 | 值 |
|----|----|
| 起始基线 | `564ec8b`（Stage B 投递单提交，Stage A APPROVE） |
| Task 4 提交 | `4b26cc2` feat: render method status from docs |
| Task 5 提交 | `af4e703` feat: gate calculator by method maturity |
| Task 6 提交 | `da8f39c` feat: expose method construction states |
| 未纳入 | `Study/01`、`docs/history/260717.md`（保持工作区未提交） |

## 改动文件（按任务）

### Task 4: 类型化访问器 + dashboard 迁移

- **新建** `src/lib/method-status.ts` — 从 `src/data/method-status.generated.json` 读取，导出 `AtomicStatus`、`MethodLevel`、`MethodCapability` 类型和 `getMethodCapability()`、`isCalculatorEnabled()`、`getEnabledMethodIds()`、`getMethodCapabilities()` 四个函数。模块不重声明状态数据，运行时 shape assertion 保护。
- **重写** `src/app/help/changelog/page.tsx` — 移除 `METHOD_STATUS` 硬编码常量、局部 `MethodStatus` 接口和 `Status` 类型。从 `getMethodCapabilities()` 渲染全部 22 个方法。保留原表格视觉语言，新增「层级」列（`closed_loop`/`layer2_complete`/`layer1_complete`/`layer1_in_progress`/`not_started` 五级）和「第一层」列（paper+5 layer1 完成数 / 6）。7 列 Tab（原理文档/程序流程/计算过程/结果分析/适用范围/可信性验证/方法对比）从生成数据原子状态派生，方法对比统一显示为平台级未计入。汇总进度条从实际 item 计数计算。

验证：
- `rg -n "const METHOD_STATUS" src/app/help/changelog/page.tsx` → 无匹配
- `npx tsc --noEmit` → 通过
- `npm run check:method-status` → cache is up to date (22 methods)

### Task 5: 计算器门控 + `?method=` 选择

- **修改** `src/components/calculator/MethodSelector.tsx` — 导入 `isCalculatorEnabled`。6 处 `method.hasDetail` 全部替换为 `isCalculatorEnabled(method.id)` 或 `isCalculatorEnabled(activeMethodId)`：`handleConfirm` 守卫、方法列表 `isImplemented` 变量、行样式和禁用态、确认按钮 disabled/className。保留日志移除 `hasDetail` 引用。`hasDetail` 属性在 `methods.json` 类型定义中保留不动（仅供未修改代码路径做详情查询）。
- **修改** `src/app/page.tsx` — 导入 `isCalculatorEnabled`、`getEnabledMethodIds`。init `useEffect` 新增 `?method=` 参数读取：若参数方法 `calculatorEnabled` 则使用；否则取 `getEnabledMethodIds()[0]`；若无可启方法则不预设 method 结果。当启用方法被选中且数据存在时，通过 `calculateWeibull()` 调用后端获取初始结果（失败时保留本地计算结果为降级），不再将本地 MLE 计算标记为另一方法的输出。保留 `caseId` 行为。

验证：
- `npx tsc --noEmit` → 通过
- `npm run check:method-status` → 通过
- `rg -n "hasDetail" src/components/calculator/MethodSelector.tsx` → 无匹配
- `rg -n "hasDetail" src`（仅限 TS/TSX）→ 仅在 `src/lib/methods.ts`（type 定义）和 `src/data/methods.json`（数据源），不再参与任何计算器门控逻辑

### Task 6: 方法详情页状态面板

- **新建** `src/components/methods/MethodBuildStatus.tsx` — 共享状态面板组件。接受 `label`、`status`、`reason?`、`evidence?`。渲染：`todo` → "未开始"、`in_progress` → "进行中"、`blocked` → "受阻"（含 reason）、`not_applicable` → "不适用"（含 reason，当 `exception_approved` 为 true 时）。各态有独立点色/背景色/文字色，匹配现有视觉语言。
- **修改** `src/app/methods/[methodId]/page.tsx` — 导入 `getMethodCapability` 和 `MethodBuildStatus`。在 `MethodDetail` 中取 `capability` 和 `isFirstLayerComplete`。Tab 内容门控：各 tab body 先检查对应原子状态是否为 `done`，非 `done` 时渲染 `MethodBuildStatus`。门控映射：theory（layer1.theory）、flow（layer1.process）、lab（layer2.calculation）、analysis（layer2.analysis）、examples（layer3.applicability）、cases（layer3.verification）。compare 保持无门控（平台级 tab）。Apply 链接门控：`isFirstLayerComplete` 时渲染可点击链接，否则渲染灰态 "开发中" 占位。

验证：
- `npx tsc --noEmit` → 通过
- `npm run check:method-status` → 通过

## 计算器开放推导结果（Tasks 4-5 后）

| 方法 | calculatorEnabled | 层级 |
|------|:---:|------|
| mdm | true | layer2_complete |
| mle | false | layer1_in_progress |
| mmle | false | layer1_in_progress |
| wmle | false | layer1_in_progress |
| lre | false | layer1_in_progress |
| 其余 17 个 | false | not_started |

仅 MDM 可在计算器中选择，其他方法灰显并标注"开发中"。`?method=mdm` 可正确预设并调用后端。

## Tab 状态覆盖（详情页 MethodBuildStatus 渲染）

以当前 `05-状态.md` 数据，各方法详情页各 tab 的渲染行为：

| 方法 | theory | flow | lab | analysis | examples | cases | apply |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| mdm | 内容 | 内容 | 内容 | 内容 | 内容 | 进行中 | 链接 |
| mle | 内容 | 内容 | 未开始 | 未开始 | 内容 | 未开始 | 开发中 |
| mmle | 内容 | 内容 | 未开始 | 未开始 | 未开始 | 未开始 | 开发中 |
| wmle | 内容 | 内容 | 内容 | 未开始 | 进行中 | 未开始 | 开发中 |
| lre | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 开发中 |
| mps/lse/mm/pwm/gm11/gibbs/map 等 15 个 | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 开发中 |
| wlse/eiv/blre/lm/tlm（别名, 17 个中的 5 个） | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 未开始 | 开发中 |

> 方法对比（compare）tab 始终渲染，不参与方法建设门控。

## 剩余 hasDetail 引用

| 位置 | 用途 | 状态 |
|------|------|------|
| `src/lib/methods.ts:10` | `MethodNode` 类型定义 `hasDetail?: boolean` | 保留（非计算器门控，仅供未修改代码路径做详情查询） |
| `src/data/methods.json` | 4 个叶子方法含 `hasDetail: true` | 保留（数据源，不影响计算器可用性） |

无 `hasDetail` 用于计算器门控。

## 跳过的检查

- 未运行 `npm run build`（Stage B 未修改构建逻辑，`prebuild` 钩子包含 `check:method-status`，已就位）。
- 未运行 Python 测试（Stage B 未触碰 Python 代码）。
- 未进行浏览器手工验证（计划要求手工验证 MDM 可选/mps 禁用，但本项目无 playwright/cypress 配置）。

## 偏离与阻塞

- 偏离：无。未实现任何算法，未重新设计计算器或方法总览布局，未添加建设标签到 `/methods`，未移除 `hasDetail` 类型或数据属性，未触碰 `Study/01` 等不相关文件。
- 阻塞：无。

## 停止点

Stage B 全部完成，已按投递单停止。未进入 Stage C（WMLE 回退移除等后端任务）。等待 Codex 审核。
