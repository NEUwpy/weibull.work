# 统一蒙特卡洛流水线说明

> 本目录是后端蒙特卡洛、真值抽样、API 现场模拟的共享基础设施。以后不要再为一次实验、一个方法或一个 API 入口重新写一套抽样、方法调用、指标聚合逻辑。

## 为什么有这个目录

旧流程的问题是：蒙特卡洛经常“用一次写一次”，不同脚本各自生成样本、调用方法、保存数据、计算指标。这样会带来三类维护风险：

- 方法调用不一致：同一个方法在 API、研究脚本、适用范围数据里可能走不同参数或不同失败处理。
- 数据保存不一致：有的实验只留聚合结果，有的留行级数据，有的缺少 manifest，后续无法复现。
- 评价标准不一致：S2R、MdAPE、P95、RMSE 等指标在不同地方各说各话，难以横向比较。

当前统一后的规则是：**抽样、方法调用、指标聚合、结果保存都从本目录进入。**

## 文件职责

| 文件 | 职责 | 主要入口 |
|------|------|----------|
| `sample.py` | 确定性样本生成 | `generate_sample()` |
| `runner.py` | 统一方法解析、实例化、调用和返回格式标准化 | `run_method()` |
| `simulation.py` | API 现场蒙特卡洛模拟和 API 行聚合 | `simulate_method()`、`aggregate_simulation_rows()` |
| `experiment.py` | 文件型实验流水线，生成 CSV/JSON/manifest | `run_experiment()` |
| `metrics.py` | 标准指标、诊断指标、质量控制 | `aggregate_standard_metrics()` |

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
python/studies/{method}/run_*.py
  -> studies.common.experiment.run_experiment()
  -> studies.common.sample.generate_sample()
  -> studies.common.runner.run_method()
  -> studies.common.metrics.aggregate_standard_metrics()
  -> results.csv / summary.json / manifest.json
```

`python/main.py` 是 API 层，不应继续堆叠蒙特卡洛主循环、抽样逻辑或指标聚合逻辑。

## 数据契约

`run_experiment()` 的默认输出是：

| 文件 | 用途 | 规则 |
|------|------|------|
| `results.csv` | 主数据，行级估计结果 | 保留所有算法返回的候选估计，适合 Excel、pandas、R 后续分析 |
| `summary.json` | 默认聚合指标 | 按质量控制后的有效行计算 Bias、SD、RMSE、MAE |
| `manifest.json` | 溯源信息 | 记录 code_version、run_label、参数网格、样本量、重复次数、seed namespace、指标口径 |

样本本身默认不单独保存。只要 `param_grid + n_values + repeat_id + seed_namespace` 足以确定性复现，就由 manifest 记录溯源。若后续实验必须保存样本，需在实验说明中写明原因。

## 指标口径

默认主指标：

```text
Bias / SD / RMSE / MAE
```

S2R 中位数族、MdAPE、P95 等保留为 diagnostics，用来观察尾部风险和异常解，不作为默认主排序口径。

`summary.json` 的主指标默认按质量控制后的有效行聚合。若研究需要“包含所有候选解”的敏感性统计，应从 `results.csv` 另算，并在报告中明确标注该口径不同于默认 summary。

## MDM 相关约定

MDM 的生产默认实现只在 `python/methods/mdm.py`。共享 runner 会把 MDM 的 `last_solution_info` 写入行级 `extra.solution_info`，用于追踪：

- `solution_strategy`
- `root_solver`
- `constraint`
- `probe_gradient_at_zero`
- `root_bracket`
- `right_edge_extrapolation`

这类诊断信息属于行级数据，应保存在 `results.csv` 的 `extra` 字段里，不要只写进临时日志。

## 新实验检查清单

```
□ 是否使用 generate_sample() 生成样本？
□ 是否使用 run_method() 调用方法？
□ 是否使用 aggregate_standard_metrics() 聚合指标？
□ 文件型实验是否使用 run_experiment() 输出 results.csv / summary.json / manifest.json？
□ 是否记录 run_label、code_version、seed_namespace、参数网格和指标口径？
□ 与 baseline 对比时，是否使用同一 seed_namespace、同一参数网格、同一质量控制口径？
```
