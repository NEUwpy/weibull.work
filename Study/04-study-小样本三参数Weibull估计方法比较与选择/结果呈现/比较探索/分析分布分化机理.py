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
from scipy.stats import gaussian_kde

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


def draw_phenomenon_explanations():
    """只读取原始估计；解释n响应与混合分布，不调用估计器。"""
    plt.rcParams.update({'font.family': 'sans-serif',
                         'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
                         'font.size': 12, 'axes.spines.top': False,
                         'axes.spines.right': False})
    assets = STUDY / 'reviewbyhtml/方法对比-v1.0/assets'
    ns = np.array([50, 20, 15, 10, 7])
    evidence = {'sources': {}, 'kr_rmse': [], 'mixture': []}

    def load(beta, n):
        path = STUDY / f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
        evidence['sources'][path.relative_to(STUDY).as_posix()] = sha(path)
        frame = pd.read_csv(path, float_precision='round_trip')
        assert frame['样本编号'].tolist() == list(range(1200))
        return frame

    colors = ['#0072B2', '#D55E00']
    fig, ax = plt.subplots(figsize=(8.3, 4.7))
    fig.subplots_adjust(left=.12, right=.97, bottom=.17, top=.82)
    for beta, color in zip([1.5, 5.], colors):
        empirical = []
        theory = math.sqrt(math.gamma(1+2/beta)) * ns**(-1/beta)
        for n, expected in zip(ns, theory):
            frame = load(beta, n)
            assert frame['MMLE(KR)_状态'].eq('success').all()
            estimate = frame['MMLE(KR)_位置估计'].to_numpy(float)
            minimum = frame.filter(regex=r'^观测值\d+$').min(axis=1).to_numpy(float)
            assert np.allclose(estimate, minimum, rtol=0, atol=1e-9)
            observed = float(np.sqrt(np.mean(((estimate-500)/1000)**2)))
            empirical.append(observed)
            evidence['kr_rmse'].append(dict(beta=beta, n=int(n), empirical=observed,
                                            theoretical=float(expected)))
        ax.plot(range(5), theory, color=color, lw=2, label=f'β = {beta:g}')
        ax.scatter(range(5), empirical, color=color, s=54, marker='o',
                   facecolors='white', linewidths=1.7, zorder=4)
    ax.set(xticks=range(5), xticklabels=ns, xlabel='n', ylabel=r'位置 RMSE / $\eta$',
           ylim=(0, .72), xlim=(-.15, 4.15))
    ax.grid(axis='y', alpha=.15)
    handles, labels = ax.get_legend_handles_labels()
    handles += [Line2D([], [], color='#555555', lw=2, label='理论'),
                Line2D([], [], color='#555555', marker='o', ls='',
                       markerfacecolor='white', label='原1200次结果')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.52, .99),
               ncol=4, frameon=False)
    fig.savefig(assets/'最小值定位_n响应_理论与原结果.png', dpi=200, facecolor='white')
    plt.close(fig)

    palette = {'boundary': '#D55E00', 'interior': '#0072B2', 'all': '#333333'}
    grid = np.linspace(0, 3200, 1601)
    for method in ['LSE', 'LRE(Park)']:
        fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.5), sharex=True, sharey=True)
        fig.subplots_adjust(left=.10, right=.98, bottom=.12, top=.84,
                            hspace=.27, wspace=.20)
        for row, n in enumerate([50, 7]):
            for col, beta in enumerate([1.5, 5.]):
                frame = load(beta, n)
                valid = frame[frame[method+'_状态'].eq('success')]
                eta = valid[method+'_尺度估计'].to_numpy(float)
                gamma = valid[method+'_位置估计'].to_numpy(float)
                zero = np.isclose(gamma, 0, atol=1e-8, rtol=0)
                # 所有组使用总体同一绝对带宽，组密度乘组权重后相加。
                bandwidth = float(gaussian_kde(eta).factor * eta.std(ddof=1))
                components = []
                for mask, key in [(zero, 'boundary'), (~zero, 'interior')]:
                    if mask.sum() < 2:
                        assert mask.sum() == 0
                        density = np.zeros_like(grid)
                    else:
                        values = eta[mask]
                        kde = gaussian_kde(values, bw_method=bandwidth/values.std(ddof=1))
                        density = kde(grid) * mask.mean()
                    components.append(density)
                    axes[row, col].fill_between(grid, density, color=palette[key], alpha=.24)
                    axes[row, col].plot(grid, density, color=palette[key], lw=1.6)
                total = gaussian_kde(eta, bw_method=bandwidth/eta.std(ddof=1))(grid)
                assert np.allclose(sum(components), total, atol=1e-14, rtol=1e-9)
                ax = axes[row, col]
                ax.plot(grid, total, color=palette['all'], lw=1.5, ls='--')
                ax.axvline(1000, color='#777777', lw=1, ls=':')
                ax.set(xlim=(0, 3200), ylim=(0, .0045), xticks=[0, 1000, 2000, 3000])
                ax.grid(axis='y', alpha=.12)
                if row == 0:
                    ax.set_title(f'β = {beta:g}', fontsize=14, pad=12)
                if col == 0:
                    ax.set_ylabel(f'n = {n}\n概率密度')
                if row == 1:
                    ax.set_xlabel(r'$\hat{\eta}$')
                evidence['mixture'].append(dict(
                    method=method, beta=beta, n=n, total=len(eta), boundary_count=int(zero.sum()),
                    boundary_fraction=float(zero.mean()), bandwidth=bandwidth,
                    visible_fraction=float(((eta>=grid[0]) & (eta<=grid[-1])).mean()),
                    boundary_eta_median=float(np.median(eta[zero])) if zero.any() else None,
                    interior_eta_median=float(np.median(eta[~zero])),
                    component_identity_max_abs=float(np.max(np.abs(sum(components)-total)))))
        fig.legend(handles=[Line2D([], [], color=palette['boundary'], lw=2, label=r'$\hat{\gamma}=0$：边界组'),
                            Line2D([], [], color=palette['interior'], lw=2, label=r'$\hat{\gamma}>0$：内部组'),
                            Line2D([], [], color=palette['all'], lw=1.5, ls='--', label='全部结果')],
                   loc='upper center', bbox_to_anchor=(.54, .97), ncol=3, frameon=False)
        fig.savefig(assets/f'尺度分布_边界内部混合_{method}.png', dpi=200, facecolor='white')
        plt.close(fig)
    for path, digest in evidence['sources'].items():
        assert sha(STUDY/path) == digest
    output = HERE.parent/'分析数据/现象解释补图核对.json'
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'kr_conditions': len(evidence['kr_rmse']),
                      'mixture_conditions': len(evidence['mixture']),
                      'output': output.as_posix()}, ensure_ascii=False))


def precision_relationship_options():
    """比较解释候选：误差组成与共同样本的起点信息分层。"""
    metrics_path = HERE.parent/'分析数据/参数指标.csv'
    metrics = pd.read_csv(metrics_path, float_precision='round_trip')
    methods = METHODS[:-1]
    records, sources, composition = [], {metrics_path.relative_to(STUDY).as_posix(): sha(metrics_path)}, []
    for beta in [1.5, 5.]:
        for n in [50, 7]:
            path = STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            frame = pd.read_csv(path, float_precision='round_trip')
            sources[path.relative_to(STUDY).as_posix()] = sha(path)
            common = np.logical_and.reduce([frame[m+'_状态'].eq('success') for m in METHODS])
            minimum = frame.filter(regex=r'^观测值\d+$').min(axis=1).to_numpy(float)
            gap = minimum > 500 + .5*1000
            cell = dict(beta=beta, n=n, total=len(frame), gap_all=int(gap.sum()),
                        common_count=int(common.sum()), common_gap=int((common & gap).sum()),
                        theoretical_gap_probability=float(math.exp(-n*.5**beta)), methods=[])
            for method in methods:
                values = frame[method+'_位置估计'].to_numpy(float)
                error = (values[common]-500)/1000
                mse, bias, variance = float(np.mean(error**2)), float(error.mean()), float(error.var())
                row = metrics[(metrics.beta==beta)&(metrics.n==n)&metrics.method.eq(method)&metrics['subset'].eq('common')].iloc[0]
                assert math.isclose(math.sqrt(mse), row.gamma_rmse/1000, rel_tol=1e-12)
                assert math.isclose(bias, row.gamma_bias/1000, abs_tol=1e-12)
                assert math.isclose(mse, bias**2+variance, abs_tol=1e-14)
                group = []
                for g in [False, True]:
                    mask = common & (gap==g)
                    group.append(float(np.mean(((values[mask]-500)/1000)**2)) if mask.any() else None)
                if all(v is not None for v in group):
                    p = cell['common_gap']/cell['common_count']
                    assert math.isclose(mse, (1-p)*group[0]+p*group[1], abs_tol=1e-14)
                cell['methods'].append(dict(method=method, mse=mse, bias=bias, variance=variance,
                                            squared_bias_share=bias**2/mse,
                                            near_mse=group[0], gap_mse=group[1]))
                composition.append(dict(beta=beta, n=n, method=method, mse=mse, bias=bias,
                                        variance=variance, squared_bias_share=bias**2/mse))
            records.append(cell)
    old, new = [next(r for r in records if r['beta']==5 and r['n']==n) for n in [50, 7]]
    p_old = old['common_gap']/old['common_count']
    standardized = []
    for row in new['methods']:
        standardized.append(dict(method=row['method'], actual_rmse=math.sqrt(row['mse']),
                                  n50_mix_rmse=math.sqrt((1-p_old)*row['near_mse']+p_old*row['gap_mse'])))
    plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                         'font.size':12, 'axes.spines.top':False, 'axes.spines.right':False})
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.8), sharex=True, sharey=True)
    fig.subplots_adjust(left=.13, right=.97, bottom=.14, top=.78, wspace=.20)
    names = ['MDM-0.1','LSE','LRE (Park)','WMLE','MLE','K–R']
    for ax, cell in zip(axes, [old, new]):
        for j, row in enumerate(cell['methods']):
            a, b = math.sqrt(row['near_mse']), math.sqrt(row['gap_mse'])
            ax.plot([a,b],[j,j], color='#b9c1c9', lw=1.2)
            ax.scatter(a,j,color='#0072B2',s=54,zorder=3)
            ax.scatter(b,j,color='#D55E00',marker='s',s=48,zorder=3)
        ax.set(yticks=range(6), yticklabels=names, xlim=(0,.72), ylim=(5.5,-.5),
               xlabel=r'条件位置 RMSE / $\eta$')
        ax.set_title(f'n = {cell["n"]}', pad=15)
        ax.grid(axis='x',alpha=.14)
    fig.legend(handles=[Line2D([],[],color='#0072B2',marker='o',ls='',label='起点附近有观测'),
                        Line2D([],[],color='#D55E00',marker='s',ls='',label='起点附近无观测')],
               loc='upper center',bbox_to_anchor=(.55,.98),ncol=2,frameon=False)
    image_path = STUDY/'reviewbyhtml/方法对比-v1.0/assets/n响应候选_起点信息分层.png'
    fig.savefig(image_path,dpi=200,facecolor='white')
    plt.close(fig)
    for path,digest in sources.items():
        assert sha(STUDY/path)==digest
    output = HERE.parent/'分析数据/精度关系解释候选核对.json'
    output.write_text(json.dumps(dict(sources=sources,threshold_eta=.5,records=records,
                                     composition=composition,n7_reweighted_to_n50_mix=standardized),
                                 ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'conditions':len(records),'method_conditions':len(composition),
                      'output':output.as_posix(),'image':image_path.as_posix()},ensure_ascii=False))


def anomaly_reference_check():
    """对拍既有异常率与原始返回行；只读取，不重新抽样或估计。"""
    risk_path = HERE.parent/'分析数据/风险统计.csv'
    risk = pd.read_csv(risk_path, float_precision='round_trip')
    risk = risk[risk['factor'].eq(3)]
    sources = {risk_path.relative_to(STUDY).as_posix(): sha(risk_path)}
    checked = []
    for beta in np.arange(1.5, 5.1, .5):
        for n in [50, 20, 15, 10, 7]:
            path = STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[path.relative_to(STUDY).as_posix()] = sha(path)
            frame = pd.read_csv(path, float_precision='round_trip')
            assert frame['样本编号'].tolist() == list(range(1200))
            for method in METHODS:
                valid = frame[frame[method+'_状态'].eq('success')]
                values = valid[method+'_形状估计'].to_numpy(float)
                low, high = int(np.sum(values <= beta/3)), int(np.sum(values >= 3*beta))
                row = risk[risk['beta'].eq(beta) & risk['n'].eq(n) & risk['method'].eq(method)]
                assert len(row) == 1
                row = row.iloc[0]
                assert (len(valid), low, high) == (row['success'], row['anomaly_low'], row['anomaly_high'])
                rate = (low+high)/len(valid)
                assert abs(rate-row['anomaly_valid_rate']) < 1e-12
                checked.append(dict(beta=float(beta), n=n, method=method,
                                    success=len(valid), low=low, high=high, rate=rate))
    endpoint_increases = sum(
        next(r['rate'] for r in checked if r['beta']==beta and r['n']==7 and r['method']==method)
        > next(r['rate'] for r in checked if r['beta']==beta and r['n']==50 and r['method']==method)
        for beta in np.arange(1.5, 5.1, .5) for method in METHODS)
    beta5_monotonic = all(
        all(a <= b for a,b in zip(rates, rates[1:]))
        for method in METHODS
        for rates in [[next(r['rate'] for r in checked if r['beta']==5 and r['n']==n and r['method']==method)
                       for n in [50,20,15,10,7]]])
    frame = pd.read_csv(STUDY/'结果/W5,1000,500/估计结果/n7.csv', float_precision='round_trip')
    cols = ['LSE_形状估计', 'LSE_尺度估计', 'LSE_位置估计']
    abnormal = frame[frame[cols[0]].le(5/3) & frame['LSE_状态'].eq('success')].iloc[0]
    near = frame[frame[cols[0]].between(4,6) & frame[cols[1]].between(800,1200)
                 & frame[cols[2]].between(300,700) & frame['LSE_状态'].eq('success')].iloc[0]
    examples = [dict(sample_id=int(r['样本编号']), beta=float(r[cols[0]]),
                     eta=float(r[cols[1]]), gamma=float(r[cols[2]])) for r in [near,abnormal]]
    for relative,digest in sources.items():
        assert sha(STUDY/relative) == digest
    output = HERE.parent/'分析数据/异常现象与素材复用核对.json'
    output.write_text(json.dumps(dict(sources=sources, records=checked, examples=examples,
        example_selection='按存档顺序，分别取形状/尺度/位置误差在预设范围内的首例与形状低估至真值1/3的首例；只作示例。',
        n7_above_n50_cells=endpoint_increases, beta5_all_methods_n_decrease_monotonic=beta5_monotonic),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(method_cells=len(checked),n7_above_n50_cells=endpoint_increases,
                         beta5_monotonic=beta5_monotonic,examples=examples,output=output.as_posix()),ensure_ascii=False))


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
    if '--phenomenon-explanations' in sys.argv:
        draw_phenomenon_explanations()
    elif '--precision-relationship-options' in sys.argv:
        precision_relationship_options()
    elif '--anomaly-reference-check' in sys.argv:
        anomaly_reference_check()
    else:
        main()
