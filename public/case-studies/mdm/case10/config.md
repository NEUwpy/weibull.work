---
id: "case-10"
name: "案例10: 中位秩方法对比研究"
description: "蒙特卡洛模拟对比Bernard近似与精确中位秩对MDM估计的影响"
architecture: "case10"
processName: "偏移量"
processSymbol: "δ"
csvFile: "/case-studies/mdm/case10/data.json"
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
  sampleSize: 7
research_type: "median_rank_comparison"
params:
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
    isVariable: true
    isDisplayDimension: false
  - id: "eta"
    name: "尺度参数"
    symbol: "η"
    state: "dependent"
    isVariable: false
    isDisplayDimension: false
---

## 案例10: 中位秩方法对比研究

### 研究目的

对比两种中位秩计算方法对MDM参数估计结果的影响：

| 方法 | 公式 | 说明 |
|------|------|------|
| Bernard's approximation | F(t_{(i)}) = (i - 0.3) / (n + 0.4) | 简单近似公式 |
| 精确中位秩 | F(t_{(i)}) = i / (i + (n+1-i) * F_{median}) | 基于F分布的精确估计 |

其中 F_{median} = F_{2(n+1-i), 2i}(0.5) 是F分布的中位数。

### 研究方法

- **蒙特卡洛模拟**: 各1000次
- **样本量**: n = 7
- **真实参数**: β=2.0, η=1000, γ=1000
- **偏移量**: δ=0.1
- **数据生成**: Weibull分布随机抽样

### 关键问题

1. 两种中位秩方法的估计偏差有何差异？
2. 哪种方法的收敛率更高？
3. 哪种方法的估计标准差更小？
4. 对于小样本(n=7)，精确中位秩是否显著优于Bernard近似？

### 可视化图表

1. **统计汇总对比表**: 两种方法的偏差均值、标准差、范围
2. **β估计分布直方图**: 对比两种方法的β估计分布
3. **γ估计分布直方图**: 对比两种方法的γ估计分布
4. **偏差箱线图**: β、η、γ三种参数的偏差对比
5. **收敛率对比**: 两种方法的收敛成功率

### 中位秩公式说明

**精确中位秩估计器**（文献推导）：

$$\hat{F}(t_{(i)}) = \frac{i}{i+(n+1-i)F_{2(n+1-i),2i,\alpha}}$$

当 α=0.5 时，取F分布的中位数作为中位秩估计。

**Bernard's approximation**：

$$\hat{F}(t_{(i)}) = \frac{i-0.3}{n+0.4}$$

这是一个简单但有效的近似公式，在工程实践中广泛使用。
