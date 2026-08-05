# 直接 NN 参数估计

> 成熟度：`NEEDS_REVIEW`
> 关系角色：`SUPPORTING`

## 研究问题

神经网络直接输出 Weibull 参数，在不同输入表示、训练协议和比较对象下表现如何？这是一个独立路线问题，不是 Study01“选择 MDM 偏移量”主论证的必要组成，也不能与 Study02 当前 P–Q 研究跨协议拼接排名。

## 当前材料

- Study01 Direct-MLP/P3/P4 的代码、测试和封存产物保持在 Study01 原位；本目录仅提供研究入口，不复制正式 evidence。
- Study02 前置研究 A 保持嵌入 Study02；它是 Study02 路线冻结的支撑材料，不搬动 formal artifacts。
- `history/E09-旧直接估计范式比较/` 是旧 `docs/research/09两种神经网络直接估计/` 原字节迁入的完整实验包。该包存在单模型 seed、数据命名空间和文档结论不一致等边界，只能作为历史探索。

## 原位入口

- Study01 P3 配置：`../../Study/01-study-MDM最小偏移量优化研究/code/p3_config.py`
- Study01 P4 配置：`../../Study/01-study-MDM最小偏移量优化研究/code/p4_config.py`
- Study01 P4 封存产物：`../../Study/01-study-MDM最小偏移量优化研究/artifacts/formal/p4_formal_compare/`
- Study02 前置研究 A：`../../Study/02-study-NN参数估计与分位点目标研究/06-A-前置研究报告.md`

不同材料只有在数据、输入、目标、切分、指标和随机性口径一致时才能比较；当前入口不把它们合并成一个统一排行榜。
