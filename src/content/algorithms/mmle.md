---
method_id: mmle
method_name: 修正极大似然估计
short_name: MMLE
category: 极大化适配法
formula: \hat{\theta} = \frac{1}{n}\sum_{i=1}^{n}(x_i - \gamma)^{\hat{\delta}}, \quad -\ln\frac{n}{n+1} = \frac{(x_1 - \gamma)^{\delta}}{\theta}
description: 修正极大似然估计 (Modified Maximum Likelihood Estimation, MMLE) 是对传统极大似然估计的改进方法。当形状参数 δ < 2 时，三参数威布尔分布的 MLE 不满足正则条件，可能产生不一致估计或根本不存在。MMLE 通过用替代约束条件替换似然方程 ∂ln L/∂γ = 0，提供了更稳健的估计。研究表明，MMLE 在偏差、方差和计算简便性方面常优于传统 MLE。
variables:
  - symbol: x_i
    description: 第 i 个样本值
  - symbol: n
    description: 样本量
  - symbol: δ
    description: 形状参数（本文献使用的符号，对应 β）
  - symbol: β
    description: 尺度参数（本文献使用的符号，对应 η）
  - symbol: γ
    description: 位置参数（阈值参数）
  - symbol: θ
    description: 尺度参数的变换形式，θ = β^δ
  - symbol: x₁
    description: 第一顺序统计量（最小样本值）
  - symbol: Γ_k
    description: 伽马函数值，Γ_k = Γ(1 + k/δ)
  - symbol: Γ(·)
    description: 伽马函数
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true
references:
  - id: 182-091
    title: Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution
    author: A. Clifford Cohen, Betty Whitten
    year: 1982
    publication: Communications in Statistics - Theory and Methods
---

# 算法原理

## 1. 基本思想

修正极大似然估计（MMLE）由 Cohen 和 Whitten 于 1982 年提出，用于解决三参数威布尔分布参数估计中的正则性问题。

### 1.1 传统 MLE 的局限性

对于三参数威布尔分布，当形状参数 $\delta < 2$ 时：

1. **正则条件不满足**：极大似然估计不满足通常的正则条件
2. **渐近性质失效**：可能产生不具有通常渐近性质的估计，甚至可能产生不一致的估计
3. **估计不存在**：对于某些样本，极大似然估计根本不存在（特别当 $\delta < 1$ 且 $\gamma$ 未知时）

### 1.2 MMLE 的核心思路

MMLE 通过**替换似然方程** $\partial \ln L / \partial \gamma = 0$，用其他更稳健的约束条件来估计位置参数 $\gamma$，同时保留另外两个似然方程。

## 2. 威布尔分布的基本形式

三参数威布尔分布的概率密度函数：

$$
f(x; \gamma, \delta, \beta) = \frac{\delta}{\beta^{\delta}}(x - \gamma)^{\delta - 1}\exp\left[-\left(\frac{x - \gamma}{\beta}\right)^{\delta}\right]
$$

其中 $\gamma < x < \infty$，$\delta > 0$，$\beta > 0$。

相应的累积分布函数：

$$
F(x; \gamma, \delta, \beta) = 1 - \exp\left\{-\left[\frac{x - \gamma}{\beta}\right]^{\delta}\right\}
$$

> **符号说明**：本文献使用 $\delta$ 表示形状参数、$\beta$ 表示尺度参数，这与项目其他文档（使用 $\beta$ 为形状参数、$\eta$ 为尺度参数）符号不同，但数学本质一致。

### 2.1 分布特征量

$$
\mu_x = \gamma + \beta\Gamma_1, \quad \sigma_x^2 = \beta^2\left[\Gamma_2 - \Gamma_1^2\right]
$$

$$
Me_x = \gamma + \beta(\ln 2)^{1/\delta}, \quad \alpha_{3:x} = \frac{\Gamma_3 - 3\Gamma_2\Gamma_1 + 2\Gamma_1^3}{\left[\Gamma_2 - \Gamma_1^2\right]^{3/2}}
$$

其中 $\Gamma_k = \Gamma(1 + k/\delta)$，$\Gamma(\cdot)$ 为伽马函数。

## 3. 五种 MMLE 变体

### 3.1 MMLE-I（基于第一顺序统计量的累积分布）

用 $E[F(X_1)] = F(x_1)$ 替换 $\partial \ln L / \partial \gamma = 0$。

由于 $E[F(X_r)] = r/(n+1)$，当 $r=1$ 时：

$$
-\ln\frac{n}{n+1} = \frac{(x_1 - \gamma)^{\delta}}{\theta}
$$

其中 $\theta = \beta^{\delta}$。

**特点**：第一个顺序统计量包含关于 $\gamma$ 的信息最多，是最常用的 MMLE 变体。

### 3.2 MMLE-II（基于第一顺序统计量的期望）

用 $E(X_1) = x_1$ 替换 $\partial \ln L / \partial \gamma = 0$：

$$
\gamma + \frac{\beta}{n^{1/\delta}}\Gamma_1 = x_1
$$

其中 $E(X_1) = \gamma + \frac{\beta}{n^{1/\delta}}\Gamma_1$。

### 3.3 MMLE-III（基于样本均值）

用 $E(X) = \bar{x}$ 替换 $\partial \ln L / \partial \gamma = 0$：

$$
\gamma + \beta\Gamma_1 = \bar{x}
$$

### 3.4 MMLE-IV（基于样本方差）

用 $V(X) = s^2$ 替换 $\partial \ln L / \partial \gamma = 0$：

$$
\beta^2\left[\Gamma_2 - \Gamma_1^2\right] = s^2
$$

### 3.5 MMLE-V（基于样本中位数）

用 $Me_X = x_{me}$ 替换 $\partial \ln L / \partial \gamma = 0$：

$$
\gamma + \beta(\ln 2)^{1/\delta} = x_{me}
$$

## 4. 估计方程与求解

以 **MMLE-I** 为例，需要联立求解三个方程：

**方程 (A)** — 关于 $\delta$ 的似然方程：

$$
\left[\frac{\sum_{i=1}^{n}(x_i - \gamma)^{\delta}\ln(x_i - \gamma)}{\sum_{i=1}^{n}(x_i - \gamma)^{\delta}} - \frac{1}{\delta}\right] - \frac{1}{n}\sum_{i=1}^{n}\ln(x_i - \gamma) = 0
$$

**方程 (B)** — 关于 $\theta$ 的似然方程：

$$
\hat{\theta} = \frac{1}{n}\sum_{i=1}^{n}(x_i - \gamma)^{\hat{\delta}}
$$

**方程 (C)** — MMLE-I 的约束条件：

$$
-\ln\frac{n}{n+1} = \frac{(x_1 - \gamma)^{\delta}}{\theta}
$$

### 4.1 计算流程

1. **选择 $\gamma$ 的初始值**：$\gamma_1 < x_1$
2. **固定 $\gamma$，求解方程 (A)**：得到 $\delta_1$
3. **计算 $\theta_1$**：从方程 (B) 得出
4. **检验约束条件**：将 $\gamma_1, \delta_1, \theta_1$ 代入方程 (C)
5. **迭代搜索**：若不满足，调整 $\gamma$ 值，重复步骤 2-4
6. **线性插值**：找到 $\gamma_i, \gamma_j$ 使得 $|\gamma_i - \gamma_j|$ 足够小且约束条件在两点间跨越目标值

### 4.2 约束条件

- 必须满足 $\hat{\gamma} < x_1$
- $\hat{\delta}$ 限制在区间 $(0.1, 15.0)$ 内
- $\hat{\gamma}$ 的搜索范围：从低于样本均值十个标准差到 $x_1 - 10^{-4}$

## 5. 与传统 MLE 的比较

| 特性 | MLE | MMLE-I/II |
|------|-----|-----------|
| $\delta < 2$ 时的正则性 | 不满足 | 适用 |
| 计算复杂度 | 高 | 中等 |
| 小样本偏差 | 显著 | 较小 |
| $\delta < 1$ 时的存在性 | 可能不存在 | 存在 |
| 渐近方差有效性 | 有效（当 $\delta > 2$） | 近似有效 |

## 6. Monte Carlo 研究结论

根据 [文献 182-091](/library/182-091) 的模拟研究：

1. **当 $\delta \geq 2.2156$（$\alpha_3 < 0.5$）时**：MLE 在偏差和方差方面表现良好
2. **当 $\delta \leq 2.2156$ 时**：MMLE-I 和 MMLE-II 是首选的估计量
3. **计算时间方面**：MMLE 约为 MLE 的 1/3 到 1/2
4. **建议**：
   - 计算时间不是关键因素时，推荐 MMLE-I 或 MMLE-II
   - 计算时间昂贵时，推荐 MME-I（修正矩估计）
