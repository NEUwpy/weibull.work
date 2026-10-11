"""Report 1 MMLE: minimum location, actual shape-score families, and scale.

Reuse archived observations and fits. Only the 50 saved beta=2, n=30 samples
need new official fits. Fixed-true-location diagnostics retain the same n-1
observations; they do not change the MMLE estimator or replace its returns.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, RESULT, setup_runtime, save_png, write_atomic, load_conditional_profiles
setup_runtime()
base = SimpleNamespace(ROOT=ROOT, RESULT=RESULT, INPUT=RESULT / '报告1/中间数据',
                       N30=HERE / '20261010-导入图n30样本.json',
                       MATRIX=HERE.parent / 'W5,1000,500/完整矩阵/数据/matrix.json',
                       REPORT=ROOT / '报告1：高形状参数下的估计偏移.md', README=ROOT / 'README.md',
                       BLUE='#345D7E', RETURN='#B55E3E', save_png=save_png, write_atomic=write_atomic)
base.read = lambda path: json.loads(Path(path).read_text(encoding='utf-8-sig'))
base.sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
base.write = lambda path, obj: write_atomic(path, (json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8'))


def style():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 7, 'axes.labelsize': 7, 'axes.titlesize': 7.2,
                         'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'axes.linewidth': .7,
                         'axes.spines.right': False, 'axes.spines.top': False, 'axes.unicode_minus': False})
    return plt


base.style = style
profiles = load_conditional_profiles()
PROJECT = base.ROOT.parents[1]
sys.path.insert(0, str(PROJECT / 'python'))

OLD = HERE / '20261011-MMLE估计与曲线.json'
DATA = HERE / '20261011-MMLE定位与形状尺度.json'
QA = HERE / '20261011-MMLE定位与形状尺度核验.json'
REPORT2 = base.ROOT / '报告2：小样本情况下的明显异常估计.md'
FIGURE = base.RESULT / '报告1/图8_MMLE六格机制.png'
TRANSFER = base.RESULT / '报告1/图15_MMLE定位与形状尺度.png'
JOINT_QA = base.INPUT / '逐法图核验.json'
MMLE_CODE = PROJECT / 'python/methods/mmle.py'
FROZEN_CODE = HERE.parent / 'W5,1000,500/依赖快照/python/methods/mmle.py'
CONDITIONS = [(b, n) for n in (7, 15, 30) for b in (2, 5)]
BLIM, BTICKS = [.5, 10.], [1, 2, 4, 6, 8, 10]
ULIM, UTICKS = [-.6, .9], [-.5, 0, .5]


def sources():
    paths = [OLD, base.INPUT / '样本.json', base.N30, base.MATRIX,
             MMLE_CODE, FROZEN_CODE, PROJECT / 'python/methods/conditional_profiles.py',
             HERE.parent / '共用.py']
    return {p.relative_to(PROJECT).as_posix(): base.sha(p) for p in paths}


def protected_results():
    folder = base.RESULT / '报告1'
    return {p.relative_to(folder).as_posix(): base.sha(p) for p in folder.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, JOINT_QA)}


def criterion(observations, beta, gamma):
    """Original MMLE shape score; always delete exactly the first observation."""
    x = np.sort(np.asarray(observations, float))[1:]
    y = np.log(x - gamma)
    z = y - y.mean()
    w = np.exp(beta * (z - z.max()))
    w /= w.sum()
    score = float(1 / beta - w @ z)
    scale = float(np.exp(y.mean() + (logsumexp(beta * z) - np.log(len(y))) / beta))
    derivative = float(-1 / beta ** 2 - w @ (z - w @ z) ** 2)
    return score, scale, derivative


def row(sample, fit, origin):
    x = np.sort(np.asarray(sample['observations'], float))
    gamma = float(x[0])
    reference = profiles.mle_profile(x[1:], 500., shape_lower=0.)
    root = profiles.mle_profile(x[1:], gamma, shape_lower=0.)
    grid = np.unique(np.r_[np.linspace(*BLIM, 151), sample['beta'], root['beta']])
    if fit['converged']:
        grid = np.unique(np.r_[grid, fit['beta_hat']])
    points = [[float(b), *criterion(x, float(b), gamma)[:2]] for b in grid]
    return dict(beta=sample['beta'], n=sample['n'], sample_id=sample['sample_id'],
                observations=x.tolist(), retained=x[1:].tolist(), sample_min=gamma,
                fit=copy.deepcopy(fit), estimate_origin=origin, reference=reference,
                diagnostic_root=root, score_at_true_shape=criterion(x, sample['beta'], gamma)[0],
                points=points)


def summarize(rows):
    output = []
    for b, n in CONDITIONS:
        rr = [r for r in rows if (r['beta'], r['n']) == (b, n)]
        ok = [r for r in rr if r['fit']['converged']]
        output.append(dict(beta=b, n=n, samples=len(rr), successful=len(ok),
                           score_at_true_shape_negative=sum(r['score_at_true_shape'] < 0 for r in rr),
                           shape_below_truth=sum(r['fit']['beta_hat'] < b for r in ok),
                           scale_below_truth=sum(r['fit']['eta_hat'] < 1000 for r in ok),
                           beta_median=float(np.median([r['fit']['beta_hat'] for r in ok])),
                           eta_median=float(np.median([r['fit']['eta_hat'] for r in ok])),
                           gamma_median=float(np.median([r['fit']['gamma_hat'] for r in ok])),
                           hidden_return_shapes=sum(not BLIM[0] <= r['fit']['beta_hat'] <= BLIM[1] for r in ok)))
    return output


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == sources()
        print('REUSED: MMLE定位与形状尺度数据。', flush=True)
        return
    # Earlier report figures load an older frozen methods package without MMLE.
    # A fresh interpreter keeps new official fits on the shared registry.
    loaded = sys.modules.get('methods')
    if loaded is not None and all(Path(p).resolve() != (PROJECT / 'python/methods').resolve()
                                  for p in loaded.__path__):
        subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), 'build'], check=True)
        return
    from studies.common.runner import run_method
    from methods.mmle import MMLE
    hashes, protected = sources(), protected_results()
    assert base.sha(MMLE_CODE) == base.sha(FROZEN_CODE)
    old = base.read(OLD)
    samples = base.read(base.INPUT / '样本.json')
    fits = {(r['beta'], r['n'], r['sample_id']): r for r in old['paired_records']}
    rows = [row(s, fits[s['beta'], s['n'], s['sample_id']], 'archived_paired')
            for s in samples if (s['beta'], s['n']) in CONDITIONS]
    matrix, n30 = base.read(base.MATRIX), base.read(base.N30)
    assert n30['source_sha256'] == base.sha(base.MATRIX)
    archived = {r['id']: r for r in matrix['results'] if r['method_id'] == 'mmle' and r['n'] == 30}
    for sample in n30['samples']:
        if sample['beta'] == 5:
            fit, origin = archived[sample['sample_id']], 'archived_beta5_n30'
        else:
            fit, origin = run_method('mmle', sample['observations']), 'official_beta2_n30_saved_observations'
        rows.append(row(sample, fit, origin))
    assert len(rows) == 300
    sid = old['selected_id']
    examples = []
    for b in (2, 5):
        r = copy.deepcopy(next(r for r in rows if (r['beta'], r['n'], r['sample_id']) == (b, 7, sid)))
        grid = np.unique(np.r_[np.linspace(*BLIM, 61), b, r['reference']['beta'], r['fit']['beta_hat']])
        r['comparison'] = [dict(gamma=g, points=[[float(v), *criterion(r['observations'], float(v), g)[:2]] for v in grid])
                           for g in (500., r['sample_min'])]
        model = MMLE(r['observations'])
        traced = model.run(trace=True)
        assert traced[4] == r['fit']['converged']
        assert np.allclose(traced[:3], [r['fit'][k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')], atol=1e-8, rtol=1e-10)
        r['trace'] = model.trace_data
        r['trace_solution_info'] = model.last_solution_info
        examples.append(r)
    cache = dict(date='2026-10-11', method='Kundu-Raqab single-sample min/delete-one',
                 source_hashes=hashes, protected_results=protected, new_samples=0,
                 added_beta2_n30_estimates=50, reused_estimates=250, replaced_archived_estimates=0,
                 selection=dict(selected_id=sid, rule=old['selection'], original_selection_cache=str(OLD.relative_to(base.ROOT))),
                 curves=rows, examples=examples, summary=summarize(rows),
                 contract=dict(family='Actual MMLE shape score versus beta, after minimum location',
                               representative='Same retained observations: true-location reference and actual minimum location',
                               backend='Python', format='PNG', axes='linear', no_gamma_search=True))
    assert sources() == hashes
    base.write(DATA, cache)
    print('BUILT: 300条MMLE形状得分曲线；复用250条估计，仅计算50条已存β=2、n=30样本。', flush=True)


def axes(ax, xlabel, ylabel, xlim, xticks, ylim, yticks, letter, title):
    ax.set(xlabel=xlabel, ylabel=ylabel, xlim=xlim, xticks=xticks, ylim=ylim, yticks=yticks)
    ax.set_title(title, loc='left', pad=9)
    ax.text(-.13, 1.10, letter, transform=ax.transAxes, weight='bold', fontsize=8)
    return dict(x_limits=list(xlim), x_ticks=list(xticks), y_limits=list(ylim), y_ticks=list(yticks),
                x_scale=ax.get_xscale(), y_scale=ax.get_yscale())


def render():
    from matplotlib.lines import Line2D
    data = base.read(DATA)
    assert data['source_hashes'] == sources()
    plt = base.style()
    fig, aa = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, settings = [], []
    for i, (b, n) in enumerate(CONDITIONS):
        ax = aa.flat[i]
        settings.append(axes(ax, 'β', r'$U_\beta(\beta;\hat\gamma)$', BLIM, BTICKS, ULIM, UTICKS,
                             chr(97 + i), f'β={b}，n={n}'))
        ax.axhline(0, color='#777777', lw=.65, zorder=0)
        ax.axvline(b, color='black', ls=':', lw=.75, zorder=0)
        rr = [r for r in data['curves'] if (r['beta'], r['n']) == (b, n)]
        for r in rr:
            p = np.asarray(r['points'])
            ax.plot(p[:, 0], p[:, 1], color=base.BLUE, alpha=.18, lw=.65)
            if r['fit']['converged']:
                score = criterion(r['observations'], r['fit']['beta_hat'], r['sample_min'])[0]
                ax.scatter(r['fit']['beta_hat'], score, color=base.RETURN, marker='x', s=9, linewidths=.6, alpha=.65, zorder=3)
        if n == 7:
            chosen = next(r for r in rr if r['sample_id'] == data['selection']['selected_id'])
            p = np.asarray(chosen['points'])
            ax.plot(p[:, 0], p[:, 1], color=base.BLUE, lw=1.3, zorder=4)
            ax.scatter(chosen['fit']['beta_hat'], criterion(chosen['observations'], chosen['fit']['beta_hat'], chosen['sample_min'])[0],
                       color=base.RETURN, marker='x', s=27, linewidths=1, zorder=5)
        panels.append(dict(beta=b, n=n, curves=len(rr), sample_ids=[r['sample_id'] for r in rr],
                           shape_on_horizontal_axis=True, shape_score_from_actual_retention=True,
                           original_returns_preserved=True))
    fig.legend([Line2D([], [], color=base.BLUE, lw=1), Line2D([], [], color=base.RETURN, marker='x', ls='None', ms=4),
                Line2D([], [], color='black', ls=':', lw=.75)], ['形状得分', 'MMLE返回值', '真β'],
               ncol=3, loc='upper center', bbox_to_anchor=(.54, .995), frameon=False, fontsize=7)
    fig.subplots_adjust(left=.12, right=.985, top=.925, bottom=.075, hspace=.60, wspace=.36)
    base.save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    family = dict(panels=panels, axis_settings=settings, dimensions=[3240, 3240])
    fig, aa = plt.subplots(3, 2, figsize=(7.2, 7.2))
    settings, panels = [], []
    for col, r in enumerate(data['examples']):
        b, x = r['beta'], np.asarray(r['observations'])
        ax = aa[0, col]
        settings.append(axes(ax, '观测序号 i', r'$\ln(x_{(i)}-\gamma)$', [1.6, 7.4], range(2, 8), [4.5, 8], [5, 6, 7, 8],
                             chr(97 + col), f'β={b:g}，n=7，#{r["sample_id"]}'))
        ids = np.arange(2, 8)
        ax.plot(ids, np.log(x[1:] - 500), color=base.BLUE, marker='o', mfc='white', ms=3.2, lw=.8)
        ax.plot(ids, np.log(x[1:] - x[0]), color=base.RETURN, marker='x', ms=3.5, lw=.8)
        for rr, ylabel, ylim, yticks in ((1, r'$U_\beta(\beta;\gamma)$', ULIM, UTICKS),
                                        (2, r'$\hat\eta(\beta,\gamma)$', [0, 1800], [0, 500, 1000, 1500])):
            ax = aa[rr, col]
            settings.append(axes(ax, 'β', ylabel, BLIM, BTICKS, ylim, yticks,
                                 chr(97 + rr * 2 + col), f'β={b:g}，n=7，#{r["sample_id"]}'))
            if rr == 1:
                ax.axhline(0, color='#777777', lw=.65, zorder=0)
                ax.axvline(b, color='black', ls=':', lw=.75, zorder=0)
            else:
                ax.axhline(1000, color='black', ls=':', lw=.75, zorder=0)
            for state, color in zip(r['comparison'], (base.BLUE, base.RETURN)):
                p = np.asarray(state['points'])
                ax.plot(p[:, 0], p[:, rr], color=color, lw=1.1)
                ax.scatter(p[:, 0], p[:, rr], s=8, facecolor='white', edgecolor=color, lw=.4, zorder=3)
            ref = r['reference']
            ax.scatter(ref['beta'], criterion(x, ref['beta'], 500)[0] if rr == 1 else ref['eta'],
                       s=26, facecolor='white', edgecolor=base.BLUE, lw=1.05, zorder=5)
            ax.scatter(r['fit']['beta_hat'], criterion(x, r['fit']['beta_hat'], x[0])[0] if rr == 1 else r['fit']['eta_hat'],
                       s=29, color=base.RETURN, marker='x', lw=1.1, zorder=5)
        panels.append(dict(beta=b, n=7, sample_id=r['sample_id'], observations=7, retained_observations=6,
                           family_sample_identical=True, deletion_set_identical_in_both_states=True,
                           actual_return_markers=True, all_calculated_nodes_drawn=True))
    fig.legend([Line2D([], [], color=base.BLUE, marker='o', mfc='white', ms=3, lw=1),
                Line2D([], [], color=base.RETURN, marker='x', ms=4, lw=1),
                Line2D([], [], color='black', ls=':', lw=.75)], ['固定真γ', '最小值定位', '真β、η'],
               ncol=3, loc='upper center', bbox_to_anchor=(.54, .995), frameon=False, fontsize=7)
    fig.subplots_adjust(left=.12, right=.985, top=.925, bottom=.075, hspace=.60, wspace=.36)
    base.save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    qa = base.read(QA) if QA.exists() else {}
    qa.update(figures=dict(family=family, representative=dict(panels=panels, axis_settings=settings, dimensions=[3240, 3240])),
              figure_hashes={p.name: base.sha(p) for p in (FIGURE, TRANSFER)})
    base.write(QA, qa)
    print('EXPORTED: MMLE实际形状判据与同组定位、形状、尺度，两张PNG。', flush=True)
    return qa['figures']


def common_principles(report2):
    a = report2.index('MMLE先用样本最小值估计位置，删除这个观测')
    b = report2.index('由式（26），', a)
    common = report2[a:b]
    mapping = {23: 35, 25: 39, 26: 40, 27: 41}
    common = re.sub(r'式（(\d+)）', lambda m: '式（' + str(mapping.get(int(m[1]), int(m[1]))) + '）', common)
    return re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(mapping[int(m[1])]) + '}', common)


DISCUSSION = r'''式（39）直接把样本最小值用于定位。图2显示，高β、小n下最小观测往往远离真起点，因此MMLE的γ高估在这一步已确定。

图14按式（40）绘制实际定位后的形状得分，曲线与零线的交点对应β̂。横坐标为β，因为MMLE在这一阶段求形状方程的根，并不搜索γ。

![图14　MMLE最小值定位后的形状得分](交付/结果/报告1/图8_MMLE六格机制.png)

**图14｜高β下，形状得分在真β处多数为负，方程根落在真值左侧。**

式（40）中的加权均值更偏向较大的保留距离。β增大时，这个加权均值增大，而1/β减小，故形状得分单调下降；在真β处为负，就对应β低估。最小值定位缩短了保留距离，较小距离缩短的比例更大，对数距离的差异随之增大，推动形状方程的根降低。

在式（38）的高β近似范围内，将两个排序观测相减得到：

$$X_{(i)}-X_{(1)}\approx\frac{\eta}{\beta}\left[Z_{(i)}-Z_{(1)}\right],\qquad i=2,\ldots,n.
\tag{42}$$

其中，X₍ᵢ₎、Z₍ᵢ₎为式（38）中随机变量的排序取值，β、η为生成分布的参数。共同因子η/β在式（40）的两个对数均值之差中抵消。该近似下，形状根主要由保留样本的相对距离决定，不随真β同比增大；尺度则随距离整体缩短而下降。

图15展开图14a、b中加深的第{sid}组配对样本。固定同一组保留观测，将式（40）、（41）的位置分别取真γ与样本最小值，比较对数距离、形状得分及条件尺度。尺度曲线以候选β代入式（41），形状根处的点给出η̂；真γ结果仅作位置影响的参照。

![图15　MMLE定位后的形状与尺度变化](交付/结果/报告1/图15_MMLE定位与形状尺度.png)

**图15｜最小值定位扩大保留对数距离的差异，使形状根及对应尺度降低。** 空心点为计算节点，橙叉为实际MMLE返回值。

高β样本中，γ由500移至约1162时，同一保留样本的条件β由约8.44降至3.48，η由约1199降至524。式（41）是保留距离的幂均值：距离缩短与β降低共同使尺度下降，因此位置高估传递为形状和尺度的低估。低β对照中的β虽也随定位下降，仍可高于真值；这一传递并不意味着每个样本都低估形状。

随n增大，最小观测更接近真起点，γ偏移减轻；β、η还受保留样本的距离分散程度影响，变化不必同步或单调。

'''


def revise():
    data = base.read(DATA)
    text = base.REPORT.read_text(encoding='utf-8')
    text = text.replace('以下固定γ考察判据变化，WMLE和MLE', '以下按各方法的实际步骤考察判据变化，WMLE和MLE')
    a, b = text.index('### 2.6　'), text.index('## 3')
    section = '### 2.6　[MMLE](../../src/content/algorithms/mmle.md)\n\n'
    section += common_principles(REPORT2.read_text(encoding='utf-8')) + DISCUSSION.replace('{sid}', str(data['selection']['selected_id']))
    after = text[b:]
    prior_equations = len(re.findall(r'\\tag\{\d+\}', text[a:b]))
    delta = 4 - prior_equations
    if delta:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) + delta) + '}', after)
        after = re.sub(r'式（(\d+)）', lambda m: '式（' + str(int(m[1]) + delta) + '）' if int(m[1]) >= 39 + prior_equations else m[0], after)
    old = '其余逐法组图比较β=2、5及n=7、15，下排展开上方同一组样本。'
    new = f"图14比较最小值定位后的形状得分，β=2、5及n=7、15、30各50组。图15展开第{data['selection']['selected_id']}组配对样本，保留观测与上方曲线族一致。"
    after = after.replace(old, new)
    link = '[MMLE定位与形状尺度数据](交付/程序/报告1/20261011-MMLE定位与形状尺度.json)'
    if link not in after:
        after = after.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    base.write_atomic(base.REPORT, (text[:a] + section + after).encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    marker = '报告1的MMLE当前按实际顺序展示'
    note = (marker + '最小值定位、形状方程定根和尺度恢复。图14为β=2/5、n=7/15/30的形状得分曲线族；'
            f"图15展开同一第{data['selection']['selected_id']}组配对样本，比较固定真γ与实际最小值定位，始终删除同一个最小观测。"
            '[独立脚本](交付/程序/报告1/20261011-MMLE定位与形状尺度.py)提供`build`、`render`、`revise`、`verify`、`all`，'
            '数据与核验留在程序目录，仅输出两张PNG。原理与报告2一致，原样本及250条估计保留；仅对已存β=2、n=30样本新增50条估计。'
            '式（42）由中部近似解释最小值平移后的形状尺度关系；它不是估计器使用的近似。'
            '当前制图入口调用本脚本；早期MMLE纳入脚本及其数据保留作为原结果来源。\n\n')
    if marker in readme:
        start = readme.index(marker)
        end = readme.find('\n\n', start)
        readme = readme[:start] + note + readme[end + 2 if end >= 0 else len(readme):]
    else:
        readme = readme.rstrip() + '\n\n' + note
    base.write_atomic(base.README, (readme.rstrip() + '\n').encode('utf-8'))
    print('REVISED: MMLE实际原理、曲线族、配对传递及图式编号。', flush=True)


def verify():
    data, qa = base.read(DATA), base.read(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    checked, largest_score, largest_scale, largest_root_gap = 0, 0., 0., 0.
    for r in data['curves']:
        x = np.asarray(r['observations'])
        assert r['retained'] == sorted(r['observations'])[1:]
        for b, u, eta in r['points']:
            y = np.log(x[1:] - r['sample_min'])
            w = np.exp(b * (y - y.max())); w /= w.sum()
            score = float(1 / b + y.mean() - w @ y)
            scale = float(np.exp((logsumexp(b * y) - np.log(len(y))) / b))
            largest_score = max(largest_score, abs(score - u))
            largest_scale = max(largest_scale, abs(scale - eta))
            assert abs(score - u) < 1e-10 and np.isclose(scale, eta, atol=1e-9, rtol=1e-10)
            assert criterion(x, b, r['sample_min'])[2] < 0
            checked += 1
        if r['fit']['converged']:
            fit = r['fit']
            assert fit['gamma_hat'] == r['sample_min']
            gap = abs(fit['beta_hat'] - r['diagnostic_root']['beta'])
            largest_root_gap = max(largest_root_gap, gap)
            assert np.isclose(fit['beta_hat'], r['diagnostic_root']['beta'], atol=1e-5, rtol=1e-7)
            assert np.isclose(fit['eta_hat'], criterion(x, fit['beta_hat'], r['sample_min'])[1], atol=1e-8, rtol=1e-10)
    for n in (7, 15, 30):
        for sid in range(1, 51):
            lo, hi = [next(r for r in data['curves'] if (r['beta'], r['n'], r['sample_id']) == (b, n, sid)) for b in (2, 5)]
            assert np.allclose(((np.asarray(lo['observations']) - 500) / 1000) ** 2,
                               ((np.asarray(hi['observations']) - 500) / 1000) ** 5)
    for r in data['examples']:
        assert r['observations'] == next(v['observations'] for v in data['curves'] if (v['beta'], v['n'], v['sample_id']) == (r['beta'], 7, r['sample_id']))
        assert r['reference']['beta'] > r['fit']['beta_hat'] and r['reference']['eta'] > r['fit']['eta_hat']
        assert len(r['trace']) > 1
        for state in r['comparison']:
            for b, u, eta in state['points']:
                check = criterion(r['observations'], b, state['gamma'])
                assert np.allclose([u, eta], check[:2], atol=1e-9, rtol=1e-10)
    scaling_checks, scaling_error = 0, 0.
    for r in data['examples']:
        x, gamma = np.asarray(r['observations']), r['sample_min']
        for factor in (.5, 2.):
            scaled = gamma + factor * (x - gamma)
            for beta in (1., 2., 5., 10.):
                u, eta, _ = criterion(x, beta, gamma)
                u2, eta2, _ = criterion(scaled, beta, gamma)
                scaling_error = max(scaling_error, abs(u2 - u))
                assert np.isclose(u2, u, atol=1e-12)
                assert np.isclose(eta2, factor * eta, atol=1e-9, rtol=1e-10)
                scaling_checks += 1
    assert data['summary'] == summarize(data['curves'])
    assert all(p['curves'] == 50 for p in qa['figures']['family']['panels'])
    ss = qa['figures']['family']['axis_settings']
    assert all(s == ss[0] for s in ss)
    ss = qa['figures']['representative']['axis_settings']
    assert all(ss[i] == ss[i + 3] for i in range(3))
    for p in (FIGURE, TRANSFER):
        assert qa['figure_hashes'][p.name] == base.sha(p)
    report = base.REPORT.read_text(encoding='utf-8')
    assert common_principles(REPORT2.read_text(encoding='utf-8')) in report
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)] == list(range(1, 46))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', report)] == list(range(1, 16))
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent / target.split('#')[0]).exists(), target
    qa['verification'] = dict(formula_nodes_checked=checked, maximum_score_difference=largest_score,
                              maximum_scale_difference=largest_scale, maximum_official_shape_vs_independent_root_difference=largest_root_gap,
                              curves=300, paired_samples_verified=True, original_return_markers=True,
                              common_distance_factor_checks=scaling_checks, maximum_scaling_score_difference=scaling_error,
                              gamma_is_original_minimum=True, single_deletion_set=True, no_gamma_search=True,
                              common_principles_identical_to_report2_except_numbers=True, main_figures=15, equations=45,
                              new_samples=0, added_beta2_n30_estimates=50, replaced_archived_estimates=0,
                              other_report1_results_unchanged=True, fixed_linear_axes=True,
                              script_sha256=base.sha(__file__))
    base.write(QA, qa)
    print(qa['verification'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
