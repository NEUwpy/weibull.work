# Study01 代码索引

`code/` 同时保留当前论文入口和历史复现代码。为保护既有导入、manifest 和运行记录，不按新叙事批量改名；以本索引区分职责。

## 当前论文核心

| 文件 | 职责 |
|---|---|
| `dim_raw_config.py` | 当前 160 组合设计、26 点 $\delta$ 网格和共享 MLP 配置 |
| `prepare_mean_normalized_main_evidence.py` | 将 E5 均值归一化折外结果重定位为 E8 正式主方法证据 |
| `analyze_e8_main_uncertainty.py` | 基于 seed 42 与 Default 的配对损失量化 Monte Carlo 不确定性和设计单元异质性 |
| `derive_e8_seed42_primary.py` | 派生固定 seed 42 的论文主报告数值 |
| `run_E8_scale_equivariance.py` | 检查“选择器→选定 $\delta$→生产 MDM”的端到端尺度等变 |
| `analyze_E1_E2_crossfit.py` | L1–L5 选点/评价分离 |
| `analyze_E10_z_only_benchmark.py` | 区分参数条件平均、可观测样本决策和 L6 事后信息的机制诊断 |
| `analyze_E11_profile_mechanism.py` | 用确认样本连接 MDM 经验梯度曲线、默认位置估计和事后低风险偏移量 |

当前代码调用项目生产 MDM 与共享样本实现，不在 Study01 内另复制估计器。

## 写作前支撑验证（B1/B2/B3，已完成）

| 文件 | 职责 |
|---|---|
| `paper_support.py` | 共享的数据读取、Default/L6 基线与指标/溯源工具 |
| `run_b1_unseen_beta.py` | 未见 $\beta$ 留出验证（8 折，per-n 网络，三 seed） |
| `run_b2_traditional_ref.py` | WMLE/LSE 同条件外部参照（同一 48,000 样本） |
| `run_b3_quantiles.py` | $x_{0.90}/x_{0.95}/x_{0.99}$ 工程分位点派生 |
| `run_pg_selector.py` | 利用初估参数选择偏移量（plug-in）的负向支撑实验：初估参数（MDM-0.1/WMLE）plug-in 到 L3–L5 条件均值曲线选 $\delta$；`--pilot-repeats N` / `--full` / `--repackage` |
| `manuscript/figures/scripts/make_submission_figures.py` | 当前论文 6 张正文图和补充图的唯一绘制入口 |

实现原则不变：复用已封存的候选损失、已有训练函数和 `python/methods/` 生产实现，不为机制诊断重跑 MDM或复制估计器；以完成当前问题的最小脚本为准，不新建通用实验控制框架。

## 历史与 Research

- `run_E3*`、`run_E4*`、旧绘图脚本：旧特征路线历史复现；
- `run_p2_*`：旧特征路线泛化；
- `run_p3_*`、`run_p4_*`：Direct-MLP/六方法 Research；
- `run_quantile_derivation.py`：旧特征路线工程分位点；
- `generate_g5_figures.py` 和旧 `plot_fig*`：旧 G5 图表，不是当前终稿绘图入口。

不要仅为目录整洁删除或重命名这些文件；它们仍与已封存产物相互引用。
