"""Restore report2's MDM exposition to the paper, following report1.

Reuse the archived paired-figure nodes; change notation only in two PNGs.
Keep method implementations, observations, estimates and counts unchanged.
The original rank/forward-difference expressions describe the paper; the
archived curves retain their Bernard ranks and numerical differences.
"""
from pathlib import Path
import csv
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
from PIL import Image
from scipy.stats import beta as beta_distribution, f as f_distribution

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1]/'图片'
REPORT = ROOT/'报告2：小样本情况下的明显异常估计.md'
QA = Path(__file__).with_suffix('.json')
LABELS = ['MDM_low', 'MDM_edge']
PRINCIPLE = r'''MDM比较各观测反算的尺度参数，以这些伪尺度之间的差异估计参数。原文首先通过秩估计得到排序观测的累计概率：

$$
\hat F(x_{(i)})=
\frac{i}{i+(n+1-i)F_{2(n+1-i),\,2i,\,0.5}}.
$$

其中，x₍ᵢ₎为第i个排序观测，F̂(x₍ᵢ₎)为对应的累计概率估计，$F_{2(n+1-i),\,2i,\,0.5}$为自由度分别为2(n+1−i)和2i的F分布中位数。本批计算采用Bernard近似$\hat F(x_{(i)})\approx(i-0.3)/(n+0.4)$。

将累计概率代入原文的尺度参数伪估计量：

$$
\hat\eta_i(\gamma,\beta)=
\frac{x_{(i)}-\gamma}{[-\ln(1-\hat F(x_{(i)}))]^{1/\beta}}.
$$

其中，η̂ᵢ为第i个观测反算的伪尺度。固定γ，尝试不同β，以n个伪尺度的标准差$\sigma_\eta(\gamma,\beta)$衡量差异；取其中最小的标准差$\sigma_{\eta,\min}(\gamma)$，同时保留对应的β。

原文以条件最小标准差对γ的差分梯度确定位置：

$$
\nabla(\gamma)=
\frac{\sigma_{\eta,\min}(\gamma+\Delta\gamma)
-\sigma_{\eta,\min}(\gamma)}{\Delta\gamma}.
$$

其中，∇(γ)为条件最小标准差的梯度，Δγ为位置参数的差分步长。用正补偿值δ代替零梯度判据，以∇(γ̂)=δ确定位置；β̂取该位置对应的形状参数，最终尺度取伪尺度均值：

$$
\hat\eta=\frac1n\sum_{i=1}^n
\frac{x_{(i)}-\hat\gamma}{[-\ln(1-\hat F(x_{(i)}))]^{1/\hat\beta}}.
$$

其中，β̂、η̂、γ̂分别为形状、尺度和位置估计。本节取δ=0.20，图15、16沿用存档程序的数值差分梯度。'''


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load(HERE/'20261010-六方法公式实现核对.py', 'mdm_original_audit')
digest = audit.digest
style = load(HERE/'20261010-配对图参照线精简.py', 'mdm_original_style')


def render(label, pair, rows, old):
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    blue, brown, gray = style.BLUE, style.BROWN, style.GRAY
    for ax, meta in zip(axes.ravel(), old['axes']):
        ax.set(xlim=meta['xlim'], xticks=meta['xticks'], ylim=meta['ylim'], yticks=meta['yticks'])
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    for ax in axes[:, 0]:
        ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\nabla(\gamma)$')
        ax.axvline(1, color=gray, lw=.7, ls='--', zorder=0)
    for ax in axes[:, 1]:
        ax.set(xlabel=r'$\beta$', ylabel=r'$\sigma_\eta(\hat\gamma,\beta)/\eta_0$')
    for ax in axes[:, 2]:
        ax.set(xlabel=r'$i$', ylabel=r'$\hat\eta_i/\eta_0$')

    def star(ax, xx, yy):
        ax.scatter([xx], [yy], marker='*', s=58, color=brown, edgecolors='white', lw=.5, zorder=6, clip_on=False)

    for row, role in enumerate(['normal', 'abnormal']):
        obj = pair[role]
        nodes = [r for r in rows if r['example']==label and r['role']==obj['role']]
        panel = lambda name: [r for r in nodes if r['panel']==name]
        column = lambda items, name: [float(r[name]) for r in items]
        curve = panel('gradient')
        assert curve
        ax = axes[row, 0]
        ax.plot(column(curve,'gamma_ratio'),column(curve,'gradient'),color=blue,lw=1.15)
        ax.axhline(.2,color=gray,lw=.7,ls=':')
        if obj['root_solver']=='right_edge_fit':
            roots = obj['gradient_roots']
            probes = panel('right_anchor')
            assert len(roots)==2 and len(probes)==24
            ax.axvline(obj['gamma_hat']/obj['gamma_true'],color=brown,lw=1.1)
            ax.scatter(np.asarray(roots)/obj['gamma_true'],[.2]*len(roots),facecolors='white',edgecolors=blue,s=25,lw=.9,zorder=5)
            ax.scatter(column(probes,'gamma_ratio'),column(probes,'gradient'),s=7,color='#444444',zorder=4)
        else:
            root = next(r for r in curve if float(r['gamma'])==obj['gamma_hat'])
            star(ax,obj['gamma_hat']/obj['gamma_true'],float(root['gradient']))
        curve = panel('conditional_sigma')
        assert curve
        axes[row,1].plot(column(curve,'beta'),column(curve,'sigma_ratio'),color=blue,lw=1.15)
        axes[row,1].axvline(obj['beta_true'],color=gray,lw=.7,ls='--')
        star(axes[row,1],obj['beta_hat'],obj['at_original']['sigma']/obj['eta_true'])
        for stage,color in [('true_beta',gray),('estimated_beta',brown)]:
            points=panel('pseudo_scale_'+stage)
            assert len(points)==obj['n']
            axes[row,2].plot(column(points,'rank'),column(points,'scale_ratio'),color=color,lw=1,marker='o',ms=3.8)
        axes[row,0].set_title(obj['role']+f" · 第{obj['group']}组",loc='left',pad=14,fontsize=9)
    for i,ax in enumerate(axes.ravel()):
        ax.text(-.16,1.04,chr(97+i),transform=ax.transAxes,fontweight='bold',fontsize=11)
    legend=[Line2D([0],[0],color=gray,marker='o',ms=3,lw=1,label='真β的伪尺度'),
            Line2D([0],[0],color=brown,marker='o',ms=3,lw=1,label='估计β的伪尺度'),
            Line2D([0],[0],marker='*',color=brown,ls='none',ms=7,label='原估计')]
    if label=='MDM_edge':
        legend += [Line2D([0],[0],marker='o',mfc='white',mec=blue,ls='none',ms=4,label='梯度交点'),
                   Line2D([0],[0],marker='o',color='#444444',ls='none',ms=3,label='右端探测')]
    fig.legend(handles=legend,loc='lower center',bbox_to_anchor=(.52,.015),ncol=len(legend),fontsize=8)
    fig.subplots_adjust(left=.08,right=.985,bottom=.14,top=.91,wspace=.39,hspace=.48)
    fig.canvas.draw()
    for item in fig.findobj(matplotlib.text.Text):
        if item.get_visible() and item.get_text():
            box=item.get_window_extent(fig.canvas.get_renderer())
            assert box.x0>=-1 and box.y0>=-1 and box.x1<=fig.bbox.x1+1 and box.y1<=fig.bbox.y1+1
    metadata=[{k:list(map(float,getattr(ax,'get_'+k)())) for k in ['xlim','ylim','xticks','yticks']} for ax in axes.ravel()]
    assert metadata==old['axes']
    target=IMAGES/f'配对情形_{label}.png'
    before=np.asarray(Image.open(target).convert('RGB'))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(target,dpi=400,facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught)
    after=np.asarray(Image.open(target).convert('RGB'))
    assert before.shape==after.shape==(2280,3840,3)
    # All six plotting rectangles retain exactly the same pixels; only the
    # mathematical axis-label strings outside those rectangles are revised.
    scale=400/fig.dpi
    for ax in axes.ravel():
        box=ax.bbox;h=after.shape[0]
        left,right=int(np.ceil(box.x0*scale))+1,int(np.floor(box.x1*scale))-1
        top,bottom=h-int(np.floor(box.y1*scale))+1,h-int(np.ceil(box.y0*scale))-1
        assert np.array_equal(before[top:bottom,left:right],after[top:bottom,left:right]),label
    plt.close(fig)
    return dict(path=str(target),sha256=digest(target),axes=metadata,panels=6,
                plotted_regions_pixel_identical=True,all_labels_within_canvas=True)


def main():
    pairs_path=HERE/'20261010-配对图参照线精简核验.json'
    curve_path=HERE/'20261010-参照线精简图数据.csv'
    catalog_path=ROOT/'跨组合汇总/程序/20261007-新增五组合/13组合取数.json'
    pair_data=json.loads(pairs_path.read_text(encoding='utf-8'))
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))['sources']
    with curve_path.open(encoding='utf-8-sig',newline='') as handle:
        rows=list(csv.DictReader(handle))
    report1=ROOT/'报告1：高形状参数下的估计偏移.md'
    paper=ROOT.parents[1]/'src/content/182-046-pdf原文.md'
    sources={str(p):digest(p) for p in [pairs_path,curve_path,catalog_path,report1,paper,Path(__file__),
             HERE/'20261010-六方法公式实现核对.py',HERE/'20261010-六方法公式实现核验.json',
             HERE/'20261010-六方法公式实现逐项.csv',HERE/'20261010-配对图参照线精简.py']}
    protected_pngs={str(p):digest(p) for p in IMAGES.glob('*.png') if p.stem not in ['配对情形_'+label for label in LABELS]}
    before=REPORT.read_text(encoding='utf-8')
    before_section=before.split('#### 2.1.4　MDM',1)[1].split('#### 2.1.5　WMLE',1)[0]
    revision_previous=json.loads(QA.read_text(encoding='utf-8')) if QA.exists() else {}
    checks=[]
    for label in LABELS:
        for role in ['normal','abnormal']:
            obj=pair_data['pairs'][label][role]
            entry=next(e for e in catalog if e['combination']==obj['combination'])
            base=Path(entry['program']);base=base if base.name=='程序' else base.parent
            path=base/'依赖快照/python/methods/mdm.py'
            sources[str(path)]=digest(path)
            x=np.asarray(obj['values']);n=len(x)
            env=dict(np=np,t=x,n=n,t_min=x[0],offset=.2,minimize_scalar=audit.minimize_scalar,
                     neg_ln_1_minus_F=-np.log(1-(np.arange(1,n+1)-.3)/(n+.4)),
                     beta_sigma_cache={},profile_gradient_cache={})
            audit.bind(path,['calculate_eta_std','find_best_beta_for_gamma','profile_sigma','profile_gradient'],env)
            for r in rows:
                if r['example']==label and r['role']==obj['role'] and r['panel'] in ['gradient','right_anchor']:
                    observed=env['profile_gradient'](float(r['gamma']));expected=float(r['gradient'])
                    error=abs(observed-expected);limit=(8e-5 if r['panel']=='right_anchor' else 2e-7)*(1+abs(expected))
                    assert error<=limit
                    checks.append(dict(example=label,role=role,panel=r['panel'],gamma=float(r['gamma']),absolute_error=error))
    ranks={}
    for n in [7,15,30]:
        i=np.arange(1,n+1)
        p=i/(i+(n+1-i)*f_distribution.ppf(.5,2*(n+1-i),2*i))
        error=float(np.max(np.abs(p-beta_distribution.ppf(.5,i,n+1-i))))
        assert error<1e-13
        ranks[n]=dict(exact_median_ranks=p.tolist(),max_beta_median_error=error)
    marker='**图14｜MDM（δ=0.20）各类明显异常估计的发生次数。**'
    prefix,rest=before_section.split(marker,1)
    _,cases=rest.split('**（1）阈值交点的低估。**',1)
    revised_section=prefix+marker+'\n\n'+PRINCIPLE+'\n\n**（1）阈值交点的低估。**'+cases
    revised=before.replace(before_section,revised_section,1)
    assert before.replace(before_section,'')==revised.replace(revised_section,'')
    tables=lambda text:re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*',text,flags=re.M)
    assert tables(before)==tables(revised)
    assert re.findall(r'!\[[^\]]*\]\([^\n]*\)',before)==re.findall(r'!\[[^\]]*\]\([^\n]*\)',revised)
    assert all(token not in PRINCIPLE for token in ['arg\\min','g(\\gamma)','\\frac{d','协方差'])
    assert all(token in report1.read_text(encoding='utf-8') for token in ['\\nabla(\\gamma)','\\sigma_{\\eta,\\min}','F_{2(n+1-i)'])
    figures={label:render(label,pair_data['pairs'][label],rows,pair_data['figures'][label]) for label in LABELS}
    assert all(digest(p)==h for p,h in sources.items())
    assert all(digest(p)==h for p,h in protected_pngs.items())
    REPORT.write_text(revised,encoding='utf-8',newline='\n')
    result=dict(scope='Report2 MDM principle and notation in figures15/16; following report1 and original paper equations3/4/6/7.',
                source_sha256=sources,sources_unchanged=True,protected_png_sha256=protected_pngs,
                protected_pngs_unchanged=True,figures=figures,
                original_median_rank_checks=ranks,frozen_gradient_checks=checks,
                frozen_gradient_check_count=len(checks),
                figure_contract=dict(conclusion='Conditional minimum standard deviation gradient determines the offset crossing; the fallback case follows the archived branch.',
                                     backend='Python',archetype='quantitative grid',export='Two PNGs; 400dpi',
                                     labels_only=True,axes_and_all_plotted_regions_unchanged=True),
                terminology=dict(pseudo_scale='eta_hat_i',standard_deviation='sigma_eta',conditional_minimum='sigma_eta_min',gradient='nabla(gamma)',compensation=.2),
                implementation_disclosure='The paper uses exact median ranks, discrete searches and forward differences. Archived calculations retain Bernard ranks, continuous shape optimization, central/one-sided differences and endpoint fallback.',
                visual_review='2026-10-10: Both exported PNGs inspected across all six panels; short labels, shared axes per quantity and unchanged curves/markers confirmed.',
                original_method_intro_before=revision_previous.get('original_method_intro_before',rest.split('**（1）阈值交点的低估。**',1)[0]),
                report_sha256=digest(REPORT),other_sections_and_all_case_analysis_unchanged=True,
                observations_estimates_statuses_and_counts_unchanged=True,no_new_samples=True,no_new_estimates=True)
    QA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS: original equations3/4/6/7; '+str(len(checks))+' frozen gradient nodes; two PNGs relabelled; all plotted rectangles unchanged.')


if __name__=='__main__':
    main()
