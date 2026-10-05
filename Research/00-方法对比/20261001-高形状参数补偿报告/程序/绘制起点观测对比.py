"""Figure 2: theoretical densities and minima of the saved paired samples.

Run with the project Python. Only a PNG is delivered; source and checks stay here.
No sampling or parameter estimation is performed.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import weibull_min

sys.path.append('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / '结果' / '中间数据' / '样本.json'
FIGURE = ROOT / '结果' / '图2_起点附近观测.png'
RECORD = HERE / '起点观测绘图数据.json'
COLORS = {2: '#345D7E', 5: '#B27448'}
X_LIMITS = [400., 3000.]
X_TICKS = [500., 1000., 1500., 2000., 2500., 3000.]
ETA, GAMMA = 1000., 500.


def density(t, beta):
    y = np.zeros_like(t)
    mask = t > GAMMA
    z = (t[mask] - GAMMA) / ETA
    y[mask] = beta / ETA * z ** (beta - 1) * np.exp(-z ** beta)
    return y


def source_data():
    samples = json.loads(SOURCE.read_text(encoding='utf-8'))
    t = np.linspace(*X_LIMITS, 1301)
    curves = []
    for beta in (2, 5):
        y = density(t, beta)
        assert np.allclose(y, weibull_min.pdf(t, beta, loc=GAMMA, scale=ETA), rtol=1e-13, atol=1e-18)
        curves.append({'beta': beta, 't': t.tolist(), 'density': y.tolist()})
    rows = []
    for n, center in ((7, 3.), (15, 1.)):
        for beta, offset in ((2, .2), (5, -.2)):
            selected = sorted((s for s in samples if s['beta'] == beta and s['n'] == n),
                              key=lambda s: s['sample_id'])
            assert [s['sample_id'] for s in selected] == list(range(1, 51))
            minima = [min(s['observations']) for s in selected]
            assert all(len(s['observations']) == n for s in selected)
            assert all(X_LIMITS[0] <= value <= X_LIMITS[1] for value in minima)
            rows.append({'beta': beta, 'n': n, 'sample_ids': [s['sample_id'] for s in selected],
                         'minimum_observations': minima, 'y_position': center + offset})
        first = [s for s in samples if s['beta'] == 2 and s['n'] == n]
        second = {s['sample_id']: s for s in samples if s['beta'] == 5 and s['n'] == n}
        for s in first:
            e2 = ((np.array(s['observations']) - GAMMA) / ETA) ** 2
            e5 = ((np.array(second[s['sample_id']]['observations']) - GAMMA) / ETA) ** 5
            assert np.allclose(e2, e5, rtol=1e-12, atol=1e-12)
    return curves, rows


def main():
    curves, rows = source_data()
    plt.rcParams.update({'font.family': 'sans-serif',
                         'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 7, 'axes.labelsize': 7, 'axes.titlesize': 7,
                         'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
                         'axes.linewidth': .7, 'axes.spines.right': False,
                         'axes.spines.top': False, 'axes.unicode_minus': False,
                         'legend.fontsize': 7, 'legend.frameon': False})
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), sharex=True)
    for curve in curves:
        axes[0].plot(curve['t'], curve['density'], color=COLORS[curve['beta']], lw=1.4)
    axes[0].set_ylim(0., .0022)
    axes[0].set_yticks([0., .001, .002], ['0', '0.001', '0.002'])
    axes[0].set_ylabel(r'$f(t)$')
    axes[0].set_title('理论密度', loc='left', pad=9)
    for row in rows:
        axes[1].scatter(row['minimum_observations'],
                        np.full(50, row['y_position']), s=13,
                        color=COLORS[row['beta']], alpha=.55, linewidths=0)
    axes[1].set_ylim(.35, 3.65)
    axes[1].set_yticks([3., 1.], [r'$n=7$', r'$n=15$'])
    axes[1].tick_params(axis='y', length=0)
    axes[1].spines['left'].set_visible(False)
    axes[1].set_title('样本最小值', loc='left', pad=9)
    for ax, letter in zip(axes, ('a', 'b')):
        ax.axvline(GAMMA, color='.25', ls='--', lw=.8, zorder=0)
        ax.set_xlim(X_LIMITS)
        ax.set_xticks(X_TICKS)
        ax.set_xlabel(r'寿命 $t$' if ax is axes[0] else r'最小观测 $t_1$')
        ax.text(-.15, 1.065, letter, transform=ax.transAxes, fontsize=8, weight='bold')
    handles = [Line2D([], [], color=COLORS[b], lw=1.4, label=rf'$\beta={b}$') for b in (2, 5)]
    handles.append(Line2D([], [], color='.25', ls='--', lw=.8, label=r'$\gamma=500$'))
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.53, .99), ncol=3,
               columnspacing=2.2, handlelength=2.)
    fig.subplots_adjust(left=.09, right=.985, top=.77, bottom=.22, wspace=.29)
    settings = [{'x_limits': list(ax.get_xlim()), 'x_ticks': ax.get_xticks().tolist(),
                 'x_scale': ax.get_xscale()} for ax in axes]
    assert settings[0] == settings[1]
    fig.savefig(FIGURE, dpi=450, facecolor='white')
    plt.close(fig)
    record = {'figure': FIGURE.relative_to(ROOT).as_posix(),
              'source_path': SOURCE.relative_to(ROOT).as_posix(),
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'true_scale': ETA, 'true_location': GAMMA,
              'density_formula': 'beta/eta*((t-gamma)/eta)**(beta-1)*exp(-((t-gamma)/eta)**beta)',
              'density_curves': curves, 'sample_minimum_rows': rows,
              'samples': 200, 'omitted_sample_minima': 0,
              'same_latent_samples_verified': True,
              'independent_scipy_density_check': True,
              'axis_settings': settings, 'formats': ['png'], 'dpi': 450,
              'png_dimensions': [3240, 1215], 'new_samples': 0, 'new_fits': 0}
    if RECORD.exists():
        previous = json.loads(RECORD.read_text(encoding='utf-8'))
        key = 'existing_exports_renumbered_without_redrawing'
        if key in previous:
            record[key] = previous[key]
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'png': str(FIGURE), 'sample_minima': 200, 'new_samples': 0,
                      'new_fits': 0, 'matching_linear_axes': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
