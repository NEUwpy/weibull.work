---
id: "case-16"
name: "案例16: MDM vs WMLE 方法对比 (精细步长 + 多尺度参数)"
description: "在案例14基础上使用精细步长MDM和有边界约束的WMLE"
architecture: "case16"
processName: "尺度参数"
processSymbol: "η"
csvFile: "/case-studies/mdm/case16/data.json"
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
  sampleSizes: [7, 9, 10, 12, 15, 20]
research_type: "method_comparison_multi_eta_fine_step"
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
    discreteValues: [7, 9, 10, 12, 15, 20]
    isVariable: true
    isDisplayDimension: true
  - id: "method"
    name: "估计方法"
    symbol: "Method"
    state: "discrete"
    discreteValues: ["mdm", "wmle"]
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

## 案例16: MDM vs WMLE 方法对比研究 (精细步长 + 多尺度参数)

### 研究目的

在案例15的基础上，扩展研究**尺度参数 η** 对两种威布尔三参数估计方法的影响：

| 方法 | 全称 | 核心特点 |
|------|------|----------|
| **MDM (精细步长)** | Minimum Discrepancy Method | β步长=0.01, γ步长=10 |
| **WMLE (有约束)** | Weighted Maximum Likelihood | 添加 γ ≥ 0 边界约束 |

### 与案例14的区别

| 参数 | 案例14 | 案例16 |
|------|--------|--------|
| MDM β搜索 | 连续优化 (scipy) | 离散步长 (0.01) |
| MDM γ搜索 | 固定60步 | 固定步长 (10) |
| WMLE γ约束 | 无 | γ ≥ 0 |

### 尺度参数的物理意义

| η 值 | 分散性 | 失效时间分布 |
|------|--------|--------------|
| 200 | 小 | 数据集中，失效时间差异小 |
| 1000 | 中 | 基准 |
| 5000 | 大 | 数据分散，失效时间差异大 |

### 研究方法

- **尺度参数**: η = 200, 1000, 5000
- **样本量**: n = 7, 9, 10, 12, 15, 20
- **蒙特卡洛模拟**: 各1000次/方法
- **真实参数**: β=2.0, γ=1000
- **MDM偏移量**: δ=0.1
- **MDM精细步长**: β_step=0.01, γ_step=10

### 关键问题

1. 精细步长是否能解决案例14中WMLE估计γ出现负数的问题？
2. 不同尺度参数下，精细步长MDM的表现如何？
3. 大分散性数据（η=5000）下，两种方法的稳健性如何？

### 方法简介

**MDM (精细步长)**
- 使用离散β搜索，步长0.01
- 使用固定γ步长10（预估位置参数的1%）
- 更精细的搜索可能提高精度

**WMLE (有边界约束)**
- 在MLE基础上引入权重修正小样本偏差
- 添加 γ ≥ 0 约束，避免物理不合理的负值
- 解决了案例14中γ出现负数的问题

### 可视化图表

1. **尺度参数选择器**: 切换 η=200/1000/5000
2. **统计汇总表**: 偏差、标准差、MSE、99%CI对比
3. **参数估计概率密度分布**: β、η、γ 的 KDE 分布对比
