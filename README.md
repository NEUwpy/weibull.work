# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

> 本文件是项目唯一权威入口。无论是人类开发者、Codex、Hermes、OpenCode、Claude Code，还是其他 AI coding agent，都从这里开始，再按任务需要渐进式阅读后续文档。

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

---

## 当前状态快照

> **快照日期**: 2026-09-06 · 以本节为当前状态权威；各分文档的进度表为开发追踪器。

**系统版本**：[v3.00-260906](08-更新日志.md)。本次完成结果分析、失败记录、异步计算和接口安全修复，并同步架构与研究入口；本地测试及生产构建通过，尚未部署。

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

**Study/02 当前态**：当前中英文正文与附录为[v2.7.0](Study/02-study-NN参数估计与分位点目标研究/manuscript/Study02论文初稿-v2.7.0.md)，主线为P → Q → QCP：任务对齐的目标收益、参数补偿代价与修复。QP与QCP精度接近，共同验证下Q仍有1.322%目标改善；协议25复用旧样本，不是新数据独立确认。2026-09-08按正文整理为[S02-01—S02-07](Study/02-study-NN参数估计与分位点目标研究/02-实验配置.md)，建立[证据索引](Study/02-study-NN参数估计与分位点目标研究/01-证据索引.md)，将退役展开数据移至外部待删除目录供用户自行删除，未释放磁盘空间。认识、去留及恢复见[研究快照](Study/02-study-NN参数估计与分位点目标研究/07-认识清单与研究快照-20260908.md)。先明确参数解释与寿命点使用要求，再决定最小新样本确认；未投稿。

**Study/01 当前态**：当前[正文 v1.12](Study/01-study-MDM最小偏移量优化研究/manuscript/Study01论文初稿-v1.12.md)与附录 v1.10 研究 MDM 偏移量的风险、参数域依赖和样本自适应选择。现有离散设计中，Mean-Normalized-MLP 的 J1 从 0.6304 降到 0.5846，改善 7.27%，125/160 单元改善；寿命收益有限，冻结后的新增独立重复确认尚未执行。2026-09-07 已清理旧试错产物并重写说明，当前实验按 S01-01—S01-08 编号，见[实验配置](Study/01-study-MDM最小偏移量优化研究/02-实验配置.md)及[正文—实验—证据索引](Study/01-study-MDM最小偏移量优化研究/01-证据索引.md)。旧代码和封存路径通过对照表保留来源身份。先明确可靠性用途，再决定最小独立确认，暂缓定刊与投稿制作；试错认识和恢复信息见[研究快照](Study/01-study-MDM最小偏移量优化研究/07-认识清单与研究快照-20260907.md)。

**Study / Research 层级**：[`Study/README.md`](Study/README.md) 是 Study 层唯一入口，当前登记 Study01、Study02 两个具有独立小论文义务的项目；[`Research/README.md`](Research/README.md) 保存有界验证、支撑研究、独立研究和孵化方向，并定义升级为 Study 的门槛。原 Study015 已作为 `COMPLETE + SUPPORTING` 的“NN 输入表征与样本量机制”迁入 Research；旧 `docs/research` 与 Study01 内部 Research 已按 [`RELOCATION.json`](Research/RELOCATION.json) 原字节归位，不删除负面或被取代结果。

**Research/05 当前态**：传统方法风险地形 v1 已在 Study01 的 160 个设计单元、48,000 个共享样本上完成。primary candidate 为 MDM-0.1、WMLE、LSE；五折交叉评价的真参数 cell 选择相对最佳固定 MDM-0.1 将 pooled J1 从 0.630409 降至 0.592141，改善 6.07%，设计单元 bootstrap 95% 区间 [4.85%, 7.30%]。样本量单独没有选择收益，主要分界来自形状参数；该结果只证明存在机会空间，下一步进入可观测性 Research，尚不建立新 Study。详见 [`Research/05-传统估计方法横向比较/`](Research/05-传统估计方法横向比较/)。

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

**AI 方法层**：产品入口按 AI 介入位置分为过程量优化、直接估计和自适应选择；研究代号不作为用户界面名称。当前科学路线见 [`Study/README.md`](Study/README.md)、[`Study/研究规划v0.3.md`](Study/研究规划v0.3.md) 和 [`AI 当前路线图`](docs/AI辅助三参数威布尔参数估计重构当前路线图.md)。

| 模块 | 当前状态 |
|------|----------|
| 过程量优化 | MDM 已接入：预测 26 个候选偏移量的损失并选择离散最低点，再调用生产 MDM；详情页复用统一计算卡片，并与固定 `δ=0.10` 成对展示预测损失、参数结果和带符号差异 |
| 直接估计 | Research04 核心比较与训练域设计实验已完成，正文及附录 [v0.2](Research/04-直接NN参数估计/03-稿件-直接神经估计与结构保留路线比较-v0.2.md) 按 Mentor 意见收口：域内未训练 β 点保持优势，低 β 外推反转；同中心扩宽在固定密度下仍有共同区间精度代价。完整方案比较与机制解释已区分，尚未分离目标/选点、逼近和优化贡献；风险诊断仅作探索，Research 仍为 `ACTIVE`，尚未作为产品默认 |
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
| `Research/README.md` | 查看项目级有界研究、成熟度、与 Study 的关系及历史归档 |
| `Study/README.md` | 判断 Research / Study 边界、共同原则与当前课题映射 |
| `Study/研究规划v0.3.md` | 查看博士总体问题、研究空间、后续方向与综合逻辑 |

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
