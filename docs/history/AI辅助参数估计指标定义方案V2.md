# AI 辅助参数估计指标定义方案 V2

> 日期：2026-05-19
> 状态：综合 `人的意见.md`、`审查报告1.md`、`审查报告2.md` 后形成的第二版方案。
> 目的：用尽量少、清楚、可解释的指标，支撑后续 `/help/metrics`、公共指标函数、模型训练和可视化。

---

## 1. 这版方案的核心变化

相比上一版草案，V2 做了五个收束：

1. **指标变少**：只保留能直接回答研究问题的核心指标。
2. **分层更直观**：只围绕“准不准、稳不稳、工程寿命准不准、能不能用”来定义。
3. **加入保护规则**：避免 γ、B-life 因分母过小导致相对误差爆炸。
4. **加入共同成功集**：跨方法比较时，避免不同方法在不同成功样本上比较造成偏差。
5. **加入 M1-B 偏差/波动指标**：因为 M1-B 的目标就是纠正传统方法系统偏差。

---

## 2. 指标体系总览

V2 不再堆很多指标，而是分成四组。

| 指标组 | 回答的问题 | 是否 V1 必须 |
|--------|------------|--------------|
| 参数精度指标 | β、η、γ 估得准不准 | 必须 |
| 稳定性指标 | 估计结果波动大不大，是否有系统偏差 | 必须 |
| 工程寿命指标 | B0.5/B1/B5/B10 这些可靠寿命估得准不准 | 必须 |
| 方法可用性指标 | 方法是否成功、是否异常、耗时多少 | 必须 |

V1 暂不把 CDF/KS、综合总分、不确定性覆盖率作为主指标。

---

## 3. 基础数据口径

### 3.1 每条样本必须记录

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
- `sample_id` 和 `seed` 用于追溯。

### 3.2 每个方法必须输出

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

M1-A 额外输出：

```text
delta_hat
delta_label
label_quality_flag
```

M1-B 额外输出：

```text
beta_base
eta_base
gamma_base
residual_beta_hat
residual_eta_hat
residual_gamma_hat
```

M3 额外输出：

```text
input_representation
model_version
target_transform
loss_function
```

---

## 4. 状态口径：success / outlier / failed

V2 采用三态，而不是简单成功/失败。

```text
status ∈ {success, outlier, failed}
```

含义：

| 状态 | 含义 | 是否进入主精度统计 |
|------|------|--------------------|
| `success` | 数值有效，且未触发异常规则 | 是 |
| `outlier` | 算出来了，但结果明显异常 | 否，单独统计 |
| `failed` | 方法没有给出可用结果 | 否，单独统计 |

### 4.1 failed 判定

以下情况记为 `failed`：

```text
optimization_failed
non_convergence
timeout
nan_output
exception
not_attempted
```

### 4.2 outlier 判定

以下情况建议记为 `outlier`：

```text
beta_hat <= 0
eta_hat <= 0
non_finite_output
abs(log(beta_hat / beta_true)) > log(10)
abs(log(eta_hat / eta_true)) > log(10)
abs(gamma_hat - gamma_true) / eta_true > 1
abs(B10_hat - B10_true) / eta_true > 5
```

说明：

- outlier 阈值一旦进入 `/help/metrics`，后续不能为了结果好看随意修改。
- 如果未来修改阈值，必须标记指标版本并重算历史结果。

---

## 5. 参数精度指标

参数精度回答：

```text
β、η、γ 估得准不准？
```

### 5.1 β 和 η

β、η 都是正参数，且 η 可能跨多个量级。

主指标：

```text
mae_log_beta = mean(abs(log(beta_hat) - log(beta_true)))
mae_log_eta  = mean(abs(log(eta_hat) - log(eta_true)))

mre_beta = mean(abs(beta_hat - beta_true) / beta_true)
mre_eta  = mean(abs(eta_hat - eta_true) / eta_true)
```

解释：

- `mae_log_beta`、`mae_log_eta` 更适合跨量级比较。
- `mre_beta`、`mre_eta` 更直观，适合给用户看。

### 5.2 γ

γ 不使用普通 MRE。

主指标：

```text
mae_gamma = mean(abs(gamma_hat - gamma_true))
scaled_gamma_error = mean(abs(gamma_hat - gamma_true) / eta_true)
```

解释：

- `mae_gamma` 保留原始量纲。
- `scaled_gamma_error` 用 η 归一化，避免 γ 接近 0 时相对误差爆炸。

---

## 6. 稳定性指标

稳定性回答：

```text
估计结果波动大不大？有没有系统性高估或低估？
```

### 6.1 偏差 bias

β、η 推荐使用 log bias：

```text
bias_log_beta = mean(log(beta_hat) - log(beta_true))
bias_log_eta  = mean(log(eta_hat) - log(eta_true))
```

γ 使用 η 归一化 bias：

```text
bias_gamma_scaled = mean((gamma_hat - gamma_true) / eta_true)
```

### 6.2 波动 std

```text
std_log_beta = std(log(beta_hat) - log(beta_true))
std_log_eta  = std(log(eta_hat) - log(eta_true))
std_gamma_scaled = std((gamma_hat - gamma_true) / eta_true)
```

### 6.3 为什么 V1 必须有 bias 和 std

尤其对 M1-B 来说，核心研究目标是：

```text
AI 是否纠正了传统方法的系统偏差？
```

只看 MAE 不够。必须能说清：

```text
修正前 bias 是多少？
修正后 bias 是否下降？
修正后 std 是否变大？
```

一个理想的 M1-B 结果应该是：

```text
bias 下降，同时 std 没有明显上升。
```

---

## 7. 工程寿命指标

工程寿命指标回答：

```text
估计参数用于可靠寿命计算时，偏差有多大？
```

### 7.1 Weibull 分位点

三参数 Weibull 的失效概率分位点：

```text
Q_p(beta, eta, gamma) = gamma + eta * [-ln(1-p)]^(1/beta)
```

V2 固定使用：

```text
B0.5_life = Q_0.005
B1_life   = Q_0.01
B5_life   = Q_0.05
B10_life  = Q_0.10
```

含义：

```text
B0.5：失效概率 0.5%，对应 99.5% 可靠度寿命
B1：失效概率 1%，对应 99% 可靠度寿命
B5：失效概率 5%，对应 95% 可靠度寿命
B10：失效概率 10%，对应 90% 可靠度寿命
```

说明：

- B1/B5/B10 是主展示。
- B0.5 用于更高可靠度场景，可作为重点扩展指标。

### 7.2 主指标：scaled error

审查意见指出，B-life 的 MRE 也可能因为分母过小而爆炸。

因此 V2 采用 η 归一化误差作为主指标：

```text
B0_5_life_scaled_error = mean(abs(B0.5_hat - B0.5_true) / eta_true)
B1_life_scaled_error   = mean(abs(B1_hat - B1_true) / eta_true)
B5_life_scaled_error   = mean(abs(B5_hat - B5_true) / eta_true)
B10_life_scaled_error  = mean(abs(B10_hat - B10_true) / eta_true)
```

### 7.3 辅助指标：MAE 和受保护 MRE

MAE：

```text
B1_life_mae  = mean(abs(B1_hat - B1_true))
B5_life_mae  = mean(abs(B5_hat - B5_true))
B10_life_mae = mean(abs(B10_hat - B10_true))
```

受保护 MRE：

```text
Bp_life_mre = mean(abs(Bp_hat - Bp_true) / abs(Bp_true))
```

但仅在以下条件下统计：

```text
abs(Bp_true) > tau * eta_true
```

V1 建议：

```text
tau = 1e-3
```

如果不满足该条件：

```text
该样本不进入 Bp_life_mre 聚合；
但必须记录 low_denominator_count 和 low_denominator_ratio。
```

### 7.4 为什么这样定

这样可以同时满足：

- 不丢失用户容易理解的 B-life MAE。
- 避免 B-life MRE 因分母过小爆炸。
- 保留可靠性工程最关心的高可靠度寿命指标。

---

## 8. 方法可用性指标

方法可用性回答：

```text
这个方法能不能稳定用？
```

主指标：

```text
success_rate = success_count / total_count
outlier_rate = outlier_count / total_count
failure_rate = failed_count / total_count
usable_rate  = success_count / total_count
```

说明：

- `success` 才算真正可用。
- `outlier` 表示数值上算出来了，但结果异常。
- `failed` 表示没有可用结果。

运行时间：

```text
mean_runtime_ms_success
mean_runtime_ms_failed
p95_runtime_ms
```

失败原因分布：

```text
failure_reason_distribution
```

建议枚举：

```text
none
convergence_fail
numeric_overflow
invalid_param
boundary_solution
timeout
exception
not_attempted
unknown
```

---

## 9. 共同成功集比较

跨方法比较时，必须增加共同成功集口径。

### 9.1 为什么需要

如果两个方法成功样本不同：

```text
方法 A 在 90% 样本上成功
方法 B 在 99% 样本上成功
```

直接比较它们各自 success 子集上的 MAE，会不公平。

### 9.2 指标命名

共同成功集指标加 `_common` 后缀：

```text
mae_log_beta_common
mre_eta_common
scaled_gamma_error_common
B1_life_scaled_error_common
```

同时记录：

```text
common_count
common_ratio = common_count / total_count
```

### 9.3 展示规则

建议：

```text
主对比表使用共同成功集。
方法可用性表单独展示 success/outlier/failure。
各自成功集指标作为附表。
```

---

## 10. M1-A 指标方案

M1-A 是 AI 优化传统方法过程量，例如 MDM 的 δ。

### 10.1 主指标

M1-A 的主指标不是 δ 预测误差。

主指标是：

```text
AI δ 带入 MDM 后，MDM 的参数精度、工程寿命精度、可用性是否改善。
```

必须比较：

```text
MDM_default_delta
MDM_best_constant_delta
MDM_search_delta
MDM_ai_delta
```

### 10.2 过程诊断指标

```text
delta_mae
label_quality_distribution
boundary_label_ratio
```

说明：

```text
delta_mae 只说明 AI 是否学到了标签，
不直接说明估计结果是否更好。
```

### 10.3 标签质量

建议：

```text
label_quality_flag ∈ {clean, boundary, flat_curve, noisy, failed}
```

---

## 11. M1-B 指标方案

M1-B 是 AI 纠正传统方法偏差。

### 11.1 主指标

必须比较：

```text
traditional_base
traditional_ai_corrected
```

主指标：

```text
参数精度是否改善
工程寿命精度是否改善
bias 是否下降
std 是否没有明显上升
success/outlier/failure 是否变差
```

### 11.2 残差表示

β、η 推荐使用乘性修正：

```text
beta_corrected = beta_base * exp(residual_log_beta_hat)
eta_corrected  = eta_base  * exp(residual_log_eta_hat)
```

γ 推荐使用加性修正：

```text
gamma_corrected = gamma_base + residual_gamma_hat
```

原因：

- β、η 必须为正，且跨量级，log 残差更稳定。
- γ 可以接近 0，不适合乘性修正。

### 11.3 失败传染规则

M1-B 依赖传统方法输出。

如果传统方法失败：

```text
M1-B 记为 not_attempted 或 failed
```

并且：

```text
M1-B 的 success_rate 分母仍然是 total_count，
不是 traditional success_count。
```

---

## 12. M3 指标方案

M3 是 AI 直接求解。

### 12.1 主指标

```text
参数精度
工程寿命精度
success/outlier/failure
ig/ip/ex 泛化差异
```

### 12.2 输入方案必须单独报告

必须记录：

```text
input_representation
```

候选：

```text
raw_sorted_sample
mask_padded_sample
summary_features
hybrid
```

不同输入方案不能混在一起平均后下结论。

### 12.3 泛化差异

建议报告：

```text
ig_metric
ip_metric
ex_metric
ig_ip_gap
ig_ex_gap
```

其中：

```text
ig_ip_gap = ip_metric - ig_metric
ig_ex_gap = ex_metric - ig_metric
```

如果 gap 很大，说明泛化风险高。

---

## 13. 训练损失函数建议

注意：

```text
训练损失不是最终评价指标。
最终评价必须回到统一指标。
```

### 13.1 M3 损失

V1 建议先从纯参数损失开始。

```text
loss_param =
  w_beta  * Huber(log(beta_hat) - log(beta_true))
+ w_eta   * Huber(log(eta_hat) - log(eta_true))
+ w_gamma * Huber((gamma_hat - gamma_true) / eta_true)
```

说明：

- Huber 比纯 L1/L2 更稳。
- β、η 用 log。
- γ 用 η 归一化。

权重建议：

```text
V1 可先等权；
更稳的做法是按 baseline error 的标准差反向加权。
```

工程寿命损失先不作为 V1 默认训练损失。

如果后续要加入：

```text
loss_life =
  v0_5 * Huber(log((B0.5_hat + eps) / (B0.5_true + eps)))
+ v1   * Huber(log((B1_hat   + eps) / (B1_true   + eps)))
+ v5   * Huber(log((B5_hat   + eps) / (B5_true   + eps)))
+ v10  * Huber(log((B10_hat  + eps) / (B10_true  + eps)))
```

### 13.2 M1-A 损失

```text
loss_delta = Huber(delta_hat - delta_label)
```

但早停和模型选择建议看下游指标：

```text
MDM_ai_delta 的参数精度或 B-life 精度
```

### 13.3 M1-B 损失

建议直接学习残差：

```text
loss_residual =
  Huber(residual_log_beta_hat - residual_log_beta_true)
+ Huber(residual_log_eta_hat  - residual_log_eta_true)
+ Huber(residual_gamma_hat_scaled - residual_gamma_true_scaled)
```

其中：

```text
residual_log_beta_true = log(beta_true) - log(beta_base)
residual_log_eta_true  = log(eta_true)  - log(eta_base)
residual_gamma_true_scaled = (gamma_true - gamma_base) / eta_true
```

---

## 14. 分组统计规则

所有指标至少按以下维度分组：

```text
method
scheme
validation_type
n
```

还应支持：

```text
beta_regime
eta_regime
gamma_regime
```

建议 β 分组：

```text
beta < 1
1 <= beta < 2
2 <= beta < 5
beta >= 5
```

建议 γ 分组：

```text
gamma_true / eta_true = 0
0 < gamma_true / eta_true <= 0.1
0.1 < gamma_true / eta_true <= 0.5
gamma_true / eta_true > 0.5
```

禁止只报告全量平均值后直接下结论。

---

## 15. V1 最终主指标清单

### 15.1 参数精度

```text
mae_log_beta
mae_log_eta
mre_beta
mre_eta
mae_gamma
scaled_gamma_error
```

### 15.2 稳定性

```text
bias_log_beta
bias_log_eta
bias_gamma_scaled
std_log_beta
std_log_eta
std_gamma_scaled
```

### 15.3 工程寿命

```text
B0_5_life_scaled_error
B1_life_scaled_error
B5_life_scaled_error
B10_life_scaled_error

B1_life_mae
B5_life_mae
B10_life_mae

B1_life_mre_protected
B5_life_mre_protected
B10_life_mre_protected
low_denominator_ratio
```

说明：

- B1/B5/B10 是主展示。
- B0.5 作为高可靠度扩展重点保留。

### 15.4 方法可用性

```text
success_rate
outlier_rate
failure_rate
mean_runtime_ms_success
mean_runtime_ms_failed
p95_runtime_ms
failure_reason_distribution
common_count
common_ratio
```

---

## 16. V1 暂缓指标

以下内容暂不作为 V1 主指标：

```text
普通 gamma MRE
total_relative_mse
单一综合总分
CDF/KS/AD 分布层指标
bootstrap 置信区间
uncertainty coverage
```

原因：

```text
V1 先保证核心指标少、清楚、可实现。
```

---

## 17. 下一步

如果本方案通过审查，下一步应该：

1. 更新 `/help/metrics` 页面。
2. 定义 `python/studies/common/metrics.py` 的函数接口。
3. 定义 `src/lib/metrics.ts` 的类型和函数接口。
4. 将 `benchmark-spec-v1.md` 中的指标字段同步为 V2。
5. 再进入数据生成和训练设计。

