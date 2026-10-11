"""LSE criterion families followed by the same paired representative's transfer.

Read the saved mother-script profiles without drawing samples or estimating
parameters. Save the selection, displayed nodes, inputs and checks for this task.
Export only the two current LSE PNGs and revise only the LSE discussion.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
MOTHER = HERE / '20261011-LSE曲线簇与参数传导.py'
spec = importlib.util.spec_from_file_location('lse_mother', MOTHER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
DATA = HERE / '20261011-LSE代表样本传递.json'
QA = HERE / '20261011-LSE代表样本传递核验.json'
DEFINITIONS = [(1, r'$1-R^2(\gamma)$', [0, .25], [0, .05, .10, .15, .20, .25]),
               (2, r'$\hat\beta(\gamma)$', [0, 10], [0, 2, 4, 6, 8, 10]),
               (3, r'$\hat\eta(\gamma)$', [0, 1600], [0, 500, 1000, 1500])]


def source_hashes():
    return {p.name: base.sha(p) for p in (MOTHER, base.CACHE, base.QA)}


def selection(source):
    pool = sorted((r for r in source['curves']
                   if r['beta'] == 5 and r['n'] == 7 and r['fit']['gamma_hat'] > 500),
                  key=lambda r: (r['fit']['gamma_hat'], r['sample_id']))
    midpoint = float(np.median([r['fit']['gamma_hat'] - 500 for r in pool]))
    chosen = min(pool, key=lambda r: (round(abs(r['fit']['gamma_hat'] - 500 - midpoint), 10),
                                      r['fit']['gamma_hat'], r['sample_id']))
    return dict(rule='Among beta=5, n=7 profiles with gamma_hat>500, choose gamma error closest to the pool median; ties by smaller gamma then sample_id. Reuse the same latent-sample ID for beta=2.',
                eligible_ids=[r['sample_id'] for r in pool], pool_size=len(pool),
                median_gamma_error=midpoint, selected_id=chosen['sample_id'],
                selected_gamma_error=chosen['fit']['gamma_hat'] - 500,
                scope='Rightward-shift transmission example, not a frequency claim or an unbiased beta=2 example.')


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == source_hashes()
        print('REUSED: LSE代表样本与节点。', flush=True)
        return
    source = base.read(base.CACHE)
    assert source['source_hashes'] == base.sources()
    chosen = selection(source)
    rows = [copy.deepcopy(next(r for r in source['curves']
                              if r['beta'] == b and r['n'] == 7
                              and r['sample_id'] == chosen['selected_id'])) for b in (2, 5)]
    base.write(DATA, dict(source_hashes=source_hashes(), protected_results=base.protected_results(),
                         selection=chosen, profiles=rows,
                         figure_contract={'criterion': 'Curve families establish criterion sensitivity and location selection across beta and n.',
                                          'transfer': 'One paired sample follows the selected gamma through conditional beta and eta.',
                                          'layout': 'Quantitative grids, beta=2/5 columns; transfer rows are criterion, beta, eta.',
                                          'backend': 'Python', 'exports': 'Two current PNGs only'},
                         new_samples=0, new_estimates=0, replaced_estimates=0))
    print(f"BUILT: 第{chosen['selected_id']}组配对代表，{chosen['pool_size']}组位置高估样本中接近中位数。", flush=True)


def render():
    data, source = base.read(DATA), base.read(base.CACHE)
    assert data['source_hashes'] == source_hashes()
    assert source['source_hashes'] == base.sources()
    selected_id = data['selection']['selected_id']
    plt = base.style()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for i, (beta, n) in enumerate(base.CONDITIONS):
        ax = axes.flat[i]
        column, label, limits, ticks = DEFINITIONS[0]
        states.append(base.axis(ax, label, beta, n, limits, ticks, chr(97 + i)))
        rows = sorted((r for r in source['curves'] if r['beta'] == beta and r['n'] == n),
                      key=lambda r: r['sample_id'])
        metadata = base.bundle(ax, rows, column)
        if n == 7:
            representative = next(r for r in rows if r['sample_id'] == selected_id)
            pp = representative['points']
            ax.plot([p[0] for p in pp], [p[column] for p in pp], color=base.BLUE,
                    lw=1.15, zorder=3)
        panels.append(dict(beta=beta, n=n, highlighted_sample_id=selected_id if n == 7 else None,
                           **metadata))
    assert all(s == states[0] for s in states)
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, base.FIGURE, dpi=450)
    plt.close(fig)
    first = dict(method='lse', file=base.FIGURE.stem, panels=panels, axis_settings=states,
                 all_curves_real=True, six_panel_axes_identical=True, single_panels=[],
                 png_dimensions=[3240, 3240])

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for row_index, (column, label, limits, ticks) in enumerate(DEFINITIONS):
        for col, profile in enumerate(data['profiles']):
            beta, pp = profile['beta'], profile['points']
            ax = axes[row_index, col]
            states.append(base.axis(ax, label, beta, 7, limits, ticks, chr(97 + row_index * 2 + col)))
            ax.plot([p[0] for p in pp], [p[column] for p in pp], color=base.BLUE, lw=1.25)
            ax.scatter([p[0] for p in pp], [p[column] for p in pp], s=4.5,
                       facecolors='white', edgecolors=base.BLUE, linewidths=.4, zorder=3)
            truth, returned = profile['truth'], profile['returned']
            ax.axvline(returned[0], color=base.RETURN, ls='--', lw=.8)
            if column in (2, 3):
                ax.axhline(beta if column == 2 else 1000, color='.55', ls='--', lw=.7)
            ax.scatter(500, truth[column], color=base.BLUE, s=16, linewidths=0, zorder=5)
            ax.scatter(returned[0], returned[column], color=base.RETURN, marker='x',
                       s=27, linewidths=1, zorder=5)
            anchors = []
            for p, color, offset in [(truth, base.BLUE, (7, 9)), (returned, base.RETURN, (7, -14))]:
                index = next(i for i, v in enumerate(pp, 1) if v[0] == p[0])
                anchors.append(dict(node_id=f'G{index}', point=p[:4]))
                if column == 1:
                    ax.annotate(f'G{index}', (p[0], p[column]), xytext=offset,
                                textcoords='offset points', fontsize=6, color=color)
            panels.append(dict(beta=beta, n=7, sample_id=selected_id, quantity=column,
                               criterion_panel='a' if beta == 2 else 'b', curves=1,
                               node_count=len(pp), all_actual_nodes_drawn=True,
                               gamma_selected=returned[0], anchors=anchors,
                               points_identical_to_multi_sample=True,
                               hidden_nodes=sum(not (limits[0] <= p[column] <= limits[1]
                                                     and base.XLIM[0] <= p[0] <= base.XLIM[1]) for p in pp)))
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, base.TRANSFER, dpi=450)
    plt.close(fig)
    second = dict(file=base.TRANSFER.stem, panels=panels, axis_settings=states,
                  same_profiles_as_criterion=True, selection=data['selection'],
                  png_dimensions=[3240, 3240])
    qa = base.read(QA) if QA.exists() else {}
    qa.update(figures={'criterion': first, 'transfer': second},
              figure_hashes={p.name: base.sha(p) for p in (base.FIGURE, base.TRANSFER)})
    base.write(QA, qa)
    shared = base.read(base.FIGURE_QA)
    shared['process_figures'] = [first if r['method'] == 'lse' else r for r in shared['process_figures']]
    shared['lse_parameter_transfer'] = second
    base.write(base.FIGURE_QA, shared)
    print('EXPORTED: 判据曲线族与配对代表性样本传递，两张PNG。', flush=True)
    return first


def revise():
    data = base.read(DATA)
    sid = data['selection']['selected_id']
    section = base.SECTION.replace(
        '其中，z̄为参考坐标的均值。图7使用图6a、b中的全部曲线，按式（16）、（12）展示位置选择向形状、尺度的传导。',
        f'其中，z̄为参考坐标的均值。图7展开图6a、b中加深的第{sid}组配对曲线：式（14）确定γ，式（16）、（12）给出该γ对应的β、η。')
    section = section.replace(
        '**图7｜所选γ通过回归斜率和截距传递到β、η。** 蓝点为固定真γ的条件拟合，橙叉为最终估计。',
        '**图7｜判据选出的偏高γ，对应较低的β、η。** 空心点为计算节点，蓝点为固定真γ的条件估计，橙叉为最终估计。')
    old = ('图7中，γ右移使较小观测的对数距离下降更多，回归斜率增大，按式（12）取倒数后β降低；'
           '截距按式（16）随右移减小，进而得到图7e、f中的η降低。左移则可产生相反变化。'
           'LSE选择的是线性匹配更好的位置，高β下的位置区分不足使这一选择更容易伴随参数偏移。')
    new = ('图7a、b中，准则最低点均在真γ右侧，β=5的右移幅度更大。'
           'γ右移使较小观测的对数距离下降更多，回归斜率增大，按式（12）取倒数后β降低（图7c、d）；'
           '本例截距随γ右移减小，按式（12）恢复的η也降低（图7e、f）。'
           '因此，准则选择的位置偏移通过同一条回归线传递到形状和尺度，形成γ高估、β和η低估。'
           '图6中的其他样本也可能选择偏低γ，并产生相反方向的参数变化。')
    assert old in section
    section = section.replace(old, new)
    text = base.REPORT.read_text(encoding='utf-8')
    start, end = text.index('### 2.2　'), text.index('### 2.3　')
    updated = text[:start] + section + text[end:]
    from importlib import import_module
    alignment = import_module('20261011-LSE原理表述统一')
    updated = alignment.align_report(updated)
    updated = updated.replace('图7展示n=7的参数传导曲线簇', f'图7展开n=7的第{sid}组配对样本，展示参数传递')
    link = '[LSE代表样本传递数据](交付/程序/报告1/20261011-LSE代表样本传递.json)'
    if link not in updated:
        updated = updated.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    if updated != text:
        base.write_atomic(base.REPORT, updated.encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    marker = '报告1的LSE原理与报告2统一'
    note = ('报告1的LSE原理与报告2统一：最大化F比等价于最小化1−R²。图6为β=2/5、n=7/15/30的判据曲线族，'
            f'图7展开图6a、b中加深的第{sid}组配对样本，依次展示判据、条件β和η。'
            '代表样本取β=5、n=7位置高估组中偏差最接近中位数者，β=2沿用同组；选择及全部节点保存在程序目录。'
            '[20261011-LSE代表样本传递.py](交付/程序/报告1/20261011-LSE代表样本传递.py)提供`build`、`render`、`revise`、`verify`和`all`，已接入统一制图入口；'
            '复用[母体程序与数据](交付/程序/报告1/20261011-LSE曲线簇与参数传导.py)，本轮无新样本、无新估计，只更新两张PNG及相应正文。\n\n')
    assert marker in readme
    a = readme.index(marker)
    b = readme.index('\n\n', a) + 2
    updated_readme = readme[:a] + note + readme[b:]
    if updated_readme != readme:
        base.write_atomic(base.README, updated_readme.encode('utf-8'))
    alignment.run()
    print('REVISED: LSE图文衔接与任务复现记录。', flush=True)


def verify():
    data, qa, source = base.read(DATA), base.read(QA), base.read(base.CACHE)
    assert data['source_hashes'] == source_hashes()
    assert source['source_hashes'] == base.sources()
    assert data['protected_results'] == base.protected_results()
    assert data['selection'] == selection(source)
    checked, maximum = 0, 0.
    for r in data['profiles']:
        original = next(v for v in source['curves'] if v['beta'] == r['beta']
                        and v['n'] == r['n'] and v['sample_id'] == r['sample_id'])
        assert r == original
        for p in r['points']:
            fit = base.regression(r['observations'], p[0])
            error = max(abs(p[1] - fit['loss']), abs(p[2] - fit['beta']), abs(p[3] - fit['eta']))
            maximum = max(maximum, error)
            assert np.allclose(p[1:4], [fit['loss'], fit['beta'], fit['eta']], rtol=1e-9, atol=1e-7)
            assert fit['slope_derivative'] > 0 and fit['intercept_derivative'] < 0
            checked += 1
        chosen = base.regression(r['observations'], r['returned'][0])
        assert np.allclose([chosen['beta'], chosen['eta']], [r['fit']['beta_hat'], r['fit']['eta_hat']])
        assert np.isclose(chosen['f'], r['fit']['extra']['solution_info']['f_max'])
        assert r['returned'][0] > 500 and r['returned'][2] < r['truth'][2] and r['returned'][3] < r['truth'][3]
        assert r['returned'][2] < r['beta'] and r['returned'][3] < 1000
    low, high = data['profiles']
    assert np.allclose(((np.asarray(low['observations']) - 500) / 1000)**2,
                       ((np.asarray(high['observations']) - 500) / 1000)**5)
    assert high['returned'][0] > low['returned'][0]
    assert all(p['curves'] == 50 and p['sample_ids'] == list(range(1, 51))
               for p in qa['figures']['criterion']['panels'])
    assert all(p['curves'] == 1 and p['sample_id'] == data['selection']['selected_id']
               and p['points_identical_to_multi_sample'] and p['all_actual_nodes_drawn']
               for p in qa['figures']['transfer']['panels'])
    assert [p['quantity'] for p in qa['figures']['transfer']['panels']] == [1, 1, 2, 2, 3, 3]
    assert all(s['x_scale'] == s['y_scale'] == 'linear' and s['x_limits'] == base.XLIM
               and s['x_ticks'] == base.XTICKS for f in qa['figures'].values() for s in f['axis_settings'])
    for p in (base.FIGURE, base.TRANSFER):
        assert qa['figure_hashes'][p.name] == base.sha(p)
    report = base.REPORT.read_text(encoding='utf-8')
    tags = [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)]
    assert tags == list(range(1, 36))
    from importlib import import_module
    import_module('20261011-LSE原理表述统一').verify_common(report)
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', report)] == list(range(1, 12))
    assert f"第{data['selection']['selected_id']}组配对曲线" in report
    assert '图7使用图6a、b中的全部曲线' not in report and '图7展示n=7的参数传导曲线簇' not in report
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent / target.split('#')[0]).exists(), target
    qa['verification'] = dict(formula_nodes_checked=checked, maximum_absolute_formula_difference=maximum,
                              selected_sample=data['selection']['selected_id'], paired_latent_sample_verified=True,
                              selection_rule_verified=True, source_hashes_unchanged=True,
                              profiles_identical_to_family=True, original_estimates_unchanged=True,
                              other_report1_results_unchanged=True, fixed_linear_axes=True,
                              new_samples=0, new_estimates=0, main_figures=11, equations=35,
                              script_sha256=base.sha(Path(__file__)))
    base.write(QA, qa)
    print(qa['verification'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
