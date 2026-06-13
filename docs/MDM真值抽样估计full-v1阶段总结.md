# MDM 真值抽样估计 full-v1 阶段总结

> 当前阶段封版记录。详细产物位于 `python/output/truth_sampling/full/`，该目录为本地实验输出，不提交到 Git。

## 1. 本阶段完成内容

- 蒙特卡洛公共流水线已收束到 `python/studies/common/`：
  - `sample.py`：确定性样本生成；
  - `runner.py`：统一方法调用，并把 MDM `last_solution_info` 写入行级 `extra.solution_info`；
  - `experiment.py`：统一生成 `results.csv`、`summary.json`、`manifest.json`。
- 新增 MDM 真值抽样入口：
  - `python/studies/mdm/run_truth_sampling.py`
  - pilot 与 full 均调用 `run_experiment()`，不复写抽样、方法调用或指标聚合逻辑。
- 默认 MDM 仍只使用 `python/methods/mdm.py`，不恢复历史分支实现。

## 2. full-v1 产物

产物目录：

```text
python/output/truth_sampling/full/
├── results.csv
├── summary.json
├── manifest.json
└── full_v1_report.md
```

`manifest.json` 关键字段：

| 字段 | 值 |
|------|-----|
| `code_version` | `2e40d3f` |
| `run_label` | `full-v1` |
| `seed_namespace` | `2026` |
| `total_rows` | `15000` |
| `R_levels` | `[0.95, 0.99]` |
| `diagnostic_R_levels` | `[0.5, 0.9, 0.95, 0.99, 0.999]` |

## 3. 数据格式约定

- `results.csv` 是主数据，保留全部行级候选估计，适合 Excel、pandas、R 后续分析。
- `summary.json` 是默认聚合结果，当前按质量控制后的有效行计算标准指标。
- `manifest.json` 只记录小体量溯源信息，不承载行级结果。
- 样本本身暂不单独保存；样本可由 `param_grid + n_values + repeat_id + seed_namespace` 确定性复现。

## 4. full-v1 核心结论

- 默认 MDM 在 full-v1 的 15000 次运行中全部返回候选估计。
- 未出现旧式 `no_intersection` / `no_offset_root` 无解。
- 行级求解信息：
  - `solution_strategy`: `brent_root=10592`, `truncated_at_zero=4408`
  - `root_solver`: `brent=10591`, `right_edge_fit=1`, `none=4408`
- 其中 1 行为 `right_edge_fit` 边界病态候选解：
  - 参数组合：`beta=3.0, eta=100, gamma=5.0, n=10, repeat_id=181`
  - 表现：`beta_hat` 触及上界，`gamma_hat` 贴近样本最小值，`r_squared` 极差。
  - 处理：原始行保留在 `results.csv`；默认 `summary.json` 的主指标聚合按质量控制口径排除。

因此推荐写法是：

```text
默认 MDM 在工程约束 gamma >= 0 下始终返回候选估计；
full-v1 未出现旧式无解。标准评价口径可按研究目的选择是否排除边界病态候选解。
```

## 5. 当前报告口径

- 生成阶段：保留所有候选解，不删除病态行。
- 默认统计阶段：`summary.json` 使用质量控制后的有效行计算 Bias、SD、RMSE、MAE。
- 如需研究“全部候选解含病态”的敏感性结果，应从 `results.csv` 另算，并在报告中明确标注统计口径。

## 6. 下一步

- 将 full-v1 作为研究 03（最优 offset / NN 修正 offset）的 baseline。
- 后续比较 NN 修正结果时，必须同时说明：
  - 是否使用质量过滤；
  - 是否保留 `right_edge_fit` 病态候选；
  - 指标是否来自同一 `seed_namespace` 和同一参数网格。

