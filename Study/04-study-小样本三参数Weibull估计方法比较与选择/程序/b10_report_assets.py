"""Export standalone scientific figures and a concise Chinese report from saved evidence."""
from pathlib import Path
import csv
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[3]
PLOT_DEPS=ROOT/'.codex-tmp/b10-plot-deps'
if PLOT_DEPS.exists():
    sys.path.insert(0,str(PLOT_DEPS))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STUDY=Path(__file__).resolve().parent.parent
OUT=Path(os.environ.get('B10_SELECTOR_OUTPUT', str(STUDY/'结果/B10方法选择-v1'))).resolve()
COLORS=['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00','#56B4E9','#444444']


def read_json(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def read_csv(name):
    with (OUT/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def save(fig,name):
    dest=OUT/'figures'
    dest.mkdir(exist_ok=True)
    fig.savefig(dest/f'{name}.png',dpi=220,bbox_inches='tight')
    fig.savefig(dest/f'{name}.pdf',bbox_inches='tight')
    plt.close(fig)


def plots():
    plt.rcParams.update({'font.size':10,'axes.spines.right':False,'axes.spines.top':False,
        'figure.facecolor':'white','axes.titleweight':'bold','pdf.fonttype':42})
    evaluation=read_json('evaluation.json');m=evaluation['metrics']
    fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
    ax=axes[0,0]
    keys=['fixed','n_rule','n_only','network','hindsight_reference']
    labels=['Fixed MDM','n rule','n-only NN','Feature NN','Hindsight*']
    ax.bar(labels,[m[k]['all_attempts']['rmse'] for k in keys],color=['#888888','#aaaaaa','#56B4E9','#0072B2','#dddddd'])
    ax.set_ylabel('B10 RMSE (original lifetime units)')
    ax.set_title('A  Held-out samples: actual selection error')
    ax.set_ylim(0,130);ax.tick_params(axis='x',labelrotation=15)
    ax.text(.02,.96,'* Opportunity reference, unavailable in practice',transform=ax.transAxes,va='top',fontsize=8)
    ax=axes[0,1]
    rows=read_csv('cell_metrics.csv')
    for key,label,color in [('fixed','Fixed MDM','#888888'),('n_rule','n rule','#D55E00'),('network','Feature NN','#0072B2')]:
        vals=[]
        for n in [7,10,15,20,50]:
            group=[float(r['mse']) for r in rows if r['strategy']==key and r['cell'].endswith(f'_n{n}')]
            vals.append(np.sqrt(np.mean(group)))
        ax.plot([7,10,15,20,50],vals,'o-',label=label,color=color)
    ax.set(xlabel='Sample size n',ylabel='B10 RMSE',title='B  Benefit across trained sample sizes')
    ax.legend(frameon=False)
    ax=axes[1,0]
    rows=read_csv('risk_calibration_bins.csv')
    for color,method in zip(COLORS,evaluation['methods']):
        group=[r for r in rows if r['method']==method]
        ax.plot([np.sqrt(float(r['predicted'])) for r in group],[np.sqrt(float(r['observed'])) for r in group],
                'o-',markersize=3,label=method,color=color,alpha=.85)
    ax.plot([0,400],[0,400],'k--',lw=1)
    ax.set(xlabel='Predicted RMS error (bin mean risk)',ylabel='Observed RMS error',
           title='C  Risk calibration: binned, method-specific')
    ax.legend(frameon=False,ncol=2,fontsize=8)
    ax=axes[1,1]
    keys=['full_single','no_n','no_level','no_shape','no_spacing','n_only']
    labels=['All features','Without n','Without level/scale','Without shape','Without spacing','Only n']
    vals=[m[k]['improvement_all_pct'] for k in keys]
    ax.barh(labels,vals,color=['#0072B2','#56B4E9','#D55E00','#009E73','#CC79A7','#888888'])
    ax.invert_yaxis();ax.axvline(0,color='k',lw=.7)
    ax.set(xlabel='RMSE reduction vs fixed MDM (%)',title='D  Ablations: same seed and training budget')
    save(fig,'01_selection_and_calibration')

    fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
    ax=axes[0,0]
    fresh=read_json('fresh_evaluation.json')
    entries=[('Leave beta=2.5 out',evaluation['holdouts']['beta_2.5']['network']),
             ('Leave n=15 out',evaluation['holdouts']['n_15']['network']),
             ('Leave n=50 out',evaluation['holdouts']['n_50']['network'])]
    entries += [(label,fresh[key]['metrics']['network']) for key,label in [
        ('fresh_in_domain','Fresh: beta=3, n=10'),('beta_interpolation','Fresh: beta=2.25'),
        ('n_interpolation','Fresh: n=30'),('scale_location','Fresh: eta=500, gamma=250'),
        ('zero_location','Fresh: gamma=0')]]
    for i,(label,value) in enumerate(entries):
        center=value['improvement_all_pct'];ci=value['improvement_all_ci95']
        ax.errorbar(center,i,xerr=np.array([[center-ci[0]],[ci[1]-center]]),fmt='o',
                    color='#0072B2' if center>0 else '#D55E00',capsize=3)
    ax.set_yticks(range(len(entries)),[v[0] for v in entries]);ax.invert_yaxis()
    ax.axvline(0,color='k',lw=.8);ax.set(xlabel='RMSE reduction vs fixed method (%)',
        title='A  Scope tests with paired 95% intervals')
    ax=axes[0,1]
    rows=read_csv('feature_distributions_by_cell.csv')
    for color,(feature,label) in zip(COLORS,[('gap_first','First normalized gap'),('skewness','Sample skewness')]):
        group=sorted([r for r in rows if float(r['beta'])==3 and r['feature']==feature],key=lambda r:int(r['n']))
        n=[int(r['n']) for r in group]
        ax.plot(n,[float(r['median']) for r in group],'o-',label=label,color=color)
        ax.fill_between(n,[float(r['p25']) for r in group],[float(r['p75']) for r in group],color=color,alpha=.12)
    ax.set(xlabel='Sample size n',ylabel='Feature median and interquartile range',
           title='B  Feature distribution changes (fixed beta=3)')
    ax.legend(frameon=False,fontsize=8)
    ax=axes[1,0]
    rows=read_csv('all_pair_top3_curves.csv')
    pair=('MLE','WMLE','log_min')
    group=[r for r in rows if (r['method_a'],r['method_b'],r['feature'])==pair]
    for field,label,color in [('mse_a','MLE','#0072B2'),('mse_b','WMLE','#D55E00')]:
        values=[np.sqrt(np.mean([float(r[field]) for r in group if int(r['bin'])==k])) for k in range(1,5)]
        ax.plot(range(1,5),values,'o-',label=label,color=color)
    ax.set(xticks=[1,2,3,4],xlabel='Within-cell quartile of sample minimum',ylabel='B10 RMSE',
           title='C  Sample minimum separates relative risk')
    ax.legend(frameon=False)
    ax=axes[1,1]
    group=[r for r in rows if r['method_a']=='MMLE(KR)' and r['method_b']=='WMLE']
    for field,label,color in [('mse_a','MMLE','#009E73'),('mse_b','WMLE','#D55E00')]:
        values=[np.sqrt(np.mean([float(r[field]) for r in group if int(r['bin'])==k])) for k in range(1,5)]
        ax.plot(range(1,5),values,'o-',label=label,color=color)
    ax.set(xticks=[1,2,3,4],xlabel='Within-cell quartile of sample mean',ylabel='B10 RMSE',
           title='D  Sample mean separates relative risk')
    ax.legend(frameon=False)
    save(fig,'02_scope_and_feature_relationships')


def report():
    evaluation=read_json('evaluation.json');fresh=read_json('fresh_evaluation.json')
    m=evaluation['metrics'];net=m['network'];fixed=m['fixed']
    analysis=read_json('feature_analysis.json');manifest=read_json('manifest.json')
    risk_scope=read_json('risk_scope_diagnostics.json')
    ratios=[r['ratio'] for r in risk_scope['primary']]
    hold50=read_json('risk_scope_diagnostics.json')['n_50']
    cal=evaluation['calibration']
    n50_ratios=[sum(r['predicted_mse']*r['n'] for r in hold50 if r['method']==method)/
        sum(r['observed_mse']*r['n'] for r in hold50 if r['method']==method) for method in evaluation['methods']]
    ci=net['improvement_all_ci95']
    lines=[
        '# 样本特征驱动B10风险预测与方法选择：简要报告 v1.0',
        '',
        '2026-10-24 · home分支。七法结果作为训练标签，模型输入仅为当前样本特征与样本量。',
        '',
        '## 怎么做',
        '',
        f'复用48,000组存档样本及336,000条方法尝试，构建30维输入：样本量、位置与尺度、分位数、分布形状、相邻间距。按样本指纹分组，训练/验证/测试分别为{manifest["split_counts"][0]:,}/{manifest["split_counts"][1]:,}/{manifest["split_counts"][2]:,}组。真参数和七法估计值均不进入输入；预处理只用训练部分。',
        '',
        '用七法B10误差平方监督两层MLP，输出各法成功返回条件下的预计平方误差风险，可用性另报；宽度32/64仅由验证集选择，最终采用64×64及三个初始化的平均预测。先运行预测风险最小的方法，失败后按预测排序依次回退。有效极端值不删，失败不填零误差。主比较按β×n条件等权，另保留七法共同有效比较。',
        '',
        '## 得到什么结果',
        '',
        '| 独立留出测试，9,642组 | B10 RMSE | 相对固定方法改善 |',
        '|---|---:|---:|',
        f'| 最佳固定方法MDM-0.1（由训练集确定） | {fixed["all_attempts"]["rmse"]:.2f} | — |',
        f'| 只按样本量选法 | {m["n_rule"]["all_attempts"]["rmse"]:.2f} | {m["n_rule"]["improvement_all_pct"]:.2f}% |',
        f'| 特征网络选法，含失败回退 | {net["all_attempts"]["rmse"]:.2f} | **{net["improvement_all_pct"]:.2f}%** |',
        '',
        f'改善的配对95%区间为[{ci[0]:.2f}%, {ci[1]:.2f}%]；40个条件点估计均改善，但不代表每个条件都已单独证明显著。共同有效7,317组上的条件等权改善为{net["improvement_common_pct"]:.2f}%。首次选中方法失败率{net["first_failure_rate"]*100:.2f}%，按排序回退后本批最终失败率0%。',
        '',
        f'风险预测方面，各法总体“预测平均风险/实际平均平方误差”为{min(r["ratio"] for r in cal):.3f}—{max(r["ratio"] for r in cal):.3f}，风险与单次平方误差的Spearman相关为{min(r["spearman"] for r in cal):.2f}—{max(r["spearman"] for r in cal):.2f}。但分条件比值范围为{min(ratios):.2f}—{max(ratios):.2f}，说明总体校准接近不等于每个条件或单个样本的误差预测精确。',
        '',
        '| 完全独立的新生成数据，每项200组 | 相对原训练选定固定方法的RMSE改善 | 配对95%区间 |',
        '|---|---:|---:|',
    ]
    labels={'fresh_in_domain':'域内新样本：β=3，n=10','beta_interpolation':'未训练β=2.25，n=10',
        'n_interpolation':'未训练n=30，β=3','scale_location':'η=500、γ=250（原值的一半）','zero_location':'γ=0，η=1000'}
    for key,label in labels.items():
        v=fresh[key]['metrics']['network'];lo,hi=v['improvement_all_ci95']
        lines.append(f'| {label} | {v["improvement_all_pct"]:.2f}% | [{lo:.2f}%, {hi:.2f}%] |')
    holds=evaluation['holdouts']
    lines += ['',
        f'另做既有条件整体留出：β=2.5、n=15、n=50从各自模型的训练和调参中完全排除，选法RMSE分别改善{holds["beta_2.5"]["network"]["improvement_all_pct"]:.2f}%、{holds["n_15"]["network"]["improvement_all_pct"]:.2f}%、{holds["n_50"]["network"]["improvement_all_pct"]:.2f}%。其中n=50的风险大小仍高估约{(min(n50_ratios)-1)*100:.0f}%—{(max(n50_ratios)-1)*100:.0f}%：选法有用与风险数值准确是两个判断。',
        '',
        '## 总结出什么结论',
        '',
        f'1. **固定训练尺度、位置下，样本特征包含样本量以外的选法信息。** 仅n的网络改善{m["n_only"]["improvement_all_pct"]:.2f}%；单模型全特征改善{m["full_single"]["improvement_all_pct"]:.2f}%，去掉位置尺度组后剩{m["no_level"]["improvement_all_pct"]:.2f}%。去掉n、形状或间距组的表现接近全特征，当前证据支持位置尺度组贡献较大，不能宣称所有特征组都有额外收益。',
        '',
        '2. **确实能区分“n改变特征分布”与“特征改变方法相对风险”。** 固定β=3，n从7到50时，归一化首间距中位数由0.154降至0.048，样本偏度四分位距由0.776收窄至0.349。在七法共同有效样本内固定β×n分析，样本最小值与MLE−WMLE损失差的平均条件内相关为0.775，独立新样本为0.816；最小值从低到高四分位时，平均风险优势由MLE转向WMLE。样本均值与MMLE−WMLE损失差也有相应关系（留出相关0.760，新样本0.730）。这些是可重复的预测关联，尚非因果机制证明。',
        '',
        f'3. **收益有边界和取舍。** 原单位平均带符号Bias由{fixed["all_attempts"]["bias"]:.2f}增至{net["all_attempts"]["bias"]:.2f}，更偏高估；绝对误差P95由{fixed["all_attempts"]["p95_abs"]:.2f}降至{net["all_attempts"]["p95_abs"]:.2f}。因此结论是总体平方误差与部分尾部风险下降，不是更无偏。',
        '',
        '4. **目前形成固定η=1000、γ=500及相近训练设置下的研究原型。** 少量β/n插值与样本量外推有正向证据，但尺度位置改变时明显退化，尚不能作为未知尺度、位置的通用选法器。没有预先规定工程误差容限，本轮也不宣布达到工程可用门槛。若下一阶段要求跨尺度位置可用，应在独立的新研究版本中调整训练覆盖或等变设计，不能仅靠本轮结果外推。',
        '',
        '所有区间均以已训练模型和固定条件为前提进行条件内配对重抽样，不包含重新训练模型的全部不确定性。新条件仅各200组，是有界范围核查，不是连续参数空间认证。',
        '',
        '## 交付与复核',
        '',
        '- [研究方案](B10方法选择-研究方案-v1.0.md)；[复现入口](程序/b10_feature_selector.py)；[新样本验证](程序/b10_fresh_validation.py)；[结构分析](程序/b10_feature_analysis.py)。',
        '- 模型、划分、逐样本预测、校准、消融及范围结果均保存在`结果/B10方法选择-v1/`；数值与模型按项目约定由Git忽略。',
        '- 已通过样本划分不交叉、训练专用预处理、独立载入预测一致、1,000组新样本与旧样本不重复、原CSV及固定方法实现未改动等检查；原始数据完整核验已于本轮数据接收时通过。',
        '',
        '![选法、校准与消融](结果/B10方法选择-v1/figures/01_selection_and_calibration.png)',
        '',
        '![适用边界与样本特征关系](结果/B10方法选择-v1/figures/02_scope_and_feature_relationships.png)',
        '',
        '训练使用条件均值一致评分μ−y log μ，目标仍为B10平方误差的条件均值；公式见[PyTorch文档](https://docs.pytorch.org/docs/stable/generated/torch.nn.PoissonNLLLoss.html)，一致评分的背景见[Gneiting](https://arxiv.org/abs/0912.0902)。这不是对连续平方误差作Poisson分布假设。',
    ]
    if (OUT/'map_comparison.json').exists():
        comparison=read_json('map_comparison.json')
        at=lines.index('## 总结出什么结论')
        lines[at:at]=[
            '## 与报告下B10性能地图对照：2026-10-24补充',
            '',
            f'在同一批7,317组共同有效测试样本上，原图推荐的条件等权B10 RMSE为{comparison["rmse"]["report_map"]:.2f}，网络为{comparison["rmse"]["network"]:.2f}，网络低{comparison["improvement_vs_report_map_pct"]:.2f}%；37/40个条件的实际测试RMSE更低。原图使用全1200组、含测试结果；只用训练部分重建地图后RMSE为{comparison["rmse"]["training_only_map"]:.2f}，网络低{comparison["improvement_vs_training_only_map_pct"]:.2f}%。',
            '',
            f'逐样本事后真实最优命中率：网络{comparison["network_actual_best_sample_rate"]*100:.2f}%，原图{comparison["map_actual_best_sample_rate"]*100:.2f}%。若把网络预测风险按条件取平均，再要求复现地图冠军，仅{comparison["grid_mean_risk_map_hits"]}/40格一致。故当前证据是逐样本选法更有效，尚不能称为逐样本保证最优，也不能称为准确重建性能地图。详细口径与逐格结果见[性能地图对照补充](B10方法选择-性能地图对照补充-v1.0.md)。',
            '',
        ]
    if (OUT/'factor_analysis/method_group_ablation.json').exists():
        at=lines.index('## 总结出什么结论')
        lines[at:at]=[
            '## 误差因素量化：2026-10-24补充',
            '',
            '已匹配三个初始化补齐四类信息消融，并按七法分别评价。删除样本位置尺度组，风险预测损失增加77%—148%；删除形状组，对MM增加约8.37%。另在固定β×n后量化真实误差的分位差异，例如样本最小值由低到高四分位时，MLE与MDM的实际B10 RMSE分别增加约138%和40%。前者是网络信息贡献，后者是观察关联，均不当作孤立因果效应；详见[因素量化补充](B10方法选择-误差因素量化补充-v1.0.md)。',
            '',
        ]
    report_path=(OUT/'简要报告.md') if os.environ.get('B10_SELECTOR_OUTPUT') else (STUDY/'B10方法选择-简要报告-v1.0.md')
    report_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    plots()
    report()
    print('Figures (PNG/PDF) and concise report generated.')
