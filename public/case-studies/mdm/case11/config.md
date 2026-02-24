---
id: "case-11"
name: "案例11: 中位秩方法对比研究 (多样本量)"
description: "扩展case10，增加n=10、n=15样本量的对比分析"
architecture: "case11"
processName: "样本量"
processSymbol: "n"
csvFile: "/case-studies/mdm/case11/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
true_params:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSizes: [7, 10, 15]
research_type: "median_rank_comparison_multi_n"
params:
  - id: "sample_size"
    name: "样本量"
    symbol: "n"
    state: "discrete"
    discreteValues: [7, 10, 15]
    isVariable: true
    isDisplayDimension: true
  - id: "rank_method"
    name: "中位秩方法"
    symbol: "Method"
    state: "discrete"
    discreteValues: ["bernard", "exact"]
    isVariable: true
    isDisplayDimension: true
  - id: "gamma"
    name: "位置参数"
    symbol: "γ"
    state: "continuous"
    range: [0, 1500]
    isVariable: false
    isDisplayDimension: false
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "dependent"
    isVariable: false
    isDisplayDimension: false
---

## 案例11: 中位秩方法对比研究 (多样本量扩展)

### 研究目的

在案例10的基础上，扩展研究不同样本量对两种中位秩方法的影响：

| 方法 | 公式 | 说明 |
|------|------|------|
| Bernard's approximation | F(t_{(i)}) = (i - 0.3) / (n + 0.4) | 简单近似公式 |
| 精确中位秩 | F(t_{(i)}) = i / (i + (n+1-i) * F_{median}) | 基于F分布的精确估计 |

### 研究方法

- **样本量**: n = 7, 10, 15
- **蒙特卡洛模拟**: 各1000次/方法
- **真实参数**: β=2.0, η=1000, γ=1000
- **偏移量**: δ=0.1

### 关键问题

1. 样本量增加后，两种方法的差异如何变化？
2. 精确中位秩的优势是否随样本量增加而更加明显？
3. 小样本(n=7)与大样本(n=15)的估计精度对比？

### 可视化图表

1. **中位秩值对比表**: 各样本量下的F(t_i)数值差异
2. **参数估计概率密度分布**: 三种样本量的β、η、γ分布对比
3. **统计汇总表**: 偏差、标准差、MSE随样本量的变化
