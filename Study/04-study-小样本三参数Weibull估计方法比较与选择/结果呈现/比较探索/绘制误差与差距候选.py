"""读取既有共同有效指标，为3.1生成三种配图候选；不重新估计。"""
from pathlib import Path
import csv
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
SOURCE = STUDY / '结果呈现/分析数据/参数指标.csv'
ASSETS = STUDY / 'reviewbyhtml/方法对比-v1.0/assets'
BETAS = [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
NS = [50, 20, 15, 10, 7]
PARAMS = ['beta', 'eta', 'gamma']
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)', 'MM']
LABELS = ['MDM', 'LSE', 'LRE (Park)', 'WMLE', 'MLE', 'K–R', 'MM']
COLORS = ['#0072B2', '#009E73', '#CC79A7', '#D55E00', '#444444', '#56B4E9']
FILES = ['误差与差距_A_方法轨迹.png', '误差与差距_B_联动轨迹.png', '误差与差距_C_条件全图.png']


def read_metrics():
    rows = list(csv.DictReader(SOURCE.open(encoding='utf-8-sig', newline='')))
    selected = [r for r in rows if r['subset'] == 'common']
    lookup = {(float(r['beta']), int(r['n']), r['method']): r for r in selected}
    if len(lookup) != 40 * 7 or len(selected) != len(lookup):
        raise ValueError('共同有效指标应为40条件×7方法，且无重复。')
    values = np.empty((3, 5, 8, 7))
    for p, parameter in enumerate(PARAMS):
        for i, n in enumerate(NS):
            for j, beta in enumerate(BETAS):
                for m, method in enumerate(METHODS):
                    row = lookup[beta, n, method]
                    assert float(row['eta']) == 1000 and float(row['gamma']) == 500
                    assert int(row['total']) == 1200
                    values[p, i, j, m] = float(row[parameter + '_rmse']) / (beta if p == 0 else 1000)
    assert np.isfinite(values).all() and (values > 0).all()
    # Same seven-method median/minimum definition as chapter 2; no composite parameter score.
    median = np.median(values, axis=3)
    gap = 100 * (median / values.min(axis=3) - 1)
    for p in range(3):
        for j in [0, 1, 2, 3]:
            assert gap[p, -1, j] > gap[p, 0, j]
        for j in [6, 7]:
            assert gap[p, -1, j] < gap[p, 0, j]
    return values, median, gap


def style_axis(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color='#dce2e6', linewidth=.6, zorder=0)
    ax.tick_params(length=3)


def save(fig, name):
    path = ASSETS / name
    fig.savefig(path, dpi=200, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    return {'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def method_paths(values):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey='col')
    x = np.arange(5)
    for row, j in enumerate([0, 7]):
        for p, ax in enumerate(axes[row]):
            for m in range(6):
                ax.plot(x, values[p, :, j, m], color=COLORS[m], marker='o', ms=4,
                        lw=1.7, label=LABELS[m])
            ax.set_xticks(x, NS)
            ax.set_ylim(bottom=0)
            style_axis(ax)
            if row == 0:
                ax.set_title([r'$\beta$', r'$\eta$', r'$\gamma$'][p], pad=11)
            else:
                ax.set_xlabel('n')
            if p == 0:
                ax.set_ylabel(f'β = {BETAS[j]:g}\nNormalized RMSE', labelpad=10)
    for p in range(3):
        axes[0, p].set_ylim(0, 1.08 * values[p, :, [0, 7], :6].max())
    fig.legend(*axes[0, 0].get_legend_handles_labels(), ncol=6,
               loc='upper center', bbox_to_anchor=(.52, 1.02), frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .96), h_pad=2, w_pad=1.8)
    return save(fig, FILES[0])


def error_gap_paths(median, gap):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    beta_colors = ['#0072B2', '#D55E00', '#009E73']
    symbols = [r'$\beta$', r'$\eta$', r'$\gamma$']
    for p, ax in enumerate(axes):
        for j, color in zip([0, 3, 7], beta_colors):
            x, y = median[p, :, j], gap[p, :, j]
            ax.plot(x, y, color=color, lw=1.5, marker='o', ms=3.5, label=f'β = {BETAS[j]:g}')
            ax.scatter(x[0], y[0], color=color, s=55, facecolor='white', zorder=3)
            ax.scatter(x[-1], y[-1], color=color, s=44, marker='s', zorder=3)
            for a in range(4):
                ax.annotate('', xy=(x[a+1], y[a+1]), xytext=(x[a], y[a]),
                            arrowprops=dict(arrowstyle='->', color=color, lw=1.2,
                                            shrinkA=6, shrinkB=6))
        ax.set_title(symbols[p], pad=11)
        ax.set_xlabel('Median normalized RMSE')
        ax.set_ylim(bottom=0)
        style_axis(ax)
        if p == 0:
            ax.set_ylabel('Relative gap (%)')
    handles, labels = axes[0].get_legend_handles_labels()
    handles += [Line2D([], [], color='#555', marker='o', markerfacecolor='white', linestyle='', label='n = 50'),
                Line2D([], [], color='#555', marker='s', linestyle='', label='n = 7')]
    fig.legend(handles=handles, ncol=5, loc='upper center', bbox_to_anchor=(.5, 1.02), frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .92), w_pad=2)
    return save(fig, FILES[1])


def condition_maps(median, gap):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for p, symbol in enumerate([r'$\beta$', r'$\eta$', r'$\gamma$']):
        for row, (data, cmap, label) in enumerate([
            (median, 'YlGnBu', 'Median normalized RMSE'),
            (gap, 'YlOrRd', 'Relative gap (%)'),
        ]):
            ax = axes[row, p]
            # Each parameter has its own labeled color scale; n and β positions are shared.
            img = ax.imshow(data[p], cmap=cmap, vmin=0, vmax=float(data[p].max()),
                            aspect='auto', interpolation='nearest')
            ax.set_xticks(range(8), [f'{x:g}' for x in BETAS])
            ax.set_yticks(range(5), NS)
            ax.set_xlabel('β')
            if p == 0:
                ax.set_ylabel('n')
            if row == 0:
                ax.set_title(symbol, pad=11)
            ax.tick_params(length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
            colorbar = fig.colorbar(img, ax=ax, fraction=.045, pad=.035)
            colorbar.ax.set_ylabel(label)
    fig.tight_layout(h_pad=2.5, w_pad=2)
    return save(fig, FILES[2])


def main():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.labelsize': 11, 'axes.titlesize': 15,
                         'legend.fontsize': 10, 'axes.spines.top': False,
                         'axes.spines.right': False})
    values, median, gap = read_metrics()
    outputs = [method_paths(values), error_gap_paths(median, gap), condition_maps(median, gap)]
    audit = dict(source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                 subset='seven-method common valid', n=NS, beta=BETAS,
                 normalization=['true beta', 1000, 1000],
                 gap='100 * (median(seven RMSE) / min(seven RMSE) - 1)',
                 outputs=outputs, median_normalized_rmse=median.tolist(), gap_percent=gap.tolist())
    (SOURCE.parent / '误差与差距候选核验.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'figures': [x['file'] for x in outputs], 'source_sha256': audit['source_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
