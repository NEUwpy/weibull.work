"""LRE criterion families and the same paired sample's parameter transfer.

Keep the 200 archived n=7/15 profiles and estimates. Add n=30 from saved
observations: reuse 50 beta=5 estimates, fit only the mapped beta=2 observations
with the frozen Bernard implementation. Save data/checks here; export PNG only.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
HELPER = HERE / '20261011-LSE曲线簇与参数传导.py'
spec = importlib.util.spec_from_file_location('r1_lre_plot_helpers', HELPER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
spec = importlib.util.spec_from_file_location('r1_lre_frozen', base.FROZEN / 'methods/lre.py')
lre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lre)
DATA = HERE / '20261011-LRE曲线族与参数传递.json'
QA = HERE / '20261011-LRE曲线族与参数传递核验.json'
FIGURE = base.RESULT / '报告1/图5_LRE六格机制.png'
TRANSFER = base.RESULT / '报告1/图9_LRE参数传递.png'
REPORT2 = base.ROOT / '报告2：小样本情况下的明显异常估计.md'
DEFINITIONS = [(1, r'$\rho(\gamma)$', [.85, 1], [.85, .9, .95, 1]),
               (2, r'$\hat\beta(\gamma)$', [0, 10], [0, 2, 4, 6, 8, 10]),
               (3, r'$\hat\eta(\gamma)$', [0, 1600], [0, 500, 1000, 1500])]


def sources():
    paths = [base.INPUT / '样本.json', base.INPUT / '实际估计.json',
             base.INPUT / '逐法过程曲线.json', base.N30, base.MATRIX,
             base.FROZEN / 'methods/lre.py', base.FROZEN / 'base.py',
             HELPER, HERE.parent / '共用.py']
    return {str(p.relative_to(base.ROOT)): base.sha(p) for p in paths}


def protected_results():
    folder = base.RESULT / '报告1'
    return {p.relative_to(folder).as_posix(): base.sha(p) for p in folder.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, base.FIGURE_QA)}


def regression(x, gamma):
    """Independent OLS, Pearson correlation and their gamma derivatives."""
    x = np.asarray(x, float)
    p = (np.arange(1, len(x) + 1) - .3) / (len(x) + .4)
    z = np.log(-np.log1p(-p))
    y = np.log(x - gamma)
    zc, yc = z - z.mean(), y - y.mean()
    syy, szz, syz = float(yc @ yc), float(zc @ zc), float(yc @ zc)
    b = syz / syy
    a = float(z.mean() - b * y.mean())
    rho = syz / np.sqrt(syy * szz)
    dy = -1 / (x - gamma)
    dsyz, dsyy = float(zc @ dy), float(2 * yc @ dy)
    db = (dsyz * syy - syz * dsyy) / syy ** 2
    drho = (dsyz - syz * dsyy / (2 * syy)) / np.sqrt(syy * szz)
    deta_log = float(dy.mean() + z.mean() * db / b ** 2)
    return dict(beta=b, eta=float(np.exp(-a / b)), slope=b, intercept=a,
                rho=float(rho), loss=float(1 - rho ** 2),
                rho_derivative=float(drho), beta_derivative=float(db),
                log_eta_derivative=deta_log)


def added_curve(sample, archived):
    x = np.asarray(sample['observations'], float)
    if archived is None:
        estimator = lre.LRE(x)
        result = estimator.run()
        assert result[4] is True
        fit = dict(beta_hat=result[0], eta_hat=result[1], gamma_hat=result[2],
                   converged=True, extra={'solution_info': estimator.last_solution_info})
    else:
        fit = copy.deepcopy(archived)
        fit['extra'] = fit['original_record']['extra']
    selected = float(fit['gamma_hat'])
    top = float(x[0] - max(1e-5, x[0] * 1e-7))
    grid = np.unique(np.r_[np.linspace(0, top, 141), 500., selected,
                            selected - 2, selected + 2, selected - 10, selected + 10])
    grid = grid[(grid >= 0) & (grid <= top)]
    points = []
    for g in grid:
        r = regression(x, float(g))
        points.append([float(g), r['loss'], r['beta'], r['eta'], False, None])
    return dict(method='lre', source='paired_n30', beta=sample['beta'], n=30,
                sample_id=sample['sample_id'], observations=sample['observations'],
                sample_min=float(x[0]), fit=fit, points=points,
                truth=next(p for p in points if p[0] == 500),
                returned=next(p for p in points if p[0] == selected),
                estimate_origin='archived_beta5' if archived is not None else 'frozen_LRE_beta2')


def selection(rows):
    pool = sorted((r for r in rows if r['beta'] == 5 and r['n'] == 7
                   and r['fit']['gamma_hat'] > 500),
                  key=lambda r: (r['fit']['gamma_hat'], r['sample_id']))
    midpoint = float(np.median([r['fit']['gamma_hat'] - 500 for r in pool]))
    chosen = min(pool, key=lambda r: (round(abs(r['fit']['gamma_hat'] - 500 - midpoint), 10),
                                      r['fit']['gamma_hat'], r['sample_id']))
    return dict(rule='Among beta=5, n=7 gamma-overestimates, choose gamma error closest to the median; ties by smaller gamma then sample ID. Reuse the same latent sample for beta=2.',
                pool_size=len(pool), eligible_ids=[r['sample_id'] for r in pool],
                median_gamma_error=midpoint, selected_id=chosen['sample_id'],
                scope='Illustrates rightward parameter transfer; does not represent every sample or establish a universal bias direction.')


def summarize(rows):
    summaries = []
    for beta, n in base.CONDITIONS:
        rr = [r for r in rows if r['beta'] == beta and r['n'] == n]
        assert len(rr) == 50
        gamma = np.array([r['fit']['gamma_hat'] for r in rr])
        summaries.append(dict(beta=beta, n=n, curves=50,
                              gamma_median=float(np.median(gamma)),
                              median_absolute_gamma_error=float(np.median(abs(gamma - 500))),
                              gamma_above_truth=int(np.sum(gamma > 500)),
                              gamma_at_zero=int(np.sum(gamma == 0)),
                              median_absolute_rho_derivative=float(np.median([
                                  abs(regression(r['observations'], 500)['rho_derivative']) for r in rr])),
                              truth_rho_quartiles=np.quantile([
                                  np.sqrt(1 - r['truth'][1]) for r in rr], [.25, .5, .75]).tolist()))
    return summaries


def build():
    if DATA.exists():
        assert base.read(DATA)['source_hashes'] == sources()
        print('REUSED: LRE曲线族与参数传递数据。', flush=True)
        return
    hashes, protected = sources(), protected_results()
    samples = base.read(base.INPUT / '样本.json')
    index = {(s['beta'], s['n'], s['sample_id']): s for s in samples}
    rows = [copy.deepcopy(r) for r in base.read(base.INPUT / '逐法过程曲线.json')['curves']
            if r['method'] == 'lre' and r['source'] == 'paired']
    assert len(rows) == 200
    for r in rows:
        r['observations'] = index[r['beta'], r['n'], r['sample_id']]['observations']
    matrix, n30 = base.read(base.MATRIX), base.read(base.N30)
    assert n30['source_sha256'] == base.sha(base.MATRIX)
    archived = {r['id']: r for r in matrix['results'] if r['n'] == 30 and r['method_id'] == 'lre'}
    assert len(archived) == 50
    for sample in n30['samples']:
        if sample['beta'] == 5:
            original = next(s['values'] for s in matrix['samples']
                            if s['n'] == 30 and s['id'] == sample['sample_id'])
            assert sample['observations'] == original
        rows.append(added_curve(sample, archived[sample['sample_id']] if sample['beta'] == 5 else None))
    chosen = selection(rows)
    profiles = [copy.deepcopy(next(r for r in rows if r['beta'] == b and r['n'] == 7
                                   and r['sample_id'] == chosen['selected_id'])) for b in (2, 5)]
    assert hashes == sources() and protected == protected_results()
    base.write(DATA, dict(source_hashes=hashes, protected_results=protected,
                         conditions=base.CONDITIONS, curves=rows, profiles=profiles,
                         selection=chosen, summaries=summarize(rows),
                         columns=['gamma', '1-rho_squared', 'conditional_beta', 'conditional_eta', 'unused', 'unused'],
                         criterion_ordinate='rho=sqrt(1-saved_loss); positive for increasing paired coordinates',
                         plotting_positions='Bernard: (i-0.3)/(n+0.4), frozen archived method',
                         new_random_draws=0, reused_n7_n15_curves=200, added_n30_curves=100,
                         reused_beta5_n30_estimates=50, added_mapped_beta2_n30_estimates=50,
                         replaced_archived_estimates=0,
                         n30_provenance={k: v for k, v in n30.items() if k != 'samples'},
                         figure_contract={'backend': 'Python', 'exports': 'Two current PNGs only',
                                          'criterion': 'beta=2/5 columns, n=7/15/30 rows, 50 curves per cell',
                                          'transfer': 'One paired sample, rows rho, conditional beta, conditional eta',
                                          'axes': 'Fixed linear gamma axes throughout, equal y scales within every quantity'}))
    print(f"BUILT: 300条曲线，第{chosen['selected_id']}组配对代表；无新抽样，存档估计未替换。", flush=True)


def ordinate(point, column):
    return float(np.sqrt(max(0., 1 - point[1]))) if column == 1 else point[column]


def bundle(ax, rows):
    hidden_nodes = hidden_returns = 0
    lo, hi = ax.get_ylim()
    for r in rows:
        pp, chosen = r['points'], r['returned']
        yy = [ordinate(p, 1) for p in pp]
        ax.plot([p[0] for p in pp], yy, color=base.BLUE, alpha=.20, lw=.65)
        ax.scatter(500, ordinate(r['truth'], 1), color=base.BLUE, s=4, alpha=.5, linewidths=0, zorder=3)
        ax.scatter(chosen[0], ordinate(chosen, 1), color=base.RETURN, marker='x',
                   s=10, alpha=.7, linewidths=.7, zorder=4)
        ax.plot(chosen[0], .018, marker='|', color=base.RETURN, ms=5,
                alpha=.55, transform=ax.get_xaxis_transform())
        hidden_nodes += sum(not (lo <= v <= hi and base.XLIM[0] <= p[0] <= base.XLIM[1])
                            for p, v in zip(pp, yy))
        hidden_returns += int(not (lo <= ordinate(chosen, 1) <= hi
                                  and base.XLIM[0] <= chosen[0] <= base.XLIM[1]))
    return dict(curves=len(rows), sample_ids=[r['sample_id'] for r in rows],
                hidden_curve_points=hidden_nodes, hidden_return_values=hidden_returns)


def render():
    data = base.read(DATA)
    assert data['source_hashes'] == sources()
    sid = data['selection']['selected_id']
    plt = base.style()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    column, label, limits, ticks = DEFINITIONS[0]
    for i, (beta, n) in enumerate(base.CONDITIONS):
        ax = axes.flat[i]
        states.append(base.axis(ax, label, beta, n, limits, ticks, chr(97 + i)))
        rows = sorted((r for r in data['curves'] if r['beta'] == beta and r['n'] == n),
                      key=lambda r: r['sample_id'])
        metadata = bundle(ax, rows)
        if n == 7:
            pp = next(r['points'] for r in rows if r['sample_id'] == sid)
            ax.plot([p[0] for p in pp], [ordinate(p, 1) for p in pp], color=base.BLUE, lw=1.15, zorder=3)
        panels.append(dict(beta=beta, n=n, highlighted_sample_id=sid if n == 7 else None, **metadata))
    assert all(s == states[0] for s in states)
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    first = dict(method='lre', file=FIGURE.stem, panels=panels, axis_settings=states,
                 criterion='rho maximization', all_curves_real=True,
                 six_panel_axes_identical=True, single_panels=[], png_dimensions=[3240, 3240])

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for row, (column, label, limits, ticks) in enumerate(DEFINITIONS):
        for col, profile in enumerate(data['profiles']):
            beta, pp = profile['beta'], profile['points']
            ax = axes[row, col]
            states.append(base.axis(ax, label, beta, 7, limits, ticks, chr(97 + row * 2 + col)))
            yy = [ordinate(p, column) for p in pp]
            ax.plot([p[0] for p in pp], yy, color=base.BLUE, lw=1.25)
            ax.scatter([p[0] for p in pp], yy, s=4.5, facecolors='white',
                       edgecolors=base.BLUE, linewidths=.4, zorder=3)
            truth, returned = profile['truth'], profile['returned']
            ax.axvline(returned[0], color=base.RETURN, ls='--', lw=.8)
            if column in (2, 3):
                ax.axhline(beta if column == 2 else 1000, color='.55', ls='--', lw=.7)
            ax.scatter(500, ordinate(truth, column), color=base.BLUE, s=16, linewidths=0, zorder=5)
            ax.scatter(returned[0], ordinate(returned, column), color=base.RETURN, marker='x',
                       s=27, linewidths=1, zorder=5)
            anchors = []
            for p, color, offset in [(truth, base.BLUE, (7, 9)), (returned, base.RETURN, (7, -14))]:
                index = next(i for i, v in enumerate(pp, 1) if v[0] == p[0])
                anchors.append(dict(node_id=f'G{index}', point=p[:4]))
                if column == 1:
                    ax.annotate(f'G{index}', (p[0], ordinate(p, column)), xytext=offset,
                                textcoords='offset points', fontsize=6, color=color)
            panels.append(dict(beta=beta, n=7, sample_id=sid, quantity=column, curves=1,
                               criterion_panel='a' if beta == 2 else 'b',
                               node_count=len(pp), all_actual_nodes_drawn=True,
                               gamma_selected=returned[0], anchors=anchors,
                               points_identical_to_multi_sample=True,
                               hidden_nodes=sum(not (limits[0] <= v <= limits[1]
                                                     and base.XLIM[0] <= p[0] <= base.XLIM[1])
                                                for p, v in zip(pp, yy))))
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    base.save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    second = dict(file=TRANSFER.stem, panels=panels, axis_settings=states,
                  same_profiles_as_criterion=True, selection=data['selection'], png_dimensions=[3240, 3240])
    qa = base.read(QA) if QA.exists() else {}
    qa.update(figures={'criterion': first, 'transfer': second},
              figure_hashes={p.name: base.sha(p) for p in (FIGURE, TRANSFER)})
    base.write(QA, qa)
    shared = base.read(base.FIGURE_QA)
    shared['process_figures'] = [first if r['method'] == 'lre' else r for r in shared['process_figures']]
    shared['lre_parameter_transfer'] = second
    base.write(base.FIGURE_QA, shared)
    print('EXPORTED: LRE判据曲线族与同组代表样本传递，两张PNG。', flush=True)
    return first


def references(text, mapping):
    # Also handle the shorthand second number in 式（a）、（b）.
    def group(match):
        return re.sub(r'（(\d+)）', lambda m: '（' + str(mapping.get(int(m[1]), int(m[1]))) + '）', match[0])
    return re.sub(r'式（\d+）(?:[、和及]（\d+）)*', group, text)


def common_principles(report2):
    a = report2.index('LRE先将样本转换为Weibull概率图坐标')
    b = report2.index('ρ(γ)为给定γ时', a)
    common = report2[a:b]
    mapping = {13: 18, 14: 19, 15: 20, 16: 21}
    return re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(mapping[int(m[1])]) + '}',
                  references(common, mapping))


DISCUSSION = r'''ρ(γ)为给定γ时yᵢ与zᵢ的相关系数。本组沿用Bernard绘图位置pᵢ=(i−0.3)/(n+0.4)。将相关系数展开，图中的位置判据为：

$$
\rho(\gamma)=
\frac{\sum_i(y_i-\overline y)(z_i-\overline z)}
{\sqrt{\sum_i(y_i-\overline y)^2\sum_i(z_i-\overline z)^2}}.
\tag{22}
$$

其中，ȳ、z̄分别为对数距离和概率图参考坐标的均值。zᵢ固定，yᵢ随γ变化；图8按式（22）绘制曲线，橙叉标记相关性最高的位置。

![图8　LRE在不同形状与样本量下的位置判据](交付/结果/报告1/图5_LRE六格机制.png)

**图8｜高β时，真位置附近的相关性曲线更平，最高点可偏离真位置。**

式（16）的前两项只改变对数距离的整体平移与比例，不改变相关系数；二次项才改变点列的弯曲程度。高β时观测相对集中，二次项较小，因此较大范围的γ仍可能给出相近的相关性。样本间距与固定绘图位置的随机差异，便可能使最高点偏离真γ。

配对样本在真γ处的对数距离仅随β整体缩放，相关系数相同。高β的影响体现为曲线对γ变化较不敏感，而非真γ处的相关性更低；最高点既可能右移，也可能落在左侧。随n增大，所选位置整体更接近真值，高β下仍可出现较大的位置偏移。

位置确定后，对zᵢ≈a+byᵢ作最小二乘回归，可得：

$$\begin{aligned}
b(\gamma)&=\frac{\sum_i(y_i-\overline y)(z_i-\overline z)}{\sum_i(y_i-\overline y)^2},\\
a(\gamma)&=\overline z-b(\gamma)\overline y.
\end{aligned}
\tag{23}$$

图9展开图8a、b中加深的第{sid}组配对曲线：式（21）选择γ，式（23）、（20）给出该γ对应的β、η。

![图9　LRE的位置选择与参数传递](交付/结果/报告1/图9_LRE参数传递.png)

**图9｜更高的相关性选中偏高γ，并通过回归线得到较低β、η。** 空心点为计算节点，蓝点为固定真γ的条件估计，橙叉为最终估计。

图9a、b的最高点均在真γ右侧，β=5的右移幅度更大。γ右移使较小观测的对数距离下降更多，拉开yᵢ的间距，而zᵢ保持不变。本例回归斜率随之减小，按式（20）得到较低β（图9c、d）；将同一γ下的斜率、截距代入式（20），也得到较低η（图9e、f）。因此，相关性提高并不意味着参数更接近真值：位置选择改变了回归线，也改变了对应的形状和尺度。

'''


def revise():
    report2 = REPORT2.read_text(encoding='utf-8')
    data = base.read(DATA)
    text = base.REPORT.read_text(encoding='utf-8')
    a, b = text.index('### 2.3　'), text.index('### 2.4　')
    before, after = text[:a], text[b:]
    if '图9_LRE参数传递.png' not in text[a:b]:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) + 2) + '}', after)
        after = references(after, {i: i + 2 for i in range(22, 36)})
        after = re.sub(r'(?<!补充)图(\d+)(?![\d_])',
                       lambda m: '图' + str(int(m[1]) + 1) if 9 <= int(m[1]) <= 11 else m[0], after)
    section = ('### 2.3　[LRE](../../src/content/algorithms/lre.md)\n\n'
               + common_principles(report2) + DISCUSSION.replace('{sid}', str(data['selection']['selected_id'])))
    updated = before + section + after
    updated = updated.replace('图4、6比较β=2、5及n=7、15、30', '图4、6、8比较β=2、5及n=7、15、30')
    appendix = f"图9展开n=7的第{data['selection']['selected_id']}组配对样本，展示LRE参数传递。"
    if appendix not in updated:
        updated = updated.replace('其余逐法组图比较', appendix + '其余逐法组图比较')
    link = '[LRE曲线族与参数传递数据](交付/程序/报告1/20261011-LRE曲线族与参数传递.json)'
    if link not in updated:
        updated = updated.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    if updated != text:
        base.write_atomic(base.REPORT, updated.encode('utf-8'))
    readme = base.README.read_text(encoding='utf-8')
    marker = '报告1的LRE原理与报告2统一'
    note = (marker + '：以绘图概率变换得到参考坐标，最大化相关系数ρ，再由斜率与截距恢复β、η；本组保留Bernard版本。'
            f"图8为β=2/5、n=7/15/30的判据曲线族，图9展开上方加深的第{data['selection']['selected_id']}组配对样本，依次展示ρ、条件β和η。"
            '代表样本取β=5、n=7位置高估组中偏差最接近中位数者，β=2沿用同组；全部曲线、选择及节点留在程序目录。'
            '[独立脚本](交付/程序/报告1/20261011-LRE曲线族与参数传递.py)提供`build`、`render`、`revise`、`verify`和`all`，已接入统一制图入口。'
            'n=7/15的200条曲线和估计保持原值，n=30复用50条β=5估计，仅对已映射的β=2样本增加50条估计；无新抽样，不替换原结果，仅导出两张PNG。\n\n')
    if marker in readme:
        a = readme.index(marker)
        ending = readme.find('\n\n', a)
        b = ending + 2 if ending >= 0 else len(readme)
        readme = readme[:a] + note + readme[b:]
    else:
        readme = readme.rstrip() + '\n\n' + note
    readme = readme.replace('报告1的WMLE图9', '报告1的WMLE图10')
    readme = readme.replace('第2.6节与图11解释', '第2.6节与图12解释')
    readme = readme.replace('图11固定删除', '图12固定删除')
    readme = readme.rstrip() + '\n'
    if readme != base.README.read_text(encoding='utf-8'):
        base.write_atomic(base.README, readme.encode('utf-8'))
    assert REPORT2.read_text(encoding='utf-8') == report2
    print('REVISED: LRE原理、判据机制、同组参数传递及顺序编号。', flush=True)


def verify():
    data, qa = base.read(DATA), base.read(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    assert data['selection'] == selection(data['curves'])
    originals = [r for r in base.read(base.INPUT / '逐法过程曲线.json')['curves']
                 if r['method'] == 'lre' and r['source'] == 'paired']
    for original in originals:
        row = next(r for r in data['curves'] if r['beta'] == original['beta']
                   and r['n'] == original['n'] and r['sample_id'] == original['sample_id'])
        assert {k: row[k] for k in original} == original
    matrix = base.read(base.MATRIX)
    checked, maximum, fit_maximum = 0, 0., 0.
    for r in data['curves']:
        for p in r['points']:
            result = regression(r['observations'], p[0])
            values = [result['loss'], result['beta'], result['eta']]
            assert np.allclose(p[1:4], values, rtol=1e-9, atol=1e-6)
            maximum = max(maximum, float(np.max(np.abs(np.array(p[1:4]) - values))))
            assert result['rho'] > 0
            checked += 1
        result = regression(r['observations'], r['returned'][0])
        target = [r['fit']['beta_hat'], r['fit']['eta_hat']]
        assert np.allclose([result['beta'], result['eta']], target, rtol=1e-9, atol=1e-6)
        fit_maximum = max(fit_maximum, float(np.max(abs(np.array(target) - [result['beta'], result['eta']]))))
        info = r['fit']['extra']['solution_info']
        assert np.isclose(result['rho'] ** 2, info['rho_squared'], rtol=1e-9, atol=1e-9)
        assert info['strategy'] == 'rho_squared_maximization'
        if r['n'] == 30 and r['beta'] == 5:
            original = next(v for v in matrix['results'] if v['method_id'] == 'lre' and v['n'] == 30
                            and v['id'] == r['sample_id'])
            assert all(r['fit'][k] == original[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat', 'converged'))
    pair_error = 0.
    for n in (7, 15, 30):
        for sid in range(1, 51):
            lo, hi = [next(r for r in data['curves'] if r['beta'] == b and r['n'] == n
                          and r['sample_id'] == sid) for b in (2, 5)]
            assert np.allclose(((np.asarray(lo['observations']) - 500) / 1000) ** 2,
                               ((np.asarray(hi['observations']) - 500) / 1000) ** 5)
            pair_error = max(pair_error, abs(ordinate(lo['truth'], 1) - ordinate(hi['truth'], 1)))
    assert pair_error < 1e-10
    lo, hi = data['profiles']
    for r in (lo, hi):
        original = next(v for v in data['curves'] if v['beta'] == r['beta'] and v['n'] == 7
                        and v['sample_id'] == r['sample_id'])
        assert r == original
        assert r['returned'][0] > 500
        assert r['returned'][2] < r['truth'][2] and r['returned'][3] < r['truth'][3]
        assert r['returned'][2] < r['beta'] and r['returned'][3] < 1000
        for p in r['points']:
            if 500 <= p[0] <= r['returned'][0]:
                result = regression(r['observations'], p[0])
                assert result['beta_derivative'] < 0 and result['log_eta_derivative'] < 0
    assert hi['returned'][0] > lo['returned'][0]
    assert all(p['curves'] == 50 and p['sample_ids'] == list(range(1, 51))
               for p in qa['figures']['criterion']['panels'])
    assert all(p['curves'] == 1 and p['sample_id'] == data['selection']['selected_id']
               and p['points_identical_to_multi_sample'] and p['all_actual_nodes_drawn']
               for p in qa['figures']['transfer']['panels'])
    assert [p['quantity'] for p in qa['figures']['transfer']['panels']] == [1, 1, 2, 2, 3, 3]
    assert all(s['x_scale'] == s['y_scale'] == 'linear' and s['x_limits'] == base.XLIM
               and s['x_ticks'] == base.XTICKS for f in qa['figures'].values() for s in f['axis_settings'])
    for p in (FIGURE, TRANSFER):
        assert qa['figure_hashes'][p.name] == base.sha(p)
    report = base.REPORT.read_text(encoding='utf-8')
    tags = [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)]
    assert tags == list(range(1, 38))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', report)] == list(range(1, 13))
    common = common_principles(REPORT2.read_text(encoding='utf-8'))
    assert common in report
    assert '原β=5、n=7第11组中' not in report
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent / target.split('#')[0]).exists(), target
    qa['verification'] = dict(formula_nodes_checked=checked, maximum_absolute_formula_difference=maximum,
                              maximum_absolute_returned_parameter_difference=fit_maximum,
                              truth_rho_pair_max_difference=pair_error,
                              common_principles_identical_to_report2_except_numbers=True,
                              selected_sample=data['selection']['selected_id'], selection_rule_verified=True,
                              profiles_identical_to_family=True, original_n7_n15_profiles_preserved=True,
                              archived_beta5_n30_estimates_preserved=True, other_report1_results_unchanged=True,
                              fixed_linear_axes=True, source_hashes_unchanged=True,
                              new_samples=0, added_mapped_beta2_n30_estimates=50,
                              replaced_archived_estimates=0, main_figures=12, equations=37,
                              script_sha256=base.sha(Path(__file__)))
    base.write(QA, qa)
    print(qa['verification'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
