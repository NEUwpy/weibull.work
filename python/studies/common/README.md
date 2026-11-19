# 统一蒙特卡洛流水线说明

本目录负责后端蒙特卡洛、真值抽样和 API 现场模拟。[调用链](#调用链) · [数据契约](#数据契约) · [MDM 相关约定](#mdm-相关约定) · [对比实验要求](#对比实验要求)

## 为什么有这个目录

旧脚本曾分别实现样本生成、方法调用、数据保存和聚合，导致结果难以复现和比较。下面的入口供 API 和文件型实验共用。

## 文件职责

| 文件 | 职责 | 主要入口 |
|------|------|----------|
| `sample.py` | 依据 `seed_namespace/seed + 参数网格 + repeat_id` 确定性生成样本 | `generate_sample()` |
| `runner.py` | 经 `methods.registry.resolve_method()` 解析方法，统一调用及返回格式 | `run_method()` |
| `simulation.py` | API 现场蒙特卡洛模拟和 API 行聚合 | `simulate_method()`、`aggregate_simulation_rows()` |
| `experiment.py` | 文件型实验流水线，生成 CSV/JSON/manifest | `run_experiment()` |
| `metrics.py` | 标准指标、诊断指标、质量控制 | `aggregate_standard_metrics()` |
| `workbook.py` | 冻结 Excel 的只读桥接，保留单元格、格式、合并及样本和方法列身份，拒绝公式及不完整对应关系 | [Research00 离线登记](../../../docs/data/README.md#research00-工作簿登记2026-11-02) |

## 调用链

API 现场模拟：

```text
python/main.py /monte_carlo_simulate
  -> studies.common.simulation.simulate_method()
  -> studies.common.sample.generate_sample()
  -> studies.common.runner.run_method()
  -> methods.registry.resolve_method()
  -> python/methods/{method}.py
  -> studies.common.simulation.aggregate_simulation_rows()
  -> studies.common.metrics.aggregate_standard_metrics()
```

文件型实验：

```text
科研仓实验脚本（集中配置软件仓 python/ 路径）
  -> studies.common.experiment.run_experiment()
  -> studies.common.sample.generate_sample()
  -> studies.common.runner.run_method()
  -> studies.common.metrics.aggregate_standard_metrics()
  -> results.csv / summary.json / manifest.json
```

`python/main.py` 的现场模拟端点委托共享流程。算法调用只接受有限的正寿命观测，非法观测须明确拒绝。涉及非正观测的研究应另定适用条件，并说明与历史过滤口径的差异及可比性。

现场模拟及批量请求见[交互计算与模拟限制](../../../01-A-数据模型与接口.md#23-交互计算与模拟限制)。计算器批量估计顺序提交原样本，结果分析保留各行的失败状态并复用标准指标。

## 数据契约

[`run_experiment()`](experiment.py) 的默认产物如下。

| 文件 | 内容与口径 |
|------|------------|
| `results.csv` | 行级估计结果，保留算法返回的全部候选估计，包括边界病态候选。 |
| `summary.json` | 聚合指标，默认按质量控制后的有效行计算主指标。 |
| `manifest.json` | 记录 `code_version`、`run_label`、参数网格、样本量、重复次数、seed namespace 和指标口径。 |

当 `param_grid + n_values + repeat_id + seed_namespace` 足以复现样本时，manifest 保留样本溯源信息，样本本身默认不单独保存。必须另存原样本时，在实验文档中说明原因和体量影响。

`run_experiment(sample_provider=..., precomputed_results=...)` 接入已有观测和核验结果。缓存须匹配方法及样本 SHA-256，行级 `extra.experiment` 记录来源与实际支持下界。K–R MMLE 明确删除最小值时按保留观测检查支持域，详见[方法说明](../../../src/content/algorithms/mmle.md)。实验的 `boundary_tol` 同时传给行状态和共享汇总，默认 `1e−10`。

## 指标口径

默认主指标为 Bias、SD、RMSE 和 MAE。S2R 中位数族、MdAPE、P95 等在 [`metrics.py`](metrics.py) 的诊断结果中提供，用于观察尾部风险和异常解。公式及用途见[指标规范](../../../src/app/help/metrics/metrics-spec.ts)。全候选敏感性统计见[对比实验要求](#对比实验要求)。

## MDM 相关约定

计算器、研究、AI、单次与重复估计和程序流程共用 [`python/methods/mdm.py`](../../methods/mdm.py)。默认使用偏移量 `0.1`。现场模拟未传偏移量时会填入该值，文件型实验在方法参数中明确写入偏移量，比较其他值时传入对应设置。非负位置约束和零边界截断见 [MDM 方法说明](../../../src/content/algorithms/mdm.md)。原文差异讨论和冻结结果追溯遵循[方法实现规则](../../../02-规则.md#24-方法页面与实现维护)。

`mdm_case6.py`、`mdm_case7.py`、`mdm_case8.py`、`mdm_fine.py` 等保留历史身份。共享 runner 将 `last_solution_info` 写入行级 `extra.solution_info`，用于追踪：

- `solution_strategy`
- `root_solver`
- `constraint`
- `probe_gradient_at_zero`
- `root_bracket`
- `right_edge_extrapolation`

这类诊断信息属于行级数据，应保存在 `results.csv` 的 `extra` 字段里，不要只写进临时日志。

## 对比实验要求

NN 修正偏移量、最优偏移量或其他策略与 full-v1 对比时，复用同一 `seed_namespace`、参数网格、`n_values`、质量控制口径及[默认主指标](#指标口径)。明确标注是否包含边界病态候选解。

包含全部候选解的敏感性统计从 `results.csv` 另算，并在报告中单独标明，便于与默认 `summary.json` 的有效行口径对照。

## 新实验检查清单

检查[入口选用](#调用链)、[产物与版本](#数据契约)及[与基线的对比口径](#对比实验要求)。

## 软件与科研分仓调用

科研仓通过集中配置的软件路径直接导入 `studies.common` 与 `methods`，无需启动服务。软件和科研资料的保存边界见[软件与科研仓的边界](../../../01-结构.md#53-软件与科研仓的边界)。本仓 `studies/mdm`、`mle`、`wmle` 与 `scripts` 提供产品数据生成和维护工具。

正式实验须同时登记软件仓与科研仓的提交号；软件仓有未提交改动时一并保存。`manifest.json` 的软件版本字段不能代替科研脚本版本记录。调用设置、环境和冻结版本的使用方式以[科研仓入口](D:/weibull-research/README.md)为准。
