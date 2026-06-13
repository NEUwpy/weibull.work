# MDM 研究脚本说明

> 本目录保存 MDM 相关研究脚本。默认 MDM 算法本体仍在 `python/methods/mdm.py`，本目录不应复制或分叉生产算法实现。

## 当前默认 MDM

当前生产默认：

- 实现文件：`python/methods/mdm.py`
- 默认 offset：`0.1`
- 工程约束：`gamma >= 0`
- 负 offset-root：截断到 `gamma = 0`
- 旧式 `no_intersection` / `no_offset_root`：不再作为默认求解结果
- 历史分支：不恢复 `mdm_case6.py`、`mdm_case7.py`、`mdm_case8.py`、`mdm_fine.py` 等作为生产默认

MDM 的求解诊断由算法写入 `last_solution_info`，再由 `python/studies/common/runner.py::run_method()` 放入行级 `extra.solution_info`。

## 真值抽样入口

当前入口：

```powershell
cd D:\weibull\python
python studies/mdm/run_truth_sampling.py
python studies/mdm/run_truth_sampling.py --full
```

`run_truth_sampling.py` 只负责定义 MDM 研究的参数网格、样本量、重复次数、seed namespace、输出目录和 run label。它必须调用：

```text
python/studies/common/experiment.py::run_experiment()
```

不得在 MDM 研究脚本里重新实现：

- 样本生成
- 方法调用
- 成功/失败状态判断
- 指标聚合
- `results.csv / summary.json / manifest.json` 写出

## full-v1 baseline

`full-v1` 是研究03（最优 offset / NN 修正 offset）的当前 baseline。

产物目录：

```text
python/output/truth_sampling/full/
├── results.csv
├── summary.json
├── manifest.json
└── full_v1_report.md
```

该目录在 `python/output/` 下，属于本地实验输出，不提交到 Git。阶段总结见：

```text
docs/MDM真值抽样估计full-v1阶段总结.md
```

关键口径：

- `results.csv` 保留全部行级候选估计。
- `summary.json` 默认按质量控制后的有效行聚合 Bias、SD、RMSE、MAE。
- `manifest.json` 记录 `code_version`、`run_label`、`seed_namespace`、参数网格、样本量、重复次数和指标口径。
- 样本本身暂不单独保存，可由参数网格、样本量、repeat_id、seed namespace 确定性复现。

## 报告措辞

可以写：

```text
默认 MDM 在工程约束 gamma >= 0 下始终返回候选估计；
full-v1 未出现旧式 no_intersection / no_offset_root 无解。
```

不能写：

```text
全组 100% 有效。
```

原因是 full-v1 中存在 1 行 `right_edge_fit` 边界病态候选解。该行保留在 `results.csv`，默认 `summary.json` 的主指标按质量控制口径排除。

## 后续对比要求

NN 修正 offset、最优 offset 或其他 offset 策略若要与 full-v1 对比，必须保持：

```text
同一 seed_namespace
同一参数网格
同一 n_values
同一主指标口径
同一质量控制口径
```

如果需要比较“包含边界病态候选解”的敏感性结果，应从 `results.csv` 另算，并在报告中明确标注统计口径。
