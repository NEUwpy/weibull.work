"""Figure 7: paired objective profiles and the same samples' joint beta/gamma search.

The lower panels expose both coordinates of the WMLE objective, their conditional
minimum, and the callback iterates from the archived estimator's selected start.
They use sample 29 from the upper panels. Only the WMLE PNG and its metadata change;
all new computation, original five-start traces, and checks stay in this directory.
The gamma axes match across all panels; O-profile axes match above, beta axes below.
Export PNG only. build/render/revise/verify preserve all archived estimates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
base = importlib.import_module('20261011-WMLE联合判据剖面')
DATA = HERE / '20261011-WMLE单样本联合过程.json'
QA = HERE / '20261011-WMLE单样本联合过程核验.json'
SINGLE_AXES = {**base.AXES, 'y_limits': [0., 10.3], 'y_ticks': [0., 2., 4., 6., 8., 10.]}


def sources():
    return {**base.sources(), 'paired_profile_cache': base.digest(base.CACHE)}


def instrument_estimator(row):
    """Capture each unmodified minimize call and its actual callback iterates."""
    original = base.weights.minimize
    calls = []

    def recorded_minimize(fun, *args, **kwargs):
        start = np.asarray(kwargs['x0'], float).copy()
        callback = kwargs.get('callback')
        points = [{'beta': float(start[0]), 'gamma': float(start[1]), 'objective': float(fun(start))}]

        def record(xk):
            points.append({'beta': float(xk[0]), 'gamma': float(xk[1]), 'objective': float(fun(xk))})
            if callback is not None:
                return callback(xk)

        kwargs['callback'] = record
        result = original(fun, *args, **kwargs)
        points.append({'beta': float(result.x[0]), 'gamma': float(result.x[1]),
                       'objective': float(result.fun)})
        calls.append({'start_index': len(calls), 'points': points, 'success': bool(result.success),
                      'iterations': int(result.nit), 'function_evaluations': int(result.nfev),
                      'final_objective': float(result.fun), 'final_parameters': result.x.tolist()})
        return result

    base.weights.minimize = recorded_minimize
    try:
        estimator = base.weights.WMLE(row['observations'])
        returned = estimator.run(trace=True, generate_surface=False)
    finally:
        base.weights.minimize = original
    expected = [row['fit'][key] for key in ['beta_hat', 'eta_hat', 'gamma_hat']]
    assert np.allclose(returned[:3], expected, rtol=1e-10, atol=1e-8)
    assert len(calls) == 5 and estimator.last_solution_info['status'] == 'ok'
    assert estimator.last_solution_info['selected_start'] == row['fit']['extra']['solution_info']['selected_start']
    return {'returned': returned[:3], 'solution_info': estimator.last_solution_info,
            'calls': calls, 'archived_trace': estimator.trace_data}


def build():
    base.build()
    if DATA.exists():
        assert base.read_json(DATA)['source_hashes'] == sources()
        print('REUSED：WMLE单样本联合目标与真实轨迹。', flush=True)
        return
    cache = base.read_json(base.CACHE)
    source_hashes = sources()
    protected = base.protected_results()
    protected_metadata = base.protected_figure_metadata()
    examples = []
    for beta in [2, 5]:
        row = next(r for r in cache['curves'] if r['beta'] == beta and r['n'] == 7
                   and r['sample_id'] == base.SELECTED_ID)
        trace = instrument_estimator(row)
        selected = trace['calls'][trace['solution_info']['selected_start']]
        gammas = np.unique(np.r_[np.linspace(0, 1400, 601),
                                  [p['gamma'] for p in row['points']],
                                  [p['gamma'] for p in selected['points']], 500, row['fit']['gamma_hat']])
        gammas = gammas[(gammas >= 0) & (gammas < min(row['observations']) - 1e-6)]
        betas = np.unique(np.r_[np.linspace(.15, 10 - 1e-9, 301),
                                [p['beta'] for p in row['points']],
                                [p['beta'] for p in selected['points']], beta, row['fit']['beta_hat']])
        betas = betas[(betas > 0) & (betas < 10)]
        t1, t2 = base.profiles.wmle_residuals(row['observations'], betas[:, None], gammas[None, :],
                                           base.CachedWeights)
        examples.append({'beta': beta, 'n': 7, 'sample_id': base.SELECTED_ID,
                         'gamma_grid': gammas.tolist(), 'beta_grid': betas.tolist(),
                         'objective_grid': (t1*t1 + t2*t2).tolist(),
                         'profile_points': row['points'], 'truth': row['truth'],
                         'fit': row['fit'], 'trace': trace, 'observations': row['observations']})
    assert protected == base.protected_results() and protected_metadata == base.protected_figure_metadata()
    assert source_hashes == sources()
    base.write_json(DATA, {'source_hashes': source_hashes, 'protected_results': protected,
                          'protected_figure_metadata': protected_metadata,
                          'profile_axes': base.AXES, 'single_axes': SINGLE_AXES,
                          'objective_display': [0, .015],
                          'examples': examples, 'new_samples': 0, 'replayed_samples': 2,
                          'archived_estimates_replaced': 0})
    print('BUILT：两组联合目标网格，十条原程序起点轨迹。', flush=True)


def figure_metadata(figure):
    record = base.figure_metadata(figure)
    record.update(six_panel_axes_identical=False, gamma_axes_identical=True,
                  profile_axes_identical=True, single_sample_axes_identical=True,
                  criterion='joint_objective_and_profile',
                  source_data=DATA.relative_to(base.ROOT).as_posix(),
                  profile_meaning='joint residual profile above; joint beta/gamma objective and actual trace below')
    return record


def single_panel(ax, example, cmap):
    from matplotlib import patheffects
    gamma, beta = np.asarray(example['gamma_grid']), np.asarray(example['beta_grid'])
    objective = np.asarray(example['objective_grid'])
    image = ax.pcolormesh(gamma, beta, objective, cmap=cmap, vmin=0, vmax=.015, shading='auto',
                          rasterized=True, zorder=0)
    ax.contour(gamma, beta, objective, levels=[.001, .005, .01], colors='.7', linewidths=.45, zorder=1)
    profile = example['profile_points']
    line, = ax.plot([p['gamma'] for p in profile], [p['beta'] for p in profile],
                    color=base.BLUE, lw=1.1, ls='--', zorder=3)
    line.set_path_effects([patheffects.Stroke(linewidth=2.0, foreground='white'), patheffects.Normal()])
    ax.scatter([p['gamma'] for p in profile], [p['beta'] for p in profile], s=4,
               facecolor='white', edgecolor=base.BLUE, linewidth=.4, zorder=4)
    selected = example['trace']['calls'][example['trace']['solution_info']['selected_start']]
    # Draw every callback coordinate; only exact consecutive duplicates are collapsed.
    path = np.asarray([[p['gamma'], p['beta']] for p in selected['points']])
    path = path[np.r_[True, np.any(path[1:] != path[:-1], axis=1)]]
    ax.plot(path[:, 0], path[:, 1], color=base.RETURN, lw=1.0, zorder=5)
    ax.scatter(path[::5, 0], path[::5, 1], color=base.RETURN, s=5, linewidths=0, zorder=5)
    ax.scatter(path[0, 0], path[0, 1], s=24, facecolor='white', edgecolor=base.RETURN,
               linewidth=.9, zorder=7)
    if len(path) > 10:
        i = min(8, len(path) - 2)
        ax.annotate('', xy=path[i + 1], xytext=path[max(0, i - 2)],
                    arrowprops=dict(arrowstyle='->', color=base.RETURN, lw=.8), zorder=6)
    ax.scatter(500, example['beta'], marker='D', s=20, facecolor='black', edgecolor='white',
               linewidth=.6, zorder=7)
    fit = example['fit']
    ax.scatter(fit['gamma_hat'], fit['beta_hat'], marker='x', color=base.RETURN,
               s=33, linewidth=1.25, zorder=8)
    for point in [example['truth'], next(p for p in profile if p['gamma'] == fit['gamma_hat'])]:
        is_truth = point['gamma'] == 500
        color = base.BLUE if is_truth else base.RETURN
        if is_truth:
            ax.scatter(point['gamma'], point['beta'], color=base.BLUE, s=14, linewidths=0, zorder=8)
        offset = (8, -15) if is_truth else (8, 7)
        ax.annotate(point['id'], (point['gamma'], point['beta']), xytext=offset,
                    textcoords='offset points', color=color, fontsize=6, zorder=9,
                    arrowprops=dict(arrowstyle='-', color=color, lw=.4, shrinkA=2, shrinkB=4))
    return image, {'beta': example['beta'], 'n': 7, 'sample_id': base.SELECTED_ID,
                   'sample_matches_panel': 'a' if example['beta'] == 2 else 'b',
                   'display': 'joint objective, conditional minimum, actual selected-start iterates',
                   'selected_start': selected['start_index'], 'all_callback_points_retained': True,
                   'callback_points': len(selected['points']) - 2}


def render():
    cache, data = base.read_json(base.CACHE), base.read_json(DATA)
    assert data['source_hashes'] == sources()
    base.setup_runtime()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    plt.rcParams.update({'font.family': 'sans-serif',
                         'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 7, 'axes.labelsize': 7, 'axes.titlesize': 7.2,
                         'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
                         'axes.linewidth': .7, 'axes.spines.right': False,
                         'axes.spines.top': False, 'axes.unicode_minus': False})
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 8), gridspec_kw={'height_ratios': [1, 1, 1.15]})
    panels = []
    for i, (beta, n) in enumerate(base.CONDITIONS):
        rows = [r for r in cache['curves'] if r['beta'] == beta and r['n'] == n]
        for row in rows:
            base.draw_curve(axes.flat[i], row)
        if n == 7:
            base.draw_curve(axes.flat[i], next(r for r in rows if r['sample_id'] == base.SELECTED_ID),
                            highlight=True)
        panels.append({'beta': beta, 'n': n, 'curves': len(rows)})
    cmap = LinearSegmentedColormap.from_list('wmle_joint_objective', ['#BCD4E0', '#EBF2F5', '#FFFFFF'])
    for i, example in enumerate(data['examples'], 4):
        image, panel = single_panel(axes.flat[i], example, cmap)
        panels.append(panel)
    for i, ax in enumerate(axes.flat):
        settings = base.AXES if i < 4 else SINGLE_AXES
        ax.set_xlim(settings['x_limits']); ax.set_xticks(settings['x_ticks'])
        ax.set_ylim(settings['y_limits']); ax.set_yticks(settings['y_ticks'])
        ax.set_xlabel('γ'); ax.set_ylabel(r'$O_p(\gamma)$' if i < 4 else 'β')
        ax.axvline(500, color='black', ls=':', lw=.8)
        ax.set_title(f"β={panels[i]['beta']}，n={panels[i]['n']}", loc='left', pad=9)
        ax.text(-.13, 1.10, chr(97 + i), transform=ax.transAxes, fontsize=8, weight='bold')
    fig.subplots_adjust(left=.115, right=.985, top=.945, bottom=.115, hspace=.64, wspace=.36)
    colorbar = fig.colorbar(image, cax=fig.add_axes([.40, .035, .27, .012]), orientation='horizontal',
                           ticks=[0, .005, .01, .015])
    colorbar.ax.tick_params(labelsize=6, length=2, width=.5)
    colorbar.set_ticklabels(['0.000', '0.005', '0.010', '≥0.015'])
    colorbar.set_label('O', fontsize=7, labelpad=1)
    colorbar.outline.set_linewidth(.5)
    fig.canvas.draw()
    actual_axes = [{'x_limits': list(ax.get_xlim()), 'y_limits': list(ax.get_ylim()),
                    'x_ticks': ax.get_xticks().tolist(), 'y_ticks': ax.get_yticks().tolist(),
                    'x_scale': ax.get_xscale(), 'y_scale': ax.get_yscale()} for ax in axes.flat]
    assert all(a == base.AXES for a in actual_axes[:4])
    assert all(a == SINGLE_AXES for a in actual_axes[4:])
    base.save_png(fig, base.FIGURE, dpi=450)
    plt.close(fig)
    output_path = base.FIGURE.relative_to(base.ROOT).as_posix() if base.FIGURE.is_relative_to(base.ROOT) else base.FIGURE.as_posix()
    record = base.read_json(QA) if QA.exists() else {}
    record['figure'] = {'path': output_path, 'sha256': base.digest(base.FIGURE), 'axes': actual_axes,
                        'panels': panels, 'formats': ['png'], 'dimensions': [3240, 3600],
                        'criterion': 'O=T1**2+T2**2; upper panels profile over beta; lower panels joint search',
                        'color_scale': 'linear', 'objective_display': [0, .015]}
    base.write_json(QA, record)
    metadata = base.read_json(base.FIGURE_QA)
    metadata['process_figures'] = [figure_metadata(record['figure']) if r['method'] == 'wmle' else r
                                  for r in metadata['process_figures']]
    base.write_json(base.FIGURE_QA, metadata)
    print('EXPORTED：WMLE六格图，单样本联合搜索。', flush=True)


def revise():
    text = base.REPORT.read_text(encoding='utf-8')
    start = text.index('其中，O为联合目标函数，Oₚ为固定γ下')
    end = text.index('### 2.5 ', start)
    replacement = '''其中，O为联合目标函数，Oₚ为固定γ下残差平方和的下界，边界处按极限计算。图7a–d展示Oₚ；每个点都在该γ处重新优化β。图7e、f展开上方同一单样本，在β–γ平面展示式（24）的联合目标与实际搜索过程。

![图7　WMLE的联合判据与单样本搜索过程](交付/结果/报告1/图6_WMLE六格机制.png)

**图7｜WMLE联合调整β、γ，使偏移组合的残差接近零。**

图题中的β为抽样真值。单样本图中，底色表示O，蓝虚线及圆点为各γ下使O最小的β，橙线为原程序选中起点的联合迭代，空心橙圆为起点。黑菱形为真参数，红叉为返回解。上方的深蓝曲线由下方蓝线对应的O值构成。

图7f中，真实γ=500处即使将β调至上界附近，O仍约为0.0105；联合搜索返回γ约979、β约4.20，O接近零。式（23）随后给出η约512，最终选中γ高估、β和η低估的分布。

该例在真实γ处的条件最优β接近程序上界10，计算涉及J₃的端点近似；形状范围与端点近似对偏移的贡献仍需进一步区分。

'''
    revised = text[:start] + replacement + text[end:]
    old = '[WMLE联合判据曲线](交付/程序/报告1/20261011-WMLE联合判据曲线.json)'
    if '[WMLE单样本联合过程]' not in revised:
        revised = revised.replace(old, old + '、[WMLE单样本联合过程](交付/程序/报告1/20261011-WMLE单样本联合过程.json)', 1)
    if revised != text:
        base.write_atomic(base.REPORT, revised.encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    readme = readme.replace('两者统一0<β<10与同一权重函数，均不代表联合求解轨迹。',
                            '两种条件诊断统一0<β<10与同一权重函数；报告1下方单样本另绘原程序的真实联合迭代。', 1)
    note = ('报告1的WMLE图7下方两格进一步展示同一第29组样本的β–γ联合目标、条件最优β及原程序选中起点的真实迭代。'
            '[单样本联合过程脚本](交付/程序/报告1/20261011-WMLE单样本联合过程.py)提供`build`、`render`、`revise`、`verify`；'
            '[目标网格与五起点轨迹](交付/程序/报告1/20261011-WMLE单样本联合过程.json)、'
            '[核验](交付/程序/报告1/20261011-WMLE单样本联合过程核验.json)放在程序目录。'
            '同类纵轴保持一致，六格共用γ刻度；上方纵轴为Oₚ，下方为候选β。估计复算仅记录过程，不替换原结果。'
            '统一制图入口采用本脚本；联合剖面脚本继续提供上方曲线数据。\n\n')
    readme = readme.replace('六格共用线性刻度，下方单样本仍为上方第29组；统一制图入口已接入本脚本。',
                            '本次保存联合剖面数据；后续单样本联合过程修订及当前制图入口见下。', 1)
    if note.strip() not in readme:
        readme = readme.replace('## 整理与恢复\n', note + '## 整理与恢复\n', 1)
    if readme != base.README.read_text(encoding='utf-8'):
        base.write_atomic(base.README, readme.encode('utf-8'))


def verify():
    data, cache, qa = base.read_json(DATA), base.read_json(base.CACHE), base.read_json(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == base.protected_results()
    assert data['protected_figure_metadata'] == base.protected_figure_metadata()
    checked, maximum_error = 0, 0.
    for example in data['examples']:
        row = next(r for r in cache['curves'] if r['beta'] == example['beta'] and r['n'] == 7
                   and r['sample_id'] == example['sample_id'])
        assert example['profile_points'] == row['points'] and example['fit'] == row['fit']
        for call in example['trace']['calls']:
            for point in call['points']:
                if point['objective'] >= 1e9:
                    continue
                value = base.direct_objective(example['observations'], point['beta'], point['gamma'])
                error = abs(value - point['objective'])
                assert np.isclose(value, point['objective'], atol=1e-10, rtol=1e-9)
                maximum_error = max(maximum_error, error)
                checked += 1
        # Independently check the raw objective on a deterministic grid subset.
        objective = np.asarray(example['objective_grid'])
        for i in np.linspace(0, len(example['beta_grid']) - 1, 30, dtype=int):
            for j in np.linspace(0, len(example['gamma_grid']) - 1, 30, dtype=int):
                value = base.direct_objective(example['observations'], example['beta_grid'][i], example['gamma_grid'][j])
                assert np.isclose(value, objective[i, j], atol=1e-10, rtol=1e-9)
                maximum_error = max(maximum_error, abs(value - objective[i, j]))
                checked += 1
    from PIL import Image
    with Image.open(base.FIGURE) as im:
        assert im.size == (3240, 3600)
    assert qa['figure']['sha256'] == base.digest(base.FIGURE)
    assert all(a == base.AXES for a in qa['figure']['axes'][:4])
    assert all(a == SINGLE_AXES for a in qa['figure']['axes'][4:])
    metadata = next(r for r in base.read_json(base.FIGURE_QA)['process_figures'] if r['method'] == 'wmle')
    assert metadata == figure_metadata(qa['figure'])
    report = base.REPORT.read_text(encoding='utf-8')
    assert '单样本图中，底色表示O' in report
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)] == list(range(1, 32))
    qa['numeric_checks'] = {'raw_objective_nodes_checked': checked, 'maximum_objective_error': maximum_error,
                            'replayed_samples': 2, 'selected_ids': [base.SELECTED_ID, base.SELECTED_ID],
                            'archived_estimates_unchanged': True, 'other_results_unchanged': True,
                            'upper_profile_points_unchanged': True, 'original_solver_and_weights_unchanged': True,
                            'script_sha256': base.digest(__file__)}
    base.write_json(QA, qa)
    print(f'PASS：{checked}个轨迹及网格点，原估计和其他结果保持一致。', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify'])
    args = parser.parse_args()
    globals()[args.action]()


if __name__ == '__main__':
    main()
