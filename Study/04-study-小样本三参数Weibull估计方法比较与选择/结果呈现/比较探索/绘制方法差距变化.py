"""直接展示六种常规量级方法的RMSE两两距离及变化；读取七法共同有效指标。"""
from pathlib import Path
from itertools import combinations
import csv
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

STUDY = Path(__file__).resolve().parents[2]
SOURCE = STUDY / '结果呈现/分析数据/参数指标.csv'
ASSETS = STUDY / 'reviewbyhtml/方法对比-v1.0/assets'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)']
LABELS = ['MDM', 'LSE', 'LRE', 'WMLE', 'MLE', 'K–R']
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


def trajectories(distances):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey='col')
    x = np.arange(5)
    for row, j in enumerate([0, 7]):
        for p, ax in enumerate(axes[row]):
            for k in range(15):
                ax.plot(x, distances[p, :, j, k], color='#9aaab7', lw=.8, alpha=.65)
            ax.plot(x, np.median(distances[p, :, j], axis=-1), color='#0072B2', lw=2.4, marker='o', ms=4)
            ax.set_xticks(x, NS)
            ax.grid(axis='y', color='#e0e5e9', lw=.7)
            if row == 0:
                ax.set_title(SYMBOLS[p], pad=10)
            else:
                ax.set_xlabel('n')
            if p == 0:
                ax.set_ylabel(f'β = {BETAS[j]:g}\nPairwise RMSE distance')
    for p in range(3):
        axes[0, p].set_ylim(0, distances[p, :, [0, 7]].max() * 1.08)
    fig.legend(handles=[Line2D([], [], color='#9aaab7', lw=1, label='15 method pairs'),
                        Line2D([], [], color='#0072B2', lw=2.4, marker='o', label='Median pair distance')],
               loc='upper center', bbox_to_anchor=(.5, 1.02), ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .96), h_pad=2)
    return save(fig, '方法差距变化_A_距离轨迹.png')


def pair_change_maps(distances):
    change = distances[:, -1] - distances[:, 0]
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.6))
    labels = [LABELS[a] + ' / ' + LABELS[b] for a, b in PAIRS]
    for p, ax in enumerate(axes):
        vmax = float(abs(change[p]).max())
        img = ax.imshow(change[p].T, cmap='RdBu_r', vmin=-vmax, vmax=vmax, aspect='auto')
        ax.set_title(SYMBOLS[p], pad=12)
        ax.set_xticks(range(8), [f'{x:g}' for x in BETAS])
        ax.set_xlabel('β')
        ax.set_yticks(range(15), labels if p == 0 else [])
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        bar = fig.colorbar(img, ax=ax, fraction=.045, pad=.035)
        bar.ax.set_ylabel('Distance(n=7) − Distance(n=50)')
    fig.tight_layout(w_pad=2.4)
    return save(fig, '方法差距变化_B_逐对变化.png')


def change_maps(distances):
    median = np.median(distances, axis=-1)
    change = median[:, 1:] - median[:, :1]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    for p, ax in enumerate(axes):
        vmax = float(abs(change[p]).max())
        img = ax.imshow(change[p], cmap='RdBu_r', vmin=-vmax, vmax=vmax, aspect='auto')
        ax.set_title(SYMBOLS[p], pad=12)
        ax.set_xticks(range(8), [f'{x:g}' for x in BETAS])
        ax.set_yticks(range(4), NS[1:])
        ax.set_xlabel('β')
        if p == 0:
            ax.set_ylabel('n')
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        bar = fig.colorbar(img, ax=ax, fraction=.045, pad=.035)
        bar.ax.set_ylabel('Median distance(n) − Median distance(n=50)')
    fig.tight_layout(w_pad=2.3)
    return save(fig, '方法差距变化_C_距离变化全图.png')


def main():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.titlesize': 15, 'axes.spines.top': False, 'axes.spines.right': False})
    distances = read_distances()
    outputs = [trajectories(distances), pair_change_maps(distances), change_maps(distances)]
    audit = dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                 subset='seven-method common valid; display six methods', n=NS, beta=BETAS,
                 distance='abs(normalized_RMSE_i - normalized_RMSE_j)',
                 methods=METHODS, pairs=PAIRS, distances=distances.tolist(), outputs=outputs)
    (SOURCE.parent / '方法差距变化核验.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'outputs': outputs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
