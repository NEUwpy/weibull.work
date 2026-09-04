# 三参数 Weibull 寿命点神经估计的任务导向损失与约束学习

> 论文工作稿 v2.1 · 2026-09-04 修订 · 目标对齐、参数补偿与约束修复

## 摘要

寿命分布的参数估计常被用于计算特定可靠度下的寿命点，但参数恢复精度与寿命点精度并不是同一个训练目标。本文以三参数 Weibull 分布的 $x_{0.95}$ 为目标，在相同输入、网络、数据划分和最大训练预算下，比较归一化参数损失 P、直接寿命点损失 Q，以及参数约束寿命点学习 QCP。三者均输出形状、尺度和位置参数；QCP 以寿命点误差为目标，以验证参数误差约束限制内部参数偏离。

在固定尺度、40 个参数组合、四种小样本量及 200 个配对模型单元的仿真实验中，Q 将目标寿命点的均方根相对误差（RMSRE）从 P 的 16.43% 降至 16.09%，相对改善 2.07%。与此同时，同一组参数预测在 $x_{0.90}$ 和 $x_{0.99}$ 上的 RMSRE 分别比 P 高 36.41% 和 63.11%。损失几何与参数误差分析共同表明，单一寿命点监督允许不同参数误差相互补偿：目标寿命点可以接近真值，而其他寿命点明显偏离。

QCP 将三个寿命点的 RMSRE 降至 13.34%、15.84% 和 20.65%，恢复到接近或略优于 P 的总体水平，并使参数误差与补偿程度接近 P。改善存在区域差异，QCP 在三个寿命点上分别有 74、76 和 77 个固定真值单元优于 P（共 160 个）。本文因此将目标对齐与参数约束视为两项互补任务：前者决定所需寿命点的精度目标，后者限制单点监督留下的参数补偿空间。该组合的优势体现为所研究设计域内总体平方误差下降，同时伴随区域和指标排序的差异。

**关键词**：三参数 Weibull；可靠度寿命点；目标对齐；参数补偿；约束学习；神经估计

## Abstract

Weibull parameter estimates are often used to calculate a life point at a specified reliability level, yet parameter recovery and life-point accuracy define different training objectives. We compare a normalized parameter loss (P), a direct life-point loss (Q), and parameter-constrained life-point learning (QCP) for estimating $x_{0.95}$. All three approaches output shape, scale, and location parameters and share the input representation, network, data splits, and maximum training budget. QCP minimizes life-point error while restricting parameter deviation through a validation-based parameter-error constraint.

Simulations cover 40 parameter combinations at a fixed scale, four small sample sizes, and 200 paired model units. Q reduces the root mean squared relative error (RMSRE) of the target life point from 16.43% for P to 16.09%, a relative improvement of 2.07%. However, the same parameter predictions increase RMSRE at $x_{0.90}$ and $x_{0.99}$ by 36.41% and 63.11%. The loss geometry and parameter-error diagnostics show how single-life-point supervision permits compensating parameter errors: an accurate target life point can coexist with inaccurate predictions at other reliability levels.

QCP reduces RMSRE at the three life points to 13.34%, 15.84%, and 20.65%, respectively, bringing aggregate accuracy close to or slightly beyond that of P while restoring parameter error and compensation to levels close to P. These gains are heterogeneous: QCP outperforms P in 74, 76, and 77 of the 160 fixed-truth cells at the respective life points. The results identify complementary roles for task alignment and parameter constraints. The former defines accuracy at the required life point; the latter restricts compensation left unconstrained by scalar supervision. Their combination reduces aggregate squared error within the studied design domain, with region- and metric-specific differences in ranking.

## 1 引言

可靠性分析既需要描述寿命分布，也常需要回答一个更具体的问题：在给定可靠度下，寿命边界是多少？三参数 Weibull 模型以形状 $\beta$、尺度 $\eta$ 和位置 $\gamma$ 描述寿命，其小样本估计是长期研究的问题 [1,2,3,4]。最小差异方法 [5,6]、神经网络估计 [7,12] 及经典拟合与一致估计方法 [13,14] 提供了不同的参数恢复途径。当估计结果最终用于某个寿命点时，参数误差只是影响最终精度的中间量。

设 $R$ 为生存概率，可靠度寿命点满足 $R(x_R)=R$。本文关注的 $x_{0.95}$ 是可靠度为 95% 时的寿命边界，即失效分布的 5% 分位点。三个参数对该寿命点的影响不同，误差之间还可能相互抵消。因此，即使先消除量纲差异，再等系数相加三个参数平方误差，也不等价于最小化寿命点误差。分位数回归、任务聚焦学习与目标泛函研究为按最终使用量定义损失提供了一般思想 [8,9,10,11,15]；Weibull 参数与插件分位点的估计精度也可能呈现不同排序 [16]。本文据此将三参数输出通过寿命点公式连接到相对平方损失。

这种目标对齐同时带来一个结构性问题。三个参数决定一条分布曲线，而单个寿命点只提供一个标量监督信号。多组不同参数可以产生相同的 $x_{0.95}$，却给出不同的 $x_{0.90}$ 和 $x_{0.99}$。因此，判断直接寿命点训练是否有效，既要看目标精度，也要看其保留的参数输出如何影响其他寿命点。后一项不是要求所有参数都达到最优精度，而是检验同一个分布表示在目标之外是否仍保持合理的一致性。

本文围绕三个问题展开：在共同三参数网络下，寿命点损失 Q 相对参数损失 P 能改善多少目标精度；单点监督是否伴随参数补偿及跨寿命点代价；以参数误差定义可行域的 QCP 能否在保留目标收益的同时修复这种代价。研究通过配对仿真、损失几何、固定真值区域分析和跨寿命点评价连接这三个问题。P 提供参数恢复参照，Q 揭示直接目标监督的收益与不足，QCP 则检验显式参数约束的修复作用。

## 2 方法

### 2.1 寿命模型、数据与评价域

三参数 Weibull 模型及其寿命点为

$$
R(x)=\exp\left[-\left(\frac{x-\gamma}{\eta}\right)^\beta\right],
\qquad
x_R=\gamma+\eta[-\ln R]^{1/\beta},\qquad x>\gamma.
$$

仿真采用

$$
\beta\in\{1.5,2,2.5,3,3.5,4,4.5,5\},\quad
\eta=1000,\quad
\gamma/\eta\in\{0.10,0.25,0.50,0.75,1.00\},
$$

以及样本量 $n\in\{7,10,15,20\}$。每个参数—样本量组合生成 300 组独立、未删失寿命样本，共 160 个固定真值单元、48,000 组样本。每组输入为升序排列的原始寿命观测，不作逐样本均值归一化；输入位置的标准化仅使用当前训练折拟合的均值与标准差。

按重复抽样编号模 5 分折，每轮以一类为测试、下一类为验证、其余三类为训练。每个参数组合相应有 180、60、60 组训练、验证、测试样本。五轮划分中的样本不跨越当前训练与测试集合，但各轮训练集存在重叠。各集合覆盖同一组参数点，因而评价的是设计域内新样本的估计表现。

固定 $\eta$ 不意味着所有寿命点数值相同：该网格的真实 $x_{0.95}$ 为 238.05–1552.09。本文采用相对误差，使各寿命水平按比例误差比较。结论对应固定物理尺度下的参数网格与小样本估计任务。

### 2.2 共同网络与两种基本损失

每个样本量分别训练 MLP，结构为 $n\rightarrow256\rightarrow128\rightarrow64\rightarrow3$，隐藏层使用 ReLU，计算精度为 float64。三条路线共用参数解码，保证

$$
\hat\beta>0,\qquad\hat\eta>0,\qquad0<\hat\gamma<\min(X).
$$

优化器为 Adam，学习率 $10^{-3}$、weight decay $10^{-4}$、batch size 256。当前比较统一最多 600 epochs、early-stopping patience 60。每个配对模型单元内，三路线共享样本划分、标准化、初始化、首 epoch batch 顺序和网络结构。

令单组样本的归一化参数误差为

$$
u=\left(
\frac{\hat\beta-\beta}{\beta},
\frac{\hat\eta-\eta}{\eta},
\frac{\hat\gamma-\gamma}{\eta}
\right).
$$

参数路线 P 最小化

$$
L_P=\operatorname{mean}\|u\|^2.
$$

三个平方项使用相同系数；位置误差以 $\eta$ 归一化，避免其度量随 $\gamma$ 接近零而发散。该损失是明确的参数恢复参照，而非对寿命点敏感度的加权。

路线 Q 使用相同三参数输出，由 Weibull 公式计算目标寿命点，最小化

$$
L_Q=\operatorname{mean}\left[
\left(\frac{\hat x_{0.95}-x_{0.95}}{x_{0.95}}\right)^2
\right].
$$

P 与 Q 分别以最低验证 $L_P$ 和 $L_Q$ 选择 checkpoint。因此，两者的受控差异是训练目标及与之对应的验证选择，而不是输出表示或网络容量。

### 2.3 参数约束寿命点学习 QCP

QCP 保留目标寿命点误差作为优化目标，以参数损失限制可接受解：

$$
\min_\theta L_Q(\theta)
\quad\text{s.t.}\quad
L_P(\theta)\le\tau_j,\qquad
\tau_j=cL_{P,\mathrm{ref},j}.
$$

$j=(n,\mathrm{fold},\mathrm{seed})$ 表示模型单元。$L_{P,\mathrm{ref},j}$ 来自匹配的早期 P 参考模型的最佳验证参数损失，该参考训练采用最多 300 epochs、patience 20。QCP 使用的阈值随后保持不变；它不由当前 600-epoch P 的测试结果确定。

令 $g_b=L_{P,b}-\tau_j$、$g_{\mathrm{tr}}=L_{P,\mathrm{tr}}-\tau_j$。batch 训练采用增广拉格朗日损失，epoch 结束更新非负乘子：

$$
L_{\mathrm{AL},b}
=L_{Q,b}+\frac{\left[\max\{0,\mu+\rho g_b\}\right]^2-\mu^2}{2\rho},
\qquad
\mu\leftarrow\max\{0,\mu+\rho g_{\mathrm{tr}}\}.
$$

当约束松弛且乘子为零时，参数项不参与更新；约束受到违反时，其作用由乘子与违反程度调节。checkpoint 选择先检查验证集平均 $L_P\le\tau_j$，再从可行 epoch 中选出验证 $L_Q$ 最小者。这是模型单元层面的经验约束，而非每条预测均满足的误差上界。

$c$ 与 $\rho$ 在 8 个验证单元上选择，共比较 48 个 fits；另以 8 个 fits 检查资源扩展，最终取 $c=1.5,\rho=0.1$ 和 600/60 预算。这两个选择阶段均未访问测试指标。随后形成 200 个 QCP 模型。为比较相同最大训练机会，在原 P/Q 测试结果打开后，将 P、Q 扩展到同样的 600/60 预算；本文主表采用这一共同预算分析。完整实验先后顺序见补充材料 S2。

### 2.4 单点监督与参数补偿

P 与 Q 的差异可以在共同的 $u$ 坐标下表示。记单组样本的相对寿命点误差为 $e(u)$，则

$$
\ell_P=\|u\|^2,\qquad
\nabla_u\ell_P=2u,\qquad H_P=2I_3,
$$

$$
\ell_Q=e(u)^2,\qquad
\nabla_u\ell_Q=2e(u)\nabla_u e(u).
$$

令 $a=-\ln R$、$t=a^{1/\beta}$，寿命点对三个参数的导数为

$$
\frac{\partial x_R}{\partial\gamma}=1,\qquad
\frac{\partial x_R}{\partial\eta}=t,\qquad
\frac{\partial x_R}{\partial\beta}=-\frac{\eta t\ln a}{\beta^2}.
$$

在真值处，归一化敏感度向量及 Q 的 Hessian 为

$$
s_0=\left(
\frac{\beta}{x_R}\frac{\partial x_R}{\partial\beta},
\frac{\eta}{x_R}\frac{\partial x_R}{\partial\eta},
\frac{\eta}{x_R}\frac{\partial x_R}{\partial\gamma}
\right),
\qquad H_Q(0)=2s_0s_0^\mathsf T.
$$

P 在三个方向上惩罚参数误差；Q 的局部 Hessian 则为秩一，在与 $s_0$ 正交的两个方向上没有二阶惩罚。更直接地说，$\hat x_{0.95}=x_{0.95}$ 在合法输出空间中定义等寿命点曲面。沿该曲面改变参数，可以保持目标点不变，同时改变其他寿命点。这是单个标量训练目标留下的自由度，不是三参数 Weibull 分布本身不可识别。

局部近似之外，微积分基本定理给出有限误差的精确表达：

$$
\bar s(u)=\int_0^1\nabla_u e(tu)\,dt,\qquad
e(u)=\bar s(u)^\mathsf Tu,\qquad
\ell_Q=u^\mathsf T[\bar s(u)\bar s(u)^\mathsf T]u.
$$

这一写法中的敏感度依赖当前预测路径，求导时也应保留这种依赖。因此，Q 不只是某个预先固定的参数权重矩阵。真值点静态代理的推导与探索性消融见补充材料 S5。

为量化终态预测中的补偿，本文对 $e$ 作精确的三项参数贡献分解，并定义

$$
C=\operatorname{mean}\left[
1-\frac{|c_\beta+c_\eta+c_\gamma|}
{|c_\beta|+|c_\eta|+|c_\gamma|}
\right].
$$

分母为零时该行取零；$C$ 越接近 1，表示贡献绝对值较大、但相加后的目标误差较小。具体对称分解见补充材料 S5.1。该指标与平均 $L_P$ 配合使用，分别反映误差抵消程度和参数偏离幅度。

### 2.5 配对评价与统计汇总

训练使用 10 个随机种子、4 个样本量和 5 折，形成每条路线 200 个模型单元，共 600 个 fits。每条路线有 480,000 条测试预测，来自 48,000 组寿命样本在 10 个训练种子下的重复预测；这些行不被当作 480,000 组独立样本。完整种子、配对键和数据来源见补充材料 S1–S3。

主指标为均方根相对误差：

$$
\operatorname{RMSRE}_m(R)
=\sqrt{\operatorname{mean}\left[
\left(\frac{\hat x_{R,m}-x_R}{x_R}\right)^2
\right]}.
$$

先对 200 个模型单元的 MSE 等权平均，再开方。相对改善定义为

$$
I_{a\rightarrow b}(R)
=\frac{\operatorname{RMSRE}_a(R)-\operatorname{RMSRE}_b(R)}
{\operatorname{RMSRE}_a(R)},
$$

正值表示路线 $b$ 更好。区间按 $n$ 分层重采样 fold，同时全局重采样 seed，始终保持路线配对，共 200,000 次。考虑到折间训练数据重叠及训练种子数量有限，所报 95% CI 为设计级经验 bootstrap 近似区间。

$x_{0.95}$ 为训练目标；另外从同一组参数预测派生 $x_{0.90}$ 和 $x_{0.99}$，评价跨寿命点一致性。后两点的分析在读取对应派生结果前固定，但属于既有模型上的事后机制分析。区域效应以 160 个固定真值单元 $(n,\beta,\gamma/\eta)$ 汇总，每单元每路线有 3,000 条预测。

为说明 RMSRE 之外的误差形态，同时报告目标点的平均绝对相对误差、绝对相对误差中位数、95% 分位点、±10% 内比例和有方向偏差。固定真值单元内的偏差—方差分解见补充材料 S4.3。指标分别回答整体平方误差、典型误差、尾部与方向问题，不合并为综合分数。

## 3 结果

### 3.1 单点目标对齐的收益与代价

在共同预算下，Q 将目标 $x_{0.95}$ 的 RMSRE 从 16.432% 降至 16.092%，相对改善 2.069%（95% CI：1.280%–2.811%）。然而，相同参数预测在另外两个寿命点上的表现明显下降：$x_{0.90}$ 和 $x_{0.99}$ 的 RMSRE 相对 P 分别增加 36.411% 和 63.114%（表1）。直接训练目标的收益温和，未受直接监督的寿命点代价更大。

**表1　三条路线在三个寿命点的总体 RMSRE**

| 寿命点 | P | Q | QCP | QCP 相对 Q 改善 | QCP 相对 P 改善（95% CI） |
|---|---:|---:|---:|---:|---:|
| $x_{0.90}$ | 13.657% | 18.630% | 13.336% | 28.417% | 2.353%（1.809%–2.904%） |
| $x_{0.95}$ | 16.432% | 16.092% | 15.841% | 1.562% | 3.599%（3.027%–4.180%） |
| $x_{0.99}$ | 21.960% | 35.820% | 20.647% | 42.360% | 5.981%（5.277%–6.673%） |

*每条路线包含同样的 200 个配对模型单元。QCP 相对 Q 及 Q 相对 P 的完整区间见补充材料 S4.1。RMSRE 的百分数表示误差水平，相对改善的百分数表示两路线误差水平之比。*

目标点精度并未保证参数恢复。Q 的平均 $L_P$ 达到 71.714，而 P 为 0.05385；其平均补偿指数从 P 的 0.33226 增至 0.91455。较大的参数偏离与较强的抵消同时出现，说明 Q 可以通过内部补偿维持目标点精度。图1以等寿命点切片说明这种可能性，并给出实际预测的参数误差与寿命点误差。

![图1：等寿命点几何与三路线经验结果](figures/main/fig1_qcp_geometry_and_evidence.png)

*图1　A–B 固定 $\gamma=100$、真值 $(\beta,\eta)=(1.5,1000)$，展示形状与尺度相对误差的二维切片。虚线为相同 $x_{0.95}$ 的参数轨迹，B 中阴影与标记示意参数约束如何截取该轨迹，不代表每条实际预测均受同一半径约束。C 为 200 个模型单元的经验汇总；连接标注表示路线之间的比较，不是训练轨迹或阈值扫描得到的 Pareto 前沿。*

### 3.2 参数约束保留目标收益并修复跨寿命点表现

QCP 的 200 个选定 checkpoint 均满足验证集平均参数约束。其测试平均 $L_P$ 为 0.05522，补偿指数为 0.34532，均接近 P。按 $(C_Q-C_{\mathrm{QCP}})/(C_Q-C_P)$ 计算，QCP 消除了 Q 相对 P 的 97.8% 超额补偿；这是补偿指标的恢复比例，而非精度改善比例。

参数恢复伴随跨寿命点误差下降。QCP 在目标点较 Q 再改善 1.562%（95% CI：1.241%–1.898%），而在两个非目标点较 Q 分别改善 28.417% 和 42.360%。与 P 相比，三个寿命点的总体 RMSRE 均小幅降低（表1）。QCP 的主要作用因此表现为：保留单点目标对齐，同时把其余寿命点恢复到接近 P 的水平，而不是在目标点上获得数量级的提升。

![图2：跨寿命点误差及参数恢复](figures/main/fig2_cross_quantile_recovery.png)

*图2　A 从同一组三参数预测派生 $R=0.50$–0.99 的 RMSRE 曲线，作为描述性背景；B 对三个预设寿命点给出 QCP 相对 Q、相对 P 的配对效应及经验 bootstrap 95% CI；C 为三项归一化参数误差的 RMSE，纵轴为对数尺度。正式数值比较集中于表1的三个寿命点。*

### 3.3 总体收益与区域差异

QCP 对 Q 的修复在多数固定真值单元内成立：三个寿命点分别有 155、119、146 个单元改善。相对 P，则只有 74、76、77 个单元改善（表2）。这与总体 RMSRE 更低并不矛盾：总体风险衡量各区域平方误差的大小，有利单元数只记录改善方向。

**表2　固定真值单元的改善方向与效应中位数**

| 寿命点 | Q 优于 P | QCP 优于 Q | QCP 优于 P | QCP 相对 P 的单元效应中位数 |
|---|---:|---:|---:|---:|
| $x_{0.90}$ | 8/160 | 155/160 | 74/160 | −0.673% |
| $x_{0.95}$ | 42/160 | 119/160 | 76/160 | −0.257% |
| $x_{0.99}$ | 13/160 | 146/160 | 77/160 | −0.080% |

*各单元具有相同数量的预测。效应中位数由单元相对改善计算，负值表示该中位数处 P 略好；它与先汇总 MSE 再计算的总体相对改善是不同统计量。*

对 $x_{0.95}$，图3同时展示所有单元及一个按“最接近总体 QCP-vs-Q 效应”规则选出的代表性单元。该单元为 $n=7,\beta=4.5,\gamma/\eta=0.75$，QCP 相对 Q 的 RMSRE 改善 1.60%，接近总体的 1.56%。两条路线的误差分布仍高度重叠，体现的是小幅分布调整。

![图3：目标寿命点的区域异质性与代表性分布](figures/main/fig3_resolution_distribution.png)

*图3　A 每点对应一个固定真值单元，正值表示 QCP 优于 Q；菱形为按最接近总体效应规则选出的单元。B 展示该单元每路线 3,000 条测试预测的有符号相对误差，小提琴为分布形状，箱线为中位数与四分位区间。C 分项展示精度、波动、方向偏差与参数补偿的变化。代表性单元用于展示效应量级，不替代全域比较。*

样本量增加则带来三条路线共同且更明显的精度改善。$n$ 从 7 增至 20 时，P 的目标 RMSRE 从 20.74% 降至 12.00%，QCP 从 19.92% 降至 11.69%。方法间差异小于这一采样效应。逐样本量结果及条件于 P 经验误差曲线的等效样本量换算见补充材料 S4.2。

### 3.4 误差形态与训练成本

相对 Q，QCP 在目标点的 RMSRE、平均绝对误差、中位绝对误差及 95% 分位误差均降低。但相对 P，较低 RMSRE 不伴随每项典型误差指标的改善（表3）：P 的平均绝对误差与中位绝对误差略低，±10% 内的预测比例也更高。三条路线的排序取决于所评价的误差特征。

**表3　共同预算下的目标寿命点误差与资源**

| 指标 | P | Q | QCP |
|---|---:|---:|---:|
| RMSRE | 16.432% | 16.092% | 15.841% |
| 平均绝对相对误差 | 10.917% | 11.185% | 10.938% |
| 绝对相对误差中位数 | 7.691% | 8.136% | 7.858% |
| 绝对相对误差 95% 分位点 | 30.429% | 30.803% | 30.314% |
| 误差在 ±10% 内的比例 | 60.746% | 58.402% | 59.698% |
| 有方向相对偏差 | −1.513% | −2.713% | −2.482% |
| 单 fit 中位训练耗时 / s | 41.4 | 29.6 | 87.2 |

*误差指标由当前 600/60 模型的全部测试预测计算。训练耗时为记录环境中的各路线训练阶段耗时；QCP 的 87.2 s 不包含早期 P 参考模型训练及约束筛选成本。*

固定真值下的偏差—方差分解进一步显示，P、Q、QCP 的单元内标准差分量依次为 14.824%、14.493%、14.210%，区域偏差的 RMS 分量则均约为 7%。总体平方误差的下降主要伴随重复估计波动减小，而不是系统偏差消失（补充材料 S4.3）。

三路线各 200 个 fits 均进入分析，预测无非有限值或支持域违规。QCP 有 3 个模型运行到 600-epoch 上限；其余模型及全部 P/Q 模型在上限前结束。统一最大预算提供了相同的训练机会，但 QCP 的约束求解与前置参考训练增加了计算成本。

## 4 讨论

### 4.1 目标对齐改变了参数误差的评价方式

本文的 P 与 Q 都从样本输出三个 Weibull 参数。Q 的特点不是跳过分布，而是通过分布公式直接评价所需寿命点。相同的参数偏差在不同真值与预测位置上会产生不同的目标误差，Q 将这种敏感度和参数间交互纳入训练。因此，P 与 Q 的结果差异回答的是如何训练同一估计器，而非参数模型与无参数分位数模型谁更好。

目标对齐也不保证有限数据、有限网络和指定优化过程下的测试误差必然更低。当前 Q 在总体 RMSRE 上取得温和收益，在许多固定真值区域却不如 P。几何推导解释了两种损失如何评价输出误差；实际网络更新还受到共享权重、解码器和优化器影响，不能仅凭输出层 Hessian 推出最终泛化排序。

### 4.2 参数补偿解释了为何目标点准确仍不够

单个寿命点由三个参数共同决定，沿等寿命点曲面的误差补偿能够保留目标值。对于只需要 $x_{0.95}$ 的任务，这种内部自由度本身未必构成问题；但当输出仍被解释为一个寿命分布，并被用于其他可靠度水平时，就需要检查其后果。本文观察到的参数偏离、补偿增强和非目标寿命点退化形成了相互一致的证据。

QCP 将参数恢复要求写为允许偏离的边界，而不要求以参数精度替代寿命点目标。其结果最鲜明的部分是大幅修复 Q 的非目标点误差，同时保留目标点的小幅收益。参数损失、补偿指标与跨寿命点结果共同支持这一解释；这些终态证据尚不区分约束改变优化轨迹的各项独立因果贡献。

这一比较也说明，QCP 的价值应从“目标与分布表示的协调”来理解。相对 Q，它解决了明显的补偿与跨点失真；相对 P，它取得的是有限设计域内的总体平方误差优势，而非全面替代参数训练。

### 4.3 使用条件与证据范围

当前网络在仿真标签已知的条件下训练，输入保留量纲，评价集中于固定 $\eta$、给定参数网格与未删失小样本。训练好的 QCP 预测器只需输入寿命样本，不需要待估样本的真实参数；真参数用于监督训练和约束选择。将其用于实际数据，关键是确认训练分布、单位尺度与实际寿命机制是否匹配。若进一步要求在无真参数标签的实际数据上重新训练，则需另行设计训练依据。

统计结果反映当前设计单元的平均风险。区域效应、多指标排序和训练成本说明，实际任务仍需明确更重视总体平方误差、典型偏差，还是某一侧的风险。本文的对称相对平方损失给出寿命点估计，不提供具有指定覆盖率的可靠性置信下限。

共同预算分析是在已有测试结果打开后的扩展，区间亦受折间重叠和有限种子数量影响。它与配对设计、参数诊断及跨寿命点结果共同支持当前问题的回答；独立参数域与实际数据属于后续外部验证，而不是本稿已覆盖的结论。

## 5 结论

在保持三参数 Weibull 输出与共同网络设置的条件下，直接以目标寿命点训练可以降低总体目标 RMSRE，但单点监督允许较大的参数误差通过补偿隐藏在准确的目标值之后。本文中，Q 的目标点收益伴随两个非目标点的明显退化。

QCP 以寿命点精度为目标、以参数误差定义可行域，使参数补偿回落，并将三个评价寿命点恢复到接近或略优于 P 的总体水平。研究的主要结论是：当神经估计器既服务于一个具体寿命点、又保留分布参数输出时，目标对齐与参数一致性约束承担不同且互补的作用。其效益应结合总体误差、区域差异和计算成本评价。

## 数据与代码可用性

仿真协议、训练与派生分析代码、模型单元结果、配对预测及校验清单随本研究项目保存。当前正文数值来自共同预算三路线分析及其跨寿命点、区域分布和偏差—方差派生结果；文件与证据对应关系见[补充材料 S7](Study02论文补充材料-v2.1.md)及[引用与完整性审计](引用与完整性审计.md)。历史预算分析单独列于补充材料，不与当前主表混用。本文工作稿尚未投稿，公开仓储地址将在发布时补充。

## 参考文献

[1] Weibull, W. (1951). A Statistical Distribution Function of Wide Applicability. *Journal of Applied Mechanics*, 18(3), 293–297. https://doi.org/10.1115/1.4010337

[2] Rinne, H. (2008). *The Weibull Distribution: A Handbook*. Chapman & Hall/CRC Press. https://doi.org/10.1201/9781420087444

[3] Murthy, D.N.P., Xie, M., & Jiang, R. (2004). *Weibull Models*. Wiley-Interscience.

[4] Meeker, W.Q., & Escobar, L.A. (1998). *Statistical Methods for Reliability Data*. Wiley.

[5] Xie, L., Wu, N., & Yang, X. (2023). A Minimum Discrepancy Method for Weibull Distribution Parameter Estimation. *International Journal of Structural Stability and Dynamics*, 23(8), 2350085. https://doi.org/10.1142/S0219455423500852

[6] 谢里阳, 朱文慧, 吴宁祥, 杨小玉. (2025). 基于统计最小差异原理的 Weibull 分布参数估计方法. *东北大学学报（自然科学版）*, 46(7), 108–112. https://doi.org/10.12068/j.issn.1005-3026.2025.20240194

[7] Yang, X., Xie, L., Chen, J., Zhao, B., & Wang, K. (2025). Estimation of Weibull distribution using the back-propagation neural network for fatigue failure data. *Probabilistic Engineering Mechanics*, 82, 103828. https://doi.org/10.1016/j.probengmech.2025.103828

[8] Koenker, R., & Bassett, G. (1978). Regression Quantiles. *Econometrica*, 46(1), 33–50. https://doi.org/10.2307/1913643

[9] Elmachtoub, A.N., & Grigas, P. (2022). Smart“Predict, then Optimize”. *Management Science*, 68(1), 9–26. https://doi.org/10.1287/mnsc.2020.3922

[10] Wilder, B., Dilkina, B., & Tambe, M. (2019). Melding the Data-Decisions Pipeline: Decision-Focused Learning for Combinatorial Optimization. *AAAI*, 33(01), 1658–1665. https://doi.org/10.1609/aaai.v33i01.33011658

[11] Donti, P.L., Amos, B., & Kolter, J.Z. (2017). Task-based End-to-end Model Learning in Stochastic Optimization. *NeurIPS*, 30, 5484–5494. arXiv:1703.04529

[12] Abbasi, B., Rabelo, L., & Hosseinkouchack, M. (2008). Estimating parameters of the three-parameter Weibull distribution using a neural network. *European Journal of Industrial Engineering*, 2(4), 428–445. https://doi.org/10.1504/EJIE.2008.018438

[13] Cousineau, D. (2009). Fitting the three-parameter Weibull distribution: Review and evaluation of existing and new methods. *IEEE Transactions on Dielectrics and Electrical Insulation*, 16(1), 281–288. https://doi.org/10.1109/TDEI.2009.4784578

[14] Nagatsuka, H., Kamakura, T., & Balakrishnan, N. (2013). A consistent method of estimation for the three-parameter Weibull distribution. *Computational Statistics & Data Analysis*, 58, 210–226. https://doi.org/10.1016/j.csda.2012.09.005

[15] Gneiting, T. (2011). Making and Evaluating Point Forecasts. *Journal of the American Statistical Association*, 106(494), 746–762. https://doi.org/10.1198/jasa.2011.r10138

[16] Jokiel-Rokita, A., & Piątek, S. (2024). Estimation of parameters and quantiles of the Weibull distribution. *Statistical Papers*, 65, 1–18. https://doi.org/10.1007/s00362-022-01379-9
