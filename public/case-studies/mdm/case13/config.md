---
id: "case-13"
name: "案例13: 中位秩方法对比 (多尺度参数)"
description: "在案例11基础上增加尺度参数选择，研究分散性对估计精度的影响"
architecture: "case13"
processName: "尺度参数"
processSymbol: "η"
csvFile: "/case-studies/mdm/case13/data.json"
defaults:
  beta: 2.0
  eta: 1000
  gamma: 1000
  sampleSize: 7
  process: 0.1
true_params:
  beta: 2.0
  eta_values: [200, 1000, 5000]
  gamma: 1000
  sampleSizes: [7, 10, 15]
research_type: "median_rank_comparison_multi_eta"
params:
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "discrete"
    discreteValues: [200, 1000, 5000]
    isVariable: true
    isDisplayDimension: true
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
---

## 案例13: 中位秩方法对比研究 (多尺度参数)

### 研究目的

在案例11的基础上，扩展研究**尺度参数 η** 对两种中位秩方法的影响：

| 方法 | 公式 | 说明 |
|------|------|------|
| Bernard's approximation | F(t_{(i)}) = (i - 0.3) / (n + 0.4) | 简单近似公式 |
| 精确中位秩 | F(t_{(i)}) = i / (i + (n+1-i) * F_{median}) | 基于F分布的精确估计 |

### 尺度参数的物理意义

| η 值 | 分散性 | 失效时间分布 |
|------|--------|--------------|
| 200 | 小 | 数据集中，失效时间差异小 |
| 1000 | 中 | 基准 |
| 5000 | 大 | 数据分散，失效时间差异大 |

### 研究方法

- **尺度参数**: η = 200, 1000, 5000
- **样本量**: n = 7, 10, 15
- **蒙特卡洛模拟**: 各1000次/方法
- **真实参数**: β=2.0, γ=1000
- **偏移量**: δ=0.1

### 关键问题

1. 尺度参数（分散性）对两种方法的估计精度有何影响？
2. 小尺度（η=200）和大尺度（η=5000）下，哪种方法更稳定？
3. 不同尺度参数下，β、η、γ 的估计偏差如何变化？

### 可视化图表

1. **尺度参数选择器**: 切换 η=200/1000/5000
2. **中位秩值对比表**: 各样本量下的F(t_i)数值差异
3. **统计汇总表**: 偏差、标准差、MSE随尺度参数的变化
4. **概率密度分布**: 不同 η 值下 β、η、γ 的分布对比
