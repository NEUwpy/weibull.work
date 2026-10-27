# AI 辅助参数估计统一蒙特卡洛实验框架方案

> 日期：2026-05-19
> 状态：方案草案。用于统一后续传统方法、AI 方法、适用范围、训练数据、测试数据和可视化结果的数据生成流程。
> 上游文档：
> - `docs/AI辅助参数估计重做简明路线图.md`
> - `docs/AI辅助参数估计指标定义方案V2.md`

---

## 1. 为什么需要统一蒙特卡洛框架

当前项目已有很多蒙特卡洛、训练数据和适用范围数据，但问题是：

```text
1. 不同方法各写各的生成脚本。
2. CSV 字段不统一。
3. 有些失败结果写成 0,0,0 或 NaN，没有明确 status。
4. 有些数据没有 sample_id 和 seed，无法追溯。
5. 指标在单个模块里临时计算，口径不统一。
6. 传统方法和 AI 方法常常不是在同一测试集上比较。
7. 每次新增实验都重新写一套蒙特卡洛，越写越乱。
```

因此需要一个统一框架，让以后所有实验都按同一条链路走。

---

## 2. 框架目标

统一蒙特卡洛框架要解决五件事：

```text
1. 样本怎么生成。
2. 参数空间怎么定义。
3. 方法怎么被调用。
4. 结果怎么保存。
5. 指标怎么统计。
```

最终目标：

```text
同一个样本集，可以被 MDM、MLE、M1-A、M1-B、M3 等方法共同使用。
所有方法输出同一种 prediction CSV。
所有指标由统一指标函数计算。
前端和组会图表只读取统一结果。
```

---

## 3. 总流程

统一流程如下：

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

这条链路以后不能绕过。

---

## 4. 建议目录结构

建议新建统一实验目录：

```text
python/experiments/
├── configs/
│   ├── parameter_spaces/
│   │   └── benchmark_v1.yaml
│   ├── methods/
│   │   ├── mdm.yaml
│   │   ├── mle.yaml
│   │   ├── m1_a_delta.yaml
│   │   ├── m1_b_residual.yaml
│   │   └── m3_direct.yaml
│   └── runs/
│       └── benchmark_v1_dry_run.yaml
│
├── common/
│   ├── sample_generator.py
│   ├── method_runner.py
│   ├── result_schema.py
│   ├── status.py
│   └── io.py
│
├── runs/
│   └── benchmark_v1/
│       ├── samples/
│       ├── predictions/
│       ├── metrics/
│       └── logs/
│
└── README.md
```

说明：

- `configs/parameter_spaces/` 只管参数空间。
- `configs/methods/` 只管方法调用配置。
- `configs/runs/` 组合参数空间和方法，定义一次实验。
- `common/` 放统一生成、调用、保存、状态判断逻辑。
- `runs/` 放实际实验产物。

---

## 5. 参数空间配置规范

参数空间建议单独成文件，例如：

```text
python/experiments/configs/parameter_spaces/benchmark_v1.yaml
```

示例：

```yaml
id: benchmark_v1
description: AI 参数估计重做第一版 benchmark

distribution:
  type: weibull_3p

splits:
  train:
    beta: [0.5, 1.0, 2.0, 3.0, 5.0]
    eta: [100.0, 500.0, 1000.0, 3000.0, 5000.0]
    gamma: [50.0, 100.0, 200.0, 1000.0]
    n: [5, 7, 10, 15]
    mc_runs: 500
    seed_start: 1

  val:
    beta: [0.5, 1.0, 2.0, 3.0, 5.0]
    eta: [100.0, 500.0, 1000.0, 3000.0, 5000.0]
    gamma: [50.0, 100.0, 200.0, 1000.0]
    n: [5, 7, 10, 15]
    mc_runs: 100
    seed_start: 300000

  ig:
    inherits: train
    mc_runs: 100
    seed_start: 100000

  ip:
    beta: [0.75, 1.5, 2.5, 4.0]
    eta: [300.0, 750.0, 2000.0, 4000.0]
    gamma: [75.0, 150.0, 600.0]
    n: [5, 7, 10, 15]
    mc_runs: 100
    seed_start: 600000

  ex:
    beta: [0.3, 8.0, 10.0]
    eta: [50.0, 8000.0, 10000.0]
    gamma: [10.0, 300.0, 1500.0]
    n: [5, 7, 10, 15]
    mc_runs: 100
    seed_start: 1100000

filters:
  - gamma_true < eta_true
```

目标：

```text
以后改参数空间，只改配置，不改生成脚本。
```

---

## 6. 样本 CSV 规范

统一样本输出为 CSV。

文件名：

```text
samples_{split}_n{n}.csv
```

字段：

```text
sample_id
split
validation_type
seed
n
beta_true
eta_true
gamma_true
t1
t2
...
tn
```

规则：

- `sample_id` 全局唯一。
- `seed` 必须记录实际生成样本所用种子。
- 每条样本内 `t1...tn` 升序。
- `train`、`val`、`ig`、`ip`、`ex` 的 seed 不能重复。
- `validation_type` 对 train/val 可为空，对测试集必须是 `ig/ip/ex`。

推荐 `sample_id`：

```text
benchmark_v1_{split}_n{n}_combo{combo_index}_mc{mc_index}
```

---

## 7. 方法调用接口规范

所有传统方法和 AI 方法都必须包装成统一接口。

统一输入：

```text
sample_id
n
beta_true
eta_true
gamma_true
t1...tn
method_config
```

统一输出：

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
extra_json
```

其中：

- `method` 表示方法大类，如 `MDM`、`MLE`、`M1_A_delta`、`M1_B_residual`、`M3_direct`。
- `scheme` 表示具体方案，如 `default_delta`、`ai_delta_v1`、`summary_features`。
- `extra_json` 放方法特有字段，例如 δ、模型版本、输入方案、损失函数。

---

## 8. 方法配置规范

方法配置单独成文件。

示例：`mdm.yaml`

```yaml
method: MDM
scheme: default_delta

parameters:
  delta: 0.1
  gamma_steps: 60
  rank_method: bernard

output:
  beta_hat: true
  eta_hat: true
  gamma_hat: true
  runtime_ms: true
  status: true
```

示例：`m1_a_delta.yaml`

```yaml
method: M1_A_delta
scheme: ai_delta_v1

base_method: MDM

model:
  path: python/models/m1_a_delta/model.pth
  input_representation: sorted_sample

mdm_parameters:
  gamma_steps: 60
  rank_method: bernard
```

目标：

```text
方法怎么跑，由配置说明；
runner 只负责按统一接口调用。
```

---

## 9. predictions CSV 规范

每个方法输出统一预测文件。

文件名：

```text
predictions_{method}_{scheme}_{validation_type}_n{n}.csv
```

字段：

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
extra_json
```

状态：

```text
status ∈ {success, outlier, failed}
```

失败原因建议枚举：

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

规则：

- 每个输入样本必须有一条输出记录。
- 失败样本不能删除。
- 失败样本必须写 `status=failed` 和 `failure_reason`。
- 异常估计写 `status=outlier`。
- 成功样本写 `status=success`。

---

## 10. 指标汇总规范

指标由统一指标函数计算。

文件名：

```text
metrics_summary.csv
```

字段：

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

可选字段：

```text
metric_scope
metric_version
common_count
common_ratio
```

规则：

- 参数精度只统计 `status=success`。
- 工程寿命精度只统计 `status=success`。
- success/outlier/failure rate 统计全部样本。
- 跨方法主对比应支持共同成功集 `_common` 指标。

---

## 11. 运行配置规范

一次实验运行由 run config 定义。

示例：

```yaml
id: benchmark_v1_dry_run
parameter_space: benchmark_v1

splits:
  - val
  - ig

methods:
  - method_config: mdm.yaml
  - method_config: mle.yaml

outputs:
  root: python/experiments/runs/benchmark_v1_dry_run
  write_samples: true
  write_predictions: true
  write_metrics: true

metrics:
  version: metrics_v2
```

目标：

```text
以后每次实验都能从 run config 复现。
```

---

## 12. 日志和可追溯性

每次运行必须保存：

```text
run_config.yaml
parameter_space.yaml
method_config.yaml
metrics_version
started_at
finished_at
git_commit 可选
python_version 可选
package_versions 可选
```

建议输出：

```text
run_manifest.json
```

用于记录本次实验所有输入、输出、配置和文件路径。

---

## 13. 与前端页面的关系

前端页面不再直接读取各种临时 JSON。

前端应该读取统一结果：

```text
samples.csv
predictions.csv
metrics_summary.csv
run_manifest.json
```

页面必须能说明：

```text
数据来自哪个 run
参数空间是什么
方法配置是什么
指标版本是什么
失败样本怎么算
```

---

## 14. 和旧系统的关系

旧的 `public/studies/{method}/chunks/` 不立刻删除。

处理方式：

```text
1. 保留旧数据作为历史页面和原型展示。
2. 新研究结果使用统一蒙特卡洛框架生成。
3. 后续逐步迁移旧适用范围数据。
4. 未迁移前，页面必须区分“旧数据”和“新 benchmark 数据”。
```

---

## 15. 最小 dry-run 建议

正式重训前，先做最小 dry-run。

目标：

```text
验证统一框架能跑通，而不是追求结果规模。
```

建议：

```text
参数组合：2-3 组
n：5 和 10
mc_runs：10
方法：MDM、MLE
输出：samples、predictions、metrics_summary
```

验收：

```text
1. 每条 sample 有 sample_id 和 seed。
2. 每条 sample 对每个方法都有 prediction。
3. failed/outlier/success 都能记录。
4. 指标函数能生成 metrics_summary。
5. 页面或 notebook 能读 metrics_summary 画最简单图。
```

---

## 16. 下一步

如果本方案通过，下一步应该：

1. 把本方案交给其他 AI 或人工审查。
2. 敲定 `metrics_v2` 指标规范。
3. 敲定 `benchmark_v1` 参数空间配置。
4. 设计 `sample_generator`、`method_runner`、`metrics_runner` 的接口。
5. 先跑 MDM/MLE dry-run。
6. 再进入 M1-A、M1-B、M3 的训练与重算。

