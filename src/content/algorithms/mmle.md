---
method_id: mmle
method_name: 修正极大似然估计
short_name: MMLE
category: 极大化适配法
formula: '\hat\gamma=x_{(1)},\quad \hat\eta=\left[\frac{1}{n-1}\sum_{i=2}^{n}(x_{(i)}-\hat\gamma)^{\hat\beta}\right]^{1/\hat\beta}'
description: Kundu–Raqab构造的单样本形式：位置取样本最小值，删除该观测后对平移样本作固定点迭代。旧Cohen–Whitten MMLE-I原样保留为mmle_ch。
variables:
  - symbol: β
    description: 形状参数，对应Kundu–Raqab原文的α
  - symbol: η
    description: 项目尺度参数，原文θ=η^β
  - symbol: γ
    description: 位置参数，对应原文μ；本方法估计为原样本最小值
  - symbol: x_(i)
    description: 升序排列的第i个观测
  - symbol: n
    description: 原样本量
  - symbol: q
    description: 保留观测数，q=n−1
  - symbol: y_i
    description: 保留观测与估计位置的距离，y_i=x_(i)−γ̂，i=2,…,n
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true
references:
  - id: kundu-raqab-2009
    url: https://doi.org/10.1016/j.spl.2009.05.026
    relation: "直接构造依据：1840页式(4)及1841页式(6)(9)–(11)；原文两样本问题在此化简为单样本。"
    title: Estimation of R = P(Y < X) for three-parameter Weibull distribution
    author: Debasis Kundu, Mohammad Z. Raqab
    year: 2009
    publication: Statistics & Probability Letters 79(17), 1839–1846
  - id: 182-091
    relation: "旧mmle_ch的构造来源；其工程实现保留，不作为当前mmle的公式来源。"
    title: Modified maximum likelihood and modified moment estimators for the three-parameter Weibull distribution
    author: A. Clifford Cohen, Betty Whitten
    year: 1982
    publication: Communications in Statistics - Theory and Methods
implementation:
  status: "已核单样本公式及R09既有结果；本轮未开放计算器"
  summary: "mmle采用最小值位置估计、删除一个观测、对平移距离按原固定点规则估计形状和尺度；mmle_ch原字节保留旧实现。"
  differences:
    - "原文研究共享形状与位置的两样本应力–强度问题；本项目实现其单样本删最小值与剖面迭代构造，不宣称完整复现该两样本实验。"
    - "初始形状1、绝对形状步长容差1e-8、最多10000次；这些数值设置沿用R09。无Firth、额外参数上界、重试或备用求解器。"
    - "支持检查使用保留观测的最小值；R²为R09的0占位，不使用包含零距离的全样本对数回归。"
  validation: "正式对拍使用R00两批各100组存档样本，200组成功/失败集合、参数与原有诊断均与R09实际KROriginal一致，最大绝对差0。R09原批6000组CSV额外核对无不一致，最大绝对差2.2737367544323206e-13。另有独立剖面得分定根等方法测试。"
---

# 算法原理

## 1. 最小值定位与修改似然

Kundu与Raqab（2009）先用样本最小值估计位置，再删除该观测，避免在该位置计算零距离观测的对数。对单样本，记

$$\hat\gamma=x_{(1)},\qquad y_i=x_{(i)}-\hat\gamma>0,\quad i=2,\ldots,n,\qquad q=n-1.$$

其中，x₍ᵢ₎为升序观测，γ̂为位置估计，yᵢ为保留观测到该位置的距离，q为保留观测数。若最小值重复，只删除一个观测后仍有零距离，固定点规则返回失败，不继续删点。

以项目的形状β、尺度η表示，保留观测的修改对数似然为

$$\ell(\beta,\eta)=q\ln\beta-q\beta\ln\eta
 +(\beta-1)\sum_{i=2}^n\ln y_i-\eta^{-\beta}\sum_{i=2}^n y_i^\beta.$$

其中，ℓ为修改对数似然，ln为自然对数。原文用α表示形状、θ表示幂尺度，对应α=β、θ=η^β；原文式(4)的两样本构造在这里保留单样本项。

## 2. 剖面形状与固定点迭代

对尺度求导，得到条件尺度：

$$\hat\eta(\beta)=\left(\frac{1}{q}\sum_{i=2}^n y_i^\beta\right)^{1/\beta}.$$

代回似然后，形状得分方程为

$$\frac{1}{\beta}+\frac{1}{q}\sum_{i=2}^n\ln y_i
 -\frac{\sum_{i=2}^n y_i^\beta\ln y_i}{\sum_{i=2}^n y_i^\beta}=0.$$

整理为原文式(9)–(11)固定点形式的单样本化简：

$$\beta_{k+1}=
\frac{q+\beta_k\sum_{i=2}^n\ln y_i}
 {q\sum_{i=2}^n w_i(\beta_k)\ln y_i},\qquad
w_i(\beta)=\frac{y_i^\beta}{\sum_{j=2}^n y_j^\beta}.$$

其中，k为迭代次数，wᵢ为归一化幂权重。代码使用减去最大对数的指数运算和logsumexp提高数值稳定性，保留R09实际运算次序。

默认β₀=1；相邻形状的绝对差不超过1e-8时停止，最多10000次。非有限或非正的更新、达到预算仍未收敛，均返回 `fixed_point_not_converged`。不加Firth修正、额外参数上界，不重试，不使用备用求解器；初始值、容差和预算允许通过 `run()`覆盖。

## 3. 返回与支持检查

返回 `[β̂,η̂,γ̂,0.0,True]`；迭代失败返回 `[None,None,None,0.0,False]`。第四项沿用R09的R²占位，不能解释为拟合优度为零。`last_solution_info`记录迭代次数、最终步长、删除数、保留观测最小值及求解规则。

γ̂等于已删除的原最小值，而小于其余保留观测。通用全样本支持检查仍要求γ̂<x₍₁₎，不能直接套到该修改构造；实验接入须使用保留观测最小值。此次不改runner、metrics或已有研究数据，计算器仍未开放。

## 4. 旧Cohen–Whitten实现

`mmle_ch`保留原 `methods.mmle` 的全部字节。它采用Cohen–Whitten（1982）MMLE-I累计概率约束

$$-\ln\frac{n}{n+1}=\frac{(x_{(1)}-\gamma)^\beta}{\eta^\beta}.$$

旧代码以50个离散位置候选配合内层Brent形状求解，原有搜索边界、近似处理及成功标记均保持；这些工程限制不是当前K-R算法的规则。通过 `run_method('mmle_ch', sample)`调用旧版，已有冻结结果按各自版本保留。

## 5. 已完成的验证范围

正式对拍使用R00的W(2,1000,500)与W(2,1000,3000)各100组存档样本，n=7、15各50组；将同一样本分别输入新实现与R09实际KROriginal。200组成功/失败集合、三个参数和原有诊断完全相同，最大绝对差为0。两批CSV及参考代码SHA256保持，不向R00写入新结果。

补充核对使用R09原W(2,1000,500)的6000组存档样本CSV，对比全部MMLE参数与成功/失败状态。相对CSV最大绝对差为2.2737367544323206e-13；对R09实际类，三个参数和原有求解诊断逐项一致。样本CSV恢复的全部SHA256与存档相同，没有重新抽样。

`python/tests/test_mmle_kundu_raqab2009.py`另核对独立剖面得分根、单次迭代预算失败、重复最小值、形状大于10、两版注册分派及配置覆盖。验证范围是上述单样本构造与既有批次，未复现原文两样本应力–强度全部实验，也不据此断言跨条件性能优势。
