"""WMLE联合目标的γ剖面；build/render/revise/verify均不替换原估计。

Figure contract: compare the attainable joint residual at the true location
with archived returns, using the existing paired beta=2/5, n=7/15 samples.
Keep the same six-panel grid and sample 29 in both single-sample expansions.
All axes are linear and identical. Export only the existing PNG filename;
new source data and checks stay beside this program.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, RESULT, setup_runtime, load_conditional_profiles, save_png, write_atomic

# Use the archived weight provider, with the shared diagnostic equations.
FROZEN = HERE / '依赖快照/python/methods'
sys.path.insert(0, str(FROZEN.parent))
sys.path.insert(0, str(FROZEN))
spec = importlib.util.spec_from_file_location('r1_frozen_wmle_weights', FROZEN / 'wmle.py')
weights = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weights)
profiles = load_conditional_profiles()


class CachedWeights:
    SHAPE_UPPER = weights.SHAPE_UPPER
    get_weight_j1 = staticmethod(weights.get_weight_j1)
    get_weight_j2 = staticmethod(weights.get_weight_j2)
    get_weight_j3 = staticmethod(lru_cache(maxsize=32768)(weights.get_weight_j3))


DATA = RESULT / '报告1/中间数据'
CACHE = HERE / '20261011-WMLE联合判据曲线.json'
QA = HERE / '20261011-WMLE联合判据核验.json'
FIGURE = RESULT / '报告1/图6_WMLE六格机制.png'
REPORT = ROOT / '报告1：高形状参数下的估计偏移.md'
README = ROOT / 'README.md'
FIGURE_QA = DATA / '逐法图核验.json'
CONDITIONS = [(2, 7), (5, 7), (2, 15), (5, 15)]
SELECTED_ID = 29
BLUE, RETURN = '#345D7E', '#B55E3E'
AXES = {'x_limits': [-25., 1400.], 'x_ticks': [0., 500., 1000.],
        'y_limits': [-.0003, .015], 'y_ticks': [0., .005, .010, .015],
        'x_scale': 'linear', 'y_scale': 'linear'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def sources():
    canonical_data = ROOT / '交付/结果/报告1/中间数据'
    hashes = {(canonical_data / name).relative_to(ROOT.parents[1]).as_posix(): digest(DATA / name)
              for name in ['样本.json', '实际估计.json', '逐法过程曲线.json', '配对单例与推导核验.json']}
    for path in [FROZEN / 'wmle.py', FROZEN / 'j3_weights.tsv',
                 ROOT.parents[1] / 'python/methods/conditional_profiles.py']:
        hashes[path.relative_to(ROOT.parents[1]).as_posix()] = digest(path)
    return hashes


def protected_results():
    return {p.relative_to(RESULT / '报告1').as_posix(): digest(p)
            for p in (RESULT / '报告1').rglob('*')
            if p.is_file() and p not in (FIGURE, FIGURE_QA)}


def protected_figure_metadata():
    record = read_json(FIGURE_QA)
    record['process_figures'] = [r for r in record['process_figures'] if r['method'] != 'wmle']
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def figure_metadata(figure):
    return dict(method='wmle', file=FIGURE.stem, criterion='min_beta(T1**2+T2**2)',
                panels=figure['panels'][:4], single_panels=figure['panels'][4:],
                axis_settings=figure['axes'], six_panel_axes_identical=True,
                png_dimensions=figure['dimensions'],
                source_data=CACHE.relative_to(ROOT).as_posix(),
                profile_meaning='joint residual objective minimized over shape',
                formula_documented_in_report=True, notes_location='report text')


def calculate_curve(task):
    row, sample = task
    fit = row['fit']
    x = np.asarray(sample['observations'], float)
    grid = [point[0] for point in row['points']]
    result = []
    for i, gamma in enumerate(grid, 1):
        is_return = bool(fit['converged'] and gamma == fit['gamma_hat'])
        p = profiles.wmle_objective_profile(
            x, gamma, CachedWeights,
            candidate_beta=fit['beta_hat'] if is_return else None)
        result.append({'id': f'G{i}', 'gamma': gamma, **p})
    truth = next(p for p in result if p['gamma'] == 500)
    returned = next((p for p in result if fit['converged'] and p['gamma'] == fit['gamma_hat']), None)
    a, b = (profiles.wmle_residuals(x, fit['beta_hat'], fit['gamma_hat'], CachedWeights)
            if fit['converged'] else (None, None))
    return {'beta': row['beta'], 'n': row['n'], 'sample_id': row['sample_id'],
            'observations': x.tolist(), 'fit': fit, 'points': result,
            'truth': truth, 'returned': returned,
            'archived_return_t1': a, 'archived_return_t2': b,
            'archived_return_objective': a * a + b * b if a is not None else None}


def build():
    if CACHE.exists():
        cache = read_json(CACHE)
        assert cache['source_hashes'] == sources(), '输入发生变化，请勿混用旧缓存'
        if 'protected_figure_metadata' not in cache:
            # Migrate this task's first cache without recalculating or changing curves.
            old_qa_hash = cache['protected_results'].pop(FIGURE_QA.relative_to(RESULT / '报告1').as_posix())
            assert old_qa_hash == digest(FIGURE_QA)
            cache['protected_figure_metadata'] = protected_figure_metadata()
            write_json(CACHE, cache)
        print('REUSED：现有联合判据缓存。', flush=True)
        return
    source_hashes = sources()
    protected = protected_results()
    protected_metadata = protected_figure_metadata()
    rows = [c for c in read_json(DATA / '逐法过程曲线.json')['curves']
            if c['source'] == 'paired' and c['method'] == 'wmle']
    sample_index = {(s['beta'], s['n'], s['sample_id']): s for s in read_json(DATA / '样本.json')}
    selection = next(s for s in read_json(DATA / '配对单例与推导核验.json')['methods'] if s['method'] == 'wmle')
    assert selection['sample_id'] == SELECTED_ID
    assert len(rows) == 200
    curves = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(calculate_curve, (r, sample_index[r['beta'], r['n'], r['sample_id']]))
                   for r in rows]
        for future in as_completed(futures):
            curves.append(future.result())
            if len(curves) % 25 == 0:
                print(f'WMLE联合判据：{len(curves)}/200组', flush=True)
    curves.sort(key=lambda r: (r['n'], r['beta'], r['sample_id']))
    summaries = []
    for beta, n in CONDITIONS:
        rr = [r for r in curves if r['beta'] == beta and r['n'] == n]
        assert len(rr) == 50
        successes = [r for r in rr if r['fit']['converged']]
        summaries.append({'beta': beta, 'n': n, 'curves': 50, 'successful_original_returns': len(successes),
                          'median_profile_objective_at_true_gamma': float(np.median([r['truth']['objective'] for r in rr])),
                          'gamma_high_original_returns': sum(r['fit']['gamma_hat'] > 500 for r in successes),
                          'maximum_profile_objective_at_original_return': max(r['returned']['objective'] for r in successes),
                          'true_gamma_upper_shape_limits': sum(r['truth']['shape_at_upper_boundary'] for r in rr)})
    assert source_hashes == sources() and protected == protected_results()
    assert protected_metadata == protected_figure_metadata()
    write_json(CACHE, {'date': '2026-10-11', 'criterion': 'Op(gamma)=min_beta(T1**2+T2**2)',
                      'shape_range': [0, 10], 'weight_identity': 'archived J1/J2/J3 provider',
                      'new_samples': 0, 'new_joint_estimates': 0,
                      'selected_id': SELECTED_ID, 'selection': selection['selection_rule'] if 'selection_rule' in selection
                      else 'Reuse archived paired WMLE example, same sample 29 for beta=2/5.',
                      'source_hashes': source_hashes, 'protected_results': protected,
                      'protected_figure_metadata': protected_metadata,
                      'axes': AXES, 'summaries': summaries, 'curves': curves})


def draw_curve(ax, row, *, single=False, highlight=False):
    pp = row['points']
    alpha, width = (1., 1.25) if single else ((.9, 1.1) if highlight else (.18, .6))
    ax.plot([p['gamma'] for p in pp], [p['objective'] for p in pp], color=BLUE,
            alpha=alpha, lw=width, zorder=2 if highlight else 1)
    truth = row['truth']
    ax.scatter(500, truth['objective'], s=13 if single else 5, color=BLUE,
               alpha=alpha, linewidths=0, zorder=3)
    if row['fit']['converged']:
        ax.scatter(row['fit']['gamma_hat'], row['archived_return_objective'],
                   s=25 if single else 11, color=RETURN, marker='x', alpha=alpha,
                   linewidths=.9 if single else .65, zorder=5)
    if single:
        ax.scatter([p['gamma'] for p in pp], [p['objective'] for p in pp], s=4.5,
                   facecolor='white', edgecolor=BLUE, linewidths=.4, alpha=.8, zorder=3)
        for p in [row['truth'], row['returned']]:
            if p is not None:
                offset = (8, 9) if p['gamma'] == 500 else (7, 12)
                ax.annotate(p['id'], (p['gamma'], p['objective']), xytext=offset,
                            textcoords='offset points', fontsize=6,
                            color=BLUE if p['gamma'] == 500 else RETURN, zorder=6)


def render():
    cache = read_json(CACHE)
    assert cache['source_hashes'] == sources()
    setup_runtime()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif',
                         'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 7, 'axes.labelsize': 7, 'axes.titlesize': 7.2,
                         'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
                         'axes.linewidth': .7, 'axes.spines.right': False,
                         'axes.spines.top': False, 'axes.unicode_minus': False})
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    singles = [next(r for r in cache['curves'] if r['beta'] == beta and r['n'] == 7
                    and r['sample_id'] == SELECTED_ID) for beta in [2, 5]]
    panels = []
    for i, (beta, n) in enumerate(CONDITIONS):
        rows = [r for r in cache['curves'] if r['beta'] == beta and r['n'] == n]
        for row in rows:
            draw_curve(axes.flat[i], row)
        if n == 7:
            draw_curve(axes.flat[i], singles[0 if beta == 2 else 1], highlight=True)
        panels.append({'beta': beta, 'n': n, 'curves': len(rows)})
    for i, row in enumerate(singles, 4):
        draw_curve(axes.flat[i], row, single=True)
        axes.flat[i].axvline(row['fit']['gamma_hat'], color=RETURN, ls='--', lw=.8)
        panels.append({'beta': row['beta'], 'n': 7, 'sample_id': SELECTED_ID,
                       'literal_expansion_from': 'a' if row['beta'] == 2 else 'b'})
    for i, ax in enumerate(axes.flat):
        ax.set_xlim(AXES['x_limits']); ax.set_xticks(AXES['x_ticks'])
        ax.set_ylim(AXES['y_limits']); ax.set_yticks(AXES['y_ticks'])
        ax.set_xlabel('γ'); ax.set_ylabel(r'$O_p(\gamma)$')
        ax.axvline(500, color='black', ls=':', lw=.8)
        ax.set_title(f"β={panels[i]['beta']}，n={panels[i]['n']}", loc='left', pad=9)
        ax.text(-.13, 1.10, chr(97 + i), transform=ax.transAxes, fontsize=8, weight='bold')
    fig.subplots_adjust(left=.115, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    fig.canvas.draw()
    actual_axes = [{'x_limits': list(ax.get_xlim()), 'y_limits': list(ax.get_ylim()),
                    'x_ticks': ax.get_xticks().tolist(), 'y_ticks': ax.get_yticks().tolist(),
                    'x_scale': ax.get_xscale(), 'y_scale': ax.get_yscale()} for ax in axes.flat]
    assert all(a == actual_axes[0] for a in actual_axes)
    assert actual_axes[0] == AXES
    save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    record = read_json(QA) if QA.exists() else {}
    output_path = FIGURE.relative_to(ROOT).as_posix() if FIGURE.is_relative_to(ROOT) else FIGURE.as_posix()
    record['figure'] = {'path': output_path, 'sha256': digest(FIGURE),
                        'axes': actual_axes, 'panels': panels, 'formats': ['png'],
                        'dimensions': [3240, 3240], 'criterion': cache['criterion']}
    write_json(QA, record)
    metadata = read_json(FIGURE_QA)
    metadata['process_figures'] = [figure_metadata(record['figure']) if r['method'] == 'wmle' else r
                                  for r in metadata['process_figures']]
    write_json(FIGURE_QA, metadata)
    print('EXPORTED：WMLE联合判据六格PNG。', flush=True)


def revise():
    text = REPORT.read_text(encoding='utf-8')
    original_text = text
    start = text.index('当各dᵢ相等时，式（22）中的乘积恰为1。')
    end = text.index('### 2.5　', start)
    section = r'''当各dᵢ相等时，式（22）中的乘积恰为1。高β样本的距离较集中，这一乘积可能接近1，但校准目标J₃由n和候选β决定。改变β会同时影响T₁、T₂；真实γ处即使使其中一项残差为零，也未必能使另一项为零。

WMLE按两项残差的平方和联合选择β、γ。为比较不同γ下能够达到的拟合程度，在每个γ处优化β，得到：

$$O(\beta,\gamma)=T_1(\beta,\gamma)^2+T_2(\beta,\gamma)^2,\qquad
O_p(\gamma)=\inf_{0<\beta<10}O(\beta,\gamma).
\tag{24}$$

其中，O为联合目标函数，Oₚ为固定γ下残差平方和的下界，边界处按极限计算。图7按式（24）绘制Oₚ；低点表示联合残差较小的位置，零点对应两条校准方程的共同解。黑点线为真实γ，深蓝曲线对应下方展开样本，红叉为原返回解。

![图7　WMLE的联合残差平方和剖面](交付/结果/报告1/图6_WMLE六格机制.png)

**图7｜高β对照中，联合残差可在偏高的位置降至接近零。**

图7f中，真实γ=500处的最小残差平方和约为0.0105，而原返回γ约979处接近零。因此，偏高的位置在WMLE联合判据下优于真实位置。位置上移后，距离的相对差异增大，联合平衡对应β约4.20；式（23）则给出η约512，最终选中γ高估、β和η低估的分布。

该例在真实γ处的条件最优β接近程序上界10，计算涉及J₃的端点近似；形状范围与端点近似对偏移的贡献仍需进一步区分。

'''
    # Keep all report numbering unchanged; replace only WMLE equation (24).
    if 'O_p(\\gamma)=\\inf_{0<\\beta<10}' not in text:
        text = text[:start] + section + text[end:]
    old_link = '[准则曲线数据](交付/结果/报告1/中间数据/逐法过程曲线.json)'
    new_link = ('[其余方法准则曲线](交付/结果/报告1/中间数据/逐法过程曲线.json)、'
                '[WMLE联合判据曲线](交付/程序/报告1/20261011-WMLE联合判据曲线.json)')
    text = text.replace(old_link, new_link, 1)
    if text != original_text:
        write_atomic(REPORT, text.encode('utf-8'))
    readme = README.read_text(encoding='utf-8')
    old_identity = ('条件诊断统一0<β<10与同一权重函数，无T1零点则留空。'
                    'J3在β>5沿用端点是本批工程近似，不能视为原文大形状权重；'
                    '条件T1零线不替代联合求解轨迹。')
    new_identity = ('报告1的条件诊断为固定γ后最小化T1²+T2²；报告2仍沿T1=0计算T2，无T1零点则留空。'
                    '两者统一0<β<10与同一权重函数，均不代表联合求解轨迹。'
                    'J3在β>5沿用端点是本批工程近似，不能视为原文大形状权重。')
    readme = readme.replace(old_identity, new_identity, 1)
    note = ('2026-10-11报告1的WMLE图7改为联合目标剖面：固定γ，在同一形状范围与权重下最小化T₁²+T₂²。'
            '[独立脚本](交付/程序/报告1/20261011-WMLE联合判据剖面.py)的`build`计算诊断曲线，`render`重绘一张PNG，'
            '`revise`更新正文，`verify`核对；[曲线](交付/程序/报告1/20261011-WMLE联合判据曲线.json)和'
            '[核验](交付/程序/报告1/20261011-WMLE联合判据核验.json)留在程序目录。原样本、参数估计、工作簿和其他图不变。'
            '六格共用线性刻度，下方单样本仍为上方第29组；统一制图入口已接入本脚本。\n\n')
    if note.strip() not in readme:
        readme = readme.replace('## 整理与恢复\n', note + '## 整理与恢复\n', 1)
    if readme != README.read_text(encoding='utf-8'):
        write_atomic(README, readme.encode('utf-8'))


def direct_objective(x, beta, gamma):
    """Independent evaluation of the estimator's two raw equations."""
    d = np.asarray(x) - gamma
    ld = np.log(d)
    beta = np.asarray(beta, float)
    # Stabilize the raw sums with one common scale; ratios are unchanged.
    power = np.exp(beta[..., None] * (ld - ld.max()))
    total = power.sum(axis=-1)
    a = weights.get_weight_j2(len(d)) / beta + ld.mean() - np.sum(power * ld, axis=-1) / total
    j3 = np.array([CachedWeights.get_weight_j3(len(d), float(v)) for v in beta.flat]).reshape(beta.shape)
    b = np.mean(1 / d) * (total / np.sum(power / d, axis=-1)) - j3
    value = a * a + b * b
    return float(value) if beta.ndim == 0 else value


def verify():
    cache = read_json(CACHE)
    assert cache['source_hashes'] == sources()
    assert cache['protected_results'] == protected_results(), '其他图、表或数据发生变化'
    assert cache['protected_figure_metadata'] == protected_figure_metadata(), '其他图的核验元数据发生变化'
    check_rows = []
    max_equation_error = 0.
    max_better_dense_grid = 0.
    for row in cache['curves']:
        assert len(row['points']) > 100
        for p in row['points']:
            actual = direct_objective(row['observations'], p['beta'], p['gamma'])
            error = abs(actual - p['objective'])
            assert np.isclose(actual, p['objective'], rtol=1e-9, atol=1e-10)
            max_equation_error = max(max_equation_error, error)
        if row['fit']['converged']:
            actual = direct_objective(row['observations'], row['fit']['beta_hat'], row['fit']['gamma_hat'])
            assert actual <= 1e-8
            assert row['returned']['objective'] <= actual + 1e-10
        # Denser independent shape search at true positions and each single-case node.
        if row['sample_id'] == SELECTED_ID and row['n'] == 7:
            nodes = row['points']
        elif row['sample_id'] % 10 == 0:
            nodes = [row['truth']]
        else:
            nodes = []
        dense = np.unique(np.r_[np.geomspace(1e-4, .1, 101), np.linspace(.1, 10-1e-9, 4097),
                                np.arange(.1, 5.001, .1)])
        for p in nodes:
            x, gamma = row['observations'], p['gamma']
            vals = direct_objective(x, dense, gamma)
            dense_best = float(vals.min())
            minimum = int(vals.argmin())
            if 0 < minimum < len(dense) - 1:
                optimized = minimize_scalar(lambda b: direct_objective(x, b, gamma),
                                            bounds=(dense[minimum-1], dense[minimum+1]),
                                            method='bounded', options={'xatol': 1e-11})
                dense_best = min(dense_best, float(optimized.fun))
            improvement = p['objective'] - dense_best
            assert improvement < 1e-8, (row['beta'], row['n'], row['sample_id'], gamma, improvement)
            max_better_dense_grid = max(max_better_dense_grid, improvement)
            check_rows.append([row['beta'], row['n'], row['sample_id'], gamma, improvement])
    qa = read_json(QA) if QA.exists() else {}
    qa['numeric_checks'] = {'curves': len(cache['curves']), 'nodes': sum(len(r['points']) for r in cache['curves']),
                            'max_equation_error': max_equation_error, 'independent_dense_nodes': len(check_rows),
                            'max_improvement_by_dense_search': max_better_dense_grid,
                            'dense_grid_checks': check_rows, 'original_results_unchanged': True,
                            'new_joint_estimates': 0, 'script_sha256': digest(__file__)}
    if FIGURE.exists():
        from PIL import Image
        with Image.open(FIGURE) as im:
            assert im.size == (3240, 3240)
        assert qa['figure']['sha256'] == digest(FIGURE)
    text = REPORT.read_text(encoding='utf-8')
    assert 'O_p(\\gamma)=\\inf_{0<\\beta<10}' in text
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', text)] == list(range(1, 32))
    current_metadata = next(r for r in read_json(FIGURE_QA)['process_figures'] if r['method'] == 'wmle')
    assert current_metadata == figure_metadata(qa['figure'])
    write_json(QA, qa)
    print(f"PASS：{qa['numeric_checks']['nodes']}个联合判据节点、{len(check_rows)}个独立密网格搜索；原图表数据保持一致。", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify'])
    args = parser.parse_args()
    globals()[args.action]()


if __name__ == '__main__':
    main()
