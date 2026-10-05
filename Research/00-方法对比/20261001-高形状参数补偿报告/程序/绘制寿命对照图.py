"""Figure 7 from frozen results; no new samples or estimations.

Nature figure contract: show one actual compensation fit, then compare its
central and tail quantiles with the known generating distribution. The seven
Bernard points are plotting positions, not independent validation observations.
"""
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

# Use project NumPy first; the available plotting runtime is supplemental.
PLOTTING_PACKAGES = Path(
    'C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages'
)
sys.path.append(str(PLOTTING_PACKAGES))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / '程序' / '输入快照'
OUT = ROOT / '结果'
DATA = OUT / '中间数据'
FIGURE_NAME = '图8_寿命分布与分位点'
TRUTH = (5.0, 1000.0, 500.0)
SWAPPED = (5.0, 500.0, 1000.0)
BLUE = '#345D7E'
WARM = '#B27448'
GREY = '#444A50'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
    'font.size': 7, 'axes.titlesize': 7, 'axes.labelsize': 7,
    'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
    'legend.fontsize': 6.2, 'axes.linewidth': .7,
    'axes.spines.right': False, 'axes.spines.top': False,
    'axes.unicode_minus': False, 'legend.frameon': False,
    'pdf.fonttype': 42, 'svg.fonttype': 'none',
})


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def cdf(t, parameters):
    beta, eta, gamma = parameters
    d = np.maximum(np.asarray(t) - gamma, 0.0)
    return -np.expm1(-(d / eta) ** beta)


def quantile(probabilities, parameters):
    beta, eta, gamma = parameters
    return gamma + eta * (-np.log1p(-np.asarray(probabilities))) ** (1.0 / beta)


def write_csv(name, header, rows):
    with (DATA / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def select_example():
    estimates = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    audit = json.loads((INPUT / '原案例核验.json').read_text(encoding='utf-8'))
    pool = [r for r in estimates if r['beta'] == 5 and r['n'] == 7
            and r['method'] == 'mdm' and r['converged']]
    center = float(np.median([r['gamma_hat'] for r in pool]))
    chosen = min(pool, key=lambda r: (abs(r['gamma_hat'] - center), r['sample_id']))
    sample = next(r for r in audit['samples'] if r['beta_true'] == 5
                  and r['n'] == 7 and r['sample_id'] == chosen['sample_id'])
    assert sample['regeneration_max_error'] == 0
    assert chosen['sample_id'] == 31
    fitted = tuple(float(chosen[p]) for p in ('beta_hat', 'eta_hat', 'gamma_hat'))
    observations = np.asarray(sample['observations'], dtype=float)
    positions = (np.arange(1, 8) - .3) / (7 + .4)
    assert fitted[2] < observations.min()
    provenance = {
        'purpose': 'Single-case illustration of compensation and quantile consequences.',
        'evidence_type': 'Known model CDFs and one archived actual fit; no new estimation.',
        'selection_rule': 'Minimize absolute gamma distance to the median of successful original beta=5,n=7,MDM returns; tie by sample_id.',
        'selection_pool_size': len(pool),
        'gamma_pool_median': center,
        'sample_id': chosen['sample_id'],
        'n': 7, 'seed': sample['seed'], 'method': 'MDM', 'delta': .1,
        'true_parameters_beta_eta_gamma': TRUTH,
        'fit_parameters_beta_eta_gamma': fitted,
        'literal_swapped_parameters_beta_eta_gamma': SWAPPED,
        'observations': observations.tolist(),
        'plotting_positions': positions.tolist(),
        'plotting_position_rule': '(i-0.3)/(n+0.4), Bernard; points are not independent validation.',
        'sample_regeneration_max_error': sample['regeneration_max_error'],
        'claim_limit': 'Only this fit shows central proximity and quantile discrepancies; no all-method tail-accuracy claim.',
        'input_hashes': {
            name: sha256(INPUT / name)
            for name in ('原案例估计.json', '原案例核验.json')
        },
    }
    return observations, positions, fitted, provenance


def plot_and_save():
    observations, positions, fitted, provenance = select_example()
    t = np.linspace(450.0, 2050.0, 1601)
    p = np.asarray([.01, .10, -np.expm1(-1.0), .90])
    true_q = quantile(p, TRUTH)
    fit_q = quantile(p, fitted)
    errors = fit_q - true_q
    assert abs(true_q[2] - (TRUTH[1] + TRUTH[2])) < 1e-10
    assert abs(fit_q[2] - (fitted[1] + fitted[2])) < 1e-10
    assert np.allclose(cdf(true_q, TRUTH), p, atol=1e-14)
    assert np.allclose(cdf(fit_q, fitted), p, atol=1e-14)
    assert np.all(np.diff(cdf(t, fitted)) >= 0)
    assert cdf([500], TRUTH)[0] == 0
    assert cdf([1000], SWAPPED)[0] == 0

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7),
                            gridspec_kw={'width_ratios': [1.23, 1.0]})
    left, right = axes
    left.axvspan(observations.min(), observations.max(), color='#DDE4E8',
                 alpha=.58, linewidth=0, zorder=0)
    left.plot(t, cdf(t, TRUTH), color=GREY, lw=1.3)
    left.plot(t, cdf(t, fitted), color=BLUE, lw=1.5)
    left.plot(t, cdf(t, SWAPPED), color=WARM, lw=1.15, ls='--')
    left.scatter(observations, positions, facecolor='white', edgecolor='#23282D',
                 s=17, linewidth=.75, zorder=4)
    left.set(xlim=(450, 2050), ylim=(-.015, 1.025),
             xlabel='t', ylabel='F(t)')
    left.set_xticks([500, 1000, 1500, 2000])
    left.set_yticks([0, .25, .5, .75, 1.0])

    for row, (a, b, difference) in enumerate(zip(true_q, fit_q, errors)):
        central = row == 2
        right.plot([a, b], [row, row], color=BLUE if central else '#AAB9C5',
                   lw=2 if central else 1.4, zorder=1)
        right.scatter(a, row, s=24, color=GREY, zorder=3)
        right.scatter(b, row, s=24, color=BLUE, zorder=3)
    right.set(xlim=(800, 2030), ylim=(3.6, -.6), xlabel='Q(p)')
    right.set_xticks([900, 1200, 1500, 1800])
    right.set_yticks(range(4), ['1%', '10%', '63.2%', '90%'])
    right.set_ylabel('p')
    for ax, tag in zip(axes, ('a', 'b')):
        ax.text(-.12, 1.11, tag, transform=ax.transAxes,
                fontsize=8, weight='bold')

    fig.legend([
        Line2D([], [], color=GREY, lw=1.3),
        Line2D([], [], color=BLUE, lw=1.5),
        Line2D([], [], color=WARM, lw=1.15, ls='--'),
        Line2D([], [], ls='', marker='o', markerfacecolor='white',
               markeredgecolor='#23282D', ms=4),
    ], [
        '真分布', 'MDM估计', '参数交换', '样本',
    ], ncol=4, loc='upper center', bbox_to_anchor=(.5, .997), columnspacing=1.8)
    fig.subplots_adjust(left=.09, right=.985, top=.84, bottom=.19, wspace=.47)
    for ext in ('png', 'pdf', 'svg'):
        target = OUT / f'{FIGURE_NAME}.{ext}'
        fig.savefig(target, dpi=450, facecolor='white')
        if ext == 'svg':
            # XML path whitespace is insignificant; keep generated source tidy.
            target.write_text(
                '\n'.join(line.rstrip() for line in target.read_text(encoding='utf-8').splitlines()) + '\n',
                encoding='utf-8', newline='\n')
    plt.close(fig)

    write_csv('CDF对照.csv',
              ['t', 'true_cdf', 'actual_mdm_fit_cdf', 'literal_swapped_cdf'],
              zip(t, cdf(t, TRUTH), cdf(t, fitted), cdf(t, SWAPPED)))
    write_csv('寿命分位点对照.csv',
              ['p', 'true_quantile', 'actual_mdm_fit_quantile', 'fit_minus_true'],
              zip(p, true_q, fit_q, errors))
    write_csv('代表样本绘图位置.csv', ['order', 't', 'Bernard_p'],
              zip(range(1, 8), observations, positions))
    provenance.update({
        'quantile_probabilities': p.tolist(),
        'true_quantiles': true_q.tolist(),
        'fit_quantiles': fit_q.tolist(),
        'quantile_errors': errors.tolist(),
        'figure_dimensions_mm': [182.88, 68.58],
        'png_dimensions': [3240, 1215],
        'notes_location': 'report text and figure caption',
        'export': 'PNG 450 dpi; PDF embedded editable TrueType; SVG live text.',
        'cdf_quantile_identity_max_error': float(max(
            np.max(np.abs(cdf(true_q, TRUTH) - p)),
            np.max(np.abs(cdf(fit_q, fitted) - p)))),
    })
    (DATA / '图8样本来源与核验.json').write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return provenance



def main():
    DATA.mkdir(parents=True, exist_ok=True)
    provenance = plot_and_save()
    print(json.dumps({'sample_id': provenance['sample_id'],
                      'quantile_errors': provenance['quantile_errors'],
                      'new_samples': 0, 'new_fits': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
