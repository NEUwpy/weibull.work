---
id: "case-6"
name: "案例6: 搜索步长对结果的影响"
description: "研究MDM算法中不同迭代次数和搜索策略对参数估计结果的影响。使用c2案例数据，对比四种搜索策略在两种偏移量下的估计结果。"
processName: "搜索策略"
processSymbol: ""
architecture: "case6"
csvFile: "/case-studies/mdm/case6/data.json"
source_case: "c2"
true_params:
  beta: 2.0
  eta: 1000
  gamma: 1000
strategies:
  - id: "iter60"
    name: "60次迭代"
    description: "默认策略，搜索范围[0, 0.99*t_min]内60个等分点"
  - id: "iter30"
    name: "30次迭代"
    description: "减半策略，30个等分点"
  - id: "iter15"
    name: "15次迭代"
    description: "四分之一策略，15个等分点"
  - id: "discrete"
    name: "离散搜索(间隔100)"
    description: "只考虑γ=0,100,200,...等离散值"
offsets: [0.1, 0.15]
---

# 案例6: 搜索步长对结果的影响

## 研究背景

MDM算法通过搜索γ值来找到梯度曲线与偏移值的交点。搜索的精细程度（迭代次数）可能影响最终结果。

## 研究内容

对比四种搜索策略：
1. **60次迭代**: 默认策略，精细搜索
2. **30次迭代**: 减半搜索
3. **15次迭代**: 粗略搜索
4. **离散搜索(间隔100)**: 只考虑γ=0,100,200,...等离散值

## 数据来源

使用c2案例数据（7个数据点），真实参数：β=2.0, η=1000, γ=1000

## 预期结果

- 迭代次数越少，结果越不稳定
- 离散搜索可能无法找到交点（间隔太大）
