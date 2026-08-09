# Weibull Analysis Platform

**威布尔参数估计方法的研究与实践平台**

> 本文件是项目唯一权威入口。无论是人类开发者、Codex、Hermes、OpenCode、Claude Code，还是其他 AI coding agent，都从这里开始，再按任务需要渐进式阅读后续文档。

集计算、对比、验证、优化于一体，并以案例数据库和学术文献库作为数据支撑与理论依据，为可靠性工程师和研究者提供从方法选型到结果验证的完整工作流。

**线上地址**: [weibull.work](https://weibull.work)

---

## 当前状态快照

> **快照日期**: 2026-08-09 · 以本节为当前状态权威；各分文档的进度表为开发追踪器。

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

**Study/02 当前态**：主问题为“在其他条件逐 fit 配对时，把训练目标从参数等权精度 `P_equal` 转向目标可靠度寿命点精度 `Q_param`，能把 \(x_R\)（\(R(x_R)=0.95\)）的 rRMSE 改善多少”。S1–S4 与 S5A 预审结果保留，但 **2026-08-09 模拟审稿给出 Major Revision，论文不再处于 APPROVE 状态**。当前正在执行 S5B：把固定网格主实验从 3 扩为预先冻结的 10 个训练 seed，新增 Study01 同参数边界的连续域内实验、同骨干 `Q_direct` 基线、Study01 MDM-Default 经典参照，并给相对 rRMSE 改善做 crossed fold×seed 配对区间。原 120 fits、中点和 gamma 层级留出证据均不覆盖；四种合同分开报告。协议与追踪见 Study/02 `17-PQ-S5B审稿大修协议与追踪.md`；未投稿、未合并 main。

**Study/01 当前态**：论文主线已收敛为“三参数 Weibull MDM 框架内偏移量 `delta` 是否有更合适的选择，以及怎样根据当前样本实现选择”。正式方法为 Dimensional-RAW-MLP：按样本量分别训练 MLP，以排序原始样本预测 26 点损失曲线并选择偏移量。在 160 组合主设计域（`eta=1000`，`n∈{7,10,15,20}`）内，pooled J1=0.5543，较固定 `delta=0.1` 改善 12.08%，失败率为 0%；结论限于已训练样本量以及训练单位和尺度范围。写作前支撑验证已补齐：未见 `beta` 留出（B1，8 折，pooled J1=0.5418、改善 14.06%、失败率 0%）、WMLE/LSE 同条件外部参照（B2，WMLE 0.7288/LSE 0.8725，WMLE 1 例未收敛计入）、`x_0.90/x_0.95/x_0.99` 工程分位点派生（B3，传递有限，WMLE 尾部分位点 RMSE 最低）；真实案例后置。per-n specialist 不定义未训练 `n` 的直接应用；旧特征路线、Normalized-RAW、旧 P2/P4/分位点和 NIST 结果已降为历史、候选或 Research 证据。Study01 活动区已整理为论文所需 `README`、`00`–`04`、证据/代码索引、`artifacts/formal/E6_dimensional_raw/paper/`（图表索引）、`Research/` 与 `archive/`；外部中文学术源稿 v0.3 是唯一活动正文。

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

**AI 方法模块**：

| 模块 | 当前状态 |
|------|----------|
| M1 关系建立 | ⚠️ 旧原型存在（R1/R2 两条路线），当前待重构 |
| M3 直接估计 | 原型已实现（8 种预处理方案、泛化验证） |
| M2 优化求解 | 待开发 |
| M4 智能推荐 | 待规划 |

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
| `docs/AI辅助三参数威布尔参数估计重构当前路线图.md` | 接手 AI 重构或继续研究 03 |
| `/help/metrics` | 使用或新增评价指标时（渲染视图；规范源为 `metrics-spec.ts`，可执行实现为 `src/lib/metrics.ts` + `python/studies/common/metrics.py`） |
| `/help/charts` | 使用或新增图表/表格范式时（渲染视图；规范源为 `charts-spec.ts`，实例源为 `chart-registry.ts`） |
| `03-维护.md` | 部署或运维 |
| `04-目标与待办.md` | 规划功能 |
| `07-用户手册.md` | 编写或核对用户手册内容 |
| `08-更新日志.md` | 查看版本更新记录 |

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
