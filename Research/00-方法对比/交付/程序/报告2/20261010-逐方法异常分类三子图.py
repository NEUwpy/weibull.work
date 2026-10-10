"""Place one three-panel anomaly heatmap in each of the six method sections.

The 624 source counts and original estimates remain unchanged. Each method
figure shares the thirteen parameter rows across n=7,15,30, with its own case
columns. This task saves a dedicated script and hash-bound verification.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import csv
import hashlib
import json
import re
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
IMAGES = RESULT / "报告2"
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
QA = DATA_DIR / '20261010-逐方法异常分类三子图核验.json'
NS = [7, 15, 30]
METHODS = ['LSE', 'LRE', 'MLE', 'MDM δ=0.20', 'WMLE', 'MMLE']
PRINCIPLES = [('LSE先将Weibull变量', 'LSE以标准对数Weibull顺序统计量', 'LSE通过调整γ'),
              ('LRE从Weibull分布函数', 'LRE按观测次序', 'LRE拟合的Weibull关系为'), 'MLE同时搜索形状',
              'MDM先在每个候选γ', 'WMLE用两条校准方程', 'MMLE直接用样本最小值']
DISPLAY_NOTE = '分类热力图显示各类异常的发生次数，空白格为0。'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def filename(method):
    return '异常分类_' + method.split(' δ=')[0] + '_三子图.png'


def render(method, matrices, cases, combinations):
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
        'font.size': 10.5, 'axes.unicode_minus': False,
    })
    cmap = LinearSegmentedColormap.from_list(
        'restrained_blue', ['#ffffff', '#e0edf5', '#a8cbdc', '#5d95b3', '#255d7b'])
    fig = plt.figure(figsize=(11.8, 6.6), facecolor='white')
    axes = [fig.add_axes([0.175+i*0.248, 0.205, 0.23, 0.695]) for i in range(3)]
    cax = fig.add_axes([0.939, 0.205, 0.013, 0.695])
    labels, displayed = [], []
    for panel, (ax, n) in enumerate(zip(axes, NS)):
        matrix = matrices[str(n)]
        artist = ax.imshow(matrix, cmap=cmap, norm=Normalize(0, 25),
                           aspect='auto', interpolation='nearest')
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels([c['label'] for c in cases], fontsize=10, rotation=33,
                           ha='right', rotation_mode='anchor')
        ax.set_yticks(range(13))
        ax.set_yticklabels(combinations if panel == 0 else ['']*13, fontsize=10)
        ax.tick_params(axis='both', length=0, pad=6)
        ax.set_xticks(np.arange(-0.5, len(cases), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 13, 1), minor=True)
        ax.grid(which='minor', color='#e5e9ec', linewidth=0.45)
        ax.tick_params(which='minor', bottom=False, left=False)
        for spine in ax.spines.values():
            spine.set_color('#d6dde1'); spine.set_linewidth(0.6)
        for y, x in zip(*np.nonzero(matrix)):
            value = int(matrix[y, x])
            text = ax.text(x, y, str(value), ha='center', va='center', fontsize=11,
                           color='white' if value >= 17 else '#263746')
            assert text.get_text() == str(value)
            displayed.append(dict(n=n, row=int(y), column=int(x), count=value))
        title = ax.set_title(f'n = {n}', fontsize=12, pad=12)
        letter = ax.text(-0.025, 1.035, 'abc'[panel], transform=ax.transAxes,
                         ha='left', va='bottom', fontsize=13, fontweight='bold')
        labels += [*ax.get_xticklabels(), *ax.get_yticklabels(), title, letter]
        assert np.array_equal(ax.get_images()[0].get_array(), matrix)
    bar = fig.colorbar(artist, cax=cax, ticks=[0, 5, 10, 15, 20, 25])
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, pad=5, labelsize=10)
    labels += [*bar.ax.get_yticklabels(), bar.ax.set_title('次数', fontsize=10, pad=10)]
    if method.startswith('MDM'):
        labels.append(fig.text(0.52, 0.972, 'δ=0.20', ha='center', fontsize=10.5))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in labels if t.get_text()]
    assert all(b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.x1 and b.y1 <= fig.bbox.y1
               for b in boxes), f'{method}: label outside canvas'
    for ax in axes:
        assert ax.get_ylim() == (12.5, -0.5) and ax.get_xlim() == (-0.5, len(cases)-0.5)
        assert ax.get_images()[0].get_clim() == (0.0, 25.0)
    output = IMAGES/filename(method)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(output, dpi=400, facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught), 'Missing font glyph'
    plt.close(fig)
    with Image.open(output) as image:
        assert image.format == 'PNG' and image.size == (4720, 2640)
    return dict(method=method, path=str(output), sha256=digest(output), pixels=[4720,2640],
                case_order=cases, parameter_order=combinations,
                matrices={n:m.tolist() for n,m in matrices.items()},
                counts_by_n={n:int(matrices[str(n)].sum()) for n in NS},
                color_limits=[0,25], color_ticks=[0,5,10,15,20,25],
                visible_cells=displayed, all_labels_within_canvas=True)
