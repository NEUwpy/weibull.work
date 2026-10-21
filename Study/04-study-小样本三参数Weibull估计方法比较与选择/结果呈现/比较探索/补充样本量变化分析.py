"""复用原40条件；固定真实位置仅作LSE/LRE诊断，不改变正式比较。"""
from pathlib import Path
import hashlib
import json
import math
import runpy
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
FROZEN = STUDY / '程序/计算实现-20261016'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)', 'MM']
NS = [50, 20, 15, 10, 7]


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(values, truth):
    e = np.asarray(values, dtype=float) - truth
    assert len(e) and np.isfinite(e).all()
    bias, variance, mse = float(e.mean()), float(e.var()), float(np.mean(e * e))
    assert np.isclose(mse, bias * bias + variance, rtol=1e-12, atol=1e-10)
    k = max(1, math.ceil(.01 * len(e)))
    return dict(count=len(e), bias=bias, sd_population=math.sqrt(variance),
                rmse=math.sqrt(mse), bias_squared_fraction=bias * bias / mse,
                largest_one_percent_sse_fraction=float(np.sort(e * e)[-k:].sum() / np.sum(e * e)))


def draw(values):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 13,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 7), sharex=True, sharey=True)
    fig.subplots_adjust(left=.075, right=.985, top=.86, bottom=.12, wspace=.12)
    grid = np.linspace(0, 4, 600)
    for ax, method, title in zip(axes, ['LSE', 'LRE(Park)'], ['LSE', 'LRE (Park)']):
        for y, n in enumerate(NS):
            for key, offset, color in [('original', -.16, '#0072B2'), ('fixed', .16, '#D55E00')]:
                a = values[(method, n)][key] / 1.5
                d = gaussian_kde(a)(grid)
                width = .13 * d / d.max()
                ax.fill_between(grid, y + offset - width, y + offset + width,
                                color=color, alpha=.43, linewidth=0)
                q1, median, q3 = np.quantile(a, [.25, .5, .75])
                ax.plot([q1, q3], [y + offset] * 2, color=color, lw=2)
                ax.scatter([median], [y + offset], color=color, s=18, zorder=4)
        ax.axvline(1, color='#9c3645', ls='--', lw=1.2)
        ax.set(xlim=(0, 4), ylim=(4.5, -.5), xlabel=r'$\hat{\beta}/\beta$', title=title)
        ax.set_yticks(range(5), [str(n) for n in NS])
        ax.grid(axis='x', alpha=.13)
    axes[0].set_ylabel('n')
    fig.legend(handles=[Line2D([], [], color='#0072B2', lw=5, label='Estimated γ'),
                        Line2D([], [], color='#D55E00', lw=5, label='True γ fixed (diagnostic)'),
                        Line2D([], [], color='#9c3645', ls='--', label='True β')],
               loc='upper center', bbox_to_anchor=(.5, .98), ncol=3, frameon=False, fontsize=12)
    path = STUDY / 'reviewbyhtml/方法对比/assets/样本量变化_定位影响诊断_β1.5.png'
    fig.savefig(path, dpi=220, facecolor='white')
    plt.close(fig)
    return path


def main():
    sys.path.insert(0, str(FROZEN))
    mechanism = runpy.run_path(str(HERE / '分析分布分化机理.py'))
    lse = runpy.run_path(str(FROZEN / 'methods/lse.py'))
    records, diagnostics, values, sources = [], [], {}, {}
    max_recovery_error = 0.
    for beta in np.arange(1.5, 5.1, .5):
        for n in NS:
            path = STUDY / f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[path.relative_to(STUDY).as_posix()] = fingerprint(path)
            frame = pd.read_csv(path, float_precision='round_trip')
            assert frame['样本编号'].tolist() == list(range(1200))
            for method in METHODS:
                ok = frame[method + '_状态'].eq('success')
                a = frame.loc[ok, method + '_形状估计'].to_numpy(float)
                records.append(dict(beta=float(beta), n=n, method=method,
                                    valid_rate=float(ok.mean()), **describe(a, beta)))
            if beta not in [1.5, 5.]:
                continue
            t = np.sort(frame.filter(regex='^观测值').to_numpy(float), axis=1)
            for method in ['LSE', 'LRE(Park)']:
                assert frame[method + '_状态'].eq('success').all()
                key = 'LSE' if method == 'LSE' else 'LRE'
                z = mechanism['scores'](n, key, lse)
                original = frame[[method + '_' + p + '估计' for p in ['形状', '尺度', '位置']]].to_numpy(float)
                reconstructed = np.array([mechanism['recover'](row, z, g, key)
                                          for row, g in zip(t, original[:, 2])])
                assert np.allclose(reconstructed, original, rtol=1e-6, atol=1e-6)
                max_recovery_error = max(max_recovery_error, float(np.max(np.abs(reconstructed - original))))
                fixed = np.array([mechanism['recover'](row, z, 500., key)[0] for row in t])
                diagnostics.append(dict(beta=float(beta), n=n, method=method,
                                        original=describe(original[:, 0], beta),
                                        true_location_fixed=describe(fixed, beta)))
                if beta == 1.5:
                    values[(method, n)] = dict(original=original[:, 0], fixed=fixed)
    figure = draw(values)
    for p in [Path(__file__), HERE / '分析分布分化机理.py', FROZEN / 'methods/lse.py', FROZEN / 'methods/lre.py']:
        sources[p.relative_to(STUDY).as_posix()] = fingerprint(p)
    output = HERE.parent / '分析数据/样本量变化补充核对.json'
    output.write_text(json.dumps(dict(sources=sources, records=records, diagnostics=diagnostics,
                                     matched_recovery_count=24000,
                                     max_absolute_recovery_error=max_recovery_error,
                                     figure=figure.as_posix(), figure_sha256=fingerprint(figure)),
                                 ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(conditions=40, method_records=len(records), diagnostics=len(diagnostics),
                          matched_recoveries=24000, formal_results_modified=False,
                          output=output.as_posix(), figure=figure.as_posix()), ensure_ascii=False))


if __name__ == '__main__':
    main()
