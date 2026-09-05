"""English labels for the same evidence-backed v2.7.0 figure objects."""
import re
from matplotlib.text import Text

LABELS={
 'A  160 个真值单元的效应分布':'A  Effects across 160 truth cells',
 'A  三个预设寿命点的误差':'A  Errors at three life points',
 'A  参数贡献抵消':'A  Parameter compensation',
 'A  同一寿命点对应多组参数':'A  Different parameters, same life point',
 'A  有符号误差分布（探索性）':'A  Signed errors (exploratory)',
 'A  样本量与误差':'A  Sample size and error',
 'A  较宽可靠度范围（描述性）':'A  Wider reliability range',
 'A  输出误差空间的梯度':'A  Gradients in output-error space',
 'B  参数恢复':'B  Parameter recovery',
 'B  实际 QCP 检查点的平均约束':'B  Validation-average QCP feasibility',
 'B  目标点净收益的集中与抵消':'B  Concentration and offset of net gains',
 'B  经验曲线换算':'B  Empirical-curve conversion',
 'B  绝对误差的超越比例（探索性）':'B  Absolute-error exceedance (exploratory)',
 'B  选定轮次分布':'B  Selected checkpoint epochs',
 'B  配对比较及 95% 区间':'B  Paired effects and 95% intervals',
 'B  静态代理未复现 Q 的精度':'B  Static proxy did not match Q',
 'C  仿真测试预测的参数贡献':'C  Contributions in test predictions',
 'C  遗漏项反转局部近似的改善':'C  Omitted terms reverse local gains',
 'C  高估与低估的再分配（探索性）':'C  Over- and underestimation (exploratory)',
 'D  同一预测内的抵消':'D  Within-prediction cancellation',
 'D  高估与低估的平方误差贡献':'D  Directional MSE contributions',
 'M95 − P 的目标点相对均方误差':'M95 minus P: target relative MSE',
 'P / QCP 局部（等比例）':'P / QCP (equal aspect)',
 'Q−P 的配对MSE贡献差，':'Paired Q minus P MSE contribution,',
 'Q 相对 P':'Q vs P','QCP 相对 P':'QCP vs P','QCP 相对 Q':'QCP vs Q',
 'QCP 相对 P 的单元 RMSRE 改善（%）':'Cell RMSRE improvement: QCP vs P (%)',
 'RMSRE 相对改善（%）':'Relative RMSRE improvement (%)',
 '不表示每条预测满足误差上界':'No per-prediction error bound',
 '200/200 检查点可行':'200/200 checkpoints feasible',
 '主要位于低形状、低位置比区域':'Low shape and location ratio',
 '位置比':'Location ratio',
 '低估侧MSE：':'Underestimation MSE:', '高估侧MSE：':'Overestimation MSE:',
 '低估侧贡献':'Underestimation\ncontribution','高估侧贡献':'Overestimation\ncontribution',
 '共享数据划分、初始化与最大训练预算；改变训练与验证选点目标':'Shared splits, initialization and epoch limits; different training and selection objectives',
 '分量绝对值之和的均值（%）':'Mean sum of contribution magnitudes (%)',
 '前5个单元：净收益的102.6%':'Top 5 cells: 102.6% of net gain',
 '前五单元的位置见附录图 B4':'Top-five locations: Figure B4',
 '单侧相对误差阈值（%）':'One-sided relative-error threshold (%)',
 '单元 RMSRE 相对改善（%）':'Cell RMSRE improvement (%)',
 '单次估计的寿命观测数 n':'Observations per estimation sample, n',
 '参数补偿与跨寿命点退化':'Parameter compensation;\ncross-point deterioration',
 '各路线分别训练并配对评价':'Separate training; paired evaluation',
 '同一寿命样本':'Same samples','同一网络结构':'Same architecture',
 '固定的归一化参数损失':'Fixed normalized parameter loss',
 '实际目标误差':'Actual target error','寿命点 RMSRE（%）':'Life-point RMSRE (%)',
 '尺度相对误差':'Relative scale error','形状相对误差':'Relative shape error',
 '平均偏差：':'Mean bias:', '平均补偿指数':'Mean compensation index',
 '归一化参数 RMSE（%，对数轴）':'Normalized parameter RMSE (%, log scale)',
 '当前上限：600轮':'Current maximum: 600 epochs',
 '形状参数':'Shape parameter','总体 RMSRE（%）':'Pooled RMSRE (%)',
 '按 ΔMSE 从大到小累计的单元数':'Cells ordered by decreasing MSE gain',
 '按样本量分别训练':'Separate fit for each n',
 '排序与训练折标准化':'Sort; training-fold scaling',
 '无抵消：两者相等':'No cancellation: equality',
 '早期 P 的验证损失决定阈值':'Threshold from earlier P validation loss',
 '最佳检查点轮次':'Selected checkpoint epoch',
 '有符号相对误差（%）':'Signed relative error (%)',
 '有符号相对贡献（%）':'Signed relative contribution (%)',
 '检验收益与代价':'Assess benefits and costs', '比较 P 与 Q':'Compare P and Q',
 '目标对齐':'Task alignment','目标寿命点损失':'Target life-point loss',
 '目标敏感度随预测参数改变':'Target sensitivity changes with prediction',
 '目标点 RMSRE（24模型单元等权）':'Target RMSRE (24 units, equal weight)',
 '目标点 RMSRE（%）':'Target RMSRE (%)',
 '目标点总体误差略降':'Small target-risk gain',
 '相加后绝对误差的均值（%）':'Mean absolute summed error (%)',
 '相对 P 的等效新增观测数':'Equivalent additional observations vs P',
 '研究递进（箭头不表示模型传递）':'Research sequence (no model transfer)',
 '等寿命点轨迹':'Equal-life trajectory','真值':'Truth',
 '累计改善 / 全部净改善（%）':'Cumulative gain / total net gain (%)',
 '经验累计比例（%）':'Empirical cumulative proportion (%)',
 '绝对相对误差阈值（%）':'Absolute relative-error threshold (%)',
 '计算所需寿命点':'Calculate required life points',
 '训练点 0.95':'Target: 0.95','训练目标':'Training target',
 '超过阈值的预测比例（%）':'Predictions exceeding threshold (%)',
 '附录图 C1：静态代理检验（早期300/20预算）':'Figure C1. Static-proxy analysis (earlier 300/20 budget)',
 '附录图 D1：早期300/20预算的误差分布':'Figure D1. Error distributions (earlier 300/20 budget)',
 '限制参数偏离':'Limit parameter displacement',
 '静态局部矩阵':'Static local matrix','验证集平均':'Validation-average',
 '验证目标点 RMSRE（%）':'Validation target RMSRE (%)',
 'P：参数恢复参照':'P: parameter reference',
 'QCP：保留任务目标':'QCP: retain the task objective',
 'Q：目标寿命点对齐':'Q: target alignment',
 '参数损失':'Parameter loss','可靠度 R':'Reliability R',
 '局部放大':'enlarged','模型单元':'model units','局部项':'Local term',
 '遗漏项':'Omitted terms','（增加）':'(increase)','（降低）':'(decrease)',
 '输出':'Output','：高估':': overestimate','：低估':': underestimate',
}

def translate(s):
    for a,b in sorted(LABELS.items(),key=lambda z:-len(z[0])):s=s.replace(a,b)
    if re.search(r'[\u4e00-\u9fff]',s):raise ValueError('Untranslated figure text: '+repr(s))
    return s

def english(fig):
    # FixedFormatter tick labels must be reset through the axis, not Text alone.
    for ax in fig.axes:
        for axis in (ax.xaxis,ax.yaxis):
            labels=axis.get_ticklabels()
            if any(re.search(r'[\u4e00-\u9fff]',v.get_text()) for v in labels):
                axis.set_ticks(axis.get_ticklocs(),labels=[translate(v.get_text()) for v in labels])
    for item in fig.findobj(Text):
        item.set_text(translate(item.get_text()))
        item.set_fontfamily('DejaVu Sans')
        if item.get_fontsize()>7:item.set_fontsize(item.get_fontsize()*.9)
        if item.get_text()=='Task alignment':item.set_fontsize(6)
    fig.canvas.draw()
    for item in fig.findobj(Text):translate(item.get_text())
