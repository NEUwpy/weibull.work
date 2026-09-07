# Research04 代码与复现入口

设计、参数和旧run id统一见[实验配置](../02-实验配置.md)。13个科学脚本保留原路径；当前图表重绘只使用 `render_manuscript_figures.py`，旧分析脚本的绘图输出不覆盖v0.2图。

| 类别 | 入口 | 输入与执行边界 |
|---|---|---|
| 稿件核验 | [verify_manuscript_v02.py](verify_manuscript_v02.py) | 标准库，核对201项表值和稿件本地链接，更新numeric-verification JSON |
| 当前绘图 | [render_manuscript_figures.py](render_manuscript_figures.py) | 9个保留CSV；需numpy/pandas/matplotlib/pypdf；生成5主图4附图及清单，需人工看图 |
| 基础训练/扫描/评价 | [run_study01_aligned_generalization.py](run_study01_aligned_generalization.py) | 在Research04自建training_scan，不读取Study01被删扫描；会执行完整模型训练与MDM扫描 |
| 基础再分析 | [analyze_study01_aligned_generalization.py](analyze_study01_aligned_generalization.py) | 需要尚未定位的基础per_sample_results.csv.gz |
| WMLE/LSE | [run_traditional_aligned.py](run_traditional_aligned.py)、[analyze_traditional_aligned.py](analyze_traditional_aligned.py) | 正式逐样本在主目录；算法版本必须对应manifest源码哈希 |
| 同中心/位置 | [run_training_domain_width_location.py](run_training_domain_width_location.py)、[analyze_training_domain_width_location.py](analyze_training_domain_width_location.py)、[verify_training_domain_width_location.py](verify_training_domain_width_location.py) | 原始结果与48模型在6615旧worktree；训练main不是只读复核 |
| 先行嵌套 | [run_training_domain_width.py](run_training_domain_width.py)、[analyze_training_domain_width.py](analyze_training_domain_width.py) | 正式模型及逐样本未定位；部分场景强制复用基础模型 |
| 尺度推断 | [run_scale_equivariance_audit.py](run_scale_equivariance_audit.py) | 不重训，但需基础4模型，当前缺失 |
| 探索诊断 | [run_replacement_boundary_diagnostic.py](run_replacement_boundary_diagnostic.py) | 会重训Direct-P；不能当只读分析运行 |

<a id="dependencies"></a>
## 共享依赖

Research04调用Study01的[dim_raw_config.py](../../../Study/01-study-MDM最小偏移量优化研究/code/dim_raw_config.py)、[run_E6b_dimensional_raw_specialist.py](../../../Study/01-study-MDM最小偏移量优化研究/code/run_E6b_dimensional_raw_specialist.py)、[run_p3_direct_mlp.py](../../../Study/01-study-MDM最小偏移量优化研究/code/run_p3_direct_mlp.py)及其传递import。共享抽样、评分、方法入口位于[python/studies/common](../../../python/studies/common/)，求解与WMLE权重在[python/methods](../../../python/methods/)。这些依赖保持原位；当前代码不依赖E09历史包。

训练/分析需要numpy、pandas、scipy、scikit-learn、torch、joblib；测试另需pytest。检查当前环境的通过结果见[本轮快照](../07-认识清单与研究快照-20260908.md#checks)，不把今日库版本当作历史训练环境锁定。

从仓库根运行轻量核验：

```powershell
python 'Research/04-直接NN参数估计/code/verify_manuscript_v02.py'
python -m pytest 'Research/04-直接NN参数估计/tests' -q -p no:cacheprovider
```

旧正式main默认写回原产物路径，不直接在封存目录重跑。需要历史数值时先恢复原始数据并比对manifest的Git基点与源码哈希；当前平台同名方法可能已更新。恢复位置、快照及缺失证据见[恢复清单](../07-认识清单与研究快照-20260908.md#restore)。
