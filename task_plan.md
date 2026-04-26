# Task Plan: AI 模块 1 可视化方案清单

## 原则
- 每做完一种图表标记 [x]
- 图表组件尽量复用（通用 Chart 组件）
- 数据来源：训练结果 CSV → 前端渲染
- CSV 存放在 `python/studies/mdm_delta/data/` 或 `python/models/mdm_delta/`
- 前端图表组件放在 `src/components/ai/charts/`

---

## 一、训练数据可视化（Data Tab）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| D1 | 最优 δ 分布直方图 | training_data_n{n}.csv | Histogram | [ ] |
| D2 | 按 β、n 分组的 δ 箱型图 | training_data_n{n}.csv | BoxPlot | [ ] |
| D3 | δ vs 样本均值散点图 | training_data_n{n}.csv | Scatter | [ ] |
| D4 | δ vs 样本标准差散点图 | training_data_n{n}.csv | Scatter | [ ] |
| D5 | δ vs 变异系数散点图 | training_data_n{n}.csv | Scatter | [ ] |
| D6 | 无解率柱状图（按参数组合） | summary.json | BarChart | [ ] |
| D7 | 参数空间覆盖散点矩阵 | config.json + training_data | ScatterMatrix | [ ] |

---

## 二、训练过程可视化（Training Tab）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| T1 | 损失收敛曲线（train/val） | n{n}_metrics.json → history | LineChart | [ ] |
| T2 | 学习率变化曲线（如有调度） | n{n}_metrics.json → history | LineChart | [ ] |

---

## 三、模型效果可视化（Performance Tab）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| P1 | 预测 vs 真实散点图 | validation_predictions_n{n}.csv | Scatter | [ ] |
| P2 | 误差分布直方图 | validation_predictions_n{n}.csv | Histogram | [ ] |
| P3 | β×n 误差热力图 | validation_predictions_n{n}.csv | Heatmap | [ ] |
| P4 | 不同指标方案效果对比柱状图 | metrics_comparison.csv | BarChart | [ ] |
| P5 | 预测 δ 分布 vs 真实 δ 分布 | validation_predictions_n{n}.csv | OverlayHistogram | [ ] |

---

## 四、路线 1 Playground 可视化（Playground Tab - 路线1）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| R1-1 | 用户输入样本的 δ 预测展示 | API 实时返回 | 数值卡片 | [ ] |
| R1-2 | 预测 δ 在分布中的位置 | 训练数据分布 + 预测值 | DistributionMark | [ ] |

---

## 五、路线 2 迭代可视化（Playground Tab - 路线2）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| R2-1 | δ 收敛轨迹 | API 返回迭代历史 | LineChart | [ ] |
| R2-2 | 参数收敛轨迹（β̂,η̂,ŷ） | API 返回迭代历史 | MultiLineChart | [ ] |
| R2-3 | 收敛步数分布直方图 | iteration_stats.csv | Histogram | [ ] |
| R2-4 | MDM 拟合线 + 数据点（最终结果） | API 返回最终结果 | Scatter+Line | [ ] |

---

## 六、方法对比可视化（Compare Tab）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| C1 | AI δ vs 固定 δ 箱型图 | comparison_ai_vs_fixed.csv | BoxPlot | [ ] |
| C2 | 固定 δ 的 MSE 曲线 + AI δ 标注 | comparison_sweep.csv | LineChart+Mark | [ ] |
| C3 | β×n 下 AI 相对固定 δ 的改善热力图 | comparison_improvement.csv | Heatmap | [ ] |
| C4 | 路线 1 vs 路线 2 效果对比 | comparison_routes.csv | GroupedBar | [ ] |

---

## 七、可信性验证可视化（Verification Tab）

| # | 图表 | 数据文件 | 组件 | 状态 |
|---|------|---------|------|------|
| V1 | 已知参数验证案例表 | verification_cases.csv | Table | [ ] |
| V2 | 验证案例的 MDM 拟合图 | verification_cases.csv | Scatter+Line | [ ] |
| V3 | 边界条件测试结果 | boundary_tests.csv | Table+Chart | [ ] |

---

## 通用图表组件（需开发）

| 组件 | 用途 | 复用于 |
|------|------|--------|
| ScatterPlot | 散点图（含对角线参考线） | D3,D4,D5,P1 |
| Histogram | 直方图 | D1,P2,P5,R2-3 |
| BoxPlot | 箱型图 | D2,C1 |
| LineChart | 折线图 | T1,T2,R2-1,C2 |
| MultiLineChart | 多线折线图 | R2-2 |
| Heatmap | 热力图 | P3,C3 |
| BarChart | 柱状图 | D6,P4 |
| GroupedBar | 分组柱状图 | C4 |
| ScatterWithLine | 散点+拟合线 | R2-4,V2 |
| DistributionMark | 分布+标记点 | R1-2 |
| DataTable | 数据表格 | V1,V3 |

---

## 数据文件生成计划

以下 CSV 需要在训练脚本中额外生成：

| 文件 | 来源 | 内容 |
|------|------|------|
| validation_predictions_n{n}.csv | train_model.py | 验证集的 (真实δ, 预测δ, β, η, γ, n) |
| iteration_stats.csv | 路线2批量测试 | 多个样本的迭代收敛统计 |
| comparison_ai_vs_fixed.csv | 对比脚本 | AI δ 和多个固定 δ 的参数估计误差 |
| comparison_sweep.csv | 对比脚本 | 固定 δ 从 0.01 到 0.50 的 MSE 曲线 |
| comparison_improvement.csv | 对比脚本 | AI δ 相对固定 δ 的改善百分比 |
| comparison_routes.csv | 对比脚本 | 路线1 vs 路线2 的效果对比 |
| verification_cases.csv | 验证脚本 | 已知参数的验证案例 |
| boundary_tests.csv | 验证脚本 | 边界条件测试 |

---

## 进度统计

- 总图表数：27
- 已完成：0
- 进行中：0
- 待开发：27

---

## 已确认决策
- 先做路线 1，再做路线 2，Tab 切换
- 路线 2 初始 δ₀ = 0.5，收敛方案 C
- 参数空间：β∈{1,2,5}, η∈{100,1000,5000}, γ=1000, n∈{5,7,15}, MC=500
- 指标：5 种方案对比
- 可视化：全部 27 个图表都做，组件复用，数据来自 CSV

## Status
**当前阶段**：方案全部确认，待开始实现
