# AI 辅助参数估计指标审计交接说明

> 用途：复制给另一个 chatbox 类 AI，让它理解前因后果、方法目标，并审查当前指标方案是否合理。
> 当前审计对象：`docs/AI辅助参数估计指标定义方案草案.md`

---

## 1. 项目背景

我正在做一个 Weibull Analysis Platform，中文名为威布尔分析平台。

项目技术栈：

```text
前端：Next.js 14 + TypeScript + Tailwind CSS
后端：Python + FastAPI + SciPy / NumPy
研究对象：可靠性工程中的 Weibull 参数估计与数据分析
```

平台原本已经做了一些传统 Weibull 参数估计方法，也做了 AI 模块原型。

目前 AI 模块主要涉及：

```text
M1：AI 辅助传统方法
M2：智能优化算法辅助传统方法求解
M3：AI 直接求解 Weibull 参数
```

但现在发现原来的 AI 模块有较大问题：指标、训练目标、损失函数、测试集、传统基准、图表展示都没有完全统一，因此旧结果不能作为可信研究结论。

---

## 2. 为什么要重做 AI 模块

旧 M1/M3 模型虽然已有训练结果和页面展示，但存在以下问题：

```text
1. 不同页面或脚本使用的指标口径不完全一致。
2. 损失函数没有明确对应研究目标。
3. 训练集、验证集、测试集、组内测试、插值测试、外推测试没有形成统一 benchmark。
4. AI 方法和传统方法没有全部在同一测试集、同一指标下公平比较。
5. 旧结果中有些改善率看起来很高，但不能证明在统一研究体系下仍然成立。
6. γ 参数如果直接使用普通 MRE，在 γ=0 或接近 0 时会爆炸。
7. 参数误差小不一定代表可靠寿命分位点误差小。
```

因此，现在的判断是：

```text
旧 M1/M3 结果全部降级为历史原型。
旧模型、旧图表、旧数据可以保留作历史对照。
但不能作为正式研究结论。
新指标、新 benchmark、新损失函数确定后，M1/M3 需要全部重新训练。
```

---

## 3. 新 AI 模块结构

### 3.1 M1：AI 辅助传统方法

M1 不是单一模型，而是一类“传统方法 + AI 增强”的研究路线。

M1 分为两个子方向。

#### M1-A：AI 优化传统方法过程量

典型例子：

```text
MDM 方法中，AI 预测或优化偏移量 δ。
```

研究目标：

```text
AI 是否能学习传统方法内部过程量的选择规律？
例如 MDM 的 δ 是否可以由 AI 自适应选择？
AI 选择 δ 后，MDM 的参数估计和 B1/B5/B10 寿命估计是否改善？
```

注意：

```text
M1-A 的最终目标不是 δ 本身预测得多准，
而是 AI δ 代入传统方法后，传统方法结果是否更好。
```

#### M1-B：AI 纠正传统方法偏差

基本思想：

```text
传统方法先估计 Weibull 参数。
AI 再学习传统方法估计结果与真实值之间的系统偏差。
最后用 AI 修正传统方法输出。
```

统一形式：

```text
sample -> traditional estimator -> theta_base
AI input: sample features + theta_base
AI output: correction / residual
theta_ai = theta_base + correction
```

其中：

```text
theta = (beta, eta, gamma)
```

研究目标：

```text
AI 是否能修正传统方法在小样本、极端参数区间下的系统偏差？
修正后是参数更准，还是 B1/B5/B10 可靠寿命更准？
修正是否会增加异常输出或失败风险？
```

### 3.2 M2：智能优化算法辅助传统方法求解

M2 暂时不做，只保留为中长期方向。

可能包括：

```text
PSO / DE / GA 辅助 MLE 或 MDM 求解
AI 预测优化初值
AI 选择优化器
AI 缩小搜索范围
```

当前审计重点不是 M2。

### 3.3 M3：AI 直接求解

M3 是 AI 直接从样本或样本特征预测 Weibull 参数。

形式：

```text
sample / features -> AI model -> beta_hat, eta_hat, gamma_hat
```

研究目标：

```text
AI 是否能直接学习样本到 Weibull 三参数的映射？
原始样本、掩码样本、统计特征等输入方式哪个更可靠？
M3 在组内、插值、外推测试中表现如何？
M3 和 M1、MDM、MLE 相比，优势来自精度、速度、成功率还是适用范围？
```

---

## 4. 当前阶段要审计什么

当前不是训练模型，也不是写代码。

当前阶段是：

```text
先确定指标体系。
```

因为如果指标错了，后续：

```text
损失函数会错；
训练目标会错；
模型比较会错；
页面展示会错；
研究结论也会错。
```

所以现在需要审计的核心文档是：

```text
docs/AI辅助参数估计指标定义方案草案.md
```

请重点判断：

```text
这些指标是否足够支撑 M1-A、M1-B、M3 的研究目标？
公式是否正确？
失败样本处理是否合理？
γ 参数误差处理是否合理？
B1/B5/B10 是否应该作为核心应用层指标？
训练损失建议是否和最终评价指标一致？
```

---

## 5. 当前指标方案摘要

当前草案建议指标分为三类：

```text
输入指标
结果指标
统计指标
```

### 5.1 输入指标

用于描述样本和实验条件：

```text
sample_id
seed
split
validation_type
n
beta_true
eta_true
gamma_true
t1...tn
sample_mean
sample_std
sample_cv
sample_min
sample_max
sample_quantiles
```

### 5.2 结果指标

用于记录方法输出：

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

AI 特有结果：

```text
M1-A: delta_hat, delta_label, label_quality_flag
M1-B: beta_base, eta_base, gamma_base, residual_*_hat
M3: input_representation, model_version, target_transform, loss_function
```

派生结果：

```text
B1_life_hat
B5_life_hat
B10_life_hat
B1_life_true
B5_life_true
B10_life_true
```

### 5.3 参数层统计指标

主指标：

```text
mae_beta  = mean(abs(beta_hat - beta_true))
mae_eta   = mean(abs(eta_hat - eta_true))
mae_gamma = mean(abs(gamma_hat - gamma_true))

mre_beta = mean(abs(beta_hat - beta_true) / abs(beta_true))
mre_eta  = mean(abs(eta_hat - eta_true) / abs(eta_true))

scaled_gamma_error = mean(abs(gamma_hat - gamma_true) / eta_true)
```

明确禁止普通 γ-MRE 作为主指标：

```text
abs(gamma_hat - gamma_true) / abs(gamma_true)
```

### 5.4 应用层统计指标

三参数 Weibull 分位点：

```text
Q_p(beta, eta, gamma) = gamma + eta * [-ln(1-p)]^(1/beta)
```

固定：

```text
B1_life  = Q_0.01
B5_life  = Q_0.05
B10_life = Q_0.10
```

其中：

```text
B1：失效概率 1%，对应 99% 可靠度寿命
B5：失效概率 5%，对应 95% 可靠度寿命
B10：失效概率 10%，对应 90% 可靠度寿命
```

指标：

```text
B1_life_mae
B5_life_mae
B10_life_mae
B1_life_mre
B5_life_mre
B10_life_mre
```

### 5.5 方法层统计指标

```text
success_rate = success_count / total_count
failure_rate = failed_count / total_count
mean_runtime_ms = mean(runtime_ms for all attempted samples)
failure_reason_distribution
outlier_ratio
```

失败样本规则：

```text
参数层和应用层误差只统计 success 样本。
方法层成功率和失败率必须包含 failed 样本。
所有指标表必须显示 count / total_count。
```

---

## 6. 训练损失函数建议

注意：

```text
训练损失不是最终评价指标。
最终评价必须回到统一指标。
```

### 6.1 M3 建议损失

```text
loss_param =
  w_beta  * abs(log(beta_hat) - log(beta_true))
+ w_eta   * abs(log(eta_hat) - log(eta_true))
+ w_gamma * abs(gamma_hat - gamma_true) / eta_true
```

如果强调可靠寿命，可加入：

```text
loss_life =
  v1  * abs(B1_hat - B1_true) / abs(B1_true)
+ v5  * abs(B5_hat - B5_true) / abs(B5_true)
+ v10 * abs(B10_hat - B10_true) / abs(B10_true)
```

组合：

```text
loss = alpha * loss_param + (1 - alpha) * loss_life
```

### 6.2 M1-A 建议损失

```text
loss_delta = abs(delta_hat - delta_label)
```

但模型选择不能只看 `loss_delta`，还必须看：

```text
AI δ 带入 MDM 后，参数层和 B1/B5/B10 是否改善。
```

### 6.3 M1-B 建议损失

参数残差修正：

```text
loss_residual =
  abs(log(beta_corrected) - log(beta_true))
+ abs(log(eta_corrected) - log(eta_true))
+ abs(gamma_corrected - gamma_true) / eta_true
```

如果应用层效果不好，再考虑加入 B1/B5/B10 损失。

---

## 7. 希望你审查的问题

请重点审查：

1. 指标分为输入指标、结果指标、统计指标是否合理？
2. 参数层主指标是否足够？
3. γ 用 `scaled_gamma_error = abs(gamma_hat - gamma_true) / eta_true` 是否合理？
4. 是否应该再加入其他 γ 误差归一化方式？
5. B1/B5/B10 是否足够代表可靠性工程应用层目标？
6. B1/B5/B10 使用 MRE 时，分母是否可能接近 0？是否需要保护规则？
7. 方法层指标是否应该包含 outlier_ratio？
8. 失败样本不参与参数误差、但参与成功率分母，这个规则是否合理？
9. M3 训练中使用 log β、log η 是否合理？
10. M1-A 是否应该把 δ 误差作为主指标，还是只作为过程诊断？
11. M1-B 应先修正参数残差，还是直接修正 B1/B5/B10？
12. 是否应该在 V1 就加入 CDF/KS 分布层指标？
13. 是否需要一个总分指标？如果需要，如何避免误导？
14. 当前指标是否足够支持后续训练、测试、可视化和论文/组会结论？

---

## 8. 希望你输出什么

请输出一份审查报告，最好按以下结构：

```text
1. 总体判断：这个指标体系是否方向正确？
2. 必须修改的问题：哪些公式、口径或指标有明显问题？
3. 建议补充的问题：哪些指标可以加入但不一定 V1 必须？
4. 可以暂缓的问题：哪些内容不适合第一版加入？
5. 对 M1-A 的建议
6. 对 M1-B 的建议
7. 对 M3 的建议
8. 对训练损失函数的建议
9. 对失败样本和异常样本统计的建议
10. 最终建议：是否可以据此进入 `/help/metrics` 和公共函数设计？
```

请不要泛泛而谈，尽量指出具体公式、字段名、指标口径和潜在风险。

