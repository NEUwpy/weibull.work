# AI 辅助参数估计 Benchmark V1 规范

> 日期：2026-05-19
> 目的：锁定第一版可执行 benchmark，避免后续 AI 自行发明参数空间、字段名和指标口径。
> 总纲入口：`docs/AI辅助参数估计模块重做总纲.md`
> 状态：V1 决策源。若后续需要更改，必须先修改本文档，再改脚本、模型和页面。

---

## 1. Benchmark V1 的定位

Benchmark V1 服务于 AI 模块全链路重做。

它不是只为重算几个代表方案，而是为以下任务提供统一数据和指标口径：

- MDM/MLE 等传统基准同集输出。
- M1-A：AI 优化传统方法过程量。
- M1-B：AI 纠正传统方法偏差。
- M3：AI 直接求解。

旧 M1/M3 结果不得混入 Benchmark V1 指标汇总。

---

## 2. 命名约定

| 名称 | 含义 |
|------|------|
| `M1_A` | AI 优化传统方法过程量 |
| `M1_B` | AI 纠正传统方法偏差 |
| `M2` | 智能优化算法辅助传统方法求解，V1 暂不做 |
| `M3` | AI 直接估计 `(β, η, γ)` |
| `ig` | in-group，组内测试 |
| `ip` | interpolation，插值测试 |
| `ex` | extrapolation，外推测试 |

注意：

- 模型方案名使用 `scheme` 字段。
- 可靠寿命指标使用 `B1_life`、`B5_life`、`B10_life`。
- 不得把 M3 方案 `B1` 与可靠寿命 `B1_life` 混写。

---

## 3. 参数空间

### 3.1 训练参数空间

```text
beta_train  = [0.5, 1.0, 2.0, 3.0, 5.0]
eta_train   = [100.0, 500.0, 1000.0, 3000.0, 5000.0]
gamma_train = [50.0, 100.0, 200.0, 1000.0]
n_train     = [5, 7, 10, 15]
mc_train    = 500
seed_start_train = 1
```

训练空间不使用 `gamma=0` 作为主训练点。若需要比较 `gamma=0`，只能作为额外 stress test。

### 3.2 验证集

验证集从训练参数空间中生成，但必须使用独立 seed。

```text
beta_val  = beta_train
eta_val   = eta_train
gamma_val = gamma_train
n_val     = n_train
mc_val    = 100
seed_start_val = 300000
```

验证集只能用于调参、早停、模型选择，不得作为最终测试结论。

### 3.3 组内测试 `ig`

```text
beta_ig  = beta_train
eta_ig   = eta_train
gamma_ig = gamma_train
n_ig     = n_train
mc_ig    = 100
seed_start_ig = 100000
```

### 3.4 插值测试 `ip`

```text
beta_ip  = [0.75, 1.5, 2.5, 4.0]
eta_ip   = [300.0, 750.0, 2000.0, 4000.0]
gamma_ip = [75.0, 150.0, 600.0]
n_ip     = [5, 7, 10, 15]
mc_ip    = 100
seed_start_ip = 600000
```

### 3.5 外推测试 `ex`

```text
beta_ex  = [0.3, 8.0, 10.0]
eta_ex   = [50.0, 8000.0, 10000.0]
gamma_ex = [10.0, 300.0, 1500.0]
n_ex     = [5, 7, 10, 15]
mc_ex    = 100
seed_start_ex = 1100000
```

外推组合过滤规则：

```text
gamma_true < eta_true
```

若生成样本时出现无效值，必须记录失败原因，不得静默跳过。

---

## 4. 样本生成规则

三参数 Weibull 样本按以下公式生成：

```text
t = gamma_true + eta_true * [-ln(1-u)]^(1/beta_true)
u ~ Uniform(0, 1)
```

规则：

- 每个样本内失效时间必须升序排列。
- 每条样本必须记录 `sample_id`。
- 每条样本必须记录实际使用的 `seed`。
- 训练、验证、测试不得共用 seed。
- `sample_id` 必须全局唯一。

建议 `sample_id` 格式：

```text
benchmark_v1_{split}_n{n}_{combo_index}_{mc_index}
```

其中 `split` 可为：

```text
train
val
ig
ip
ex
```

---

## 5. 数据文件格式

### 5.1 训练集 CSV

文件命名：

```text
benchmark_v1_train_n{n}.csv
```

字段：

```text
sample_id,split,n,beta_true,eta_true,gamma_true,seed,t1,t2,...,tn
```

字段规则：

- `split` 固定为 `train`。
- `t1...tn` 必须升序。

### 5.2 验证集 CSV

文件命名：

```text
benchmark_v1_val_n{n}.csv
```

字段：

```text
sample_id,split,n,beta_true,eta_true,gamma_true,seed,t1,t2,...,tn
```

字段规则：

- `split` 固定为 `val`。

### 5.3 测试集 CSV

文件命名：

```text
benchmark_v1_test_{validation_type}_n{n}.csv
```

字段：

```text
sample_id,validation_type,n,beta_true,eta_true,gamma_true,seed,t1,t2,...,tn
```

字段规则：

- `validation_type` 只能是 `ig`、`ip`、`ex`。

### 5.4 预测结果 CSV

文件命名：

```text
benchmark_v1_predictions_{method}_{scheme}_{validation_type}_n{n}.csv
```

字段：

```text
sample_id,method,scheme,n,validation_type,
beta_hat,eta_hat,gamma_hat,
status,failure_reason,runtime_ms
```

字段规则：

- `method` 示例：`MDM`、`MLE`、`M1_A_delta`、`M1_B_residual`、`M3_direct`。
- `scheme` 记录具体模型或传统方法配置。
- `status` 只能是 `success` 或 `failed`。
- 失败样本仍必须保留一行。
- 失败样本的参数预测值可为空，但 `failure_reason` 必须非空。

### 5.5 指标汇总 CSV

文件命名：

```text
benchmark_v1_metrics_summary.csv
```

字段：

```text
method,scheme,validation_type,n,group_key,
metric_name,metric_value,count,total_count
```

字段规则：

- `count` 是参与该指标计算的成功样本数。
- `total_count` 是该组全部样本数。
- 成功率使用 `success_count / total_count`。
- 参数误差不统计失败样本。
- 成功率、失败率必须统计失败样本。

---

## 6. 指标定义

### 6.1 参数层指标

```text
mae_beta  = mean(abs(beta_hat - beta_true))
mae_eta   = mean(abs(eta_hat - eta_true))
mae_gamma = mean(abs(gamma_hat - gamma_true))

mre_beta = mean(abs(beta_hat - beta_true) / abs(beta_true))
mre_eta  = mean(abs(eta_hat - eta_true) / abs(eta_true))

scaled_gamma_error = mean(abs(gamma_hat - gamma_true) / eta_true)
```

禁止作为主指标：

```text
mre_gamma = abs(gamma_hat - gamma_true) / abs(gamma_true)
```

### 6.2 应用层指标

三参数 Weibull 分位点：

```text
Q_p(beta, eta, gamma) = gamma + eta * [-ln(1-p)]^(1/beta)
```

固定计算：

```text
B1_life  = Q_0.01
B5_life  = Q_0.05
B10_life = Q_0.10
```

指标：

```text
B1_life_mae  = mean(abs(B1_hat - B1_true))
B5_life_mae  = mean(abs(B5_hat - B5_true))
B10_life_mae = mean(abs(B10_hat - B10_true))

B1_life_mre  = mean(abs(B1_hat - B1_true) / abs(B1_true))
B5_life_mre  = mean(abs(B5_hat - B5_true) / abs(B5_true))
B10_life_mre = mean(abs(B10_hat - B10_true) / abs(B10_true))
```

### 6.3 方法层指标

```text
success_rate = success_count / total_count
failure_rate = failed_count / total_count
mean_runtime_ms = mean(runtime_ms for all attempted samples)
```

失败样本要求：

- 失败样本不参与参数误差均值。
- 失败样本必须参与成功率和失败率分母。
- 失败原因必须进入 `failure_reason`。

---

## 7. 训练目标登记

每个模型训练前，必须登记训练目标。

字段建议：

```text
method
scheme
model_family
input_representation
target_definition
target_transform
loss_function
training_split
validation_split
test_splits
metric_priority
```

原则：

- 损失函数必须解释与研究目标的关系。
- 最终评价必须使用系统级指标，而不是训练损失本身。
- 若研究目标包含 B1/B5/B10，训练或模型选择必须说明是否使用应用层指标。

---

## 8. M1-A 标签协议

M1-A 是 AI 优化传统方法过程量。

δ 标签 CSV 至少包含：

```text
sample_id,n,beta_true,eta_true,gamma_true,
delta_label,label_quality_flag,best_metric,
status,failure_reason
```

训练前必须确定：

```text
delta_search_min
delta_search_max
delta_search_strategy
best_delta_selection_metric
boundary_rule
label_quality_flag
```

在没有完成标签协议前，不得训练 M1-A。

---

## 9. M1-B 标签协议

M1-B 是 AI 纠正传统方法偏差。

残差标签 CSV 至少包含：

```text
sample_id,traditional_method,scheme,n,validation_type,
beta_true,eta_true,gamma_true,
beta_base,eta_base,gamma_base,
residual_beta,residual_eta,residual_gamma,
residual_target_type,status,failure_reason
```

训练前必须确定：

```text
traditional_method
correction_target
residual_formula
target_transform
invalid_baseline_rule
```

在没有完成残差协议前，不得训练 M1-B。

---

## 10. M3 方案登记

M3 是 AI 直接求解。

所有纳入研究的 M3 方案都必须重新登记并重新训练。

方案登记至少包含：

```text
scheme
input_representation
supports_multiple_n
uses_mask
uses_summary_statistics
target_transform
loss_function
model_path
training_log_path
```

原则：

- 旧 M3 方案若继续作为研究对象，必须重训。
- 不得只重训少数代表方案后宣称 M3 完成。
- 若某旧方案不再研究，必须明确标注为废止，不进入新结果比较。

---

## 11. 验收标准

Benchmark V1 完成时必须满足：

1. 每个样本有 `sample_id` 和 `seed`。
2. 训练、验证、测试 seed 不重复。
3. 每个预测样本无论成功失败都有记录。
4. 指标汇总可追溯到预测结果。
5. M1/M3/MDM/MLE 使用同一测试集。
6. γ 不使用普通 MRE 作主指标。
7. B1/B5/B10 指标在汇总文件中存在。
8. `ig/ip/ex` 三类结果分开统计。
9. 失败样本计入成功率和失败率分母。
10. 所有纳入研究的 M1/M3 方案已按新协议重训。

