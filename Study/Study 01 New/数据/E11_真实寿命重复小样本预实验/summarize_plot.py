"""Pilot figures: empirical-distribution recovery, not parameter-truth accuracy.

Quantitative grid; 183 x 130 mm; Python, editable SVG/PDF and 350 dpi PNG.
All valid-score distributions shown on common-six-method subsets; no truncation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_pilot import HERE,NS,METHODS,cdf,sha,MODELDIR

COLORS=['#436F91','#659B89','#B88755','#7B7B86','#AB8097','#8D9CBE']
LABELS=['AMDM','MDM','WMLE','MLE','LSE','LRE']

def export(fig,name):
    for ext in ['png','svg','pdf']:fig.savefig(HERE/(name+'.'+ext),dpi=350,facecolor='white')
    plt.close(fig)

def main():
    df=pd.read_csv(HERE/'per_subsample.csv')
    obs=pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    ref=pd.read_csv(HERE/'reference_fits.csv').iloc[0]
    truthproxy=np.array([ref.beta_hat,ref.eta_hat,ref.gamma_hat])
    normalizer=np.array([ref.beta_hat,ref.eta_hat,ref.eta_hat])
    errors=(df[['beta_hat','eta_hat','gamma_hat']].to_numpy()-truthproxy)/normalizer
    errors[~df.valid]=np.nan
    for j,p in enumerate(['beta','eta','gamma']):df['reference_error_'+p]=errors[:,j]
    # This is agreement with one fitted reference, not known-truth error.
    df['reference_squared_error']=np.sum(errors**2,axis=1)
    proxy=[]
    for (n,m),g in df.groupby(['n','method']):
        v=g[g.valid]
        proxy.append(dict(n=n,method=m,valid=len(v),reference_J=np.sqrt(v.reference_squared_error.mean()),
            **{p+'_reference_rmse':np.sqrt((v['reference_error_'+p]**2).mean()) for p in ['beta','eta','gamma']}))
    pd.DataFrame(proxy).to_csv(HERE/'parameter_reference_comparison.csv',index=False)
    paired=pd.read_csv(HERE/'paired_comparison.csv')
    ref_pairs=[]
    for n,part in df.groupby('n'):
        a=part[part.method=='AMDM'].set_index('repeat')
        for method in METHODS[1:]:
            b=part[part.method==method].set_index('repeat');valid=a.valid & b.valid
            av=np.sqrt(a.loc[valid,'reference_squared_error'].mean())
            bv=np.sqrt(b.loc[valid,'reference_squared_error'].mean())
            ref_pairs.append(dict(n=n,comparator=method,paired_valid=int(valid.sum()),
                amdm_reference_J=av,baseline_reference_J=bv,gain_percent=100*(1-av/bv)))
    ref_pairs=pd.DataFrame(ref_pairs)
    ref_pairs.to_csv(HERE/'paired_parameter_reference.csv',index=False)
    summary=pd.read_csv(HERE/'summary.csv')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,'axes.linewidth':.6})
    common=[];parts={}
    for n in NS:
        part=df[df.n==n]
        mask=part.pivot(index='repeat',columns='method',values='valid')[METHODS].all(axis=1)
        parts[n]=part[part.repeat.isin(mask[mask].index)]
        common.append(dict(n=n,common_valid=int(mask.sum()),total=100))
    pd.DataFrame(common).to_csv(HERE/'common_counts.csv',index=False)
    fig,axes=plt.subplots(2,2,figsize=(183/25.4,130/25.4),sharey=True)
    fig.subplots_adjust(left=.1,right=.98,bottom=.12,top=.92,wspace=.15,hspace=.45)
    for i,(ax,n) in enumerate(zip(axes.flat,NS)):
        arrays=[parts[n].loc[parts[n].method==m,'cdf_l2'].to_numpy()*1000 for m in METHODS]
        bp=ax.boxplot(arrays,patch_artist=True,widths=.52,showfliers=True,
            medianprops=dict(color='#24313B',linewidth=1),flierprops=dict(marker='.',markersize=2,alpha=.45))
        for patch,color in zip(bp['boxes'],COLORS):patch.set(facecolor=color,alpha=.65)
        ax.scatter(np.arange(1,7),[a.mean() for a in arrays],marker='D',s=12,c='#26343F',zorder=4)
        ax.set_xticks(np.arange(1,7),LABELS,rotation=35)
        ax.set_title(f'({chr(97+i)}) n = {n}  ·  共同有效 {common[i]["common_valid"]}/100',loc='left',fontsize=8)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.17)
        if i%2==0:ax.set_ylabel(r'分布恢复误差（$\times 10^{-3}$）')
    export(fig,'P11_分布恢复误差')
    grid=np.linspace(0,2700,701);curves=[]
    fig,axes=plt.subplots(2,2,figsize=(183/25.4,130/25.4),sharex=True,sharey=True)
    fig.subplots_adjust(left=.1,right=.98,bottom=.18,top=.94,wspace=.15,hspace=.3)
    for i,(ax,n) in enumerate(zip(axes.flat,NS)):
        ax.step(np.r_[0,np.sort(obs),2700],np.r_[0,np.arange(1,102)/101,1],where='post',color='#272E34',linewidth=1.3,label='全体101个观测')
        for m,color,label in zip(METHODS,COLORS,LABELS):
            estimates=parts[n][parts[n].method==m][['beta_hat','eta_hat','gamma_hat']].to_numpy()
            ys=np.array([cdf(grid,p) for p in estimates]);mean=ys.mean(axis=0)
            ax.plot(grid,mean,color=color,label=label,linewidth=1.3 if m=='AMDM' else .95)
            curves.extend(dict(n=n,method=m,t=float(x),mean_cdf=float(y)) for x,y in zip(grid,mean))
        ax.set_title(f'({chr(97+i)}) n = {n}',loc='left',fontsize=9)
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
        if i>=2:ax.set_xlabel('疲劳寿命（千次循环）')
        if i%2==0:ax.set_ylabel('累积失效概率')
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=4,fontsize=7,frameon=False)
    export(fig,'P11_分布恢复曲线')
    pd.DataFrame(curves).to_csv(HERE/'mean_cdf_curves.csv',index=False)
    lines=['# E11 真实疲劳寿命重复小样本预实验','',
        '状态：预实验已完成，尚未写入论文4.3。真实数据结果不作为已知真参数的精度证明。','',
        '## 数据与冻结方案','',
        '- 来源：[NIST原始数据](https://www.itl.nist.gov/div898/handbook/datasets/BIRNSAUN.DAT)，Birnbaum与Saunders（1958）6061-T6铝合金疲劳寿命，最大应力21,000 psi，101个完整观测，单位为千次循环。',
        '- [NIST模型比较](https://www.itl.nist.gov/div898/handbook/eda/section4/eda4292.htm)考察了三参数Weibull等模型，其信息准则偏向正态分布。因此这是三参数Weibull估计方法的真实数据适配预实验，不能将数据视为已知Weibull总体。',
        '- 按作者决定：全体101个观测同时作为经验参考与抽样池；无61/40拆分。原拟议拆分未执行。',
        '- n=7、10、15、20各100次；每次从101个观测中无放回抽取，同一小样本用于六方法；不同重复之间可重叠。种子20260925，不根据结果筛选样本或更换数据集。',
        '- AMDM直接使用E09冻结模型，不用真实数据重新训练；沿用E09传统方法求解协议及固定单位换算。',
        '- 主指标：估计CDF与全101个观测的经验CDF，在[0,参考最大观测]上的归一化积分平方距离，越小越贴近完整数据分布；次指标为全参考集平均CRPS/参考IQR。两者均非独立留出预测误差。',
        '- 三参数仅报告相对全样本MLE拟合的偏离，作为辅助描述，不称真参数RMSE、不据此确定方法优劣。',
        '- 图中箱线表示四分位数及1.5 IQR须，离群点全部保留，菱形为均值；这是固定数据集下重复抽取的变异，不是总体置信区间。','',
        '## AMDM相对各方法的分布恢复误差降幅','',
        '每格按AMDM与该方法共同有效的小样本比较；正值为AMDM平均CDF距离较小。','',
        '| n | 固定MDM | WMLE | MLE | LSE | LRE |','|---|---:|---:|---:|---:|---:|']
    for n in NS:
        part=paired[(paired.n==n)&(paired.metric=='cdf_l2')].set_index('comparator')
        lines.append('| '+str(n)+' | '+' | '.join(f'{part.loc[m,"gain_percent"]:.2f}%' for m in METHODS[1:])+' |')
    lines+=['','## 相对完整数据拟合参数的恢复','',
        '完整101观测的MLE拟合是参考估计，不是真参数。下表比较AMDM相对固定MDM的参考联合误差降幅，两个方法均使用全部100次抽取。','',
        '| n | AMDM参考联合误差 | 固定MDM参考联合误差 | 降幅 |','|---|---:|---:|---:|']
    for row in ref_pairs[ref_pairs.comparator=='MDM-0.1'].itertuples():
        lines.append(f'| {row.n} | {row.amdm_reference_J:.5f} | {row.baseline_reference_J:.5f} | {row.gain_percent:.2f}% |')
    lines+=['','参数参考比较与经验分布比较回答不同问题。本预实验中，AMDM在n=10、15、20时比固定MDM更接近全样本拟合参数，但四档经验CDF距离略高于固定MDM。不能因某个指标有利就将其重新命名为真实精度。','',
        '## 求解失败数（每方法每档100次）','','| n | AMDM | MDM | WMLE | MLE | LSE | LRE |','|---|---:|---:|---:|---:|---:|---:|']
    for n in NS:
        s=summary[summary.n==n].set_index('method');lines.append('| '+str(n)+' | '+' | '.join(str(int(s.loc[m,'failures'])) for m in METHODS)+' |')
    lines+=['','## 结果图','','![分布恢复误差](P11_分布恢复误差.png)','','![分布恢复曲线](P11_分布恢复曲线.png)','',
        '曲线为六方法共同有效重复上的平均拟合CDF，不挑选有利的单次样本，也不把平均曲线当作可部署估计器。误差图使用相同共同有效集合；上述成对比较表用各对自己的有效集合，二者汇总口径不同。','',
        '## 复现与核验','',
        '`python run_pilot.py` 完成计算，`python summarize_plot.py` 生成报告和图。保留原始数值转录、观测编号、每次抽样编号、模型/代码哈希、逐样本结果、失败记录、比较表及验证JSON。',
        '直接HTTP下载返回403，原始数值来自NIST网页工具读取后按原顺序转录；文件哈希对应转录文件。全样本MLE与NIST报告拟合核对，CRPS与数值积分交叉检查，CDF距离用更细网格核验；见[验证结果](verification.json)。','',
        '全样本MLE拟合：形状 %.6f，尺度 %.6f，位置 %.6f；NIST报告约3.43、1357、181。'%(ref.beta_hat,ref.eta_hat,ref.gamma_hat)]
    (HERE/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('Report and two pilot figures exported.')

if __name__=='__main__':main()
