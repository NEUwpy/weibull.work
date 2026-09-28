对。你要是问的是 **Park 之前，传统三参数 Weibull 的 LS 到底怎么把那个未知的位置参数 \(\gamma\) 搞出来**，核心答案其实很简单：

> **它也得“试 \(\gamma\)”；不是一次最小二乘直接把三个参数同时算出来。**

以你前面提到的 **Soman & Misra 1992 的 LS 方法**为例，这篇文章讲得非常明确：它把二参数 Weibull 的最小二乘法扩展到三参数 Weibull，然后对位置参数做迭代搜索。[ResearchGate](https://www.researchgate.net/publication/238802403_A_least_square_estimation_of_three_parameters_of_a_Weibull_distribution)

### 先理解为什么必须“试 \(\gamma\)”

三参数 Weibull 变换以后是：

\[ \ln(t-\gamma) = \ln \eta + \frac{1}{\beta} \ln[-\ln(1-F(t))]. \]

如果 \(\gamma\) 已经知道，这就是：

\[ Y=a+bX \]

其中

\[ Y_i=\ln(t_i-\gamma), \]\[ X_i=\ln[-\ln(1-F_i)]. \]

然后普通最小二乘一做：

\[ \text{截距}\rightarrow \eta, \qquad \text{斜率}\rightarrow \beta. \]

**难点只有一个：\(\gamma\) 不知道。**

所以老办法就是：

```
先猜一个 γ
    ↓
把所有寿命减掉 γ
    ↓
变成二参数 Weibull
    ↓
做一次最小二乘直线
    ↓
看看这条直线拟合得好不好
    ↓
换一个 γ
    ↓
再做一遍
    ↓
……
    ↓
哪一个 γ 让直线拟合最好，就选哪个
```

这就是传统三参数 LS 最基本的思想。

---

### Soman & Misra 1992 具体是怎么做的？

它甚至给出了非常直接的算法。

假设最小的样本是

\[ t_{(1)}. \]

它第一步先取一个非常接近最小样本、但比它小的位置参数，例如：

\[ \gamma=t_{(1)}-0.01. \]

然后计算

\[ t_i-\gamma. \]

这样暂时把 \(\gamma\) 当成已知。

接下来，对这些

\[ t_i-\gamma \]

使用 White 的二参数 Weibull 最小二乘法，估计：

\[ \hat\beta,\quad \hat\eta. \]

这就是一次完整的 LS 拟合。Soman & Misra 原文就是“取位置参数 → 从每个观测值中减掉它 → 用 White 的 least square estimators 求另外两个参数”。[ResearchGate](https://www.researchgate.net/publication/238802403_A_least_square_estimation_of_three_parameters_of_a_Weibull_distribution)

然后它问：

> **这个 \(\gamma\) 好不好呢？**

它计算一个 **Fisher 的 F 比值**，来衡量这些变换后的点到底有多接近一条直线。然后继续降低 \(\gamma\)，重复整个过程。最后：

\[ \boxed{ \text{选择使 }F\text{ 最大的那组 } (\gamma,\beta,\eta) } \]

Soman & Misra 的步骤 1–4 就是这么写的：先从 \(t_{(1)}-0.01\) 开始，对每个候选位置参数做 LS，再计算 F-ratio，反复改变位置参数，最后选择 F 最大的参数组合。[ResearchGate](https://www.researchgate.net/publication/238802403_A_least_square_estimation_of_three_parameters_of_a_Weibull_distribution)

---

### 所以你可以把它想象成这样

假设你依次尝试：

\[ \gamma_1,\gamma_2,\gamma_3,\gamma_4,\cdots \]

每一个 \(\gamma\) 都会产生一张不同的 Weibull 概率图：

```
γ1                γ2                 γ3

●                    ●                  ●
  ●                ●                  ●
    ●               ●                ●
       ●          ●                 ●
          ●      ●                 ●
比较弯             还可以              最直
```

对于每一个：

\[ \gamma_j \]

都重新做：

\[ \ln(t_i-\gamma_j)=a_j+b_jX_i. \]

于是每一个候选 \(\gamma_j\) 都对应：

\[ \hat\beta_j,\quad \hat\eta_j, \]

以及一个“这条直线到底拟合得怎么样”的指标。

传统 LS 的核心就是：

\[ \boxed{ \gamma\text{ 外层搜索} + \text{每个 }\gamma\text{ 下做 LS} } \]

---

## 那 Park 到底改了什么？

这就非常容易看懂了。

**Park 并没有推翻前面的“找一个 \(\gamma\)，让 Weibull 图尽量直”的思想。**

Park 仍然是：

\[ \gamma \rightarrow \ln(t_i-\gamma) \rightarrow \text{看概率图有多直}. \]

但是 Park 说：

> 我不用以前那种不断做 LS、再用 F-ratio 判断直线拟合效果的办法来确定 \(\gamma\) 了。

它直接定义：

\[ R(\gamma) = \operatorname{Cor} \left[ \ln(t_i-\gamma), \ln\{-\ln(1-p_i)\} \right]. \]

然后直接找：

\[ \boxed{ \hat\gamma = \arg\max_\gamma R(\gamma) } \]

因为相关系数越接近 1，这些点越接近一条直线。Park 原文明确把三参数问题写成最大化 Weibull 图的 sample correlation，并且还进一步通过求 \(R(\mu)\) 的导数、解 \(g(\mu)=0\) 来寻找位置参数。 粘贴的文本 (1)

找到 \(\hat\gamma\) 后，它才再对

\[ t_i-\hat\gamma \]

做普通二参数 Weibull 回归，求形状和尺度参数。 粘贴的文本 (1)

---

所以你现在可以非常清楚地把二者区别记成一句话：

> **老 LS：试一个 \(\gamma\) → 做一次最小二乘 → 用拟合优度判断这个 \(\gamma\) 好不好 → 继续试。**
> 
> **Park：试一个 \(\gamma\) → 直接算概率图相关系数 \(R(\gamma)\) → 哪个相关系数最大就选哪个。**

也就是说，**两者寻找 \(\gamma\) 的大思想其实非常像——都是“找一个位置参数，使 Weibull 概率图最直”**；主要区别是“**拿什么尺子衡量最直**”。

Soman 1992 用的是 **LS + F-ratio**；Park 用的是 **概率图相关系数 \(R\)**。而且早期文献里三参数 LS 并没有一个唯一统一的实现，后来不同方法和软件对第三个位置参数的处理也确实不同。[digitalcommons.otterbein.edu](https://digitalcommons.otterbein.edu/math_fac/25/?utm_source=chatgpt.com)

这其实也解释了为什么你之前会觉得 **LS 和 Park 那个 LRE 怎么这么像**：**因为它们确实不是两条截然不同的路线，而是在同一个 Weibull 概率图/线性化框架里，用不同准则解决最难的 \(\gamma\) 估计问题。**