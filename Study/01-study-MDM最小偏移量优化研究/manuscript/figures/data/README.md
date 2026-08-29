# 数据来源

本目录不复制大规模实验数据。所有图表通过 `../figure_sources.json` 指向 `D:/weibull` 中的正式数据或计算后结果。

| 数据块 | 路径 | 主要用途 |
|---|---|---|
| Monte Carlo 损失扫描 | `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E5_normalized_raw/shared_data/` | 图 1 及逐参数表；160 组合、48,000 样本、26 个候选偏移量。图 1 稳定性按组合内 300 次重复计算 |
| 参数域敏感性 | `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E13_beta_domain_sensitivity/` | 图 3 的 11 个固定宽度 $\beta$ 参数域、26 点原始 $J_1$ 风险曲线和离散最低点 |
| 信息空间定义 | `data/derived/fig4_information_space_cells.csv` | 图 4 的 160 个设计单元及 L1–L5 分组标识；由正式设计水平机械派生，不包含性能值 |
| 信息层级结果 | `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E6_dimensional_raw/paper/table1_l1_l6.csv` | 图 5 的 Default 与 L1–L6 pooled、分 $n$ 风险及相对降幅；与正文表 2 为同一数值源 |
| 均值归一化主结果 | `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E8_mean_normalized_selector/specialist/` | 图 2 方法配置依据、图 6–7、主结果表和随机种子结果 |
| 均值归一化折外选择 | `.../E5_normalized_raw/specialist/` | 图 6–7 的逐样本派生数据；源提交与哈希由 E8 manifest 绑定 |
| 未见 beta 验证 | `.../E8_mean_normalized_selector/unseen_beta/` | 支撑验证表、未见 beta 图表 |
| 传统方法参照 | `.../E6_dimensional_raw/traditional_ref/` | WMLE/LSE 图表 |
| 工程分位点 | `.../E8_mean_normalized_selector/quantiles/` | x0.90/x0.95/x0.99 图表 |
| 尺度等变检查 | `.../E8_mean_normalized_selector/scale_equivariance/` | 选择器→生产 MDM 的 4 样本×3 尺度检查 |

优先读取汇总文件 `summary.json`、`summary.csv`、`crossfit_layers.csv`、`seed_stability.csv` 和 `beta_holdout.csv`。只有需要重新派生曲线或核查单样本结果时，才读取 MC chunks 或逐样本文件。

正式数据受仓库内 manifest 与 SHA256SUMS 约束；本写作目录中的图像只是稿件副本，不能反过来作为科学数据源。
