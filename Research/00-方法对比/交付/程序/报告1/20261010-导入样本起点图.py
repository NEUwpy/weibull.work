"""Show all saved observations and their distance from the true support endpoint.

This revision uses the existing paired samples; it generates no samples or fits.
"""
from 共用 import RESULT, PROGRAM, ROOT as RESEARCH_ROOT
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.append('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = (RESULT / '报告1') / '中间数据' / '样本.json'
FIGURE = (RESULT / '报告1') / '图2_样本与真实起点.png'
RECORD = RESULT / '报告1/中间数据/20261010-导入样本起点图.json'
ARCHIVE = HERE / '历史图' / '20261010-原下尾统计图'
OLD_NAME = '补充图3_下尾观测对照'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(extra_samples=None, extra_provenance=None, minimum_distributions=False):
    before = digest(SOURCE)
    samples = json.loads(SOURCE.read_text(encoding='utf-8'))
    if extra_samples:
        samples.extend(extra_samples)
    ns = sorted({r['n'] for r in samples if r['beta'] in (2., 5.)})
    index = {(r['beta'], r['n'], r['sample_id']): r for r in samples}
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
        'font.size': 7, 'axes.titlesize': 8, 'axes.labelsize': 7,
        'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.linewidth': .7, 'axes.unicode_minus': False,
        'legend.frameon': False,
    })
    plot_rows = len(ns) + int(bool(minimum_distributions))
    height = 2.3 * plot_rows + .3
    fig, axes = plt.subplots(plot_rows, 2, figsize=(7.2, height))
    panels = []
    for row, n in enumerate(ns):
        order = sorted(range(1, 51), key=lambda sid: (index[2., n, sid]['observations'][0], sid))
        for col, beta in enumerate((2., 5.)):
            ax = axes[row, col]
            records = []
            xx, yy = [], []
            for rank, sid in enumerate(order, 1):
                x = np.array(index[beta, n, sid]['observations'])
                latent = ((x - 500.) / 1000.) ** beta
                low = np.array(index[2., n, sid]['observations'])
                assert np.allclose(latent, ((low - 500.) / 1000.) ** 2., rtol=1e-10, atol=1e-12)
                assert len(x) == n and np.all(np.diff(x) >= 0) and np.all(x > 500.)
                ax.hlines(rank, 500., x[0], colors='#D3DAE0', lw=.65, zorder=1)
                xx.extend(x[1:].tolist())
                yy.extend([rank] * (n - 1))
                records.append({'rank': rank, 'sample_id': sid,
                                'observations': x.tolist(), 'minimum': float(x[0])})
            others = ax.scatter(xx, yy, s=3, color='#426981', linewidths=0, zorder=3)
            minima = ax.scatter([r['minimum'] for r in records], range(1, 51),
                                s=8, color='#C27F45', linewidths=0, zorder=4)
            assert np.array_equal(others.get_offsets(), np.column_stack([xx, yy]))
            assert np.array_equal(minima.get_offsets()[:, 0], [r['minimum'] for r in records])
            ax.axvline(500., color='#444444', ls='--', lw=.85, zorder=2)
            ax.set_xlim(450., 3500.)
            ax.set_ylim(50.8, .2)
            ax.set_xticks([500, 1000, 1500, 2000, 2500, 3000, 3500])
            ax.set_yticks([1, 25, 50])
            ax.tick_params(labelbottom=row == len(ns)-1, labelleft=col == 0)
            ax.set_title(f'β = {int(beta)}, n = {n}', loc='left', pad=8)
            ax.text(-.09, 1.08, chr(97 + row * 2 + col), transform=ax.transAxes,
                    fontsize=8, fontweight='bold')
            if row == len(ns) - 1:
                ax.set_xlabel('寿命 t')
            if col == 0:
                ax.set_ylabel('排序序号')
            panels.append({'beta': beta, 'n': n, 'groups': 50,
                           'observations_shown': 50 * n, 'rows': records,
                           'x_limits': list(ax.get_xlim()), 'y_limits': list(ax.get_ylim()),
                           'x_ticks': ax.get_xticks().tolist(), 'y_ticks': ax.get_yticks().tolist(),
                           'x_scale': ax.get_xscale(), 'y_scale': ax.get_yscale(),
                           'median_minimum': float(np.median([r['minimum'] for r in records]))})
    distribution_panels = []
    if minimum_distributions:
        assert ns == [7, 15, 30]
        theoretical = minimum_distributions == 'theoretical'
        edges = np.arange(500., 1500. + 50., 50.)
        density_grid = np.linspace(450., 1700., 1251)
        colors = {7: '#426981', 15: '#C27F45', 30: '#4E8C79'}
        styles = {7: ':', 15: '--', 30: '-'}
        for col, beta in enumerate((2., 5.)):
            ax = axes[-1, col]
            series = []
            for n in ns:
                raw = [float(index[beta, n, sid]['observations'][0]) for sid in range(1, 51)]
                item = {'n': n, 'groups': 50, 'sample_ids': list(range(1,51)),
                        'minima': raw, 'median_minimum': float(np.median(raw)),
                        'color': colors[n], 'line_style': styles[n]}
                if theoretical:
                    distance = np.maximum((density_grid - 500.) / 1000., 0.)
                    density = n * beta / 1000. * distance ** (beta - 1.) * np.exp(-n * distance ** beta)
                    curve, = ax.plot(density_grid, density, color=colors[n], ls=styles[n],
                                     lw=1.2, label=f'n = {n}', zorder=3)
                    ax.fill_between(density_grid, 0., density, color=colors[n], alpha=.06, linewidth=0)
                    assert np.array_equal(curve.get_xdata(), density_grid)
                    assert np.array_equal(curve.get_ydata(), density)
                    item.update(grid=density_grid.tolist(), density=density.tolist(),
                                minimum_scale=1000.*n**(-1./beta),
                                theoretical_median=500.+1000.*(np.log(2.)/n)**(1./beta))
                else:
                    counts, _ = np.histogram(raw, bins=edges)
                    assert int(counts.sum()) == len(raw) == 50
                    frequency = 100. * counts / len(raw)
                    stairs = ax.stairs(frequency, edges, color=colors[n], ls=styles[n],
                                       lw=1., label=f'n = {n}', zorder=3)
                    actual = stairs.get_data()
                    assert np.array_equal(actual.values, frequency) and np.array_equal(actual.edges, edges)
                    item.update(bin_counts=counts.tolist(), bin_frequency_percent=frequency.tolist())
                series.append(item)
            ax.axvline(500., color='#444444', ls='--', lw=.85, zorder=2)
            ax.set_xlim(450., 1700. if theoretical else 1500.)
            ax.set_ylim(0., .0052 if theoretical else 30.)
            ax.set_xticks([500, 750, 1000, 1250, 1500])
            ax.set_yticks([0., .002, .004] if theoretical else [0, 10, 20, 30])
            ax.tick_params(labelleft=col == 0)
            ax.set_title(f'β = {int(beta)}', loc='left', pad=8)
            ax.text(-.09, 1.08, chr(97+len(ns)*2+col), transform=ax.transAxes,
                    fontsize=8, fontweight='bold')
            ax.set_xlabel(r'最小观测 $t_1$')
            if col == 0:
                ax.set_ylabel('概率密度' if theoretical else '频率 (%)')
            else:
                ax.legend(loc='upper right', fontsize=6.5, handlelength=2.5,
                          labelspacing=.35, borderaxespad=.25)
            distribution_panels.append({'beta': beta, 'label': chr(97+len(ns)*2+col),
                                        'source_kind': 'analytic_minimum_distribution' if theoretical else 'empirical_histogram',
                                        'bin_edges': None if theoretical else edges.tolist(),
                                        'bin_width': None if theoretical else 50.,
                                        'curve_formula': 'n*(1-F(t))**(n-1)*f(t)' if theoretical else None,
                                        'series': series, 'no_omitted_minima': True,
                                        'smoothing': False,
                                        'x_limits': list(ax.get_xlim()), 'y_limits': list(ax.get_ylim()),
                                        'x_ticks': ax.get_xticks().tolist(), 'y_ticks': ax.get_yticks().tolist(),
                                        'x_scale': ax.get_xscale(), 'y_scale': ax.get_yscale()})
    handles = [
        Line2D([], [], marker='o', ls='', ms=2.5, color='#426981', label='观测'),
        Line2D([], [], marker='o', ls='', ms=3, color='#C27F45', label='最小观测'),
        Line2D([], [], color='#D3DAE0', lw=1.5, label='起点至最小观测'),
        Line2D([], [], color='#444444', ls='--', lw=.85, label='真实 γ = 500'),
    ]
    fig.legend(handles=handles, ncol=4, loc='upper center', bbox_to_anchor=(.53, .994),
               fontsize=6.5, columnspacing=1.4, handletextpad=.55)
    fig.subplots_adjust(left=.085, right=.985, bottom=.4655/height,
                        top=1-.588/height, hspace=.36, wspace=.15)
    fig.savefig(FIGURE, dpi=450, facecolor='white')
    plt.close(fig)
    assert digest(SOURCE) == before
    observations_shown = sum(p['observations_shown'] for p in panels)
    assert observations_shown == 100 * sum(ns)
    assert all(450. <= t <= 3500. for p in panels for r in p['rows'] for t in r['observations'])
    retired = []
    record = {
        'task': '2026-10-10: direct observation comparison for the chapter 2 opening',
        'claim': 'Higher beta leaves more space between the true endpoint and the sample minimum.',
        'source': SOURCE.name, 'source_sha256': before,
        'new_samples': 50 if extra_samples else 0, 'new_random_draws': 0, 'new_fits': 0,
        'sample_groups': 100*len(ns), 'observations_shown': observations_shown,
        'row_order': 'Ascending minimum at beta=2 within n; beta=5 uses the same sample ids.',
        'across_n_paired': False, 'no_omitted_observations': True,
        'figure': FIGURE.name, 'formats': ['png'],
        'observation_axes_linear_and_shared': True, 'panels': panels,
        'minimum_distribution_panels': distribution_panels,
        'minimum_distribution_axes_linear_and_shared': bool(distribution_panels),
        'total_panel_count': len(panels)+len(distribution_panels),
        'png_dimensions': [round(7.2*450), round(height*450)],
        'retired_figures': retired, 'dpi': 450,
    }
    if extra_provenance:
        record['n30_provenance'] = extra_provenance
    record_path = (RESULT / '报告1/中间数据/20261010-图2最小值密度曲线.json' if minimum_distributions == 'theoretical' else
                   HERE / '20261010-图2补最小值分布.json' if minimum_distributions else
                   HERE / '20261010-导入图补入n30.json' if extra_samples else RECORD)
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'EXPORTED: {100*len(ns)} groups, all {observations_shown} observations, '
          f'{len(panels)} observation panels + {len(distribution_panels)} minimum distributions, PNG only.')
