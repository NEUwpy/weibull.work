# AI 辅助三参数威布尔参数估计重构前因后果

> 用途：与 `AI辅助三参数威布尔参数估计重构与实验设计总纲.md` 一起发送给外部审稿型 chatbox。
> 目标：帮助审稿人快速理解为什么要重构、旧工作为什么不能直接沿用、新总纲希望解决什么问题，以及需要重点把关哪些地方。

---

## 1. 项目原始背景

本项目是一个三参数威布尔分布参数估计与分析平台，研究对象是可靠性工程中的寿命数据建模和参数估计。

旧平台已经具备一定基础：

- 多种传统威布尔参数估计方法；
- 蒙特卡洛模拟与适用范围分析；
- 方法页面和可视化展示；
- 初步 AI 参数估计模块；
- 若干训练结果、模型文件和页面展示。

这些工作说明项目已经不是从零开始，而是在一个已有研究平台上继续推进。

### 1.1 旧平台代码现状清单

以下是对旧平台代码的系统梳理，作为重构的起点依据。

#### 传统估计方法（`python/methods/`）

已实现 11 个方法，统一继承 `WeibullBase` 基类，通过 `registry.py` 注册：

| 方法 | 文件 | 说明 | gamma 估计 |
|------|------|------|------------|
| MLE | `mle.py` | 极大似然估计 | 有 |
| MMLE | `mmle.py` | 修正极大似然估计 | 有 |
| LSE | `lse.py` | 最小二乘估计 | 有 |
| LRE | `lre.py` | 线性回归估计 | 有 |
| MPS | `mps.py` | 最大概率积估计 | 有 |
| MM | `mm.py` | 矩估计 | 有 |
| PWM | `pwm.py` | 概率权重矩估计 | 有 |
| WMLE | `wmle.py` | 加权极大似然估计 | 有 |
| MDM | `mdm.py` | 最小差异法 | 有 |
| GreyGM11 | `grey_gm11.py` | 灰色 GM(1,1) 模型 | 有 |
| Bayesian | `bayesian.py` | 贝叶斯估计 | 有 |

所有方法通过 `resolve_method()` 统一调用，返回 `MethodResult(beta, eta, gamma, r_squared, converged)`。

另有 `NOT_IMPLEMENTED` 集合标记了前端已定义但后端未实现的方法：`construct_stat, mve, lsf, ai, pso, svr, ann`。

#### AI 原型模块

**M3 直接估计（`python/studies/direct_estimation/`）**

- `generate_training_data.py`：蒙特卡洛生成训练数据
  - 参数空间：`β∈{0.5,1,2,3,5}, η∈{100,500,1000,3000,5000}, γ∈{50,100,200,1000}, n∈{5,7,10,15}`
  - 每组 500 次 MC，共 200,000 个样本
  - 样本生成：`gamma + eta * (-ln(1-u))^(1/beta)`
- `train_model.py`：MLP 训练脚本
  - 架构：`Linear(n,128)→ReLU→Linear(128,64)→ReLU→Linear(64,32)→ReLU→Linear(32,3)`
  - 损失函数：相对 MSE = `((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/γ)²`
  - 按 n 分别训练独立模型
  - 支持 8 种输入预处理方案（A1/A2/A3/B1/B2/C1/C2/C3）
- `evaluate_generalization.py`：泛化评估脚本，按 ig/ip/ex 三种验证类型分组
- `generate_mdm_baseline.py`：用 MDM(δ=0.5) 生成对比基准

已产出模型文件（`python/models/direct_estimation/`）：按 n5/n7/n10/n15 和预处理方案命名的 `.pth` + `_metrics.json`。

**M1 偏移量预测（`python/studies/mdm_delta/`）**

- `train_model.py`：两种 MLP 模型
  - N₂（路线 1）：样本 → 最优 δ，按 n 分别训练
  - N₁（路线 2）：`(β,η,γ)` 真值 → 最优 δ，训练一个公共模型
  - N₂ 架构：`Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid`
- `generate_training_data.py`：对每个样本遍历 δ 网格，找使相对 MSE 最小的 δ*
- 辅助研究脚本 10+ 个（`study_*.py, diagnose_*.py, plot_*.py`）

已产出模型文件（`python/models/mdm_delta/`）：n5/n7/n10/n15/n20 的 `_model.pth` + `_metrics.json`，以及 `delta_from_params.pth`。

#### 蒙特卡洛脚本（`python/studies/`）

每个方法目录下各有独立的 `simulate.py`：

| 方法 | 脚本 | 参数来源 | 输出格式 |
|------|------|----------|----------|
| MDM | `studies/mdm/simulate.py` | `public/studies/mdm/{id}/config.md` | 分片 CSV + index.json + data.csv |
| MLE | `studies/mle/simulate.py` | `public/studies/mle/{id}/config.md` | 分片 CSV + index.json + data.csv |
| WMLE | `studies/wmle/simulate.py` | `public/studies/wmle/{id}/config.md` | 分片 CSV + index.json + data.csv |

三个 simulate.py 结构高度相似：都从 config.md 读配置、分片生成、增量更新、合并导出。核心函数 `parse_config, get_param_values, generate_chunk_filename, generate_weibull_sample, load_index, save_index` 几乎完全重复。

#### 指标计算现状

没有统一的指标计算模块。指标计算逻辑分散在：

- `train_model.py` 中的 `evaluate_model()`：计算 MSE、MAE、RMSE、MRE（按参数分别计算）
- `mdm_delta/` 下 7+ 个文件各自重复定义 `compute_relative_mse()`
- `simulate.py` 中内联计算 bias（`est - true`）和 r_squared
- `base.py` 中的 `_calculate_r2()`：仅用于拟合优度

**没有** NE、NQE_R、Failure Rate、Outlier Rate、Time 等总纲要求的指标。

#### 前端可视化

- `src/components/methods/`：mdm、mle、wmle 三个方法的前端组件
- `src/components/shared/charts/`：BoxPlotChart、HeatmapChart、ContourChart、DensityChart、ConvergenceChart 等通用图表
- `src/lib/`：ai-data.ts、weibull.ts 等工具函数
- 前端指标引用在 `src/lib/config.ts` 和 `src/lib/ai-data.ts` 中

#### 样本生成逻辑

样本生成函数 `generate_weibull_sample()` 在以下位置独立定义：

- `studies/mdm/simulate.py`
- `studies/mle/simulate.py`
- `studies/wmle/simulate.py`
- `studies/direct_estimation/generate_training_data.py`

公式相同：`gamma + eta * (-ln(1-u))^(1/beta)`，但随机种子策略不统一。

---

## 2. 为什么需要重构

旧平台的问题不是“完全不能用”，而是“作为正式研究体系不够可信”。

主要问题有五类。

### 2.1 AI 模块边界不清

旧 AI 模块曾粗略分为 M1、M2、M3，但内部逻辑混杂。

例如 M1 中既有过程量预测，又有类似误差修正的思路。不同模型到底是在：

- 优化传统方法过程；
- 修正传统方法偏差；
- 直接估计参数；
- 还是用智能优化算法改进求解；

并没有清晰分开。

具体代码证据：

- `studies/direct_estimation/` 是 M3 直接估计（样本 → 参数），但其中的 `generate_mdm_baseline.py` 又在用 MDM 做基准对比，混合了传统方法逻辑。
- `studies/mdm_delta/` 是 M1 过程量预测（样本 → MDM 偏移量 δ），但其中 10+ 个辅助研究脚本（`study_robustness.py, study_edge_cases.py, diagnose_overfit.py` 等）混杂了误差分析、曲线性质研究、泛化评估等不同层次的目标。
- `registry.py` 中 `NOT_IMPLEMENTED` 标记了 `ai, pso, svr, ann`，但这些方法的前端页面可能已经存在，前后端状态不一致。
- 没有 M2（误差修正）的独立实现，也没有 M4（智能优化）的独立实现。

这会导致后续实验结果难以解释：即使某个 AI 模型表现较好，也难以说明它到底改善了什么。

### 2.2 评价指标不统一

旧平台中传统方法、AI 方法、不同实验脚本和页面展示使用过不同指标。

常见问题包括：

- 有的地方看 MSE；
- 有的地方看 MAE 或 MRE；
- 有的地方使用综合误差；
- `beta`、`eta`、`gamma` 的量纲和数值范围不同，却可能被直接混合比较；
- `gamma` 可能为 0，普通相对误差会失效；
- 失败样本和异常样本没有形成统一口径。

具体代码证据：

- `compute_relative_mse()` 在 `mdm_delta/` 下至少 7 个文件中重复定义，公式为 `((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/γ)²`，其中 gamma 用 gamma 自身归一化——当 gamma=0 时会除零。
- `train_model.py` 中的 `relative_mse_loss()` 对 gamma 做了 `1e-6` 的防除零处理，但这引入了数值不稳定。
- `simulate.py` 中只计算单参数 bias（`est - true`）和 r_squared，没有综合误差指标。
- 没有统一的 NE、NQE_R、Failure Rate、Outlier Rate 计算。

结果是：不同方法之间无法公平横向比较。

### 2.3 工程应用目标没有充分体现

三参数威布尔分布参数估计在工程中常常不是直接使用 `beta, eta, gamma`，而是使用给定可靠度水平下的寿命分位点。

旧实验更偏向参数本身误差，但对于可靠度寿命分位点，例如：

- 99.5% 可靠度寿命；
- 99.0% 可靠度寿命；
- 95.0% 可靠度寿命；
- 90.0% 可靠度寿命；

没有形成同等重要的系统评价视角。

因此可能出现一种情况：某个方法参数误差不是最小，但关键工程分位点估计更好。旧评价体系难以解释这种现象。

### 2.4 AI 损失函数缺少系统验证

旧 AI 模型训练时使用的 loss 没有经过系统对比。

不清楚：

- 原始参数 MSE 是否合适；
- 标准化参数 MSE 是否更合理；
- 归一化综合误差是否更适合三参数估计；
- 分位点导向 loss 是否更贴近工程应用；
- 混合 loss 是否能兼顾参数精度和分位点精度。

具体代码证据：

- M3 直接估计模型（`train_model.py`）实际训练使用的是 `normalized_mse_loss()`（对归一化后的 y 做 MSE），而不是文件头注释中声称的 `relative_mse_loss()`。文档描述与代码行为不一致。
- `relative_mse_loss()` 中 gamma 用 gamma 自身归一化（`/γ`），与总纲定义的 NE（gamma 用 eta 归一化 `/η`）公式不同。当 gamma=0 时旧 loss 会除零或产生极大值，总纲的 NE 设计正是为了避免这个问题。
- M1 偏移量预测模型的训练目标是使 MDM 的相对 MSE 最小，但这个相对 MSE 本身也有上述 gamma 归一化问题。
- 没有任何实验比较过不同 loss 对参数精度和分位点精度的影响。

因此旧模型即使已有结果，也不能直接说明”这种训练目标是合理的”。

### 2.5 蒙特卡洛流程重复

旧平台中每新增一个方法或实验，容易重新写一套：

- 参数空间遍历；
- 样本生成；
- 重复模拟；
- 方法调用；
- 结果保存；
- 指标统计。

具体代码证据：

- `studies/mdm/simulate.py`、`studies/mle/simulate.py`、`studies/wmle/simulate.py` 三个脚本结构高度相似，核心函数（`parse_config, get_param_values, generate_chunk_filename, generate_weibull_sample, load_index, save_index`）几乎完全重复。
- `generate_weibull_sample()` 在 4 个不同位置独立定义，公式相同但随机种子策略不统一。
- 参数空间定义方式不统一：蒙特卡洛脚本从 `config.md` 读取，AI 训练数据脚本硬编码在代码中。
- 输出 CSV 列名不统一：simulate.py 输出 `est_beta, est_eta, est_gamma, bias_beta, ...`；AI 训练数据输出 `n, beta, eta, gamma, t1, t2, ...`。
- 失败记录不统一：simulate.py 写 `NaN`；train_model.py 跳过失败样本。
- 没有 `studies/common/` 共享目录，各方法独立维护各自的脚本。

这会带来几个问题：

- 字段不统一；
- 失败记录不统一；
- 统计口径不统一；
- 传统方法和 AI 方法可能不在同一测试集上比较；
- 后续扩展越来越难维护。

---

## 3. 旧结果的定位

旧 M1/M3 原型、模型文件、训练结果和页面展示不应被简单删除。

它们仍有价值：

- 说明项目曾经探索过 AI 参数估计；
- 说明哪些方向有潜力；
- 说明为什么需要统一指标和蒙特卡洛框架；
- 可以作为历史原型资料。

但旧结果不应继续作为正式研究结论。

原因是：

- 旧指标口径不统一；
- 旧训练 loss 没有系统验证；
- 旧训练集、验证集、测试集和传统基准没有形成统一 benchmark；
- 失败样本和异常样本处理不统一；
- 传统方法与 AI 方法未必在完全同一套样本、同一套指标下比较。

### 3.1 旧可复用资产清单

以下旧代码在重构中应优先**包装复用**，而不是重写：

| 资产 | 位置 | 复用方式 |
|------|------|----------|
| 11 个传统方法实现 | `python/methods/*.py` | 包装接入统一蒙特卡洛框架 |
| WeibullBase 基类 | `python/base.py` | 保留，提供中位秩和 R² 计算 |
| MethodResult 数据类 | `python/base.py` | 保留或扩展为统一结果结构 |
| 方法注册表 | `python/methods/registry.py` | 扩展以支持新方法接入 |
| 样本生成公式 | 各 `simulate.py` | 提取为共享函数，统一种子策略 |
| config.md 配置格式 | `public/studies/*/` | 保留作为前端配置来源 |
| 前端通用图表 | `src/components/shared/charts/` | 直接复用 |
| 前端方法组件 | `src/components/methods/mdm,mle,wmle/` | 保留，后续扩展 |

### 3.2 旧仅作历史参考的资产

以下旧代码/结果只能作为历史原型，不应作为正式研究依据：

| 资产 | 位置 | 原因 |
|------|------|------|
| M3 直接估计模型 | `python/models/direct_estimation/*.pth` | loss 有 gamma 除零问题，参数空间与总纲不一致 |
| M1 偏移量预测模型 | `python/models/mdm_delta/*.pth` | 训练目标的相对 MSE 有同样问题 |
| 旧训练数据 | `studies/direct_estimation/data/` | 参数空间为旧设定，不含总纲要求的 gamma/eta 比例 |
| 旧泛化评估结果 | `evaluate_generalization.py` 产出 | 基于旧指标体系 |
| 旧蒙特卡洛结果 | `public/studies/*/` 下的 data.csv | 指标不含 NE、分位点误差、Failure/Outlier Rate |
| mdm_delta 辅助研究脚本 | `studies/mdm_delta/study_*.py` | 10+ 个探索性脚本，逻辑混杂 |

### 3.3 旧平台与总纲的关键差异

| 维度 | 旧平台 | 总纲要求 |
|------|--------|----------|
| gamma 归一化 | 用 gamma 自身（`/γ`），gamma=0 时除零 | 用 eta（`/η`），避免除零 |
| 参数空间 | gamma 用绝对值（50,100,200,1000） | gamma/eta 用比例（0, 0.05, 0.10, 0.20） |
| 评价指标 | 单参数 MAE/MRE + r_squared | NE + 分位点 NQE_R + Failure Rate + Outlier Rate |
| 状态判定 | converged True/False 或 NaN | success/failure/outlier 三态 |
| 样本共享 | 各脚本独立生成，种子不统一 | 给定参数组合+样本量+编号，必须可复现 |
| 分位点评价 | 无 | R∈{0.995, 0.990, 0.950, 0.900} 的寿命分位点误差 |

所以当前判断是：

```text
旧结果保留为历史原型，
新研究结论必须在统一评价体系和统一蒙特卡洛框架下重新产生。
```

---

## 4. 为什么整理文档

在前期讨论中，已经生成过多份文档，包括：

- 总纲；
- 简明路线图；
- 指标方案；
- 蒙特卡洛方案；
- 审查意见；
- AI 接手提示词；
- 研究路线；
- 工程路线；
- 进度控制文档。

这些文档在探索阶段有帮助，但后来出现了新的问题：

1. 文档数量过多；
2. 多份文档之间存在重复；
3. 有些文档过早规定变量名、函数名和文件名；
4. 容易让后续 AI Coding 工具机械执行，而不是根据真实代码结构灵活落地；
5. 对外部审稿人来说，主线不够清楚。

因此已经将旧草案、旧审查稿和旧交接文档归档到 `docs/history/`。

当前希望保留一份新的主文档：

```text
AI辅助三参数威布尔参数估计重构与实验设计总纲.md
```

它不是代码设计文档，而是研究重构总纲。

---

## 5. 新总纲的核心意图

新总纲想解决的是“研究体系怎么重新搭起来”，而不是提前规定代码怎么写。

它的核心意图包括：

### 5.1 重新划分 AI 模块

将 AI 模块分为：

- M1：AI 预测过程量；
- M2：AI 误差修正 / 偏差纠正；
- M3：AI 直接估计；
- M4：智能优化算法。

这样每类方法的研究问题更清楚。

### 5.2 建立双视角评价体系

评价体系必须同时包含：

1. 参数估计视角；
2. 工程应用分位点视角。

参数视角回答：

```text
beta、eta、gamma 估得准不准？
```

分位点视角回答：

```text
给定可靠度水平下的寿命估计准不准？
```

两者不能互相替代。

### 5.3 用损失函数实验支撑后续训练

正式训练复杂 AI 模块前，应先用一个简单 M3 直接估计模型比较不同 loss。

候选 loss 包括：

- 原始参数 MSE；
- 标准化参数 MSE；
- NE-Loss；
- Huber Loss；
- Quantile-Loss；
- Hybrid-Loss。

这个实验的目标不是追求模型最强，而是判断不同 loss 对参数精度和工程分位点精度的影响。

### 5.4 建立统一蒙特卡洛调度框架

后续传统方法、M1、M2、M3、M4 都应接入同一套蒙特卡洛流程。

统一框架应负责：

- 参数空间遍历；
- 样本生成；
- 重复模拟；
- 方法调用；
- 结果保存；
- 指标统计。

目标是避免每新增一个方法就重新写一套流程。

### 5.5 保留分类问题作为 M3 子方向

导师提出可以把离散参数空间下的参数估计转为分类问题。

新总纲没有把分类单独升为主模块，而是放入 M3 的子方向：

- 参数组合分类；
- 分参数分类；
- 分类辅助回归。

其中更推荐分类辅助回归，因为它保留了连续参数估计能力。

---

## 6. 当前希望审稿人重点把关的问题

请审稿人重点看以下问题。

### 6.1 模块划分是否合理

请判断 M1、M2、M3、M4 的划分是否清晰，是否符合三参数威布尔参数估计研究逻辑。

重点关注：

- M1 预测过程量是否和 M2 误差修正区分清楚；
- M3 直接估计是否应包含分类扩展；
- M4 智能优化算法是否应作为独立模块；
- 是否存在遗漏的重要 AI 方法类型。

### 6.2 评价体系是否足够

请判断参数视角和工程分位点视角是否都被合理保留。

重点关注：

- NE 是否适合作为参数视角核心综合指标；
- `gamma` 使用 `eta` 归一化是否合理；
- 分位点指标是否能反映工程应用价值；
- 是否还需要加入其他必要指标；
- 是否存在指标过多、难以执行的问题。

### 6.3 损失函数验证实验是否合理

请判断前置 loss 对比实验是否必要且设计合理。

重点关注：

- 是否应该先用简单 M3 模型验证 loss；
- 候选 loss 是否覆盖参数导向、分位点导向和混合导向；
- Quantile-Loss 和 Hybrid-Loss 的设计方向是否合理；
- 选择标准是否应优先看 NE 和分位点误差；
- 是否还需要单独关注异常估计率和失败率。

### 6.4 蒙特卡洛框架是否过度或不足

请判断统一蒙特卡洛框架的抽象程度是否合适。

重点关注：

- 是否足以避免重复写仿真流程；
- 是否给后续 AI Coding 工具留下足够实现自由；
- 是否还需要提前规定更多结果字段；
- 是否会因为过度抽象而增加实现负担。

### 6.5 实验参数空间是否合适

新总纲建议第一版参数空间为：

```text
beta ∈ {0.8, 1.2, 1.5, 2.0, 3.0, 5.0}
eta ∈ {50, 100, 200}
gamma / eta ∈ {0, 0.05, 0.10, 0.20}
n ∈ {10, 20, 30, 50, 100}
```

请判断：

- 这个空间是否覆盖足够的分布形态；
- 是否过大或过小；
- 是否适合作为第一版统一实验空间；
- 是否需要增加外推测试或插值测试；
- `gamma/eta` 的设定是否合理。

### 6.6 文档层级是否合适

请判断新总纲是否达到了“高层清晰、不过度规定实现细节”的目标。

重点关注：

- 是否足够指导后续 AI Coding；
- 是否仍然过于复杂；
- 是否有不必要的工程细节；
- 是否有关键研究设计没有说清楚。

---

## 7. 当前不希望审稿人做的事情

本次审稿阶段暂时不需要：

- 写具体代码；
- 设计完整类结构；
- 规定所有文件名和函数名；
- 训练模型；
- 跑蒙特卡洛实验；
- 直接比较旧 AI 结果；
- 继续扩写大量分散文档。

希望审稿人做的是：

```text
像研究方案审稿人一样，判断这个重构总纲是否逻辑清楚、指标合理、实验顺序合理、边界合适。
```

---

## 8. 当前最需要的审稿输出

建议审稿人输出：

1. 总体评价；
2. 认为最合理的部分；
3. 认为最需要修改的部分；
4. 是否同意 M1/M2/M3/M4 划分；
5. 是否同意参数视角 + 分位点视角双评价；
6. 是否同意先做 loss 对比实验；
7. 是否同意统一蒙特卡洛框架的抽象层级；
8. 对参数空间的修改建议；
9. 对总纲文档的精简或补充建议。

如果审稿人认为当前方案过度复杂，也请明确指出哪些部分应该删减。

---

## 9. 一句话总结

本次重构的核心不是“再训练几个 AI 模型”，而是先建立一个可信研究体系：

```text
清晰模块划分
 + 双视角统一评价指标
 + 经过验证的训练 loss
 + 统一蒙特卡洛调度框架
 + 可横向比较的传统方法与 AI 方法结果
```

只有这样，后续 AI 模型结果才适合作为组会或论文中的正式研究结论。
