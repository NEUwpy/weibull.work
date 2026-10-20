"""复用40条件，核对位置边界、参数补偿和最小值定位；不改正式估计结果。"""
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
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
FROZEN = STUDY / '程序/计算实现-20261016'
OUTPUT = HERE.parent / '分析数据/分布分化机理核对.json'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)', 'MM']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scores(n, method, lse_module):
    if method == 'LSE':
        return lse_module['log_weibull_order_stat_means'](n)
    ranks = np.arange(1, n + 1, dtype=float)
    p = (ranks - 3/8) / (n + 1/4) if n <= 10 else (ranks - .5) / n
    return np.log(-np.log1p(-p))


def profile(t, z, locations):
    x = np.log(t[None, :] - locations[:, None])
    xc = x - x.mean(axis=1, keepdims=True)
    zc = z - z.mean()
    cov = xc @ zc
    ssx = np.sum(xc**2, axis=1)
    ssz = np.dot(zc, zc)
    return cov**2 / (ssx * ssz)


def recover(t, z, location, method):
    x = np.log(t - location)
    xc, zc = x - x.mean(), z - z.mean()
    cov = np.dot(xc, zc)
    if method == 'LSE':
        slope = cov / np.dot(zc, zc)
        return [1/slope, math.exp(x.mean() - slope*z.mean()), location]
    beta = cov / np.dot(xc, xc)
    return [beta, math.exp(x.mean() - z.mean()/beta), location]


def inspect_case(frame, method, branch, lse_module, lre_module):
    valid = frame[frame[method + '_状态'].eq('success')]
    zero = np.isclose(valid[method + '_位置估计'], 0, atol=1e-8, rtol=0)
    group = valid.loc[zero if branch == 'boundary' else ~zero]
    target = group[method + '_尺度估计'].median()
    row = group.loc[(group[method + '_尺度估计'] - target).abs().idxmin()]
    columns = [col for col in frame if col.startswith('观测值')]
    t = np.sort(row[columns].to_numpy(float))
    z = scores(len(t), method, lse_module)
    stored = row[[method + '_' + name + '估计' for name in ['形状', '尺度', '位置']]].to_numpy(float)
    clazz = lse_module['LSE'] if method == 'LSE' else lre_module['LRE']
    rerun = np.array(clazz(t).run()[:3], dtype=float)
    assert np.allclose(rerun, stored, rtol=1e-6, atol=1e-5), (method, branch, rerun, stored)
    upper = t[0] * (1-1e-10)
    locations = np.unique(np.r_[np.linspace(0, upper, 2401),
                               t[0] - np.geomspace(t[0]*1e-10, t[0], 601),
                               stored[2], 500.])
    locations = locations[locations < t[0]]
    values = profile(t, z, locations)
    k = int(np.argmax(values))
    candidates = [(float(locations[k]), float(values[k]))]
    if 0 < k < len(locations)-1:
        result = minimize_scalar(lambda g: -float(profile(t, z, np.array([g]))[0]),
                                 bounds=(locations[k-1], locations[k+1]), method='bounded')
        candidates.append((float(result.x), -float(result.fun)))
    dense_location, dense_score = max(candidates, key=lambda pair: pair[1])
    stored_score = float(profile(t, z, stored[2:3])[0])
    delta = t[0] * 1e-4
    local_scores = profile(t, z, np.array([-delta, 0, delta]))
    negative_locations = np.linspace(-16*t[0], 0, 1601)
    negative_scores = profile(t, z, negative_locations)
    negative_best = int(np.argmax(negative_scores))
    # 数值检查实际F准则与相关系数的恒等关系。
    identity_error = 0.
    for g in np.linspace(0, .9*t[0], 21):
        y = np.log(t-g)
        slope = np.dot(z-z.mean(), y-y.mean()) / np.dot(z-z.mean(), z-z.mean())
        residual = y - (y.mean() - slope*z.mean() + slope*z)
        actual_f = np.var(y, ddof=1) / (np.dot(residual, residual)/(len(t)-2))
        r2 = float(profile(t, z, np.array([g]))[0])
        implied_f = (len(t)-2)/(len(t)-1)/(1-r2)
        identity_error = max(identity_error, abs(actual_f-implied_f)/actual_f)
    return dict(method=method, branch=branch, sample_id=int(row['样本编号']), sample=t.tolist(),
                stored=stored.tolist(), rerun=rerun.tolist(), stored_rho2=stored_score,
                dense_location=dense_location, dense_score=dense_score,
                dense_improvement=dense_score-stored_score,
                correlation_at_negative_zero_positive=local_scores.tolist(),
                negative_extension_best_location=float(negative_locations[negative_best]),
                negative_extension_score_improvement=float(negative_scores[negative_best]-local_scores[1]),
                negative_extension_ends_at_search_limit=bool(negative_best == 0),
                f_identity_relative_error=identity_error,
                profile_locations=locations.tolist(), profile_rho2=values.tolist(),
                negative_profile_locations=negative_locations.tolist(),
                negative_profile_rho2=negative_scores.tolist(),
                at_true_location=recover(t, z, 500., method))


def draw_mechanisms(cases):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False})
    paths = []
    colors = {'interior': '#477b9d', 'boundary': '#c18754'}
    assets = STUDY / 'reviewbyhtml/方法对比/assets'
    for n in [50, 7]:
        frame = pd.read_csv(STUDY/f'结果/W5,1000,500/估计结果/n{n}.csv', float_precision='round_trip')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.subplots_adjust(left=.075, right=.985, bottom=.095, top=.89, hspace=.31, wspace=.21)
        for col, method in enumerate(['LSE', 'LRE(Park)']):
            valid = frame[frame[method+'_状态'].eq('success')]
            eta, gamma = (valid[method+'_'+name+'估计'].to_numpy() for name in ['尺度', '位置'])
            zero = np.isclose(gamma, 0, atol=1e-8, rtol=0)
            assert eta.max() <= 2000 and gamma.max() <= 1500
            ax = axes[0, col]
            ax.scatter(gamma[~zero], eta[~zero], color=colors['interior'], s=11, alpha=.27, linewidths=0)
            ax.scatter(gamma[zero], eta[zero], color=colors['boundary'], s=14, alpha=.5, linewidths=0)
            ax.plot([0, 1500], [1500, 0], color='#414c54', ls='--', lw=1.2)
            ax.scatter([500], [1000], s=64, facecolors='none', edgecolors='#a63039', linewidths=1.5, zorder=6)
            ax.set(xlim=(-25, 1500), ylim=(0, 2000), xlabel='γ estimate', ylabel='η estimate')
            ax.set_title('LSE' if col == 0 else 'LRE (Park)', fontsize=15, pad=10)
            ax.grid(alpha=.12)
            ax.text(-.11, 1.03, chr(97+col), transform=ax.transAxes, weight='bold')
            ax = axes[1, col]
            ax.axvspan(-1500, 0, color='#c7cbd0', alpha=.28)
            ax.axvline(0, color='#8a949c', lw=1, ls='--')
            ax.axvline(500, color='#a63039', lw=1, ls=':')
            for branch in ['boundary', 'interior']:
                case = next(c for c in cases if c['n'] == n and c['method'] == method and c['branch'] == branch)
                ax.plot(case['negative_profile_locations'], case['negative_profile_rho2'], color=colors[branch], lw=1.8)
                ax.plot(case['profile_locations'], case['profile_rho2'], color=colors[branch], lw=1.8)
                ax.scatter([case['stored'][2]], [case['stored_rho2']], s=42, color=colors[branch],
                           edgecolors='white', linewidths=.6, zorder=6)
            ax.set(xlim=(-1500, 1500), ylim=(.85, 1.005), xlabel='γ candidate', ylabel='ρ²')
            ax.grid(alpha=.12)
            ax.text(-.11, 1.03, chr(99+col), transform=ax.transAxes, weight='bold')
        fig.legend(handles=[
            Line2D([], [], marker='o', ls='-', color=colors['interior'], label='Interior results / example'),
            Line2D([], [], marker='o', ls='-', color=colors['boundary'], label='Zero-boundary results / example'),
            Line2D([], [], color='#414c54', ls='--', label='η + γ = 1500'),
            Line2D([], [], marker='o', ls='', markerfacecolor='none', color='#a63039', label='True parameters'),
        ], loc='upper center', bbox_to_anchor=(.5, .98), ncol=2, frameon=False, fontsize=11)
        path = assets/f'尺度双峰_边界与参数补偿_n{n}.png'
        fig.savefig(path, dpi=180, facecolor='white')
        plt.close(fig)
        paths.append(path.as_posix())
    return paths


def main():
    sys.path.insert(0, str(FROZEN))
    lse_module = runpy.run_path(str(FROZEN/'methods/lse.py'))
    lre_module = runpy.run_path(str(FROZEN/'methods/lre.py'))
    sources = {f'程序/计算实现-20261016/methods/{name}.py': sha(FROZEN/f'methods/{name}.py')
               for name in ['lse', 'lre', 'mmle']}
    records, kr_checks, cases = [], [], []
    for n in [50, 20, 15, 10, 7]:
        for beta in np.arange(1.5, 5.1, .5):
            path = STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[path.relative_to(STUDY).as_posix()] = sha(path)
            frame = pd.read_csv(path, float_precision='round_trip')
            assert frame['样本编号'].tolist() == list(range(1200))
            for method in METHODS:
                valid = frame[frame[method+'_状态'].eq('success')]
                eta, gamma = (valid[method+'_'+name+'估计'].to_numpy(float) for name in ['尺度', '位置'])
                records.append(dict(n=n, beta=float(beta), method=method, valid=len(valid),
                                    eta_rmse=float(np.sqrt(np.mean((eta-1000)**2))),
                                    gamma_rmse=float(np.sqrt(np.mean((gamma-500)**2))),
                                    q632_rmse=float(np.sqrt(np.mean((eta+gamma-1500)**2))),
                                    q632_bias=float(np.mean(eta+gamma-1500)),
                                    eta_gamma_correlation=float(np.corrcoef(eta, gamma)[0, 1])))
            minimum = frame[[col for col in frame if col.startswith('观测值')]].min(axis=1).to_numpy()
            kr = frame['MMLE(KR)_位置估计'].to_numpy()
            assert np.allclose(kr, minimum, rtol=0, atol=1e-9)
            expected = 1000 * n**(-1/beta) * math.gamma(1+1/beta)
            variance = 1000**2 * n**(-2/beta) * (math.gamma(1+2/beta)-math.gamma(1+1/beta)**2)
            observed = float(np.mean(kr-500))
            kr_checks.append(dict(n=n, beta=float(beta), theoretical_bias=expected,
                                  empirical_bias=observed, monte_carlo_se=math.sqrt(variance/1200),
                                  standardized_difference=(observed-expected)/math.sqrt(variance/1200)))
            if beta == 5. and n in [50, 7]:
                for method in ['LSE', 'LRE(Park)']:
                    for branch in ['boundary', 'interior']:
                        case = inspect_case(frame, method, branch, lse_module, lre_module)
                        case.update(n=n, beta=float(beta))
                        cases.append(case)
                        print(f'已核对廓线 n={n} {method} {branch}，稠密搜索增益={case["dense_improvement"]:.3g}', flush=True)
            print(f'已核对参数组合与最小值定位 n={n} β={beta:g}', flush=True)
    for relative, digest in sources.items():
        assert sha(STUDY/relative) == digest
    OUTPUT.write_text(json.dumps(dict(sources=sources, records=records, kr_checks=kr_checks, cases=cases),
                                 ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    images = draw_mechanisms(cases)
    print(json.dumps(dict(cells=len(kr_checks), method_cells=len(records), profile_cases=len(cases),
                         max_dense_improvement=max(c['dense_improvement'] for c in cases),
                         output=OUTPUT.as_posix(), images=images), ensure_ascii=False))


if __name__ == '__main__':
    main()
