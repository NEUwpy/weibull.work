"""WMLE: six criterion-family panels, then a paired sample's joint solution.

Reuse all 200 saved n=7/15 joint profiles and their archived returns. Add n=30
using saved observations and the frozen estimator/weights. Joint solving remains
joint: the gamma profile is a diagnostic, not a replacement estimation rule.
Only two PNGs are exported; inputs, traces, grids and checks stay beside this file.
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib
import importlib.util
from pathlib import Path
import re
import sys

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
joint = importlib.import_module('20261011-WMLE联合判据剖面')
traces = importlib.import_module('20261011-WMLE单样本联合过程')
HELPER = HERE / '20261011-LSE曲线簇与参数传导.py'
spec = importlib.util.spec_from_file_location('wmle_family_plot_helpers', HELPER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
DATA = HERE / '20261011-WMLE曲线族与参数传递.json'
PARTS = HERE / '20261011-WMLE曲线族计算缓存'
QA = HERE / '20261011-WMLE曲线族与参数传递核验.json'
FIGURE = base.RESULT / '报告1/图6_WMLE六格机制.png'
TRANSFER = base.RESULT / '报告1/图11_WMLE参数传递.png'
REPORT2 = base.ROOT / '报告2：小样本情况下的明显异常估计.md'
CONDITIONS = base.CONDITIONS
DEFINITIONS = [(r'$O_p(\gamma)$', [-.0003, .015], [0, .005, .01, .015]),
               ('β', [0, 10.3], [0, 2, 4, 6, 8, 10]),
               (r'$\eta_p(\gamma)$', [0, 1600], [0, 500, 1000, 1500])]
GREEN = '#4B8B86'


def sources():
    paths = [joint.CACHE, base.N30, base.MATRIX, HELPER,
             HERE / '20261011-WMLE联合判据剖面.py', HERE / '20261011-WMLE单样本联合过程.py']
    return {**joint.sources(), **{str(p.relative_to(base.ROOT)): base.sha(p) for p in paths}}


def protected_results():
    folder = base.RESULT / '报告1'
    return {p.relative_to(folder).as_posix(): base.sha(p) for p in folder.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, base.FIGURE_QA)}


def selection(rows):
    pool = sorted((r for r in rows if r['beta'] == 5 and r['n'] == 7
                   and r['fit']['converged'] and r['fit']['gamma_hat'] > 500),
                  key=lambda r: (r['fit']['gamma_hat'], r['sample_id']))
    midpoint = float(np.median([r['fit']['gamma_hat'] - 500 for r in pool]))
    chosen = min(pool, key=lambda r: (round(abs(r['fit']['gamma_hat'] - 500 - midpoint), 10),
                                      r['fit']['gamma_hat'], r['sample_id']))
    return dict(rule='Among successful beta=5, n=7 gamma-overestimates, choose gamma error closest to the median; ties by smaller gamma then sample ID. Reuse the same latent sample for beta=2.',
                selected_id=chosen['sample_id'], eligible_ids=[r['sample_id'] for r in pool],
                pool_size=len(pool), median_gamma_error=midpoint,
                scope='Illustrates joint rightward solutions, not a sequential gamma-first estimator or a universal bias direction.')


def added_curve(task):
    sample, archived, hashes = task
    part = PARTS / f"beta{sample['beta']}-n30-{sample['sample_id']:02d}.json"
    if part.exists():
        cached = base.read(part)
        assert cached['source_hashes'] == hashes
        return cached['row']
    x = np.asarray(sample['observations'], float)
    if archived is None:
        estimator = joint.weights.WMLE(x)
        result = estimator.run()
        status = estimator.last_solution_info['status']
        fit = dict(beta_hat=result[0], eta_hat=result[1], gamma_hat=result[2],
                   converged=status == 'ok', status=status,
                   extra={'solution_info': estimator.last_solution_info})
    else:
        fit = copy.deepcopy(archived)
        fit['extra'] = fit['original_record']['extra']
    top = float(x[0] - max(1e-5, x[0] * 1e-7))
    selected = float(fit['gamma_hat']) if fit['converged'] else None
    extra = [500.] + ([selected, selected - 2, selected + 2, selected - 10, selected + 10]
                      if selected is not None else [])
    grid = np.unique(np.r_[np.linspace(0, top, 141), extra])
    grid = grid[(grid >= 0) & (grid <= top)]
    points = []
    for i, g in enumerate(grid, 1):
        value = joint.profiles.wmle_objective_profile(
            x, float(g), joint.CachedWeights,
            candidate_beta=fit['beta_hat'] if selected == g else None)
        points.append(dict(id=f'G{i}', gamma=float(g), **value))
    truth = next(p for p in points if p['gamma'] == 500)
    returned = next((p for p in points if p['gamma'] == selected), None)
    t1, t2 = (joint.profiles.wmle_residuals(x, fit['beta_hat'], selected, joint.CachedWeights)
              if fit['converged'] else (None, None))
    row = dict(beta=sample['beta'], n=30, sample_id=sample['sample_id'],
               observations=x.tolist(), fit=fit, points=points, truth=truth, returned=returned,
               archived_return_t1=t1, archived_return_t2=t2,
               archived_return_objective=t1*t1 + t2*t2 if t1 is not None else None,
               estimate_origin='archived_beta5' if archived is not None else 'frozen_WMLE_beta2')
    base.write(part, dict(source_hashes=hashes, row=row))
    return row


def summaries(rows):
    result = []
    for beta, n in CONDITIONS:
        rr = [r for r in rows if r['beta'] == beta and r['n'] == n]
        success = [r for r in rr if r['fit']['converged']]
        assert len(rr) == 50
        gamma = np.array([r['fit']['gamma_hat'] for r in success])
        result.append(dict(beta=beta, n=n, curves=50, successful_original_returns=len(success),
                           gamma_above_truth=int(np.sum(gamma > 500)),
                           median_absolute_gamma_error=float(np.median(abs(gamma - 500))),
                           gamma_median=float(np.median(gamma)),
                           truth_objective_median=float(np.median([r['truth']['objective'] for r in rr])),
                           truth_upper_shape_limits=sum(r['truth']['shape_at_upper_boundary'] for r in rr)))
    return result


def example(row):
    trace = traces.instrument_estimator(row)
    chosen = trace['calls'][trace['solution_info']['selected_start']]
    gamma = np.unique(np.r_[np.linspace(0, min(1400, min(row['observations']) - 1e-5), 321),
                            [p['gamma'] for p in row['points']],
                            [p['gamma'] for p in chosen['points']], 500, row['fit']['gamma_hat']])
    gamma = gamma[(gamma >= 0) & (gamma < min(row['observations']) - 1e-6)]
    beta = np.unique(np.r_[np.linspace(.1, 10 - 1e-9, 241), np.arange(.1, 5.001, .1),
                           [p['beta'] for p in row['points']],
                           [p['beta'] for p in chosen['points']], row['beta'], row['fit']['beta_hat']])
    beta = beta[(beta > 0) & (beta < 10)]
    t1, t2 = joint.profiles.wmle_residuals(row['observations'], beta[:, None], gamma[None, :],
                                         joint.CachedWeights)
    return dict(beta=row['beta'], n=7, sample_id=row['sample_id'], observations=row['observations'],
                fit=row['fit'], profile_points=row['points'], truth=row['truth'], returned=row['returned'],
                beta_grid=beta.tolist(), gamma_grid=gamma.tolist(),
                t1_grid=t1.tolist(), t2_grid=t2.tolist(), trace=trace)


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == sources()
        cleanup_parts()
        print('REUSED: WMLE曲线族、同组联合轨迹与尺度。', flush=True)
        return
    hashes, protected = sources(), protected_results()
    old = joint.read_json(joint.CACHE)
    assert old['source_hashes'] == joint.sources()
    rows = copy.deepcopy(old['curves'])
    assert len(rows) == 200
    matrix, n30 = base.read(base.MATRIX), base.read(base.N30)
    assert n30['source_sha256'] == base.sha(base.MATRIX)
    archived = {r['id']: r for r in matrix['results'] if r['n'] == 30 and r['method_id'] == 'wmle'}
    assert len(archived) == 50
    tasks = []
    PARTS.mkdir(parents=True, exist_ok=True)
    for sample in n30['samples']:
        if sample['beta'] == 5:
            original = next(s['values'] for s in matrix['samples']
                            if s['n'] == 30 and s['id'] == sample['sample_id'])
            assert sample['observations'] == original
        tasks.append((sample, archived[sample['sample_id']] if sample['beta'] == 5 else None, hashes))
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(added_curve, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
            if (len(rows) - 200) % 10 == 0:
                print(f'WMLE n=30剖面: {len(rows)-200}/100', flush=True)
    rows.sort(key=lambda r: (r['n'], r['beta'], r['sample_id']))
    selected = selection(rows)
    examples = [example(next(r for r in rows if r['beta'] == b and r['n'] == 7
                              and r['sample_id'] == selected['selected_id'])) for b in (2, 5)]
    assert hashes == sources() and protected == protected_results()
    base.write(DATA, dict(source_hashes=hashes, protected_results=protected, selection=selected,
                         curves=rows, examples=examples, summaries=summaries(rows),
                         criterion='O=T1^2+T2^2; Op(gamma)=inf_beta O, 0<beta<10',
                         weight_identity='frozen J1/J2/J3; J3 table 0.1..5, endpoint continuation outside',
                         n30_provenance={k: v for k, v in n30.items() if k != 'samples'},
                         new_random_draws=0, reused_n7_n15_profiles=200, added_n30_profiles=100,
                         reused_beta5_n30_estimates=50, added_mapped_beta2_n30_estimates=50,
                         replayed_n7_samples=2, replaced_archived_estimates=0,
                         figure_contract={'backend': 'Python', 'exports': 'Two PNGs only',
                                          'criterion': 'beta=2/5 columns, n=7/15/30 rows',
                                          'transfer': 'one paired sample; rows joint profile, joint zeros and actual trajectory, conditional scale',
                                          'axes': 'same linear gamma limits and ticks, matching y axes within every quantity'}))
    cleanup_parts()
    print(f"BUILT: 300条WMLE剖面，第{selected['selected_id']}组配对联合过程。", flush=True)


def cleanup_parts():
    """Remove verified duplicate fragments after saving the complete input."""
    if not PARTS.exists():
        return
    assert PARTS.resolve().parent == HERE.resolve()
    data = base.read(DATA)
    index = {(r['beta'], r['n'], r['sample_id']): r for r in data['curves']}
    for part in PARTS.glob('beta*-n30-*.json'):
        assert part.resolve().parent == PARTS.resolve()
        content = base.read(part)
        row = content['row']
        assert content['source_hashes'] == data['source_hashes']
        assert row == index[row['beta'], row['n'], row['sample_id']]
        part.unlink()
    PARTS.rmdir()


def curve(ax, row, single=False, highlight=False):
    pp = row['points']
    ax.plot([p['gamma'] for p in pp], [p['objective'] for p in pp], color=base.BLUE,
            alpha=1 if single or highlight else .20, lw=1.25 if single else (1.15 if highlight else .65))
    if single:
        ax.scatter([p['gamma'] for p in pp], [p['objective'] for p in pp], s=4.5,
                   facecolors='white', edgecolors=base.BLUE, linewidths=.4, zorder=3)
    ax.scatter(500, row['truth']['objective'], color=base.BLUE,
               s=16 if single else 4, alpha=1 if single else .5, linewidths=0, zorder=5)
    if row['fit']['converged']:
        g, o = row['fit']['gamma_hat'], row['archived_return_objective']
        ax.scatter(g, o, color=base.RETURN, marker='x', s=27 if single else 10,
                   alpha=1 if single else .7, linewidths=1 if single else .7, zorder=6)
        if not single:
            ax.plot(g, .018, marker='|', color=base.RETURN, ms=5, alpha=.55,
                    transform=ax.get_xaxis_transform())


def render():
    data = base.read(DATA)
    assert data['source_hashes'] == sources()
    sid = data['selection']['selected_id']
    plt = base.style()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    label, limits, ticks = DEFINITIONS[0]
    for i, (beta, n) in enumerate(CONDITIONS):
        ax = axes.flat[i]
        states.append(base.axis(ax, label, beta, n, limits, ticks, chr(97 + i)))
        rows = sorted((r for r in data['curves'] if r['beta'] == beta and r['n'] == n),
                      key=lambda r: r['sample_id'])
        for r in rows:
            curve(ax, r)
        if n == 7:
            curve(ax, next(r for r in rows if r['sample_id'] == sid), highlight=True)
        panels.append(dict(beta=beta, n=n, curves=len(rows), sample_ids=[r['sample_id'] for r in rows],
                           successful_returns=sum(r['fit']['converged'] for r in rows),
                           highlighted_sample_id=sid if n == 7 else None,
                           hidden_nodes=sum(not (limits[0] <= p['objective'] <= limits[1]
                                                 and base.XLIM[0] <= p['gamma'] <= base.XLIM[1])
                                            for r in rows for p in r['points'])))
    assert all(s == states[0] for s in states)
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    first = dict(method='wmle', file=FIGURE.stem, panels=panels, axis_settings=states,
                 single_panels=[], six_panel_axes_identical=True, criterion=data['criterion'],
                 all_curves_real=True, png_dimensions=[3240, 3240])

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for row, (label, limits, ticks) in enumerate(DEFINITIONS):
        for col, ex in enumerate(data['examples']):
            ax = axes[row, col]
            states.append(base.axis(ax, label, ex['beta'], 7, limits, ticks, chr(97 + 2*row + col)))
            fit, pp = ex['fit'], ex['profile_points']
            ax.axvline(fit['gamma_hat'], color=base.RETURN, ls='--', lw=.8)
            if row == 0:
                original = next(r for r in data['curves'] if r['beta'] == ex['beta'] and r['n'] == 7
                                and r['sample_id'] == sid)
                curve(ax, original, single=True)
                for p, color, offset in [(ex['truth'], base.BLUE, (7, 9)),
                                          (ex['returned'], base.RETURN, (7, 10))]:
                    ax.annotate(p['id'], (p['gamma'], p['objective']), xytext=offset,
                                textcoords='offset points', fontsize=6, color=color)
                quantity = 'Op'
            elif row == 1:
                ax.contour(ex['gamma_grid'], ex['beta_grid'], ex['t1_grid'], levels=[0],
                           colors=[base.BLUE], linewidths=1.15)
                ax.contour(ex['gamma_grid'], ex['beta_grid'], ex['t2_grid'], levels=[0],
                           colors=[GREEN], linewidths=1.15, linestyles='--')
                selected = ex['trace']['calls'][ex['trace']['solution_info']['selected_start']]
                path = np.array([[p['gamma'], p['beta']] for p in selected['points']])
                path = path[np.r_[True, np.any(path[1:] != path[:-1], axis=1)]]
                ax.plot(path[:, 0], path[:, 1], color=base.RETURN, lw=.85, alpha=.9, zorder=5)
                ax.scatter(path[:, 0], path[:, 1], s=2.5, color=base.RETURN, linewidths=0, zorder=5)
                ax.scatter(path[0, 0], path[0, 1], s=20, facecolors='white',
                           edgecolors=base.RETURN, linewidths=.8, zorder=6)
                ax.scatter(500, ex['beta'], marker='D', s=17, color='black',
                           edgecolors='white', linewidths=.5, zorder=6)
                ax.scatter(500, ex['truth']['beta'], color=base.BLUE, s=16, linewidths=0, zorder=6)
                ax.scatter(fit['gamma_hat'], fit['beta_hat'], color=base.RETURN, marker='x',
                           s=27, linewidths=1, zorder=7)
                from matplotlib.lines import Line2D
                ax.legend([Line2D([], [], color=base.BLUE, lw=1.15),
                           Line2D([], [], color=GREEN, lw=1.15, ls='--')],
                          [r'$T_1=0$', r'$T_2=0$'], loc='upper right', frameon=False,
                          fontsize=6, handlelength=1.6)
                quantity = 'joint_beta_gamma'
            else:
                ax.plot([p['gamma'] for p in pp], [p['eta'] for p in pp], color=base.BLUE, lw=1.25)
                ax.scatter([p['gamma'] for p in pp], [p['eta'] for p in pp], s=4.5,
                           facecolors='white', edgecolors=base.BLUE, linewidths=.4, zorder=3)
                ax.axhline(1000, color='.55', ls='--', lw=.7)
                ax.scatter(500, ex['truth']['eta'], color=base.BLUE, s=16, linewidths=0, zorder=5)
                ax.scatter(fit['gamma_hat'], fit['eta_hat'], color=base.RETURN, marker='x',
                           s=27, linewidths=1, zorder=6)
                quantity = 'eta_profile'
            panels.append(dict(beta=ex['beta'], n=7, sample_id=sid, quantity=quantity,
                               points_identical_to_family=True, node_count=len(pp),
                               actual_selected_start=ex['trace']['solution_info']['selected_start'],
                               all_callback_points_retained=True))
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    second = dict(file=TRANSFER.stem, panels=panels, axis_settings=states,
                  same_sample_as_criterion=True, selection=data['selection'], png_dimensions=[3240, 3240])
    qa = base.read(QA) if QA.exists() else {}
    qa.update(figures={'criterion': first, 'transfer': second},
              figure_hashes={p.name: base.sha(p) for p in (FIGURE, TRANSFER)})
    base.write(QA, qa)
    shared = base.read(base.FIGURE_QA)
    shared['process_figures'] = [first if r['method'] == 'wmle' else r for r in shared['process_figures']]
    shared['wmle_parameter_transfer'] = second
    base.write(base.FIGURE_QA, shared)
    print('EXPORTED: WMLE六格判据曲线族与六格联合求解、尺度传递。', flush=True)
    return first


def references(text, mapping):
    def group(match):
        return re.sub(r'（(\d+)）', lambda m: '（' + str(mapping.get(int(m[1]), int(m[1]))) + '）', match[0])
    return re.sub(r'式（\d+）(?:[、和及]（\d+）)*', group, text)


def common_principles(report2):
    a = report2.index('WMLE先根据样本量取得校准权重')
    b = report2.index('图12、13的a、d为', a)
    first = report2[a:b]
    a = report2.index('得到β̂、γ̂后，将它们代入尺度公式：', b)
    b = report2.index('J₁为尺度校准权重。', a) + len('J₁为尺度校准权重。')
    second = report2[a:b] + '\n\n'
    mapping = {17: 27, 18: 28, 19: 29, 20: 30}
    result = references(first + second, mapping)
    return re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(mapping[int(m[1])]) + '}', result)


DISCUSSION = r'''本批J₃表覆盖β=0.1—5，β>5沿用端点近似，形状搜索范围为0<β<10。

为比较不同γ下两条方程能否同时得到满足，在每个γ处最小化式（29）的联合残差：

$$\begin{aligned}
O(\beta,\gamma)&=T_1(\beta,\gamma)^2+T_2(\beta,\gamma)^2,\\
\beta_p(\gamma)&=\underset{0<\beta<10}{\arg\min}\,O(\beta,\gamma),\\
O_p(\gamma)&=O(\beta_p(\gamma),\gamma).
\end{aligned}
\tag{31}$$

其中，O为联合残差平方和，βₚ为固定γ下使O最小的形状，Oₚ为该处的最小残差。图10按式（31）绘制曲线；接近零的低点表示两条方程可在该γ处同时满足，橙叉为原程序返回解。

![图10　WMLE在不同形状与样本量下的联合判据](交付/结果/报告1/图6_WMLE六格机制.png)

**图10｜高β时，联合残差更多在真位置右侧降至接近零；n增大时位置偏移减轻。**

高β下观测较集中，真实γ处的距离相对差异较小。γ右移既缩短平均距离，也拉开距离的相对差异，从而改变两条加权方程的平衡。

这一影响可由式（27）、（28）看出。在平均距离x̄−γ处，对对数项和幂项作二阶展开；观测偏差的一次项平均为零，保留二阶项得到：

$$\begin{aligned}
T_1(\beta,\gamma)&\approx\frac{J_2(n)}{\beta}-\frac{\beta s^2}{(\overline x-\gamma)^2},\\
T_2(\beta,\gamma)&\approx1+\frac{\beta s^2}{(\overline x-\gamma)^2}-J_3(n,\beta),\\
\frac{d}{d\gamma}\frac{s^2}{(\overline x-\gamma)^2}
&=\frac{2s^2}{(\overline x-\gamma)^3}.
\end{aligned}
\tag{32}$$

其中，x̄为样本均值，s²=n⁻¹∑ᵢ(x₍ᵢ₎−x̄)²。式（32）适用于相对间距较小、候选β与相对间距之积也较小的局部范围。

γ右移时，s²不变、x̄−γ减小，距离相对差异项增大。形状方程因而需要较小β重新平衡；位置方程则同时受这一项和J₃(n,β)影响。高β时s²较小，该项在真γ附近对位置变化的响应较弱，样本波动可能对应较大的γ调整。当右移后出现共同零点，联合判据便接受偏高γ与较低β。交点位置仍取决于实际样本和校准权重，图10使用完整方程计算。

图11展开图10a、b中加深的第{sid}组配对样本。上排为原剖面曲线，中排展示式（27）、（28）的共同交点与实际联合迭代，下排将各γ处的βₚ代入式（30），得到条件尺度ηₚ(γ)。

![图11　WMLE的联合求解与尺度传递](交付/结果/报告1/图11_WMLE参数传递.png)

**图11｜β、γ在两方程的共同交点同时确定，η随后由尺度公式恢复。** 空心点为计算节点，蓝点为固定真γ的条件最优拟合，橙线为实际迭代，橙叉为返回解，黑菱形为真参数。

图11b中，真γ处的最小联合残差仍为正，右移后才接近零；图11d的共同交点因此位于真γ右侧，并对应较低β。将这对β、γ代入式（30），尺度也降低（图11f），形成γ高估、β和η低估。配对的β=2样本也有位置右移，但幅度较小。

该高β样本在真γ处的条件形状接近上界10，涉及J₃的端点近似。因此，本批偏移同时受加权方程、权重近似和搜索范围影响，不能全部归为原方法的固有性质。

'''


def revise():
    data = base.read(DATA)
    report2 = REPORT2.read_text(encoding='utf-8')
    text = base.REPORT.read_text(encoding='utf-8')
    a, b = text.index('### 2.4　'), text.index('### 2.5　')
    before, after = text[:a], text[b:]
    existing = text[a:b]
    prefix_end = existing.index('WMLE将式（25）') if 'WMLE将式（25）' in existing else existing.index('WMLE先根据样本量')
    prefix = existing[:prefix_end]
    prefix = prefix.replace('：样本集中改变校准方程的联合平衡', '')
    prefix = prefix.replace('WMLE用有限样本校准系数调整似然方程。样本统计量与校准目标的差异，会使两式的共同交点偏离真位置。',
                            'WMLE在似然方程中加入有限样本校准权重，联合估计形状与位置，再恢复尺度。')
    section = prefix + common_principles(report2) + DISCUSSION.replace('{sid}', str(data['selection']['selected_id']))
    if '图11_WMLE参数传递.png' not in existing:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) + 2) + '}', after)
        after = references(after, {**{i: i + 2 for i in range(31, 38)}, 29: 30, 30: 29})
        after = re.sub(r'(?<!补充)图(\d+)(?![\d_])',
                       lambda m: '图' + str(int(m[1]) + 1) if 11 <= int(m[1]) <= 12 else m[0], after)
    updated = before + section + after
    updated = updated.replace('图4、6、8比较β=2、5及n=7、15、30', '图4、6、8、10比较β=2、5及n=7、15、30')
    appendix = f"图11展开n=7的第{data['selection']['selected_id']}组配对样本，展示WMLE联合求解和尺度传递。"
    if appendix not in updated:
        updated = updated.replace('其余逐法组图比较', appendix + '其余逐法组图比较')
    link = '[WMLE曲线族与参数传递数据](交付/程序/报告1/20261011-WMLE曲线族与参数传递.json)'
    if link not in updated:
        updated = updated.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    if updated != text:
        base.write_atomic(base.REPORT, updated.encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    marker = '报告1的WMLE当前采用判据曲线族与同组参数传递'
    note = (marker + '：图10按β=2/5、n=7/15/30比较联合残差剖面，'
            f"图11展开第{data['selection']['selected_id']}组配对样本，展示剖面、两方程共同交点与原程序轨迹、条件尺度。"
            '残差、联合估计和尺度公式与报告2统一；剖面仅作诊断，不改为先求γ的估计规则。'
            '[独立脚本](交付/程序/报告1/20261011-WMLE曲线族与参数传递.py)提供`build`、`render`、`revise`、`verify`、`all`，已接入统一制图入口。'
            '代表样本取β=5、n=7成功位置高估组中偏差最接近中位数者，两种β使用同组。'
            'n=7/15复用200条联合剖面，n=30复用50条β=5估计，仅对已映射的β=2样本增加50条估计；两组原估计只复算轨迹，不替换结果。'
            '全部输入、节点、联合网格与核验留在程序目录，结果仅更新两张PNG。\n\n')
    if marker in readme:
        a = readme.index(marker)
        ending = readme.find('\n\n', a)
        readme = readme[:a] + note + readme[ending + 2 if ending >= 0 else len(readme):]
    else:
        readme = readme.rstrip() + '\n\n' + note
    readme = readme.replace('第2.6节与图12解释', '第2.6节与图13解释').replace('图12固定删除', '图13固定删除')
    readme = readme.replace('统一制图入口采用本脚本；联合剖面脚本继续提供上方曲线数据。',
                            '本次过程记录保留；当前制图入口采用下述WMLE曲线族与参数传递脚本。')
    for legacy in ('2026-10-11报告1的WMLE图10改为联合目标剖面',
                   '报告1的WMLE图10下方两格进一步展示'):
        start = readme.find(legacy)
        if start >= 0:
            ending = readme.find('\n\n', start)
            readme = readme[:start] + readme[ending + 2 if ending >= 0 else len(readme):]
    archive_note = ('早期WMLE联合剖面及第29组过程记录分别由'
                    '[联合剖面脚本](交付/程序/报告1/20261011-WMLE联合判据剖面.py)与'
                    '[单样本过程脚本](交付/程序/报告1/20261011-WMLE单样本联合过程.py)保存。')
    if archive_note not in readme:
        readme = readme.replace('结果仅更新两张PNG。', '结果仅更新两张PNG。' + archive_note)
    readme = readme.rstrip() + '\n'
    if readme != base.README.read_text(encoding='utf-8'):
        base.write_atomic(base.README, readme.encode('utf-8'))
    assert REPORT2.read_text(encoding='utf-8') == report2
    print('REVISED: WMLE联合原理、曲线机制、同组求解与尺度传递。', flush=True)


def verify():
    data, qa = base.read(DATA), base.read(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    old = joint.read_json(joint.CACHE)
    for r in old['curves']:
        assert r == next(v for v in data['curves'] if (v['beta'], v['n'], v['sample_id'])
                         == (r['beta'], r['n'], r['sample_id']))
    assert data['selection'] == selection(data['curves'])
    expansion_checks = []
    for beta in (2, 5):
        errors = []
        for epsilon in (.01, .005, .0025):
            x = 1500 + 1000*epsilon*np.arange(-3, 4)
            ratio = np.var(x)/(np.mean(x)-500)**2
            approximation = np.array([joint.weights.get_weight_j2(7)/beta-beta*ratio,
                                      1+beta*ratio-joint.CachedWeights.get_weight_j3(7,beta)])
            actual = np.array(joint.profiles.wmle_residuals(x,beta,500,joint.CachedWeights))
            maximum = float(np.max(abs(actual-approximation)))
            errors.append(maximum)
            expansion_checks.append(dict(beta=beta,relative_spread_step=epsilon,
                                         maximum_residual_approximation_error=maximum))
        assert errors[0]/errors[1] > 10 and errors[1]/errors[2] > 10
    checked, error, returned_error = 0, 0., 0.
    for r in data['curves']:
        for p in r['points']:
            actual = joint.direct_objective(r['observations'], p['beta'], p['gamma'])
            assert np.isclose(actual, p['objective'], rtol=1e-9, atol=1e-10)
            error = max(error, abs(actual - p['objective']))
            checked += 1
            x = np.array(r['observations']) - p['gamma']
            scale = float(np.exp(np.log(x).mean() +
                          (np.log(np.mean(np.exp(p['beta']*(np.log(x)-np.log(x).mean()))))
                           - np.log(joint.weights.get_weight_j1(len(x)))) / p['beta']))
            assert np.isclose(scale, p['eta'], rtol=1e-9)
        if r['fit']['converged']:
            actual = joint.direct_objective(r['observations'], r['fit']['beta_hat'], r['fit']['gamma_hat'])
            assert actual <= 1e-8
            returned_error = max(returned_error, abs(actual-r['archived_return_objective']))
            assert r['returned']['objective'] <= actual + 1e-10
    # Denser independent one-dimensional searches at all true positions, and at
    # every fifth profile node for the two representative samples.
    dense = np.unique(np.r_[np.geomspace(1e-4,.1,51), np.linspace(.1,10-1e-9,2049), np.arange(.1,5.001,.1)])
    dense_checks, dense_gain = 0, 0.
    for r in data['curves']:
        nodes = r['points'][::5] + [r['truth'],r['returned']] if r['n']==7 and r['sample_id']==data['selection']['selected_id'] else [r['truth']]
        for p in nodes:
            if p is None:
                continue
            values = joint.direct_objective(r['observations'], dense, p['gamma'])
            best, i = float(values.min()), int(values.argmin())
            if 0 < i < len(dense)-1:
                result = minimize_scalar(lambda b: joint.direct_objective(r['observations'],b,p['gamma']),
                                         bounds=(dense[i-1],dense[i+1]),method='bounded', options={'xatol':1e-11})
                best = min(best,float(result.fun))
            gain = p['objective']-best
            assert gain < 1e-8
            dense_gain=max(dense_gain,gain)
            dense_checks+=1
    for ex in data['examples']:
        row = next(r for r in data['curves'] if r['beta']==ex['beta'] and r['n']==7 and r['sample_id']==ex['sample_id'])
        assert ex['profile_points']==row['points'] and ex['fit']==row['fit']
        assert ex['fit']['gamma_hat']>500
        assert ex['fit']['eta_hat']<ex['truth']['eta'] and ex['fit']['beta_hat']<ex['truth']['beta']
        for call in ex['trace']['calls']:
            for point in call['points']:
                if point['objective']>=1e9:
                    continue
                actual=joint.direct_objective(ex['observations'],point['beta'],point['gamma'])
                assert np.isclose(actual,point['objective'],rtol=1e-9,atol=1e-10)
                error=max(error,abs(actual-point['objective']))
                checked+=1
        for i in np.linspace(0,len(ex['beta_grid'])-1,20,dtype=int):
            for j in np.linspace(0,len(ex['gamma_grid'])-1,20,dtype=int):
                a,b=joint.profiles.wmle_residuals(ex['observations'],ex['beta_grid'][i],ex['gamma_grid'][j],joint.CachedWeights)
                assert np.isclose(a,ex['t1_grid'][i][j]) and np.isclose(b,ex['t2_grid'][i][j])
                assert np.isclose(a*a+b*b,joint.direct_objective(ex['observations'],ex['beta_grid'][i],ex['gamma_grid'][j]))
                checked+=1
    assert data['examples'][1]['fit']['gamma_hat']>data['examples'][0]['fit']['gamma_hat']
    for n in (7,15,30):
        for sid in range(1,51):
            lo,hi=[next(r for r in data['curves'] if r['beta']==b and r['n']==n and r['sample_id']==sid) for b in (2,5)]
            assert np.allclose(((np.array(lo['observations'])-500)/1000)**2,((np.array(hi['observations'])-500)/1000)**5)
    matrix=base.read(base.MATRIX)
    for r in data['curves']:
        if r['n']==30 and r['beta']==5:
            origin=next(v for v in matrix['results'] if v['method_id']=='wmle' and v['n']==30 and v['id']==r['sample_id'])
            assert all(r['fit'][k]==origin[k] for k in ('beta_hat','eta_hat','gamma_hat','converged'))
    assert all(p['curves']==50 and p['sample_ids']==list(range(1,51)) for p in qa['figures']['criterion']['panels'])
    assert all(p['sample_id']==data['selection']['selected_id'] and p['points_identical_to_family'] for p in qa['figures']['transfer']['panels'])
    assert all(s['x_scale']==s['y_scale']=='linear' and s['x_limits']==base.XLIM and s['x_ticks']==base.XTICKS
               for f in qa['figures'].values() for s in f['axis_settings'])
    for p in (FIGURE,TRANSFER):
        assert qa['figure_hashes'][p.name]==base.sha(p)
    report=base.REPORT.read_text(encoding='utf-8')
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}',report)]==list(range(1,40))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜',report)]==list(range(1,14))
    assert common_principles(REPORT2.read_text(encoding='utf-8')) in report
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent/target.split('#')[0]).exists(),target
    qa['verification']=dict(formula_trace_and_grid_nodes_checked=checked, maximum_objective_difference=error,
                            maximum_original_return_objective_difference=returned_error,
                            independent_dense_searches=dense_checks,maximum_improvement_by_dense_search=dense_gain,
                            source_hashes_unchanged=True, original_n7_n15_profiles_preserved=True,
                            archived_beta5_n30_estimates_preserved=True,other_report1_results_unchanged=True,
                            selected_sample=data['selection']['selected_id'],paired_latent_samples_verified=True,
                            original_solver_and_weights_preserved=True, new_samples=0,
                            added_mapped_beta2_n30_estimates=50,replayed_n7_samples=2,replaced_archived_estimates=0,
                            common_principles_identical_to_report2_except_numbers=True,
                            fixed_linear_gamma_axes=True,equations=39,main_figures=13,script_sha256=base.sha(__file__))
    qa['second_order_expansion_checks'] = expansion_checks
    base.write(QA,qa)
    print(qa['verification'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['build','render','revise','verify','all'],nargs='?',default='verify')
    action=parser.parse_args().action
    for name in ['build','render','revise','verify'] if action=='all' else [action]:
        globals()[name]()
