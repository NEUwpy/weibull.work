---
method_id: "mle"
method_name: "极大似然估计"
short_name: "MLE"
category: "极大化适配法"

# 核心信息
formula: '\ln L = n \ln\beta - n\beta\ln\eta + (\beta-1)\sum_{i=1}^{n}\ln(x_i-\gamma) - \sum_{i=1}^{n}\left(\frac{x_i-\gamma}{\eta}\right)^\beta'
description: "极大似然估计（Maximum Likelihood Estimation, MLE）是统计推断中最基础且最重要的方法。通过最大化样本观测值的联合概率密度（似然函数）来估计参数。在大样本下具有渐近正态性、一致性和有效性，但在小样本下存在显著偏差。"

# 变量说明
variables:
  - symbol: "L"
    description: "似然函数 (Likelihood Function)"
    range: "L > 0"
  - symbol: "n"
    description: "样本量"
    range: "n ≥ 1"
  - symbol: "β"
    description: "形状参数"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数"
    range: "0 ≤ γ < min(x)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入据 X] --> B[初始猜测<br/>利用 LRE 估算]
    B --> C[数值优化<br/>最大化 ln L]
    C --> D{收敛?}
    D -->|否| C
    D -->|是| E[输出结果<br/>β, η, γ]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: true
  small_sample: false
  large_sample: true

# 相关文献
references:
  - id: "182-090"
    title: "Maximum likelihood estimation in a class of nonregular cases"
    author: "Smith, R. L."
    year: "1985"
    publication: "Biometrika"
---

# 极大似然估计 (MLE)

## 算法原理

极大似然估计 (MLE) 的核心思想是寻找一组参数 $(\hat{\beta}, \hat{\eta}, \hat{\gamma})$，使得在该组参数下，观测到当前数据集 $X = \{x_1, ..., x_n\}$ 的概率密度乘积（即似然函数）最大。即：**“已经发生的事情应该是概率最大的事情”**。

## 威布尔分布基础

概率密度函数（PDF）：

$$
f(x | \beta, \eta, \gamma) = \frac{\beta}{\eta} \left( \frac{x - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

## 估计方程

为了简化计算（将乘积转化为求和），通常最大化**对数似然函数** $\ln L$：

$$$ 
\ln L = n \ln \beta - n \beta \ln \eta + (\beta - 1) \sum_{i=1}^{n} \ln(x_i - \gamma) - \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta
$$$ 

### 变量说明

| 符号 | 说明 | 范围 |
|------|------|----------|
| $\beta$ | 形状参数 | $\beta > 0$ |
| $\eta$ | 尺度参数 | $\eta > 0$ |
| $\gamma$ | 位置参数 | $0 \le \gamma < \min(x)$ |

## 算法流程详解

### 输入
- 失效数据数组 X = [x₁, x₂, ..., xₙ]
- 样本量 n

### 步骤

1. **初始猜测**
   - 使用线性回归法 (LRE) 快速估算 $\beta_0, \eta_0$。
   - 设 $\gamma_0 = 0$（或略小于最小值）。

2. **数值优化**
   - 使用 Nelder-Mead 或 Newton-Raphson 算法。
   - 目标：$\max_{\beta, \eta, \gamma} (\ln L)$。
   - 约束：$\beta > 0, \eta > 0, \gamma < \min(x)$。

3. **结果验证**
   - 检查 Hessian 矩阵是否负定（确保是极大值）。
   - 检查 $\beta$ 是否小于 1（可能涉及无界问题）。

### 输出
```python
{
    "beta": 2.5,
    "eta": 100.0,
    "gamma": 0.0,
    "log_likelihood": -150.23,
    "success": true
}
```

## 适用场景详解

| 场景 | 说明 |
|------|------|
| **完全样本** | 最常用的场景，效果稳定。 |
| **截尾样本** | 需修改似然函数（加入生存函数项），完全支持。 |
| **小样本** | **不推荐**。偏差显著，建议改用 WMLE。 |
| **大样本** | **最优**。渐近方差最小。 |

## 优缺点分析

### 优点
- **理论性质优**：渐近无偏、一致、有效。
- **通用性**：适用于各种复杂的截尾类型。

### 缺点
- **无界问题**：当 $\beta < 1$ 且 $\gamma$ 未知时，似然函数可能趋向无穷大。
- **小样本偏差**：严重高估 $\beta$。
- **计算复杂**：需要迭代求解，对初值敏感。

## 与其他方法对比

| 方法 | 小样本偏差 | 计算复杂度 | 特点 |
|------|----------|-----------|---------|
| MLE | 高 | 中 | 大样本理论最优 |
| WMLE | 低 | 高 | 修正了小样本偏差 |
| LRE | 低 | 低 | 简单，无解问题少 |

## 参考文献

[1] Smith, R. L. (1985). Maximum likelihood estimation in a class of nonregular cases. *Biometrika*, 72(1): 67-90.

---

**相关文献**：详见 [182-090](/library/182-090) 完整论文