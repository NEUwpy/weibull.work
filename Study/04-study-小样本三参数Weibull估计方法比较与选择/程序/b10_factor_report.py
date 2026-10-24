"""Render the distinction between predictive contribution and observed error amplitude."""
import csv
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
PLOT_DEPS=ROOT/'.codex-tmp/b10-plot-deps'
if PLOT_DEPS.exists():
    sys.path.insert(0,str(PLOT_DEPS))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

STUDY=Path(__file__).resolve().parent.parent
OUT=Path(os.environ.get('B10_SELECTOR_OUTPUT',str(STUDY/'结果/B10方法选择-v1')))
DEST=OUT/'factor_analysis'
METHODS=['MLE','MMLE(KR)','WMLE','LSE','LRE(Park)','MDM-0.1','MM']
GROUPS=['no_n','no_level','no_shape','no_spacing']
FEATURES=['log_min','log_mean','gap_first','skewness']


def rows(name):
    with (DEST/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main():
    a=rows('method_group_ablation.csv');c=rows('actual_error_quartile_contrasts.csv')
    matrix=np.array([[float(next(r['loss_increase_pct'] for r in a if r['group']==g and r['method']==m))
                      for m in METHODS] for g in GROUPS])
    contrasts=np.array([[float(next(r['q4_vs_q1_pct'] for r in c if r['feature']==f and r['method']==m))
                      for m in METHODS] for f in FEATURES])
    plt.rcParams.update({'font.size':10,'figure.facecolor':'white','pdf.fonttype':42})
    fig,axes=plt.subplots(2,1,figsize=(11.5,7),layout='constrained')
    labels=[['Remove n','Remove level/scale','Remove shape','Remove spacing'],
            ['Sample minimum','Sample mean','First normalized gap','Sample skewness']]
    titles=['A  Increase in risk-prediction loss after refitting (%)',
            'B  Observed B10 RMSE change: Q4 vs Q1 (%)']
    for ax,values,ylab,title in zip(axes,[matrix,contrasts],labels,titles):
        bound=max(1,float(np.abs(values).max()))
        norm=TwoSlopeNorm(vmin=-bound,vcenter=0,vmax=bound)
        im=ax.imshow(values,cmap='RdBu_r',norm=norm,aspect='auto')
        ax.set_xticks(range(7),['MLE','MMLE','WMLE','LSE','LRE','MDM','MM'])
        ax.set_yticks(range(4),ylab);ax.set_title(title,fontweight='bold',loc='left')
        for i in range(4):
            for j in range(7):
                color='white' if norm(values[i,j])>.85 or norm(values[i,j])<.15 else 'black'
                ax.text(j,i,f'{values[i,j]:+.1f}',ha='center',va='center',color=color)
        fig.colorbar(im,ax=ax,pad=.02,shrink=.9)
    fig.savefig(DEST/'factor_quantification.png',dpi=220,bbox_inches='tight')
    fig.savefig(DEST/'factor_quantification.pdf',bbox_inches='tight')
    plt.close(fig)
    nrows=rows('actual_method_error_by_n.csv')
    nr={(int(r['n']),r['method']):float(r['rmse']) for r in nrows}
    selected=[('log_min','MLE'),('log_min','MDM-0.1'),('log_mean','MMLE(KR)'),('gap_first','MDM-0.1'),('skewness','MM')]
    lines=['# 各方法B10误差的因素量化：补充报告 v1.0','',
        '2026-10-24。已完成四类信息消融、七法分别评价、三个匹配初始化，以及四项样本特征的实际误差幅度分析。',
        '',
        '**能量化，但两种数字不能混用：消融给出误差预测所需的信息贡献；分组对比给出与真实估计误差相关的幅度。它们都不是该因素占全部误差的因果百分比。**',
        '',
        '## 一、删除哪些信息，七法误差就更难预测',
        '',
        '保留原指纹划分、网络结构与预算，每个删除组重新训练，匹配42/43/44三个初始化。使用9,642组原留出样本，风险标签仍为B10误差平方，各法按自身成功集合、β×n条件等权评价；失败不当作零误差。表中为删除组后的风险预测损失相对全特征模型增加百分比。',
        '',
        '| 删除的特征组 | MLE | MMLE | WMLE | LSE | LRE | MDM | MM |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    cn=['样本量n','位置与尺度','分布形状','相邻间距']
    for label,values in zip(cn,matrix):
        lines.append('| '+label+' | '+' | '.join(f'{v:+.2f}%' for v in values)+' |')
    mm=next(r for r in a if r['group']=='no_shape' and r['method']=='MM')
    lines += ['',
        '位置尺度组是样本均值、标准差、最小值、最大值、中位数与极差的对数；形状组包括归一化分位数、变异、偏度、峰度等。这些均由当前样本计算。',
        '',
        f'位置尺度组的删除损失增量为77.19%—148.36%，三个初始化方向一致。形状组对MM具有额外预测价值：损失增加{float(mm["loss_increase_pct"]):.2f}%（95%区间{float(mm["ci95_low"]):.2f}%—{float(mm["ci95_high"]):.2f}%）。n的独立增量较小；间距组删除后本批预测损失反而略低。负值照实保留，不能解释为间距对传统方法误差没有作用。',
        '',
        '这里的预测损失是按训练标签均值归一化后的非负均值一致deviance：D=2[y log(y/μ)−y+μ]。它衡量网络预测各法平方误差的质量，**不是传统方法自身B10 RMSE的增加百分比**。每法、每组的95%区间、初始化范围及原单位风险预测RMSE均在CSV中。',
        '',
        '## 二、同一β、n下，特征高低对应多大的真实误差差别',
        '',
        '使用训练部分在每个β×n条件内确定四分位界限，再在七法共同有效的留出样本中分组。四项特征均覆盖40个条件；四点曲线完整保留，不强迫假设单调。以下为Q4与Q1的实际B10 RMSE对比，均按条件等权：',
        '',
        '| 特征 | 方法 | 低四分位Q1 RMSE | 高四分位Q4 RMSE | 相对变化 | 95%区间 |',
        '|---|---|---:|---:|---:|---:|',
    ]
    cnfeat={'log_min':'样本最小值','log_mean':'样本均值','gap_first':'归一化首间距','skewness':'样本偏度'}
    for f,m in selected:
        r=next(r for r in c if r['feature']==f and r['method']==m)
        lines.append(f'| {cnfeat[f]} | {m} | {float(r["q1_rmse"]):.2f} | {float(r["q4_rmse"]):.2f} | {float(r["q4_vs_q1_pct"]):+.2f}% | [{float(r["pct_ci95_low"]):+.2f}%, {float(r["pct_ci95_high"]):+.2f}%] |')
    lines += ['',
        '这直接给出“特征与方法误差关联有多大”：同样是样本最小值较高，MLE的误差增幅比MDM大；MM的偏度分组差别也很明显。首间距对MDM的Q4−Q1区间跨0，当前不能据此确认端点差异。完整四组曲线还可识别中间低、两端高等关系。',
        '',
        f'一个反例说明消融不能替代误差影响分析：删除n后，MDM的风险预测损失仅增加约0.24%，但原研究中n从7增至50时，其成功记录上的实际B10 RMSE从{nr[7,"MDM-0.1"]:.2f}降至{nr[50,"MDM-0.1"]:.2f}。其他特征可以提供与n重叠的信息，所以“删n后预测变化小”不能推出“n不影响估计误差”；各n的失败比例另存，未把成功集合的精度当作全部尝试的无条件风险。',
        '',
        '## 三、可以怎样写结论',
        '',
        '可以写：“在当前参数域与固定模型下，位置尺度特征对七法B10风险预测提供了较大的额外信息；形状特征对MM的风险预测也有额外贡献。在固定β×n的共同有效样本中，最小值、均值和偏度与不同方法误差存在大小不同的关系。”',
        '',
        '不能写：“位置尺度因素造成了某方法误差的148%”，也不能把各组数值相加归一成总影响100%。相关特征会替代或共同承载信息；分组比较控制了β和n，但没有固定所有其他样本特征。要解释一个特征的孤立因果作用，需要另外定义可实现的样本扰动与重新估计实验。',
        '',
        '这些是复用原留出集的追加解释分析；区间固定已训练模型，初始化变化单独报告，不涵盖全部训练不确定性。范围仍限于η=1000、γ=500及已有β/n网格；新原型未作跨尺度位置推广。',
        '',
        '![预测贡献与实际误差关联幅度](结果/B10方法选择-v1/factor_analysis/factor_quantification.png)',
        '',
        '产物：[七法×特征组消融](结果/B10方法选择-v1/factor_analysis/method_group_ablation.csv)、[按n分解](结果/B10方法选择-v1/factor_analysis/method_group_ablation_by_n.csv)、[实际误差对比](结果/B10方法选择-v1/factor_analysis/actual_error_quartile_contrasts.csv)、[四点曲线](结果/B10方法选择-v1/factor_analysis/actual_error_quartile_curves.csv)、[程序](程序/b10_factor_quantification.py)、[补充方案](B10方法选择-误差因素量化方案-v1.0.md)。',
        '',
        '解释依据：[模型依赖与变量重要性](https://jmlr.org/beta/papers/v20/18-760.html)，[相关特征会共享重要性](https://scikit-learn.org/stable/auto_examples/inspection/plot_permutation_importance_multicollinear.html)。当前使用删除组后重新训练，未把不同特征随意置零当作删除。',
    ]
    (STUDY/'B10方法选择-误差因素量化补充-v1.0.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Factor quantification figure and report saved.')


if __name__=='__main__':
    main()
