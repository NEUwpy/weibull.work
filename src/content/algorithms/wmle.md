---
method_id: "wmle"
method_name: "加权极大似然估计"
short_name: "WMLE"
category: "极大化适配法"

# 核心信息
formula: "\\{\\hat{\\gamma}, \\hat{\\alpha}\\}_W = \\arg \\min_{\\gamma, \\alpha} \\left[ \\left( \\frac{W_2}{\\gamma} + \\frac{1}{n}\\sum_{i=1}^{n}\\log(x_i - \\alpha) - \\frac{\\sum_{i=1}^{n}\\log(x_i - \\alpha)(x_i - \\alpha)^{\\gamma}}{\\sum_{i=1}^{n}(x_i - \\alpha)^{\\gamma}} \\right)^2 + \\left( \\frac{1}{n}\\sum_{i=1}^{n}\\frac{1}{x_i - \\alpha} \\times \\frac{\\sum_{i=1}^{n}(x_i - \\alpha)^{\\gamma}}{\\sum_{i=1}^{n}(x_i - \\alpha)^{\\gamma-1}} - W_3 \\right)^2 \\right]"
description: "引入权重以减少小样本偏差，偏差减少约 7 倍。"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数，控制分布形状"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数，也称特征寿命"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数，也称最小寿命"
    range: "γ < min(X)"
  - symbol: "W₁, W₂, W₃"
    description: "修正权重，用于减小偏差"
    range: "W₁≈1, W₂≈1, W₃依赖于γ"
  - symbol: "n"
    description: "样本量"
    range: "n ≥ 3"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 X] --> B[数据预处理<br/>排序、确定搜索范围]
    B --> C[计算权重 W1, W2<br/>查表或直接使用]
    C --> D[数值搜索形状和位置参数<br/>最小化目标函数]
    D --> E{收敛?}
    E -->|否| D
    E -->|是| F[动态计算权重 W3<br/>基于当前形状参数]
    F --> G[代数计算尺度参数<br/>使用公式求解]
    G --> H[输出结果<br/>beta, eta, gamma]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: true
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-088"
    title: "Nearly unbiased estimators for the three-parameter Weibull distribution"
    author: "Cousineau, D."
    year: 2009
    publication: "British Journal of Mathematical and Statistical Psychology"
---

# 算法原理

加权极大似然估计（Weighted Maximum Likelihood Estimation, WMLE）是对传统极大似然估计（MLE）的改进方法。MLE 在小样本情况下会产生显著偏差，WMLE 通过引入三个权重（W₁、W₂、W₃）来修正这种偏差。

**核心思想**：在 MLE 方程中引入权重项，使估计参数的偏差显著减小。蒙特卡洛模拟表明，与迭代 MLE 技术相比，偏差减少了 7 倍（无论样本量大小），对于非常小的样本量，参数估计的变异性也减少了 7 倍。

**两步法策略**：
1. **搜索阶段**：通过数值搜索同时估计位置参数 γ 和形状参数 β
2. **代数求解**：在获得 γ 和 β 后，直接通过代数公式计算尺度参数 η

## 威布尔分布基础

概率密度函数（PDF）：

$$
f(x | \beta, \eta, \gamma) = \frac{\beta}{\eta} \left( \frac{x - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

累积分布函数（CDF）：

$$
F(x | \beta, \eta, \gamma) = 1 - \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

## 标准 MLE 方程

搜索 γ 和 α：

$$
\{\hat{\gamma}, \hat{\alpha}\}_{\mathrm{MLE}} = \arg \min_{\gamma, \alpha} \left[ \left( \frac{1}{\gamma} + \frac{1}{n}\sum_{i=1}^{n}\log(x_i - \alpha) - \frac{\sum_{i=1}^{n}\log(x_i - \alpha)(x_i - \alpha)^{\gamma}}{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma}} \right)^2 + \left( \frac{1}{n}\sum_{i=1}^{n}\frac{1}{x_i - \alpha} \times \frac{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma}}{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma-1}} - \frac{\gamma}{\gamma-1} \right)^2 \right]
$$

代数求解 β：

$$
[\hat{\eta} | \hat{\beta}, \hat{\gamma}]_{\mathrm{MLE}} = \sqrt[\hat{\beta}]{\frac{1}{n}\sum_{i=1}^{n}(x_i - \hat{\gamma})^{\hat{\beta}}}
$$

## WMLE 加权方程

搜索 γ 和 α：

$$
\{\hat{\gamma}, \hat{\alpha}\}_{W} = \arg \min_{\gamma, \alpha} \left[ \left( \frac{W_2}{\gamma} + \frac{1}{n}\sum_{i=1}^{n}\log(x_i - \alpha) - \frac{\sum_{i=1}^{n}\log(x_i - \alpha)(x_i - \alpha)^{\gamma}}{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma}} \right)^2 + \left( \frac{1}{n}\sum_{i=1}^{n}\frac{1}{x_i - \alpha} \times \frac{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma}}{\sum_{i=1}^{n}(x_i - \alpha)^{\gamma-1}} - W_3 \right)^2 \right]
$$

代数求解 β：

$$
[\hat{\eta} | \hat{\beta}, \hat{\gamma}]_{W} = \sqrt[\hat{\beta}]{\frac{1}{n W_1}\sum_{i=1}^{n}(x_i - \hat{\gamma})^{\hat{\beta}}}
$$

## 权重定义与计算

$$
\begin{aligned}
W_1 &= \frac{1}{n}\sum_{i=1}^{n}\log\left(\frac{1}{1-F(x_i)}\right) \\[6pt]
W_2 &= \frac{\sum_{i=1}^{n}\log\frac{1}{1-F(x_i)}\log\log\frac{1}{1-F(x_i)}}{\sum_{i=1}^{n}\log\frac{1}{1-F(x_i)}} - \frac{1}{n}\sum_{i=1}^{n}\log\log\frac{1}{1-F(x_i)} \\[6pt]
W_3 &= W_1 \cdot \frac{\frac{1}{n}\sum_{i=1}^{n}\left(\log\frac{1}{1-F(x_i)}\right)^{-1/\gamma}}{\frac{1}{n}\sum_{i=1}^{n}\left(\log\frac{1}{1-F(x_i)}\right)^{(\gamma-1)/\gamma}}
\end{aligned}
$$

### 权重的近似值

对于未知总体参数的情况，可使用以下近似：

| 权重 | 期望值 E | 中位数 J | 几何平均 G | 依赖于 |
|------|---------|---------|-----------|--------|
| W₁ | 1 (常数) | 表2查值 | e^ψ(n)/n | n |
| W₂ | 1 - 1/n | 表3查值 | 蒙特卡洛估计 | n |
| W₃ | 依赖于γ | 依赖于γ | 依赖于γ | n, γ |

**注**：ψ(n) 是 digamma 函数，ψ(n) = Γ'(n)/Γ(n)

## 算法流程详解

### 输入
- 失效数据数组 X = [x₁, x₂, ..., xₙ]
- 样本量 n ≥ 3

### 步骤

1. **数据预处理**
   - 排序数据：x₍₁₎ ≤ x₍₂₎ ≤ ... ≤ x₍ₙ₎
   - 确定位置参数搜索范围：γ ∈ [0, x₍₁₎)
   - 确定形状参数搜索范围：β ∈ (0, 10]

2. **计算权重**
   - 根据样本量 n 从权重表中查取 W₁, W₂
   - 或直接使用近似值：W₁ = 1, W₂ = 1 - 1/n
   - W₃ 在迭代过程中动态计算（依赖于当前的 γ 值）

3. **数值搜索 γ 和 α**
   - 使用优化算法（如 Nelder-Mead、BFGS）最小化目标函数
   - 目标函数由两个平方项组成（见 WMLE 方程）
   - 约束条件：γ > 0, α < min(X)
   - 检查收敛性，未收敛则返回步骤3

4. **动态计算 W₃**
   - 使用收敛后的 γ 值
   - 根据公式计算 W₃

5. **代数计算 η**
   - 使用搜索得到的 β̂ 和 γ̂
   - 通过公式直接计算：η̂ = [(1/(n·W₁)) · Σ(xᵢ - γ̂)^β̂]^(1/β̂)

### 输出
```python
{
    "beta": 形状参数估计值,
    "eta": 尺度参数估计值,
    "gamma": 位置参数估计值,
    "success": 是否成功,
    "message": 状态信息,
    "iterations": 迭代次数
}
```

## 适用场景详解

WMLE 特别适用于以下情况：

| 场景 | 说明 |
|------|------|
| **完全样本** | 完全支持，是最常用的应用场景 |
| **截尾样本** | 理论支持，需修改似然函数以适应截尾数据 |
| **小样本 (n < 20)** | **优势领域**，偏差修正效果显著 |
| **大样本 (n > 50)** | 渐近等价于 MLE，但仍有小幅改进 |
| **β < 1** | 可处理 MLE 困难的情况，处处有定义 |

## 优缺点分析

### 优点
- **偏差修正显著**：小样本下偏差减少 7 倍
- **处处有定义**：包括 β = 1 和 β < 1 的情况
- **两步法效率高**：β 和 γ 搜索后，η 代数求解
- **理论完善**：有完整的推导和证明

### 缺点
- **计算复杂**：需要数值搜索和权重计算
- **依赖权重表**：小样本需要预计算的权重值
- **参数敏感**：W₃ 依赖于形状参数 β
- **实现难度**：比标准 MLE 更复杂

## 与其他方法对比

| 方法 | 小样本偏差 | 计算复杂度 | β < 1 适用性 | 特点 |
|------|----------|-----------|-------------|------|
| MLE | 高 | 中 | ❌ 无界 | 大样本最优 |
| WMLE | 低（优 7 倍） | 高 | ✅ 有定义 | 小样本偏差修正 |
| MMLE | 中 | 中 | ⚠️ 部分可用 | Cohen-Whitten 方法 |
| LRE | 低 | 低 | ✅ 有定义 | 简单易用 |

## 数值示例

**输入数据**：X = {310, 342, 353, 365, 383, 393, 403, 412, 451, 456}, n = 10

**真实参数**：β = 2, η = 100, γ = 300

**MLE 结果**：β̂ = 2.80, η̂ = 126.0, γ̂ = 274.8（有明显高估）

**WMLE 结果**（使用中位数权重）：β̂ = 2.29, η̂ = 116.0, γ̂ = 283.7（更接近真实值）

## 参考文献

[1] Cousineau, D. (2009). Nearly unbiased estimators for the three-parameter Weibull distribution with greater efficiency than the iterative likelihood method. *British Journal of Mathematical and Statistical Psychology*, 62(1), 167-191.

[2] Cohen, A. C., & Whitten, B. (1982). Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution. *Communications in Statistics-Theory and Methods*, 11(23), 2631-2656.

---

**相关文献**：详见 [182-088](/library/182-088) 完整论文
