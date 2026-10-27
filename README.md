# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

> 本文件是项目唯一权威入口。无论是人类开发者、Codex、Hermes、OpenCode、Claude Code，还是其他 AI coding agent，都从这里开始，再按任务需要渐进式阅读后续文档。

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

> **双仓整理（2026-10-27）**：已将日常目录切换为软件仓，科研工作转入 `D:\weibull-research`。[分仓检查记录](coworker/plans/2026-10-26-repository-split.md)记录保存点、验收及恢复位置；[v4.0 基线记录](coworker/plans/2026-10-27-v4-baseline.md)记录本轮版本与 Git 基线整理。

---

## 当前状态快照

> **软件状态更新**: 2026-10-27 · 以本节为软件当前状态权威；研究进度由科研仓维护。

**当前开发版本**：[v4.0.0](08-更新日志.md)（2026-10-27）。这是软件与科研分仓后，以软件现状态建立的开发基线；统一包元数据与页面版本标识。本次基线整理不改变算法或已有研究结果，尚未部署。v3.00 及其后已经完成的方法更新均包含在此基线中，原更新记录保留。

**双仓职责（2026-10-27）**：本仓维护网站、API、公共算法、统一蒙特卡洛流程和产品资源；Study、Research、论文与研究专用程序已迁至私有[科研仓 `weibull-research`](https://github.com/NEUwpy/weibull-research)。

**外挂文献库**：可通过服务器运行时配置`WEIBULL_LIBRARY_ROOT`读取独立文献目录；列表、原译文、图片、引用和问答取材共用同一来源，新增资料刷新即可读取。未配置时保留当前内置库，原文献和科研结果不移动。格式、核验、导入与回退见[外挂文献库说明](docs/外挂文献库.md)；[任务记录](coworker/plans/2026-10-27-external-literature.md)登记隔离验证与交付范围。

| 日常工作 | 本机目录与入口 |
|---|---|
| 网站、API、共享算法、产品模型与展示资源 | `D:\weibull`，本 README |
| 课题、实验、训练、论文、科研测试与证据 | `D:\weibull-research`，[科研 README](https://github.com/NEUwpy/weibull-research#readme) |

科研仓通过 `research.py setup / doctor / run` 集中选择软件路径，直接导入本仓 `python/` 源码，无需启动网站。共享入口是 `methods` 与 `studies.common`；科研的模型和输出写在科研目录。正式实验同时保存两仓提交号、dirty 状态及配置和数据身份；冻结实现与历史结果按原版本使用。新方法在科研仓验证，通过明确的代码或模型交付进入软件仓。

软件仓继续使用 [NEUwpy/weibull.work](https://github.com/NEUwpy/weibull.work)，新历史从无父提交的 `v4.0.0`（`6147387f`）开始。完整旧本地 Git 历史已封存至 `D:\weibull-backups\pre-v4.0-20261027\weibull-history.git`；旧公开 GitHub 仓库已改名为 [weibull.work-history-pre-v4-20261027](https://github.com/NEUwpy/weibull.work-history-pre-v4-20261027)并归档，只保留其原有公开历史。未公开的本地旧科研提交保存在本机封存中。所有备份与迁移恢复副本统一放在 `D:\weibull-backups`，使用与恢复步骤见 [v4.0 基线记录](coworker/plans/2026-10-27-v4-baseline.md)。旧 worktree 及历史文档仅用于恢复或追溯。当前科研工作只在科研仓继续，已迁出的 Study/Research 不作为实时镜像维护。

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | Python + FastAPI + SciPy/NumPy |
| 部署 | Docker + Cloudflare Tunnel |
| 托管 | 绿联 NAS（无公网 IP） |

```
用户 → Cloudflare CDN → Tunnel → NAS Docker
                                    ├── frontend:3000 (Next.js)
                                    └── backend:8001 (FastAPI)
```

**方法系统**：8 大类 22 子方法。详细建设状态（原子层级、计算器开放、证据路径）见 [`05-状态.md`](05-状态.md)，页面消费该文档的生成缓存。

当前第一轮方法建设已闭环：MLE、WMLE、MDM、LSE、MM、LRE 均完成第一层并在计算器开放，其中 MDM 已达到第二层完成；其余 16 个方法继续保持未开放状态。

**LRE 实现更新（2026-09-29）**：已按 Park（2017）Proposed+Plot 统一绘图位置、相关系数定位与 OLS，并完成论文算例和边界测试；[方法说明](src/content/algorithms/lre.md)标明引用作用及表值末位差异。旧 Bernard 版本研究结果未重算，本次为本地代码更新，未部署。

**MLE、WMLE求解更新（2026-10-16）**：v2采用条件求根与位置搜索，补查很窄的有限似然峰；MLE支持边界极限单列，WMLE保留原权重、残差门槛，并标记零边界近似解。已保存[更新前日期备份](https://github.com/NEUwpy/weibull-research/blob/main/Study/04-study-%E5%B0%8F%E6%A0%B7%E6%9C%AC%E4%B8%89%E5%8F%82%E6%95%B0Weibull%E4%BC%B0%E8%AE%A1%E6%96%B9%E6%B3%95%E6%AF%94%E8%BE%83%E4%B8%8E%E9%80%89%E6%8B%A9/%E7%A8%8B%E5%BA%8F/%E5%8E%86%E5%8F%B2%E7%89%88%E6%9C%AC/2026-10-16-%E6%B1%82%E8%A7%A3%E6%9B%B4%E6%96%B0%E5%89%8D/%E7%89%88%E6%9C%AC%E8%AF%B4%E6%98%8E.md)，完成论文算例、103组存档样本及800条旧成功结果验证；800条在新版中均仍有效。历史结果不覆盖，方法更新未部署。研究比较与冻结版本见科研仓的[实验设置](https://github.com/NEUwpy/weibull-research/blob/main/Study/04-study-%E5%B0%8F%E6%A0%B7%E6%9C%AC%E4%B8%89%E5%8F%82%E6%95%B0Weibull%E4%BC%B0%E8%AE%A1%E6%96%B9%E6%B3%95%E6%AF%94%E8%BE%83%E4%B8%8E%E9%80%89%E6%8B%A9/%E5%AE%9E%E9%AA%8C%E8%AE%BE%E7%BD%AE.md)。

**MMLE方法程序更新（2026-10-07）**：共享`mmle`改为Kundu–Raqab构造的单样本形式，旧Cohen–Whitten工程实现原字节保留为`mmle_ch`。R00两批200组存档样本对拍参数、状态与原有诊断完全一致；方法规则和支持检查区别见[开发说明](python/methods/README_DEV.md)。本轮仅更新共享程序，未开放计算器，未补齐R00结果。

| 大类 | 子方法 | 后端 |
|------|--------|------|
| 极大化适配法 | MLE, MMLE, MPS, WMLE | ✅ |
| 极小化适配法 | LSE, MDM | ✅ (WLSE/EIV→LSE 别名) |
| 线性回归法 | LRE | ✅ (BLRE/RRX/RRY→LRE 别名) |
| 矩方法 | MM, PWM | MM 已实现；PWM 未实现（LM/TLM 别名同为未实现） |
| 灰色估计法 | Grey GM(1,1) | ❌ NOT_IMPLEMENTED |
| 贝叶斯方法 | Bayesian | ❌ NOT_IMPLEMENTED（Gibbs/MAP 别名同为未实现） |
| 构造统计量法 | MVE, LSF | ❌ NOT_IMPLEMENTED |
| 人工智能方法 | PSO, SVR, ANN | ❌ NOT_IMPLEMENTED（见 AI 模块） |

**AI 方法层**：产品入口按 AI 介入位置分为过程量优化、直接估计和自适应选择；研究代号不作为用户界面名称。产品集成门槛见 [AI 当前路线图](docs/AI辅助三参数威布尔参数估计重构当前路线图.md)，研究状态与论文见[科研仓](https://github.com/NEUwpy/weibull-research)。

| 模块 | 当前状态 |
|------|----------|
| 过程量优化 | MDM 已接入：预测 26 个候选偏移量的损失并选择离散最低点，再调用生产 MDM；详情页复用统一计算卡片，并与固定 `δ=0.10` 成对展示预测损失、参数结果和带符号差异 |
| 直接估计 | 保留原型接口；独立部署与风险证据尚未完成，尚未作为产品默认。Research04 的研究进度由科研仓维护 |
| 自适应选择 | 页面入口已建立；部署选择与回退规则尚在研究，不提供自动方法推荐 |

---

## 文档权威模型

**Ground Truth 层级**：项目源文件（如本 README）> wiki 副本 > agent 记忆。冲突时源文件赢。

### 文档职责分工

| 文档 | 职责 | 类型 |
|------|------|------|
| `README.md` | 入口、路由、当前状态快照 | 权威源 |
| `02-规则.md` | 开发规范、复用规则、文档更新契约 | 权威源 |
| `04-目标与待办.md` | 长期目标、路线规划 | 权威源 |
| `05-状态.md` | 方法建设状态（单一可编辑事实源，含 22 个叶子方法的原子状态、层级推导与证据路径） | 权威源 |
| `06-模块.md` | 系统模块定义（目的-功能-结果） | 权威源 |
| `01-结构.md` | 文件组织、目录职责、数据流向 | 权威源 |
| `01-A-数据模型与接口.md` | 数据模型、API 端点、渲染管线 | 权威源 |
| `02-A-适用范围规范.md` | 适用范围模块的分片命名、组件结构 | 专题规范 |
| `02-B-可信性验证规范.md` | 验证配置格式、组件架构 | 专题规范 |
| `03-维护.md` | 部署流程、日常维护、故障排查 | 运维手册 |
| `07-用户手册.md` | 面向终端用户的使用说明 | 用户文档 |
| `08-更新日志.md` | 版本更新条目（只记事实，不做当前状态判断） | 日志 |
| `06-A-架构决策.md` | 关键架构决策的背景与后果 | 决策记录 |

### Docs-as-Data 与 Help 渲染

Help 页面是权威源的渲染视图，不是第二事实源：

| Help 路由 | 读取的权威源 |
|-----------|-------------|
| `/help/changelog` (版本页) | `08-更新日志.md` |
| `/help/changelog/todos` | `04-目标与待办.md` |
| `/help/manual` (用户手册) | `07-用户手册.md` |
| `/help/metrics` | `src/app/help/metrics/metrics-spec.ts` + 共享实现 |
| `/help/charts` | `src/app/help/charts/charts-spec.ts` + `chart-registry.ts` + 图表组件 |

`/help/metrics`、`/help/charts` 是渲染视图，不是第二事实源。指标规范源为 `metrics-spec.ts`，图表/表格展示规范源为 `charts-spec.ts`，真实图表使用实例由 `chart-registry.ts` 维护；可执行计算和渲染实现见 `src/lib/metrics.ts`、`python/studies/common/metrics.py` 及图表组件。`06-模块.md` §6.3/§6.4 为设计参考文档。

### 文档同步矩阵

改动发生时，必须同步的权威源：

| 改动类型 | 必须同步 |
|----------|----------|
| 新增/修改评价指标 | `02-规则.md` §5 + `src/app/help/metrics/metrics-spec.ts` + `src/lib/metrics.ts` + `python/studies/common/metrics.py` |
| 新增/修改图表/表格范式 | `02-规则.md` §5 + `src/app/help/charts/charts-spec.ts` + `chart-registry.ts` + 图表组件 |
| 新增方法/模块 | `06-模块.md` + `05-状态.md` + `04-目标与待办.md`（如涉及路线） |
| 版本发布 | `08-更新日志.md` + `README.md`「当前状态快照」（如状态变化） |
| 架构决策变更 | `06-A-架构决策.md` + `README.md`（如影响概况） |

详见 `02-规则.md` §11。

---

## 快速开始

### 启动后端 (Python API)

```bash
cd python
pip install -r requirements.txt
python main.py
# http://localhost:8001
```

### 启动前端 (Next.js)

```bash
npm install
npm run dev
# http://localhost:3000
```

---

## 代码位置

| 模块 | 路径 |
|------|------|
| 核心算法 | `python/methods/*.py` |
| API 接口 | `python/main.py` |
| 前端页面 | `src/app/` |
| UI 组件 | `src/components/` |

---

## 阅读路径

遵循渐进式披露：先读本 README，再根据任务继续深入。不要把历史归档当作当前依据。

| 文档 | 何时读 |
|------|--------|
| `02-规则.md` | 写新代码、改组件、改指标、改图表前 |
| `06-模块.md` | 需要了解系统功能定义 |
| `01-结构.md` | 需要了解文件组织和数据流向 |
| `01-A-数据模型与接口.md` | 需要了解接口细节 |
| `02-A-适用范围规范.md` | 开发适用范围模块 |
| `02-B-可信性验证规范.md` | 开发可信性验证模块 |
| `06-A-架构决策.md` | 需要了解设计原因 |
| `python/studies/common/README.md` | 开发蒙特卡洛、API 模拟、实验流水线 |
| `docs/AI辅助三参数威布尔参数估计重构当前路线图.md` | 把已有 Study/Research 证据转成 AI 能力 |
| `/help/metrics` | 使用或新增评价指标时（渲染视图；规范源为 `metrics-spec.ts`，可执行实现为 `src/lib/metrics.ts` + `python/studies/common/metrics.py`） |
| `/help/charts` | 使用或新增图表/表格范式时（渲染视图；规范源为 `charts-spec.ts`，实例源为 `chart-registry.ts`） |
| `03-维护.md` | 部署或运维 |
| `04-目标与待办.md` | 规划功能 |
| `07-用户手册.md` | 编写或核对用户手册内容 |
| `08-更新日志.md` | 查看版本更新记录 |
| [科研仓](https://github.com/NEUwpy/weibull-research) | 查看 Study、Research、论文、实验配置与科研进度；私有仓需要访问权限 |

---

## AI 与协作约定

- 所有人和所有 agent 都以本 README 为唯一入口。
- 编程、重构、修 bug、审查 diff 或在 Codex / Hermes / OpenCode / Claude Code 之间交接任务时，使用 `coworker` skill。
- 具体多 agent 任务的计划、分发、执行报告和验收记录放在 `coworker/`；该目录是流转工作区，不是新的规则入口。
- 默认协作角色：Codex 负责需求对齐、规划审查和最终验收；Hermes / MiMo 或 Claude Code / MiMo 优先执行；OpenCode / DeepSeek 可作二审、备选执行或独立 bug-finding。
- 规划只写目标、已知事实、边界、执行自主性、停止条件和验证条件；不要把执行者当新手写成逐步施工脚本。
- 写新代码前必须阅读 `02-规则.md`，并按任务读取相关专题规范。
- 禁止读取 `_archive/` 作为当前实现参考；`docs/history/` 和 `docs/oldrules/` 只用于历史追溯。
- 审查时以实际 diff、验证命令和项目规则为准，不以历史手稿覆盖当前代码事实。

## 凭证信息

GitHub、NAS、Cloudflare 等连接信息存储在 `docs/凭证信息.md`（本地文件，不提交）。
