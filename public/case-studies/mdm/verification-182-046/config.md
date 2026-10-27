---
id: "verification-182-046"
name: "复现182-046: 基于统计最小差异原理的威布尔分布参数估计方法"
description: "复现论文图5：30个样本的∇(γ)-γ曲线"
paper:
  id: "182-046"
  title: "基于统计最小差异原理的威布尔分布参数估计方法"
  authors: "谢里阳, 朱文慧, 吴宁祥, 杨小玉"
  journal: "东北大学学报（自然科学版）"
  year: 2025
  figure: "图5"
verification:
  trueParams:
    beta: 2.0
    eta: 1000
    gamma: 1000
  sampleSize: 7
  offset: 0.1
  nSamples: 30
  paperImage: "/182-046-图片/images/1d2f540c5c3f3bbcb65573317f0693a446050724b97d8db2547241bf17194757.jpg"
  curvesData: "/case-studies/mdm/verification-182-046/curves.json"
  samplesData: "/case-studies/mdm/verification-182-046/data.csv"
  resultsData: "/case-studies/mdm/verification-182-046/results.csv"
  summaryData: "/case-studies/mdm/verification-182-046/summary.json"
---

# 复现论文 182-046 图5

## 论文信息

**标题**: 基于统计最小差异原理的威布尔分布参数估计方法

**作者**: 谢里阳, 朱文慧, 吴宁祥, 杨小玉

**期刊**: 东北大学学报（自然科学版）, 2025

## 图5 说明

基于 Weibull 分布 W(2.0, 1000, 1000) 的 30 个随机样本（样本量为 7）的梯度曲线。

采用偏移值 δ=0.1 后，位置参数估计范围从 0~1475 缩小到 463~1506。

## 验证条件

- 真实分布: W(2.0, 1000, 1000)
- 样本量: n=7
- 偏移量: δ=0.1
- 样本数: 30组
