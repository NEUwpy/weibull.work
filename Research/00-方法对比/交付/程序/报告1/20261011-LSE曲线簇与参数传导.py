"""LSE: paired beta=2/5 curve bundles, then slope -> shape -> scale.

Reuse the 200 saved n=7/15 profiles byte-for-byte at the data level. For n=30,
reuse saved observations and the 50 archived beta=5 fits; estimate the already
mapped beta=2 observations with the frozen LSE. No random draws or archived-fit
replacement. Source data and checks stay here; export two PNGs only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, RESULT, setup_runtime, save_png, write_atomic

FROZEN = HERE / '依赖快照/python'
sys.path.insert(0, str(FROZEN))
spec = importlib.util.spec_from_file_location('r1_lse_bundle_frozen', FROZEN / 'methods/lse.py')
lse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lse)
INPUT = RESULT / '报告1/中间数据'
N30 = HERE / '20261010-导入图n30样本.json'
MATRIX = HERE.parent / 'W5,1000,500/完整矩阵/数据/matrix.json'
CACHE = HERE / '20261011-LSE曲线簇与参数传导.json'
QA = HERE / '20261011-LSE曲线簇与参数传导核验.json'
FIGURE = RESULT / '报告1/图4_LSE六格机制.png'
TRANSFER = RESULT / '报告1/图7_LSE参数传导.png'
FIGURE_QA = INPUT / '逐法图核验.json'
REPORT = ROOT / '报告1：高形状参数下的估计偏移.md'
README = ROOT / 'README.md'
CONDITIONS = [(b, n) for n in (7, 15, 30) for b in (2, 5)]
BLUE, RETURN = '#345D7E', '#B55E3E'
XLIM, XTICKS = [-25, 1400], [0, 500, 1000]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':')) + '\n').encode('utf-8'))


def sources():
    paths = [INPUT / '样本.json', INPUT / '实际估计.json', INPUT / '逐法过程曲线.json',
             N30, MATRIX, FROZEN / 'methods/lse.py', FROZEN / 'base.py']
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def protected_results():
    folder = RESULT / '报告1'
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, FIGURE_QA)}


def regression(x, gamma):
    """The frozen estimator's OLS and original total/residual variance F ratio."""
    x = np.asarray(x, float)
    z = lse.log_weibull_order_stat_means(len(x))
    y = np.log(x - gamma)
    zc, yc = z - z.mean(), y - y.mean()
    szz, syy = float(zc @ zc), float(yc @ yc)
    b = float(zc @ yc) / szz
    a = float(y.mean() - b * z.mean())
    residual = y - a - b * z
    loss = float(residual @ residual) / syy
    dy = -1 / (x - gamma)
    db = float(zc @ dy) / szz
    da = float(dy.mean() - db * z.mean())
    szy = float(zc @ yc)
    dloss = -(2 * szy * float(zc @ dy) / (szz * syy)
              - szy ** 2 * 2 * float(yc @ dy) / (szz * syy ** 2))
    f = (len(x) - 2) / ((len(x) - 1) * loss)
    return dict(slope=b, intercept=a, beta=1 / b, eta=float(np.exp(a)),
                loss=loss, f=f, slope_derivative=db, intercept_derivative=da,
                loss_derivative=dloss)


def added_curve(sample, archived):
    x = np.asarray(sample['observations'], float)
    if archived is None:
        estimator = lse.LSE(x)
        result = estimator.run(mu_steps=200)
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
    return dict(method='lse', source='paired_n30', beta=sample['beta'], n=30,
                sample_id=sample['sample_id'], observations=sample['observations'],
                sample_min=float(x[0]), fit=fit, points=points,
                truth=next(p for p in points if p[0] == 500),
                returned=next(p for p in points if p[0] == selected),
                estimate_origin='archived_beta5' if archived is not None else 'frozen_LSE_beta2')


def summarize(rows):
    summaries = []
    for beta, n in CONDITIONS:
        rr = [r for r in rows if r['beta'] == beta and r['n'] == n]
        assert len(rr) == 50
        gamma = np.array([r['fit']['gamma_hat'] for r in rr])
        derivatives = [regression(r['observations'], 500)['loss_derivative'] for r in rr]
        right = [r for r in rr if r['fit']['gamma_hat'] > 500]
        summaries.append(dict(beta=beta, n=n, curves=50, gamma_median=float(np.median(gamma)),
                              median_absolute_gamma_error=float(np.median(abs(gamma - 500))),
                              gamma_above_truth=int(np.sum(gamma > 500)), gamma_at_zero=int(np.sum(gamma == 0)),
                              median_absolute_loss_derivative=float(np.median(np.abs(derivatives))),
                              truth_loss_quartiles=np.quantile([r['truth'][1] for r in rr], [.25, .5, .75]).tolist(),
                              rightward_shape_below_truth=sum(r['fit']['beta_hat'] < beta for r in right),
                              rightward_scale_below_truth=sum(r['fit']['eta_hat'] < 1000 for r in right)))
    return summaries


def build():
    if CACHE.exists():
        assert read(CACHE)['source_hashes'] == sources()
        print('REUSED: LSE曲线簇与参数传导数据。', flush=True)
        return
    hashes, protected = sources(), protected_results()
    samples = read(INPUT / '样本.json')
    index = {(s['beta'], s['n'], s['sample_id']): s for s in samples}
    rows = [copy.deepcopy(r) for r in read(INPUT / '逐法过程曲线.json')['curves']
            if r['method'] == 'lse' and r['source'] == 'paired']
    assert len(rows) == 200
    for r in rows:
        r['observations'] = index[r['beta'], r['n'], r['sample_id']]['observations']
    matrix, n30 = read(MATRIX), read(N30)
    assert n30['source_sha256'] == sha(MATRIX)
    archived = {r['id']: r for r in matrix['results'] if r['n'] == 30 and r['method_id'] == 'lse'}
    assert len(archived) == 50
    for sample in n30['samples']:
        if sample['beta'] == 5:
            original = next(s['values'] for s in matrix['samples']
                            if s['n'] == 30 and s['id'] == sample['sample_id'])
            assert sample['observations'] == original
        rows.append(added_curve(sample, archived[sample['sample_id']] if sample['beta'] == 5 else None))
    assert hashes == sources() and protected == protected_results()
    write(CACHE, dict(source_hashes=hashes, protected_results=protected, conditions=CONDITIONS,
                      new_random_draws=0, reused_n7_n15_curves=200, added_n30_curves=100,
                      reused_beta5_n30_estimates=50, added_mapped_beta2_n30_estimates=50,
                      replaced_archived_estimates=0,
                      transfer_scope='All 50 n=7 profiles per beta, identical to criterion panels a/b; no sample selection.',
                      columns=['gamma', '1-R2', 'conditional_beta', 'conditional_eta', 'unused', 'unused'],
                      n30_provenance={k: v for k, v in n30.items() if k != 'samples'},
                      summaries=summarize(rows), curves=rows))
    print('BUILT: 300条LSE曲线；无新抽样，存档估计未替换。', flush=True)


def style():
    setup_runtime()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 7, 'axes.labelsize': 7, 'axes.titlesize': 7.2,
                         'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'axes.linewidth': .7,
                         'axes.spines.right': False, 'axes.spines.top': False, 'axes.unicode_minus': False})
    return plt


def axis(ax, label, beta, n, limits, ticks, letter):
    ax.set(xlim=XLIM, xticks=XTICKS, ylim=limits, yticks=ticks, xlabel='γ', ylabel=label)
    ax.axvline(500, color='black', ls=':', lw=.8)
    ax.set_title(f'β={beta}，n={n}', loc='left', pad=9)
    ax.text(-.13, 1.10, letter, transform=ax.transAxes, fontsize=8, weight='bold')
    return dict(x_limits=XLIM, x_ticks=XTICKS, y_limits=limits, y_ticks=ticks,
                x_scale=ax.get_xscale(), y_scale=ax.get_yscale())


def bundle(ax, rows, column):
    hidden_curve_points = hidden_return_values = 0
    lo, hi = ax.get_ylim()
    for r in rows:
        values = [(1 / p[2] if column == 'slope' else p[column]) for p in r['points']]
        ax.plot([p[0] for p in r['points']], values, color=BLUE, alpha=.20, lw=.65)
        truth, chosen = r['truth'], r['returned']
        tv = 1 / truth[2] if column == 'slope' else truth[column]
        cv = 1 / chosen[2] if column == 'slope' else chosen[column]
        ax.scatter(500, tv, color=BLUE, s=4, alpha=.5, linewidths=0, zorder=3)
        ax.scatter(chosen[0], cv, color=RETURN, marker='x', s=10, alpha=.7, linewidths=.7, zorder=4)
        hidden_curve_points += sum(not (lo <= v <= hi and XLIM[0] <= p[0] <= XLIM[1])
                                   for p, v in zip(r['points'], values))
        hidden_return_values += int(not (lo <= cv <= hi and XLIM[0] <= chosen[0] <= XLIM[1]))
        if column == 1:
            ax.plot(chosen[0], .018, marker='|', color=RETURN, ms=5, alpha=.55,
                    transform=ax.get_xaxis_transform())
    return dict(curves=len(rows), sample_ids=[r['sample_id'] for r in rows],
                hidden_curve_points=hidden_curve_points, hidden_return_values=hidden_return_values)


def render():
    data = read(CACHE)
    assert data['source_hashes'] == sources()
    plt = style()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    for i, (beta, n) in enumerate(CONDITIONS):
        ax = axes.flat[i]
        states.append(axis(ax, r'$1-R^2(\gamma)$', beta, n, [0, .25], [0, .05, .10, .15, .20, .25], chr(97 + i)))
        rows = sorted((r for r in data['curves'] if r['beta'] == beta and r['n'] == n), key=lambda r: r['sample_id'])
        panels.append(dict(beta=beta, n=n, **bundle(ax, rows, 1)))
    assert all(s == states[0] for s in states)
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    save_png(fig, FIGURE, dpi=450)
    plt.close(fig)
    first = dict(method='lse', file=FIGURE.stem, panels=panels, axis_settings=states,
                 all_curves_real=True, six_panel_axes_identical=True, single_panels=[], png_dimensions=[3240, 3240])
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
    panels, states = [], []
    definitions = [('slope', r'$b(\gamma)$', [0, 2], [0, .5, 1, 1.5, 2]),
                   (2, r'$\hat\beta(\gamma)$', [0, 10], [0, 2, 4, 6, 8, 10]),
                   (3, r'$\hat\eta(\gamma)$', [0, 1600], [0, 500, 1000, 1500])]
    for row, (column, label, limits, ticks) in enumerate(definitions):
        for col, beta in enumerate((2, 5)):
            ax = axes[row, col]
            states.append(axis(ax, label, beta, 7, limits, ticks, chr(97 + row * 2 + col)))
            ax.axhline(1 / beta if column == 'slope' else (beta if column == 2 else 1000),
                       color='.55', ls='--', lw=.7)
            rows = sorted((r for r in data['curves'] if r['beta'] == beta and r['n'] == 7), key=lambda r: r['sample_id'])
            panels.append(dict(beta=beta, n=7, quantity=column, criterion_panel='a' if beta == 2 else 'b',
                               **bundle(ax, rows, column)))
    assert all(states[i] == states[i + 1] for i in (0, 2, 4))
    fig.subplots_adjust(left=.12, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.36)
    save_png(fig, TRANSFER, dpi=450)
    plt.close(fig)
    second = dict(file=TRANSFER.stem, panels=panels, axis_settings=states,
                  same_profiles_as_criterion=True, no_single_sample_selection=True, png_dimensions=[3240, 3240])
    qa = read(QA) if QA.exists() else {}
    qa.update(figures={'criterion': first, 'transfer': second},
              figure_hashes={FIGURE.name: sha(FIGURE), TRANSFER.name: sha(TRANSFER)})
    write(QA, qa)
    if FIGURE_QA.exists():
        shared = read(FIGURE_QA)
        shared['process_figures'] = [first if r['method'] == 'lse' else r for r in shared['process_figures']]
        shared['lse_parameter_transfer'] = second
        write(FIGURE_QA, shared)
    print('EXPORTED: LSE三档n准则曲线簇与参数传导曲线簇。', flush=True)
    return first


SECTION = r'''### 2.2　[LSE](../../src/content/algorithms/lse.md)

LSE对每个候选位置γ拟合一条直线，选择F比最大的位置，再由斜率和截距恢复形状与尺度。其依据是Weibull变量的对数距离关系及顺序统计量期望：

$$\begin{aligned}
\ln(X-\gamma)&=\ln\eta+\frac{Z}{\beta},\\
\mathbb{E}[\ln(X_{(i)}-\gamma)]&=\ln\eta+\frac{z_i}{\beta},\qquad z_i=\mathbb{E}[Z_{(i)}].
\end{aligned}
\tag{11}$$

其中，X为Weibull随机变量，Z=βln[(X−γ)/η]为标准对数Weibull变量，X₍ᵢ₎、Z₍ᵢ₎为n个变量排序后的第i个值，𝔼为数学期望，zᵢ为标准变量的顺序统计量期望。对实际观测t₍ᵢ₎，以zᵢ为横坐标、对数距离yᵢ为纵坐标作最小二乘回归：

$$y_i(\gamma)=\ln(t_{(i)}-\gamma)\approx a+bz_i,\qquad
\hat\beta(\gamma)=\frac1b,\qquad\hat\eta(\gamma)=e^a.
\tag{12}$$

其中，a、b分别为截距、斜率，e为自然指数的底数。LSE用F比评价直线拟合程度：

$$\begin{aligned}
\mathrm{SST}&=\sum_i(y_i-\overline y)^2, &\mathrm{SSE}&=\sum_i(y_i-a-bz_i)^2,\\
F(\gamma)&=\frac{\mathrm{SST}/(n-1)}{\mathrm{SSE}/(n-2)}, &R^2(\gamma)&=1-\frac{\mathrm{SSE}}{\mathrm{SST}}.
\end{aligned}
\tag{13}$$

其中，ȳ为对数距离的均值，SST、SSE分别为总平方和、残差平方和，F为方差比，R²为回归决定系数。由式（13），位置判据写成：

$$\begin{aligned}
F(\gamma)&=\frac{n-2}{(n-1)[1-R^2(\gamma)]},\\
\hat\gamma&=\underset{0\le\gamma<t_{(1)}}{\arg\max}\,F(\gamma)
=\underset{0\le\gamma<t_{(1)}}{\arg\min}\,[1-R^2(\gamma)].
\end{aligned}
\tag{14}$$

其中，t₍₁₎为最小观测。固定n后，最大化F比等价于最小化1−R²，图6按式（14）展示位置准则，橙叉标记所选γ。

![图6　LSE在不同形状与样本量下的位置准则](交付/结果/报告1/图4_LSE六格机制.png)

**图6｜高β时，真位置附近的准则曲线更平，最低点可向两侧偏移。**

β=5时，改变γ对真位置附近拟合程度的影响较小，不同位置难以区分。样本间距的随机波动因而可能使最佳拟合位置偏离真值；随n增大，位置偏移减轻。

这种差别可以从对数变换看出。观测较集中且γ未接近最小观测时，在样本均值附近展开：

$$\ln(t_{(i)}-\gamma)\approx\ln(\overline t-\gamma)
+\frac{t_{(i)}-\overline t}{\overline t-\gamma}
-\frac{(t_{(i)}-\overline t)^2}{2(\overline t-\gamma)^2}.
\tag{15}$$

其中，t̄为样本均值。式（15）的前两项只改变截距和整体比例，不影响R²；二次项才改变点列的弯曲程度。高β时相对间距较小，二次项的影响较弱，因此位置改变较大时仍可能保持接近的拟合程度。

配对样本在真γ处的对数距离仅随β整体缩放，R²保持相同。图6中的差别来自离开真位置后，对数变换对样本间距的重新匹配；最低点位于哪一侧，仍由具体样本决定。

位置选定后，回归斜率和截距决定其余两个参数。式（12）的最小二乘解为：

$$\begin{aligned}
b(\gamma)&=\frac{\sum_i(z_i-\overline z)\ln(t_{(i)}-\gamma)}{\sum_i(z_i-\overline z)^2},\\
a(\gamma)&=\frac1n\sum_i\ln(t_{(i)}-\gamma)-b(\gamma)\overline z.
\end{aligned}
\tag{16}$$

其中，z̄为参考坐标的均值。图7使用图6a、b中的全部曲线，按式（16）、（12）展示位置选择向形状、尺度的传导。

![图7　LSE的位置选择与参数传导](交付/结果/报告1/图7_LSE参数传导.png)

**图7｜所选γ通过回归斜率和截距传递到β、η。** 蓝点为固定真γ的条件拟合，橙叉为最终估计。

图7中，γ右移使较小观测的对数距离下降更多，回归斜率增大，按式（12）取倒数后β降低；截距按式（16）随右移减小，进而得到图7e、f中的η降低。左移则可产生相反变化。LSE选择的是线性匹配更好的位置，高β下的位置区分不足使这一选择更容易伴随参数偏移。

'''


def revise():
    text = REPORT.read_text(encoding='utf-8')
    start, end = text.index('### 2.2　'), text.index('### 2.3　')
    before, after = text[:start], text[end:]
    already = '图7　LSE的位置选择与参数传导' in text[start:end]
    if not already:
        after = re.sub(r'\\tag\{(\d+)\}', lambda m: r'\tag{' + str(int(m[1]) + 1) + '}', after)
        after = re.sub(r'式（(\d+)）', lambda m: '式（' + str(int(m[1]) + 1 if int(m[1]) >= 16 else int(m[1])) + '）', after)
        after = re.sub(r'(?<!补充)图(\d+)(?![\d_])',
                       lambda m: '图' + str(int(m[1]) + 1) if 7 <= int(m[1]) <= 10 else m[0], after)
        after = after.replace('图4–10', '图4–11')
    after = after.replace('图4–11对比β=2、5和n=7、15，每个条件使用50组样本；同一样本量下两种β共用潜在单位指数样本E。下排两格分别展开上排两条深蓝曲线。',
                          '图4、6比较β=2、5及n=7、15、30，图7展示n=7的参数传导曲线簇。其余逐法组图比较β=2、5及n=7、15，下排展开上方同一组样本。每个条件使用50组样本，同一样本量下两种β共用潜在单位指数样本E。')
    link = '[LSE曲线簇与参数传导数据](交付/程序/报告1/20261011-LSE曲线簇与参数传导.json)'
    if link not in after:
        after = after.replace('**数据与程序。** ', '**数据与程序。** ' + link + '、', 1)
    updated = before + SECTION + after
    if updated != text:
        write_atomic(REPORT, updated.encode('utf-8'))
    readme = README.read_text(encoding='utf-8')
    if not already:
        readme = readme.replace('报告1的WMLE图8', '报告1的WMLE图9')
        readme = readme.replace('第2.6节与图10解释', '第2.6节与图11解释').replace('图10固定删除', '图11固定删除')
        readme = readme.replace('后续各方法图顺延为图6—10', '后续各方法图现为图6—11')
    marker = '报告1的LSE原理与报告2统一'
    note = ('报告1的LSE原理与报告2统一：最大化F比等价于最小化1−R²。图6为β=2/5、n=7/15/30的准则曲线簇，'
            '图7用图6a、b的同一批50组样本展示斜率、β及η的传导，无正常/异常单例筛选。'
            '[20261011-LSE曲线簇与参数传导.py](交付/程序/报告1/20261011-LSE曲线簇与参数传导.py)提供`build`、`render`、`revise`、`verify`；'
            '曲线数据和核验记录与脚本同目录，已接入统一制图入口。n=7/15复用200条曲线；'
            'n=30复用已保存样本及β=5的50条估计，仅新增转换后β=2的50条LSE估计，无新抽样、不替换存档结果。只输出两张PNG。\n\n')
    if marker in readme:
        a = readme.index(marker)
        b = readme.index('\n\n', a) + 2
        readme = readme[:a] + note + readme[b:]
    else:
        readme = readme.replace('## 整理与恢复\n', note + '## 整理与恢复\n', 1)
    if readme != README.read_text(encoding='utf-8'):
        write_atomic(README, readme.encode('utf-8'))
    print('REVISED: LSE原理、曲线簇解释和全文图式编号。', flush=True)


def verify():
    data, qa = read(CACHE), read(QA)
    assert data['source_hashes'] == sources()
    assert data['protected_results'] == protected_results()
    old = {(r['beta'], r['n'], r['sample_id']): r for r in read(INPUT / '逐法过程曲线.json')['curves']
           if r['method'] == 'lse' and r['source'] == 'paired'}
    maximum, checked, slope_derivatives = 0., 0, []
    for r in data['curves']:
        if r['n'] in (7, 15):
            previous = old[r['beta'], r['n'], r['sample_id']]
            assert r['points'] == previous['points'] and r['fit'] == previous['fit']
        for point in r['points']:
            fit = regression(r['observations'], point[0])
            err = max(abs(point[1] - fit['loss']), abs(point[2] - fit['beta']), abs(point[3] - fit['eta']))
            maximum = max(maximum, err)
            assert np.allclose(point[1:4], [fit['loss'], fit['beta'], fit['eta']], rtol=1e-9, atol=1e-7)
            assert fit['slope_derivative'] > 0
            if r['n'] == 7:
                assert fit['intercept_derivative'] < 0
            checked += 1
            slope_derivatives.append(fit['slope_derivative'])
        chosen = regression(r['observations'], r['fit']['gamma_hat'])
        assert np.allclose([chosen['beta'], chosen['eta']], [r['fit']['beta_hat'], r['fit']['eta_hat']], rtol=1e-8, atol=1e-6)
        f_max = r['fit']['extra']['solution_info']['f_max']
        assert np.isclose(chosen['f'], f_max, rtol=1e-9, atol=1e-8)
    invariance = []
    by_key = {(r['beta'], r['n'], r['sample_id']): r for r in data['curves']}
    for n in (7, 15, 30):
        differences = [abs(by_key[2, n, sid]['truth'][1] - by_key[5, n, sid]['truth'][1]) for sid in range(1, 51)]
        assert max(differences) < 1e-12
        invariance.append(dict(n=n, maximum_absolute_truth_loss_difference=max(differences)))
    report = REPORT.read_text(encoding='utf-8')
    tags = [int(n) for n in re.findall(r'\\tag\{(\d+)\}', report)]
    assert tags == list(range(1, len(tags) + 1))
    figures = [int(n) for n in re.findall(r'\*\*图(\d+)｜', report)]
    assert figures == list(range(1, 12))
    assert report.count('White比值') == 0
    assert '原β=5、n=7第37组中，γ由500移至约974时' not in report
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if '://' not in target and not target.startswith('#'):
            assert (REPORT.parent / target.split('#')[0]).exists(), target
    for path in (FIGURE, TRANSFER):
        assert qa['figure_hashes'][path.name] == sha(path)
    assert all(s['x_scale'] == s['y_scale'] == 'linear'
               for f in qa['figures'].values() for s in f['axis_settings'])
    assert all(p['curves'] == 50 and p['sample_ids'] == list(range(1, 51))
               for f in qa['figures'].values() for p in f['panels'])
    qa['verification'] = dict(checked_nodes=checked, maximum_absolute_formula_difference=maximum,
                              selected_f_max_checked=300, positive_slope_derivatives=len(slope_derivatives),
                              n7_intercept_decreases_verified=True, truth_loss_invariance=invariance,
                              source_hashes_unchanged=True, other_report1_results_unchanged=True,
                              equations=tags, main_figures=figures, script_sha256=sha(Path(__file__)),
                              original_estimates_replaced=0, new_random_draws=0)
    write(QA, qa)
    print(json.dumps(qa['verification'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['build', 'render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
