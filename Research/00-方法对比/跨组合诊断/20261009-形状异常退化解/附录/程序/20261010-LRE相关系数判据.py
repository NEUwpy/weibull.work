"""Use the original correlation criterion in report2's LRE explanation.

Read the archived pairs and plot nodes. Reconstruct three six-panel figures,
changing only the middle-column criterion from residual fraction to Pearson
correlation. Keep original samples, parameters, fit points and all other PNGs.
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
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1]/'图片'
REPORT = ROOT/'报告2：小样本情况下的明显异常估计.md'
QA = HERE/'20261010-LRE相关系数判据核验.json'
DATA = HERE/'20261010-LRE相关系数曲线.csv'
LABELS = ['LRE_zero', 'LRE_left', 'LRE_right']
PRINCIPLE = r'''LRE从Weibull分布函数的线性化出发：

$$
\ln[-\ln(1-F(x))]
=\beta\ln(x-\gamma)-\beta\ln\eta.
$$

F(x)为Weibull分布函数。将第i个排序观测x₍ᵢ₎的累积概率用绘图位置pᵢ代替，得到：

$$
z_i=\ln[-\ln(1-p_i)]
\approx\beta y_i-\beta\ln\eta,
\qquad y_i=\ln(x_{(i)}-\gamma).
$$

pᵢ为按次序i和样本量n分配的累积概率，zᵢ为相应的概率图参考坐标。与LSE采用顺序统计量期望不同，这些参考点来自绘图概率的分位变换。

LRE以样本对数距离yᵢ为横坐标、zᵢ为纵坐标，拟合直线zᵢ≈a+byᵢ。斜率b直接对应形状β，截距a对应−βlnη，因此：

$$
\hat\beta(\gamma)=b,
\qquad
\hat\eta(\gamma)=e^{-a/b}.
$$

LRE通过改变γ，使样本对数距离与概率图参考坐标的线性相关性最大，位置判据为：

$$
\hat\gamma
=\underset{0\le\gamma<x_{(1)}}{\arg\max}\,\rho(\gamma).
$$

ρ(γ)为给定γ时yᵢ与zᵢ的线性相关系数。以γ为横坐标、ρ(γ)为纵坐标，曲线最高点对应LRE选择的位置估计。'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_style():
    path = HERE/'20261010-配对图参照线精简.py'
    spec = importlib.util.spec_from_file_location('archived_pair_style', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(label, pair, rows, previous, style):
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    blue, brown, gray = style.BLUE, style.BROWN, style.GRAY
    old_axes = previous['axes']
    for index, ax in enumerate(axes.ravel()):
        meta = old_axes[index]
        ax.set(xlim=meta['xlim'], xticks=meta['xticks'],
               ylim=meta['ylim'], yticks=meta['yticks'])
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 0]:
        ax.set(xlabel=r'$\ln(d_i/\eta_0)$', ylabel=r'$z_i$')
    for ax in axes[:, 1]:
        ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\rho(\gamma)$',
               ylim=(.75, 1), yticks=[.75, .8, .85, .9, .95, 1])
        ax.yaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 2]:
        ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\hat\beta(\gamma)$')
    for ax in axes[:, 1:].ravel():
        ax.axvline(1, color=gray, lw=.7, ls='--', zorder=0)

    def star(ax, xx, yy):
        ax.scatter([xx], [yy], marker='*', s=58, color=brown,
                   edgecolors='white', lw=.5, zorder=6, clip_on=False)

    records, correlations, visible_points = [], {}, 0
    for row, key in enumerate(['normal', 'abnormal']):
        obj = pair[key]
        values = np.asarray(obj['values'])
        role_rows = [r for r in rows if r['example'] == label and r['role'] == obj['role']]
        fit = [r for r in role_rows if r['panel'] == 'fit_estimated']
        criterion = [r for r in role_rows if r['panel'] == 'criterion']
        assert len(fit) == obj['n']
        columns = lambda items, name: np.asarray([float(r[name]) for r in items])
        xx, zz, fitted = [columns(fit, col) for col in ['horizontal', 'vertical', 'fitted']]
        assert np.allclose(xx, np.log((values-obj['gamma_hat'])/obj['eta_true']), rtol=0, atol=1e-14)
        ax = axes[row, 0]
        ax.plot(xx, fitted, color=brown, lw=1.1)
        ax.scatter(xx, zz, s=17, color=brown, edgecolors='white', lw=.35, zorder=4)
        for i, (u, v) in enumerate(zip(xx, zz), 1):
            ax.annotate(str(i), (u, v), xytext=(8 if i%2 else -8, 0),
                        textcoords='offset points', fontsize=6,
                        ha='left' if i%2 else 'right', va='center', color='#515151')
        visible_points += len(fit)

        gs, ratios, losses, betas = [columns(criterion, col)
                                     for col in ['gamma', 'gamma_ratio', 'loss', 'beta']]
        rho = lambda gamma: float(np.corrcoef(np.log(values-gamma), zz)[0, 1])
        rs = np.asarray([rho(g) for g in gs])
        assert np.all(rs > 0)
        error = float(np.max(np.abs(rs**2-(1-losses))))
        assert error < 2e-14
        original_rho, true_rho = rho(obj['gamma_hat']), rho(obj['gamma_true'])
        assert abs(original_rho**2-obj['at_original']['r2']) < 2e-14
        # The maximum of rho corresponds to the minimum of the archived loss.
        assert rs.max()-rs[np.argmin(losses)] < 2e-14
        axes[row, 1].plot(ratios, rs, color=blue, lw=1.15)
        star(axes[row, 1], obj['gamma_hat']/obj['gamma_true'], original_rho)
        axes[row, 2].plot(ratios, betas, color=blue, lw=1.15)
        axes[row, 2].axhline(obj['beta_true'], color=gray, lw=.7, ls='--')
        star(axes[row, 2], obj['gamma_hat']/obj['gamma_true'], obj['beta_hat'])
        axes[row, 0].set_title(obj['role']+f" · 第{obj['group']}组", loc='left', pad=14, fontsize=9)
        correlations[key] = dict(true=true_rho, original=original_rho,
                                 maximum_rho_squared_error=error, group=obj['group'])
        records += [dict(example=label, role=obj['role'], group=obj['group'],
                         gamma=float(g), gamma_ratio=float(ratio), rho=float(r), beta=float(b))
                    for g, ratio, r, b in zip(gs, ratios, rs, betas)]

    for index, ax in enumerate(axes.ravel()):
        ax.text(-.16, 1.04, chr(97+index), transform=ax.transAxes, fontweight='bold', fontsize=11)
    legend = [Line2D([0], [0], color=brown, marker='o', ms=3, ls='none', label='样本点'),
              Line2D([0], [0], color=brown, lw=1, label='拟合直线'),
              Line2D([0], [0], marker='*', color=brown, ls='none', ms=7, label='原估计')]
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.52, .015), ncol=3, fontsize=8)
    fig.subplots_adjust(left=.08, right=.985, bottom=.14, top=.91, wspace=.39, hspace=.48)
    fig.canvas.draw()
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(fig.canvas.get_renderer())
            assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.x1+1 and box.y1 <= fig.bbox.y1+1
    metadata = [{k: [float(value) for value in getattr(ax, 'get_'+k)()]
                 for k in ['xlim', 'ylim', 'xticks', 'yticks']} for ax in axes.ravel()]
    assert all(metadata[col] == metadata[col+3] for col in range(3))
    assert all(metadata[index] == old_axes[index] for index in [0, 2, 3, 5])
    path = IMAGES/f'配对情形_{label}.png'
    old_image = np.asarray(Image.open(path).convert('RGB'))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(path, dpi=400, facecolor='white')
    plt.close(fig)
    assert not any('Glyph' in str(w.message) for w in caught)
    image = np.asarray(Image.open(path).convert('RGB'))
    assert image.shape == old_image.shape == (2280, 3840, 3)
    # Fixed subplot positions let us compare the unaffected outer columns directly.
    assert np.array_equal(image[:, :1280], old_image[:, :1280])
    assert np.array_equal(image[:, 2630:], old_image[:, 2630:])
    return dict(path=str(path), sha256=digest(path), axes=metadata, panels=6,
                correlations=correlations, fit_points=visible_points,
                outer_columns_pixel_identical=True, all_labels_within_canvas=True), records


def revise_report(text, figures):
    heading = '#### 2.1.2　LRE'
    prefix, section = text.split(heading, 1)
    section, suffix = section.split('#### 2.1.3　MLE', 1)
    intro, rest = section.split('**图6｜LRE各类明显异常估计的发生次数。**', 1)
    _, cases = rest.split('\n\n**（1）零边界高估。**', 1)
    paragraphs = [
        ('第5组的最小观测与其余观测相隔较远。左移γ压缩下端对数间距，', '零位置处', 'LRE_zero'),
        ('W(2,100,500)、n=15的第36组，下端观测与其余点列间隔较大，', 'γ=85.73处', 'LRE_left'),
        ('W(2,1000,500)、n=7的第19组，上端观测远离其余点列，', 'γ=773.02处', 'LRE_right'),
    ]
    for start, position, label in paragraphs:
        values = figures[label]['correlations']['abnormal']
        true, selected = values['true'], values['original']
        if label == 'LRE_zero':
            new = start+f'相关系数ρ由真位置处的{true:.3f}升至{position}的{selected:.3f}；向右离开零边界，相关系数下降，LRE因此选择γ=0。'
        elif label == 'LRE_left':
            new = start+f'左移γ改善了概率图的线性相关性，ρ在{position}达到内部最大值。ρ由真位置处的{true:.3f}升至{selected:.3f}，在该点两侧均较低，因此位置搜索停在内部左侧。'
        else:
            new = start+f'真位置下的点列弯曲。右移γ拉开下端对数距离，ρ由{true:.3f}升至{position}的{selected:.3f}，在该点两侧再次下降，LRE据此选取右侧内部位置。'
        cases, count = re.subn(re.escape(start)+r'[^\n]*', lambda _: new, cases)
        assert count == 1
    revised = (prefix+heading+intro+'**图6｜LRE各类明显异常估计的发生次数。**\n\n'
               +PRINCIPLE+'\n\n**（1）零边界高估。**'+cases+'#### 2.1.3　MLE'+suffix)
    lre = revised.split(heading, 1)[1].split('#### 2.1.3', 1)[0]
    assert not any(term in lre for term in ['R²', 'R^2', 'arg\\min', '最低点'])
    return revised


def main():
    baseline_path = HERE/'20261010-LSE与LRE表述区分核验.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    pairs_path = HERE/'20261010-配对图参照线精简核验.json'
    previous = json.loads(pairs_path.read_text(encoding='utf-8'))
    plot_data_path = HERE/'20261010-参照线精简图数据.csv'
    style_path = HERE/'20261010-配对图参照线精简.py'
    sources = dict(baseline['source_sha256'])
    sources.update({str(p):digest(p) for p in
                    [baseline_path, pairs_path, plot_data_path, style_path, Path(__file__)]})
    assert all(digest(p) == value for p, value in sources.items())
    target_paths = {str(IMAGES/f'配对情形_{label}.png') for label in LABELS}
    protected = {p:value for p, value in baseline['protected_png_sha256'].items() if p not in target_paths}
    assert all(digest(p) == value for p, value in protected.items())
    with plot_data_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    style = load_style()
    before = REPORT.read_text(encoding='utf-8')
    figures, records = {}, []
    for label in LABELS:
        figure, data = render(label, previous['pairs'][label], rows, previous['figures'][label], style)
        figures[label] = figure
        records += data
    revised = revise_report(before, figures)
    assert before.split('#### 2.1.2', 1)[0] == revised.split('#### 2.1.2', 1)[0]
    assert before.split('#### 2.1.3', 1)[1] == revised.split('#### 2.1.3', 1)[1]
    tables = lambda text: re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*', text, flags=re.M)
    images = lambda text: re.findall(r'!\[[^\]]*\]\([^\n]*\)', text)
    assert tables(before) == tables(revised)
    assert images(before) == images(revised) and len(images(revised)) == 24
    assert re.findall(r'\*\*图(\d+)｜', revised) == list(map(str, range(1, 25)))
    assert all(digest(p) == value for p, value in sources.items())
    assert all(digest(p) == value for p, value in protected.items())
    REPORT.write_text(revised, encoding='utf-8')
    with DATA.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    result = dict(
        scope='Report2 LRE section and its three paired criterion figures only.',
        figure_contract=dict(conclusion='LRE selects the maximum of the original Pearson correlation.',
                             backend='Python', archetype='quantitative grid', export='Three PNGs, 400 dpi',
                             panels='Same six panels and original pairs; middle column now rho(gamma).',
                             criterion_limits=[.75, 1], criterion_ticks=[.75, .8, .85, .9, .95, 1]),
        source_sha256=sources, sources_unchanged=True, protected_png_sha256=protected,
        other_pngs_unchanged=True, sample_tables_and_estimates_unchanged=True,
        before_and_after_LRE_unchanged=True, all_24_image_refs_and_numbers_unchanged=True,
        figures=figures, pairs={label:previous['pairs'][label] for label in LABELS},
        baseline_png_sha256={p:baseline['protected_png_sha256'][p] for p in target_paths},
        curve_data_sha256=digest(DATA), report_sha256=digest(REPORT),
        no_resampling=True, no_estimator_runs=True, criterion_maximizer_preserved=True,
        visual_review='pending')
    if QA.exists():
        prior = json.loads(QA.read_text(encoding='utf-8'))
        if {k:f['sha256'] for k,f in prior['figures'].items()} == {k:f['sha256'] for k,f in figures.items()}:
            result['visual_review'] = prior.get('visual_review', 'pending')
    QA.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: three LRE rho(gamma) figures; identical outer panels, pairs and estimates; '
          'positive correlations independently agree with archived R2; other report sections and PNGs unchanged.')


if __name__ == '__main__':
    main()
