"""Use the original correlation criterion in report2's LRE explanation.

Read the archived pairs and plot nodes. Reconstruct three six-panel figures,
changing only the middle-column criterion from residual fraction to Pearson
correlation. Keep original samples, parameters, fit points and all other PNGs.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import re
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
IMAGES = RESULT / "报告2"
REPORT = ROOT/'报告2：小样本情况下的明显异常估计.md'
QA = DATA_DIR/'20261010-LRE相关系数判据核验.json'
DATA = DATA_DIR/'20261010-LRE相关系数曲线.csv'
LABELS = ['LRE_zero', 'LRE_left', 'LRE_right']
PRINCIPLE = r'''LRE从Weibull分布函数的线性化出发：

$$
\ln[-\ln(1-F(x))]
=\beta\ln(x-\gamma)-\beta\ln\eta.
$$

F(x)为Weibull分布函数。将第i个排序观测x₍ᵢ₎的累积概率用绘图位置pᵢ代替，得到：

$$
z_i=\ln[-\ln(1-p_i)]
\approx\beta y_i-\beta\ln\eta,
\qquad y_i=\ln(x_{(i)}-\gamma).
$$

pᵢ为按次序i和样本量n分配的累积概率，zᵢ为相应的概率图参考坐标。与LSE采用顺序统计量期望不同，这些参考点来自绘图概率的分位变换。

LRE以样本对数距离yᵢ为横坐标、zᵢ为纵坐标，拟合直线zᵢ≈a+byᵢ。斜率b直接对应形状β，截距a对应−βlnη，因此：

$$
\hat\beta(\gamma)=b,
\qquad
\hat\eta(\gamma)=e^{-a/b}.
$$

LRE通过改变γ，使样本对数距离与概率图参考坐标的线性相关性最大，位置判据为：

$$
\hat\gamma
=\underset{0\le\gamma<x_{(1)}}{\arg\max}\,\rho(\gamma).
$$

ρ(γ)为给定γ时yᵢ与zᵢ的线性相关系数。以γ为横坐标、ρ(γ)为纵坐标，曲线最高点对应LRE选择的位置估计。'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_style():
    path = HERE/'20261010-配对图参照线精简.py'
    spec = importlib.util.spec_from_file_location('archived_pair_style', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(label, pair, rows, previous, style, *, check_outer_columns=True):
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    blue, brown, gray = style.BLUE, style.BROWN, style.GRAY
    old_axes = previous['axes']
    for index, ax in enumerate(axes.ravel()):
        meta = old_axes[index]
        ax.set(xlim=meta['xlim'], xticks=meta['xticks'],
               ylim=meta['ylim'], yticks=meta['yticks'])
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 0]:
        ax.set(xlabel=r'$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$', ylabel=r'$z_i$')
    for ax in axes[:, 1]:
        ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\rho(\gamma)$',
               ylim=(.75, 1), yticks=[.75, .8, .85, .9, .95, 1])
        ax.yaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 2]:
        ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\hat\beta(\gamma)$')
    for ax in axes[:, 1:].ravel():
        ax.axvline(1, color=gray, lw=.7, ls='--', zorder=0)

    def star(ax, xx, yy):
        ax.scatter([xx], [yy], marker='*', s=58, color=brown,
                   edgecolors='white', lw=.5, zorder=6, clip_on=False)

    records, correlations, visible_points = [], {}, 0
    for row, key in enumerate(['normal', 'abnormal']):
        obj = pair[key]
        values = np.asarray(obj['values'])
        role_rows = [r for r in rows if r['example'] == label and r['role'] == obj['role']]
        fit = [r for r in role_rows if r['panel'] == 'fit_estimated']
        criterion = [r for r in role_rows if r['panel'] == 'criterion']
        assert len(fit) == obj['n']
        columns = lambda items, name: np.asarray([float(r[name]) for r in items])
        xx, zz, fitted = [columns(fit, col) for col in ['horizontal', 'vertical', 'fitted']]
        assert np.allclose(xx, np.log((values-obj['gamma_hat'])/obj['eta_true']), rtol=0, atol=1e-14)
        ax = axes[row, 0]
        ax.plot(xx, fitted, color=brown, lw=1.1)
        ax.scatter(xx, zz, s=17, color=brown, edgecolors='white', lw=.35, zorder=4)
        for i, (u, v) in enumerate(zip(xx, zz), 1):
            ax.annotate(str(i), (u, v), xytext=(8 if i%2 else -8, 0),
                        textcoords='offset points', fontsize=6,
                        ha='left' if i%2 else 'right', va='center', color='#515151')
        visible_points += len(fit)

        gs, ratios, losses, betas = [columns(criterion, col)
                                     for col in ['gamma', 'gamma_ratio', 'loss', 'beta']]
        rho = lambda gamma: float(np.corrcoef(np.log(values-gamma), zz)[0, 1])
        rs = np.asarray([rho(g) for g in gs])
        assert np.all(rs > 0)
        error = float(np.max(np.abs(rs**2-(1-losses))))
        assert error < 2e-14
        original_rho, true_rho = rho(obj['gamma_hat']), rho(obj['gamma_true'])
        assert abs(original_rho**2-obj['at_original']['r2']) < 2e-14
        # The maximum of rho corresponds to the minimum of the archived loss.
        assert rs.max()-rs[np.argmin(losses)] < 2e-14
        axes[row, 1].plot(ratios, rs, color=blue, lw=1.15)
        star(axes[row, 1], obj['gamma_hat']/obj['gamma_true'], original_rho)
        axes[row, 2].plot(ratios, betas, color=blue, lw=1.15)
        axes[row, 2].axhline(obj['beta_true'], color=gray, lw=.7, ls='--')
        star(axes[row, 2], obj['gamma_hat']/obj['gamma_true'], obj['beta_hat'])
        axes[row, 0].set_title(obj['role']+f" · 第{obj['group']}组", loc='left', pad=14, fontsize=9)
        correlations[key] = dict(true=true_rho, original=original_rho,
                                 maximum_rho_squared_error=error, group=obj['group'])
        records += [dict(example=label, role=obj['role'], group=obj['group'],
                         gamma=float(g), gamma_ratio=float(ratio), rho=float(r), beta=float(b))
                    for g, ratio, r, b in zip(gs, ratios, rs, betas)]

    for index, ax in enumerate(axes.ravel()):
        ax.text(-.16, 1.04, chr(97+index), transform=ax.transAxes, fontweight='bold', fontsize=11)
    legend = [Line2D([0], [0], color=brown, marker='o', ms=3, ls='none', label='样本点'),
              Line2D([0], [0], color=brown, lw=1, label='拟合直线'),
              Line2D([0], [0], marker='*', color=brown, ls='none', ms=7, label='原估计')]
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.52, .015), ncol=3, fontsize=8)
    fig.subplots_adjust(left=.08, right=.985, bottom=.14, top=.91, wspace=.39, hspace=.48)
    fig.canvas.draw()
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(fig.canvas.get_renderer())
            assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.x1+1 and box.y1 <= fig.bbox.y1+1
    metadata = [{k: [float(value) for value in getattr(ax, 'get_'+k)()]
                 for k in ['xlim', 'ylim', 'xticks', 'yticks']} for ax in axes.ravel()]
    assert all(metadata[col] == metadata[col+3] for col in range(3))
    assert all(metadata[index] == old_axes[index] for index in [0, 2, 3, 5])
    path = IMAGES/f'配对情形_{label}.png'
    old_image = np.asarray(Image.open(path).convert('RGB'))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        from 共用 import save_png
        save_png(fig, path, dpi=400)
    plt.close(fig)
    assert not any('Glyph' in str(w.message) for w in caught)
    image = np.asarray(Image.open(path).convert('RGB'))
    assert image.shape == old_image.shape == (2280, 3840, 3)
    # Fixed subplot positions let us compare the unaffected outer columns directly.
    if check_outer_columns:
        assert np.array_equal(image[:, :1280], old_image[:, :1280])
        assert np.array_equal(image[:, 2630:], old_image[:, 2630:])
    return dict(path=str(path), sha256=digest(path), axes=metadata, panels=6,
                correlations=correlations, fit_points=visible_points,
                outer_columns_pixel_identical=check_outer_columns, all_labels_within_canvas=True), records
