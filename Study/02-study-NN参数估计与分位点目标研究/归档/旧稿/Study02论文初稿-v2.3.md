# 三参数 Weibull 寿命点神经估计中的任务诱导耦合与参数约束

> 论文工作稿 v2.3 · 2026-09-04 · v2.1 事实底稿与 v2.2 论证逐节合并版

## 摘要

当三参数 Weibull 神经估计的最终用途是计算特定可靠度下的寿命点时，归一化参数误差的等权相加并不等价于最小化该寿命点误差。本文以 $x_{0.95}$ 为目标，在相同输入、三参数网络、数据划分和最大训练预算下，比较参数损失 P、寿命点损失 Q 和参数约束寿命点学习 QCP。Q 通过寿命点公式耦合三个参数的误差；QCP 保留这一任务目标，并以参数误差可行域限制单点监督留下的内部偏离。

在固定尺度、40 个参数组合、四种小样本量和 200 个配对模型单元的仿真实验中，Q 将目标寿命点的均方根相对误差（RMSRE）从 P 的 16.43% 降至 16.09%，相对改善 2.07%（95% CI：1.28%–2.81%）；同一组参数预测在 $x_{0.90}$ 和 $x_{0.99}$ 上的 RMSRE 却分别比 P 高 36.41% 和 63.11%。损失几何与终态误差共同揭示了单点监督的补偿机制：目标寿命点接近真值，并不要求组成它的三个参数同时接近真值。

QCP 将三个寿命点的 RMSRE 降至 13.34%、15.84% 和 20.65%，并消除了 Q 相对 P 的 97.8% 超额参数补偿。在目标点，QCP 的 RMSRE、平均及中位绝对相对误差、95% 分位误差和 ±10% 内比例均优于 Q，有方向偏差的绝对值也较小。相对 P，QCP 的三个总体 RMSRE 均降低，但有利固定真值单元仅为 74、76 和 77 个（共 160 个）；P 仍在典型绝对误差与训练成本上占优。

本文形成了“参数恢复参照—任务耦合与补偿—参数约束修复”的论证链。QCP 是该链条提出的约束估计方案：在所研究设计域内，它保留目标点的平方误差收益，并修复 Q 在另外两个评价寿命点上的明显退化；其收益不等于对 P 的全指标或逐区域支配。

**关键词**：三参数 Weibull；可靠度寿命点；任务诱导耦合；参数补偿；约束学习；神经估计

## Abstract

When a three-parameter Weibull neural estimator is used to calculate a life point at a specified reliability level, equal weighting of normalized parameter errors is not equivalent to minimizing error at that life point. We compare a parameter loss (P), a life-point loss (Q), and parameter-constrained life-point learning (QCP) for estimating $x_{0.95}$ under matched inputs, three-parameter networks, data splits, and maximum training budgets. Q couples parameter errors through the life-point formula. QCP retains this task objective while restricting parameter deviations left uncontrolled by single-point supervision.

Simulations cover 40 parameter combinations at a fixed scale, four small sample sizes, and 200 paired model units. Q reduces the target root mean squared relative error (RMSRE) from 16.43% for P to 16.09%, a relative improvement of 2.07% (95% CI: 1.28%–2.81%). However, the same parameter predictions increase RMSRE at $x_{0.90}$ and $x_{0.99}$ by 36.41% and 63.11%. The loss geometry and terminal-error diagnostics reveal compensating parameter errors: an accurate target life point does not require all three constituent parameters to be accurate.

QCP reduces RMSRE at the three life points to 13.34%, 15.84%, and 20.65%, respectively, and removes 97.8% of Q's excess parameter compensation relative to P. At the target point, QCP improves on Q in RMSRE, mean and median absolute relative error, the 95th percentile of absolute relative error, and the fraction within ±10%; its absolute signed bias is also smaller. Relative to P, QCP reduces all three aggregate RMSREs but improves only 74, 76, and 77 of the 160 fixed-truth cells. P retains advantages in typical absolute error and training cost.

The study connects parameter recovery, task-induced coupling and compensation, and constrained repair. Within the studied design domain, QCP retains the target squared-error benefit while repairing Q's marked deterioration at the other two evaluated life points. These gains do not imply dominance over P across all metrics or parameter regions.

## 1 引言

可靠性分析既需要描述寿命分布，也常需要回答一个更具体的问题：在给定可靠度下，寿命边界是多少？三参数 Weibull 模型以形状 $\beta$、尺度 $\eta$ 和位置 $\gamma$ 描述寿命，其小样本估计是长期研究的问题 [1,2,3,4]。最小差异方法 [5,6]、神经网络估计 [7,12] 及经典拟合与一致估计方法 [13,14] 提供了不同的参数恢复途径。当估计结果最终用于某个寿命点时，参数误差是影响最终精度的中间量，而不是最终任务本身。

设 $R$ 为生存概率，可靠度寿命点满足 $R(x_R)=R$。本文关注的 $x_{0.95}$ 是可靠度为 95% 时的寿命边界，即失效分布的 5% 分位点。对输出三个参数的监督网络，一个基础选择是如何把三个误差合成为标量损失。直接相加带量纲的平方误差会受单位与数值尺度影响；归一化后使用 $1{:}1{:}1$ 系数，则构成透明、可复现的参数恢复参照。但归一化并未回答三个参数对 $x_{0.95}$ 应具有怎样的相对作用。等系数是一种度量约定，不是由该寿命点任务唯一推导出的权重。

三个参数对寿命点的影响随参数位置变化，误差还可能相互放大或抵消。因此，逐项惩罚参数偏差与惩罚由它们共同形成的寿命点偏差并不等价。分位数回归、任务聚焦学习与目标泛函研究为按最终使用量定义损失提供了一般思想 [8,9,10,11,15]；Weibull 参数与插件分位点的估计精度也可能呈现不同排序 [16]。本文保留三参数 Weibull 输出，将其通过寿命点公式连接到相对平方损失。这个改变不是寻找另一组固定系数，而是让目标公式在反向传播时引入依赖当前预测的敏感度及参数误差耦合。

这种目标对齐同时留下一个结构性问题。三个参数决定一条分布曲线，而单个寿命点只提供一个标量监督信号。多组不同参数可以产生相同的 $x_{0.95}$，却给出不同的 $x_{0.90}$ 和 $x_{0.99}$。因此，直接训练所需寿命点能够使优化目标更明确，却未必约束了三参数输出的全部偏离方向。若继续用同一参数向量计算其他寿命点，就需要检查这些自由度的后果。

本文围绕三个连续问题展开：在共同三参数网络下，寿命点损失 Q 相对参数损失 P 能改善多少目标精度；单点监督是否伴随参数补偿及跨寿命点代价；保留 Q 目标、以参数误差定义可行域的 QCP 能否修复这种代价。P 提供参数恢复参照，Q 用于检验任务对齐并暴露补偿机制，QCP 是在此基础上提出的约束估计方案。配对仿真、损失几何、固定真值区域分析及多项误差统计共同检验这条链条，使总体精度、内部参数偏离和方法成本分别得到回答。

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

三个平方项使用相同系数；位置误差以 $\eta$ 归一化，避免其度量随 $\gamma$ 接近零而发散。因此，$1{:}1{:}1$ 指的是上述归一化坐标中三个误差项的等系数，而不是三个原始参数误差等权，也不是三个相对误差都以各自真值作分母。该损失明确控制参数恢复，但并非由寿命点敏感度导出的度量。

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

局部寿命点平方误差可写为

$$
(s_0^\mathsf Tu)^2
=\sum_i s_{0,i}^2u_i^2+2\sum_{i<j}s_{0,i}s_{0,j}u_i u_j.
$$

对角项反映各参数的局部敏感度，交叉项则允许误差联合放大或抵消。本文将这种通过寿命点形成的联合评价称为任务诱导耦合。它不是三个独立参数误差权重的简单替换。

P 在三个方向上惩罚参数误差；Q 的局部 Hessian 则为秩一，在与 $s_0$ 正交的两个方向上没有二阶惩罚。更直接地说，$\hat x_{0.95}=x_{0.95}$ 在合法输出空间中定义等寿命点曲面。沿该曲面改变参数，可以保持目标点不变，同时改变其他寿命点。这是单个标量训练目标留下的自由度，不是三参数 Weibull 分布本身不可识别。上述秩一结论针对单组样本、真值处的输出误差坐标；它不是共享神经网络权重空间 Hessian 的秩结论。

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

分母为零时该行取零；$C$ 越接近 1，表示相加后的绝对目标误差相对于三项贡献绝对值之和越小，而不单独说明参数偏离的绝对大小。具体对称分解见补充材料 S5.1。该指标与平均 $L_P$ 配合使用，分别反映误差抵消程度和参数偏离幅度。

以 P 为参照，另定义 QCP 对超额补偿的恢复比例

$$
\mathrm{Resolution}_{\mathrm{comp}}
=\frac{C_Q-C_{\mathrm{QCP}}}{C_Q-C_P}.
$$

本研究中 $C_Q>C_P$，因而该比例有明确参照；它衡量补偿指标的回落，不是寿命点精度的改善比例。

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

为说明 RMSRE 之外的误差形态，同时报告目标点的平均绝对相对误差、绝对相对误差中位数、95% 分位点、±10% 内比例和有方向偏差。固定真值单元内的偏差—方差分解见补充材料 S4.3。指标分别回答整体平方误差、典型误差、尾部与方向问题，不合并为综合分数。这里“绝对误差的 95% 分位点”是误差分布的尾部统计量，不是可靠度寿命点 $x_{0.95}$。

对固定真值单元 $c$，记 $b_c=\operatorname{mean}(e_c)$、$v_c=\operatorname{mean}[(e_c-b_c)^2]$，则

$$
B_{\mathrm{RMS}}=\sqrt{\operatorname{mean}_c b_c^2},
\qquad S_{\mathrm{within}}=\sqrt{\operatorname{mean}_c v_c},
\qquad \mathrm{RMSRE}^2=B_{\mathrm{RMS}}^2+S_{\mathrm{within}}^2.
$$

$B_{\mathrm{RMS}}$ 不允许不同区域的正负偏差相互抵消；$S_{\mathrm{within}}$ 则包含抽样重复与训练随机性形成的单元内波动。各比较的区间与分层结果未作多重比较校正，分别按既定主比较和描述性机制分析解释。

## 3 结果

### 3.1 单点目标对齐的收益与代价

在共同预算下，Q 将目标 $x_{0.95}$ 的 RMSRE 从 16.432% 降至 16.092%，相对改善 2.069%（95% CI：1.280%–2.811%）。然而，相同参数预测在另外两个寿命点上的表现明显下降：$x_{0.90}$ 和 $x_{0.99}$ 的 RMSRE 相对 P 分别增加 36.411% 和 63.114%（表1）。直接训练目标的收益温和，未受直接监督的寿命点代价更大。

**表1　三条路线在三个寿命点的总体 RMSRE**

| 寿命点 | P | Q | QCP | Q 相对 P 改善（95% CI） | QCP 相对 Q 改善 | QCP 相对 P 改善（95% CI） |
|---|---:|---:|---:|---:|---:|---:|
| $x_{0.90}$ | 13.657% | 18.630% | 13.336% | −36.411%（−38.508%–−34.321%） | 28.417% | 2.353%（1.809%–2.904%） |
| $x_{0.95}$ | 16.432% | 16.092% | 15.841% | 2.069%（1.280%–2.811%） | 1.562% | 3.599%（3.027%–4.180%） |
| $x_{0.99}$ | 21.960% | 35.820% | 20.647% | −63.114%（−65.268%–−61.158%） | 42.360% | 5.981%（5.277%–6.673%） |

*每条路线包含同样的 200 个配对模型单元。QCP 相对 Q 的完整区间见补充材料 S4.1；表内负改善表示误差增加。RMSRE 的百分数表示误差水平，相对改善的百分数表示两路线误差水平之比。*

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

相对 Q，QCP 在目标点的 RMSRE、平均绝对误差、中位绝对误差及 95% 分位误差均降低，±10% 内比例提高，有方向偏差的绝对值也减小。但相对 P，较低 RMSRE 不伴随每项典型误差指标的改善（表3）：P 的平均绝对误差与中位绝对误差略低，±10% 内的预测比例也更高。三条路线的排序取决于所评价的误差特征。

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

固定真值下的偏差—方差分解进一步显示，P、Q、QCP 的单元内标准差分量依次为 14.824%、14.493%、14.210%，区域偏差的 RMS 分量则依次为 7.091%、6.994%、7.001%，均约为 7%。总体平方误差的下降主要伴随重复估计波动减小，而不是系统偏差消失（补充材料 S4.3）。

三路线各 200 个 fits 均进入分析，预测无非有限值或支持域违规。QCP 有 3 个模型运行到 600-epoch 上限；其余模型及全部 P/Q 模型在上限前结束。统一最大预算提供了相同的训练机会，但 QCP 的约束求解与前置参考训练增加了计算成本。

## 4 讨论

### 4.1 从参数等系数到任务诱导耦合

本文的 P 与 Q 都从寿命样本输出三个 Weibull 参数。Q 不跳过分布，而是通过分布公式评价所需寿命点。P 的归一化解决量纲问题，等系数则表达一种参数恢复要求；Q 让这些误差按它们对目标的联合影响进入损失。两者回答的是如何训练同一估计器，而非参数模型与无参数分位数模型谁更好。

把 Q 理解为“给参数找到最合适的权重”仍不完整。固定对角权重只能改变各参数误差的相对惩罚，不能表达参数间的抵消项。Q 同时包含敏感度与交互，而且敏感度随当前预测变化。§2.4 的路径平均表达说明，这种有限误差度量可以精确写出，但不能冻结其中的矩阵再当作原 Q 使用。

这一解释有独立的辅助检验。在早期 300/20 预算下，24 个匹配单元的真值点静态敏感度代理 M95 的 RMSRE 为 0.2005，高于 P 的 0.1676 和 Q 的 0.1622，且 24/24 单元均未优于二者。局部近似项虽改善，非线性余项与交叉项却使真实寿命点误差增加（补充材料 S5.3–S5.4）。该结果排除了“Q 只是该真值点静态代理”的解释；它不表明所有任务加权参数损失都无效，也不单独识别优化过程中的因果贡献。

### 4.2 为什么更贴近任务的 Q 只取得有限收益

首先需要区分“是否更好”和“为什么没有好很多”。当前 Q 的目标 RMSRE 确实低于 P：16.092% 对 16.432%，相对改善 2.069%。但平均绝对误差、中位绝对误差和 ±10% 内比例没有同时改善，160 个固定真值单元中也只有 42 个方向有利。Q 优化的是相对平方风险，不是所有误差统计量，也不是每个参数区域各自的最小风险。

理想化地，设 $\mathcal F$ 为共同的预测函数集合，$\mathcal R_Q(f)$ 为相同数据分布上的总体目标平方风险，$f_P\in\mathcal F$ 为 P 学得的预测器。按定义，

$$
\inf_{f\in\mathcal F}\mathcal R_Q(f)\le\mathcal R_Q(f_P).
$$

这说明直接目标存在不差于 P 候选解的最优可能性，却没有证明有限训练得到的 $\hat f_Q$ 达到该下确界。实验比较的是实际训练与验证选择后的模型，不是两个已知的总体全局最优解。

有限收益可以结合三个事实理解。第一，P 并非无效参照。在当前设计域内，寿命点是三个参数的平滑函数；对全部归一化参数偏离的控制，已能产生较准确的插件寿命点。Q 改变的是这一参照上剩余的任务度量错配，而不是从一个完全不相关的目标出发。第二，每个待估样本只有 7–20 个寿命观测。改变训练损失不增加这些观测本身的信息；$n$ 从 7 增至 20 带来的共同改善明显大于方法间差异。第三，经验损失优化、共享网络权重、正则化及验证选择共同决定实际解。每个 $n$ 单独训练的网络仍需同时处理 40 个参数组合及其抽样变化；输出层的敏感度结构不能直接推出该网络最终的泛化排序。

训练预算也提供了一个实测参照：早期 300/20 下 Q 相对 P 的 RMSRE 改善为 3.00%，共同预算下为 2.069%。这说明方法差距随训练机会变化；它不能被解释为目标对齐固有的常数量级。本文不把这几个百分点归因于某个未经分离验证的单一机制，而用几何分析说明可发生什么，用配对结果说明本次实际发生了多少。

### 4.3 单点补偿为何影响其他寿命点

一个寿命点由三个参数共同决定。沿等寿命点曲面的参数变化可以保留目标值，却改变其他寿命点。这解释了为什么 Q 的平均参数损失达到 71.714、补偿指数达到 0.91455 时，目标 RMSRE 仍能略低于 P。内部偏离并未全部表现为目标点误差，而是在参数贡献相加时被部分抵消。

单纯的参数补偿不必破坏唯一目标的精度。因此，不能只因参数不准便判定 Q 对 $x_{0.95}$ 无效。真正的下游证据是：同一组预测在 $x_{0.90}$ 与 $x_{0.99}$ 上明显退化。本文据此把 Q 作为机制中间路线，展示任务对齐的收益以及单点监督留下的缺口，而不以“目标点略有改善”作为推荐整组三参数预测的充分依据。

QCP 的修复呈现相应的不对称性。相对 Q，目标点 RMSRE 改善 1.562%，另外两点却分别改善 28.417% 和 42.360%。这与“限制近等目标的参数偏离，对目标值影响较小、对其他寿命点影响较大”的几何解释一致。相对 P 的总体改善也从 $x_{0.90}$ 的 2.353% 增至 $x_{0.99}$ 的 5.981%。但相对改善还受各点的基线误差及敏感度影响，不能仅据最大增益出现在 $x_{0.99}$ 就断定任务对齐没有作用，或推出任意可靠度水平上的单调优势。

### 4.4 QCP 组合了什么，又没有保证什么

QCP 保留 $L_Q$ 作为主目标，以 $L_P\le\tau_j$ 规定可接受的参数偏离。可行域由参数损失的定义与阈值确定；增广系数、乘子更新和 checkpoint 规则决定如何寻找并选择可行解。P 的归一化与阈值仍是方法的一部分，其作用由“主优化目标”转为“内部参数偏离的边界”，并没有变得无关。

当前实测支持将 QCP 作为这条研究链的最终约束方案。相对 Q，它在表3的五项精度统计上均改善，偏差绝对值也更小；参数损失与补偿程度接近 P，并修复了两个非目标点的明显退化。QCP 因而不只是用目标精度交换参数恢复：在本次训练结果中，它同时改善了两者。

不过，这不是“加约束必然比 Q 更好”的定理。在相同总体目标与函数空间下，任何可行子集 $\mathcal F_\tau\subseteq\mathcal F$ 都满足

$$
\inf_{f\in\mathcal F}\mathcal R_Q(f)
\le
\inf_{f\in\mathcal F_\tau}\mathcal R_Q(f).
$$

约束不可能通过缩小可选范围来突破无约束的理想最优值。实际 QCP 优于实际 Q，说明约束训练与可行 checkpoint 选择在有限样本学习中得到了测试风险更低的解；这一结果与限制不稳定解、改善选解的解释相容，但终态比较没有分别量化这些过程的贡献。

相对 P，QCP 的三个总体 RMSRE 和目标点绝对误差的 95% 分位点更低，但 P 的平均绝对误差、中位绝对误差与 ±10% 内比例更好。QCP 相对 P 的真值单元效应中位数在三点上也均为负。因此，QCP 的正面主张是当前设计域内较低的总体平方风险、受控的参数偏离以及相对 Q 的跨点恢复，不是全面替代 P。较小的典型误差与较低计算成本仍是 P 的实际优势；QCP 的单模型中位训练耗时为 87.2 s，还需计入前置 P 参考训练与约束筛选。

### 4.5 效应量、使用条件与证据范围

样本量分析有助于判断方法收益的实际量级。条件于 P 的四点经验误差曲线，Q 的改善相当于增加约 0.30–0.54 个观测，QCP 相当于约 0.57–1.04 个观测（补充材料 S4.2）。这里的 $n$ 是一次待估样本包含的寿命观测数，不是训练仿真集规模；等效数量是描述性换算，不是实际采样替代率。

当前网络在仿真标签已知的条件下训练，输入保留量纲，评价集中于固定 $\eta$、给定参数网格与未删失小样本。训练好的 QCP 预测器只需输入寿命样本，不需要待估样本的真实参数；真参数用于监督训练和约束选择。将其用于实际数据，关键是确认训练分布、单位尺度与实际寿命机制是否匹配。若进一步要求在无真参数标签的实际数据上重新训练，则需另行设计训练依据。

统计结果反映当前设计单元的平均风险。区域效应、多指标排序和训练成本说明，实际任务仍需明确更重视总体平方误差、典型偏差，还是某一侧的风险。本文的对称相对平方损失给出寿命点估计，不提供具有指定覆盖率的可靠性置信下限。早期 300/20 P/Q 的高估与低估再分配结果保留在补充材料 S6，不能代替当前 600/60 三路线的单侧风险评价。

共同预算分析是在已有测试结果打开后的扩展，区间亦受折间重叠和有限种子数量影响。它与配对设计、参数诊断及跨寿命点结果共同支持当前问题的回答；独立参数域与实际数据属于后续外部验证。三个评价寿命点及描述性曲线不等于完整分布的精度保证。

## 5 结论

本研究以三参数 Weibull 网络为共同估计器，区分了参数恢复与寿命点精度两种训练要求。P 在归一化坐标中提供等系数参数参照，Q 通过寿命点公式引入任务诱导耦合。共同预算下，Q 将目标 $x_{0.95}$ 的 RMSRE 从 16.432% 降至 16.092%，但这一收益没有扩展到全部典型误差指标与多数固定真值单元。

单点监督同时允许较大的参数误差相互补偿。Q 的目标点收益伴随 $x_{0.90}$ 与 $x_{0.99}$ 的明显退化，表明一个准确寿命点不足以证明其内部参数可准确支持其他寿命点。Q 在本文中承担揭示这一机制的中间作用。

QCP 以寿命点精度为主目标、以参数误差定义可行域，将参数补偿降至接近 P 的水平，并在三个评价寿命点上取得本次比较中最低的总体 RMSRE。它在目标点的五项精度统计及偏差绝对值上均优于 Q，是本文提出的约束修复方案；相对 P，其收益集中于总体平方误差与部分较大误差统计，而不是典型精度、逐区域表现和计算成本的全面优势。任务对齐决定优化所需量，参数约束限制单点监督留下的内部自由度，两者在当前有限样本学习中发挥了互补作用。

## 数据与代码可用性

仿真协议、训练与派生分析代码、模型单元结果、配对预测及校验清单随本研究项目保存。当前正文数值来自共同预算三路线分析及其跨寿命点、区域分布和偏差—方差派生结果；文件与证据对应关系见[补充材料 S7](Study02论文补充材料-v2.3.md)及[引用与完整性审计](引用与完整性审计.md)。历史预算分析单独列于补充材料，不与当前主表混用。本文工作稿尚未投稿，公开仓储地址将在发布时补充。

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
