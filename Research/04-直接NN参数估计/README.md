# 直接 NN 参数估计

> 成熟度：`RESULTS_AVAILABLE`
> 关系角色：`SUPPORTING`

## 研究问题

神经网络直接输出 Weibull 参数，在不同输入表示、训练协议和比较对象下表现如何？这是一个独立路线问题，不是 Study01“选择 MDM 偏移量”主论证的必要组成，也不能与 Study02 当前 P–Q 研究跨协议拼接排名。

## 当前材料

- Study01 Direct-MLP/P3/P4 的代码、测试和封存产物保持在 Study01 原位；本目录仅提供研究入口，不复制正式 evidence。
- Study02 前置研究 A 保持嵌入 Study02；它是 Study02 路线冻结的支撑材料，不搬动 formal artifacts。
- `history/E09-旧直接估计范式比较/` 是旧 `docs/research/09两种神经网络直接估计/` 原字节迁入的完整实验包。该包存在单模型 seed、数据命名空间和文档结论不一致等边界，只能作为历史探索。
- 连续参数域与 OOD 的正式比较口径见 [`02-连续参数域与OOD正式实验计划-v0.1.md`](02-连续参数域与OOD正式实验计划-v0.1.md)。正式轮以当前 Study01 Mean-Normalized-MLP + MDM 为结构保留路线，并为 Direct 网络加入尺度等变输出。
- Study01 对齐泛化实验入口为 [`code/run_study01_aligned_generalization.py`](code/run_study01_aligned_generalization.py)。训练使用 Study01 的 48,000 样本设计和种子 42；独立测试包含已见网格、域内未见点、近域外和远域外共 126,000 个共享样本。Smoke 与正式结果分别写入 `artifacts/smoke/study01_aligned_generalization_v1/` 和 [`artifacts/study01_aligned_generalization_v1/`](artifacts/study01_aligned_generalization_v1/)。
- 正式结果已经完成：Direct-P 在已见网格与域内未见点的联合误差相对自适应 MDM 分别下降 35.8% 和 37.5%，对应的 $x_{0.95}$ RMSE 分别下降 14.9% 和 16.5%；低 $\beta$ 外推发生反转，高 $\beta$ 外推在测试上限 5.75 处仍保持优势。完整统计、配对置信区间和机制分解见 [`artifacts/study01_aligned_generalization_v1/analysis/report.md`](artifacts/study01_aligned_generalization_v1/analysis/report.md)。
- 样本量分层已经补齐：$n=7$ 至 20 时两类路线均改善，自适应 MDM 的改善更快，Direct-P 的域内相对优势由 41.3% 收窄到 28.3%。大 $\beta$ 机制诊断显示 MDM 的形状方向敏感度随 $1/\beta^2$ 衰减，且 $\eta$ 与 $\gamma$ 误差呈强负相关补偿。
- 训练域宽度实验已经补齐：Direct-P 分别在 $\beta\in[2,3]$、$[1.5,3.5]$ 和 $[1.5,5]$ 上训练，并共享 $0.75$ 至 5.75 的正式测试样本。固定总训练样本量时，宽域模型在共同区间 $[2,3]$ 的 $J_1$ 比窄域高 32.3%；固定每个参数单元的样本密度后，宽域使用 2.67 倍总训练量，增幅仍为 31.5%。训练域扩大因而牺牲局部参数精度、改善远点覆盖，主要代价落在 $\beta$ 恢复；$x_{0.95}$ 因参数补偿只小幅变化。完整结果见 [`artifacts/training_domain_width_v1/analysis/report.md`](artifacts/training_domain_width_v1/analysis/report.md)。
- 三个训练域的点类型已单独汇总：训练网格间距为 0.5，正式测试间距为 0.25，因此每个区间均覆盖训练点、域内非训练点、左右紧邻域外点和更远域外点。代表结果与解释见 [`artifacts/training_domain_width_v1/analysis/point_type_report.md`](artifacts/training_domain_width_v1/analysis/point_type_report.md)。
- 多尺度等变审计已经补齐：四个正式 Direct-P 模型不重新训练，将全部 126,000 个测试样本分别成对缩放到 $\eta=1,10,100,1000,10^4,10^6$，六个尺度的 $J_1=0.4705367$、$x_{0.95}$ RMSE=0.2060071、失败率=0.05476% 均保持不变；参数缩放还原后的最大数值差为 $9.1\times10^{-13}$。结果见 [`artifacts/scale_equivariance_v1/report.md`](artifacts/scale_equivariance_v1/report.md)。
- 正式中文稿件为 [`03-稿件-直接神经估计与结构保留路线比较-v0.1.md`](03-稿件-直接神经估计与结构保留路线比较-v0.1.md)，包含方法、结果、机制、图题、表题和复现入口。
- 结果分析与作图入口为 [`code/analyze_study01_aligned_generalization.py`](code/analyze_study01_aligned_generalization.py)；数值表保留为 CSV，图形同时输出 PNG 与 PDF。
- 训练域宽度实验与作图入口分别为 [`code/run_training_domain_width.py`](code/run_training_domain_width.py) 和 [`code/analyze_training_domain_width.py`](code/analyze_training_domain_width.py)；正式清单位于 [`artifacts/training_domain_width_v1/manifest.json`](artifacts/training_domain_width_v1/manifest.json)。

## 原位入口

- Study01 P3 配置：`../../Study/01-study-MDM最小偏移量优化研究/code/p3_config.py`
- Study01 P4 配置：`../../Study/01-study-MDM最小偏移量优化研究/code/p4_config.py`
- Study01 P4 封存产物：`../../Study/01-study-MDM最小偏移量优化研究/artifacts/formal/p4_formal_compare/`
- Study02 前置研究 A：`../../Study/02-study-NN参数估计与分位点目标研究/06-A-前置研究报告.md`

不同材料只有在数据、输入、目标、切分、指标和随机性口径一致时才能比较；当前入口不把它们合并成一个统一排行榜。

## 当前结论边界

- 当前正式轮固定一个模型种子 42，能够回答冻结训练协议下的域内插值、方向性外推和训练域宽度权衡，不代表网络初始化的总体稳定性。
- 尺度审计验证的是 $\eta,\gamma$ 同比例变化下的确定性尺度等变，不覆盖绝对测量噪声、截断阈值或传感器分辨率不随尺度同比例变化的情况。
- 当前三个训练域是嵌套区间，尚未系统平移同一宽度的区间；因此可以说明当前区间的宽度—覆盖权衡，但不能把宽度效应与区间位置效应完全分离。
- Bias、SD、RMSE 与 $x_{0.95}$ 指标已经报告；区间覆盖率尚未验证。
- 低 $\beta$ 侧的反转说明 Direct-P 需要训练域检查或 OOD 触发机制；高 $\beta$ 侧未在本轮范围内观察到反转。
