# Stage A 执行报告：方法状态基础（状态源与生成缓存）

Role: executor（OpenCode/DeepSeek，按 Hermes 投递单执行）

Handoff: `coworker/handoffs/2026-07-17-method-status-foundation-hermes.md`
Plan: `coworker/plans/2026-07-17-method-status-foundation.md`（Stage A / Tasks 1–3）
Design: `docs/superpowers/specs/2026-07-17-method-construction-status-source-design.md`

## 提交范围

| 项 | 值 |
|----|----|
| 起始提交 | `8350f29`（计划提交，本轮基线） |
| Task 1–2 提交 | `f8b6761` feat: validate method construction status |
| Task 3 提交 | `d7e3ac7` docs: establish method status source |
| 未纳入 | `Study/01` 三个 draft 改动、`docs/history/260717.md`（保持工作区未提交状态） |

## 改动文件（按任务）

Task 1（测试先行）：

- 新建 `scripts/tests/method-status.test.mjs` — 14 个 `node:test` 用例，含投递单要求的 5 个精确用例 + 9 个补充用例（层级推导连续性、not_started、未知状态、重复 ID、论文引用元数据、not_applicable 例外）。
- 先行运行确认因 `ERR_MODULE_NOT_FOUND`（`scripts/lib/method-status.mjs` 不存在）按预期失败。

Task 2（解析器/校验器/生成器）：

- 新建 `scripts/lib/method-status.mjs` — 导出计划要求的 `STATUS_VALUES/LAYER1_KEYS/LAYER2_KEYS/LAYER3_KEYS`、`validateStatusDocument()`、`deriveMethodCapability()`、`buildGeneratedStatus()`、`parseStatusMarkdown()`，另加 `flattenLeafIds()` 供 CLI 复用。校验覆盖：重复/缺失/多余 ID、未知状态、`done` 无证据、`blocked` 无原因、完成论文缺引用元数据（title/publication/year/stable_id）、必填项 `not_applicable` 需 `exception_approved: true` + reason、未知字段拒绝。证据路径存在性检查通过 `options.checkEvidencePaths` 在 CLI 侧启用（fail-closed）。
- 新建 `scripts/generate-method-status.mjs` — 从仓库根读取 `05-状态.md` + `src/data/methods.json`，flatten children 得叶子 ID，写/校验 `src/data/method-status.generated.json`；输出含 `schemaVersion`、`source: "05-状态.md"`，无时间戳与绝对路径，稳定 2 空格缩进 + 结尾单换行；`--check` 过期时非零退出并给出可操作提示。
- 修改 `package.json` — 恰好新增计划要求的 5 个脚本（`generate:method-status`、`check:method-status`、`test:method-status`、`predev`、`prebuild`），原有脚本保留。未新增任何依赖（`gray-matter@4.0.3` 已在 dependencies）。

Task 3（保守迁移）：

- 重写 `05-状态.md` — YAML front matter 覆盖 22 个叶子方法全量 schema；正文改为控制指南（三层级、状态图例、自动推导规则、证据要求、论文交接、生成命令、设计/路线图链接），不再重复 YAML 中的每方法状态；原「方法状态」人工表删除；AI 模块表保留（AI 模块另设成熟度标准，见正文说明）。
- 新建（生成）`src/data/method-status.generated.json`。

## 验证结果（精确）

| 命令 | 结果 |
|------|------|
| `node --test scripts/tests/method-status.test.mjs`（实现前） | FAIL：`ERR_MODULE_NOT_FOUND`（预期） |
| `npm run test:method-status` | 14/14 pass |
| `npm run generate:method-status` | wrote 22 methods |
| `npm run check:method-status` | cache is up to date (22 methods) |
| `git diff --check` | 通过（无 whitespace/conflict 标记） |
| 叶子 ID 集合 | `src/data/methods.json` flatten 后恰为 22 个，与状态文档一一对应 |

后端定样本烟测（`generate_sample(2.0, 100.0, 5.0, 30, 0)` + `run_method`）：

- 返回有效估计：mle、mmle、wmle、mdm(offset=0.1)、lre（5 个）；
- 抛 `NotImplementedError`：mps、lse、mm、pwm、grey、bayesian（6 个注册占位）。

## 初始状态计数与推导结果

| 层级 | 数量 | 方法 |
|------|------|------|
| `layer2_complete` | 1 | mdm |
| `layer1_in_progress` | 4 | mle、mmle、wmle、lre |
| `not_started` | 17 | 其余全部 |

**计算器开放推导（`calculatorEnabled`）：仅 mdm。**

各在建方法第一层缺口：

- mle：`paper`（PAPER_NEEDED）
- mmle：`paper`、`tests`（无独立测试）
- wmle：`tests`（无独立测试；论文 182-088 已闭合）
- lre：`paper`、`calculator`（选择器未开放）、`theory`（无原理文档）、`process`（无 @step 标注）

## 相对旧状态表的保守降级

| 方法 | 旧表声明 | 迁移结果 | 依据 |
|------|---------|---------|------|
| WMLE 计算过程 | ✅ | `done`（保留） | `src/components/methods/wmle` 存在可视化组件 |
| WMLE 适用范围 | ⬜ | `in_progress` | `public/studies/wmle` 已有 chunks+demo1 数据，旧表未确认完成，不升为 done |
| MLE 计算/分析 | ⬜ | `todo`（维持） | 无组件目录证据 |
| LRE 全部 Tab | ⬜ | `todo`（维持）；仅 backend/tests 依烟测与 test_runner 断言标 done | 无 theory/process/calculator 证据 |
| MLE/MMLE process | ✅ | `done`（保留） | 流程 Tab 实际由 `/api/method-flow` 解析 python 源 `@step` 标注渲染；`mle.py` 7 处、`mmle.py` 9 处标注存在 |
| 占位方法（mps/lse/mm/pwm/gm11/bayesian 系） | 未列入旧表 | backend `todo` + note | 仅 5 行占位类，抛 `NotImplementedError`，不算实现 |
| 别名变体（wlse/eiv/blre/lm/tlm/gibbs/map） | 未列入旧表 | backend `todo` + note「仅为 X 的注册别名」 | 设计禁止别名充当实现 |
| mve/lsf/pso/svr/ann | 未列入旧表 | 全 `todo` | 注册表 NOT_IMPLEMENTED |

无方法从旧表 done 被凭空升级；无 legacy 计算器覆盖项。

## PAPER_NEEDED（3 项，状态保持 blocked）

```text
PAPER_NEEDED
方法：mle 极大似然估计
需要：与当前三参数 MLE 实现口径一致的专项论文
已知线索：181-004 引用 Smith (1985)、Hirose (1996)
用途：公式核对、参数规则、测试基准
当前可继续部分：独立测试补强、状态基础设施、接口审计
```

```text
PAPER_NEEDED
方法：mmle 修正极大似然估计
需要：Cohen & Whitten (1982) Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution 全文
已知线索：题名/作者/年份如上，181-004 有引用线索
用途：公式核对、参数规则、测试基准
当前可继续部分：独立测试补强、状态基础设施
```

```text
PAPER_NEEDED
方法：lre 线性回归
需要：Park (2017) Weibullness test and parameter estimation for the three-parameter Weibull model using the sample correlation coefficient 全文
已知线索：题名/作者/年份如上
用途：公式核对、理论说明、测试基准
当前可继续部分：原理文档、@step 流程标注前置调研（不做状态升级）
```

## 判断说明（供审核）

1. **WMLE 论文 stable_id**：本地 `182-088-pdf原文.md` 无 DOI；采用可从本地证据（181-004 参考文献 [10]）核验的等价稳定标识 `Br. J. Math. Stat. Psychol. 62(1): 167-191 (2009)`，未杜撰 DOI。
2. **process 证据口径**：流程 Tab 实际渲染源是 python 源码 `@step` 标注（`src/app/api/method-flow/[methodId]/route.ts`），故 mle/mmle 的 process 证据指向 `python/methods/*.py`；mdm/wmle 同时保留 `src/data/method_flows/*.json`。
3. **calculator 项口径**：mle/mmle/wmle/mdm 标 done 指「计算器接入已完成」（经 `src/hooks/useWeibullCalculation.ts` 调用后端 `/calculate`，当前 UI 可选）；是否**向用户开放**由推导的第一层完成状态决定，此为设计允许的建设期完成。
4. **证据路径存在性检查**放在 CLI（`checkEvidencePaths: true`），单元测试保持纯函数——生成路径 fail-closed 不受影响。

## 跳过的检查

- `npx tsc --noEmit`、`npm run build`、pytest 全量：Stage A 未触碰 TS 页面与 Python 生产代码，计划将其安排在 Stage B/C；`prebuild` 钩子已就位。
- 未验证 `05-状态.md` 在 Help 文档渲染管线中的显示效果（front matter 对渲染的影响属 Stage B 页面接入范围）。

## 偏离与阻塞

- 偏离：无。未实现任何缺失算法，未改动页面/计算器/回退逻辑，未触碰 `Study/01`、`Study/02`、`docs/history/`、`_archive/`。
- 阻塞：无。3 项 PAPER_NEEDED 不阻塞后续独立基础设施工作。

## 停止点

Stage A 完成，已按投递单停止。

---

## 修订（2026-07-17，REVISE 响应）

审核记录：`coworker/reviews/2026-07-17-method-status-foundation-stage-a-codex.md`。判决：REVISE。两个 P2 缺口，一个修订提交。

### 修订提交

`f95bb9c` — fix: harden method status validation boundary

### 修复内容

| 缺口 | 修复 |
|------|------|
| [P2] 证据路径可逃出仓库 | `assertRepositoryPath()`：resolve 候选路径后通过 `path.relative(root, candidate)` 拒绝 `..`、`../outside` 和绝对路径；`classification_source` 也纳入仓库路径校验 |
| [P2] 目录元数据未做一致性校验 | `flattenCatalogLeaves()` 拒绝重复 category/leaf ID；`validateStatusDocument()` 通过 `options.catalogLeaves` 校验 name/family 与 `methods.json` 一致 |

### 新增测试（4 个边界用例）

- `evidence path must not escape the repository root` — `..` 和 `../outside` 均被拒绝
- `duplicate leaf ids in methods catalog are rejected`
- `name in status document must match methods catalog`
- `family in status document must match methods catalog`

### 修订验证

| 命令 | 结果 |
|------|------|
| `npm run test:method-status` | 18/18 pass（原 14 + 新增 4） |
| `npm run check:method-status` | cache is up to date (22 methods) |
| `git diff --check` | 通过 |
| path_escape 探针 | REJECTED |
| name_family_drift 探针 | REJECTED |
| duplicate_catalog_ids 探针 | REJECTED |

### 修订后提交链

- `8350f29` — docs: plan method status foundation（基线）
- `f8b6761` — feat: validate method construction status（Task 1–2）
- `d7e3ac7` — docs: establish method status source（Task 3）
- `f95bb9c` — fix: harden method status validation boundary（本次修订）

缓存未变化（`05-状态.md` 数据为真值，本次修订仅加固校验器）。

### 审核状态

等待 Codex 依据 `coworker/reviews/2026-07-17-method-status-foundation-codex-contract.md` 对修订后实现出具 APPROVE / REVISE / BLOCK；`APPROVE` 后方可开始 Stage B。
