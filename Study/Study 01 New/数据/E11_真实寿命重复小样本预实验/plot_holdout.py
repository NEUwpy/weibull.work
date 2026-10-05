"""Four-panel holdout CRPS comparison, matched successful splits.

Figure contract: compare predictive score distributions without assuming a winner.
Quantitative grid, n=7/10/15/20, Python; 200 x 150 mm, editable SVG/PDF and PNG.
Violins: full-range density, IQR and median; diamonds: means.
Fixed method order, a shared focus window and full-range overview clarify score differences.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_pilot import HERE, NS, METHODS, sha, write_json

OUT=HERE/'留出预测评价'
COLORS=['#436F91','#659B89','#B88755','#7B7B86','#AB8097','#8D9CBE']
LABELS=['AMDM','MDM','WMLE','MLE','LSE','LRE']


def main():
    assert json.loads((OUT/'verification.json').read_text(encoding='utf8'))['status']=='passed'
    common=pd.read_csv(OUT/'common_scores.csv.gz')
    summary=pd.read_csv(OUT/'summary.csv')
    pairs=pd.read_csv(OUT/'paired_comparison.csv')
    counts=pd.read_csv(OUT/'common_counts.csv').set_index('n')
    input_paths=[OUT/x for x in ['common_scores.csv.gz','summary.csv','paired_comparison.csv',
                               'common_counts.csv','per_subsample.csv.gz','protocol.json']]
    before={str(p):sha(p) for p in input_paths}
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,
        'axes.linewidth':.65,'axes.spines.top':False,'axes.spines.right':False})
    # Keep the original method order and magnify the central score region.
    color_map=dict(zip(METHODS,COLORS));label_map=dict(zip(METHODS,LABELS))
    fig=plt.figure(figsize=(200/25.4,150/25.4))
    outer=fig.add_gridspec(2,2,left=.08,right=.98,bottom=.12,top=.93,wspace=.25,hspace=.43)
    focus=(215,260)
    full=(float(np.floor(common.crps.min()/10)*10),float(np.ceil(common.crps.max()/10)*10))
    ranking=[]
    for i,n in enumerate(NS):
        inner=outer[i//2,i%2].subgridspec(1,2,width_ratios=[4.4,1],wspace=.25)
        ax=fig.add_subplot(inner[0,0]);overview=fig.add_subplot(inner[0,1])
        part=common[common.n==n]
        order=METHODS
        arrays=[part[part.method==m].crps.to_numpy() for m in order]
        colors=[color_map[m] for m in order]
        assert all(len(a)==counts.loc[n,'all_six_valid'] for a in arrays)
        for target in [ax,overview]:
            vp=target.violinplot(arrays,positions=np.arange(1,7),widths=.85,points=400,
                bw_method='scott',showmeans=False,showmedians=False,showextrema=False)
            for j,(body,color,a) in enumerate(zip(vp['bodies'],colors,arrays),1):
                body.set(facecolor=color,edgecolor=color,alpha=.6,linewidth=.6)
                q25,median,q75=np.quantile(a,[.25,.5,.75])
                if target is ax:
                    target.vlines(j,q25,q75,color=color,linewidth=2.5,zorder=3)
                    target.scatter(j,median,s=10,color='white',edgecolor=color,linewidth=.6,zorder=4)
            target.set_xlim(.35,6.65)
            target.grid(axis='y',color='#DCE1E4',linewidth=.5,alpha=.6);target.set_axisbelow(True)
        means=[a.mean() for a in arrays]
        ax.plot(np.arange(1,7),means,color='#253A48',lw=1,marker='D',markersize=4,
                markerfacecolor='white',markeredgewidth=.9,zorder=5)
        ax.set_xticks(np.arange(1,7),[label_map[m]+'\n'+f'{a.mean():.2f}' for m,a in zip(order,arrays)],fontsize=7)
        ax.set_ylim(*focus);ax.set_yticks(np.arange(215,261,5))
        ax.set_title(f'({chr(97+i)})  n = {n}',loc='left',fontsize=9,fontweight='bold',pad=14)
        ax.text(1,1.04,'局部放大',transform=ax.transAxes,ha='right',fontsize=7,color='#5B646A')
        if i%2==0:ax.set_ylabel('留出 CRPS（千次循环）',fontsize=8)
        ax.set_xlabel('方法及平均 CRPS',fontsize=7,color='#5B646A',labelpad=6)
        overview.set_ylim(*full)
        overview.axhspan(*focus,color='#849BA8',alpha=.14,zorder=0)
        overview.set_xticks([]);overview.set_yticks([200,300,400])
        overview.tick_params(labelsize=6,length=2,pad=2)
        overview.set_title('全范围',fontsize=7,pad=14,color='#5B646A')
        for rank,(m,a) in enumerate(zip(order,arrays),1):
            ranking.append(dict(n=n,rank=rank,method=m,mean_crps=a.mean(),count=len(a),
                                below_focus=int((a<focus[0]).sum()),above_focus=int((a>focus[1]).sum())))
        assert overview.get_ylim()[0]<=part.crps.min() and overview.get_ylim()[1]>=part.crps.max()
    fig.text(.53,.025,'菱形与下方数字表示均值；CRPS 越低，留出预测得分越好',ha='center',fontsize=8,color='#46545E')
    for ext in ['png','svg','pdf']:
        fig.savefig(OUT/f'P11_留出预测误差.{ext}',dpi=350,facecolor='white')
    plt.close(fig)
    pd.DataFrame(ranking).to_csv(OUT/'figure_ranking.csv',index=False)
    lines=['# E11 真实疲劳寿命数据的重复小样本留出预测评价','',
        '2026-09-25。使用101个真实寿命观测，n=7、10、15、20各2,000次无放回抽取；每次用n个观测估计，用剩余101−n个观测评价。所有方法共享划分，AMDM采用原冻结模型。',
        '', '**评价对象：少量寿命观测得到的估计分布，能否描述同来源的其他观测。** 本轮不使用全样本MLE或多方法共识作为参数真值。该数据集此前已用于探索，本轮属于同一案例的进一步评价。',
        '', '## 主要结果','',
        '六方法共同成功的抽样上，AMDM平均CRPS低于MLE、WMLE、LSE和LRE；相对MLE降幅为0.49%—1.67%，相对WMLE为0.16%—0.29%。相对固定MDM则高0.04%—0.08%，两者非常接近。这是描述性比较，不宣称统计显著。',
        '', '仅比较AMDM与固定MDM时，两者各档2,000次均成功，AMDM降幅依次为+0.007%、−0.029%、−0.055%、−0.051%。因此不受其他方法失败筛选影响的完整配对结果也没有显示清晰的额外预测优势。AMDM与固定MDM均可稳定完成本案例求解；本案例的分布预测评价与模拟中的参数精度评价回答不同问题。',
        '', '## 指标和比较口径','',
        '主指标为留出观测上的平均CRPS，原始单位为千次循环，越小越好。每个抽样先对其剩余观测求平均，再对共同成功的抽样等权平均。CRPS衡量分布预测，不是参数RMSE。',
        '',r'$$\operatorname{CRPS}(\hat F,y)=\int_{-\infty}^{\infty}[\hat F(t)-\mathbf{1}\{y\le t\}]^2\,dt.$$','',
        '指标依据：[Gneiting与Raftery（2007）](https://doi.org/10.1198/016214506000001437)。数据来源：[NIST BIRNSAUN](https://www.itl.nist.gov/div898/handbook/datasets/BIRNSAUN.DAT)。',
        '', '主图和主表采用六方法共同成功的抽样；成功率按全部2,000次计算。另保存AMDM与各方法在两者共同成功抽样上的配对比较，避免将不同评价集合混为一谈。重复抽取的分布反映固定101个观测下的划分变异，不是总体置信区间。',
        '', '## 汇总表','',
        '| n | 方法 | 平均CRPS | 中位CRPS | AMDM较该方法降幅 | 成功率 | 六方法共同有效数 |',
        '|---:|---|---:|---:|---:|---:|---:|']
    for n in NS:
        part=summary[summary.n==n].set_index('method')
        for m,label in zip(METHODS,LABELS):
            r=part.loc[m]; gain='—' if m=='AMDM' else f'{r.amdm_gain_percent:+.2f}%'
            lines.append(f'| {n} | {label} | {r.common_mean_crps:.3f} | {r.common_median_crps:.3f} | {gain} | {r.success_percent:.2f}% | {int(r.common_valid)} |')
    lines+=['','降幅 = 100 ×（1 − AMDM平均CRPS / 对照平均CRPS）。正值表示AMDM较低，负值表示AMDM较高。MDM指固定δ=0.1。共同成功得分与成功率需一起阅读，不能将成功子集中的表现等同于所有任务上的表现。','',
        '## 结果图','','![留出预测误差](P11_留出预测误差.png)','',
        '图：不同小样本量下六方法的留出CRPS小提琴图。(a)–(d)分别对应n=7、10、15、20。每幅主图保持AMDM、MDM、WMLE、MLE、LSE、LRE顺序，方法颜色保持一致。宽度表示核密度，内部粗线为四分位区间，白圆点为中位数，空心菱形及方法名下方数字为均值。均值连线仅辅助比较高低，不表示连续变量趋势。数值越低表示留出预测得分越好。','',
        '主图统一放大215—260区间，旁侧小图使用统一全范围显示全部得分，其阴影标出放大范围。未删掉尾部观测；[均值与范围计数](figure_ranking.csv)保存各方法均值、数量及主图范围外计数。各小提琴等最大宽度。图与主表均为六方法共同成功抽样，其数量依次为1025、1350、1560、1670。','',
        '## 固定MDM的完整配对检查','',
        '以下只要求AMDM与固定MDM共同成功，不受其他方法失败影响。','',
        '| n | 配对数量 | AMDM平均CRPS | 固定MDM平均CRPS | AMDM降幅 |','|---:|---:|---:|---:|---:|']
    for r in pairs[pairs.comparator=='MDM-0.1'].itertuples():
        lines.append(f'| {r.n} | {r.paired_valid} | {r.amdm_crps:.3f} | {r.baseline_crps:.3f} | {r.gain_percent:+.2f}% |')
    lines+=['','## 文件与复现','',
        '- [运行程序](../run_holdout.py)：冻结协议、核验历史估计、补算方法、计算留出得分及汇总。',
        '- [绘图与报告程序](../plot_holdout.py)：生成本报告及PNG、SVG、PDF。',
        '- [冻结协议](protocol.json)、[核验结果](verification.json)、[逐抽样结果](per_subsample.csv.gz)、[抽取编号](estimation_ids.csv.gz)。',
        '- [主表](summary.csv)、[全部配对比较](paired_comparison.csv)、[共同成功绘图数据](common_scores.csv.gz)。',
        '', '本次复用24,000条既有估计并补算24,000条估计，全部48,000条留出得分重新计算。检查每次训练/评价编号不重叠、缓存估计数值不变、数据/代码/模型哈希不变，并以独立数值积分校验24种样本量×方法的CRPS。未重新训练、未改变旧结果、未自动写入论文或Git提交。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    write_json(OUT/'figure_manifest.json',dict(archetype='quantitative grid',backend='Python matplotlib',
        purpose='Compare holdout predictive scores and conditional subsampling spread; no assumed winner',
        size_mm=[200,150],files=['P11_留出预测误差.'+x for x in ['png','svg','pdf']],
        data_sha256=sha(OUT/'common_scores.csv.gz'),script_sha256=sha(Path(__file__)),
        center='white circle median, hollow diamond mean, numeric means under method labels',
        spread='Scott-bandwidth KDE plus IQR',ordering='fixed original method order and colors',
        focus_ylim=focus,overview_ylim=full,all_observations_included=True,
        scope='all-six-successful subsets; separate success rates and paired sensitivity'))
    assert all(sha(p)==h for p,h in before.items()),'Scientific data changed during plotting'
    write_json(OUT/'plot_verification.json',dict(data_unchanged=True,input_hashes=before,
        overview_full_range=True,focus_ylim=focus,fixed_original_method_order=True))
    print(summary[['n','method','common_mean_crps','amdm_gain_percent','success_percent','common_valid']].to_string(index=False))


if __name__=='__main__':main()
