---
method_id: mdm
method_name: 最小差异法
short_name: MDM
category: 极小化适配法
formula: '\beta^*(\gamma)=\arg\min_\beta\sigma_\eta(\beta,\gamma),\quad g(\gamma)=\frac{d\sigma_{\eta,\min}(\gamma)}{d\gamma},\quad g(\hat\gamma)=\delta,\quad\hat\beta=\beta^*(\hat\gamma),\quad\hat\eta=\frac1n\sum_i\eta_i(\hat\beta,\hat\gamma)'
description: "通过伪尺度参数的条件最小差异和梯度偏移判据，确定形状、尺度和位置参数。"
variables:
  - symbol: t_i
    description: 第 i 个样本值
  - symbol: n
    description: 样本量
  - symbol: β
    description: 形状参数
  - symbol: η
    description: 尺度参数
  - symbol: η_i
    description: 基于第 i 个样本点估计的伪尺度参数
  - symbol: "η̄"
    description: 伪尺度参数的均值
  - symbol: γ
    description: 位置参数
  - symbol: F(t)
    description: 累积分布函数
  - symbol: σ_η
    description: 伪尺度参数的标准差
  - symbol: σ_{η,min}(γ)
    description: 固定位置γ、对形状取最小值后的条件标准差
  - symbol: β*(γ)
    description: 固定位置γ时使伪尺度标准差最小的形状
  - symbol: ∇γ
    description: 条件最小标准差关于位置参数的梯度，本文也记为g(γ)
  - symbol: δ
    description: 梯度偏移值
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true
references:
  - id: 182-030
    relation: "最小差异方法的早期研究背景；本页现行偏移判据主要对照2025年论文。"
    title: 威布尔分布参数估计的最小差异法
    author: Liyang Xie, et al.
    year: 2022
    publication: International Journal of Structural Stability and Dynamics
  - id: 182-046
    relation: "当前核心依据：伪尺度、最小差异与梯度偏移；默认秩和数值搜索存在项目改写。"
    title: 基于统计最小差异原理的Weibull分布参数估计方法
    author: 谢里阳, 朱文慧, 吴宁祥, 杨小玉
    year: 2025
    publication: 东北大学学报（自然科学版）

# 当前实现与论文的关系
implementation:
  status: "单一现行实现，原文差异待讨论"
  summary: "采用 Bernard 近似秩和连续形状优化，在相邻梯度点之间线性插值确定位置。另有零位置和右端回退规则。"
  differences:
    - "现行mdm.py默认绘图位置为Bernard近似；原文式(3)采用精确中位秩。是否修改默认秩须先与用户讨论。"
    - "原文按离散梯度曲线和偏移量定位。相邻点线性插值、连续形状优化、差分步长及边界处理是本软件的数值规则。"
  validation: "已有精确中位秩公式、理想样本、尺度回代与偏移方向测试；论文未给出完整数值的样本A/B不能据此声称已逐样本复现。"

# 实现与核验资料
implementation_notes: |
  ## 4. 当前数值求解与回退

  当前 MDM 按几何网格试算位置，并计算各位置的条件最小标准差、最优形状和廓线梯度。网格由 `gamma_steps` 控制，在最小观测值 $t_{(1)}$ 附近更密。过程图读取本次计算的梯度点及采纳位置。

  1. 若 $g(0)\ge\delta$，按非负位置约束取 $\hat\gamma=0$，记录为 `truncated_at_zero`。
  2. 若 $g(0)<\delta$，检查相邻梯度是否夹住 $\delta$。有多个区间时取最靠右的已检出区间。网格未夹住时，向 $t_{(1)}$ 附近补探。用区间中点的梯度缩小区间，宽度达到 $10^{-5}t_{(1)}$ 后，在线段上取交点

  $$
  \hat\gamma=\gamma_L+\frac{\delta-g(\gamma_L)}{g(\gamma_R)-g(\gamma_L)}(\gamma_R-\gamma_L)
  $$

  端点达到 $\delta$ 时直接取该端点。该分支记录为 `interpolated_crossing`。图中分别标示插值交点与实际梯度求值。
  3. 探测后仍缺少夹住目标的相邻点时，按右端回退规则返回接近 $t_{(1)}$ 的内部浮点位置，记录为 `right_edge_fit`。在通用过程图中，回退目标用虚拟梯度表示。
---

# 算法原理

## 1. 基本思想

最小差异法（MDM）的核心思想是：如果所选择的形状参数 $\beta$ 和位置参数 $\gamma$ 是真实的，那么利用样本中每一个数据点 $t_i$ 及其对应的累积失效概率 $F(t_i)$ 反算出来的尺度参数 $\eta_i$ 之间的差异应该最小。

对于三参数威布尔分布，累积分布函数 (CDF) 为

$$
F(t) = 1 - \exp \left[ - \left(\frac{t - \gamma}{\eta}\right)^{\beta} \right]
$$

由此可构造尺度参数的**伪估计量**

$$
\eta_i = \frac{t_i - \gamma}{\left(-\ln(1 - F(t_i))\right)^{1/\beta}}
$$

其中 $F(t_i)$ 可使用中位秩公式估计。精确形式基于 F 分布中位数

$$
\hat{F}(t_{(i)}) = \frac{i}{i + (n + 1 - i) \cdot F_{2(n+1-i), 2i, 0.5}}
$$

式中 $F_{2(n+1-i), 2i, 0.5}$ 是自由度为 $2(n+1-i)$ 和 $2i$ 的 F 分布的中位数。

工程中常采用如下近似形式

$$
F(t_i) \approx \frac{i - 0.3}{n + 0.4}
$$

## 2. 最小差异准则

由于样本的随机性，计算出的 $n$ 个 $\eta_i$ 值不可能完全相等。我们用它们的标准差 $\sigma_\eta$ 来衡量这种差异

$$
\sigma_\eta(\beta, \gamma) = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (\eta_i - \bar{\eta})^2}
$$

原始最小差异准则是对 $\beta$、$\gamma$ 搜索，使 $\sigma_\eta$ 最小。当前采用的正偏移版本保留固定位置下的形状极小化：

$$
\beta^*(\gamma)=\arg\min_\beta\sigma_\eta(\beta,\gamma),\qquad
\sigma_{\eta,\min}(\gamma)=\sigma_\eta(\beta^*(\gamma),\gamma).
$$

位置随后按下一节的梯度偏移判据确定，不能将这个版本概括为 $\beta$、$\gamma$ 联合最小化标准差。

## 3. 梯度偏移补偿

研究表明（[文献 182-046](/library/182-046)），由于样本的统计不确定性，尺度参数估计值标准差的条件最小值 $\sigma_{\eta,\min}(\gamma)$ 的梯度在位置参数的真实值处**未必等于零**。基于某一样本得到的梯度在真实位置参数点的值可能大于零，也可能小于零。如果简单地应用极值判据（梯度为零），对于某些样本，位置参数估计值的误差可能非常大。

为了提高稳健性，引入**偏移值 $\delta$**，即寻找位置参数 $\gamma$，使得条件最小标准差的梯度等于一个大于零的值而非零。记 $g(\gamma)=d\sigma_{\eta,\min}(\gamma)/d\gamma$；原文式(7)用前向差分评价该梯度：

$$
\nabla \gamma = \frac{\sigma_{\eta,\min}(\gamma + \Delta\gamma) - \sigma_{\eta,\min}(\gamma)}{\Delta\gamma}
$$

确定有效交点 $g(\hat\gamma)=\delta$ 后，回代条件形状并取伪尺度均值：

$$
\hat\beta=\beta^*(\hat\gamma),\qquad
\hat\eta=\frac1n\sum_{i=1}^n\eta_i(\hat\beta,\hat\gamma).
$$

当前程序在内部点用中心差分，零位置附近用前向差分，最小观测附近用后向差分；它们是上述梯度的数值评价规则。

根据 [文献 182-046](/library/182-046) 的研究（基于 120 个参数估计案例，以及形状参数 $\beta$ 在 2~5 范围内的近千个样本），偏移值取 $\delta = 0.1$ 效果良好。

> **注**：偏移值的最优取法可能与样本特征和样本量有关，仍需进一步研究。
