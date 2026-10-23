"""直接展示六种常规量级方法的RMSE两两距离及变化；读取七法共同有效指标。"""
from pathlib import Path
from itertools import combinations
import csv
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

STUDY = Path(__file__).resolve().parents[2]
SOURCE = STUDY / '结果呈现/分析数据/参数指标.csv'
ASSETS = STUDY / 'reviewbyhtml/方法对比-v1.0/assets'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)']
LABELS = ['MDM', 'LSE', 'LRE', 'WMLE', 'MLE', 'MMLE']
PAIRS = list(combinations(range(6), 2))
BETAS = [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
NS = [50, 20, 15, 10, 7]
SYMBOLS = [r'$\beta$', r'$\eta$', r'$\gamma$']


def read_distances():
    rows = list(csv.DictReader(SOURCE.open(encoding='utf-8-sig', newline='')))
    common = [r for r in rows if r['subset'] == 'common']
    lookup = {(float(r['beta']), int(r['n']), r['method']): r for r in common}
    assert len(lookup) == len(common) == 280
    values = np.empty((3, 5, 8, 6))
    for p, param in enumerate(['beta', 'eta', 'gamma']):
        for i, n in enumerate(NS):
            for j, beta in enumerate(BETAS):
                for m, method in enumerate(METHODS):
                    row = lookup[beta, n, method]
                    assert float(row['eta']) == 1000 and float(row['gamma']) == 500
                    values[p, i, j, m] = float(row[param + '_rmse']) / (beta if p == 0 else 1000)
    distances = np.stack([abs(values[..., a] - values[..., b]) for a, b in PAIRS], axis=-1)
    assert distances.shape == (3, 5, 8, 15) and np.isfinite(distances).all()
    # The largest pair distance equals max(method RMSE) - min(method RMSE), cell by cell.
    np.testing.assert_allclose(distances.max(axis=-1), np.ptp(values, axis=-1), atol=1e-14)
    return distances


def save(fig, name):
    path = ASSETS / name
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return {'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def draw_trajectories(axes, distances):
    x = np.arange(5)
    colors = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#A97500']
    styles = ['-', '--', ':']
    markers = ['o', 's', 'D']
    for row, j in enumerate([0, 7]):
        for p, ax in enumerate(axes[row]):
            for k, (a, b) in enumerate(PAIRS):
                group = k // 5
                ax.plot(x, distances[p, :, j, k], color=colors[k % 5],
                        ls=styles[group], marker=markers[group], lw=1.3, ms=3.2,
                        alpha=.9, label=LABELS[a] + ' / ' + LABELS[b])
            ax.set_xticks(x, NS)
            ax.grid(axis='y', color='#e0e5e9', lw=.7)
            if row == 0:
                ax.set_title(SYMBOLS[p], pad=10)
            else:
                ax.set_xlabel('n')
            if p == 0:
                ax.set_ylabel(f'β = {BETAS[j]:g}\nRMSE 差距（绝对值）')
    for p in range(3):
        for row in range(2):
            axes[row, p].set_ylim(0, distances[p, :, [0, 7]].max() * 1.08)


def trajectory_figure(distances):
    """按形状分层比较n响应；六个面板复用原联合图前两行的数据。"""
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.1))
    draw_trajectories(axes, distances)
    assert len(fig.axes) == 6
    for row, j in enumerate([0, 7]):
        for p, ax in enumerate(axes[row]):
            for k, line in enumerate(ax.lines):
                np.testing.assert_array_equal(line.get_ydata(), distances[p, :, j, k])
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc='upper center',
               bbox_to_anchor=(.53, 1), ncol=5, frameon=False, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, .87), h_pad=3, w_pad=2.3)
    return save(fig, '方法差距变化_按形状分层轨迹.png')


def main():
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'font.size': 11,
                         'axes.titlesize': 15, 'axes.spines.top': False, 'axes.spines.right': False})
    distances = read_distances()
    outputs = [trajectory_figure(distances)]
    audit = dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                 subset='seven-method common valid; display six methods', n=NS, beta=BETAS,
                 distance='abs(normalized_RMSE_i - normalized_RMSE_j)',
                 display_beta=[1.5, 5], display_rows=2,
                 all_90_trajectories_checked=True,
                 methods=METHODS, pairs=PAIRS, distances=distances.tolist(), outputs=outputs)
    (SOURCE.parent / '方法差距变化核验.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'outputs': outputs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
