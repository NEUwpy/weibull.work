"""Report 1 MMLE likelihood families and minimum -> shape -> scale.

Reuse the saved 300 samples and their original estimates, including paired
example 3. Evaluate Report 2's exact retained-observation log likelihood.
Only the two current MMLE PNGs and Report 1's MMLE section are replaced.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re
import sys

import numpy as np
from scipy.stats import weibull_min

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


prior = module('r1_mmle_saved_process', HERE / '20261011-MMLE定位与形状尺度.py')
likelihood = module('r2_mmle_likelihood', HERE.parent / '报告2/20261011-MMLE对数似然峰图.py')
base = prior.base
DATA = HERE / (Path(__file__).stem + '.json')
QA = HERE / (Path(__file__).stem + '核验.json')
FIGURE, TRANSFER = prior.FIGURE, prior.TRANSFER
REPORT, README, REPORT2 = base.REPORT, base.README, prior.REPORT2
CONDITIONS, BLIM, BTICKS = prior.CONDITIONS, prior.BLIM, prior.BTICKS
LLIM, LTICKS = [-20., .8], [-20, -15, -10, -5, 0]
GLIM, GTICKS = [450., 1500.], [500, 750, 1000, 1250, 1500]
ELIM, ETICKS = [0., 1800.], [0, 500, 1000, 1500]


def sources():
    paths = [prior.DATA, Path(prior.__file__), Path(likelihood.__file__),
             Path(likelihood.base.__file__), prior.MMLE_CODE, prior.FROZEN_CODE]
    return {p.relative_to(prior.PROJECT).as_posix(): base.sha(p) for p in paths}


def protected_results():
    return {p.relative_to(base.ROOT).as_posix(): base.sha(p)
            for p in base.RESULT.rglob('*') if p.is_file() and p not in (FIGURE, TRANSFER)}


def make_curve(original, points):
    fit = copy.deepcopy(original['fit'])
    assert fit['converged'] and fit['gamma_hat'] == original['sample_min']
    peak = likelihood.profile(original['observations'], fit['beta_hat'])
    computed = [[float(b), likelihood.profile(original['observations'], float(b)),
                 likelihood.profile(original['observations'], float(b)) - peak, float(eta)]
                for b, _, eta in points]
    return dict(beta=original['beta'], n=original['n'], sample_id=original['sample_id'],
                observations=original['observations'], fit=fit, peak_log_likelihood=peak,
                points=computed, hidden_return=not BLIM[0] <= fit['beta_hat'] <= BLIM[1])


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == sources()
        print('REUSED: MMLE似然与参数流程数据。', flush=True)
        return
    old = base.read(prior.DATA)
    hashes, protected = sources(), protected_results()
    assert old['source_hashes'] == prior.sources()
    sid = old['selection']['selected_id']
    examples = {r['beta']: r for r in old['examples']}
    rows = []
    for original in old['curves']:
        points = original['points']
        if original['n'] == 7 and original['sample_id'] == sid:
            state = examples[original['beta']]['comparison'][1]
            assert state['gamma'] == original['sample_min']
            points = state['points']
        rows.append(make_curve(original, points))
    assert len(rows) == 300
    chosen = [copy.deepcopy(next(r for r in rows if (r['beta'], r['n'], r['sample_id']) == (b, 7, sid)))
              for b in (2, 5)]
    base.write(DATA, dict(source_hashes=hashes, protected_results=protected,
                         report2_sha256=base.sha(REPORT2), selection=old['selection'],
                         curves=rows, examples=chosen, source_summary=old['summary'],
                         samples_generated=0, new_estimates=0, replaced_estimates=0,
                         contract=dict(backend='Python/matplotlib', export='PNG only',
                                       archetype='quantitative grid', axes='fixed linear',
                                       family='beta=2/5, n=7/15/30; likelihood maximum determines beta',
                                       flow='50 minimum locations, same example likelihood peak, scale recovery',
                                       displayed_likelihood='ell(beta; gamma_hat) - ell(beta_hat; gamma_hat)',
                                       normalization='Additive per-curve shift; maxima and source fits unchanged.',
                                       gamma_search=False)))
    print('BUILT: 300条真实似然曲线；复用全部样本和估计，无新增估计。', flush=True)


def configure(ax, xlabel, ylabel, xlim, xticks, ylim, yticks, letter, title):
    state = prior.axes(ax, xlabel, ylabel, xlim, xticks, ylim, yticks, letter, title)
    ax.tick_params(axis='both', labelbottom=True, labelleft=True)
    return state


def mark(ax, x, y, label, offset=(5, 6)):
    ax.scatter(x, y, color=base.RETURN, marker='x', s=29, linewidths=1.1, zorder=5)
    ax.annotate(label, (x, y), xytext=offset, textcoords='offset points',
                fontsize=6.6, color=base.RETURN, annotation_clip=True)


def render():
    from matplotlib.lines import Line2D
    data = base.read(DATA)
    assert data['source_hashes'] == sources()
    plt = base.style()
    sid = data['selection']['selected_id']
    fig, aa = plt.subplots(3, 2, figsize=(7.2, 7.2))
    settings, panels = [], []
    for i, (b, n) in enumerate(CONDITIONS):
        ax = aa.flat[i]
        settings.append(configure(ax, 'β', '对数似然（相对峰值）', BLIM, BTICKS,
                                  LLIM, LTICKS, chr(97 + i), f'β={b}，n={n}'))
        ax.axvline(b, color='black', ls=':', lw=.75, zorder=0)
        rows = [r for r in data['curves'] if (r['beta'], r['n']) == (b, n)]
        for r in rows:
            p = np.asarray(r['points'])
            ax.plot(p[:, 0], p[:, 2], color=base.BLUE, alpha=.18, lw=.65)
            if not r['hidden_return']:
                ax.scatter(r['fit']['beta_hat'], 0., color=base.RETURN,
                           marker='x', s=10, linewidths=.6, alpha=.6, zorder=3)
        if n == 7:
            r = next(r for r in rows if r['sample_id'] == sid)
            p = np.asarray(r['points'])
            ax.plot(p[:, 0], p[:, 2], color=base.BLUE, lw=1.35, zorder=4)
            mark(ax, r['fit']['beta_hat'], 0., f'#{sid}', offset=(5, -13))
        panels.append(dict(beta=b, n=n, curves=50, sample_ids=[r['sample_id'] for r in rows],
                           hidden_return_ids=[r['sample_id'] for r in rows if r['hidden_return']],
                           highlighted_id=sid if n == 7 else None))
    fig.legend([Line2D([], [], color=base.BLUE, lw=1),
                Line2D([], [], color=base.RETURN, marker='x', ls='None', ms=4),
                Line2D([], [], color='black', ls=':', lw=.75)],
               ['对数似然', 'MMLE返回值', '真β'], ncol=3, loc='upper center',
               bbox_to_anchor=(.54, .995), frameon=False, fontsize=7)
    fig.subplots_adjust(left=.13, right=.985, top=.925, bottom=.075, hspace=.60, wspace=.38)
    assert len(fig.axes) == 6
    base.save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    family = dict(panels=panels, axis_settings=settings, dimensions=[3240, 3240],
                  criterion='exact retained-observation profile log likelihood')

    fig, aa = plt.subplots(3, 2, figsize=(7.2, 7.2))
    states = [None] * 6
    panels = []
    for col, r in enumerate(data['examples']):
        b, fit, p = r['beta'], r['fit'], np.asarray(r['points'])
        rows = sorted((v for v in data['curves'] if (v['beta'], v['n']) == (b, 7)),
                      key=lambda v: (v['fit']['gamma_hat'], v['sample_id']))
        ranks = np.arange(1, len(rows) + 1)
        selected_rank = next(i for i, v in enumerate(rows, 1) if v['sample_id'] == sid)
        ax = aa[0, col]
        states[col] = configure(ax, '排序序号', r'$\hat\gamma$', [0, 51], [1, 10, 20, 30, 40, 50],
                                GLIM, GTICKS, chr(97 + col), f'β={b:g}，n=7')
        ax.axhline(500., color='black', ls=':', lw=.75, zorder=0)
        ax.scatter(ranks, [v['fit']['gamma_hat'] for v in rows],
                   color=base.BLUE, s=10, alpha=.70)
        mark(ax, selected_rank, fit['gamma_hat'], f'#{sid}，' + rf'$\hat{{\gamma}}={fit["gamma_hat"]:.0f}$', offset=(7, 7))
        ax = aa[1, col]
        states[2 + col] = configure(ax, 'β', '对数似然（相对峰值）', BLIM, BTICKS,
                                    LLIM, LTICKS, chr(99 + col), f'第{sid}组')
        ax.axvline(b, color='black', ls=':', lw=.75, zorder=0)
        ax.axvline(fit['beta_hat'], color=base.RETURN, ls='--', lw=.65, alpha=.7, zorder=0)
        ax.plot(p[:, 0], p[:, 2], color=base.BLUE, lw=1.05)
        ax.scatter(p[:, 0], p[:, 2], s=7, facecolor='white', edgecolor=base.BLUE, lw=.4, zorder=3)
        mark(ax, fit['beta_hat'], 0., rf'$\hat{{\beta}}={fit["beta_hat"]:.2f}$', offset=(7, -14))
        ax = aa[2, col]
        states[4 + col] = configure(ax, 'β', r'$\hat\eta(\beta;\hat\gamma)$', BLIM, BTICKS,
                                    ELIM, ETICKS, chr(101 + col), f'第{sid}组')
        ax.axhline(1000., color='black', ls=':', lw=.75, zorder=0)
        ax.axvline(fit['beta_hat'], color=base.RETURN, ls='--', lw=.65, alpha=.7, zorder=0)
        ax.plot(p[:, 0], p[:, 3], color=base.BLUE, lw=1.05)
        ax.scatter(p[:, 0], p[:, 3], s=7, facecolor='white', edgecolor=base.BLUE, lw=.4, zorder=3)
        mark(ax, fit['beta_hat'], fit['eta_hat'], rf'$\hat{{\eta}}={fit["eta_hat"]:.0f}$', offset=(7, 7))
        panels.append(dict(beta=b, n=7, sample_id=sid, location_groups=50,
                           location_sample_ids=[v['sample_id'] for v in rows],
                           location_gamma_values=[v['fit']['gamma_hat'] for v in rows],
                           selected_location_rank=selected_rank,
                           family_points_identical=True, node_count=len(p), all_nodes_drawn=True,
                           gamma_hat=fit['gamma_hat'], beta_hat=fit['beta_hat'], eta_hat=fit['eta_hat']))
    fig.legend([Line2D([], [], color=base.BLUE, marker='o', mfc='white', ms=3, lw=1),
                Line2D([], [], color=base.RETURN, marker='x', ls='None', ms=4),
                Line2D([], [], color='black', ls=':', lw=.75)],
               ['计算值', f'第{sid}组返回值', '真值'], ncol=3, loc='upper center',
               bbox_to_anchor=(.54, .995), frameon=False, fontsize=7)
    fig.subplots_adjust(left=.13, right=.985, top=.925, bottom=.075, hspace=.60, wspace=.38)
    assert len(fig.axes) == 6
    base.save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    representative = dict(panels=panels, axis_settings=states, dimensions=[3240, 3240],
                          location_order='ascending gamma_hat',
                          row_order=['minimum locations across samples', 'same example likelihood maximum',
                                     'scale recovered at that maximum'])
    record = base.read(QA) if QA.exists() else {}
    record.update(figures=dict(family=family, representative=representative),
                  figure_hashes={p.name: base.sha(p) for p in (FIGURE, TRANSFER)})
    base.write(QA, record)
    print('EXPORTED: MMLE似然曲线族及γ—β—η估计流程，两张PNG。', flush=True)
    return record['figures']


def common_principles(report2):
    start = report2.index('MMLE用样本最小值估计位置，删除该观测后')
    end = report2.index('图19、20左列', start)
    common = report2[start:end]
    mapping = {21: 33, 25: 38, 26: 39, 27: 40}
    common = re.sub(r'式（(\d+)）', lambda m: f'式（{mapping.get(int(m[1]), int(m[1]))}）', common)
    return re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(mapping[int(m[1])]) + '}', common)


DISCUSSION = r'''式（38）直接以样本最小值定位。高β、小n下，最小观测往往远离真起点（图2），γ在这一步被高估。

图14按式（39）展示β的似然峰；纵轴为$\ell(\beta;\hat\gamma)-\ell(\hat\beta;\hat\gamma)$，峰顶对应β̂。

![图14　MMLE最小值定位后的似然峰](交付/结果/报告1/图8_MMLE六格机制.png)

**图14｜高β下，多数似然峰位于真β左侧，对应形状低估。**

最小值定位缩短了保留距离，其中较小距离缩短的比例更大，保留距离的相对分散程度增大，对应的形状估计降低。在式（37）的高β近似范围内，将两个排序观测相减得到：

$$X_{(i)}-X_{(1)}\approx\frac{\eta}{\beta}\left[Z_{(i)}-Z_{(1)}\right],\qquad i=2,\ldots,n.
\tag{41}$$

其中，X₍ᵢ₎、Z₍ᵢ₎为式（37）中随机变量的排序取值，β、η为生成分布的参数。共同因子η/β只改变式（39）的常数项，不改变似然峰的位置。因此，高β下的形状估计主要受保留距离的相对分散程度影响，未必随真β同比增大。

图15上排将50组γ估计从小到大排列，中排、下排展开同一第{sid}组的形状选择与尺度恢复。其似然曲线与图14a、b中的加深曲线一致。尺度曲线由候选β代入式（40）得到，似然峰对应的β给出最终η。

![图15　MMLE最小值定位、似然峰与尺度恢复](交付/结果/报告1/图15_MMLE定位与形状尺度.png)

**图15｜MMLE先以最小值确定γ，再取似然峰对应的β，最后计算η。**

高β代表样本的γ偏高，固定这一位置后，似然峰位于真β左侧，计算出的η也低于真值（图15b、d、f）。η由缩短后的保留距离与所选β共同决定。低β对照的似然峰仍可位于真值右侧，体现了具体样本分散程度的影响。

随n增大，最小观测更接近真起点，γ高估和η低估减轻；β仍受保留距离的随机分散程度影响。

'''


def revise():
    data = base.read(DATA)
    text = REPORT.read_text(encoding='utf-8')
    a, b = text.index('### 2.6　'), text.index('## 3　', text.index('### 2.6　'))
    section = ('### 2.6　[MMLE](../../src/content/algorithms/mmle.md)\n\n'
               + common_principles(REPORT2.read_text(encoding='utf-8'))
               + DISCUSSION.replace('{sid}', str(data['selection']['selected_id'])))
    assert len(re.findall(r'\\tag\{\d+\}', text[a:b])) == 4
    after = text[b:]
    after = after.replace('图14比较最小值定位后的形状得分，β=2、5及n=7、15、30各50组。',
                          '图14比较最小值定位后的似然峰，β=2、5及n=7、15、30各50组。')
    link = '[MMLE似然与参数流程数据](交付/程序/报告1/20261011-MMLE似然与参数流程.json)'
    if link not in after:
        after = after.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    updated = text[:a] + section + after
    if updated != text:
        base.write_atomic(REPORT, updated.encode('utf-8'))
    readme = README.read_text(encoding='utf-8')
    marker = '报告1的MMLE当前按实际顺序展示'
    note = (marker + '最小值定位、对数似然峰和尺度恢复。图14为β=2/5、n=7/15/30的实际似然曲线族，'
            '曲线仅减去各自峰值以统一线性刻度；图15上排按γ从小到大展示50组估计，中、下排展开同一第3组的β、η。'
            '[独立脚本](交付/程序/报告1/20261011-MMLE似然与参数流程.py)提供`build`、`render`、`revise`、`verify`、`all`，'
            '数据和核验留在程序目录，仅更新两张PNG。似然函数复用报告2当前程序，所有300组样本及估计均复用，'
            '不新增估计、不替换原结果。原过程数据保留在[定位与形状尺度数据](交付/程序/报告1/20261011-MMLE定位与形状尺度.json)，'
            '统一制图入口已接入当前脚本。\n\n')
    start = readme.index(marker)
    end = readme.find('\n\n', start)
    revised = readme[:start] + note + readme[end + 2 if end >= 0 else len(readme):]
    if revised != readme:
        base.write_atomic(README, revised.encode('utf-8'))
    print('REVISED: MMLE似然公式、两张图及参数估计过程。', flush=True)


def verify():
    from PIL import Image
    data, qa, old = base.read(DATA), base.read(QA), base.read(prior.DATA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    assert data['report2_sha256'] == base.sha(REPORT2)
    originals = {(r['beta'], r['n'], r['sample_id']): r for r in old['curves']}
    checked, error, peak_residual = 0, 0., 0.
    for r in data['curves']:
        original = originals[r['beta'], r['n'], r['sample_id']]
        assert r['observations'] == original['observations'] and r['fit'] == original['fit']
        x, p = np.array(r['observations']), np.array(r['points'])
        assert r['fit']['gamma_hat'] == x[0]
        direct = weibull_min.logpdf((x[1:] - x[0])[None, :], p[:, 0, None], scale=p[:, 3, None]).sum(axis=1)
        error = max(error, float(np.max(np.abs(direct - p[:, 1]))))
        assert np.allclose(direct, p[:, 1], rtol=1e-12, atol=1e-9)
        assert np.allclose(p[:, 2], p[:, 1] - r['peak_log_likelihood'], atol=1e-12)
        assert p[:, 2].max() < 1e-9
        beta = r['fit']['beta_hat']
        score, eta, slope = prior.criterion(x, beta, x[0])
        peak_residual = max(peak_residual, abs(score))
        assert abs(score) < 1e-7 and slope < 0
        assert np.isclose(eta, r['fit']['eta_hat'], rtol=1e-10, atol=1e-8)
        checked += len(p)
    for r in data['examples']:
        assert r == next(v for v in data['curves'] if (v['beta'], v['n'], v['sample_id']) == (r['beta'], 7, r['sample_id']))
        assert np.isclose(likelihood.profile(r['observations'], r['fit']['beta_hat']), r['peak_log_likelihood'])
    states = qa['figures']['family']['axis_settings']
    assert all(s == states[0] for s in states)
    states = qa['figures']['representative']['axis_settings']
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    location_panels = qa['figures']['representative']['panels']
    for panel in location_panels:
        expected = sorted((r for r in data['curves'] if (r['beta'], r['n']) == (panel['beta'], 7)),
                          key=lambda r: (r['fit']['gamma_hat'], r['sample_id']))
        assert panel['location_sample_ids'] == [r['sample_id'] for r in expected]
        assert panel['location_gamma_values'] == [r['fit']['gamma_hat'] for r in expected]
        assert np.all(np.diff(panel['location_gamma_values']) >= 0)
        rank = panel['selected_location_rank'] - 1
        assert panel['location_sample_ids'][rank] == panel['sample_id']
        assert panel['location_gamma_values'][rank] == panel['gamma_hat']
    assert location_panels[0]['location_sample_ids'] == location_panels[1]['location_sample_ids']
    for p in (FIGURE, TRANSFER):
        assert qa['figure_hashes'][p.name] == base.sha(p)
        with Image.open(p) as im:
            assert im.size == (3240, 3240)
    text = REPORT.read_text(encoding='utf-8')
    assert common_principles(REPORT2.read_text(encoding='utf-8')) in text
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', text)] == list(range(1, 45))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', text)] == list(range(1, 16))
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in target and not target.startswith('#'):
            assert (REPORT.parent / target.split('#')[0]).exists(), target
    record = dict(status='passed', curves=300, likelihood_nodes_checked=checked,
                  maximum_direct_density_difference=error, maximum_peak_score_residual=peak_residual,
                  identical_likelihood_function_to_report2=True, original_samples_and_estimates_unchanged=True,
                  representative_points_identical_to_family=True, fixed_linear_axes=True,
                  gamma_sorted_ascending=True, paired_columns_same_sample_order=True,
                  highlighted_original_sample_preserved=True,
                  other_results_and_report2_unchanged=True, new_samples=0, new_estimates=0,
                  script_sha256=base.sha(__file__), report_sha256=base.sha(REPORT))
    qa.update(verification=record, cache_sha256=base.sha(DATA))
    base.write(QA, qa)
    print(record, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
