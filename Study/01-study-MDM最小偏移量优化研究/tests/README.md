# 当前证据核验

实验定义见[配置文档](../02-实验配置.md)。测试用于关键口径与已有产物核对，不自动触发完整训练或候选扫描。

| 实验 | 相关已有测试 |
|---|---|
| [S01-01](../02-实验配置.md#s01-01) | 当前稿件/图件检查与已保存的风险分解 QA；不把图像格式验收当作科学复算 |
| [S01-02](../02-实验配置.md#s01-02) | [test_e13_beta_domain_sensitivity.py](test_e13_beta_domain_sensitivity.py) |
| [S01-03/04](../02-实验配置.md#s01-03) | [test_mean_normalized_confirmation.py](test_mean_normalized_confirmation.py)、[test_e8_seed42_primary.py](test_e8_seed42_primary.py)、[test_e8_main_uncertainty.py](test_e8_main_uncertainty.py) |
| S01-04 表示来历 | [test_scale_invariant_input_screen.py](test_scale_invariant_input_screen.py) |
| [S01-05](../02-实验配置.md#s01-05) | [test_profile_mechanism.py](test_profile_mechanism.py)、[test_z_only_benchmark.py](test_z_only_benchmark.py) |
| [S01-06](../02-实验配置.md#s01-06) | [test_mean_normalized_confirmation.py](test_mean_normalized_confirmation.py)、[test_paper_evidence.py](test_paper_evidence.py)；后者含旧有量纲参照，按其合同理解 |
| [S01-07](../02-实验配置.md#s01-07) | [test_pg_selector.py](test_pg_selector.py) |
| [S01-08](../02-实验配置.md#s01-08) | [test_delta_upper_boundary.py](test_delta_upper_boundary.py) |

2026-09-07 清理验收已运行 seed42、不确定性、profile、Z-only、E13、E12 六个测试文件，共 30 项通过，详见[当次验证记录](../snapshots/2026-09-07/validation.json)。这不是整个 tests 目录的通过声明。

旧 test_p2/test_p3/test_p4、旧标签与分位点测试属于历史路线，可能需要已退出活动目录的数据；不再作为当前论文默认验收集。环境和代码入口见[代码说明](../code/README.md)。文档重编号主要检查配置事实、链接/锚点、图表映射和现有数值不变，无需为新编号增加算法测试。
