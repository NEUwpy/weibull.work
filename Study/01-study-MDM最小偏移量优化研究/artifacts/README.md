# Study01 产物索引

正式产物保持原路径，避免破坏 manifest、SHA256SUMS、Git LFS 和代码引用。本文件只说明当前论文如何消费，不重新命名封存目录。

## 当前论文直接使用

| 目录 | 用途 |
|---|---|
| `formal/E8_mean_normalized_selector/` | 均值归一化主方法、seed 42 主报告、未见 $\beta$、可靠度寿命与尺度等变检查 |
| `formal/E5_normalized_raw/shared_data/` | E8 复用的 160 组合风险数据清单与哈希 |
| `formal/E10_z_only_benchmark/` | 参数条件、可观测样本规则与 L6 事后信息的机制诊断 |
| `formal/E11_profile_mechanism/` | 20 个预设参数单元内的 MDM 梯度曲线与样本实现机制诊断 |

E8 的主方法事实源为 `specialist/`、`seed42_primary/`、`unseen_beta/`、`quantiles/` 和 `scale_equivariance/` 下的 summary/manifest/SHA256SUMS。E10 机制事实源为 `confirmation_sample_losses.csv`、`confirmation_by_method.csv`、`mechanism_by_cell.csv`、`paired_repeat_bootstrap.csv`、`learning_curve.csv`、`summary.json` 和 `SHA256SUMS`。E11 的梯度机制事实源为 `sample_metrics.csv`、`cell_associations.csv`、`conditional_loss_curves.csv`、`representative_gradient_curves.csv`、`summary.json` 和 `SHA256SUMS`。

## 负向支撑实验（当前论文直接使用，作对照）

| 目录 | 用途 |
|---|---|
| `formal/pg_selector/` | 利用初估参数选择偏移量（plug-in）的负向支撑实验最终包：`variant_summary.csv`、`paired_bootstrap.csv`、`summary_by_beta.csv`、`beta_cell_correctness.csv`、`prov_err_vs_delta.csv`、`summary.json`、`manifest.json`（Phase B 合同版本、run-start 溯源、WMLE worker/生产与扫描数据源哈希） |

PG 直接 plug-in 总体不能恢复 L3–L5 收益（最优单步 0.6507 vs Default 0.6304；配对 CI 全部为正）；结论作为主方法的负向支撑证据，不与 Mean-Normalized-MLP 作无协议排名。

## 候选或 Research

| 目录 | 当前定位 |
|---|---|
| `formal/E6_dimensional_raw/` | 固定尺度下的有量纲 RAW 敏感性/历史对照；`traditional_ref/` 仍被当前论文使用 |
| `candidate/E3b_RAW_specialist/` | 旧 RAW/Tabular 候选 |
| `formal/p4_formal_compare/` | Direct-MLP 与旧特征路线比较，属于 Research |

## 历史封存，不支持当前 E8/E10/E11 主张

`formal/E1_baseline/`、`E1_E2_crossfit/`、`E2_oracle_layers/`、`E2_beta_profile_audit/`、`E3_sample_adaptive/`、`E3b_vector_mlp/`、`E4_robustness/`、`extended_validation/`、`quantile_derivation/`、`real_data/` 等均保留用于历史复核。旧 P2/P4/分位点和 NIST 数字不得直接写成当前方法的验证结果。

## 大文件规则

- 不把被 `.gitignore` 排除的 MC 分片、逐样本预测或 checkpoint 强行加入 Git。
- 已由 Git LFS 管理的封存文件保持现状。
- 不移动、不覆盖、不重新换行或重新封存正式文件。
- 新派生结果使用独立子目录，并记录输入文件、参数、seed、命令和汇总到逐样本的对应关系。
