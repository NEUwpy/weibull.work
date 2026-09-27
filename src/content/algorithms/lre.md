---
method_id: "lre"
method_name: "线性回归估计"
short_name: "LRE"
category: "线性回归法"

# 核心信息
formula: '\hat{\gamma} = \arg\max_\gamma \rho^2(\gamma), \quad \rho = \mathrm{corr}(\ln(t-\gamma), \ln(-\ln(1-\hat{F})))'
description: "本项目 LRE 使用 Bernard 绘图位置，在 γ≥0 的可行域内最大化 Weibull 图相关系数平方，再用概率分数对对数寿命的 OLS 回归恢复形状和尺度。Li (1994) 提供线性化背景，Park (2018) 提供相关系数路线的文献依据；本实现不等于 Li 第4节公式或 Park 全方法的完整复现。"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数（回归斜率）"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数（平台工程约束 γ ≥ 0）"
    range: "0 ≤ γ < t_(1)"
  - symbol: "ρ"
    description: "Pearson 相关系数（平方值作为目标函数）"
    range: "ρ ∈ [-1, 1]"
  - symbol: "F̂"
    description: "中位秩估计（默认 Bernard 近似）"
    range: "(0, 1)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 t] --> B[计算中位秩 v=ln-ln 1-F]
    B --> C[优化 γ 使相关系数平方最大]
    C --> D[OLS 回归<br/>v 对 ln t-γ]
    D --> E[β = 斜率, η = e^{-截距/β}]
    E --> F[输出 β, η, γ, R²]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-107"
    title: "A General Linear-Regression Analysis Applied to the 3-Parameter Weibull Distribution"
    author: "Li, Y.-M."
    year: "1994"
    publication: "IEEE Transactions on Reliability"
  - id: "182-106"
    title: "A Note on the Existence of the Location Parameter Estimate of the Three-Parameter Weibull Model Using the Weibull Plot"
    author: "Park, C."
    year: "2018"
    publication: "Mathematical Problems in Engineering"
---

# 线性回归估计 (LRE)

## 1. 线性化变换

三参数威布尔 CDF 经双对数变换（Li 1994 式(2-4)，或称 Weibull 图坐标）：

$$
Y = \ln(-\ln(1 - \hat{F})), \qquad X = \ln(t - \gamma)
$$

有直线关系 $Y = \beta X - \beta \ln \eta$。因此：
- $\hat{\beta} = \mathrm{slope}(Y \sim X)$
- $\hat{\eta} = \exp(-\mathrm{intercept}/\hat{\beta})$

## 2. γ 确定：相关系数最大化

$\gamma$ 未知时，搜索使 $Y$ 与 $\ln(t-\gamma)$ 的 Pearson 相关系数平方 $\rho^2$ 最大的位置。该路线与 Park (2018) 讨论的 Weibull 图相关系数估计相关，但绘图位置和位置约束须单独核对；不能把原文的存在性结论直接套用于任意工程约束。

当前代码合并201点线性网格和201点几何网格，在最佳点邻域做有界标量精化，然后回归 $Y$ 对 $X$。候选位置非负；目标函数拒绝 $\gamma\geq t_{(1)}-10^{-5}$，网格另有相对最小间隔保护。这里的绝对容差依赖数据单位，不能描述为完全尺度无关。旧版 L-BFGS-B 已不代表当前实现。

默认绘图位置为 $\hat F_i=(i-0.3)/(n+0.4)$。Park (2018) 式(4)对 n≤10 使用 $(i-3/8)/(n+1/4)$，对 n≥11 使用 $(i-1/2)/n$，与本项目默认值不同。

## 3. 与其他方法的关系

| 方法 | γ 确定 | β, η 确定 |
|---|---|---|
| **本 LRE** | Bernard分数下优化 $\rho^2$ | $Y$ 对 $X$ 的OLS |
| 本项目LS（Soman–Misra分支） | 次序统计量期望分数下最大化F比 | $X$ 对分数的OLS，斜率取倒数 |
| 相关法位置＋2P MLE组合 | 指定分数和可行域的相关系数法 | 固定位置后求2P MLE；是另一组合 |
| Li (1994) §4、§5 | 位置近似构造或联立曲线求解 | 应按对应原文算法实现，不能与本LRE等同 |

Li (1994) 式(2-4)支持线性化关系，但其第4节采用有限差分等构造推导位置近似，不是当前相关系数优化器的直接来源。Park (2017) 原文现已入库为182-115（2026-09-27），完整算法与当前实现仍待逐步核对，不能未经核对便将某个后续2P MLE步骤称为其唯一全方法。

对于相同分数和位置，带截距OLS的F比与 $\rho^2$ 单调对应；当前LS与LRE的主要差别是分数及回归方向。版本证据、公式推导和实际样本诊断见[四方法实现核查](../../../Research/09-Weibull参数估计方法谱系与比较基线/06-现有四方法实现与版本核查.md)。

## 4. 边界与失败语义

- $\gamma \geq 0$（平台工程约束）。
- 全等或近退化样本返回 `degenerate_sample`，不将形状1作为有效估计返回。
- n < 3 返回 `insufficient_sample`。
- 本类只接收完整样本，没有实现删失观测的秩调整或似然扩展。
- 返回的R²由基础类在双对数变换后的概率图上计算，不是原始CDF残差的R²，也不是参数估计误差。
