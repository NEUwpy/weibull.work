"""Figure 2: two specified Weibull CDFs and one archived seven-point sample.

Reuse the median-location MDM example already used in Figure 8. This entry
does not generate samples or fit parameters. Deliver PNG only; keep source
values, selection provenance and checks beside the program.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import weibull_min

from 绘制寿命对照图 import cdf, select_example, plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGURE = ROOT / '结果' / '图2_样本与分布相容.png'
RECORD = HERE / '样本相容绘图数据.json'
TRUTH = (5., 1000., 500.)
COMPARISON = (2., 500., 1000.)
X_LIMITS = [500., 2200.]
X_TICKS = [500., 1000., 1500., 2000.]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_data():
    observations, positions, fitted, provenance = select_example()
    assert len(observations) == len(positions) == 7
    assert np.all(np.diff(observations) > 0)
    t = np.linspace(*X_LIMITS, 1701)
    curves = []
    for parameters in (TRUTH, COMPARISON):
        beta, eta, gamma = parameters
        values = cdf(t, parameters)
        independent = weibull_min.cdf(t, beta, loc=gamma, scale=eta)
        assert np.allclose(values, independent, rtol=1e-13, atol=1e-15)
        curves.append({'parameters_beta_eta_gamma': list(parameters),
                       't': t.tolist(), 'cdf': values.tolist(),
                       'cdf_at_observations': cdf(observations, parameters).tolist()})
    observed_grid = np.linspace(observations.min(), observations.max(), 10001)
    return {
        'cdf_formula': '1-exp(-((t-gamma)/eta)**beta) for t>gamma; 0 otherwise',
        'curves': curves,
        'observations': observations.tolist(),
        'plotting_positions': positions.tolist(),
        'plotting_position_rule': provenance['plotting_position_rule'],
        'actual_fit_parameters_beta_eta_gamma': list(fitted),
        'sample_id': provenance['sample_id'], 'n': provenance['n'],
        'sample_selection_rule': provenance['selection_rule'],
        'sample_selection_pool_size': provenance['selection_pool_size'],
        'gamma_pool_median': provenance['gamma_pool_median'],
        'sample_regeneration_max_error': provenance['sample_regeneration_max_error'],
        'max_cdf_difference_on_observed_interval': float(np.max(np.abs(
            cdf(observed_grid, TRUTH) - cdf(observed_grid, COMPARISON)))),
        'source_hashes': {
            ('程序/输入快照/' + name): value
            for name, value in provenance['input_hashes'].items()
        } | {'程序/绘制寿命对照图.py': digest(HERE / '绘制寿命对照图.py')},
        'independent_scipy_cdf_check': True,
        'claim_limit': 'One archived sample illustrates finite-sample compatibility; '
                       'the two distributions are different and their tails differ.',
        'new_samples': 0, 'new_fits': 0,
    }


def main():
    record = source_data()
    plt.rcParams.update({'font.size': 8, 'axes.labelsize': 8,
                         'xtick.labelsize': 7, 'ytick.labelsize': 7,
                         'legend.fontsize': 7, 'legend.frameon': False})
    fig, ax = plt.subplots(figsize=(4.8, 3.1))
    for curve, color, style, label in zip(
            record['curves'], ('#345D7E', '#B27448'), ('-', '--'),
            (r'$W(5,1000,500)$', r'$W(2,500,1000)$')):
        ax.plot(curve['t'], curve['cdf'], color=color, ls=style,
                lw=1.4, label=label)
    ax.scatter(record['observations'], record['plotting_positions'],
               s=22, c='#33383D', edgecolors='white', linewidths=.5,
               zorder=3, label='样本')
    ax.set_xlim(X_LIMITS)
    ax.set_xticks(X_TICKS)
    ax.set_ylim(0., 1.)
    ax.set_yticks([0., .2, .4, .6, .8, 1.])
    ax.set_xlabel(r'寿命 $t$')
    ax.set_ylabel(r'累计概率 $F(t)$')
    ax.legend(loc='upper left', borderaxespad=1., handlelength=2.2,
              labelspacing=.8)
    fig.subplots_adjust(left=.15, right=.97, bottom=.18, top=.97)
    record.update({
        'figure': FIGURE.relative_to(ROOT).as_posix(),
        'axis_settings': {'x_limits': list(ax.get_xlim()),
                          'x_ticks': ax.get_xticks().tolist(),
                          'y_limits': list(ax.get_ylim()),
                          'y_ticks': ax.get_yticks().tolist(),
                          'x_scale': ax.get_xscale(), 'y_scale': ax.get_yscale()},
        'formats': ['png'], 'dpi': 450, 'png_dimensions': [2160, 1395],
        'plotted_curve_count': len(ax.lines), 'plotted_sample_point_count': 7,
        'extra_annotation_count': len(ax.texts),
    })
    assert len(ax.lines) == 2 and not ax.texts
    fig.savefig(FIGURE, dpi=450, facecolor='white')
    plt.close(fig)
    if RECORD.exists():
        previous = json.loads(RECORD.read_text(encoding='utf-8'))
        key = 'existing_exports_renumbered_without_redrawing'
        if key in previous:
            record[key] = previous[key]
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8')
    print(json.dumps({'png': str(FIGURE), 'sample_id': record['sample_id'],
                      'sample_points': 7, 'curves': 2,
                      'new_samples': 0, 'new_fits': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
