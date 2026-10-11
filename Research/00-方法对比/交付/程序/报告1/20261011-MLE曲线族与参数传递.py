"""MLE likelihood families and transmission in the same paired observations.

Keep 200 archived n=7/15 profiles and every original estimate. Add n=30
profiles from saved observations, reusing 50 beta=5 fits and fitting only the
50 already mapped beta=2 samples with the frozen joint estimator. Conditional
profiles explain the criterion; they do not replace the joint estimator.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
HELPER = HERE / '20261011-LSE曲线簇与参数传导.py'
spec = importlib.util.spec_from_file_location('r1_mle_plot_helpers', HELPER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
spec = importlib.util.spec_from_file_location('r1_mle_frozen', base.FROZEN / 'methods/mle.py')
mle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mle)
from 共用 import load_conditional_profiles
profiles = load_conditional_profiles()
DATA = HERE / '20261011-MLE曲线族与参数传递.json'
QA = HERE / '20261011-MLE曲线族与参数传递核验.json'
FIGURE = base.RESULT / '报告1/图7_MLE六格机制.png'
TRANSFER = base.RESULT / '报告1/图13_MLE参数传递.png'
REPORT2 = base.ROOT / '报告2：小样本情况下的明显异常估计.md'
PROFILE_SOURCE = base.ROOT.parents[1] / 'python/methods/conditional_profiles.py'
FAMILY_Y = [-1., 2.65]
FAMILY_TICKS = [-1, 0, 1, 2]
DEFINITIONS = [(5, '对数似然（相对真γ）', [-.15, .12], [-.15, -.1, -.05, 0, .05, .1]),
               (2, r'$\hat\beta(\gamma)$', [0, 10], [0, 2, 4, 6, 8, 10]),
               (3, r'$\hat\eta(\gamma)$', [0, 1600], [0, 500, 1000, 1500])]


def sources():
    paths = [base.INPUT / '样本.json', base.INPUT / '实际估计.json',
             base.INPUT / '逐法过程曲线.json', base.N30, base.MATRIX,
             base.FROZEN / 'methods/mle.py', base.FROZEN / 'base.py',
             PROFILE_SOURCE, HELPER, HERE.parent / '共用.py']
    return {str(p.relative_to(base.ROOT)) if p.is_relative_to(base.ROOT) else str(p): base.sha(p)
            for p in paths}


def protected_results():
    folder = base.RESULT / '报告1'
    return {p.relative_to(folder).as_posix(): base.sha(p) for p in folder.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, base.FIGURE_QA)}


def likelihood(x, beta, eta, gamma):
    """Independent full likelihood, without conditional-optimizer shortcuts."""
    d = np.asarray(x, float) - gamma
    z = np.log(d) - np.log(eta)
    return float(len(d) * (np.log(beta) - np.log(eta))
                 + (beta - 1) * z.sum() - np.exp(beta * z).sum())


def conditioned_ll(x, beta, gamma):
    """Eliminate eta algebraically for an independent shape search."""
    y = np.log(np.asarray(x) - gamma)
    power = logsumexp(beta * y) - np.log(len(y))
    return float(len(y) * (np.log(beta) - power - 1) + (beta - 1) * y.sum())


def added_curve(sample, archived):
    x = np.asarray(sample['observations'], float)
    if archived is None:
        estimator = mle.MLE(x)
        result = estimator.run()
        if result[4] is True:
            fit = dict(beta_hat=float(result[0]), eta_hat=float(result[1]), gamma_hat=float(result[2]),
                       converged=True, extra={'solution_info': copy.deepcopy(estimator.last_solution_info)})
        else:
            fit = dict(beta_hat=None, eta_hat=None, gamma_hat=None, converged=False,
                       extra={'raw_status': result[4]})
    else:
        fit = copy.deepcopy(archived)
        fit['extra'] = fit['original_record']['extra']
    selected = float(fit['gamma_hat']) if fit['converged'] else None
    top = float(x[0] - max(1e-5, x[0] * 1e-7))
    anchors = [] if selected is None else [selected, selected - 2, selected + 2, selected - 10, selected + 10]
    grid = np.unique(np.r_[np.linspace(0, top, 141), 500., anchors])
    grid = grid[(grid >= 0) & (grid <= top)]
    points = []
    for g in grid:
        r = profiles.mle_profile(x, float(g), shape_lower=1.)
        points.append([float(g), 1000 * r['location_score'] / len(x), r['beta'], r['eta'], False, r['ll']])
    return dict(method='mle', source='paired_n30', beta=sample['beta'], n=30,
                sample_id=sample['sample_id'], observations=sample['observations'],
                sample_min=float(x[0]), fit=fit, points=points,
                truth=next(p for p in points if p[0] == 500),
                returned=None if selected is None else next(p for p in points if p[0] == selected),
                estimate_origin='archived_beta5' if archived is not None else 'frozen_MLE_beta2')


def selection(rows):
    pool = [r for r in rows if r['beta'] == 5 and r['n'] == 7
            and r['fit']['converged'] and r['fit']['gamma_hat'] > 500]
    median = float(np.median([r['fit']['gamma_hat'] - 500 for r in pool]))
    eligible = [r for r in pool if next(v for v in rows if v['beta'] == 2 and v['n'] == 7
                                      and v['sample_id'] == r['sample_id'])['fit']['converged']]
    chosen = min(eligible, key=lambda r: (round(abs(r['fit']['gamma_hat'] - 500 - median), 10),
                                         r['sample_id']))
    return dict(rule='Among beta=5, n=7 successful gamma-overestimates with a successful beta=2 partner, choose gamma error closest to the median of all successful beta=5 gamma-overestimates; ties by sample ID.',
                pool_size=len(pool), median_gamma_error=median,
                eligible_ids=sorted(r['sample_id'] for r in eligible), selected_id=chosen['sample_id'],
                scope='Demonstrates a rightward likelihood peak and parameter transmission, not the direction of all MLE estimates.')


def summarize(rows):
    summary = []
    for beta, n in base.CONDITIONS:
        rr = [r for r in rows if r['beta'] == beta and r['n'] == n]
        good = [r for r in rr if r['fit']['converged']]
        g = np.array([r['fit']['gamma_hat'] for r in good])
        summary.append(dict(beta=beta, n=n, curves=len(rr), successful_estimates=len(good),
                            gamma_median=float(np.median(g)), median_absolute_gamma_error=float(np.median(abs(g - 500))),
                            gamma_above_truth=int(np.sum(g > 500)), gamma_at_zero=int(np.sum(g == 0)),
                            median_absolute_truth_location_score=float(np.median([abs(r['truth'][1] * n / 1000) for r in rr]))))
    return summary


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == sources()
        print('REUSED: MLE曲线族与参数传递数据。', flush=True)
        return
    hashes, protected = sources(), protected_results()
    samples = base.read(base.INPUT / '样本.json')
    index = {(s['beta'], s['n'], s['sample_id']): s for s in samples}
    rows = [copy.deepcopy(r) for r in base.read(base.INPUT / '逐法过程曲线.json')['curves']
            if r['method'] == 'mle' and r['source'] == 'paired']
    assert len(rows) == 200
    for r in rows:
        r['observations'] = index[r['beta'], r['n'], r['sample_id']]['observations']
    matrix, n30 = base.read(base.MATRIX), base.read(base.N30)
    assert n30['source_sha256'] == base.sha(base.MATRIX)
    archived = {r['id']: r for r in matrix['results'] if r['n'] == 30 and r['method_id'] == 'mle'}
    assert len(archived) == 50
    for i, sample in enumerate(n30['samples'], 1):
        if sample['beta'] == 5:
            original = next(s['values'] for s in matrix['samples'] if s['n'] == 30 and s['id'] == sample['sample_id'])
            assert original == sample['observations']
        rows.append(added_curve(sample, archived[sample['sample_id']] if sample['beta'] == 5 else None))
        if i % 20 == 0:
            print(f'PROFILED: n=30，{i}/100。', flush=True)
    for r in rows:
        if r['fit']['converged']:
            f = r['fit']
            r['original_log_likelihood'] = likelihood(r['observations'], f['beta_hat'], f['eta_hat'], f['gamma_hat'])
            r['original_likelihood_gain'] = r['original_log_likelihood'] - r['truth'][5]
            r['conditional_improvement_at_return'] = r['returned'][5] - r['original_log_likelihood']
        else:
            r['original_log_likelihood'] = r['original_likelihood_gain'] = r['conditional_improvement_at_return'] = None
    chosen = selection(rows)
    examples = [copy.deepcopy(next(r for r in rows if r['beta'] == b and r['n'] == 7
                                  and r['sample_id'] == chosen['selected_id'])) for b in (2, 5)]
    assert hashes == sources() and protected == protected_results()
    base.write(DATA, dict(source_hashes=hashes, protected_results=protected, curves=rows,
                         examples=examples, selection=chosen, summaries=summarize(rows),
                         columns=['gamma', '1000*location_score/n', 'conditional_beta', 'conditional_eta', 'unused', 'profile_log_likelihood'],
                         domain='beta>=1, eta>0, 0<=gamma<sample_min',
                         original_estimator='Frozen five-start joint Nelder-Mead, reject beta<1 after the search; unchanged.',
                         ordinate='profile_log_likelihood minus profile_log_likelihood at true gamma=500',
                         original_return_markers='Full likelihood evaluated at the original three-parameter tuple, not its conditional replacement.',
                         new_random_draws=0, reused_n7_n15_curves=200, added_n30_curves=100,
                         reused_beta5_n30_estimates=50, added_mapped_beta2_n30_estimates=50,
                         replaced_archived_estimates=0,
                         n30_provenance={k: v for k, v in n30.items() if k != 'samples'},
                         figure_contract={'backend': 'Python', 'exports': 'Two PNGs only',
                                          'criterion': 'beta=2/5 columns, n=7/15/30 rows, 50 profiles per cell',
                                          'transfer': 'Same paired sample, rows likelihood, conditional beta, conditional eta',
                                          'axes': 'Linear, fixed gamma limits/ticks, identical y scales for the same quantity within each figure'}))
    print(f"BUILT: 300条MLE曲线，第{chosen['selected_id']}组配对代表；原估计未替换。", flush=True)


def ordinate(p, column, row, *, centered=True):
    return p[5] - row['truth'][5] if column == 5 and centered else p[column]


def return_ordinate(row, column, *, centered=True):
    if column == 5:
        return row['original_log_likelihood'] - (row['truth'][5] if centered else 0.)
    return row['fit']['beta_hat' if column == 2 else 'eta_hat']


def draw_family(ax, rows, *, centered=True, limits=None):
    limits = FAMILY_Y if limits is None else limits
    hidden_nodes = hidden_returns = 0
    for r in rows:
        yy = [ordinate(p, 5, r, centered=centered) for p in r['points']]
        ax.plot([p[0] for p in r['points']], yy, color=base.BLUE, alpha=.20, lw=.65)
        hidden_nodes += sum(not (limits[0] <= y <= limits[1] and base.XLIM[0] <= p[0] <= base.XLIM[1])
                            for p, y in zip(r['points'], yy))
        if r['fit']['converged']:
            g, value = r['fit']['gamma_hat'], return_ordinate(r, 5, centered=centered)
            ax.scatter(g, value, color=base.RETURN, marker='x', s=10, alpha=.7, linewidths=.7, zorder=4)
            ax.plot(g, .018, marker='|', color=base.RETURN, ms=5, alpha=.55, transform=ax.get_xaxis_transform())
            hidden_returns += int(not (limits[0] <= value <= limits[1] and base.XLIM[0] <= g <= base.XLIM[1]))
    return dict(curves=len(rows), sample_ids=[r['sample_id'] for r in rows],
                original_return_markers=sum(r['fit']['converged'] for r in rows),
                hidden_curve_points=hidden_nodes, hidden_return_values=hidden_returns)


def render(*, expected_source_hashes=None, centered=True):
    data = base.read(DATA)
    assert (data['source_hashes'] if expected_source_hashes is None else expected_source_hashes) == sources()
    sid = data['selection']['selected_id']
    family_y = FAMILY_Y if centered else [-245., -30.]
    family_ticks = FAMILY_TICKS if centered else [-240, -200, -160, -120, -80, -40]
    label = '对数似然（相对真γ）' if centered else r'$\ell_p(\gamma)$'
    definitions = DEFINITIONS if centered else [(5, label, [-50., -43.], [-50, -48, -46, -44])] + DEFINITIONS[1:]
    plt = base.style()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for i, (beta, n) in enumerate(base.CONDITIONS):
        ax = axes.flat[i]
        states.append(base.axis(ax, label, beta, n, family_y, family_ticks, chr(97 + i)))
        if centered:
            ax.axhline(0, color='.6', lw=.6)
        rows = sorted((r for r in data['curves'] if r['beta'] == beta and r['n'] == n), key=lambda r: r['sample_id'])
        meta = draw_family(ax, rows, centered=centered, limits=family_y)
        if n == 7:
            example = next(r for r in rows if r['sample_id'] == sid)
            ax.plot([p[0] for p in example['points']], [ordinate(p, 5, example, centered=centered) for p in example['points']],
                    color=base.BLUE, lw=1.2, zorder=3)
        panels.append(dict(beta=beta, n=n, highlighted_sample_id=sid if n == 7 else None, **meta))
    assert all(s == states[0] for s in states)
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    first = dict(method='mle', file=FIGURE.stem, panels=panels, axis_settings=states,
                 criterion='Maximize the full likelihood; conditional profile is diagnostic.',
                 all_curves_real=True, six_panel_axes_identical=True, single_panels=[], png_dimensions=[3240, 3240])

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for row, (column, label, limits, ticks) in enumerate(definitions):
        for col, example in enumerate(data['examples']):
            beta, pp = example['beta'], example['points']
            ax = axes[row, col]
            states.append(base.axis(ax, label, beta, 7, limits, ticks, chr(97 + 2 * row + col)))
            yy = [ordinate(p, column, example, centered=centered) for p in pp]
            ax.plot([p[0] for p in pp], yy, color=base.BLUE, lw=1.25)
            ax.scatter([p[0] for p in pp], yy, s=4.5, facecolors='white', edgecolors=base.BLUE,
                       linewidths=.4, zorder=3)
            truth, returned = example['truth'], example['returned']
            selected = example['fit']['gamma_hat']
            ax.axvline(selected, color=base.RETURN, ls='--', lw=.8)
            if column != 5 or centered:
                ax.axhline(0 if column == 5 else beta if column == 2 else 1000, color='.55', ls='--', lw=.7)
            ax.scatter(500, ordinate(truth, column, example, centered=centered), color=base.BLUE, s=16, linewidths=0, zorder=5)
            ax.scatter(selected, return_ordinate(example, column, centered=centered), color=base.RETURN,
                       marker='x', s=27, linewidths=1, zorder=5)
            anchors = []
            for p, color, offset in [(truth, base.BLUE, (7, -14)), (returned, base.RETURN, (7, 9))]:
                node_id = f"G{next(i for i, v in enumerate(pp, 1) if v[0] == p[0])}"
                anchors.append(dict(node_id=node_id, conditional_point=p))
                if column == 5:
                    ax.annotate(node_id, (p[0], ordinate(p, column, example, centered=centered)), xytext=offset,
                                textcoords='offset points', fontsize=6, color=color)
            panels.append(dict(beta=beta, n=7, sample_id=sid, quantity=column, curves=1,
                               node_count=len(pp), all_actual_nodes_drawn=True,
                               points_identical_to_family=True, gamma_selected=selected, anchors=anchors,
                               marker_value=return_ordinate(example, column, centered=centered),
                               marker_is_original_estimate=True,
                               hidden_nodes=sum(not (limits[0] <= y <= limits[1] and base.XLIM[0] <= p[0] <= base.XLIM[1])
                                                for p, y in zip(pp, yy))))
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    second = dict(file=TRANSFER.stem, panels=panels, axis_settings=states,
                  same_profiles_as_criterion=True, selection=data['selection'], png_dimensions=[3240, 3240])
    qa = base.read(QA) if QA.exists() else {}
    qa.update(figures={'criterion': first, 'transfer': second},
              displayed_ordinate='profile log likelihood minus its value at true gamma' if centered else 'raw profile log likelihood; no additive shift',
              figure_hashes={p.name: base.sha(p) for p in (FIGURE, TRANSFER)})
    base.write(QA, qa)
    shared = base.read(base.FIGURE_QA)
    shared['process_figures'] = [first if r['method'] == 'mle' else r for r in shared['process_figures']]
    shared['mle_parameter_transfer'] = second
    base.write(base.FIGURE_QA, shared)
    print('EXPORTED: MLE判据曲线族与同组参数传递，两张PNG。', flush=True)
    return first


def references(text, mapping):
    def group(match):
        return re.sub(r'（(\d+)）', lambda m: '（' + str(mapping.get(int(m[1]), int(m[1]))) + '）', match[0])
    return re.sub(r'式（\d+）(?:[、和及]（\d+）)*', group, text)


def common_principles(report2):
    a = report2.index('MLE寻找使样本似然最大的形状、尺度和位置组合。')
    b = report2.index('式（24）的ℓₚ(γ)表示', a)
    common = report2[a:b]
    mapping = {21: 33, 22: 34, 23: 35, 24: 36}
    return re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(mapping[int(m[1])]) + '}', references(common, mapping))


DISCUSSION = r'''图12展示式（36）的剖面对数似然，最高点对应最优位置。图12、13均减去同一样本在真γ=500处的值，使曲线变化更清楚，最高点位置不变。橙叉按原程序返回的三个参数计算；程序仍联合搜索三参数。

![图12　MLE在不同形状与样本量下的似然判据](交付/结果/报告1/图7_MLE六格机制.png)

**图12｜高β时，真位置附近的似然更平，较远的参数组合仍可取得接近的似然。**

这种接近来自参数补偿。令Z=βln[(X−γ)/η]，其密度为exp(z−exp z)。由X=γ+ηexp(Z/β)，当中部观测的|Z|/β较小时，一阶展开得到：

$$\begin{aligned}
X&\approx\gamma+\eta+\frac{\eta}{\beta}Z,\\
\ell(\beta,\eta,\gamma)&\approx-n\ln(\eta/\beta)
+\sum_i\left(z_i-\exp z_i\right),\qquad
z_i=\frac{x_{(i)}-(\gamma+\eta)}{\eta/\beta}.
\end{aligned}
\tag{37}$$

X为Weibull随机变量，Z为标准对数Weibull变量，zᵢ为一阶近似中的标准化观测。式（37）的近似似然主要取决于γ+η和η/β：γ升高时，η和β同步降低，仍可能保留相近的中部位置与分散程度。高β、小n下，观测不足以清楚区分这些组合，样本波动便可能使似然峰偏离真位置。图12按完整的式（33）计算；式（37）解释曲线较平的原因。

增大n后，本组估计的位置偏移总体减轻。MLE的似然峰既可能右移，也可能左移，不能将所有结果概括为γ高估。

图13展开图12a、b中加深的第{sid}组配对曲线。式（35）和（34）给出各γ下的条件最优β、η，展示较优参数组合中三个参数的联动。

![图13　MLE的条件似然与参数联动](交付/结果/报告1/图13_MLE参数传递.png)

**图13｜本例的似然峰位于真γ右侧，β、η较固定真γ时降低。** 空心点为计算节点，蓝点为固定真γ的条件估计，橙叉为原程序返回值。

高β样本在γ≈935处的对数似然，比固定真γ的最优拟合仅提高约0.022，对应的条件β由约8.51降至4.51，η由约992降至550。沿条件最优组合，γ上移扩大对数距离的相对差异，式（35）对应较小β；在式（34）中，观测距离缩短与β降低共同对应较小η。该例说明，似然略高的参数组合仍可能明显偏离真值。

本例原返回值位于图示剖面峰附近，但数值收敛不保证全局最优。程序在搜索结束后剔除β<1，部分样本在其他γ处仍有更高似然的β≥1候选。曲线保留β=1分支，并按原参数标记返回值；这类求解不足需与高β下的参数补偿区分，具体见[报告2的MLE分析](报告2：小样本情况下的明显异常估计.md)。

'''


def revise(*, centered=True):
    report2 = REPORT2.read_text(encoding='utf-8')
    data = base.read(DATA)
    text = base.REPORT.read_text(encoding='utf-8')
    a, b = text.index('### 2.5　'), text.index('### 2.6　')
    before, after = text[:a], text[b:]
    existing = text[a:b]
    section = '### 2.5　[MLE](../../src/content/algorithms/mle.md)\n\n'
    discussion = DISCUSSION.replace('{sid}', str(data['selection']['selected_id']))
    if not centered:
        discussion = discussion.replace('图12、13均减去同一样本在真γ=500处的值，使曲线变化更清楚，最高点位置不变。', '')
    section += common_principles(report2) + discussion
    if r'\Delta\ell(\gamma)' in existing:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) - 1) + '}', after)
        after = references(after, {i: i - 1 for i in range(38, 46)})
    if '图13_MLE参数传递.png' not in existing:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) + 4) + '}', after)
        after = references(after, {i: i + 4 for i in range(35, 40)})
        after = re.sub(r'(?<!补充)图(\d+)(?![\d_])', lambda m: '图14' if int(m[1]) == 13 else m[0], after)
    updated = before + section + after
    updated = updated.replace('图4、6、8、10比较', '图4、6、8、10、12比较')
    old_appendix = f"图13展开n=7的第{data['selection']['selected_id']}组配对样本，展示MLE似然选择及形状、尺度对应关系。"
    appendix = f"图13展开n=7的第{data['selection']['selected_id']}组配对样本，展示剖面对数似然及条件最优β、η的联动。"
    updated = updated.replace(old_appendix, appendix)
    if appendix not in updated:
        updated = updated.replace('其余逐法组图比较', appendix + '其余逐法组图比较')
    updated = updated.replace('图4–11使用配对样本', '逐法组图使用配对样本')
    link = '[MLE曲线族与参数传递数据](交付/程序/报告1/20261011-MLE曲线族与参数传递.json)'
    if link not in updated:
        updated = updated.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    if updated != text:
        base.write_atomic(base.REPORT, updated.encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    marker = '报告1的MLE当前采用似然曲线族与同组参数联动'
    readme = readme.replace('报告1的MLE当前采用似然曲线族与同组参数传递', marker, 1)
    display_note = '绘图减去同一样本在真γ处的基准值，仅平移曲线，不改变最高点。' if centered else '绘图直接显示原始对数似然。'
    task_script = '20261012-MLE似然曲线显示恢复.py' if centered else '20261011-MLE原始对数似然图.py'
    note = (marker + '：图12按β=2/5、n=7/15/30比较β≥1的剖面对数似然，'
            f"图13展开第{data['selection']['selected_id']}组配对样本，展示剖面对数似然及条件最优β、η的联动。"
            + display_note +
            '原理、尺度和形状公式与报告2一致；γ剖面是联合准则的条件分析，不代表先估计γ的程序顺序。原返回标记采用原三个参数的似然，保留β=1分支，并区分数值收敛与全局最优。'
            '[母体程序](交付/程序/报告1/20261011-MLE曲线族与参数传递.py)保存原始计算；'
            f'[当前独立入口](交付/程序/报告1/{task_script})提供`render`、`revise`、`verify`、`all`，已接入统一制图入口。'
            '代表样本从β=5、n=7位置高估且两种β均成功的组中选取，位置偏差最接近全部高估组的中位数。'
            '复用200条n=7/15曲线和50条β=5、n=30估计，仅对已映射的β=2、n=30样本增加50条估计；无新抽样、原结果不替换。'
            '输入、曲线和核验留在程序目录，结果仅更新两张PNG。'
            '当前显示修订无新样本或估计。\n\n')
    if marker in readme:
        start = readme.index(marker)
        end = readme.find('\n\n', start)
        readme = readme[:start] + note + readme[end + 2 if end >= 0 else len(readme):]
    else:
        readme = readme.rstrip() + '\n\n' + note
    readme = readme.replace('第2.6节与图13解释', '第2.6节与图14解释').replace('图13固定删除', '图14固定删除')
    readme = readme.rstrip() + '\n'
    if readme != base.README.read_text(encoding='utf-8'):
        base.write_atomic(base.README, readme.encode('utf-8'))
    assert REPORT2.read_text(encoding='utf-8') == report2
    print('REVISED: MLE共同原理、曲线机制、同组参数传递及顺序编号。', flush=True)


def verify():
    data, qa = base.read(DATA), base.read(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    assert data['selection'] == selection(data['curves'])
    old = [r for r in base.read(base.INPUT / '逐法过程曲线.json')['curves'] if r['method'] == 'mle' and r['source'] == 'paired']
    for original in old:
        r = next(v for v in data['curves'] if (v['beta'], v['n'], v['sample_id']) == (original['beta'], original['n'], original['sample_id']))
        assert {k: r[k] for k in original} == original
    checked, ll_error, shape_error, scale_error = 0, 0., 0., 0.
    search_gain, searches, score_checks, score_error = 0., 0, 0, 0.
    conditional_gaps = []
    for r in data['curves']:
        x = np.asarray(r['observations'])
        for p in r['points']:
            gamma, beta, eta = p[0], p[2], p[3]
            actual = likelihood(x, beta, eta, gamma)
            assert np.isclose(actual, p[5], rtol=1e-10, atol=1e-8)
            ll_error = max(ll_error, abs(actual - p[5]))
            y = np.log(x - gamma)
            calculated_eta = float(np.exp((logsumexp(beta * y) - np.log(len(y))) / beta))
            assert np.isclose(calculated_eta, eta, rtol=1e-10)
            scale_error = max(scale_error, abs(calculated_eta - eta))
            weights = np.exp(beta * (y - y.max())); weights /= weights.sum()
            score = float(1 / beta + y.mean() - weights @ y)
            if beta == 1:
                assert score <= 1e-9
            else:
                assert abs(score) < 1e-9
                shape_error = max(shape_error, abs(score))
            derivative = float(len(x) * (beta * (weights @ (1 / (x - gamma))) - (beta - 1) * np.mean(1 / (x - gamma))))
            assert np.isclose(derivative, p[1] * len(x) / 1000, rtol=1e-7, atol=1e-10)
            checked += 1
        if r['fit']['converged']:
            assert r['conditional_improvement_at_return'] > -1e-8
            conditional_gaps.append(dict(beta=r['beta'], n=r['n'], sample_id=r['sample_id'],
                                         improvement=r['conditional_improvement_at_return']))
        # Independent shape maximization at every true gamma and the example's
        # return. Search has a separate objective and includes the beta=1 case.
        nodes = [r['truth']]
        if r['n'] == 7 and r['sample_id'] == data['selection']['selected_id']:
            nodes += [r['returned']]
        for p in nodes:
            result = minimize_scalar(lambda b: -conditioned_ll(x, b, p[0]),
                                     bounds=(1., max(64., 2 * p[2])), method='bounded', options={'xatol': 1e-10})
            best = max(-result.fun, conditioned_ll(x, 1., p[0]))
            gain = best - p[5]
            assert gain < 1e-8
            search_gain = max(search_gain, gain)
            searches += 1
            if p[0] > 0:
                h = min(.01, (x.min() - p[0]) / 100)
                lp = profiles.mle_profile(x, p[0] + h)['ll']
                lm = profiles.mle_profile(x, p[0] - h)['ll']
                finite = (lp - lm) / (2 * h)
                analytic = p[1] * len(x) / 1000
                assert abs(finite - analytic) < 1e-7
                score_error = max(score_error, abs(finite - analytic))
                score_checks += 1
    for n in (7, 15, 30):
        for sid in range(1, 51):
            lo, hi = [next(r for r in data['curves'] if r['beta'] == b and r['n'] == n and r['sample_id'] == sid) for b in (2, 5)]
            assert np.allclose(((np.asarray(lo['observations']) - 500) / 1000) ** 2,
                               ((np.asarray(hi['observations']) - 500) / 1000) ** 5)
    matrix = base.read(base.MATRIX)
    for r in data['curves']:
        if r['beta'] == 5 and r['n'] == 30:
            original = next(v for v in matrix['results'] if v['method_id'] == 'mle' and v['n'] == 30 and v['id'] == r['sample_id'])
            assert all(r['fit'][k] == original[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat', 'converged'))
    for r in data['examples']:
        assert r == next(v for v in data['curves'] if v['beta'] == r['beta'] and v['n'] == 7 and v['sample_id'] == r['sample_id'])
        assert r['fit']['gamma_hat'] > 500 and abs(r['conditional_improvement_at_return']) < 1e-8
        assert r['returned'][2] < r['truth'][2] and r['returned'][3] < r['truth'][3]
        assert abs(r['returned'][1]) < 1e-4
        step = .1
        assert all(profiles.mle_profile(r['observations'], r['returned'][0] + h)['ll'] < r['returned'][5]
                   for h in (-step, step))
    hi = data['examples'][1]
    assert hi['fit']['beta_hat'] < 5 and hi['fit']['eta_hat'] < 1000
    # Verify the first-order compensation explanation on fixed standardized
    # observations. As beta grows, both the likelihood approximation and a
    # second tuple preserving gamma+eta and eta/beta approach the same limit.
    approximation = []
    z = np.linspace(-1.5, 1.5, 7)
    for b in (20., 40., 80., 160.):
        x = 500 + 1000 * np.exp(z / b)
        linear_z = (x - 1500) / (1000 / b)
        approx = -len(z) * np.log(1000 / b) + np.sum(linear_z - np.exp(linear_z))
        exact = likelihood(x, b, 1000, 500)
        compensated = likelihood(x, .7 * b, 700, 800)
        approximation.append(dict(beta=b, likelihood_approximation_error=abs(approx - exact),
                                  compensated_likelihood_difference=abs(compensated - exact)))
    for key in ('likelihood_approximation_error', 'compensated_likelihood_difference'):
        assert all(approximation[i + 1][key] < approximation[i][key] for i in range(3))
    assert all(p['curves'] == 50 and p['sample_ids'] == list(range(1, 51)) for p in qa['figures']['criterion']['panels'])
    assert all(p['sample_id'] == data['selection']['selected_id'] and p['points_identical_to_family']
               and p['all_actual_nodes_drawn'] and p['marker_is_original_estimate'] for p in qa['figures']['transfer']['panels'])
    assert all(s['x_scale'] == s['y_scale'] == 'linear' and s['x_limits'] == base.XLIM and s['x_ticks'] == base.XTICKS
               for f in qa['figures'].values() for s in f['axis_settings'])
    for path in (FIGURE, TRANSFER):
        assert qa['figure_hashes'][path.name] == base.sha(path)
    report = base.REPORT.read_text(encoding='utf-8')
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)] == list(range(1, 44))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', report)] == list(range(1, 15))
    assert common_principles(REPORT2.read_text(encoding='utf-8')) in report
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent / target.split('#')[0]).exists(), target
    qa['verification'] = dict(formula_nodes_checked=checked, maximum_likelihood_error=ll_error,
                              maximum_shape_score_error=shape_error, maximum_scale_formula_error=scale_error,
                              independent_shape_searches=searches, maximum_gain_by_independent_shape_search=search_gain,
                              finite_difference_score_checks=score_checks, maximum_location_score_error=score_error,
                              source_hashes_unchanged=True, original_n7_n15_profiles_preserved=True,
                              archived_beta5_n30_estimates_preserved=True, other_report1_results_unchanged=True,
                              selected_sample=data['selection']['selected_id'], paired_latent_samples_verified=True,
                              fixed_linear_gamma_axes=True, original_joint_estimator_preserved=True,
                              original_return_likelihood_markers_verified=True,
                              common_principles_identical_to_report2_except_numbers=True,
                              new_samples=0, added_mapped_beta2_n30_estimates=50, replaced_archived_estimates=0,
                              main_figures=14, equations=43, script_sha256=base.sha(__file__))
    qa['conditional_gaps_at_original_returns'] = conditional_gaps
    qa['first_order_likelihood_approximation_checks'] = approximation
    base.write(QA, qa)
    print(qa['verification'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
