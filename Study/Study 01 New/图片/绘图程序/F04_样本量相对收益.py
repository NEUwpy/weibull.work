"""Three parameter panels: paired relative RMSE gains over MLE by sample size.

Quantitative comparison, 183 x 78 mm; PNG/SVG/PDF and individual panels.
Standardized parameter errors follow the manuscript and F03 definitions.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / '数据/E09_六方法共同测试/per_sample.csv.gz'
EXTENSION = ROOT.parent / '数据/E10_样本量扩展/per_sample.csv.gz'
EXTENSION100 = ROOT.parent / '数据/E10_样本量扩展/n100/per_sample.csv.gz'
STEM = 'F04_样本量相对收益'
NS = [7, 10, 15, 20, 30, 50]
METHODS = ['AMDM', 'WMLE', 'MDM-0.1', 'MLE']
PARAMS = ['beta', 'eta', 'gamma']
TITLES = ['(a) 形状参数 β', '(b) 尺度参数 η', '(c) 位置参数 γ']
COLORS = {'AMDM': '#436F91', 'WMLE': '#B88755', 'MDM-0.1': '#659B89'}
MARKERS = {'AMDM': 'o', 'WMLE': '^', 'MDM-0.1': 's'}
LABELS = {'AMDM': 'AMDM', 'WMLE': 'WMLE', 'MDM-0.1': 'MDM (δ = 0.1)'}
SEED, DRAWS = 20260924, 2000


def export(fig, path):
    for ext in ['png', 'svg', 'pdf']:
        dest = path.with_suffix('.'+ext)
        fig.savefig(dest, dpi=400, facecolor='white')
        if ext == 'svg':
            dest.write_text('\n'.join(s.rstrip() for s in dest.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
    plt.close(fig)


def draw(ax, stats, param, title):
    for method in METHODS[:-1]:
        part = stats[(stats.parameter == param) & (stats.method == method)].sort_values('n')
        ax.fill_between(part.n, part.ci95_low, part.ci95_high, color=COLORS[method], alpha=.13, linewidth=0)
        ax.plot(part.n, part.gain_percent, color=COLORS[method], marker=MARKERS[method],
                linewidth=1.65 if method == 'AMDM' else 1.15, markersize=4,
                markeredgecolor='white', markeredgewidth=.45, label=LABELS[method], zorder=3)
    ax.set_title(title, loc='left', fontsize=9, pad=9)
    ax.set_xscale('linear')
    ax.set(xlabel='样本量 n', xticks=NS, xlim=(4,53),
           ylim=(min(0, np.floor(stats.ci95_low.min()/10)*10),max(80,np.ceil(stats.ci95_high.max()/10)*10)))
    ax.set_xticklabels([str(n) for n in NS])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.tick_params(axis='x', labelrotation=45, labelsize=7)
    ax.spines[['top','right']].set_visible(False)
    ax.tick_params(direction='out', length=3, width=.6)
    ax.grid(axis='y', color='#E6EBEF', linewidth=.5)
    ax.set_axisbelow(True)


def main():
    rows = pd.concat([pd.read_csv(SOURCE), pd.read_csv(EXTENSION)], ignore_index=True)
    rows = rows[rows.method.isin(METHODS)]
    keys = ['cell_id', 'repeat_id']
    assert len(rows) == 28800 and not rows.duplicated(['n']+keys+['method']).any()
    rng = np.random.default_rng(SEED)
    summaries, bootstrap, groups, selected_ids = [], [], [], []
    for n in NS:
        part = rows[rows.n == n]
        valid = part.pivot(index=keys, columns='method', values='valid')[METHODS]
        hashes = part.pivot(index=keys, columns='method', values='sample_sha256')[METHODS]
        assert valid.shape == (1200,4) and not valid.isna().any().any()
        assert hashes.nunique(axis=1).eq(1).all()
        shared = valid.index[valid.all(axis=1)]
        selected_ids.extend(dict(n=n, cell_id=k[0], repeat_id=k[1], sample_sha256=hashes.loc[k,'MLE']) for k in shared)
        cells, cell_counts = [], {}
        for cell_id in sorted(shared.get_level_values('cell_id').unique()):
            ids = shared[shared.get_level_values('cell_id') == cell_id]
            block = part.set_index(keys+['method'])
            arr = np.stack([block.loc[[(c,r,m) for c,r in ids], ['err_'+p for p in PARAMS]].to_numpy() for m in METHODS], axis=1)**2
            assert arr.shape == (len(ids),4,3) and np.isfinite(arr).all()
            cells.append(arr)
            cell_counts[str(cell_id)] = len(ids)
        assert len(cells) == 12
        total = np.concatenate(cells)
        rmse = np.sqrt(total.mean(axis=0))
        boot_sums = np.zeros((DRAWS,4,3))
        for arr in cells:
            idx = rng.integers(0,len(arr),size=(DRAWS,len(arr)))
            boot_sums += arr[idx].sum(axis=1)
        brmse = np.sqrt(boot_sums / len(total))
        bgain = 100*(1-brmse[:,:3,:]/brmse[:,3:4,:])
        for m,method in enumerate(METHODS[:-1]):
            for j,param in enumerate(PARAMS):
                lo,hi = np.quantile(bgain[:,m,j],[.025,.975])
                summaries.append(dict(n=n,method=method,parameter=param,rmse=rmse[m,j],MLE_rmse=rmse[3,j],
                                      gain_percent=100*(1-rmse[m,j]/rmse[3,j]),ci95_low=lo,ci95_high=hi,
                                      common_valid_samples=len(total)))
                bootstrap.append(pd.DataFrame(dict(n=n,method=method,parameter=param,draw=np.arange(DRAWS),gain_percent=bgain[:,m,j])))
        groups.append(dict(n=n,total_samples=1200,common_valid_samples=len(total),valid_per_cell=cell_counts,
                           failures={m:int((~part.loc[part.method==m,'valid']).sum()) for m in METHODS}))
    stats = pd.DataFrame(summaries)
    stats.to_csv(ROOT/'数据'/(STEM+'.csv'),index=False,encoding='utf-8-sig')
    pd.concat(bootstrap).to_csv(ROOT/'数据'/(STEM+'_重抽样.csv'),index=False,encoding='utf-8-sig')
    pd.DataFrame(selected_ids).to_csv(ROOT/'数据'/(STEM+'_共同样本.csv'),index=False,encoding='utf-8-sig')
    meta = dict(source=str(SOURCE.relative_to(ROOT.parent)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                extension_source=str(EXTENSION.relative_to(ROOT.parent)),extension_sha256=hashlib.sha256(EXTENSION.read_bytes()).hexdigest(),
                baseline='MLE',methods=METHODS,groups=groups,draws=DRAWS,seed=SEED,
                metric='100 * (1 - method standardized parameter RMSE / MLE standardized parameter RMSE)',
                normalization={'beta':'true beta','eta':'true eta','gamma':'true eta'},
                aggregation='Pool shared-valid samples within n; cell weights proportional to retained sample counts, matching F03.',
                resampling='Resample shared-valid sample pairs within each cell, retaining that cell count; same indices across all methods and parameters.',
                interval='Pointwise percentile 95% intervals conditional on common validity, fixed design and frozen models; not simultaneous bands.',
                scope='E09 n=7/10/15/20 and E10 n=30/50 use independent development/test namespaces and separately trained models. Validity subsets and cell weights differ across n; descriptive trends only. No training variation included. n=100 retained in the supplemental shape-stratified analysis.',
                geometry='Three panels, shared y-axis including all intervals; linear n-axis with true sample-size spacing; ordinary constant-size markers; no smoothing.',summary=summaries)
    (ROOT/'数据'/(STEM+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                         'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,'axes.linewidth':.65})
    fig,axes = plt.subplots(1,3,figsize=(183/25.4,78/25.4),sharey=True)
    fig.subplots_adjust(left=.08,right=.98,top=.86,bottom=.27,wspace=.18)
    for ax,param,title in zip(axes,PARAMS,TITLES): draw(ax,stats,param,title)
    axes[0].set_ylabel('相对MLE的RMSE降幅（%）')
    h,l = axes[0].get_legend_handles_labels()
    fig.legend(h,l,loc='lower center',bbox_to_anchor=(.53,.015),ncol=3,frameon=False,handlelength=2,columnspacing=2.5)
    export(fig,ROOT/STEM)
    for i,(param,title) in enumerate(zip(PARAMS,TITLES)):
        fig,ax=plt.subplots(figsize=(90/25.4,82/25.4))
        fig.subplots_adjust(left=.20,right=.96,top=.86,bottom=.28)
        draw(ax,stats,param,title)
        ax.set_ylabel('相对MLE的RMSE降幅（%）')
        fig.legend(*ax.get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False,fontsize=7,columnspacing=.8)
        export(fig,ROOT/'子图'/f'F04{chr(97+i)}_{param}_样本量相对收益')
    print(stats[['n','method','parameter','gain_percent','ci95_low','ci95_high']].to_string(index=False))


if __name__ == '__main__':
    main()
