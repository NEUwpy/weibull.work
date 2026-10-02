"""Shared plotting helpers; Figure 1 uses 绘制图1小提琴.py, methods use 绘制公式与拟合点图.py."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from 计算逐法过程曲线 import mother
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / '结果'
DATA = OUT / '中间数据'
METHODS = ['mdm', 'lse', 'lre', 'wmle', 'mle']
NAMES = dict(mdm='MDM', lse='LSE', lre='LRE', wmle='WMLE', mle='MLE')
COLORS = dict(mdm='#345D7E', lse='#589CA3', lre='#8A7398', wmle='#B27448', mle='#5F6570')
STYLES = ['-', '--', '-.', (0, (5, 2, 1, 2)), ':']
BLUE, RETURN = '#345D7E', '#B55E3E'
CONDITIONS = [(2, 7), (5, 7), (2, 15), (5, 15)]
FILES = dict(mdm='图2_MDM六格机制', lse='图3_LSE六格机制', lre='图4_LRE六格机制',
             wmle='图5_WMLE六格机制', mle='图6_MLE六格机制')
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
    'font.size': 7, 'axes.titlesize': 7.2, 'axes.labelsize': 7, 'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.linewidth': .7,
    'axes.spines.right': False, 'axes.spines.top': False, 'axes.unicode_minus': False,
    'pdf.fonttype': 42, 'svg.fonttype': 'none', 'legend.frameon': False})
source = json.loads((DATA / '逐法过程曲线.json').read_text(encoding='utf-8'))
old = json.loads((HERE / '输入快照' / '原案例估计.json').read_text(encoding='utf-8'))


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        path = OUT / f'{name}.{ext}'
        fig.savefig(path, dpi=450, facecolor='white')
        if ext == 'svg':
            # XML attribute whitespace is immaterial; keep Git diffs clean.
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)


def tag(ax, label):
    ax.text(-.13, 1.10, label, transform=ax.transAxes, fontsize=8, weight='bold')




def format_axis(ax, method, xmax, original=False):
    ax.set_xlim(-25, xmax)
    ax.set_xlabel('γ')
    ax.axvline(500, color='black', ls=':', lw=.9, zorder=3)
    ax.set_xticks([0, 500, 1000])
    if method in ('lse', 'lre'):
        ax.set_yscale('log'); ax.set_ylim(.001, 1.)
        ax.set_ylabel(r'$D(\gamma)$')
    elif method == 'mdm':
        ax.set_ylim((-.04, .23) if original else (-.46, 1.10))
        ax.axhline(.1, color='black', ls='--', lw=.85)
        ax.set_ylabel(r'$g(\gamma)$')
    else:
        ax.axhline(0, color='black', ls='--', lw=.85)
        if method == 'wmle':
            ax.set_ylim((-.32, .13) if original else (-.13, .13))
        else:
            ax.set_ylim((-.05, .035) if original else (-.25, .27))
        ax.set_ylabel(r'$T_2(\gamma)$' if method == 'wmle' else r'$1000\,U_\gamma/n$')


def draw_curve(ax, r, color, alpha, lw, method):
    pp = np.array([[p[0], np.nan if p[1] is None else p[1]] for p in r['points']])
    if method == 'wmle':
        ordinary = [p[1] if p[1] is not None and not p[4] else np.nan for p in r['points']]
        ax.plot(pp[:, 0], ordinary, color=color, alpha=alpha, lw=lw, zorder=1)
        clamp = [p[1] if p[4] else np.nan for p in r['points']]
        ax.plot(pp[:, 0], clamp, color=color, ls=(0, (2, 2)), alpha=alpha, lw=lw + .1)
    else:
        ax.plot(pp[:, 0], pp[:, 1], color=color, alpha=alpha, lw=lw, zorder=1)
    truth = r['truth']
    if truth is not None and truth[1] is not None:
        ax.scatter(500, truth[1], s=5 if alpha < .9 else 14, color=color, alpha=max(.35, alpha), linewidths=0, zorder=3)
    if r['fit']['converged']:
        g = r['fit']['gamma_hat']
        p = r['returned']
        if p is not None and p[1] is not None:
            ax.scatter(g, p[1], s=11 if alpha < .9 else 26, color=RETURN, alpha=.65 if alpha < .9 else 1,
                       marker='x', lw=.8, zorder=4)
        # Rug preserves every returned gamma even when the conditional y is outside the zoom.
        ax.plot(g, .018, marker='|', color=RETURN, ms=6, alpha=.55 if alpha < .9 else 1,
                transform=ax.get_xaxis_transform(), clip_on=True, zorder=5)







def main():
    from 绘制图1小提琴 import main as draw_violin
    draw_violin()


if __name__ == '__main__':
    main()
