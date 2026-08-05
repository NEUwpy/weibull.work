# Study01 产物索引

正式产物保持原路径，避免破坏 manifest、SHA256SUMS、Git LFS 和代码引用。本文件只说明当前论文如何消费，不重新命名封存目录。

## 当前论文直接使用

| 目录 | 用途 |
|---|---|
| `formal/E6_dimensional_raw/specialist/` | Dimensional-RAW 主结果、L1–L6、seed、留出和输入检查 |
| `formal/E5_normalized_raw/shared_data/` | E6 复用的 160 组合风险数据清单与哈希 |

E6 的主要事实源依次为 `summary.json`、`crossfit_layers.csv`、`model_comparison.csv`、`seed_stability.csv`、`split_report.csv`、`representation_check.json`、`manifest.json` 和 `SHA256SUMS`。

## 负向支撑实验（当前论文直接使用，作对照）

| 目录 | 用途 |
|---|---|
| `formal/pg_selector/` | 参数引导（plug-in）负向支撑实验最终包：`variant_summary.csv`、`paired_bootstrap.csv`、`summary_by_beta.csv`、`beta_cell_correctness.csv`、`prov_err_vs_delta.csv`、`summary.json`、`manifest.json`（Phase B 合同版本、run-start 溯源、WMLE worker/生产与扫描数据源哈希） |

PG 直接 plug-in 总体不能恢复 L3–L5 收益（最优单步 0.6507 vs Default 0.6304；配对 CI 全部为正）；结论作为界定主方法必要性的负向支撑证据，不与 Dimensional-RAW 排名。

## 候选或 Research

| 目录 | 当前定位 |
|---|---|
| `formal/E5_normalized_raw/` | 未采用的归一化 RAW 候选；其中 `shared_data/` 仍是 E6 数据源 |
| `candidate/E3b_RAW_specialist/` | 旧 RAW/Tabular 候选 |
| `formal/p4_formal_compare/` | Direct-MLP 与旧特征路线比较，属于 Research |

## 历史封存，不支持当前 E6 主张

`formal/E1_baseline/`、`E1_E2_crossfit/`、`E2_oracle_layers/`、`E2_beta_profile_audit/`、`E3_sample_adaptive/`、`E3b_vector_mlp/`、`E4_robustness/`、`extended_validation/`、`quantile_derivation/`、`real_data/` 等均保留用于历史复核。旧 P2/P4/分位点和 NIST 数字不得直接写成当前方法的验证结果。

## 大文件规则

- 不把被 `.gitignore` 排除的 MC 分片、逐样本预测或 checkpoint 强行加入 Git。
- 已由 Git LFS 管理的封存文件保持现状。
- 不移动、不覆盖、不重新换行或重新封存正式文件。
- 新派生结果使用独立子目录，并记录输入文件、参数、seed、命令和汇总到逐样本的对应关系。
