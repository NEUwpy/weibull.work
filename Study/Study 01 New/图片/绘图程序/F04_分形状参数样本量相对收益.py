"""F04 quantitative grid: true shape by estimated parameter.

Show whether relative RMSE gains over MLE differ across true shapes.
Python/matplotlib; 183 x 205 mm, editable SVG/PDF, PNG and individual panels.
Frozen E09/E10 observations; no refitting or smoothing. All intervals retained.
"""
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from F04_样本量相对收益 import (
    ROOT, SOURCE, EXTENSION, EXTENSION100, METHODS, PARAMS,
    COLORS, MARKERS, LABELS, SEED, DRAWS, export,
)

STEM = 'F04_分形状参数样本量相对收益'
BETAS = [1.5, 2., 3., 5.]
NS = [7, 10, 15, 20, 30, 50, 100]
HEADERS = ['形状参数 β', '尺度参数 η', '位置参数 γ']


def compute():
    rows = pd.concat([pd.read_csv(p) for p in [SOURCE, EXTENSION, EXTENSION100]], ignore_index=True)
    rows = rows[rows.method.isin(METHODS)]
    keys = ['cell_id', 'repeat_id']
    assert len(rows) == 33600 and not rows.duplicated(['n']+keys+['method']).any()
    summaries, draws, selected, groups = [], [], [], []
    for beta in BETAS:
        for n in NS:
            part = rows[(rows.beta == beta) & (rows.n == n)]
            valid = part.pivot(index=keys, columns='method', values='valid')[METHODS]
            hashes = part.pivot(index=keys, columns='method', values='sample_sha256')[METHODS]
            assert valid.shape == (300, 4) and not valid.isna().any().any()
            assert hashes.nunique(axis=1).eq(1).all()
            shared = valid.index[valid.all(axis=1)]
            block = part.set_index(keys+['method'])
            cells, counts = [], {}
            for cell in sorted(shared.get_level_values('cell_id').unique()):
                ids = shared[shared.get_level_values('cell_id') == cell]
                arr = np.stack([block.loc[[(c,r,m) for c,r in ids], ['err_'+p for p in PARAMS]].to_numpy() for m in METHODS], axis=1)**2
                assert np.isfinite(arr).all()
                cells.append(arr)
                counts[str(cell)] = len(ids)
            assert len(cells) == 3
            selected.extend(dict(beta=beta,n=n,cell_id=c,repeat_id=r,sample_sha256=hashes.loc[(c,r),'MLE']) for c,r in shared)
            total = np.concatenate(cells)
            rmse = np.sqrt(total.mean(axis=0))
            rng = np.random.default_rng(np.random.SeedSequence([SEED, int(beta*10), n]))
            sums = np.zeros((DRAWS,4,3))
            for arr in cells:
                idx = rng.integers(0,len(arr),size=(DRAWS,len(arr)))
                sums += arr[idx].sum(axis=1)
            brmse = np.sqrt(sums/len(total))
            gain = 100*(1-brmse[:,:3,:]/brmse[:,3:4,:])
            for m,method in enumerate(METHODS[:-1]):
                for j,param in enumerate(PARAMS):
                    lo,hi = np.quantile(gain[:,m,j],[.025,.975])
                    summaries.append(dict(beta=beta,n=n,method=method,parameter=param,
                        rmse=rmse[m,j],MLE_rmse=rmse[3,j],gain_percent=100*(1-rmse[m,j]/rmse[3,j]),
                        ci95_low=lo,ci95_high=hi,common_valid_samples=len(total)))
                    draws.append(pd.DataFrame(dict(beta=beta,n=n,method=method,parameter=param,
                        draw=np.arange(DRAWS),gain_percent=gain[:,m,j])))
            groups.append(dict(beta=beta,n=n,total_samples=300,common_valid_samples=len(total),
                valid_per_cell=counts,failures={m:int((~part.loc[part.method==m,'valid']).sum()) for m in METHODS}))
    stats = pd.DataFrame(summaries)
    stats.to_csv(ROOT/'数据'/(STEM+'.csv'),index=False,encoding='utf-8-sig')
    pd.concat(draws).to_csv(ROOT/'数据'/(STEM+'_重抽样.csv.gz'),index=False,compression='gzip')
    pd.DataFrame(selected).to_csv(ROOT/'数据'/(STEM+'_共同样本.csv'),index=False,encoding='utf-8-sig')
    meta = dict(sources=[dict(path=str(p.relative_to(ROOT.parent)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [SOURCE,EXTENSION,EXTENSION100]],
        baseline='MLE',methods=METHODS,groups=groups,draws=DRAWS,seed=SEED,
        random_stream='SeedSequence([seed, int(true_beta*10), n])',
        metric='100*(1-method standardized parameter RMSE/MLE standardized parameter RMSE)',
        normalization={'beta':'true beta','eta':'true eta','gamma':'true eta'},
        aggregation='Within each true beta and n, pool common-valid observations across gamma/eta=0.1,0.5,1; weights proportional to retained counts.',
        interval='2000 within-cell paired bootstrap draws; pointwise percentile 95%; identical indices for all methods and parameters.',
        scope='Conditional on common validity and frozen models; excludes training variation. Validity composition varies across n. Descriptive comparisons, not causal mechanism evidence.',
        geometry='4 true-shape rows x 3 estimated-parameter columns; common y limits include every interval; log n; no smoothing.',summary=summaries)
    (ROOT/'数据'/(STEM+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return stats


def draw(ax, stats, beta, param, label, limits):
    part = stats[(stats.beta == beta) & (stats.parameter == param)]
    for method in METHODS[:-1]:
        p = part[part.method == method].sort_values('n')
        ax.fill_between(p.n,p.ci95_low,p.ci95_high,color=COLORS[method],alpha=.13,linewidth=0)
        ax.plot(p.n,p.gain_percent,color=COLORS[method],marker=MARKERS[method],
            linewidth=1.35 if method=='AMDM' else 1.05,markersize=3.3,
            markeredgecolor='white',markeredgewidth=.4,label=LABELS[method],zorder=3)
    ax.axhline(0,color='#929BA3',linewidth=.7,linestyle=(0,(3,3)))
    ax.set_xscale('log')
    ax.set(xticks=NS,xlim=(6,115),ylim=limits)
    ax.set_xticklabels([str(n) for n in NS])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(20))
    ax.spines[['top','right']].set_visible(False)
    ax.tick_params(direction='out',length=2.5,width=.6,labelsize=7)
    ax.grid(axis='y',color='#E6EBEF',linewidth=.5)
    ax.set_axisbelow(True)
    ax.text(.015,.97,label,transform=ax.transAxes,va='top',fontsize=8,fontweight='bold')


def main():
    stats = compute()
    limits = (min(-10,np.floor(stats.ci95_low.min()/10)*10),max(80,np.ceil(stats.ci95_high.max()/10)*10))
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
        'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,'axes.linewidth':.65})
    fig,axes = plt.subplots(4,3,figsize=(183/25.4,205/25.4),sharex=True,sharey=True)
    fig.subplots_adjust(left=.105,right=.985,top=.92,bottom=.11,wspace=.14,hspace=.32)
    for i,beta in enumerate(BETAS):
        for j,param in enumerate(PARAMS):
            ax = axes[i,j]
            draw(ax,stats,beta,param,f'({chr(97+i*3+j)})',limits)
            ax.tick_params(labelbottom=True)
            if i==0: ax.set_title(HEADERS[j],fontsize=9,pad=24)
        axes[i,1].text(.5,1.045,f'总体形状参数 β = {beta:g}',transform=axes[i,1].transAxes,
            ha='center',va='bottom',fontsize=8,color='#44515C')
    fig.supylabel('相对 MLE 的 RMSE 降幅（%）',x=.018,fontsize=9)
    fig.supxlabel('样本量 n（对数刻度）',y=.062,fontsize=8)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.54,.012),ncol=3,frameon=False,columnspacing=2.5)
    export(fig,ROOT/STEM)
    for i,beta in enumerate(BETAS):
        for j,param in enumerate(PARAMS):
            letter = chr(97+i*3+j)
            fig,ax = plt.subplots(figsize=(90/25.4,80/25.4))
            fig.subplots_adjust(left=.19,right=.97,top=.86,bottom=.27)
            draw(ax,stats,beta,param,f'({letter})',limits)
            ax.set_title(f'β = {beta:g} · {HEADERS[j]}',fontsize=9)
            ax.set(xlabel='样本量 n（对数刻度）',ylabel='相对MLE的RMSE降幅（%）')
            fig.legend(*ax.get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False,fontsize=7,columnspacing=.8)
            export(fig,ROOT/'子图'/f'F04{letter}_真beta{beta:g}_{param}_相对收益')
    print(stats[(stats.n==100)&(stats.method=='WMLE')][['beta','parameter','gain_percent']].to_string(index=False))
    print('points:',len(stats),'y limits:',limits)


if __name__ == '__main__':
    main()
