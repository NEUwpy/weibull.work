"""One-off bilingual editorial revision; preserve all table rows and equations."""
from pathlib import Path
import re

M = Path(__file__).resolve().parents[1]
paths = [M/'Study02论文初稿-v2.7.0.md', M/'submission/Study02-manuscript-v2.7.0-en.md', M/'Study02论文附录-v2.7.0.md', M/'submission/Study02-supplement-v2.7.0-en.md']
original = [p.read_text(encoding='utf-8') for p in paths]
texts = original.copy()

def paragraph(i, prefix, new):
    lines = texts[i].splitlines()
    found = [j for j,s in enumerate(lines) if s.startswith(prefix)]
    assert len(found)==1, (i,prefix,found)
    lines[found[0]] = new
    texts[i] = '\n'.join(lines)+'\n'

def replace(i, old, new=''):
    assert old in texts[i], (i,old)
    texts[i] = texts[i].replace(old,new)

paragraph(0, '*图1', '*图1　神经网络与监督路径。A：n–256–128–64–3全连接网络、参数解码与寿命点计算，圆点示意神经元。B：P按参数误差训练，Q按目标寿命点误差训练，QCP加入参数约束惩罚Ψ；Σ表示三项参数误差平方之和，虚线为梯度回传或阈值依赖。底部示意验证选点规则，空心圈为QCP选中点。*')
paragraph(1, '*Figure 1.', '*Figure 1. Neural architecture and supervision paths. A: the n–256–128–64–3 network, parameter decoding, and life-point calculation; circles represent neurons schematically. B: P uses parameter error, Q uses target life-point error, and QCP adds the parameter-constraint penalty Ψ. Σ sums the three squared parameter errors; dashed arrows indicate gradients or threshold dependence. Bottom plots illustrate validation selection; the open circle marks the selected QCP checkpoint.*')
paragraph(0, '*图2', r'*图2　损失几何与参数补偿。A：固定 $\gamma=100$、真值 $(\beta,\eta)=(1.5,1000)$ 的输出切片；虚线为等目标寿命点轨迹，灰线为绝对相对误差等高线。B：200个QCP选定检查点的验证集平均参数损失与目标误差，虚线为 $L_P/\tau_j=1$。C：参数误差的精确对称贡献，标记、粗线和细线分别为中位数、四分位范围及5%–95%分位范围。D：每点为一个模型单元，横纵坐标分别为逐预测贡献绝对值之和与相加后绝对误差的均值；虚线表示无抵消，插图等比例放大P/QCP。*')
paragraph(1, '*Figure 2.', r'*Figure 2. Loss geometry and parameter compensation. A: output slice at $\gamma=100$ and truth $(\beta,\eta)=(1.5,1000)$; the dashed curve preserves the target life point, and gray contours show absolute relative error. B: validation-average parameter loss and target error for 200 selected QCP checkpoints; the boundary is $L_P/\tau_j=1$. C: exact symmetric parameter contributions; markers, thick lines, and thin lines denote medians, interquartile ranges, and 5th–95th percentile ranges. D: model-unit means of within-prediction contribution magnitudes and absolute summed error. The dashed line denotes no cancellation; the equal-aspect inset enlarges P/QCP.*')
paragraph(0, '*图3', '*图3　三种预设寿命点的误差与配对效应。A：总体RMSRE。B：Q相对P、QCP相对Q及QCP相对P的RMSRE改善与配对crossed-bootstrap 95%区间；正值表示改善。比较包含200个配对模型单元，插图放大目标点效应。*')
paragraph(1, '*Figure 3.', '*Figure 3. Errors and paired effects at three prespecified life points. A: pooled RMSRE. B: relative RMSRE improvements for Q vs P, QCP vs Q, and QCP vs P, with paired crossed-bootstrap 95% intervals; positive values denote improvement. Comparisons include 200 paired model units. The inset enlarges target-point effects.*')
paragraph(0, '*图4', r'*图4　区域效应与目标点收益来源。A：Q、QCP相对P的160个真值单元RMSRE改善；白色菱形为中位数，粗线为四分位范围。B：在 $x_{0.95}$ 上按 $\Delta_c$ 降序累计QCP相对P的MSE改善，以全部净改善为100%；超过100%的部分由后续单元的退化抵消。*')
paragraph(1, '*Figure 4.', r'*Figure 4. Regional effects and sources of target gains. A: cell-level RMSRE improvements of Q and QCP over P across 160 truth cells; white diamonds and thick lines denote medians and interquartile ranges. B: cumulative QCP-vs-P MSE improvement at $x_{0.95}$, ordered by descending $\Delta_c$ and normalized to total net improvement. Gains above 100% are offset by deterioration in subsequent cells.*')
paragraph(0, '*各单元具有', '*各单元包含相同数量的预测。中位数由单元RMSRE相对改善计算，负值表示P误差较低。*')
paragraph(1, '*Truth cells contain', '*Truth cells contain equal numbers of predictions. Medians summarize cell-level relative RMSRE improvements; negative values favor P.*')
paragraph(0, '*误差指标由当前', '*误差指标汇总全部测试预测；高估指正的目标相对误差。耗时为单模型CPU训练时间中位数，QCP的前置参考训练和筛选成本见附录A.2。*')
paragraph(1, '*Secondary metrics are', '*Error metrics pool all test predictions; overestimation denotes positive relative target error. Times are medians per CPU fit. Appendix A.2 reports QCP reference-training and screening costs.*')
paragraph(0, '固定 $\\eta$ 下', r'固定 $\eta$ 下，该网格的真实 $x_{0.95}$ 为238.05–1552.09。本文采用相对误差比较不同寿命水平。')
paragraph(1, 'Although scale was fixed', r'With scale fixed, true $x_{0.95}$ ranged from 238.05 to 1552.09. Relative error allowed proportional comparisons across these life levels.')
replace(0, '二者都不提供单条预测的误差上界。')
replace(0, '这些事后补充对照复用原样本；当前证据支持根据寿命点任务与参数解释需求共同设计监督，不支持QCP精度优于简单加权。', '这些结果表明，监督设计需要同时考虑寿命点任务与参数解释需求。')
replace(1, 'These post-test controls reuse the original samples. The evidence supports matching supervision to both the intended life points and parameter interpretation, without demonstrating an accuracy advantage of QCP over simple weighting.', 'These results support matching supervision to both the intended life points and parameter interpretation.')
replace(0, '该比较允许实际停止轮次不同，不能把两项相对改善相加当作独立因果贡献。')
replace(1, ' Stopping epochs could still differ, and the two relative improvements cannot be added as independent causal contributions.')
replace(0, '因此，本批Q轨迹不能仅靠可行选点获得同一修复；该结果不涉及延长训练或改变优化后的可行性，也没有可汇总的Q_FEAS测试精度。', '因此，原生Q轨迹的可行性筛选未产生可用模型。')
replace(1, 'Feasible selection alone therefore supplied no repair within these trajectories and no Q_FEAS test-accuracy result to aggregate. This finding does not establish infeasibility under longer training or altered optimization.', 'Feasibility screening of the native Q trajectories therefore produced no eligible model.')
replace(0, '三个点均被直接监督，该结果不是未监督寿命点的泛化证据。')
replace(1, ' All three points were directly supervised, so these results do not establish generalization to unsupervised life points.')
paragraph(0, '补充协议在旧测试', '')
paragraph(1, 'The supplementary protocol was specified', '')
replace(0, '完整单元身份、分组数值及事后分解的解释范围见附录B.7。', '完整单元身份与分组数值见附录B.7。')
replace(1, ' This is a post hoc localization of observed gains, not a rule for selecting a procedure when true parameters are unknown.')

zh_disc = r'''## 4 讨论

### 4.1 任务对齐改变了什么

P分别惩罚三个归一化参数误差，Q则评价它们对最终寿命点的联合影响。Q的敏感度随预测参数变化，分布公式中的交互项允许误差放大或抵消。单点损失在输出误差空间保留的等寿命点自由度，为参数漂移提供了几何解释。

早期M95消融进一步显示，真值点的静态敏感度代理未能复现Q的精度：局部近似项虽有改善，有限误差的交叉项与非线性余项却使实际目标误差增加（附录C）。这一差异说明，所检验的局部代理遗漏了影响实际寿命点误差的组成部分。

### 4.2 如何理解小幅总体收益

总体RMSRE按平方误差汇总，对较大误差的变化更敏感。困难单元的误差下降可以决定总体排序，同时与典型单元略偏向P并存。图4和附录图B4显示，目标点净收益集中于少数低形状、低位置比单元。

P本身已给出较准确的插件寿命点。单个待估样本仅含7–20个观测，增加观测数带来的误差下降明显大于流程间差异。验证准则也影响流程表现：统一验证目标后，Q相对P的目标改善由主比较的2.07%缩小至1.32%，表明训练目标与检查点选择共同影响最终精度。

### 4.3 参数补偿为何影响其他寿命点

沿等目标寿命点曲面移动，参数可以明显偏离而目标值保持接近不变，其他寿命点则随之改变。Q的形状参数中位数为20.39、尺度参数中位数为67.00；形状与位置贡献主要为正、尺度贡献主要为负。逐预测精确分解将这种抵消定位到同一次估计内部。Q距位置解码上界不足0.1%的预测仅占0.014%（附录B.6），参数漂移因此主要表现为参数组合改变，位置上界附近的预测占比较小。

若预测器只用于目标点，参数补偿可以与较低目标风险并存。当同一组参数还用于解释分布或计算其他寿命点时，参数恢复就成为额外要求。QCP对两个非目标点的改善远大于目标点改善，与限制参数自由度的作用相符。

### 4.4 QCP与简单修复方式的取舍

QCP以参数损失阈值规定可接受的平均参数偏离，并从验证可行的检查点中选择目标误差最小者。其特点是将参数恢复要求写成可检查的条件，阈值由归一化方式、参考P模型和松弛系数共同确定。

固定加权QP也能修复Q。共同600/60预算下，QP与QCP的目标RMSRE分别为15.8505%和15.8406%；QCP相对改善0.0623%，95%经验区间为−0.0499%至0.1679%，另外两个点的区间也跨零（附录B.9）。二者的平均参数损失与补偿指数接近。QP的记录训练中位耗时较低，QCP另需参考训练与约束筛选。因此，当前精度表现接近，主要取舍在于显式验证可行性控制与计算成本。

约束子集上的理想最优目标风险至少与原函数集合上的最优风险一样大。实际QCP较实际Q的改善反映了有限训练中的正则化与选解作用。共同验证后Q仍有目标优势，而原生Q轨迹未出现可行检查点；多点直接监督也缓解了跨点误差。综合这些对照，参数正则化和多点监督均是有效修复途径；当参数本身需要解释时，QP与QCP同时提供了更好的参数恢复。

### 4.5 适用范围与后续验证

本研究覆盖固定尺度、未删失小样本及相同参数网格内的新抽样。尺度标签恒为1000，使P可通过学习常量降低尺度误差，Q则可通过偏离该常量的参数组合逼近目标点。输入保留原始量纲，因此尺度变化、单位变化与其他寿命生成机制需要进一步验证。本文的几何分析刻画输出误差空间；扩展到完整分布评价或具有指定覆盖率的寿命置信下限，还需相应的评价目标。

共同预算扩展与补充对照在早期测试结果已知后形成，复用了原48,000组仿真样本。折间训练集重叠且训练种子有限，本文区间为条件于当前设计的经验近似；真值单元的排序用于描述本批结果。后续独立样本与变化尺度实验可检验这些收益、补偿形态及方法排序的稳定性。

## 5 结论

在固定尺度的三参数Weibull小样本设计域内，将训练与验证目标转向目标寿命点，降低了总体目标误差，同时产生较大的参数补偿与跨寿命点代价。总体收益集中于少数高误差单元，P仍保留典型绝对误差优势。

引入参数恢复要求能够修复跨点退化。QCP通过验证集平均参数损失阈值控制可行性，并保留目标点收益；固定加权QP取得接近的精度。统一验证后Q仍保留目标优势，三点直接监督也能缓解跨点误差。监督设计应同时考虑最终寿命点任务、参数解释需求及计算成本。

'''
en_disc = r'''## 4 Discussion

### 4.1 What task alignment changes

P penalizes the three normalized parameter errors separately; Q evaluates their joint effect on the final life point. Q's sensitivity changes with predicted parameters, and interactions in the distribution formula permit amplification or cancellation of errors. Equal-life freedom in output-error space provides a geometric account of parameter drift.

The earlier M95 ablation shows why the tested static truth-point sensitivity proxy did not reproduce Q accuracy. Although the local approximation term improved, finite-error cross terms and nonlinear remainders increased the actual target error (Appendix C). The local proxy thus omitted components that materially affected life-point error.

### 4.2 Interpreting modest pooled gains

Pooled RMSRE aggregates squared errors and is especially sensitive to larger errors. Reductions in difficult cells can determine the overall ranking while typical cells slightly favor P. Figures 4 and B4 locate the net target gains in a few cells with low shape and low location ratio.

P already provides reasonably accurate plug-in life points. Each estimation sample contains only 7–20 observations, and increasing this number reduces error more than changing the procedure. Validation criteria also affect performance: using a common validation target reduced Q's improvement over P from 2.07% in the primary comparison to 1.32%. Training objectives and checkpoint selection therefore both affect final accuracy.

### 4.3 Why compensation affects other life points

Parameters can move substantially along an equal-target surface while the target remains nearly unchanged and other life points change. Q had median predicted shape 20.39 and scale 67.00; shape and location contributions were mainly positive, whereas scale contributions were mainly negative. Exact prediction-level decomposition locates this cancellation within individual estimates. Only 0.014% of Q predictions lay within 0.1% of the location decoding upper bound (Appendix B.6), so drift mainly involved altered parameter combinations, with few predictions near that boundary.

Compensation can coexist with low target risk when the predictor is used only for that target. Parameter recovery becomes an additional requirement when the same parameters also describe the distribution or estimate other life points. QCP's larger improvements at the two non-target points are consistent with restricting this freedom.

### 4.4 QCP and simpler repairs

QCP expresses acceptable average parameter displacement through a loss threshold and selects the lowest-target-loss checkpoint satisfying validation feasibility. Its distinguishing feature is a checkable parameter-recovery condition, defined jointly by normalization, the reference P model, and the slack coefficient.

Fixed weighting also repaired Q. Under the common 600/60 budget, QP and QCP had target RMSRE of 15.8505% and 15.8406%. QCP's relative improvement was 0.0623%, with a 95% empirical interval from −0.0499% to 0.1679%; intervals at the other two points also crossed zero (Appendix B.9). Mean parameter loss and compensation were similar. Recorded median training time was lower for QP, while QCP additionally required reference training and constraint screening. With closely matched observed accuracy, the main trade-off is between explicit validation feasibility control and computational cost.

The ideal minimum target risk over a constrained subset is at least as large as that over the original function class. Better fitted QCP performance than fitted Q therefore reflects regularization and solution selection under finite training. Q retained a target advantage under common validation, whereas native Q trajectories supplied no feasible checkpoint. Direct multi-point supervision also mitigated cross-point errors. Together, these controls identify parameter regularization and multi-point supervision as effective repairs; QP and QCP additionally provided better parameter recovery when parameter interpretation mattered.

### 4.5 Scope and further validation

This study evaluates new uncensored small samples within a fixed-scale parameter grid. The constant scale label of 1000 lets P reduce scale error by learning a constant, whereas Q can approach the target using off-label parameter combinations. Inputs retain their original units, so changes in scale, units, and lifetime-generating mechanisms require further evaluation. The geometric analysis concerns output-error space; complete-distribution accuracy and life confidence bounds with specified coverage require corresponding evaluation objectives.

The common-budget extension and supplementary controls followed inspection of early test outcomes and reused the original 48,000 simulation samples. With overlapping fold training sets and finite training seeds, intervals are empirical approximations conditional on the present design; truth-cell rankings describe this set of outcomes. Independent samples and varying-scale experiments can assess the stability of the gains, compensation patterns, and procedure rankings.

## 5 Conclusions

Within the fixed-scale three-parameter Weibull small-sample design, aligning training and validation with a target life point reduced pooled target error while producing substantial parameter compensation and deterioration at other life points. Pooled gains concentrated in a few high-error cells, while P retained an advantage in typical absolute error.

Parameter-recovery requirements repaired cross-point deterioration. QCP controlled feasibility through a validation-average parameter-loss threshold while preserving target gains; fixed weighting achieved closely matched accuracy. Q retained its target advantage under common validation, and direct three-point supervision also mitigated cross-point errors. Supervision should reflect the final life-point task, the intended interpretation of parameters, and computational cost.

'''
for i, start, end, new in [(0,'## 4 讨论','## 数据与代码可用性',zh_disc),(1,'## 4 Discussion','## Data and code availability',en_disc)]:
    a=texts[i].index(start);b=texts[i].index(end)
    texts[i]=texts[i][:a]+new+texts[i][b:]

# Synchronize the embedded English abstract and remove the accidental pasted URL.
abstract=texts[1].split('## Abstract\n\n',1)[1].split('\n\n**Keywords',1)[0]
a=texts[0].index('## Abstract\n\n');b=texts[0].index('## 1 引言',a)
texts[0]=texts[0][:a]+'## Abstract\n\n'+abstract+'\n\n'+texts[0][b:]

# Appendix definitions remain; repetitive qualifications and cross-references go.
for i, fragments in {
2:[
'约束范围不延伸为单条预测的误差保证。',
'目标点精度与配对效应见正文表1、图3，不在此重复。',
'共同预算汇总在早期测试结果读取后形成，因此作为预算敏感性分析解释。',
'三个离散寿命点用于检验跨点变化，完整分布精度需要更密集的可靠度水平评价。',
'该统计量用于描述区域分布，不增加显著性检验。',
'这一例子描述接近总体效应的单元，不表示它是全部真值单元的中位表现。',
'，实际增加观测后的收益仍需直接实验确认',
'该分解属于事后描述性分析。',
'；它不是独立样本的概率',
'该曲线为既有预测上的描述性评价。',
'预设点的配对效应见正文图3。',
'该图仅描述测试结果的区域分布，不提供部署规则。',
'本节来自已有四路线同预算敏感性证据，不是新的首次测试确认。',
'区间均跨零不等于已证明统计等效，而是未显示QCP的精度优势。',
'QP的历史权重选择与QCP阈值选择并非相同开发成本，因此不把这些训练时间作为完整算法开发成本比较。',
'该区别是约束定义上的区别，不能由此推断QCP具有更低测试误差。',
'200个模型单元在训练种子间重复使用48,000组测试样本；这些分布和散点只用于描述终态预测。',
'由于该分析用于机制探索，本文报告方向和效应量，不计算置信区间，也不把零空间与非线性曲率分别解释为已经识别的训练因果。',
'该分解是代数恒等式，各项不对应随机梯度下降过程中可独立识别的因果贡献。',
'它是正文动态敏感度表达的辅助检验，不改变 P/Q/QCP 的主比较。',
'阈值仅用于描述误差形态，共同预算下的收益以正文和附录 B 为准。',
'，不是独立新数据确认',
],
3:[
' Repeated predictions of the same sample are not new independent observations.',
' Validation-average feasibility does not imply an error bound for each prediction.',
' These stages therefore do not constitute independent fresh-data confirmation.',
' Original records did not fully bind processor model and concurrent load, so no cross-hardware speed claim is made.',
' Target accuracy and paired effects are reported in main Table 1 and Figure 3.',
' Three discrete points do not establish complete-distribution accuracy.',
'; collecting additional observations has not been directly tested by this calculation',
'; they are not probabilities',
' Paired effects at prespecified points are in main Figure 3.',
' This map describes test outcomes and does not prescribe deployment selection.',
' The evidence comes from the existing four-route budget-sensitivity experiment, not a new first evaluation.',
' Intervals crossing zero do not demonstrate equivalence; they provide no demonstrated accuracy advantage for QCP.',
' Historical weight and threshold selection incurred different development work, so these fit times are not a complete development-cost comparison.',
' This distinction in definition does not imply lower test error for QCP.',
' All distributions are descriptive; the 200 model units repeatedly use 48,000 samples across training seeds.',
' No interval was calculated for this exploratory ablation, and the null space and nonlinear curvature are not separately identified causal training effects.',
' These are algebraic terms, not independently identified causal contributions in gradient descent.',
' The ablation supports the finite-error qualification without changing the main P/Q/QCP comparison.',
' These results do not establish confidence-bound coverage.',
' Thresholds describe error shape; current common-budget gains are reported in the main text and Appendix B.',
' Current QCP one-sided errors are already given in main Table 3; these earlier P/Q results do not substitute for them.',
' They are not independent fresh-data confirmation.',
]
}.items():
    for fragment in fragments: replace(i,fragment)

paragraph(2, 'QCP 模型检查点的可行性', r'QCP检查点以验证集平均 $L_P\le\tau_j$ 判定可行性。正文所报87.2 s为单次训练中位耗时；前置参考训练与筛选耗时如下。')
paragraph(2, '表中运行信息来自', '表中运行信息来自 `artifacts/qcp_main_analysis/analysis/summary.json`。累计耗时为各路线训练任务的时长之和，单模型中位耗时描述典型运行；前置训练单列如下。')
replace(2, '训练实现使用 PyTorch CPU、float64、每进程一个计算线程；原记录未完整绑定处理器型号和并行负载，因此不作跨硬件速度结论。', '训练采用PyTorch CPU、float64、每进程一个计算线程。')
paragraph(2, '以下诊断由每路线', '以下分位数由每路线480,000条参数预测计算，汇总整个设计域的参数输出分布。')
paragraph(3, 'These descriptive quantiles use', 'These quantiles summarize the design-domain output distribution using 480,000 saved parameter predictions per procedure.')
replace(2, '这两个阈值是本次事后诊断采用的边界邻近尺度，而非训练约束。', '这两个阈值用于诊断预测与位置上界的邻近程度。')
replace(3, 'These post hoc proximity thresholds are not training constraints.', 'These thresholds measure proximity to the location upper bound.')
paragraph(2, '分组和收益均使用', '分组与收益均由同一批测试预测计算，用于定位净收益来源。')
paragraph(2, '按同一批测试结果的ΔMSE', '单元按测试预测的ΔMSE降序排列。')
replace(2, '每个格子是一个设计单元，格子尺寸不表示连续参数区间宽度。', '每个等大格子对应一个设计单元。')
replace(3, 'Each equal-sized tile represents one design cell, not a continuous parameter-interval width.', 'Each equal-sized tile represents one design cell.')
paragraph(2, '*图C1', '*图C1　A：输出误差空间中P与Q的梯度；B：24个匹配模型单元的P/M95/Q RMSRE；C：局部近似项与遗漏项。B、C使用早期300/20预算。*')
paragraph(3, '*Figure C1.', '*Figure C1. A: P and Q gradients in output-error space. B: P/M95/Q RMSRE across 24 matched model units. C: the local approximation and omitted terms. B–C use the earlier 300/20 budget.*')
paragraph(2, '本节数值来自 `artifacts/pq_engineering', '本节数值来自 `artifacts/pq_engineering_audit/summary.json`。')
paragraph(2, 'Q_FEAS在0/200', 'Q_FEAS在0/200条原生Q轨迹内可用；全部记录轮次的最小验证参数损失/阈值比为10.268，未产生可供测试评价的可行模型。')
paragraph(3, 'Q_FEAS was available', 'Q_FEAS was available in 0/200 native Q trajectories. The smallest recorded validation parameter-loss/threshold ratio was 10.268; no feasible model was available for test evaluation.')
paragraph(2, 'QMULTI对表中的三个', '补充结果来源为 `artifacts/submission_controls_v1/analysis/` 下的summary、model_mse、parameter_loss、resources与manifest。')
paragraph(3, 'QMULTI directly supervised all three', 'Supplementary results are recorded in the summary, model_mse, parameter_loss, resources, and manifest files in `artifacts/submission_controls_v1/analysis/`.')

for p, old, new in zip(paths, original, texts):
    new=re.sub(r'\n{3,}', '\n\n', new)
    assert [s for s in old.splitlines() if s.startswith('|')]==[s for s in new.splitlines() if s.startswith('|')], p
    assert re.findall(r'\$\$.*?\$\$', old,re.S)==re.findall(r'\$\$.*?\$\$', new,re.S), p
    assert 'help.openai.com' not in new
    p.write_text(new,encoding='utf-8')
    print(p.name, len(old),'->',len(new))
