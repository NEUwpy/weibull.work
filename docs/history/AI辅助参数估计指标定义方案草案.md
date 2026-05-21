# AI 辅助参数估计指标定义方案草案

> 日期：2026-05-19
> 用途：提交给本人和其他 AI 审计的指标方案草案。
> 状态：未敲定。审计通过后，再更新 `/help/metrics` 和公共指标函数。
> 上游文档：`docs/AI辅助参数估计重做简明路线图.md`

---

## 1. 这份文档要解决什么

当前进入第 3 步：统一系统指标。

本方案先回答：

```text
1. 最终评价指标应该有哪些？
2. 每个指标怎么算？
3. 哪些指标是主指标？
4. 哪些指标只作为辅助诊断？
5. 失败样本怎么算？
6. M1-A、M1-B、M3 分别重点看哪些指标？
7. 训练损失函数和最终评价指标是什么关系？
```

---

## 2. 总原则

### 2.1 指标分三类

系统指标分为三类：

```text
输入指标：描述样本和实验条件
结果指标：描述某个方法输出了什么
统计指标：评价方法表现好不好
```

### 2.2 最终评价指标必须统一

无论是：

```text
MDM
MLE
M1-A
M1-B
M3
```

最终都必须用同一套统计指标评价。

### 2.3 训练损失不等于最终评价

训练时可以使用不同损失函数，但最终报告必须回到统一指标。

例如：

```text
M3 训练时可以用 log(beta)、log(eta)、scaled gamma loss
但最终评价仍然必须输出 MAE、MRE、B1/B5/B10、成功率等统一指标
```

### 2.4 γ 不使用普通 MRE

禁止把下面这个作为主指标：

```text
abs(gamma_hat - gamma_true) / abs(gamma_true)
```

原因：

```text
gamma_true 可能为 0 或接近 0，相对误差会爆炸。
```

γ 推荐使用：

```text
mae_gamma
scaled_gamma_error = abs(gamma_hat - gamma_true) / eta_true
```

### 2.5 参数准不等于工程结果准

参数误差小，不一定代表可靠寿命分位点误差小。

因此必须加入：

```text
B1_life
B5_life
B10_life
```

其中：

```text
B1 对应失效概率 1%，也就是 99% 可靠度寿命。
```

---

## 3. 输入指标

输入指标用于描述样本和实验条件，不直接评价方法好坏。

### 3.1 必须字段

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
```

说明：

- `split` 用于 `train`、`val`。
- `validation_type` 用于 `ig`、`ip`、`ex`。
- `sample_id` 和 `seed` 用于结果追溯。

### 3.2 推荐样本统计特征

这些可以作为模型输入或页面解释特征：

```text
sample_mean
sample_std
sample_cv
sample_min
sample_max
sample_range
sample_median
sample_q25
sample_q75
sample_iqr
log_sample_mean
log_sample_std
```

注意：

```text
样本统计特征是输入描述，不是最终评价指标。
```

---

## 4. 结果指标

结果指标用于记录某个方法对某条样本输出了什么。

### 4.1 通用结果字段

所有方法统一输出：

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

### 4.2 AI 特有结果字段

M1-A 可额外输出：

```text
delta_hat
delta_label
label_quality_flag
```

M1-B 可额外输出：

```text
beta_base
eta_base
gamma_base
residual_beta_hat
residual_eta_hat
residual_gamma_hat
```

M3 可额外输出：

```text
input_representation
model_version
target_transform
loss_function
```

### 4.3 派生结果字段

由估计参数派生：

```text
B1_life_hat
B5_life_hat
B10_life_hat
```

由真实参数派生：

```text
B1_life_true
B5_life_true
B10_life_true
```

---

## 5. 统计指标：参数层

参数层回答：

```text
β、η、γ 估得准不准？
```

### 5.1 主指标

```text
mae_beta  = mean(abs(beta_hat - beta_true))
mae_eta   = mean(abs(eta_hat - eta_true))
mae_gamma = mean(abs(gamma_hat - gamma_true))

mre_beta = mean(abs(beta_hat - beta_true) / abs(beta_true))
mre_eta  = mean(abs(eta_hat - eta_true) / abs(eta_true))

scaled_gamma_error = mean(abs(gamma_hat - gamma_true) / eta_true)
```

主指标解释：

- `mae_beta`：β 原始尺度误差。
- `mae_eta`：η 原始尺度误差。
- `mae_gamma`：γ 原始尺度误差。
- `mre_beta`：β 相对误差。
- `mre_eta`：η 相对误差。
- `scaled_gamma_error`：γ 相对于 η 尺度的误差。

### 5.2 辅助指标

```text
bias_beta  = mean(beta_hat - beta_true)
bias_eta   = mean(eta_hat - eta_true)
bias_gamma = mean(gamma_hat - gamma_true)

rmse_beta  = sqrt(mean((beta_hat - beta_true)^2))
rmse_eta   = sqrt(mean((eta_hat - eta_true)^2))
rmse_gamma = sqrt(mean((gamma_hat - gamma_true)^2))
```

辅助指标用途：

- `bias_*` 看系统性高估或低估。
- `rmse_*` 对大误差更敏感，适合诊断异常估计。

### 5.3 不建议作为主指标

```text
total_relative_mse
overall_mre
single_score
```

原因：

```text
聚合指标容易掩盖 β、η、γ 各自的问题。
如果必须排序，可以作为辅助总分，但必须说明权重。
```

---

## 6. 统计指标：应用层

应用层回答：

```text
估计参数推导出的可靠寿命准不准？
```

### 6.1 Weibull 分位点

三参数 Weibull 的失效概率分位点：

```text
Q_p(beta, eta, gamma) = gamma + eta * [-ln(1-p)]^(1/beta)
```

固定使用：

```text
B1_life  = Q_0.01
B5_life  = Q_0.05
B10_life = Q_0.10
```

说明：

```text
B1：失效概率 1%，对应 99% 可靠度寿命
B5：失效概率 5%，对应 95% 可靠度寿命
B10：失效概率 10%，对应 90% 可靠度寿命
```

### 6.2 主指标

```text
B1_life_mae  = mean(abs(B1_hat - B1_true))
B5_life_mae  = mean(abs(B5_hat - B5_true))
B10_life_mae = mean(abs(B10_hat - B10_true))

B1_life_mre  = mean(abs(B1_hat - B1_true) / abs(B1_true))
B5_life_mre  = mean(abs(B5_hat - B5_true) / abs(B5_true))
B10_life_mre = mean(abs(B10_hat - B10_true) / abs(B10_true))
```

### 6.3 为什么应用层必须保留

原因：

```text
可靠性工程最终常常关心寿命分位点，而不是参数本身。
两个方法可能参数误差接近，但 B1/B5/B10 误差差很多。
```

---

## 7. 统计指标：方法层

方法层回答：

```text
方法是否稳定、是否会失败、是否可用？
```

### 7.1 主指标

```text
success_rate = success_count / total_count
failure_rate = failed_count / total_count
mean_runtime_ms = mean(runtime_ms for all attempted samples)
```

说明：

- `total_count` 必须包含失败样本。
- 失败样本不能从分母删除。
- `runtime_ms` 建议统计所有尝试样本，包括失败样本。

### 7.2 失败原因

必须记录：

```text
failure_reason
```

建议枚举：

```text
none
invalid_input
optimization_failed
non_convergence
invalid_prediction
nan_output
out_of_domain
timeout
unknown
```

### 7.3 异常估计比例

建议加入：

```text
outlier_ratio = outlier_count / success_count
```

异常估计可先定义为：

```text
beta_hat <= 0
eta_hat <= 0
gamma_hat >= min(sample)
non_finite_output
```

说明：

```text
具体异常规则可以在实现前再细化。
```

---

## 8. 可选指标：分布层

分布层回答：

```text
估计出来的 Weibull 分布整体是否接近真实分布？
```

V1 可先作为辅助，不作为必须主指标。

### 8.1 CDF 平均误差

在一组固定网格点 `x_j` 上：

```text
cdf_mae = mean(abs(F_hat(x_j) - F_true(x_j)))
```

### 8.2 KS 型误差

```text
ks_error = max(abs(F_hat(x_j) - F_true(x_j)))
```

### 8.3 审计建议

分布层指标很有价值，但 V1 先不强制作为主指标。

原因：

```text
需要额外定义 x_j 网格、积分范围和数值稳定规则。
如果过早加入，会增加工程复杂度。
```

---

## 9. 各模块重点看什么

### 9.1 传统基准：MDM / MLE

重点看：

```text
参数层指标
应用层指标
方法层指标
```

作用：

```text
作为 AI 方法的参照系。
```

### 9.2 M1-A：AI 优化过程量

过程量指标：

```text
delta_mae = mean(abs(delta_hat - delta_label))
label_quality_distribution
boundary_label_ratio
```

但 M1-A 的最终主指标不是 δ 本身，而是：

```text
使用 AI δ 后，MDM 的参数层和应用层指标是否改善。
```

必须比较：

```text
MDM_fixed_delta
MDM_search_delta
MDM_ai_delta
```

### 9.3 M1-B：AI 纠正传统方法偏差

重点看：

```text
修正前 vs 修正后
```

必须比较：

```text
traditional_base
traditional_ai_corrected
```

主指标：

```text
参数层改善
B1/B5/B10 改善
成功率是否下降
异常估计比例是否上升
```

### 9.4 M3：AI 直接求解

重点看：

```text
参数层指标
应用层指标
ig/ip/ex 泛化差异
异常输出比例
```

必须比较：

```text
M3 各输入方案
MDM
MLE
M1-A
M1-B
```

---

## 10. 训练损失函数建议

这一节不是最终评价指标，而是训练时可选择的损失函数方案。

### 10.1 M3 推荐损失

建议优先考虑：

```text
loss_param =
  w_beta  * abs(log(beta_hat) - log(beta_true))
+ w_eta   * abs(log(eta_hat) - log(eta_true))
+ w_gamma * abs(gamma_hat - gamma_true) / eta_true
```

原因：

- β、η 为正，log 误差更稳定。
- η 尺度跨度大，log 后更适合训练。
- γ 用 η 归一化，避免 γ 接近 0 的相对误差问题。

如果要强调工程寿命，可加入：

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

### 10.2 M1-A 推荐损失

M1-A 训练 AI 预测 δ。

可选：

```text
loss_delta = abs(delta_hat - delta_label)
```

但模型选择不能只看 `loss_delta`，还必须看：

```text
AI δ 带入 MDM 后的参数层和应用层指标。
```

### 10.3 M1-B 推荐损失

若修正参数残差：

```text
loss_residual =
  abs(log(beta_corrected) - log(beta_true))
+ abs(log(eta_corrected) - log(eta_true))
+ abs(gamma_corrected - gamma_true) / eta_true
```

若修正工程寿命：

```text
loss_life_residual =
  B1/B5/B10 relative error after correction
```

建议：

```text
先做参数残差修正，再评估 B1/B5/B10；
如果应用层效果不好，再加入应用层损失。
```

---

## 11. 聚合和分组规则

所有统计指标必须至少按以下维度分组：

```text
method
scheme
validation_type
n
```

建议增加：

```text
beta_true
eta_true
gamma_true
```

最终展示时必须分开：

```text
ig
ip
ex
```

禁止把三类测试混在一起得到一个总平均后直接下结论。

---

## 12. 成功样本和失败样本规则

### 12.1 参数层和应用层

只统计：

```text
status = success
```

但必须记录：

```text
count
total_count
```

### 12.2 方法层

统计全部样本：

```text
success + failed
```

### 12.3 页面展示

每个指标表都应显示：

```text
count / total_count
```

否则用户不知道精度均值是基于多少成功样本算出来的。

---

## 13. 建议主指标清单

V1 最少主指标：

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
```

V1 辅助指标：

```text
bias_beta
bias_eta
bias_gamma
rmse_beta
rmse_eta
rmse_gamma
outlier_ratio
failure_reason_distribution
```

V2 可扩展：

```text
cdf_mae
ks_error
integrated_cdf_error
uncertainty_coverage
```

---

## 14. 审计问题清单

请另一个 AI 重点审计这些问题：

1. γ 使用 `scaled_gamma_error = abs(gamma_hat - gamma_true) / eta_true` 是否合理？
2. B1/B5/B10 是否足够代表可靠性工程应用层目标？
3. B1/B5/B10 使用 MRE 时，分母 `B*_true` 是否可能接近 0？是否需要保护规则？
4. M3 训练损失中使用 log β、log η 是否合理？
5. M1-A 是否应该把 δ 误差作为主指标，还是只作为过程诊断？
6. M1-B 应优先修正参数残差，还是直接修正 B1/B5/B10？
7. 是否应该在 V1 强制加入 CDF/KS 分布层指标？
8. `outlier_ratio` 的异常估计规则是否合理？
9. `mean_runtime_ms` 是否应该统计失败样本？
10. 是否需要一个聚合总分？如果需要，权重怎么定才不误导？

---

## 15. 我建议先敲定的版本

我建议 V1 先敲定：

```text
参数层：MAE + β/η MRE + scaled γ error
应用层：B1/B5/B10 的 MAE 和 MRE
方法层：success_rate + failure_rate + runtime + failure_reason
```

先不把以下内容作为 V1 主指标：

```text
普通 γ-MRE
total_relative_mse
单一综合评分
CDF/KS 分布层指标
```

原因：

```text
V1 要先稳定、清楚、可实现。
分布层和综合评分可以等第一轮可信结果出来后再扩展。
```

