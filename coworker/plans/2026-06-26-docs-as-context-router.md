# Task Plan

Goal:

将项目文档改造成“README 作为上下文路由器，分文档作为按需加载的权威源，Help 页面作为同一权威源的渲染视图”的结构。文档应真实反映当前状态，支持 AI / 人按任务渐进式读取；内容要像地图和契约，不写成教程、流水账或执行脚本。

Known facts:

- 当前基线提交：`c8b7ec4`。
- `README.md` 是唯一入口；`AGENTS.md` 只是兼容重定向。
- 用户明确希望 docs-as-data：同一份结构化权威源既能被 AI / 人读取，也能被 `/help` 页面渲染。
- 当前 `/help` 已经部分读取 Markdown：版本页读 `08-更新日志.md`，待办页读 `04-目标与待办.md`，用户手册功能页读 `07-用户手册.md`。
- `/help/metrics`、`/help/charts` 目前仍较多硬编码，但本阶段只做文档源治理，不改 React 页面读取逻辑。
- 当前 AI 口径：M1/M3 有旧原型，但不作为当前正式结论；M1 当前状态为旧原型/待重构，M2/M4 待开发。
- 当前工程底座：`python/studies/common/` 是统一抽样、方法调用、指标聚合和实验输出入口；MDM full-v1 是研究03 baseline。

Boundaries:

- Allowed:
  - 修改 `README.md`，让它成为高密度上下文路由器：当前状态快照、文档权威顺序、按任务阅读路径、docs-as-data/Help 渲染关系、文档同步矩阵。
  - 修改 `02-规则.md`，增加“文档更新契约”或“改动类型 -> 必须同步的权威源”规则。
  - 修改 `04-目标与待办.md`，使其成为可被 `/help/changelog/todos` 读取的当前长期目标/路线源，清除明显过期口径。
  - 修改 `05-状态.md`，使其成为当前状态源，或将其明确降级为不再作为当前依据并在 README 中说明。二选一即可，但不能继续留下独立旧状态。
  - 修改 `06-模块.md`，只做必要的口径对齐和去冗余；保持模块地图属性。
  - 必要时小幅修改 `07-用户手册.md`、`08-更新日志.md` 中和本次文档源治理直接相关的入口/口径说明。
  - 可以在 `coworker/reports/2026-06-26-docs-as-context-router-hermes.md` 写执行报告。
- Not allowed:
  - 不修改业务代码、算法代码、实验脚本、模型、数据文件。
  - 不改 `src/app/help/**` 的 React 实现；Help 读取化代码改造留到下一阶段。
  - 不移动、删除或归档 `_archive/`、`docs/history/`、研究产物目录。
  - 不把 README 写成长篇说明书；避免复制各分文档正文。
  - 不新增另一份“全项目总纲”来和 README/路线图竞争权威。

Executor autonomy:

- 选择最小改动路径，让文档职责边界清楚即可。
- 可以重组标题、删减过期段落、压缩重复说明。
- 保留读者智能预期：写给有能力的 AI / 人，不写低价值步骤教学。
- 遇到当前事实不确定时，优先引用现有代码或当前文档；若仍不确定，停止并报告，不要编造状态。

Stop conditions:

- 发现 `04-目标与待办.md`、`05-状态.md` 是否保留的选择会显著改变方案且无法从现有讨论判断。
- 发现 Help 页面读取结构必须改 React 才能让文档不矛盾。
- 发现当前文档与代码事实冲突，且无法用“旧原型/历史/当前正式”标签解决。
- 需要删除、移动、归档敏感历史文件。

Verification:

- `git diff --check`
- `rg -n "25\\+|已实现，含 R1|关系建立原型已完成|S2R 评价指标体系成为当前唯一|docs/oldrules|AI协作协议.md" README.md 02-规则.md 04-目标与待办.md 05-状态.md 06-模块.md 07-用户手册.md 08-更新日志.md`
- 手动检查：
  - README 能在 2 分钟内说明当前态、入口、权威顺序、按任务阅读路径。
  - `04-目标与待办.md` 作为 Help 待办源不再宣传旧完成状态为当前正式结论。
  - `05-状态.md` 不再和 README/06/路线图冲突。
  - 没有新增硬编码第二事实源。

Report:

写入 `coworker/reports/2026-06-26-docs-as-context-router-hermes.md`，包含：

- changed files
- summary of the new document authority model
- checks run and exact results
- skipped checks with reasons
- any open questions or deviations
