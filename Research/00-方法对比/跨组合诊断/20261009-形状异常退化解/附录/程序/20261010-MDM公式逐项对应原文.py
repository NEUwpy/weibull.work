"""Align report2 MDM equations and figure quantities with the source paper.

Reuse archived nodes, observations and estimates. Export two PNGs only.
Record the paper's duplicated gradient/increment symbol explicitly.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import re
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter
import numpy as np
from scipy.stats import beta as beta_distribution, f as f_distribution

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1] / '图片'
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
APPENDIX = HERE.parent / 'README.md'
ENTRY = ROOT / 'README.md'
PAPER = ROOT.parents[1] / 'src/content/182-046-pdf原文.md'
PDF = ROOT.parents[1] / 'public/182-046-图片/012c91a7-edf6-4ddb-942c-5a8add25e875_origin.pdf'
QA = Path(__file__).with_suffix('.json')
LABELS = ['MDM_low', 'MDM_edge']

PRINCIPLE = r'''MDM比较由同一组样本反算的尺度参数，以这些尺度值的标准差衡量差异。以下公式沿用原文编号。排序观测的累计概率由秩估计得到：

$$
\hat F(t_{(i)})=
\frac{i}{i+(n+1-i)F_{2(n+1-i),\,2i,\,0.5}},
\qquad i=1,2,\ldots,n.\tag{3}
$$

其中，n为样本量，t₍ᵢ₎为第i个排序观测，F̂(t₍ᵢ₎)为对应的累计概率估计；$F_{2(n+1-i),\,2i,\,0.5}$为自由度分别为2(n+1−i)和2i的F分布中位数。

给定位置参数γ和形状参数β，每个观测反算的尺度参数伪估计量为：

$$
\hat\eta_i=
\frac{t_{(i)}-\gamma}{[-\ln(1-\hat F(t_{(i)}))]^{1/\beta}},
\qquad i=1,2,\ldots,n.\tag{4}
$$

其中，η̂ᵢ为第i个观测反算的伪尺度。原文从最小观测开始逐步递减候选位置γⱼ；对每个γⱼ，尝试一系列候选形状βₖ，计算n个伪尺度的标准差$\sigma_\eta(\gamma_j,\beta_k)$。j、k分别为位置与形状候选的编号。保留该γⱼ下最小的标准差$\sigma_{\eta,\min}(\gamma_j)$，以及达到这个最低点的βₖ。

确定位置和形状后，尺度取全部伪尺度的平均值：

$$
\hat\eta=
\sum_{i=1}^{n}\left\{
\frac{t_{(i)}-\hat\gamma}{[-\ln(1-F(t_{(i)}))]^{1/\hat\beta}}
\right\}/n.\tag{6}
$$

其中，γ̂、β̂、η̂分别为位置、形状、尺度估计，式中F(t₍ᵢ₎)采用上述秩估计的累计概率。

位置由条件最小标准差的差分梯度确定：

$$
\nabla\gamma=
\frac{\sigma_{\eta,\min}(\gamma+\Delta\gamma)
-\sigma_{\eta,\min}(\gamma)}{\Delta\gamma}.\tag{7}
$$

其中，∇γ为条件最小标准差对γ的梯度，Δγ为位置增量。用正偏移值δ代替零梯度判据，本节取δ=0.20。达到该梯度的位置取为γ̂，再取该位置下标准差最低点对应的βₖ作为β̂，最后按式（6）取η̂。图15、16依次展示梯度定位、形状选择和伪尺度均值。'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


style = load(HERE / '20261010-配对图参照线精简.py', 'mdm_source_style')
audit = load(HERE / '20261010-六方法公式实现核对.py', 'mdm_source_audit')


def render(label, pair, rows, old):
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    blue, brown, gray = style.BLUE, style.BROWN, style.GRAY
    gamma_true = pair['normal']['gamma_true']
    eta_true = pair['normal']['eta_true']
    assert gamma_true == pair['abnormal']['gamma_true']
    assert eta_true == pair['abnormal']['eta_true']
    for index, (ax, meta) in enumerate(zip(axes.ravel(), old['axes'])):
        column = index % 3
        xfactor = gamma_true if column == 0 else 1
        yfactor = 1 if column == 0 else eta_true
        ax.set(xlim=np.asarray(meta['xlim']) * xfactor,
               xticks=np.asarray(meta['xticks']) * xfactor,
               ylim=np.asarray(meta['ylim']) * yfactor,
               yticks=np.asarray(meta['yticks']) * yfactor)
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
        ax.yaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 0]:
        ax.set(xlabel=r'$\gamma$', ylabel=r'$\nabla\gamma$')
        ax.axvline(gamma_true, color=gray, lw=.7, ls='--', zorder=0)
    for ax in axes[:, 1]:
        ax.set(xlabel=r'$\beta$', ylabel=r'$\sigma_\eta(\hat\gamma,\beta)$')
    for ax in axes[:, 2]:
        ax.set(xlabel=r'$i$', ylabel=r'$\hat\eta_i$')

    def star(ax, xx, yy):
        ax.scatter([xx], [yy], marker='*', s=58, color=brown,
                   edgecolors='white', lw=.5, zorder=6, clip_on=False)

    coordinate_errors = []
    means = []
    for row, role in enumerate(['normal', 'abnormal']):
        obj = pair[role]
        nodes = [r for r in rows if r['example'] == label and r['role'] == obj['role']]
        panel = lambda name: [r for r in nodes if r['panel'] == name]
        column = lambda records, name: np.asarray([float(r[name]) for r in records])
        curve = panel('gradient')
        gammas = column(curve, 'gamma')
        coordinate_errors.append(float(np.max(np.abs(gammas / gamma_true - column(curve, 'gamma_ratio')))))
        axes[row, 0].plot(gammas, column(curve, 'gradient'), color=blue, lw=1.15)
        axes[row, 0].axhline(.2, color=gray, lw=.7, ls=':')
        if obj['root_solver'] == 'right_edge_fit':
            roots = obj['gradient_roots']
            probes = panel('right_anchor')
            assert len(roots) == 2 and len(probes) == 24
            axes[row, 0].axvline(obj['gamma_hat'], color=brown, lw=1.1)
            axes[row, 0].scatter(roots, [.2] * len(roots), facecolors='white',
                                 edgecolors=blue, s=25, lw=.9, zorder=5)
            axes[row, 0].scatter(column(probes, 'gamma'), column(probes, 'gradient'),
                                 s=7, color='#444444', zorder=4)
        else:
            root = next(r for r in curve if float(r['gamma']) == obj['gamma_hat'])
            star(axes[row, 0], obj['gamma_hat'], float(root['gradient']))
        curve = panel('conditional_sigma')
        axes[row, 1].plot(column(curve, 'beta'), column(curve, 'sigma_ratio') * eta_true,
                          color=blue, lw=1.15)
        axes[row, 1].axvline(obj['beta_true'], color=gray, lw=.7, ls='--')
        star(axes[row, 1], obj['beta_hat'], obj['at_original']['sigma'])
        for stage, color in [('true_beta', gray), ('estimated_beta', brown)]:
            points = panel('pseudo_scale_' + stage)
            assert len(points) == obj['n']
            values = column(points, 'scale_ratio') * eta_true
            axes[row, 2].plot(column(points, 'rank'), values, color=color,
                              lw=1, marker='o', ms=3.8)
            if stage == 'estimated_beta':
                error = abs(float(np.mean(values)) - obj['eta_hat'])
                assert error < 1e-8 * (1 + abs(obj['eta_hat']))
                means.append(dict(role=role,mean=float(np.mean(values)),
                                  stored_eta=obj['eta_hat'],absolute_error=error))
        axes[row, 2].axhline(obj['eta_hat'], color=brown, ls='--', lw=.7)
        axes[row, 0].set_title(obj['role'] + f" · 第{obj['group']}组", loc='left', pad=14, fontsize=9)
    for i, ax in enumerate(axes.ravel()):
        ax.text(-.16, 1.04, chr(97 + i), transform=ax.transAxes, fontweight='bold', fontsize=11)
    legend = [Line2D([0], [0], color=gray, marker='o', ms=3, lw=1, label='真β的伪尺度'),
              Line2D([0], [0], color=brown, marker='o', ms=3, lw=1, label='估计β的伪尺度'),
              Line2D([0], [0], color=brown, ls='--', lw=.7, label='伪尺度均值'),
              Line2D([0], [0], marker='*', color=brown, ls='none', ms=7, label='原估计')]
    if label == 'MDM_edge':
        legend.extend([Line2D([0], [0], marker='o', mfc='white', mec=blue, ls='none', ms=4, label='梯度交点'),
                       Line2D([0], [0], marker='o', color='#444444', ls='none', ms=3, label='右端探测')])
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.52, .015), ncol=len(legend), fontsize=8)
    fig.subplots_adjust(left=.09, right=.985, bottom=.14, top=.91, wspace=.44, hspace=.48)
    fig.canvas.draw()
    for item in fig.findobj(matplotlib.text.Text):
        if item.get_visible() and item.get_text():
            box = item.get_window_extent(fig.canvas.get_renderer())
            assert box.x0 >= -1 and box.y0 >= -1
            assert box.x1 <= fig.bbox.x1 + 1 and box.y1 <= fig.bbox.y1 + 1
    axes_meta = [{k:list(map(float, getattr(ax, 'get_' + k)()))
                  for k in ['xlim', 'ylim', 'xticks', 'yticks']} for ax in axes.ravel()]
    assert axes_meta[:3] == axes_meta[3:]
    assert max(coordinate_errors) < 1e-12
    target = IMAGES / f'配对情形_{label}.png'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(target, dpi=400, facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught)
    plt.close(fig)
    return dict(path=str(target),sha256=digest(target),axes=axes_meta,
                inverse_coordinate_max_error=max(coordinate_errors),scale_means=means,
                no_new_curve_nodes=True,all_labels_within_canvas=True)


def main():
    pairs_path = HERE / '20261010-配对图参照线精简核验.json'
    curves_path = HERE / '20261010-参照线精简图数据.csv'
    catalog_path = ROOT / '跨组合汇总/程序/20261007-新增五组合/13组合取数.json'
    pairs = json.loads(pairs_path.read_text(encoding='utf-8'))
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))['sources']
    with curves_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    protected = {str(p):digest(p) for p in [PAPER, PDF, pairs_path, curves_path,
                 catalog_path, ROOT / '报告1：高形状参数下的估计偏移.md',
                 HERE / '20261010-MDM沿用原文表达.py', Path(__file__)]}
    for entry in catalog:
        base = Path(entry['program'])
        added_batch = base.name == '程序'
        base = base if added_batch else base.parent
        matrix = base / ('中间数据/matrix.json' if added_batch else '完整矩阵/数据/matrix.json')
        assert matrix.exists(), matrix
        for path in [matrix, base / '依赖快照/python/methods/mdm.py']:
            protected[str(path)] = digest(path)
    protected_png = {str(p):digest(p) for p in IMAGES.glob('*.png')
                     if p.stem not in ['配对情形_' + label for label in LABELS]}
    checks = []
    for label in LABELS:
        for role in ['normal', 'abnormal']:
            obj = pairs['pairs'][label][role]
            x = np.asarray(obj['values'])
            n = len(x)
            entry = next(e for e in catalog if e['combination'] == obj['combination'])
            base = Path(entry['program'])
            base = base if base.name == '程序' else base.parent
            method = base / '依赖快照/python/methods/mdm.py'
            env = dict(np=np,t=x,n=n,t_min=x[0],offset=.2,minimize_scalar=audit.minimize_scalar,
                       neg_ln_1_minus_F=-np.log(1-(np.arange(1,n+1)-.3)/(n+.4)),
                       beta_sigma_cache={},profile_gradient_cache={})
            audit.bind(method,['calculate_eta_std','find_best_beta_for_gamma','profile_sigma','profile_gradient'],env)
            for record in rows:
                if record['example'] != label or record['role'] != obj['role']:
                    continue
                panel = record['panel']
                if panel in ['gradient', 'right_anchor']:
                    actual = env['profile_gradient'](float(record['gamma']))
                    expected = float(record['gradient'])
                    limit = (8e-5 if panel == 'right_anchor' else 2e-7) * (1 + abs(expected))
                elif panel == 'conditional_sigma':
                    actual = env['calculate_eta_std'](float(record['beta']),obj['gamma_hat'],x)
                    expected = float(record['sigma_ratio']) * obj['eta_true']
                    limit = 1e-9 * (1 + abs(expected))
                elif panel.startswith('pseudo_scale_'):
                    beta = obj['beta_true'] if panel.endswith('true_beta') else obj['beta_hat']
                    i = int(float(record['rank'])) - 1
                    actual = (x[i]-obj['gamma_hat'])/env['neg_ln_1_minus_F'][i]**(1/beta)
                    expected = float(record['scale_ratio']) * obj['eta_true']
                    limit = 1e-9 * (1 + abs(expected))
                else:
                    continue
                error = abs(float(actual)-expected)
                assert error <= limit, (label,role,panel,error,limit)
                checks.append(dict(example=label,role=role,panel=panel,absolute_error=error))
            beta, sigma = env['find_best_beta_for_gamma'](obj['gamma_hat'])
            assert abs(beta-obj['beta_hat']) < 1e-8
            eta = np.mean((x-obj['gamma_hat'])/env['neg_ln_1_minus_F']**(1/beta))
            assert abs(eta-obj['eta_hat']) < 1e-8 * (1+abs(eta))
    rank_checks = {}
    for n in [7,15,30]:
        i = np.arange(1,n+1)
        probability = i/(i+(n+1-i)*f_distribution.ppf(.5,2*(n+1-i),2*i))
        error = float(np.max(np.abs(probability-beta_distribution.ppf(.5,i,n+1-i))))
        assert error < 1e-13
        rank_checks[n] = dict(probabilities=probability.tolist(),max_error=error)

    before = REPORT.read_text(encoding='utf-8')
    anchor = '**图14｜MDM（δ=0.20）各类明显异常估计的发生次数。**'
    start = before.index(anchor) + len(anchor)
    end = before.index('**（1）阈值交点的低估。**',start)
    revised = before[:start] + '\n\n' + PRINCIPLE + '\n\n' + before[end:]
    assert re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*',before,re.M) == re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*',revised,re.M)
    assert re.findall(r'!\[[^\]]*\]\([^\n]*\)',before) == re.findall(r'!\[[^\]]*\]\([^\n]*\)',revised)
    assert [int(q) for q in re.findall(r'\*\*图(\d+)｜',revised)] == list(range(1,25))
    assert re.findall(r'\\tag\{(\d+)\}',PRINCIPLE) == ['3','4','6','7']
    assert all(token not in PRINCIPLE for token in ['x_{(i)}','operatorname{Cov}','arg\\min','/\\eta_0'])
    for match in re.findall(r'!\[[^\]]*\]\(([^\n]*)\)',revised):
        assert (ROOT / match).exists(), match
    figures = {label:render(label,pairs['pairs'][label],rows,pairs['figures'][label]) for label in LABELS}
    assert all(digest(path) == value for path,value in protected.items())
    assert all(digest(path) == value for path,value in protected_png.items())
    REPORT.write_text(revised,encoding='utf-8',newline='\r\n')
    equation_mapping = {
        '3':'Exact median rank; same F-distribution quantile and degrees of freedom.',
        '4':'Pseudo scale; t_(i), gamma, beta and rank probability as in the paper.',
        '6':'Arithmetic mean over all n pseudo scales; retain paper F(t_(i)) notation and clarify use of rank probability.',
        '7':'Same finite forward difference of conditional minimum SD. Delta gamma denotes the increment; the printed paper reuses nabla gamma for both increment and gradient.'}
    result = dict(scope='Report2 section2.1.4 and figures15/16; source-paper equations3/4/6/7.',
                  source_sha256=protected,sources_unchanged=True,
                  protected_png_sha256=protected_png,other_pngs_unchanged=True,
                  equation_mapping=equation_mapping,original_median_rank_checks=rank_checks,
                  figure_contract=dict(conclusion='Location threshold, shape at conditional SD minimum, scale as arithmetic mean.',
                                       backend='Python',archetype='quantitative grid',export='Two PNGs only;400dpi',
                                       same_limits_and_ticks_within_paired_columns=True,
                                       axes='Raw gamma, SD and pseudo scale; inverse transform of archived display normalization.',
                                       added_mark='One estimated-pseudo-scale mean line in each right panel.'),
                  figures=figures,frozen_formula_check_count=len(checks),frozen_formula_checks=checks,
                  archived_calculation='Bernard probabilities; bounded continuous beta search0.1..15; central or one-sided finite differences; endpoint fallback. Preserved without re-estimation.',
                  compensation=.2,no_new_samples=True,no_new_estimates=True,
                  sample_tables_case_analysis_counts_and_other_sections_unchanged=True,
                  report_sha256=digest(REPORT),visual_review='Pending inspection of both exported PNGs.')
    QA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'PASS: equations3/4/6/7; {len(checks)} frozen formula checks; raw axes and four verified scale means; protected sources unchanged.')


if __name__ == '__main__':
    main()
