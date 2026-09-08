# 当前代码与复现入口

> 2026-09-08：本轮仅做AMDM规划。现有入口不构成下一阶段任务；待审工作与数据见[10](../10-实验与数据补充规划.md)。本目录下旧 _ch5_*、_fig* Markdown 是历史审计/图形合同，不是当前执行计划。

按[实验配置](../02-实验配置.md)选择入口。这里区分扫描、训练、派生与作图，避免运行旧主程序时启动另一条实验路线。

| 实验 | 代码入口 | 实际操作 |
|---|---|---|
| [共用配置](../02-实验配置.md#common) | [dim_raw_config.py](dim_raw_config.py)、[paper_support.py](paper_support.py) | 当前网格与共享扫描读取；config.py 是旧网格 |
| [S01-01](../02-实验配置.md#s01-01) | [scan_offset_bias_variance.py](scan_offset_bias_variance.py) | 从保留扫描派生风险分解，不训练 |
| [S01-02](../02-实验配置.md#s01-02) | [analyze_E13_beta_domain_sensitivity.py](analyze_E13_beta_domain_sensitivity.py) | 复用原格点；缺新增 β 分片时需补扫描，再汇总 |
| [S01-03](../02-实验配置.md#s01-03) | [run_E6b_dimensional_raw_specialist.py](run_E6b_dimensional_raw_specialist.py) 的 run_crossfit_layers | 调用 [run_crossfit](analyze_E1_E2_crossfit.py) 处理当前数据；不要运行旧 crossfit main，也无需启动整个 E6 训练 |
| [S01-04](../02-实验配置.md#s01-04) | [prepare_mean_normalized_main_evidence.py](prepare_mean_normalized_main_evidence.py)、[derive_e8_seed42_primary.py](derive_e8_seed42_primary.py) | 已有源结果整理与固定 seed42 派生；不训练 |
| S01-04 不确定性 | [analyze_e8_main_uncertainty.py](analyze_e8_main_uncertainty.py) | 配对损失重采样，不训练 |
| S01-04 表示与训练复现 | [run_E7_scale_invariant_input_screen.py](run_E7_scale_invariant_input_screen.py) | 均值/SD/RMS 表示训练实现；完整 main 会筛多个表示，不作为日常任务 |
| [S01-05](../02-实验配置.md#s01-05) | [analyze_E11_profile_mechanism.py](analyze_E11_profile_mechanism.py)、[analyze_E10_z_only_benchmark.py](analyze_E10_z_only_benchmark.py) | 前者重建轨迹；后者拟合/选模/重拟合后确认 |
| [S01-06a](../02-实验配置.md#s01-06a) | [run_b1_mean_normalized_unseen_beta.py](run_b1_mean_normalized_unseen_beta.py) | 归一化模型的 β 留出训练；run_b1_unseen_beta.py 只作为其依赖 |
| [S01-06b](../02-实验配置.md#s01-06b) | [run_b2_traditional_ref.py](run_b2_traditional_ref.py) | 生产 WMLE/LSE 同样本计算；核对归档实现版本 |
| [S01-06c](../02-实验配置.md#s01-06c) | [derive_mean_normalized_quantiles.py](derive_mean_normalized_quantiles.py) | 由当前选点派生寿命；旧 run_b3_quantiles.py 不是当前主入口 |
| [S01-06d](../02-实验配置.md#s01-06d) | [check_mean_normalized_e2e_scale.py](check_mean_normalized_e2e_scale.py) | 历史最终模型的12次端到端尺度检查 |
| [S01-07](../02-实验配置.md#s01-07) | [run_pg_selector.py](run_pg_selector.py) | --full 为全量已完成路线；--repackage 派生；pilot 不是新任务 |
| [S01-08](../02-实验配置.md#s01-08) | [analyze_E12_delta_upper_boundary.py](analyze_E12_delta_upper_boundary.py) | 仅选定样本的候选上界补算 |

## 当前环境与使用方式

2026-09-07 当前证据测试通过的 Python 为 `C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`，包含 numpy/pandas/scipy/scikit-learn/pytest。项目 `python/.venv` 当时缺 scikit-learn，不能直接用它声称复现环境完整。历史运行版本仍以各 manifest 为准；本地测试通过不等于所有训练都重新复现。

这些文件保留旧合同和输出路径，直接执行可能训练或覆盖产物。重跑前核对输入/输出，使用独立输出或隔离工作区；长计算先最小 smoke，工作进程数先按当前机器情况选低值，而非照搬旧 8/16 workers。当前任务不新建统一调度框架。

## 历史依赖与图表

旧 E3/E4/P2/P3/P4、旧图形程序仍有少量函数被当前代码复用，保留文件不表示路线继续。旧生成数据已清理，恢复说明见[认识快照](../07-认识清单与研究快照-20260907.md)。不要按旧 docstring 的“最终方法”字样覆盖当前配置。

当前图件入口在[图表索引](../manuscript/figures/figure-index.md)：图 2 与图 7 已有专用修订程序，旧 make_submission_figures.py 不能单独代表当前全部成图。
