# Task Plan

## Goal

把 Help 规范页从“页面里写死说明文字”推进为“权威源 / 注册表 / 共享实现驱动的渲染视图”。

本阶段重点治理最容易膨胀、最容易产生重复事实的三类内容：

- 指标与公式：计算调用共享函数，说明从可读规范源渲染。
- 图表与表格：定义有限的可复用展示范式，后续页面按范式和数据契约复用，不再临时重写图表。
- Help 页面：只负责布局、交互和渲染，不成为第二事实源。

完成后，新增或修改指标、公式、图表、表格时，应能明确知道：改哪个权威源、调用哪个共享实现、Help 从哪里展示。

## Known facts

- `README.md` 是项目唯一权威入口；`AGENTS.md` 只是兼容重定向。
- 第一阶段已完成 README context router 和文档源治理，最新提交为 `c39e05a`。
- 现有 Help 已部分读取 Markdown：
  - `/help/changelog/versions` 读取 `08-更新日志.md`
  - `/help/changelog/todos` 读取 `04-目标与待办.md`
  - `/help/manual/features` 读取 `07-用户手册.md`
- `/help/metrics` 仍主要在 `src/app/help/metrics/page.tsx` 中硬编码指标卡片、公式说明和开发规范。
- `/help/charts` 已有 `src/app/help/charts/chart-registry.ts` 记录使用实例和数据源，但图表类型清单、用途、配色、表格/图表规范文本仍大量写在 `src/app/help/charts/page.tsx`。
- 指标可执行实现已经存在于：
  - `src/lib/metrics.ts`
  - `python/studies/common/metrics.py`
- 图表可执行组件已经分布在：
  - `src/components/ai/charts/`
  - `src/components/shared/charts/`
  - `src/components/methods/*/charts/`
- `src/lib/markdown.ts` 已有轻量 Markdown 工具：`stripBlockquotes()`、`extractFromHeading()` 等。
- `08-更新日志.md` v1.71 当前仍有一个小矛盾：先说 `06-模块.md` 指标/图表清单是 Help 权威数据源，后面又说已修正为代码/Help 规范权威。

## Desired Architecture

```text
README.md
  -> 按任务路由到权威源

指标/公式规范源
  -> Help metrics 页面渲染
  -> 与 src/lib/metrics.ts / python/studies/common/metrics.py 保持实现口径一致

图表/表格展示规范源 + chart registry
  -> Help charts 页面渲染
  -> 业务页面复用既有 chart/table 范式和组件

共享实现 / 组件
  -> 负责真实计算和真实渲染
  -> 不由 Help 页面重复实现
```

## Boundaries

### Allowed

- 新增少量权威规范源文件，例如：
  - 指标/公式规范源
  - 图表/表格展示规范源
  - 必要的结构化 registry / catalog 模块
- 修改 `/help/metrics`，让页面从规范源渲染指标、公式、含义、使用场景、实现位置等内容。
- 修改 `/help/charts`，让页面从规范源 / registry 渲染图表类型、表格类型、用途、数据 shape、视觉语义、复用规则和使用实例。
- 保留并复用现有 `chart-registry.ts` 的真实数据展开能力；可以重构它的结构，但不要丢失现有实例信息。
- 修改 `README.md`、`02-规则.md`、`06-模块.md`、`07-用户手册.md` 中与本阶段直接相关的权威源和读取关系说明。
- 修正 `08-更新日志.md` v1.71 的自相矛盾条目，使版本页渲染出的历史记录不误导读者。
- 新增或复用轻量 Markdown/registry 读取工具，前提是实现简单、可维护、符合现有 Next.js 模式。

### Not allowed

- 不重构算法、实验脚本、模型训练、数据生成逻辑。
- 不重写所有业务页面的图表调用；本阶段只建立规范源和 Help 渲染，不做全站迁移。
- 不为了“读取化”引入重型 CMS、数据库、远端服务或复杂构建链。
- 不把同一事实同时写进 Markdown、TSX、registry 三处；如果必须有可读文档和结构化 registry，必须明确各自职责，避免重复同一口径。
- 不把 README 写成长篇总纲；README 仍是路由器和当前状态快照。
- 不移动、删除或归档 `_archive/`、`docs/history/`、研究产物目录。
- 不读取历史归档作为当前实现依据，除非只是核对历史背景。

## Design Guidance

- “不是硬编码”的核心不是文件扩展名，而是页面不再拥有事实。TSX 页面应导入或读取源，然后渲染。
- 指标/公式至少应覆盖：
  - 稳定 ID / 名称
  - 公式
  - 变量定义
  - 含义和回答的问题
  - 主指标或诊断指标
  - 适用视角（参数视角、工程寿命视角等）
  - 对应共享实现位置
- 图表/表格规范至少应覆盖：
  - 展示范式 ID / 名称
  - 适用问题
  - 期望数据 shape
  - 推荐组件
  - 视觉语义（颜色、坐标轴、参考线、误差方向等）
  - 当前使用位置或 registry 入口
- “表格”要纳入规范，不只治理 charts；常见表格可先定义为 summary table、comparison table、diagnostic table、parameter grid table 等有限范式。
- 规范文字要克制，像地图和契约，不写成教程或流水账。
- 若发现现有公式说明与共享实现不一致，优先以实现和测试为准，并在报告中明确列出差异。

## Stop Conditions

- 发现指标公式、变量定义或当前实现存在实质冲突，无法在不改算法口径的情况下对齐。
- 发现图表 registry 与真实组件/业务页面使用大面积不一致，超出本阶段 Help 读取化范围。
- 需要对业务页面做大规模迁移才能避免文档矛盾。
- 需要删除、移动、归档敏感历史文件。
- 无法用现有 Next.js 构建方式安全读取新增规范源。

## Verification

必须运行：

```powershell
git diff --check
npx tsc --noEmit
```

如项目环境允许，额外运行：

```powershell
npm run build
```

必须做文本检查：

```powershell
rg -n "CORE_METRICS|const chartGroups|新增图表 → 必须先更新本页面|图表类型、用途、配色规范已嵌入规范页|06-模块.*权威数据源" src/app/help README.md 02-规则.md 04-目标与待办.md 06-模块.md 07-用户手册.md 08-更新日志.md
```

期望结果：

- `/help/metrics` 不再用页面内 `CORE_METRICS` 作为事实源。
- `/help/charts` 不再用页面内 `chartGroups` 或页面内规范文本作为事实源。
- README 和规则文档不再把 Help 页面本身描述成事实源；Help 应被描述为渲染视图。
- `08-更新日志.md` v1.71 不再留下互相矛盾的最终状态描述。

手动检查：

- `/help/metrics` 能展示指标公式、意义、实现位置和主/诊断口径。
- `/help/charts` 能展示图表/表格范式、复用规则、组件/registry 关系和现有实例。
- 新增规范源能被人和 agent 直接读取，不依赖打开 React 页面才能理解。
- 页面交互能力没有明显倒退，尤其是 charts 页已有的实例展开能力。

## Report

写入：

`coworker/reports/2026-06-26-help-specs-as-data-hermes.md`

报告必须包含：

- changed files
- 新的权威源 / registry / Help 渲染关系
- 哪些内容从 TSX 页面迁出，迁到了哪里
- 指标/公式与共享实现是否发现不一致
- 图表/表格规范覆盖了哪些范式
- checks run and exact results
- skipped checks with reasons
- deviations from this plan
- blockers or open questions
