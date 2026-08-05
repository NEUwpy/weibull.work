# Study01 代码索引

`code/` 同时保留当前论文入口和历史复现代码。为保护既有导入、manifest 和运行记录，不按新叙事批量改名；以本索引区分职责。

## 当前论文核心

| 文件 | 职责 |
|---|---|
| `dim_raw_config.py` | 当前 160 组合设计、26 点 $\delta$ 网格和 MLP 配置 |
| `run_E6a_data_inventory.py` | 核对共享损失数据 |
| `run_E6b_dimensional_raw_specialist.py` | 当前主方法训练、评价和汇总 |
| `run_E6b_smoke.py` | 当前方法端到端 smoke |
| `analyze_E1_E2_crossfit.py` | L1–L5 选点/评价分离 |
| `finalize_e6_manifest.py` | E6 provenance 收口 |

当前代码调用项目生产 MDM 与共享样本实现，不在 Study01 内另复制估计器。

## 待补验证应复用的能力

- 未见 $\beta$：复用 E6 训练函数、现有风险数据和 per-n 模型，不重跑 MDM。
- 工程分位点：复用现有候选估计并按 E6 的 `selected_delta` 取对应参数。
- WMLE/LSE：调用 `python/methods/` 当前生产实现，不复制传统估计器。

实现以完成当前问题的最小脚本为准。除非出现第二个明确使用者，不新建通用实验控制框架。

## 历史与 Research

- `run_E3*`、`run_E4*`、旧绘图脚本：旧特征路线历史复现；
- `run_p2_*`：旧特征路线泛化；
- `run_p3_*`、`run_p4_*`：Direct-MLP/六方法 Research；
- `run_quantile_derivation.py`：旧特征路线工程分位点；
- `generate_g5_figures.py` 和旧 `plot_fig*`：旧 G5 图表，不是当前终稿绘图入口。

不要仅为目录整洁删除或重命名这些文件；它们仍与已封存产物相互引用。
