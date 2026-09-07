# 当前证据目录

证据按[实验配置 S01-01—S01-08](../02-实验配置.md)理解，章节消费位置见[证据索引](../01-证据索引.md)。目录名是既有来源标识，不按新编号搬动或重新封存。

| 实际目录 | 当前实验 | 保留用途 |
|---|---|---|
| `formal/E5_normalized_raw/` | [共用数据、S01-04](../02-实验配置.md#common) | 160 单元候选扫描、源选择结果、模型与哈希 |
| `exploratory/offset_mechanism_scan_20260905/` | [S01-01](../02-实验配置.md#s01-01)、S01-05a 图7派生 | 当前正文已使用的风险分解与同样本候选损失；exploratory 是来源名 |
| `formal/E13_beta_domain_sensitivity/` | [S01-02](../02-实验配置.md#s01-02) | 参数域平移与实际风险格点 |
| `formal/E6_dimensional_raw/` | [S01-03](../02-实验配置.md#s01-03)、[S01-06b](../02-实验配置.md#s01-06b) | 当前层级表、传统参照及必要依赖；RAW 自身只作敏感性 |
| `formal/E8_mean_normalized_selector/` | [S01-04](../02-实验配置.md#s01-04)、[S01-06](../02-实验配置.md#s01-06) | seed42 主报告、不确定性、未见 β、寿命及尺度 |
| `formal/E11_profile_mechanism/`、`formal/E10_z_only_benchmark/` | [S01-05](../02-实验配置.md#s01-05) | 样本轨迹、条件风险与信息参照 |
| `formal/pg_selector/` | [S01-07](../02-实验配置.md#s01-07) | 初估查表的完整负结果 |
| `candidate/E12_delta_upper_boundary/` | [S01-08](../02-实验配置.md#s01-08) | 附录的选择性上界诊断 |
| `candidate/E7_scale_invariant_input_screen/` | [S01-04](../02-实验配置.md#s01-04) | 表示选择来历，不是独立主确证 |

其余保留的小型旧 E1/E2/figures 包仅供历史追溯，不能代替当前 160 单元结果。旧 shared_data 与当前 E5/shared_data 是不同设计。

已退出主线的 P4/P2/E3/E4/E9、pilot 与旧真实数据等不再保留活动运行。试错结果、恢复版本和清理范围见[认识快照](../07-认识清单与研究快照-20260907.md)。当前新增编号不改原数值、文件哈希或模型身份。
