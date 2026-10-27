---
method_id: "mle"
method_name: "极大似然估计"
short_name: "MLE"
category: "极大化适配法"

# 核心信息
formula: '\ln L = n \ln\beta - n\beta\ln\eta + (\beta-1)\sum_{i=1}^{n}\ln(x_i-\gamma) - \sum_{i=1}^{n}\left(\frac{x_i-\gamma}{\eta}\right)^\beta'
description: "本项目通过条件形状求根与位置剖面搜索，寻找完整失效样本的有限局部似然极大值。经典 MLE 的渐近性质依赖正则条件，支持边界极限单独记录。"

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
    range: "模型 β > 0；本批接受 β ≥ 1"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数"
    range: "0 ≤ γ < min(x)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入样本 X] --> B[固定位置<br/>求形状并恢复尺度]
    B --> C[扫描位置剖面<br/>精化有限局部极大值]
    C --> D{存在合格有限极大值?}
    D -->|是| E[按对数似然选择候选]
    D -->|否| F[返回明确失败]
    E --> G[另记支持边界极限]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: false
  large_sample: true

# 相关文献
references:
  - id: "182-105"
    relation: "数值基准与发散问题来源；未采用其完整 GEV 求解和置信区间流程。"
    title: "Maximum Likelihood Estimation in the 3-parameter Weibull Distribution: A Look through the Generalized Extreme-value Distribution"
    author: "Hirose, H."
    year: "1996"
    publication: "IEEE Transactions on Dielectrics and Electrical Insulation"
  - id: "182-090"
    relation: "理论背景：非正则似然及边界性质。"
    title: "Maximum likelihood estimation in a class of nonregular cases"
    author: "Smith, R. L."
    year: "1985"
    publication: "Biometrika"
  - id: "182-101"
    relation: "方法综述与比较背景。"
    title: "Fitting the Three-Parameter Weibull Distribution: Review and Evaluation of Existing and New Methods"
    author: "Cousineau, D."
    year: "2009"
    publication: "IEEE Transactions on Dielectrics and Electrical Insulation"

# 当前实现与论文的关系
implementation:
  status: "标准似然的工程实现"
  summary: "实现标准三参数似然，采用非负位置约束和条件剖面搜索，返回有限局部极大值；Hirose（1996）仅作数值基准，未复现其 GEV 求解流程及置信区间。"
  differences:
    - "位置限定为 0≤γ<最小观测值；论文中的负位置、参数发散及 GEV 重参数化流程未实现。"
    - "2026-10-16起在条件搜索中施加β≥1，比较内部有限局部极大值与γ=0单侧极大值；不把β=1、γ趋于最小观测值的开边界极限伪装成有限解。有限网格及局部精化不构成全局搜索证明。当前接口仅处理完整失效样本。"
  validation: "已有 Hirose 论文数值基准与边界测试；相同样本上的数值吻合不能证明求解流程、参数域及整篇实验均已复现。"
---

# 极大似然估计 (MLE)

原文入口：[Hirose（1996）数值基准](../182-105-pdf原文.md)、[Smith（1985）非正则理论](../182-090-pdf原文.md)。本批使用标准似然及明确的工程接受域；不声称复现Hirose的完整求解流程。

## 1. 基本思想

极大似然估计 (MLE) 的核心思想是：寻找一组参数 $(\hat{\beta}, \hat{\eta}, \hat{\gamma})$，使得在该组参数下，观测到当前数据集 $X = \{x_1, ..., x_n\}$ 的概率密度乘积（即似然函数）最大。

即：**已经发生的事情应该是概率最大的事情**。

## 2. 似然函数

威布尔分布的概率密度函数 (PDF)：

$$
f(x | \beta, \eta, \gamma) = \frac{\beta}{\eta} \left( \frac{x - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x - \gamma}{\eta} \right)^\beta \right]
$$

假设样本相互独立，则**似然函数**为各样本点概率密度的乘积：

$$
L(\beta, \eta, \gamma) = \prod_{i=1}^{n} f(x_i | \beta, \eta, \gamma) = \prod_{i=1}^{n} \frac{\beta}{\eta} \left( \frac{x_i - \gamma}{\eta} \right)^{\beta - 1} \exp\left[ -\left( \frac{x_i - \gamma}{\eta} \right)^\beta \right]
$$

为简化计算（将乘积转化为求和），取**对数似然函数**：

$$
\ln L = n \ln \beta - n \beta \ln \eta + (\beta - 1) \sum_{i=1}^{n} \ln(x_i - \gamma) - \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta
$$

## 3. 似然方程

对 $\beta, \eta, \gamma$ 分别求偏导；内部驻点要求以下导数为零，工程边界采用单侧最优条件：

$$
\frac{\partial \ln L}{\partial \beta} = \frac{n}{\beta} - n \ln \eta + \sum_{i=1}^{n} \ln(x_i - \gamma) - \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta \ln\left( \frac{x_i - \gamma}{\eta} \right) = 0
$$

$$
\frac{\partial \ln L}{\partial \eta} = -\frac{n \beta}{\eta} + \frac{\beta}{\eta} \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^\beta = 0
$$

$$
\frac{\partial \ln L}{\partial \gamma} = -(\beta - 1) \sum_{i=1}^{n} \frac{1}{x_i - \gamma} + \frac{\beta}{\eta} \sum_{i=1}^{n} \left( \frac{x_i - \gamma}{\eta} \right)^{\beta - 1} = 0
$$

该方程组无解析解，需通过数值方法（如 Nelder-Mead、Newton-Raphson）迭代求解。

## 4. 无界问题与非正则边界

当 $\beta < 1$ 且 $\gamma$ 未知时，似然函数可能趋向无穷大。

原因：当 $\gamma \to \min(x_i)$ 时，$x_{\min} - \gamma \to 0$，若 $\beta < 1$，则 $(x_{\min} - \gamma)^{\beta - 1} \to \infty$，导致似然函数无界。

Smith（1985）讨论了这类非正则模型的渐近性质，不能直接套用常规正则MLE结论。无约束模型在β<1处的似然无界，与某组样本是否存在β≥1的有限局部极大值是两个问题。新版没有找到合格有限极大值时返回`no_finite_local_maximum`；数值求解异常返回`profile_solver_failed`，均不补默认参数。这些状态只描述本次数值搜索。

## 5. 参数发散问题与平台约束

Hirose (1996) 指出：对高度负偏的样本，三参数 MLE 会出现"参数发散"（$\hat{\beta} \to \infty$、$\hat{\gamma} \to -\infty$，而对数似然收敛于 Gumbel 极限）。

本平台面向寿命数据，采用工程约束 $0 \leq \gamma < \min(x_i)$：在已核验的相关论文样本上，估计收敛到 $\gamma = 0$ 边界，即两参数威布尔（W2P）的 MLE 解（与 Hirose 1996 第 5.3 节的 W2P 基准一致）。

## 6. 条件剖面与有限局部极大值

本批统一使用**标准似然＋明确的工程接受域**：β≥1、η>0、0≤γ<x₍₁₎。固定γ时，记未约束形状得分方程的根为β₀(γ)，有：

$$
U_\beta(\beta;\gamma)=\frac1\beta+\overline{\ln d}
-\frac{\sum_i d_i^\beta\ln d_i}{\sum_i d_i^\beta},\qquad d_i=x_i-\gamma,
$$
$$
\hat\beta(\gamma)=\max\{1,\beta_0(\gamma)\},\qquad
\hat\eta(\gamma)=\left[\frac1n\sum_i d_i^{\hat\beta(\gamma)}\right]^{1/\hat\beta(\gamma)},
$$
$$
\ell_p(\gamma)=\ell\{\hat\beta(\gamma),\hat\eta(\gamma),\gamma\}.
$$

若β₀<1，应保留β=1并重新计算η，此时η为距离的算术均值，Uβ(1;γ)≤0；边界最优不要求Uβ=0。β<1的剖面只能作为注明参数域的扩展诊断，不能与本批接受域的条件最优曲线混用。等值退化样本没有有限条件形状最优值。

Research00两报告调用[共享条件诊断](../../../python/methods/conditional_profiles.py)中的`mle_profile()`；横轴为候选γ，纵轴为条件β或ℓₚ的增量，曲线不表示历史优化器的迭代轨迹，历史结果仍以各批冻结程序为准。

2026-10-16起，[当前估计器](../../../python/methods/mle.py)使用同一条件构造：按最小观测值归一化，在普通位置及接近两端的位置加密扫描，以位置得分由正转负的交点和剖面峰值精化有限局部极大值，另检查γ=0单侧边界。v2补充精化位置得分的局部低谷，避免相邻网格同号时漏掉很窄的极大—极小配对。存在多个有限候选时选择似然较大的一个。

β=1、γ趋于x₍₁₎时，有η趋于mean(x−x₍₁₎)，对数似然趋于−n[1+ln η]。该点不在γ<x₍₁₎的支持域内，即使其极限似然高于选中的有限局部极大值，也只记录为`support_boundary_limit`和`boundary_limit_exceeds_selected`，不以任意ε构造估计值。本实现沿用有限局部MLE口径，不声称求得完整参数域的全局最大值。

程序版本为`2026-10-16-profile-v2`。更新前程序与依赖见[日期备份](https://github.com/NEUwpy/weibull-research/blob/main/Study/04-study-%E5%B0%8F%E6%A0%B7%E6%9C%AC%E4%B8%89%E5%8F%82%E6%95%B0Weibull%E4%BC%B0%E8%AE%A1%E6%96%B9%E6%B3%95%E6%AF%94%E8%BE%83%E4%B8%8E%E9%80%89%E6%8B%A9/%E7%A8%8B%E5%BA%8F/%E5%8E%86%E5%8F%B2%E7%89%88%E6%9C%AC/2026-10-16-%E6%B1%82%E8%A7%A3%E6%9B%B4%E6%96%B0%E5%89%8D/%E7%89%88%E6%9C%AC%E8%AF%B4%E6%98%8E.md)，旧实验不覆盖；Study04正式比较需使用新版另算。
