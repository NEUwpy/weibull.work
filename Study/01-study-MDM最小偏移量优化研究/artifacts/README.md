# Study01 当前产物

2026-09-07 按作者要求清理旧试错运行。研究判断、试错结果和恢复说明见[认识清单](../07-认识清单与研究快照-20260907.md)。本目录保留当前稿件所需证据及其依赖，不再默认积累已退出主线的实验。

| 保留目录 | 用途 |
|---|---|
| `formal/E5_normalized_raw/` | 当前 160 单元扫描、源选择结果及模型；E8 和绘图程序仍依赖，不能因命名旧而删除 |
| `formal/E6_dimensional_raw/` | 传统方法参照、信息层级与当前依赖；有量纲方法只作敏感性对照 |
| `formal/E8_mean_normalized_selector/` | 当前主结果、seed 42、未见 β、寿命点、尺度等变与不确定性 |
| `formal/E10_z_only_benchmark/`、`E11_profile_mechanism/`、`E13_beta_domain_sensitivity/` | 条件信息、样本机制及参数域变化证据 |
| `formal/pg_selector/` | 当前附录使用的 plug-in 负结果 |
| `candidate/E7_scale_invariant_input_screen/` | 当前表示选择来历及 E8 生成依赖 |
| `candidate/E12_delta_upper_boundary/` | 当前附录的上界敏感性证据 |
| 其余少量 E1/E2、figures 与 exploratory 汇总 | 历史认识或图表来源；不当作新任务，数字按原合同解释 |

已退出活动目录：旧 `p4_formal_compare`、`extended_validation`、`shared_data`、E3/E3b/E4、旧真实数据和寿命派生、旧上界试验、RAW/E9 候选及 `pilot/`。其中旧 `formal/shared_data` 与保留的 `formal/E5_normalized_raw/shared_data` 是两套设计；当前图表使用后者。

试错结果已合并到[紧凑摘要](../snapshots/2026-09-07/retired-results.json)。恢复旧生成数据不是日常维护任务；确有需要时依据清理前 Git 标签和代码重跑，或取回一次性快照。当前保留的正式证据不改数值、不重新封存。
