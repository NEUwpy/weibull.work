### Source: src/data/methods.json
- **Location**: Element with id "mle" and "wmle"
- **Excerpt**: 
    - MLE: "通过最大化似然函数... MLE大样本最优... 解似然方程组。当 β<1 时无界。"
    - WMLE: "引入权重以减少小样本偏差... 偏差减少约 7 倍。"
- **Analysis**: Provides the high-level definition and the primary trade-off (Large vs Small sample performance).

### Source: src/content/algorithms/wmle.md
- **Location**: Section "算法原理" (Algorithm Principle)
- **Excerpt**: "MLE 在小样本情况下会产生显著偏差... 核心思想：在 MLE 方程中引入权重项... 偏差减少了 7 倍"
- **Analysis**: Explains the motivation for improvement.

- **Location**: Section "标准 MLE 方程" (Standard MLE Equation)
- **Excerpt**: Shows the specific minimization formula for MLE: $\min_{\gamma, \alpha} [ (\frac{1}{\gamma} + ...)^2 + ... ]$.
- **Analysis**: Defines the mathematical process of MLE (solving these specific equations).

- **Location**: Section "WMLE 加权方程" (WMLE Weighted Equation)
- **Excerpt**: Shows the modified formula: $\min_{\gamma, \alpha} [ (\frac{W_2}{\gamma} + ...)^2 + (... - W_3)^2 ]$.
- **Analysis**: Shows *how* the improvement is implemented mathematics (replacing 1/n terms with Weights).

- **Location**: Section "与其他方法对比" (Comparison)
- **Excerpt**: Table comparing MLE, WMLE, MMLE.
- **Analysis**: Lists MMLE as another improvement method (Cohen-Whitten).
