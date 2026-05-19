# AI 辅助参数估计工程路线

> 日期：2026-05-19
> 定位：工程侧规划文档，说明如何把研究总目标落成指标、代码、训练、可视化和结果。
> 总纲入口：`docs/AI辅助参数估计模块重做总纲.md`
> 研究承接：`docs/ai-research/research-roadmap.md`

---

## 1. 工程总目标

工程目标不是继续堆模型或页面，而是建立一条可信证据链：

```text
研究目标
↓
系统级指标规范
↓
benchmark 数据协议
↓
公共指标函数
↓
传统基准统一输出
↓
M1/M3 全量重训
↓
统一指标汇总
↓
研究型可视化
↓
可复现结论
```

只有这条链路跑通后，AI 模块的新结果才可以用于组会和论文讨论。

---

## 2. 工程推进原则

### 2.1 研究目标先行

工程实现必须服务研究目标。

不能先写训练脚本，再回头解释模型在研究什么；必须先知道：

- 训练目标是什么；
- 损失函数对应什么研究指标；
- 测试集验证什么泛化能力；
- 可视化要回答什么问题。

### 2.2 指标先于训练

所有训练和评估前，必须先统一指标。

指标统一包括：

- 指标名称。
- 数学公式。
- 输入字段。
- 失败样本处理。
- 聚合方式。
- 前后端公共函数。
- 页面解释文案。

### 2.3 Benchmark 先于模型

所有方法必须在统一 benchmark 上训练或测试。

禁止：

- M1/M3 各自生成测试集后横向比较。
- 拿旧数据和新数据混合比较。
- 只跑成功样本，不保留失败样本。
- 用训练集或验证集结果当最终结论。

### 2.4 全量重训而不是局部修补

旧 M1/M3 模型因指标和损失函数体系不清，不能继续作为正式研究模型。

工程上必须按新协议全量重训：

- M1-A：AI 优化传统方法过程量。
- M1-B：AI 纠正传统方法偏差。
- M3：AI 直接求解。

M2 暂不实现。

---

## 3. 系统级指标工程

指标规范页面是整个系统的指标准绳。

落地位置：

- 指标规范页面：`/help/metrics`。
- 图表规范页面：`/help/charts`。
- 后端公共指标函数：`python/studies/common/metrics.py`。
- 前端公共指标函数：`src/lib/metrics.ts`。

### 3.1 输入指标

用于描述样本、参数空间和实验条件。

必须覆盖：

```text
sample_id
seed
n
beta_true
eta_true
gamma_true
validation_type
sample_statistics
```

### 3.2 结果指标

用于描述方法输出。

必须覆盖：

```text
method
scheme
beta_hat
eta_hat
gamma_hat
delta_hat
B1_life_hat
B5_life_hat
B10_life_hat
status
failure_reason
runtime_ms
```

### 3.3 统计指标

用于评价方法表现。

必须覆盖：

```text
mae_beta
mae_eta
mae_gamma
mre_beta
mre_eta
scaled_gamma_error
B1_life_mae
B5_life_mae
B10_life_mae
B1_life_mre
B5_life_mre
B10_life_mre
success_rate
failure_rate
mean_runtime_ms
failure_reason_distribution
```

禁止：

```text
mre_gamma = abs(gamma_hat - gamma_true) / abs(gamma_true)
```

作为主指标。

---

## 4. 工程模块划分

### 4.1 指标公共库

后端：

```text
python/studies/common/metrics.py
```

前端：

```text
src/lib/metrics.ts
```

必须实现：

- `mae`
- `mre`
- `scaled_gamma_error`
- `weibull_quantile`
- `b_life_errors`
- `success_rate`
- `failure_rate`
- `runtime_summary`

必须测试：

- γ=0 时不输出普通 γ-MRE。
- B1/B5/B10 公式正确。
- 失败样本参与成功率分母。
- 参数误差只统计成功样本。

### 4.2 Benchmark 数据生成

必须生成：

- 训练集。
- 验证集。
- 组内测试集 `ig`。
- 插值测试集 `ip`。
- 外推测试集 `ex`。

每条样本必须有：

```text
sample_id
seed
n
beta_true
eta_true
gamma_true
t1...tn
split / validation_type
```

### 4.3 传统基准统一输出

短期至少包括：

- MDM。
- MLE。

统一输出字段：

```text
sample_id
method
scheme
n
validation_type
beta_hat
eta_hat
gamma_hat
status
failure_reason
runtime_ms
```

### 4.4 M1-A 数据与训练

工程任务：

- 生成 δ 搜索结果。
- 定义 δ 标签质量。
- 训练 AI 预测 δ。
- 输出固定 δ、搜索 δ、AI δ 的同集对比。

必须先确定：

```text
delta_search_min
delta_search_max
delta_search_strategy
best_delta_selection_metric
boundary_rule
label_quality_flag
```

### 4.5 M1-B 数据与训练

工程任务：

- 对传统方法输出结果。
- 生成残差或修正标签。
- 训练 AI 修正模型。
- 对比修正前后参数层和应用层指标。

必须先确定：

```text
traditional_method
correction_target
residual_formula
target_transform
invalid_baseline_rule
```

### 4.6 M3 数据与训练

工程任务：

- 重新定义输入方案。
- 重新定义目标变换。
- 重新定义损失函数。
- 全量重训所有纳入研究的 M3 方案。

必须先确定：

```text
input_representation
target_transform
output_constraint
loss_function
invalid_prediction_rule
```

---

## 5. 可视化工程

可视化必须围绕研究问题设计。

### 5.1 数据来源说明

所有新 AI 页面必须展示或能追溯：

- Benchmark 版本。
- 参数空间。
- 样本量。
- MC 次数。
- 训练/验证/测试划分。
- 指标定义。
- 失败样本口径。

### 5.2 必备图表

参数层：

- 真实值 vs 估计值散点图。
- 参数误差箱型图。
- 参数空间热力图。

应用层：

- B1/B5/B10 误差图。
- 高可靠度寿命误差曲线。

方法层：

- 成功率柱状图。
- 失败原因分布图。
- 运行时间对比图。

泛化层：

- `ig/ip/ex` 分组对比图。
- 训练范围内外表现差异图。

### 5.3 图表复用

新增图表前必须先查：

- `/help/charts`
- `src/components/shared/charts`
- 现有 AI 图表组件

已有图表能复用时，不新建相似图表。

---

## 6. 工程阶段

### E0：文档和目标对齐

产物：

- 总纲。
- 研究路线。
- 工程路线。
- 执行手册。
- Benchmark 规范。

### E1：系统级指标固化

产物：

- `/help/metrics` 更新。
- 指标字段清单。
- 前后端公共指标函数接口。
- 指标测试用例。

### E2：Benchmark 和数据管线

产物：

- 统一训练集。
- 统一验证集。
- `ig/ip/ex` 测试集。
- 数据生成脚本。
- 数据校验脚本。

### E3：传统基准同集输出

产物：

- MDM 预测结果。
- MLE 预测结果。
- 失败原因统计。
- 运行时间统计。

### E4：M1/M3 全量重训

产物：

- M1-A 新模型。
- M1-B 新模型。
- M3 新模型。
- 统一预测结果 CSV。
- 模型训练记录。

### E5：指标汇总和可视化

产物：

- 指标汇总 CSV/JSON。
- 前端研究结果页面。
- 旧结果与新结果区分说明。
- 组会图表。

---

## 7. 工程验收标准

工程成果只有满足以下条件，才算进入可信研究阶段：

1. 指标规范页面已更新。
2. 前后端公共指标函数已实现并测试。
3. Benchmark 数据可追溯到参数空间和随机种子。
4. 失败样本被保留并计入成功率分母。
5. MDM/MLE 与 AI 方法使用同一测试集。
6. M1/M3 已按新协议全量重训。
7. 指标汇总能追溯到预测结果。
8. 页面能说明数据来源、指标定义、失败口径和适用范围。

