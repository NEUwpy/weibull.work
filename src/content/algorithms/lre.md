---
method_id: "lre"
method_name: "线性回归估计"
short_name: "LRE"
category: "线性回归法"

# 核心信息
formula: '\hat{\gamma} = \arg\max_{0\leq\gamma<t_{(1)}} \rho(\gamma), \quad \rho = \mathrm{corr}(\ln(t-\gamma), \ln(-\ln(1-\hat{F})))'
description: "按 Park（2017）Proposed+Plot 实现完整样本参数估计：采用原文分段绘图位置，在非负位置区间最大化相关系数，再以概率图 OLS 恢复形状和尺度。"

# 变量说明
variables:
  - symbol: "β"
    description: "形状参数（回归斜率）"
    range: "β > 0"
  - symbol: "η"
    description: "尺度参数"
    range: "η > 0"
  - symbol: "γ"
    description: "位置参数（Park 原文非负搜索范围）"
    range: "0 ≤ γ < t_(1)"
  - symbol: "ρ"
    description: "Pearson 相关系数（位置搜索目标）"
    range: "ρ ∈ [-1, 1]"
  - symbol: "F̂"
    description: "Park 分段绘图位置（n≤10 与 n≥11）"
    range: "(0, 1)"

# 计算流程图（Mermaid语法）
flowchart: |
  flowchart LR
    A[输入数据 t] --> B[Park 分段绘图位置与双对数变换]
    B --> C[优化 γ 使相关系数最大]
    C --> D[OLS 回归<br/>v 对 ln t-γ]
    D --> E["β = 斜率, η = e^{-截距/β}"]
    E --> F[输出 β, η, γ, R²]

# 适用场景
applicability:
  complete_sample: true
  censored_sample: false
  small_sample: true
  large_sample: true

# 相关文献
references:
  - id: "182-115"
    url: "https://doi.org/10.23055/ijietap.2017.24.4.2848"
    relation: "直接算法依据：第2节绘图位置、第5节 Proposed+Plot；表1用于算例核验。"
    title: "Weibullness Test and Parameter Estimation of the Three-Parameter Weibull Model Using the Sample Correlation Coefficient"
    author: "Park, C."
    year: "2017"
    publication: "International Journal of Industrial Engineering: Theory, Applications and Practice"
  - id: "182-107"
    relation: "线性化背景：式(2–4)给出 Weibull 图的直线关系。"
    title: "A General Linear-Regression Analysis Applied to the 3-Parameter Weibull Distribution"
    author: "Li, Y.-M."
    year: "1994"
    publication: "IEEE Transactions on Reliability"
  - id: "182-106"
    relation: "理论补充：相关系数法的位置估计存在性。"
    title: "A Note on the Existence of the Location Parameter Estimate of the Three-Parameter Weibull Model Using the Weibull Plot"
    author: "Park, C."
    year: "2018"
    publication: "Mathematical Problems in Engineering"

# 当前实现与论文的关系
implementation:
  status: "Park（2017）Proposed+Plot 参数估计分支复现"
  summary: "按 Park（2017）Proposed+Plot 实现绘图位置、相关系数定位与 OLS，已核验论文算例；原表形状参数有末位差异。范围限于该估计分支，不含 MLE2 和拟合检验。"
  differences:
    - "这里的复现范围是完整样本 Proposed+Plot 参数估计，不包含另一 Proposed+MLE2 分支、Weibullness 假设检验、p值或临界值 Monte Carlo 模拟，也不是 Li（1994）算法复现。"
    - "原文允许相关系数最大化或式(3)定根。本实现用无量纲对数间隔网格及局部精化求解同一最大化目标；开端点由浮点可表示边界处理，不再设置固定寿命间隔。"
    - "表1的形状值为1.363，按所列样本与公式复算为1.363761（常规舍入为1.364），末位差异尚未解释；位置、尺度及相关系数符合表中精度。"
  validation: "Park 表1的24个寿命算例、独立式(3)定根与OLS核验、n=10/11分段切换、零位置边界、单位换算、退化样本及统一接口测试。历史 Bernard 版本的研究结果未重算，不作为本版验证结果。"
---

# 线性回归估计 (LRE)

## 1. 当前采用的论文方法

本页 LRE 对应 **Park（2017）第5节 Proposed+Plot**。它先确定位置参数，再对平移后的完整寿命样本做 Weibull 概率图线性回归。“Plot”指回归所在的概率图坐标，不是只凭肉眼画图。

直接来源为 Park, C. (2017), *Weibullness Test and Parameter Estimation of the Three-Parameter Weibull Model Using the Sample Correlation Coefficient*, International Journal of Industrial Engineering: Theory, Applications and Practice, 24(4):376–391，[出版链接](https://doi.org/10.23055/ijietap.2017.24.4.2848)。核对范围为原文第2节、第5节及表1；原文编号182-115。Li（1994）只作为线性化背景，Park（2018）作为位置估计存在性的理论补充。

## 2. 绘图位置、位置估计及回归

将完整失效时间排序为 $t_{(1)}\leq\cdots\leq t_{(n)}$。按 Park 第2节取：

$$
p_i=\begin{cases}
\dfrac{i-3/8}{n+1/4}, & n\leq10,\\
\dfrac{i-1/2}{n}, & n\geq11.
\end{cases}
\qquad Y_i=\ln[-\ln(1-p_i)].
$$

定义 $X_i(\gamma)=\ln(t_{(i)}-\gamma)$，按第5节式(2)求：

$$
\hat\gamma=\arg\max_{0\leq\gamma<t_{(1)}}
\mathrm{corr}(X(\gamma),Y).
$$

然后固定 $\hat\gamma$，用带截距普通最小二乘拟合 **$Y=a+bX$**，得到：

$$
\hat\beta=b=\frac{\sum_i(X_i-\bar X)(Y_i-\bar Y)}{\sum_i(X_i-\bar X)^2},
\qquad a=\bar Y-b\bar X,
\qquad \hat\eta=\exp(-a/b).
$$

回归方向与论文一致；交换两轴后再取斜率倒数通常会改变估计结果。

## 3. 数值求解和核验

原文允许直接最大化相关系数，或对其导数等价方程(3)定根。本实现采用前者：以 $s=\ln[(t_{(1)}-\gamma)/t_{(1)}]$ 为搜索变量，合并201点对数间隔网格和201点常规位置网格，精化网格识别的各局部峰后比较目标值，并保留 $\gamma=0$。有界精化在无量纲变量上使用 `xatol=1e-12`；接近 $t_{(1)}$ 的最大候选由 `nextafter(t_(1), 0)` 决定。归一化只用于数值计算，不改变相关系数、回归方向或估计定义。

不再使用旧版的 $t_{(1)}-10^{-5}$ 固定截断。基础类的 Bernard/exact 秩选项不参与本方法，避免不经声明改变论文绘图位置。

表1的24个寿命算例复算如下：

| 数量 | 当前公式复算 | Park 表1 Proposed+Plot |
|---|---:|---:|
| 位置 $\gamma$ | 9.197683 | 9.198 |
| 形状 $\beta$ | 1.363761 | 1.363 |
| 尺度 $\eta$ | 15.116027 | 15.116 |
| 相关系数 $R$ | 约0.9902 | 0.9902 |

形状值的末位差异尚未解释，不能声称所有表值逐位一致，也不通过修改公式或特设舍入去凑表值。测试另以原文式(3)独立定根，再用独立线性代数求解 OLS 核对结果，覆盖小样本分段及寿命单位换算。

代码与可重跑验证分别为 `python/methods/lre.py`、`python/tests/test_lre_park2017.py`。

## 4. 与其他方法及历史版本的关系

| 方法 | 位置确定 | 形状、尺度确定 |
|---|---|---|
| **当前 LRE：Park Proposed+Plot** | 原文分段分数下最大化相关系数 | $Y$ 对 $X$ 的OLS |
| Park Proposed+MLE2（本页未实现） | 同上 | 固定位置后求二参数MLE |
| 本项目LS（Soman–Misra分支） | 次序统计量期望分数下最大化F比 | $X$ 对分数的OLS，斜率取倒数 |
| Li（1994）§4、§5（本页未实现） | 位置近似构造或联立曲线求解 | 须按对应原文算法实现 |

**版本切换日期为2026-09-29。** 之前的 LRE 使用 Bernard 绘图位置 $(i-0.3)/(n+0.4)$，属于相关系数定位加 OLS 的项目变体。Bernard 本身不是错误公式，但不符合此次 Park 原版复现目标。已生成的工作簿、研究数据和结论保持原版本身份；本次没有重跑这些实验，后续比较必须记录实际代码版本。历史代码可由 Git 提交 `80d08ca8` 及此前版本恢复。

历史四方法核查与原算例见[Research09附录B](../../../Research/09-Weibull参数估计方法谱系与比较基线/附录B-方法实现与版本.md)，其中历史数值不应读作本版输出。

## 5. 适用边界与输出

- 完整、有限、正寿命样本；不含删失数据扩展。
- 位置域为原文的 $0\leq\gamma<t_{(1)}$。
- $n<3$ 返回 `insufficient_sample`；全等或相对极差不超过 $10^{-12}$ 的近退化样本显式失败，不返回虚构估计。
- 返回的 $R^2$ 是同一组 Park 分数上的概率图 OLS 决定系数，等于相关系数平方；表1报告的是 $R$。它不是参数误差，也不等于 Weibullness 检验的p值。
- 本页完成所选参数估计分支的实现和核验，不宣称复现整篇论文的全部检验与模拟。
