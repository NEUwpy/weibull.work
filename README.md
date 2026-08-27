# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

> 本文件是项目唯一权威入口。无论是人类开发者、Codex、Hermes、OpenCode、Claude Code，还是其他 AI coding agent，都从这里开始，再按任务需要渐进式阅读后续文档。

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

---

## 当前状态快照

> **快照日期**: 2026-08-24 · 以本节为当前状态权威；各分文档的进度表为开发追踪器。

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

**Study/02 当前态**：论文主线已收口为一个受控问题：在 Study01 冻结参数网格和相同三参数网络下，仅改变训练/验证损失，`Q_param` 相对本文定义的 `P_equal` 能把目标可靠度寿命点 \(x_{0.95}\) 的误差降低多少，为什么。10-seed 主实验共 200 个 P/Q 对（400 fits）：Q 的 rRMSE 改善 3.00%（95% CI [2.19%,3.79%]），10 个 seed 的 pooled 方向一致。必要的机制链只有三步：P 在同一无量纲坐标中采用固定参数误差规则；Q 在每个当前预测点按 B5 误差及其实际敏感度更新参数；真值点静态矩阵 M95 虽复现 Q 的局部二次项，但 24 单元消融中反而差于 P 与 Q，精确分解显示它改善了局部近似，却遗漏了有限参数误差带来的额外目标误差。因此 Q 不能被一套真值点静态权重替代；精确等价的矩阵必须随当前误差路径变化，而这种写法本质上仍是 Q。现有预测的事后工程审计进一步发现，Q 的均方收益来自误差再分配：高估和极端尾部下降、低估增加；只有在 \(x_{0.95}\) 用作保证寿命且高估代价更高时，才讨论其潜在工程含义。连续域、Q_direct、中点和 OOD 等后加实验原样保留为探索性归档，不进入当前论文主结论。Mentor 叙述必要性终审已通过，现为 `READY FOR USER REVIEW`；未投稿。入口见 Study/02 [`README.md`](Study/02-study-NN参数估计与分位点目标研究/README.md)、[`docs/研究说明.md`](Study/02-study-NN参数估计与分位点目标研究/docs/研究说明.md) 与 [`paper/论文初稿.md`](Study/02-study-NN参数估计与分位点目标研究/paper/论文初稿.md)。

**Study/01 当前态**：论文研究的问题是：在三参数 Weibull 小样本 MDM 估计中，偏移量 `delta` 如何影响有限样本估计风险，其合理取值受哪些因素决定，以及在总体参数未知时能否仅依据观测样本实现有效选择。图 1 以组合内重复抽样离散程度确认了正偏移量相对于无偏移判据的稳定性作用，后续主比较以固定 `delta=0.1` 为经验基准。正式方法为 Mean-Normalized-MLP：按样本量分别训练 MLP，对排序样本作 `X/mean(X)` 处理，再经训练折内逐位置 StandardScaler 预测 26 点损失曲线并选择偏移量。在同一 48,000 个测试样本上，固定随机种子 42 的 pooled J1=0.5846，较固定 `delta=0.1` 的 0.6304 改善 7.2740%（配对 repeat-block bootstrap 95% CI 6.9448%—7.6376%），三个参数的标准化 Bias 绝对值、SD 和 RMSE 均下降，失败率 0%；160 个设计单元中 125 个改善、35 个退化。另外两个预设种子仅用于初始化敏感性核查。未见 `beta`、WMLE/LSE 外部参照、三个可靠度寿命点和端到端尺度等变检查已完成，其中参数精度收益向可靠度寿命的传递有限。E10 表明较灵活的可观测样本规则仍能低于当前 MLP 的风险，但不是精确 Bayes 风险。E11 在 20 个预设参数单元的 2,000 个确认样本上进一步发现：抽样结果会移动 MDM 经验梯度曲线和搜索交点；固定 `delta=0.1` 时的标准化位置估计与 L6 偏移量的单元内相关中位数为 −0.765，20/20 个单元方向一致，且边界解只占 7.1%。E6 Dimensional-RAW（J1=0.5543）仅作固定尺度敏感性/历史对照。正式方法与机制证据见 `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E8_mean_normalized_selector/`、`E10_z_only_benchmark/` 和 `E11_profile_mechanism/`，当前正文与附录为 `manuscript/` 下 v1.3；v1.0—v1.2 已移入 `manuscript/shelve/`。真实案例仍后置。

**Study / Research 层级**：[`Study/README.md`](Study/README.md) 是 Study 层唯一入口，当前登记 Study01、Study02 两个具有独立小论文义务的项目；[`Research/README.md`](Research/README.md) 保存有界验证、支撑研究、独立研究和孵化方向，并定义升级为 Study 的门槛。原 Study015 已作为 `COMPLETE + SUPPORTING` 的“NN 输入表征与样本量机制”迁入 Research；旧 `docs/research` 与 Study01 内部 Research 已按 [`RELOCATION.json`](Research/RELOCATION.json) 原字节归位，不删除负面或被取代结果。

**Research/05 当前态**：传统方法风险地形 v1 已在 Study01 的 160 个设计单元、48,000 个共享样本上完成。primary candidate 为 MDM-0.1、WMLE、LSE；五折交叉评价的真参数 cell 选择相对最佳固定 MDM-0.1 将 pooled J1 从 0.630409 降至 0.592141，改善 6.07%，设计单元 bootstrap 95% 区间 [4.85%, 7.30%]。样本量单独没有选择收益，主要分界来自形状参数；该结果只证明存在机会空间，下一步进入可观测性 Research，尚不建立新 Study。详见 [`Research/05-传统估计方法横向比较/`](Research/05-传统估计方法横向比较/)。

| 大类 | 子方法 | 后端 |
|------|--------|------|
| 极大化适配法 | MLE, MMLE, MPS, WMLE | ✅ |
| 极小化适配法 | LSE, MDM | ✅ (WLSE/EIV→LSE 别名) |
| 线性回归法 | LRE | ✅ (BLRE/RRX/RRY→LRE 别名) |
| 矩方法 | MM, PWM | ✅ (LM/TLM→PWM 别名) |
| 灰色估计法 | Grey GM(1,1) | ✅ |
| 贝叶斯方法 | Bayesian | ✅ (Gibbs/MAP→Bayesian 别名) |
| 构造统计量法 | MVE, LSF | ❌ NOT_IMPLEMENTED |
| 人工智能方法 | PSO, SVR, ANN | ❌ NOT_IMPLEMENTED（见 AI 模块） |

**AI 方法层**：产品入口按 AI 介入位置分为过程量优化、直接估计和自适应选择；研究代号不作为用户界面名称。当前科学路线见 [`Study/README.md`](Study/README.md)、[`Study/研究规划v0.2.md`](Study/研究规划v0.2.md) 和 [`AI 当前路线图`](docs/AI辅助三参数威布尔参数估计重构当前路线图.md)。

| 模块 | 当前状态 |
|------|----------|
| 过程量优化 | MDM 已接入：预测 26 个候选偏移量的损失并选择离散最低点，再调用生产 MDM；详情页复用统一计算卡片，并与固定 `δ=0.10` 成对展示预测损失、参数结果和带符号差异 |
| 直接估计 | 既有端到端参数估计原型保留，后续按当前证据边界继续整理 |
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
| `Study/研究规划v0.2.md` | 查看博士总体问题、研究空间、后续方向与综合逻辑 |

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
