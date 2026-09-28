---
method_id: mmle
method_name: 修正极大似然估计
short_name: MMLE
category: 极大化适配法
formula: \hat{\theta} = \frac{1}{n}\sum_{i=1}^{n}(x_i - \gamma)^{\hat{\delta}}, \quad -\ln\frac{n}{n+1} = \frac{(x_1 - \gamma)^{\delta}}{\theta}
description: 当前代码实现标为MMLE-I的替代约束估计，尚待独立论文核验。下文其他变体用于理论介绍，不代表平台均已实现或已经验证其性能。
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
    relation: "MMLE与修正矩估计的原始方法论文；当前仅有标为MMLE-I的待核验实现。"
    title: Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution
    author: A. Clifford Cohen, Betty Whitten
    year: 1982
    publication: Communications in Statistics - Theory and Methods

# 当前实现与论文的关系
implementation:
  status: "已有代码，论文对应核验未完成"
  summary: "现有代码标为 Cohen 与 Whitten（1982）的 MMLE-I，保留形状似然方程，以最小顺序统计量累积概率约束替换位置方程。原文已收录，但当前程序尚未完成独立论文级核验。"
  differences:
    - "只实现标为I的分支，页面介绍的II–V不代表均已实现。位置采用50个离散候选，内层用Brent求形状，没有外层插值求根。"
    - "现有程序在约束残差较大甚至无合格候选时仍可能返回成功，尚不适合作为已验真的比较基线；计算器保持未开放。"
  validation: "尚无针对MMLE的独立论文数值断言；文献链接、理论公式和已有代码均不足以确认完整复现。"
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

## 3. 五种 MMLE 变体（理论介绍，当前仅有I的代码）

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

### 4.1 当前代码流程

在位置区间 [max(0, x₁−10·std(x)), 0.99x₁] 取50个候选；每个候选内在形状区间[0.2,10]用Brent求解方程(A)，再计算(B)与(C)的残差，保留绝对残差最小者。残差足够小时提前退出，没有外层线性插值求根。当前成功标记尚未严格反映约束是否满足，因此不能仅凭返回参数认定估计有效。

## 5. 文献结果与本项目验证的区别

原论文讨论不同修正估计量的偏差、方差与计算量。具体优劣受其模拟条件和方法变体限制；当前程序尚未复现这些比较实验，不能把论文结论直接作为本实现的性能结论。原文见[文献182-091](/library/182-091)。
