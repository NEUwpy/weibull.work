# AI 辅助参数估计统一蒙特卡洛框架审查意见

> 定位：对 `docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md` 的阶段性审查。
> 结论：当前框架方向正确，可以解决“每次蒙特卡洛都重写一套”的核心问题；但在真正进入代码实现前，必须先补齐状态口径、字段口径、方法调用边界和指标汇总口径。
> 边界：本文只做方案审查和下一阶段排序，不训练模型，不跑实验，不使用旧 M1/M3 结果作为正式结论。

---

## 1. 总体判断

统一蒙特卡洛框架的主链路是正确的：

```text
参数空间配置
↓
统一样本生成器
↓
samples.csv
↓
统一方法调用接口
↓
predictions.csv
↓
统一指标函数
↓
metrics_summary.csv
↓
前端页面 / 组会图表 / 论文实验表格
```

这条链路能解决当前最关键的问题：

1. 传统方法、AI 方法使用同一批样本。
2. 失败样本不再被静默删除或写成 `0/NaN`。
3. MDM、MLE、M1-A、M1-B、M3 都能输出同一种预测结果表。
4. 指标由统一函数计算，避免页面、训练脚本、研究脚本各算各的。
5. 前端和论文图表读取同一套 `predictions.csv` 与 `metrics_summary.csv`。

但当前方案还不能直接进入实现。原因不是方向错，而是几个关键协议还没有冻结。

---

## 2. P0 必须补齐的问题

### 2.1 Benchmark 规范与指标 V2 仍有不一致

`docs/AI辅助参数估计指标定义方案V2.md` 已经采用：

```text
status ∈ {success, outlier, failed}
mae_log_beta / mae_log_eta
scaled_gamma_error
B0.5/B1/B5/B10 life scaled error
protected B-life MRE
common success set
```

但 `docs/ai-research/benchmark-spec-v1.md` 仍有旧口径：

```text
status 只能是 success 或 failed
mae_beta / mae_eta 仍作为参数层主指标
B-life MRE 没有分母保护
没有 outlier、common、B0.5、log 参数误差字段
```

因此下一步不能先写生成器。必须先同步：

```text
指标 V2
统一蒙特卡洛框架
benchmark-spec-v1
/help/metrics
```

否则会再次出现“文档一套、脚本一套、页面一套”的问题。

### 2.2 samples / predictions 的 split 与 validation_type 需要统一

当前方案里：

- `split` 用于 `train/val`。
- `validation_type` 用于 `ig/ip/ex`。

这个设计容易导致测试集没有 `split`、训练集没有 `validation_type`，后续 runner 和 metrics runner 要写很多特殊判断。

建议统一为：

```text
split ∈ {train, val, ig, ip, ex}
validation_type ∈ {train, val, ig, ip, ex}
```

规则：

- 对训练集：`split=train`, `validation_type=train`
- 对验证集：`split=val`, `validation_type=val`
- 对组内测试：`split=ig`, `validation_type=ig`
- 对插值测试：`split=ip`, `validation_type=ip`
- 对外推测试：`split=ex`, `validation_type=ex`

这样所有 CSV 都有同一组字段，所有指标都能按 `validation_type` 分组。

### 2.3 method_runner 不能把真值传给普通估计方法

当前方案的“统一输入”包含：

```text
beta_true
eta_true
gamma_true
```

这对指标计算是必须的，但对普通方法调用是危险的。MDM、MLE、M3 推理、M1-B 推理都不应该看到真值，否则协议上存在数据泄漏风险。

建议拆成两层：

```text
estimator_runner 输入：
sample_id, n, t1...tn, method_config

metrics_runner 输入：
sample truth + predictions

label_oracle_runner 输入：
sample truth + samples + label config
```

只有以下任务允许使用真值：

1. 指标计算。
2. M1-A δ 标签搜索。
3. M1-B 残差标签生成。
4. oracle / upper-bound 对照，例如 `MDM_search_delta`。

并且这些方法必须在配置里明确标记：

```text
uses_ground_truth: true
role: label_generation / oracle_baseline
```

### 2.4 status 与 failure_reason 需要改成 status + reason_code

当前 `failure_reason` 同时承担 failed 和 outlier 的解释，语义不够准。

建议统一为：

```text
status ∈ {success, outlier, failed}
reason_code
```

规则：

- `success`：`reason_code=none`
- `outlier`：有结果，但触发异常阈值，例如 `extreme_beta_error`
- `failed`：没有可用结果，例如 `non_convergence`

建议 V1 枚举：

```text
none
not_attempted
not_attempted_due_to_dependency
exception
timeout
non_convergence
optimization_failed
unbounded_likelihood
no_intersection
nan_output
non_finite_output
invalid_parameter
numeric_overflow
constraint_violation
boundary_solution
model_missing
unknown
extreme_log_beta_error
extreme_log_eta_error
extreme_gamma_scaled_error
extreme_b_life_error
```

说明：

- MLE 当前的 `unbounded` 应映射为 `failed + unbounded_likelihood`。
- MDM 当前的 `no_intersection` 应映射为 `failed + no_intersection`。
- M1-B 因 baseline 失败无法运行，应映射为 `failed + not_attempted_due_to_dependency`。

### 2.5 predictions CSV 需要保留每个样本的完整追溯字段

建议 `predictions.csv` V1 字段为：

```text
run_id
sample_id
split
validation_type
n
method
scheme
beta_hat
eta_hat
gamma_hat
status
reason_code
runtime_ms
extra_json
```

规则：

1. 每个输入样本对每个方法必须有一行 prediction。
2. failed 行的 `beta_hat/eta_hat/gamma_hat` 留空，不写 0。
3. outlier 行保留估计值，但不进入主精度统计。
4. 方法特有字段放在 `extra_json`，但常用分组字段必须显式写入 `method/scheme`。

M1-A 的 `extra_json` 至少包含：

```json
{
  "base_method": "MDM",
  "delta_hat": 0.1,
  "delta_label": 0.12,
  "label_quality_flag": "clean",
  "uses_ground_truth": false
}
```

M1-B 的 `extra_json` 至少包含：

```json
{
  "base_method": "MDM",
  "base_scheme": "default_delta",
  "base_status": "success",
  "beta_base": 1.2,
  "eta_base": 900.0,
  "gamma_base": 80.0,
  "residual_log_beta_hat": 0.02,
  "residual_log_eta_hat": -0.01,
  "residual_gamma_scaled_hat": 0.03
}
```

M3 的 `extra_json` 至少包含：

```json
{
  "input_representation": "summary_features",
  "model_version": "m3_v1",
  "training_run_id": "benchmark_v1_m3_v1",
  "target_transform": "log_beta_log_eta_scaled_gamma",
  "loss_function": "huber_param_v1"
}
```

### 2.6 metrics_summary 需要表达统计口径

当前字段：

```text
method
scheme
validation_type
n
group_key
metric_name
metric_value
count
total_count
```

可以表达基础汇总，但不足以表达：

- success-only 指标。
- all-sample 可用性指标。
- protected MRE 排除的样本数。
- common success set。
- 指标版本。
- 分组维度。

建议 V1 字段扩展为：

```text
run_id
metric_version
method
scheme
validation_type
n
group_key
group_value
metric_scope
metric_name
metric_value
count
total_count
excluded_count
common_set_id
common_count
common_ratio
```

其中：

```text
metric_scope ∈ {success_only, all_samples, protected_mre, common_success}
```

规则：

1. 参数精度、工程寿命精度：`metric_scope=success_only`。
2. success/outlier/failure rate：`metric_scope=all_samples`。
3. B-life protected MRE：`metric_scope=protected_mre`，必须记录 `excluded_count`。
4. 跨方法主对比：`metric_scope=common_success`，必须记录 `common_set_id`。

### 2.7 run_manifest 需要记录输入输出哈希和行数

当前方案已经要求保存 run manifest，但还应明确至少包含：

```text
run_id
started_at
finished_at
status
parameter_space_id
parameter_space_config_path
parameter_space_config_hash
method_config_paths
method_config_hashes
metrics_version
code_git_commit
python_version
package_versions
sample_files
prediction_files
metrics_files
row_counts
status_counts
```

这样后续前端、组会图表、论文表格都能追溯到同一次运行。

---

## 3. 对 MDM / MLE / M1-A / M1-B / M3 的支持性检查

### 3.1 MDM

可以支持，但需要 wrapper 统一旧返回值。

当前 MDM 可能返回：

```text
beta, eta, gamma, r2, True
None, None, None, None, "no_intersection"
```

统一映射：

```text
True -> success + none
"no_intersection" -> failed + no_intersection
exception -> failed + exception
```

MDM 的不同 δ 方案用 `scheme` 区分：

```text
default_delta
best_constant_delta
search_delta_oracle
ai_delta_v1
```

### 3.2 MLE

可以支持，但必须禁止把旧返回的 `[0,0,0,0,False]` 直接写入预测值。

统一映射：

```text
True -> success + none
False -> failed + optimization_failed
"unbounded" -> failed + unbounded_likelihood
invalid_likelihood -> failed + numeric_overflow / non_finite_output
```

failed 行参数列留空。

### 3.3 M1-A

可以支持，但必须区分“标签/上界”和“可部署方法”。

对比组建议固定为：

```text
MDM_default_delta
MDM_best_constant_delta
MDM_search_delta_oracle
MDM_ai_delta
```

其中：

- `search_delta_oracle` 可以使用真值和目标指标，是研究上界，不是实际可部署方法。
- `ai_delta` 不允许使用真值，只能使用样本和模型。
- 主指标不是 `delta_mae`，而是带入 MDM 后的下游参数和 B-life 指标。

### 3.4 M1-B

可以支持，但必须显式记录 baseline 依赖。

规则：

1. baseline failed，则 M1-B 必须输出一行 `failed + not_attempted_due_to_dependency`。
2. M1-B 的 success_rate 分母仍是 total_count。
3. 修正前后比较必须能通过 `base_method/base_scheme` 追溯。
4. M1-B 必须报告 bias 和 std，因为它研究的是偏差修正。

### 3.5 M3

可以支持，但必须把输入方案和训练版本写入 `extra_json` 或显式字段。

规则：

1. 不同 `input_representation` 不得混在一起平均。
2. 不同 `model_version` 不得混在一起平均。
3. 所有纳入研究的旧 M3 方案必须按新协议重训；未重训方案只能标为历史原型。

---

## 4. 推荐的下一阶段执行顺序

不要直接实现完整框架。建议先按下面顺序走。

### Step 1：冻结指标 V2 与 benchmark 口径

产物：

```text
docs/AI辅助参数估计指标定义方案V2.md
docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md
docs/ai-research/benchmark-spec-v1.md
```

动作：

1. 将 benchmark-spec-v1 的 `success/failed` 更新为 `success/outlier/failed`。
2. 将 benchmark-spec-v1 的指标字段同步为指标 V2。
3. 明确 `split/validation_type` 的统一规则。
4. 明确 `reason_code` 枚举。

### Step 2：升级 `/help/metrics`

产物：

```text
src/app/help/metrics/page.tsx
```

但此时只更新指标规范页面，不接入新结果。

必须移除或降级：

```text
total_relative_mse
普通 gamma MRE
无保护 B-life MRE
单一综合排序指标
```

必须新增：

```text
mae_log_beta
mae_log_eta
scaled_gamma_error
B0.5/B1/B5/B10 life scaled error
protected B-life MRE
success/outlier/failed
common success set
```

### Step 3：定义公共指标函数接口

产物：

```text
python/studies/common/metrics.py
src/lib/metrics.ts
```

当前这两个文件还不存在，因此先写接口和测试规划，再实现。

最低测试：

1. `gamma_true=0` 时不产生普通 γ-MRE。
2. B-life 分位点公式正确。
3. failed/outlier 不进入参数精度统计。
4. failed/outlier 进入 total_count。
5. protected MRE 正确记录 low denominator 排除数。

### Step 4：冻结 CSV schema 和 run manifest schema

产物：

```text
samples schema
predictions schema
metrics_summary schema
run_manifest schema
```

此时仍不跑实验，只冻结字段。

### Step 5：设计 dry-run，不做全量实验

最小 dry-run：

```text
参数组合：2-3 组
n：5 和 10
mc_runs：10
方法：MDM、MLE
输出：samples、predictions、metrics_summary、run_manifest
```

验收：

1. 每个 sample 有一行 MDM prediction 和一行 MLE prediction。
2. failed/outlier/success 都能保留。
3. MLE/MDM 旧返回值不会写成 `0,0,0`。
4. metrics_summary 可追溯到 predictions。
5. 指标口径与 `/help/metrics` 一致。

### Step 6：再设计 M1-A / M1-B / M3 协议

MDM/MLE dry-run 通过后，再进入：

```text
M1-A δ 标签协议
M1-B baseline/residual 协议
M3 input/output/loss 登记协议
```

仍然不训练，先冻结协议。

---

## 5. 可复制给其他 AI 的审计提示词

```text
我正在审查 C:\weibull 项目的 AI 辅助 Weibull 参数估计统一蒙特卡洛实验框架。

请先读：
1. AGENTS.md
2. README.md
3. 02-规则.md
4. docs/AI辅助参数估计指标定义方案V2.md
5. docs/AI辅助参数估计统一蒙特卡洛实验框架方案.md
6. docs/ai-research/benchmark-spec-v1.md
7. docs/AI辅助参数估计统一蒙特卡洛框架审查意见.md

禁止读取 _archive/。
禁止训练模型。
禁止跑实验。
禁止使用旧 M1/M3 结果作为正式结论。

请只审查方案，不改代码。重点判断：

1. 指标 V2、benchmark-spec-v1、统一蒙特卡洛框架之间是否有字段或口径冲突。
2. samples.csv 是否足以追溯参数空间、seed、n、split、validation_type。
3. predictions.csv 是否能同时支持 MDM、MLE、M1-A、M1-B、M3。
4. method_runner 是否避免把 beta_true/eta_true/gamma_true 泄漏给普通估计方法。
5. status/reason_code 是否能表达 success、outlier、failed、依赖失败、MLE 无界、MDM 无交点。
6. metrics_summary 是否能表达 success_only、all_samples、protected_mre、common_success 四种统计口径。
7. run_manifest 是否足以复现实验。
8. 是否还有会导致以后“每次蒙特卡洛都重写一套”的缺口。

请输出：

- 总体结论。
- P0 必须修订项。
- P1 可后续增强项。
- 推荐的下一阶段执行顺序。
- 不建议现在做的事项。
```

---

## 6. 当前结论

当前统一蒙特卡洛框架可以作为主方向保留。

但在进入代码实现前，必须先完成四个冻结：

```text
1. 指标 V2 冻结
2. benchmark-spec-v1 与指标 V2 同步
3. samples / predictions / metrics_summary schema 冻结
4. status + reason_code 枚举冻结
```

冻结后，才适合进入最小 MDM/MLE dry-run。M1-A、M1-B、M3 的训练协议应排在 MDM/MLE dry-run 之后，而不是现在直接展开训练。
