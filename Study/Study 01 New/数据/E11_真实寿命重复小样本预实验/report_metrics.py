"""Report full prespecified metric scan and focused lower-tail evidence.

Python quantitative grid: every scanned quantile shown, no negative clipping.
Colors encode n; pointwise intervals are conditional Monte Carlo intervals only.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_pilot import HERE,sha,write_json

OUT=HERE/'指标与跨案例探索'
NAMES={'fatigue101':'铝合金疲劳寿命（101个）','rotor20':'转子寿命（20个）','bearing23':'轴承寿命（23个）'}
PS=[.01,.05,.1,.2,.5,.8,.9,.95,.99]


def main():
    assert json.loads((OUT/'verification.json').read_text(encoding='utf8'))['status']=='passed'
    assert json.loads((OUT/'极端观测敏感性/verification.json').read_text(encoding='utf8'))['status']=='passed'
    real=pd.read_csv(OUT/'real_comparison.csv')
    sim=pd.read_csv(OUT/'sim_comparison.csv')
    sensitivity=pd.read_csv(OUT/'极端观测敏感性/comparison.csv')
    r=real[real.comparator=='MDM-0.1'];s=sim[sim.comparator=='MDM-0.1']
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,
        'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,3,figsize=(200/25.4,128/25.4),sharex=True,sharey=True)
    fig.subplots_adjust(left=.085,right=.985,bottom=.14,top=.9,wspace=.16,hspace=.32)
    for col,case in enumerate(NAMES):
        for row,n in enumerate([7,10]):
            ax=axes[row,col]
            g=r[(r.case==case)&(r.n==n)].set_index('metric').loc[[f'pinball_{p:g}' for p in PS]]
            color='#436F91' if n==7 else '#B88755'
            ax.fill_between(np.arange(9),g.conditional_lo95,g.conditional_hi95,color=color,alpha=.18,linewidth=0)
            ax.plot(np.arange(9),g.gain_percent,color=color,lw=1.5,marker='o',markersize=3)
            ax.axhline(0,color='#78838B',ls='--',lw=.7)
            ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
            ax.set_title(f'({chr(97+row*3+col)}) n = {n}',loc='left',fontsize=9)
            if row==0:ax.text(.5,1.22,NAMES[case],transform=ax.transAxes,ha='center',fontsize=8)
            ax.set_xticks(np.arange(9),['1','5','10','20','50','80','90','95','99'],rotation=45,fontsize=6.5)
            if col==0:ax.set_ylabel('分位点损失降幅（%）')
            if row==1:ax.set_xlabel('失效概率 p（%）')
    for ext in ['png','svg','pdf']:
        fig.savefig(OUT/f'P11_全分位点跨案例比较.{ext}',dpi=350,facecolor='white')
    plt.close(fig)
    # Save a compact table gathering low-tail evidence without dropping other metrics.
    focus=[]
    for p in [.01,.05,.1]:
        for n in [7,10,15,20]:
            a=r[(r.case=='fatigue101')&(r.n==n)&(r.metric==f'pinball_{p:g}')].iloc[0]
            row=dict(n=n,p=p,real_gain=a.gain_percent,real_lo=a.conditional_lo95,real_hi=a.conditional_hi95)
            for c in ['sim_MLE_anchor','sim_MDM_anchor']:
                z=s[(s.case==c)&(s.n==n)&(s.metric==f'mse_q{p:g}')].iloc[0]
                row[c+'_RMSE_gain']=z.gain_percent
            for drop in ['drop_min','drop_max']:
                row[drop+'_gain']=sensitivity[(sensitivity['drop']==drop)&(sensitivity.n==n)&(sensitivity.metric==f'pinball_{p:g}')].gain_percent.iloc[0]
            focus.append(row)
    pd.DataFrame(focus).to_csv(OUT/'lower_tail_evidence.csv',index=False)
    # Calibration reported separately from proper-score gains.
    scores=pd.read_csv(OUT/'real_scores.csv.gz',low_memory=False)
    common_rows=[]
    methods=['AMDM','MDM-0.1','WMLE','MLE','LSE','LRE']
    for (case,n),g in scores.groupby(['case','n']):
        counts=g.groupby('repeat').method.nunique()
        common=g[g.repeat.isin(counts[counts==len(methods)].index)]
        for metric in ['crps']+[f'pinball_{p:g}' for p in PS]:
            means=common.groupby('method')[metric].mean()
            for method in methods:
                common_rows.append(dict(case=case,n=n,metric=metric,method=method,
                    common_count=int((counts==len(methods)).sum()),mean_score=means[method],
                    AMDM_gain_percent=100*(1-means['AMDM']/means[method])))
    pd.DataFrame(common_rows).to_csv(OUT/'six_method_common_comparison.csv',index=False)
    calibration=[]
    for (case,n,m),g in scores.groupby(['case','n','method']):
        for p in [.01,.05,.1]:
            calibration.append(dict(case=case,n=n,method=m,p=p,
                observed_fraction_below_prediction=g[f'coverage_{p:g}'].mean(),count=len(g)))
    pd.DataFrame(calibration).to_csv(OUT/'calibration.csv',index=False)
    # Bias/dispersion decomposition only where generating parameters are known.
    simrows=pd.read_csv(OUT/'simulation_scores.csv.gz')
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf8'))
    anchors={'sim_MLE_anchor':pd.read_csv(HERE/'reference_fits.csv')[['beta_hat','eta_hat','gamma_hat']].iloc[0].to_numpy(),
        'sim_MDM_anchor':np.array(protocol['simulation_anchor_MDM'])}
    decomposition=[]
    for (case,n,m),g in simrows.groupby(['case','n','method']):
        theta=anchors[case]
        for p in [.01,.05,.1]:
            q=g.gamma_hat+g.eta_hat*(-np.log1p(-p))**(1/g.beta_hat)
            truth=theta[2]+theta[1]*(-np.log1p(-p))**(1/theta[0])
            err=(q-truth)/theta[1]
            decomposition.append(dict(case=case,n=n,method=m,p=p,bias=err.mean(),sd=err.std(ddof=0),rmse=np.sqrt(np.mean(err**2))))
    pd.DataFrame(decomposition).to_csv(OUT/'known_truth_quantile_bias_sd.csv',index=False)
    # Post-discovery check of all nine quantiles in the existing E09 design.
    # These already inspected tests are reused evidence, not fresh confirmation.
    e09_path=HERE.parent/'E09_六方法共同测试/per_sample.csv.gz'
    e09_sha=sha(e09_path)
    e09=pd.read_csv(e09_path)
    e09=e09[e09.method.isin(['AMDM','MDM-0.1'])].copy()
    assert e09.valid.all() and len(e09)==9600
    e09_cells=[];e09_summary=[]
    for n,g in e09.groupby('n'):
        am=[];ba=[]
        for cell,h in g.groupby('cell_id'):
            a=h[h.method=='AMDM'].sort_values('repeat_id')
            b=h[h.method=='MDM-0.1'].sort_values('repeat_id')
            assert len(a)==len(b)==100 and np.array_equal(a.sample_sha256,b.sample_sha256)
            truth=a.gamma.to_numpy()[:,None]+a.eta.to_numpy()[:,None]*(-np.log1p(-np.array(PS)))**(1/a.beta.to_numpy()[:,None])
            mse=[]
            for frame in [a,b]:
                q=frame.gamma_hat.to_numpy()[:,None]+frame.eta_hat.to_numpy()[:,None]*(-np.log1p(-np.array(PS)))**(1/frame.beta_hat.to_numpy()[:,None])
                mse.append(((q-truth)/a.eta.to_numpy()[:,None])**2)
            am.append(mse[0]);ba.append(mse[1])
            for j,p in enumerate(PS):
                e09_cells.append(dict(n=n,cell_id=cell,beta=a.beta.iloc[0],gamma_over_eta=a.gamma_over_eta.iloc[0],p=p,
                    amdm_RMSE=np.sqrt(mse[0][:,j].mean()),mdm_RMSE=np.sqrt(mse[1][:,j].mean()),
                    gain_percent=100*(1-np.sqrt(mse[0][:,j].mean()/mse[1][:,j].mean()))))
        av=np.array(am);bv=np.array(ba)
        rng=np.random.default_rng(2026092530+int(n));drawa=0.;drawb=0.
        for ac,bc in zip(av,bv):
            counts=rng.multinomial(100,np.full(100,.01),size=2000)
            drawa=drawa+counts@ac;drawb=drawb+counts@bc
        lo,hi=np.quantile(100*(1-np.sqrt(drawa/drawb)),[.025,.975],axis=0)
        for j,p in enumerate(PS):
            e09_summary.append(dict(n=n,p=p,amdm_RMSE=np.sqrt(av[:,:,j].mean()),mdm_RMSE=np.sqrt(bv[:,:,j].mean()),
                gain_percent=100*(1-np.sqrt(av[:,:,j].mean()/bv[:,:,j].mean())),lo95=lo[j],hi95=hi[j]))
    pd.DataFrame(e09_cells).to_csv(OUT/'existing_E09_quantile_by_cell.csv',index=False)
    pd.DataFrame(e09_summary).to_csv(OUT/'existing_E09_quantile_by_n.csv',index=False)
    assert sha(e09_path)==e09_sha
    lines=['# E11 指标与跨案例探索','',
        '状态：探索性评价。候选指标、案例、随机种子在本轮评分前固定；低尾优势出现后追加最小/最大观测剔除敏感性。不将探索中选出的指标称为事先设定的论文主终点。','',
        '## 本轮判断','',
        '**目前最值得继续发展的目标是低失效概率寿命点B1、B5。** 它们对应估计分布中1%、5%失效概率的寿命，即名义99%、95%可靠度寿命。这个应用目标把三参数改进连接到一个明确的可靠性量，且不需要把全样本某种方法的拟合当作真实答案。','',
        '在101个疲劳寿命上，AMDM相对固定MDM的B1留出分位点损失下降2.41%—7.36%，B5下降0.65%—2.04%；四档样本量均为正。前后两半抽样分别汇总后仍为正，去掉最小值或最大值后重新抽样、重新估计也保留该方向。这些检查支持该案例内的稳定性，不增加独立真实案例数。','',
        '已知真值方面，两个匹配Weibull总体中B1/B5的RMSE均下降；已有E09全部48条件的复核也得到B1 RMSE下降3.37%—6.11%、B5下降0.76%—2.59%。因此，这一发现不仅来自换一种真实数据评分，也得到真值可知条件下的误差结果支持。E09是已用过的测试数据，本次只是新增指标分析。','',
        '**尚不能写成普遍真实数据优势。** 新增轴承案例的B1/B5有小幅改善，但转子案例n=7的低尾得分变差；疲劳案例的上尾分位点也有退步。CRPS整体分布得分基本持平。六方法共同成功集合上，疲劳B1/B5得分优于固定MDM、MLE、WMLE和LSE，但未超过LRE；完整数值与失败率均保留。','',
        '**建议的后续方向：** 保持论文的参数估计主线，把B5作为下一次独立真实案例检验的主要工程目标、B1作为辅助目标，提前固定评价方案，在有足够原始观测的新数据上确认。B1当前相对改善更大，但101个观测只能提供很有限的1%尾部信息，不能因数值更亮眼就把它直接升级为普遍可靠度保证。当前结果可作为“疲劳案例中低尾寿命预测改善”的探索性证据，不据此改写为“真实三参数估计已经证实更准”。','',
        '## 本轮问题与范围','',
        '寻找AMDM相对固定δ=0.1 MDM在哪些具有明确应用意义的目标上确有改善，并检查这种改善是否由单次抽样、个别极端观测或单一模拟参数参照造成。','',
        '- 既有真实数据：101个铝合金疲劳寿命，n=7、10、15、20，每档2,000次留出评价，保留六方法。',
        '- 新真实案例：20个转子寿命、23个轴承寿命，各取n=7、10，每档1,000次，共24,000条六方法估计。',
        '- 已知真值：复用全样本MLE拟合参数对应的Weibull模拟；新增以全样本固定MDM拟合参数为生成参数的模拟，四档各2,000次、两方法共16,000条新估计。拟合值只有在作为模拟生成参数时才是真值，不能回称真实数据的真参数。',
        '- 极端观测敏感性：分别移除101个观测中的最小值370、最大值2440，重新抽取、重新估计，并在剩余观测上评价；四档各1,000次，两方法共16,000条新估计。','',
        '共新增56,000条估计。未重新训练AMDM、未改变模型、未删除原数据或未获益指标。','',
        '发现低尾方向后，另复核已有E09的4,800组共同测试：沿用全部48个条件和九个分位点，直接计算已知真值下的分位点RMSE。该复核没有新增估计，也不作为独立确认。','',
        '## 指标为什么有意义','',
        '| 指标 | 回答的问题 | 判定 |','|---|---|---|',
        '| 分位点损失（pinball） | 预测的B1、B5、B10等寿命点能否描述留出观测 | 越小越好；B1/B5/B10对应1%/5%/10%失效概率 |',
        '| CRPS | 整个寿命分布的预测表现 | 越小越好，保留为总体参照 |',
        '| 80%/90%区间得分 | 区间宽度与漏覆盖代价的综合表现 | 越小越好，不只奖励窄区间 |',
        '| 固定寿命阈值Brier得分 | 到指定寿命前是否失效的概率预测 | 越小越好，阈值在本轮评分前固定 |',
        '| 已知真值下参数/分位点RMSE | 模拟中估计是否更接近生成真值 | 越小越好，仅用于模拟 |',
        '',r'分位点损失：$\rho_p(y-q)=\max\{p(y-q),(p-1)(y-q)\}$。',
        '', '参考：[Gneiting与Raftery（2007）](https://doi.org/10.1198/016214506000001437)。1%—99%的九个分位点全部保留，极低概率点的真实验证受原始样本量限制。','',
        '## 全分位点结果','',
        '![全分位点跨案例比较](P11_全分位点跨案例比较.png)','',
        '正值为AMDM相对固定MDM的平均分位点损失下降。横轴列出预设概率点，等距排列是分类坐标。阴影为条件于固定观测池和冻结模型的逐点95%配对Monte Carlo重抽样区间，不是总体置信区间，也没有对多指标搜索作显著性校正。重复抽样增加的是数值精度，不增加原始独立试件数。','',
        '## 101个疲劳寿命的低尾结果','',
        '| p | n | 真实留出损失降幅 | 删除最小值后 | 删除最大值后 | MLE参照模拟RMSE降幅 | MDM参照模拟RMSE降幅 |',
        '|---:|---:|---:|---:|---:|---:|---:|']
    for row in focus:
        lines.append(f'| {row["p"]:.0%} | {row["n"]} | {row["real_gain"]:+.2f}% | {row["drop_min_gain"]:+.2f}% | {row["drop_max_gain"]:+.2f}% | {row["sim_MLE_anchor_RMSE_gain"]:+.2f}% | {row["sim_MDM_anchor_RMSE_gain"]:+.2f}% |')
    lines+=['','## 原主体参数域的复核','',
        '在既有E09全部条件内重新汇总分位点RMSE：各条件等权，条件内AMDM与固定MDM配对；区间采用2,000次条件内配对重抽样。所有九个分位点结果见CSV，以下摘出与当前低尾发现对应的B1/B5。','',
        '| n | B1 RMSE降幅 | B5 RMSE降幅 |','|---:|---:|---:|']
    eg=pd.DataFrame(e09_summary)
    for n in [7,10,15,20]:
        g=eg[eg.n==n].set_index('p')
        lines.append(f'| {n} | {g.loc[.01,"gain_percent"]:+.2f}% | {g.loc[.05,"gain_percent"]:+.2f}% |')
    lines+=['','## 新案例交叉检查','',
        '| 案例 | n | B1损失降幅 | B5损失降幅 | B10损失降幅 | CRPS降幅 |','|---|---:|---:|---:|---:|---:|']
    for case in ['rotor20','bearing23']:
        for n in [7,10]:
            g=r[(r.case==case)&(r.n==n)].set_index('metric')
            lines.append(f'| {NAMES[case]} | {n} | '+' | '.join(f'{g.loc[m,"gain_percent"]:+.2f}%' for m in ['pinball_0.01','pinball_0.05','pinball_0.1','crps'])+' |')
    lines+=['','两个新增案例在本轮计算前选定，均报告结果。它们来自前一轮读到的文献，不是从大量数据集跑分后择优挑选；但每个案例的独立原始观测仅20/23个，尤其不足以充分验证1%尾部。','',
        '## 改善的误差构成','',
        '在两个匹配Weibull模拟的n=7条件下，AMDM的B1标准化偏差略增，但抽样标准差下降约12%—13%，最终RMSE下降约6%。这说明此处收益主要体现在对抽样波动的抑制，并非每个样本都更接近真值；完整偏差/标准差/RMSE分解见CSV。该解释仅针对这两个模拟条件，不据此推断真实总体的偏差。','',
        '## 99%可靠度寿命与99%可靠度保证的区别','',
        'B1是估计模型中对应1%失效概率的寿命点。其留出分位点损失下降，表示针对该寿命点的预测得分改善，不自动表示真实失效比例已经达到1%。下表检查实际留出观测落在预测B1以下的平均比例。','',
        '| n | AMDM | 固定MDM | 名义比例 |','|---:|---:|---:|---:|']
    cal=pd.DataFrame(calibration)
    for n in [7,10,15,20]:
        g=cal[(cal.case=='fatigue101')&(cal.n==n)&(cal.p==.01)].set_index('method')
        lines.append(f'| {n} | {g.loc["AMDM","observed_fraction_below_prediction"]:.2%} | {g.loc["MDM-0.1","observed_fraction_below_prediction"]:.2%} | 1% |')
    lines+=['','## 完整结果与复现','',
        '- [全部真实指标与五个对照的配对结果](real_comparison.csv)：含逐点条件区间及前后半批次结果。',
        '- [六方法共同成功抽样的比较](six_method_common_comparison.csv)：CRPS及九个分位点使用统一抽样集合，成功率另报。',
        '- [已知真值模拟结果](sim_comparison.csv)、[分位点偏差与离散分解](known_truth_quantile_bias_sd.csv)。',
        '- [已有E09全分位点复核](existing_E09_quantile_by_n.csv)、[各参数条件结果](existing_E09_quantile_by_cell.csv)。',
        '- [极端观测剔除结果](极端观测敏感性/comparison.csv)、[极端观测是否进入估计样本的分层诊断](extreme_inclusion_sensitivity.csv)。',
        '- [求解成功率](success_rates.csv)、[校准诊断](calibration.csv)、[低尾证据汇总](lower_tail_evidence.csv)。',
        '- [冻结配置与来源哈希](protocol.json)、[数据](cases.json)、[核验](verification.json)。',
        '- [计算程序](../explore_metrics.py)、[端点敏感性程序](../tail_sensitivity.py)、[汇总绘图程序](../report_metrics.py)。','',
        '文献来源：[182-047，第4.1节](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-047-pdf原文.md:199>)；[182-050，第5.2节及表9](<D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-050-pdf原文.md:305>)。','',
        '所有真实比较使用每对方法共同成功的抽样，失败另记；不能将不同配对集合的均值混成统一排名。完整指标表包含未改善结果，不以数据探索结果修改冻结模型或主论文结论。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    write_json(OUT/'figure_manifest.json',dict(backend='Python',size_mm=[200,128],archetype='quantitative grid',
        claim='map the full lower-to-upper quantile score changes across three real cases',
        data_sha=sha(OUT/'real_comparison.csv'),script_sha=sha(Path(__file__)),
        reused_E09_source_sha=e09_sha,
        interval='pointwise conditional bootstrap, exploratory',negative_values_retained=True))
    print(pd.DataFrame(focus).round(3).to_string(index=False))


if __name__=='__main__':main()
