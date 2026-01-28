### Source: src/content/182-088-pdf翻译.md
- **Location**: Section "摘要" (Summary)
- **Excerpt**: "最大似然估计（MLE）方法是估计三参数威布尔分布参数最常用的方法。然而，它返回有偏估计... 在本文中，我们展示了如何计算权重来消除MLE方程中包含的偏差... 蒙特卡洛模拟证明了加权MLE方法的实用性。与迭代MLE技术相比，偏差减少了7倍"
- **Analysis**: Confirms the problem (Bias in MLE) and the solution (WMLE reduces bias by 7x).

- **Location**: Section "1. 引言" (Introduction)
- **Excerpt**: "这种技术的问题是它返回有偏估计量... 对于非常小的样本（八个观测值），形状参数和尺度参数可能分别被低估超过$40\%$和$30\%$... 总体而���... 估计向量的长度错误超过$50\%$。"
- **Analysis**: Quantifies the MLE bias in small samples.

- **Location**: Section "2. 迭代和加权MLE方程" (Iterative and Weighted MLE Equations)
- **Excerpt**: "迭代MLE通过同时搜索三个参数获得... $\{\hat {\gamma}, \hat {\beta}, \hat {\alpha} \} _ {\mathrm {M L E}} = \arg \max \log (\ell (\gamma , \beta , \alpha | X))"
- **Analysis**: Defines the standard MLE process (Iterative maximization of Log-Likelihood).

- **Location**: Section "2. 迭代和加权MLE方程" (Iterative and Weighted MLE Equations) - Equations (3)
- **Excerpt**: Shows the WMLE equations. "加权MLE解... 与标准MLE解完全相同，除了存在三个权重$W_{1}$、$W_{2}$和$W_{3}$。"
- **Analysis**: Explains the mechanism of improvement (introducing weights into the algebraic equations).

- **Location**: Section "9. 一般讨论" (General Discussion)
- **Excerpt**: "随着$n$的增加，这里提出的权重与MLE权重之间的差异变得非常小... 临界$n$接近80... 此时选择技术不再有影响"
- **Analysis**: Discusses when the improvement is needed (n < 80).
