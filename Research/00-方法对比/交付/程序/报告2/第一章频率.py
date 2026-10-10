"""Count shape estimates outside [truth/3, truth*3], including both limits."""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import csv
import hashlib
import json
import math
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = RESULT / "报告2/图1_明显异常估计频率.png"
FACTOR_THRESHOLD = 3.0
METHODS = ['MDM δ=0.10', 'MDM δ=0.15', 'MDM δ=0.20', 'LSE', 'LRE', 'MLE', 'WMLE', 'MMLE']
PLOT_METHODS = ['MDM δ=0.20', 'LSE', 'LRE', 'MLE', 'WMLE', 'MMLE']


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources = json.loads((PROGRAM / '跨参数对比/13组合取数.json').read_text(encoding='utf-8'))['sources']
    counts = Counter()
    totals = Counter()
    successful = Counter()
    true_shapes = {}
    source_hashes = {}
    for source in sources:
        matrix = matrix_path(source)
        source_hashes[str(matrix)] = digest(matrix)
        payload = json.loads(matrix.read_text(encoding='utf-8'))
        beta_true = float(payload['config']['truth'][0])
        assert beta_true > 0
        true_shapes[source['combination']] = beta_true
        for r in payload['results']:
            method = f"MDM δ={r['delta']:.2f}" if r['method_id'] == 'mdm' else r['method_id'].upper()
            key = (source['combination'], int(r['n']), method)
            totals[key] += 1
            finite = r['converged'] and all(isinstance(r[k], (int, float)) and math.isfinite(r[k]) for k in ['beta_hat', 'eta_hat', 'gamma_hat'])
            if finite:
                successful[key] += 1
                assert r['beta_hat'] > 0
                if r['beta_hat'] >= FACTOR_THRESHOLD * beta_true or r['beta_hat'] <= beta_true / FACTOR_THRESHOLD:
                    counts[key] += 1
    assert len(totals) == 312 and sum(totals.values()) == 15600
    assert all(v == 50 for v in totals.values())
    table = [dict(combination=c, beta_true=true_shapes[c], n=n, method=m,
                  total=totals[c,n,m], successful=successful[c,n,m],
                  abnormal=counts[c,n,m], percent=100*counts[c,n,m]/totals[c,n,m])
             for c,n,m in sorted(totals)]
    with (DATA_DIR / '第一章频率.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(table)
    plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'], 'font.size':10, 'axes.unicode_minus':False})
    def combination_order(c):
        beta, eta, gamma = (float(v) for v in c[2:-1].split(','))
        return beta, eta, gamma

    combos = sorted({c for c,n,m in totals}, key=combination_order)
    boundaries = [i-.5 for i in range(1,len(combos))
                  if combination_order(combos[i])[0] != combination_order(combos[i-1])[0]]
    ns = [7,15,30]
    matrices = {m: np.array([[100*counts[c,n,m]/totals[c,n,m] for n in ns] for c in combos]) for m in PLOT_METHODS}
    vmax = max(10, 10 * math.ceil(max(values.max() for values in matrices.values()) / 10))
    fig, axs = plt.subplots(2,3,figsize=(11,9),sharey=True,layout='constrained')
    for panel, (ax, method) in enumerate(zip(axs.flat, PLOT_METHODS)):
        values = matrices[method]
        im = ax.imshow(values,cmap='YlOrRd',vmin=0,vmax=vmax,aspect='auto',interpolation='nearest')
        ax.set(title=method,xticks=np.arange(3),xticklabels=ns,xlabel='样本量 n',yticks=np.arange(len(combos)),yticklabels=combos)
        ax.spines[['top','right','left','bottom']].set_visible(False)
        ax.tick_params(axis='both',length=0,labelsize=9)
        ax.text(-0.02,1.045,'abcdef'[panel],transform=ax.transAxes,fontweight='bold',ha='left')
        for boundary in boundaries:
            ax.axhline(boundary, color='white', linewidth=1.2)
        for i in range(len(combos)):
            for j in range(3):
                ax.text(j,i,f'{values[i,j]:.0f}%',ha='center',va='center',fontsize=9,color='white' if values[i,j]>=.65*vmax else '#333333')
    for ax in axs[:,0]:
        ax.set_ylabel('参数组合 W(β,η,γ)')
    fig.colorbar(im,ax=list(axs.flat),shrink=.85,pad=.025,ticks=np.arange(0,vmax+1,10),label='明显异常估计频率（%）')
    fig.savefig(OUT,dpi=400)
    plt.close(fig)
    assert all(digest(Path(p)) == value for p,value in source_hashes.items())
    summary = dict(criterion='successful positive finite estimate with beta_hat >= 3*beta_true or beta_hat <= beta_true/3',
                   parameter='beta', factor_threshold=FACTOR_THRESHOLD,
                   denominator='all 50 attempts per combination, sample size and method setting',
                   total_records=sum(totals.values()), successful_records=sum(successful.values()),
                   abnormal=sum(counts.values()),
                   by_method={m:sum(v for (c,n,mm),v in counts.items() if mm==m) for m in METHODS},
                   by_n={n:sum(v for (c,nn,m),v in counts.items() if nn==n) for n in ns},
                   plot_total_records=sum(v for (c,n,m),v in totals.items() if m in PLOT_METHODS),
                   plot_abnormal=sum(v for (c,n,m),v in counts.items() if m in PLOT_METHODS),
                   plot_by_method={m:sum(v for (c,n,mm),v in counts.items() if mm==m) for m in PLOT_METHODS},
                   plot_by_n={n:sum(v for (c,nn,m),v in counts.items() if nn==n and m in PLOT_METHODS) for n in ns},
                   plot_methods=PLOT_METHODS, plot_row_order=combos, color_limits=[0,vmax],
                   source_sha256=source_hashes, source_unchanged=True)
    (DATA_DIR / '第一章频率核对.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS all eight settings:',summary['by_method'],summary['by_n'],f"{summary['abnormal']}/{summary['total_records']}")
    print('PASS six displayed methods:',summary['plot_by_method'],summary['plot_by_n'],f"{summary['plot_abnormal']}/{summary['plot_total_records']}; 13 source matrices unchanged")


if __name__ == '__main__':
    main()
