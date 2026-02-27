---
id: "case-15"
name: "案例15: WMLE 权重 Monte Carlo 验证"
description: "复现 Cousineau (2009) 论文的权重计算方法，验证当前代码实现的准确性"
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
  gamma: 1000
  sampleSizes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
research_type: "wmle_weights_verification"
params:
  - id: "sample_size"
    name: "样本量"
    symbol: "n"
    state: "discrete"
    discreteValues: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    isVariable: true
    isDisplayDimension: true
  - id: "gamma"
    name: "形状参数"
    symbol: "γ"
    state: "continuous"
    range: [0.5, 5]
    isVariable: false
    isDisplayDimension: false
---

## 案例15: WMLE 权重 Monte Carlo 验证

### 研究目的

验证当前 WMLE 实现中三个权重 (W1, W2, W3) 的准确性，复现 Cousineau (2009) 论文的 Monte Carlo 模拟方法。

### 权重的物理意义

| 权重 | 作用 | 依赖因素 |
|------|------|----------|
| **W1** | 修正尺度参数 η 的估计偏差 | 仅依赖样本量 n |
| **W2** | 修正形状参数 β 的估计偏差 | 仅依赖样本量 n |
| **W3** | 修正位置参数 γ 的估计偏差 | 依赖样本量 n 和形状参数 β |

### 权重的定义

根据 Cousineau (2009) 论文，三个权重的定义为：

$$W_1 = \frac{1}{n}\sum_{i=1}^{n}\log\left(\frac{1}{1-F(x_i)}\right)$$

$$W_2 = \frac{\sum_{i=1}^{n}\log\left(\frac{1}{1-F(x_i)}\right)\log\left(\log\left(\frac{1}{1-F(x_i)}\right)\right)}{\sum_{i=1}^{n}\log\left(\frac{1}{1-F(x_i)}\right)} - \frac{1}{n}\sum_{i=1}^{n}\log\left(\log\left(\frac{1}{1-F(x_i)}\right)\right)$$

$$W_3 = W_1 \cdot \frac{\sum_{i=1}^{n}\left(\log\left(\frac{1}{1-F(x_i)}\right)\right)^{-1/\gamma}}{\sum_{i=1}^{n}\left(\log\left(\frac{1}{1-F(x_i)}\right)\right)^{(\gamma-1)/\gamma}}$$

### Monte Carlo 模拟方法

1. 将公式中的 $\log(1/(1-F(x_i)))$ 替换为标准指数分布随机变量 $z_i \sim \text{Exp}(1)$
2. 重复 $2^{20}$ (约 100 万) 次模拟
3. 计算均值 (E)、中位数 (J)、几何均值 (G)

### 研究参数

- **样本量**: n = 1 到 30
- **形状参数**: γ = 2.0
- **模拟次数**: $2^{20}$ = 1,048,576 次

### 对比内容

1. **论文值**: Cousineau (2009) Tables 2-4 中的 J1, J2, J3
2. **Monte Carlo 模拟值**: 本脚本运行的结果
3. **代码实现值**: 当前 `python/methods/wmle.py` 中的权重计算函数

### 关键问题

1. Monte Carlo 模拟结果与论文值的一致性如何？
2. 当前代码中 J1, J2 的查表值是否准确？
3. 当前代码中 J3 的近似公式精度如何？
4. n > 16 时，权重如何变化？

### 可视化图表

1. **权重对比表**: 论文值 vs Monte Carlo vs 代码实现
2. **误差分析表**: 相对误差百分比
3. **权重曲线图**: J1, J2, J3 随 n 变化的趋势
4. **代码公式精度**: J3 近似公式 vs Monte Carlo 真值
