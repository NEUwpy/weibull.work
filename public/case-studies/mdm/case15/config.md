---
id: "case-15"
name: "案例15: MDM vs WMLE 方法对比 (精细步长)"
description: "在案例12基础上使用精细步长MDM和有边界约束的WMLE"
architecture: "case15"
processName: "样本量"
processSymbol: "n"
csvFile: "/case-studies/mdm/case15/data.json"
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
  sampleSizes: [7, 9, 10, 12, 15, 20]
research_type: "method_comparison_fine_step"
params:
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

## 案例15: MDM vs WMLE 方法对比研究 (精细步长)

### 研究目的

对比两种威布尔三参数估计方法，使用**精细步长MDM**：

| 方法 | 全称 | 核心特点 |
|------|------|----------|
| **MDM (精细步长)** | Minimum Discrepancy Method | β步长=0.01, γ步长=10 |
| **WMLE (有约束)** | Weighted Maximum Likelihood | 添加 γ ≥ 0 边界约束 |

### 与案例12的区别

| 参数 | 案例12 | 案例15 |
|------|--------|--------|
| MDM β搜索 | 连续优化 (scipy) | 离散步长 (0.01) |
| MDM γ搜索 | 固定60步 | 固定步长 (10) |
| WMLE γ约束 | 无 | γ ≥ 0 |

### 研究方法

- **样本量**: n = 7, 9, 10, 12, 15, 20
- **蒙特卡洛模拟**: 各1000次/方法
- **真实参数**: β=2.0, η=1000, γ=1000
- **MDM偏移量**: δ=0.1
- **MDM精细步长**: β_step=0.01, γ_step=10

### 关键问题

1. 精细步长是否能提高MDM的估计精度？
2. WMLE添加边界约束后，γ的估计是否更合理？
3. 小样本和大样本下，两种方法的差异如何？

### 方法简介

**MDM (精细步长)**
- 使用离散β搜索，步长0.01
- 使用固定γ步长10（预估位置参数的1%）
- 更精细的搜索可能提高精度，但计算时间增加

**WMLE (有边界约束)**
- 在MLE基础上引入权重修正小样本偏差
- 添加 γ ≥ 0 约束，避免物理不合理的负值

### 可视化图表

1. **统计汇总表**: 偏差、标准差、MSE、有解率对比
2. **参数估计概率密度分布**: β、η、γ 的 KDE 分布对比
