"""Expand report 2 distance notation without changing samples or plotted data.

revise removes d_i from the report; render redraws the eleven affected PNGs from
the saved data and active renderers. Formula numbers, estimates and counts stay
unchanged. This task's checks and script remain in the program directory.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, setup_runtime, matrix_path, write_atomic, save_png
setup_runtime()
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter

REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
QA = HERE / (Path(__file__).stem + '-核验.json')
DATA = RESULT / '报告2/数据'
IMAGES = RESULT / '报告2'
CHANGED = ['LSE_zero', 'LSE_right', 'LRE_zero', 'LRE_right', 'MLE_high', 'MLE_low', 'MLE_stop',
           'WMLE_low', 'WMLE_high', 'MMLE_low', 'MMLE_high_deletion']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def module(name):
    spec = importlib.util.spec_from_file_location('expanded_' + name, HERE / (name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def write_json(obj):
    write_atomic(QA, (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def protected():
    paths = list(DATA.glob('*'))
    paths += [p for p in IMAGES.glob('*.png') if p.stem.replace('配对情形_', '') not in CHANGED]
    for source in load(PROGRAM / '跨参数对比/13组合取数.json')['sources']:
        p = matrix_path(source)
        assert digest(p) == source['matrix_sha256']
        paths.append(p)
        paths += list((RESULT / source['program']).glob('*.xlsx'))
    return {str(p): digest(p) for p in paths if p.is_file()}


def revise():
    text = REPORT.read_text(encoding='utf-8')
    old = text
    if 'd_i' not in text and 'dᵢ' not in text and QA.exists() and 'text' in load(QA):
        print('Report already uses the explicit observation-location difference.')
        return
    before, mmle = text.split('#### 2.1.6', 1)
    before = before.replace('dᵢ/η₀', '(x₍ᵢ₎−γ̂)/η₀')
    before = before.replace('对实际观测x₍ᵢ₎，记距离dᵢ=x₍ᵢ₎−γ、对数距离yᵢ=ln dᵢ。',
                            '对实际观测x₍ᵢ₎，记对数距离yᵢ=ln(x₍ᵢ₎−γ)。')
    before = before.replace('ℓ为对数似然，dᵢ=x₍ᵢ₎−γ为样本距离。', 'ℓ为对数似然。')
    before = before.replace('yᵢ=ln dᵢ', 'yᵢ=ln(x₍ᵢ₎−γ)')
    before = before.replace('dᵢ=x₍ᵢ₎−γ为观测到候选位置的距离；', '')
    before = before.replace('；此处dᵢ=x₍ᵢ₎−γ̂', '')
    before = before.replace('d_i', '(x_{(i)}-\\gamma)')
    mmle = mmle.replace(r'\hat\gamma=x_{(1)},\qquad d_i=x_{(i)}-x_{(1)},\quad i=2,\ldots,n.',
                        r'\hat\gamma=x_{(1)}.')
    mmle = mmle.replace('这里的dᵢ为保留观测到样本最小值的距离。对式（25）的保留距离应用式（13）的形状得分关系，将样本均值改为n−1个保留观测的均值，得到：',
                        '将式（25）的位置代入式（13），删去最小观测，将均值改为n−1个保留观测的均值，得到：')
    mmle = mmle.replace('d_i', '(x_{(i)}-\\hat\\gamma)')
    final = before + '#### 2.1.6' + mmle
    assert 'd_i' not in final and 'dᵢ' not in final
    assert re.findall(r'\\tag\{(\d+)\}', final) == [str(i) for i in range(1, 31)]
    assert re.findall(r'^\|.*$', old, re.M) == re.findall(r'^\|.*$', final, re.M)
    assert re.findall(r'!\[[^\]]*\]\((.*?)\)', old) == re.findall(r'!\[[^\]]*\]\((.*?)\)', final)
    if final != old:
        write_atomic(REPORT, final.encode('utf-8'))
    record = load(QA) if QA.exists() else {}
    record['text'] = dict(before_sha256=hashlib.sha256(old.encode()).hexdigest(), after_sha256=digest(REPORT),
                          expanded_symbol='d_i', numbered_equations=30, sample_tables_unchanged=True,
                          before_math=re.findall(r'\$\$.*?\$\$', old, re.S),
                          after_math=re.findall(r'\$\$.*?\$\$', final, re.S))
    write_json(record)
    print('Expanded all distance symbols in the report; 30 formula numbers and all sample tables retained.')


def cached_pair(label, pairs, rows, meta, style):
    """Reconstruct four unchanged criterion/fit figures from saved plot nodes."""
    pair = pairs[label]
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    for i, ax in enumerate(axes.flat):
        ax.set(**meta['axes'][i])
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
        ax.text(-.16, 1.04, chr(97+i), transform=ax.transAxes, fontweight='bold', fontsize=11)
    def star(ax, x, y):
        ax.scatter([x], [y], marker='*', s=58, color=style.BROWN, edgecolors='white', lw=.5, zorder=6, clip_on=False)
    for row, role in enumerate(('normal', 'abnormal')):
        obj = pair[role]
        saved = [r for r in rows if r['example'] == label and r['role'] == obj['role']]
        arr = lambda series, key: np.array([float(r[key]) for r in series])
        axes[row, 0].set_title(obj['role'] + f" · 第{obj['group']}组", loc='left', pad=14, fontsize=9)
        if label == 'LSE_right':
            a, b, c = axes[row]
            a.set(xlabel=r'$z_i$', ylabel=r'$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$')
            fit = [r for r in saved if r['panel'] == 'fit_estimated']
            xx, yy, ff = [arr(fit, key) for key in ('horizontal', 'vertical', 'fitted')]
            assert np.allclose(yy, np.log((np.array(obj['values'])-obj['gamma_hat'])/obj['eta_true']), atol=1e-14)
            a.plot(xx, ff, color=style.BROWN, lw=1.1)
            a.scatter(xx, yy, s=17, color=style.BROWN, edgecolors='white', lw=.35, zorder=4)
            for i, (u, v) in enumerate(zip(xx, yy), 1):
                a.annotate(str(i), (u,v), xytext=(0, 6 if i%2 else -10), textcoords='offset points',
                           fontsize=6, ha='center', va='center', color='#515151')
            curve = [r for r in saved if r['panel'] == 'criterion']
            ratios, scores, betas = [arr(curve,k) for k in ('gamma_ratio','loss','beta')]
            b.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$1-R^2(\gamma)$')
            b.plot(ratios, scores, color=style.BLUE, lw=1.15)
            star(b, obj['gamma_hat']/obj['gamma_true'], obj['at_original']['relative_residual'])
            c.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\hat\beta(\gamma)$')
            c.plot(ratios, betas, color=style.BLUE, lw=1.15)
            c.axhline(obj['beta_true'], color=style.GRAY, lw=.7, ls='--')
            star(c, obj['gamma_hat']/obj['gamma_true'], obj['beta_hat'])
            for ax in (b,c):
                ax.axvline(1, color=style.GRAY, lw=.7, ls='--', zorder=0)
        else:
            a, b, c = axes[row]
            curve = [r for r in saved if r['panel'] == 'profile']
            ratios, scores, betas = [arr(curve,k) for k in ('gamma_ratio','ll_difference','beta')]
            a.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\ell_p(\gamma)-\ell_p(\gamma_0)$')
            a.plot(ratios, scores, color=style.BLUE, lw=1.15)
            a.axhline(0, color=style.GRAY, lw=.7, ls='--')
            star(a, obj['gamma_hat']/obj['gamma_true'], obj['at_original']['ll']-obj['at_true']['ll'])
            b.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\hat\beta(\gamma)$')
            b.plot(ratios, betas, color=style.BLUE, lw=1.15)
            b.axhline(obj['beta_true'], color=style.GRAY, lw=.7, ls='--')
            star(b, obj['gamma_hat']/obj['gamma_true'], obj['beta_hat'])
            for ax in (a,b):
                ax.axvline(1, color=style.GRAY, lw=.7, ls='--', zorder=0)
            c.set(xlabel=r'$i$', ylabel=r'$(x_{(i)}-\hat\gamma)/\eta_0$')
            pts = [r for r in saved if r['panel'] == 'distance_estimated']
            c.plot(arr(pts,'rank'), arr(pts,'distance_ratio'), color=style.BROWN, lw=1, marker='o', ms=3.5)
    estimate = Line2D([0],[0],marker='*',color=style.BROWN,ls='none',ms=7,label='原估计')
    legend = ([Line2D([0],[0],color=style.BROWN,marker='o',ms=3,ls='none',label='样本点'),
               Line2D([0],[0],color=style.BROWN,lw=1,label='拟合直线'),estimate] if label=='LSE_right' else
              [Line2D([0],[0],color=style.BROWN,marker='o',ms=3,lw=1,label='样本距离'),estimate])
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.52,.015), ncol=len(legend), fontsize=8)
    fig.subplots_adjust(left=.08,right=.985,bottom=.14,top=.91,wspace=.39,hspace=.48)
    actual = [dict(xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim()),xticks=ax.get_xticks().tolist(),yticks=ax.get_yticks().tolist()) for ax in axes.flat]
    assert actual == meta['axes']
    save_png(fig, IMAGES / ('配对情形_'+label+'.png'), dpi=400)
    plt.close(fig)


def render():
    saved = load(DATA / '20261010-配对图参照线精简核验.json')
    rows = list(csv.DictReader((DATA / '20261010-参照线精简图数据.csv').open(encoding='utf-8-sig')))
    before = protected()
    with matplotlib.rc_context():
        style = module('20261010-配对图参照线精简')
        for label in ('LSE_right','MLE_high','MLE_low','MLE_stop'):
            cached_pair(label,saved['pairs'],rows,saved['figures'][label],style)
        lre = module('20261010-LRE相关系数判据')
        lre.render('LRE_right',saved['pairs']['LRE_right'],rows,saved['figures']['LRE_right'],style,
                   check_outer_columns=False)
    with matplotlib.rc_context():
        merged = module('20261011-合并高估与MMLE实际流程')
        merged.style()
        source_rows=[]
        for method in ('LSE','LRE'):
            merged.regression_figure(method,saved['pairs'],rows,source_rows)
        for label in ('MMLE_low','MMLE_high_deletion'):
            merged.mmle_figure(label,saved['pairs'],source_rows)
    with matplotlib.rc_context():
        current = module('20261011-WMLE迭代残差与尺度方程')
        current.render()
    assert protected() == before
    record = load(QA) if QA.exists() else {}
    record.update(protected_sha256=before, script_sha256=digest(__file__),
                  figures={label:dict(path=str(IMAGES/('配对情形_'+label+'.png')),
                                     sha256=digest(IMAGES/('配对情形_'+label+'.png'))) for label in CHANGED},
                  estimates_recomputed=0, samples_generated=0, export='PNG only',
                  changed='Axis labels expand the distance notation; same saved nodes, ranges, ticks, samples and criteria.')
    write_json(record)
    print('Updated eleven PNG labels from unchanged stored plot data; matrices, workbooks and all other figures unchanged.')


def verify():
    record = load(QA)
    assert record['protected_sha256'] == protected()
    assert record['script_sha256'] == digest(__file__)
    text = REPORT.read_text(encoding='utf-8')
    assert 'd_i' not in text and 'dᵢ' not in text
    assert re.findall(r'\\tag\{(\d+)\}',text)==[str(i) for i in range(1,31)]
    before, after = record['text']['before_math'], re.findall(r'\$\$.*?\$\$', text, re.S)
    compact = lambda s: re.sub(r'\s+', '', s)
    for index, (original, expanded) in enumerate(zip(before, after), 1):
        if index == 25:
            assert compact(expanded) == compact('$$\\hat\\gamma=x_{(1)}.\\tag{25}$$')
        else:
            replacement = r'(x_{(i)}-\hat\gamma)' if index in (26,27) else r'(x_{(i)}-\gamma)'
            assert compact(original.replace('d_i',replacement)) == compact(expanded), index
    for item in record['figures'].values():
        assert digest(item['path'])==item['sha256']
    record['validation']=dict(status='passed', no_distance_alias=True, formula_numbers=30,
                              formula_substitution_equivalence=True,
                              figures=11, matrices_workbooks_saved_plot_nodes_unchanged=True)
    write_json(record)
    print('PASS: no d_i in report; thirty formula numbers and eleven PNG labels; original data and estimates retained.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='verify',choices=['revise','render','verify'])
    globals()[parser.parse_args().action]()
