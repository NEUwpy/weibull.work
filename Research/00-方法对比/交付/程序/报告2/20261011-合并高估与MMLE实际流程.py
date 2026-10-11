"""Report2: merge regression high estimates and compare actual MMLE samples.

Reads archived samples, selected fits and diagnostic nodes. No sampling or
estimator replacement. PNGs go to results; source data and checks stay here.
"""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, setup_runtime, save_png, write_atomic
setup_runtime()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter
import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
DATA = RESULT / '报告2/数据'
IMAGES = RESULT / '报告2'
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
STEM = Path(__file__).stem
QA_PATH = HERE / (STEM + '.json')
CURVES_PATH = HERE / (STEM + '.csv')
BLUE, BROWN, PURPLE, GRAY = '#487A8B', '#B67550', '#80749A', '#999999'
MODIFIED = ['配对情形_LSE_zero.png', '配对情形_LRE_zero.png',
            '配对情形_MMLE_low.png', '配对情形_MMLE_high_deletion.png',
            '异常分类_LSE_三子图.png', '异常分类_LRE_三子图.png', '异常分类_MMLE_三子图.png']
OBSOLETE = ['配对情形_LSE_left.png', '配对情形_LRE_left.png',
            '配对情形_MMLE_high_concentrated.png']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def inputs():
    pairs = load(DATA / '20261010-配对图参照线精简核验.json')['pairs']
    with (DATA / '20261010-参照线精简图数据.csv').open(encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    return pairs, rows


def style():
    plt.rcParams.update({'font.family': 'sans-serif',
                        'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                        'font.size': 8.5, 'axes.linewidth': .65,
                        'axes.spines.top': False, 'axes.spines.right': False,
                        'legend.frameon': False, 'axes.unicode_minus': False})


def star(ax, x, y, color):
    ax.scatter([x], [y], marker='*', s=48, color=color, edgecolors='white',
               linewidths=.5, zorder=6, clip_on=False)


def finish(fig, axes, filename, legend):
    for i, ax in enumerate(axes.ravel()):
        ax.text(-.14, 1.035, chr(97+i), transform=ax.transAxes,
                fontsize=11, fontweight='bold')
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
        ax.yaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.53, .01),
               ncol=len(legend), fontsize=8)
    fig.subplots_adjust(left=.085, right=.985, bottom=.15, top=.91,
                        wspace=.43, hspace=.52)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = fig.bbox
    for item in fig.findobj(matplotlib.text.Text):
        if not item.get_visible() or not item.get_text():
            continue
        b = item.get_window_extent(renderer)
        assert b.x0 >= box.x0-2 and b.x1 <= box.x1+2 and b.y0 >= box.y0-2 and b.y1 <= box.y1+2, item.get_text()
    save_png(fig, IMAGES / filename, dpi=400)
    meta = [dict(xlim=list(ax.get_xlim()), ylim=list(ax.get_ylim()),
                 xticks=ax.get_xticks().tolist(), yticks=ax.get_yticks().tolist())
            for ax in axes.ravel()]
    plt.close(fig)
    return dict(path=filename, sha256=digest(IMAGES/filename), axes=meta,
                panels=6, labels_inside_canvas=True)


def regression_figure(method, pairs, rows, source_rows):
    labels = [method+'_zero', method+'_left']
    selected = [(labels[0], pairs[labels[0]]['normal'], BLUE, '正常'),
                (labels[0], pairs[labels[0]]['abnormal'], BROWN, '零边界'),
                (labels[1], pairs[labels[1]]['abnormal'], PURPLE, '内部左侧')]
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    reverse = method == 'LRE'
    xmax = np.ceil(max(o['values'][0]/o['gamma_true'] for _, o, _, _ in selected)*10)/10
    xticks = np.arange(0, xmax+.001, .25)
    bmax = max(25, np.ceil(max(o['beta_hat'] for _, o, _, _ in selected)/5)*5)
    for ax in axes[:, 0]:
        ax.set(xlim=(-.5, 2) if reverse else (-3.6, 1.3),
               xticks=[-.5,0,.5,1,1.5,2] if reverse else [-3,-2,-1,0,1],
               ylim=(-4.2, 1.5) if reverse else (-6, 2),
               yticks=[-4,-3,-2,-1,0,1] if reverse else [-6,-4,-2,0,2],
               xlabel=r'$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$' if reverse else r'$z_i$',
               ylabel=r'$z_i$' if reverse else r'$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$')
    for ax in axes[:, 1]:
        ax.set(xlim=(0, xmax), xticks=xticks, xlabel=r'$\gamma/\gamma_0$',
               ylim=(.88,1) if reverse else (0,.12),
               yticks=[.88,.91,.94,.97,1] if reverse else [0,.03,.06,.09,.12],
               ylabel=r'$\rho(\gamma)$' if reverse else r'$1-R^2(\gamma)$')
    for ax in axes[:, 2]:
        ax.set(xlim=(0, xmax), xticks=xticks, xlabel=r'$\gamma/\gamma_0$',
               ylim=(0,bmax), yticks=np.arange(0,bmax+.001,5), ylabel=r'$\hat\beta(\gamma)$')
        ax.axhline(selected[0][1]['beta_true'], color=GRAY, lw=.7, ls='--')
    for ax in axes[:, 1:].ravel():
        ax.axvline(1, color=GRAY, lw=.7, ls='--', zorder=0)
    verified = []
    normal_curves = None
    for index, (label, obj, color, kind) in enumerate(selected):
        row = 0 if index == 0 else 1
        saved = [r for r in rows if r['example']==label and r['role']==obj['role']]
        fit = [r for r in saved if r['panel']=='fit_estimated']
        curve = [r for r in saved if r['panel']=='criterion']
        array = lambda records, key: np.array([float(r[key]) for r in records])
        xx, yy, fitted = [array(fit,k) for k in ['horizontal','vertical','fitted']]
        assert len(xx)==obj['n']
        distances = np.array(obj['values'])-obj['gamma_hat']
        logged = np.log(distances/obj['eta_true'])
        assert np.allclose(xx if reverse else yy, logged, atol=1e-13)
        slope = np.polyfit(xx, yy, 1)[0]
        beta = slope if reverse else 1/slope
        assert np.isclose(beta, obj['beta_hat'], rtol=2e-5)
        assert np.allclose(fitted, yy.mean()+slope*(xx-xx.mean()), atol=1e-12)
        axes[row,0].plot(xx, fitted, color=color, lw=1.1)
        axes[row,0].scatter(xx, yy, s=16, color=color, edgecolors='white', lw=.35, zorder=4)
        for rank, (x,y) in enumerate(zip(xx,yy),1):
            offset = ((8 if rank%2 else -8), 0) if reverse else (0,6 if rank%2 else -10)
            axes[row,0].annotate(str(rank), (x,y), xytext=offset, textcoords='offset points',
                                 fontsize=5.8, color=color, ha=('left' if rank%2 else 'right') if reverse else 'center')
        gs, ratios, losses, betas = [array(curve,k) for k in ['gamma','gamma_ratio','loss','beta']]
        reference = yy if reverse else xx
        metrics = np.array([np.corrcoef(np.log(np.array(obj['values'])-g),reference)[0,1]
                            for g in gs])
        assert np.max(np.abs(metrics**2-(1-losses))) < 3e-13
        criterion = metrics if reverse else losses
        axes[row,1].plot(ratios,criterion,color=color,lw=1.2)
        axes[row,2].plot(ratios,betas,color=color,lw=1.2)
        selected_score = np.sqrt(obj['at_original']['r2']) if reverse else obj['at_original']['relative_residual']
        star(axes[row,1],obj['gamma_hat']/obj['gamma_true'],selected_score,color)
        star(axes[row,2],obj['gamma_hat']/obj['gamma_true'],obj['beta_hat'],color)
        if index==0:
            normal_curves = (ratios,criterion,betas)
        for rank, (x,y,f) in enumerate(zip(xx,yy,fitted),1):
            source_rows.append(dict(figure=method+'_high',sample=kind,combination=obj['combination'],
                                    n=obj['n'],group=obj['group'],panel='fit',rank=rank,
                                    horizontal=x,vertical=y,fitted=f))
        for g,r,c,b in zip(gs,ratios,criterion,betas):
            source_rows.append(dict(figure=method+'_high',sample=kind,combination=obj['combination'],
                                    n=obj['n'],group=obj['group'],panel='criterion',gamma=g,
                                    gamma_ratio=r,criterion=c,beta=b))
        verified.append(dict(kind=kind,combination=obj['combination'],n=obj['n'],group=obj['group'],
                             beta=obj['beta_hat'],gamma=obj['gamma_hat'],fit_points=len(xx),
                             fitted_beta=beta,criterion=selected_score))
    r,c,b = normal_curves
    axes[1,1].plot(r,c,color=BLUE,lw=.85,ls='--',zorder=0)
    axes[1,2].plot(r,b,color=BLUE,lw=.85,ls='--',zorder=0)
    axes[0,0].set_title('正常样本', loc='left', pad=13, fontsize=9)
    axes[1,0].set_title('两组异常样本', loc='left', pad=13, fontsize=9)
    legend = [Line2D([0],[0],color=color,marker='o',ms=3,lw=1,
                      label=f'{kind}·第{obj["group"]}组') for _,obj,color,kind in selected]
    legend.append(Line2D([0],[0],color='#555555',marker='*',ls='none',ms=7,label='原估计'))
    meta = finish(fig, axes, '配对情形_'+method+'_zero.png', legend)
    meta.update(samples=verified,criterion='rho' if reverse else '1-R2',
                conclusion='Two abnormal samples share left-location compression and shape overestimation.')
    return meta


def mmle_score(distances, beta):
    logs=np.log(distances)
    centered=logs-logs.mean()
    weights=np.exp(beta*centered-np.max(beta*centered))
    weights/=weights.sum()
    return float(1/beta-np.sum(weights*centered))


def mmle_figure(label, pairs, source_rows):
    # 当前MMLE图按三个参数的实际确定顺序绘制，共用本次独立入口。
    spec = importlib.util.spec_from_file_location('r2_mmle_process', HERE / '20261011-MMLE三参数流程图.py')
    current = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(current)
    return current.render_pair(label, pairs, source_rows)


def merged_counts():
    original=list(csv.DictReader((DATA/'20261010-各类异常参数空间.csv').open(encoding='utf-8-sig')))
    merged=collections.Counter()
    for r in original:
        case=r['case']
        if r['method'] in ['LSE','LRE'] and case in ['zero_high','interior_left_high']:
            case='left_high'
        if r['method']=='MMLE' and case in ['deletion_concentrated_high','complete_concentrated_high']:
            case='retained_high'
        merged[r['method'],case,r['combination'],int(r['n'])]+=int(r['count'])
    assert len(merged)==507 and sum(merged.values())==963
    flow=list(csv.DictReader((DATA/'全量流程定位.csv').open(encoding='utf-8-sig')))
    direct=collections.Counter((r['method'],r['combination'],int(r['n'])) for r in flow if r['abnormal']=='True')
    for key,count in direct.items():
        assert count==sum(v for (method,case,combo,n),v in merged.items() if (method,combo,n)==key)
    return merged


def render():
    style()
    pairs,rows=inputs()
    protected_paths=[DATA/'20261010-配对图参照线精简核验.json',
                     DATA/'20261010-参照线精简图数据.csv',DATA/'全量流程定位.csv',
                     DATA/'20261010-各类异常参数空间.csv',IMAGES/'图1_明显异常估计频率.png']
    for s in load(PROGRAM/'跨参数对比/13组合取数.json')['sources']:
        p=matrix_path(s);assert digest(p)==s['matrix_sha256'];protected_paths.append(p)
        protected_paths.extend((RESULT/s['program']).glob('*.xlsx'))
    protected={str(p):digest(p) for p in protected_paths}
    source_rows=[]
    figures={method:regression_figure(method,pairs,rows,source_rows) for method in ['LSE','LRE']}
    for label in ['MMLE_low','MMLE_high_deletion']:
        figures[label]=mmle_figure(label,pairs,source_rows)
    count=merged_counts()
    qa=load(DATA/'20261010-异常分类三档热力表核验.json')
    spec=importlib.util.spec_from_file_location('r2_merged_heatmaps',HERE/'20261010-逐方法异常分类三子图.py')
    heatmaps=importlib.util.module_from_spec(spec);spec.loader.exec_module(heatmaps)
    summaries={}
    for method in ['LSE','LRE','MMLE']:
        cases=([dict(case='left_high',label='左侧定位高估'),dict(case='interior_right_low',label='右侧定位低估')]
               if method!='MMLE' else [dict(case='minimum_shift_low',label='保留距离分散低估'),
                                       dict(case='retained_high',label='保留距离集中高估')])
        matrices={str(n):np.array([[count[method,c['case'],combo,n] for c in cases]
                                   for combo in qa['column_order']]) for n in [7,15,30]}
        summaries[method]=heatmaps.render(method,matrices,cases,qa['column_order'])
    fields=list(dict.fromkeys(k for row in source_rows for k in row))
    from io import StringIO
    buffer=StringIO();writer=csv.DictWriter(buffer,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows(source_rows)
    write_atomic(CURVES_PATH,buffer.getvalue().encode('utf-8-sig'))
    assert protected=={p:digest(p) for p in protected}
    for name in OBSOLETE:
        path=(IMAGES/name).resolve()
        assert path.parent==IMAGES.resolve() and path.suffix=='.png'
        if path.exists():path.unlink()
    record=dict(backend='Python/matplotlib',export='PNG',
                source_sha256=protected,original_estimates_and_frequencies_unchanged=True,
                figures=figures,heatmaps=summaries,
                merged_cell_count=len(count),abnormal_total=sum(count.values()),
                merged_counts=[dict(method=m,case=c,combination=w,n=n,count=v)
                               for (m,c,w,n),v in count.items()],
                source_data=CURVES_PATH.name,source_data_sha256=digest(CURVES_PATH),
                retired_result_figures=OBSOLETE,script_sha256=digest(__file__),
                figure_contract=dict(regression='Left-location compression explains both boundary and interior high estimates.',
                                     mmle='Compare actual retained samples: dispersion lowers shape; concentration raises it.',
                                     grid='2x3; matching limits and ticks in each column; no explanatory boxes.'))
    write_atomic(QA_PATH,(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
    print('Generated 7 PNGs; merged 507 count cells retain all 963 abnormal estimates.')


def verify():
    qa=load(QA_PATH)
    assert qa['abnormal_total']==963 and qa['merged_cell_count']==507
    assert qa['source_data_sha256']==digest(CURVES_PATH)
    for path,sha in qa['source_sha256'].items():assert digest(path)==sha,path
    for meta in [*qa['figures'].values(),*qa['heatmaps'].values()]:
        path=IMAGES/Path(meta['path']).name
        assert path.exists() and digest(path)==meta['sha256'],path
    for meta in qa['figures'].values():
        for column in range(3):assert meta['axes'][column]==meta['axes'][column+3]
    assert sum(merged_counts().values())==963
    text=REPORT.read_text(encoding='utf-8')
    links=re.findall(r'!\[[^\]]*\]\((.*?)\)',text)
    assert len(links)==21
    for link in links:assert (REPORT.parent/link).exists(),link
    for filename in OBSOLETE:assert filename not in text and not (IMAGES/filename).exists()
    assert len(re.findall(r'^\*\*图\d+｜',text,re.M))==21
    print('Verified original matrices/workbooks/counts, plot nodes, MMLE roots, axes and 21 report figures.')


def sample_table(samples, conditions=False):
    head=('| 样本 | 参数组合 | n | 形状β̂ | 尺度η̂ | 位置γ̂ | 观测值（升序） |\n'
          '| --- | --- | ---: | ---: | ---: | ---: | --- |\n' if conditions else
          '| 样本 | 形状β̂ | 尺度η̂ | 位置γ̂ | 观测值（升序） |\n'
          '| --- | ---: | ---: | ---: | --- |\n')
    for name,obj in samples:
        condition=f' {obj["combination"]} | {obj["n"]} |' if conditions else ''
        values='，'.join(f'{x:.2f}' for x in obj['values'])
        head+=f'| {name}·第{obj["group"]}组 |{condition} {obj["beta_hat"]:.2f} | {obj["eta_hat"]:.2f} | {obj["gamma_hat"]:.2f} | {values} |\n'
    return head


def revise():
    pairs,_=inputs()
    text=REPORT.read_text(encoding='utf-8')
    if '正常样本与两种左侧高估样本如下：' in text:
        assert '图19、20对照正常与异常样本的实际保留距离' in text
        print('Narrative already uses merged classes and actual MMLE comparisons.')
        return
    original=text
    lse_table=sample_table([('正常',pairs['LSE_zero']['normal']),
                            ('零边界高估',pairs['LSE_zero']['abnormal']),
                            ('内部左侧高估',pairs['LSE_left']['abnormal'])],conditions=True)
    lre_table=sample_table([('正常',pairs['LRE_zero']['normal']),
                            ('零边界高估',pairs['LRE_zero']['abnormal']),
                            ('内部左侧高估',pairs['LRE_left']['abnormal'])],conditions=True)
    lse_high='''**（1）左侧定位导致的形状高估。**

正常样本与两种左侧高估样本如下：

'''+lse_table+'''
图3将零边界与内部左侧两条异常曲线放在一起，对照正常样本的位置判据与拟合斜率。

![LSE正常样本与两种左侧高估样本](交付/结果/报告2/配对情形_LSE_zero.png)

**图3｜两个异常样本均在左侧取得较好的线性匹配，同时得到较小斜率与形状高估。**

第35组的最低点位于真位置附近，斜率对应正常形状。两个异常样本在真位置下的下端间距与参考点匹配较差，左移γ压缩下端间距，使点列更接近直线。第36组的最低点落在γ=0；第1组继续左移后准则回升，最低点留在内部γ=1273.68。

改善拟合同时也压缩了整体对数跨度。第36组的跨度由1.74缩至0.20，斜率降至0.046，β升至21.70；第1组的斜率降至0.119，β升至8.42。两者都经较小斜率的倒数形成高估，区别在于最佳位置是否落在零边界。

'''
    lre_high='''**（1）左侧定位导致的形状高估。**

正常样本与两种左侧高估样本如下：

'''+lre_table+'''
图7比较两个异常样本的相关性最高点及其对应拟合线。

![LRE正常样本与两种左侧高估样本](交付/结果/报告2/配对情形_LRE_zero.png)

**图7｜两个异常样本均通过左移提高概率图相关性，压缩的横向跨度使斜率和形状增大。**

第4组的相关性最高点位于内部，所选点列保留较大的横向跨度。第5组的最小观测较孤立，后续观测集中；第36组的下端间距较大。左移γ压缩下端对数间距，改善与概率图参考点的匹配，第5组在γ=0达到最高相关性，第36组在内部γ=85.73达到最高相关性。

LRE的纵向参考坐标固定。第5组左移后的对数跨度缩至0.21，第36组由1.74缩至0.23；横向跨度变窄使拟合线变陡，斜率分别达到13.78、18.80，直接得到形状高估。

'''
    for start,end,new in [(text.index('**（1）零边界高估。**',text.index('#### 2.1.1')),
                            text.index('**（3）内部右侧低估。**',text.index('#### 2.1.1')),lse_high),
                           (text.index('**（1）零边界高估。**',text.index('#### 2.1.2')),
                            text.index('**（3）内部右侧低估。**',text.index('#### 2.1.2')),lre_high)][::-1]:
        text=text[:start]+new+text[end:]
    text=text.replace('明显异常分为零边界高估、内部左侧高估和内部右侧低估。',
                      '明显异常分为左侧定位高估和右侧定位低估。')
    text=text.replace('**（3）内部右侧低估。**','**（2）右侧定位导致的形状低估。**')
    marker='#### 2.1.2'
    start=text.index(marker)
    text=text[:start].rstrip()+'''\n\nLSE中，位置左移可通过压缩对数跨度、减小斜率造成β高估；位置右移可通过拉开对数跨度、增大斜率造成β低估。\n\n'''+text[start:]
    start=text.index('#### 2.1.3')
    text=text[:start].rstrip()+'''\n\nLRE中，位置左移压缩概率图的横向跨度，增大斜率并造成β高估；位置右移拉开横向跨度，减小斜率并造成β低估。\n\n'''+text[start:]
    low_table=sample_table([('正常',pairs['MMLE_low']['normal']),('异常',pairs['MMLE_low']['abnormal'])])
    high_table=sample_table([('正常',pairs['MMLE_high_deletion']['normal']),('异常',pairs['MMLE_high_deletion']['abnormal'])])
    mmle='''Uβ为形状得分。方程要求1/β等于保留对数距离的加权均值与普通均值之差。距离更集中时，这个差较小，根对应较大β；距离更分散时，根可移向较小β。图21、22对照正常与异常样本的实际保留距离及形状得分曲线，曲线与零线的交点对应β̂。

![MMLE各类明显异常估计的发生次数](交付/结果/报告2/异常分类_MMLE_三子图.png)

**图20｜MMLE保留距离分散与集中的两类明显异常估计。**

**（1）保留距离分散导致的形状低估。**

W(5,100,500)、n=7的正常与异常样本如下：

'''+low_table+'''
![MMLE正常与低估样本的实际保留距离和形状得分](交付/结果/报告2/配对情形_MMLE_low.png)

**图21｜第11组的保留距离相对分散，形状得分的零点落在低估范围。**

第11组以575.95为位置后，前三个保留距离约为9.34、9.87、10.09，后续距离增至30.46—53.94，下端形成一簇较小距离。其对数跨度为1.75，大于第10组的1.21；对数距离标准差为0.80，第10组为0.42。

这种相对离散增大了形状方程中的均值之差，零点对应β=1.54，低于5/3。第10组的保留对数距离相对更集中，方程的根为3.19，处于正常范围。

**（2）保留距离集中导致的形状高估。**

W(2,1000,3000)、n=7的正常与异常样本如下：

'''+high_table+'''
![MMLE正常与高估样本的实际保留距离和形状得分](交付/结果/报告2/配对情形_MMLE_high_deletion.png)

**图22｜第5组的保留距离集中，形状得分的零点移向较大β。**

第5组的最小观测与其余点列相隔较远，以最小值为位置后，六个保留距离都落在516.94—789.60，对数跨度仅0.42。第4组的保留距离为279.54—1540.59，对数跨度为1.71，分散程度明显更大。

第5组集中的对数距离使加权均值与普通均值之差较小，形状得分曲线直到β=7.69才与零线相交，超过高估界限6；第4组的交点为2.48。两组都执行相同的最小值定位与保留样本拟合，最终差别来自方法实际使用的距离分散程度。

MMLE中，保留距离的相对离散较大时可能形成β低估，过于集中时可能形成β高估；正常样本的距离特征则对应异常界限以内的方程根。

'''
    start=text.index('MMLE的位置由最小值直接给出，图21—23')
    end=text.index('### 2.2',start)
    text=text[:start]+mmle+text[end:]
    text=text.replace('| MMLE | 直接用最小值定位，删点后估计形状与尺度 | 最小值平移放大相对离散，推动低估；删除孤立的最小观测则可能加强集中，推动高估 |',
                      '| MMLE | 直接用最小值定位，再由保留距离的形状方程确定β | 实际保留距离的相对离散较大时推动低估，过于集中时推动高估 |')
    text=text.replace('MMLE可研究最小值平移与删点对形状估计的共同作用。',
                      'MMLE可研究最小值定位后保留距离的分散程度与形状估计的关系。')
    caption_numbers={}
    for number in re.findall(r'^\*\*图(\d+)｜',text,re.M):
        caption_numbers[int(number)]=len(caption_numbers)+1
    def number(match):
        a=int(match.group(1));tail=match.group(2)
        out=str(caption_numbers[a])
        if tail:out+=tail[0]+str(caption_numbers[int(tail[1:])])
        return '图'+out
    text=re.sub(r'图(\d+)([—、]\d+)?',number,text)
    assert len(re.findall(r'^\*\*图\d+｜',text,re.M))==21
    before_formulas=re.findall(r'\$\$.*?\$\$',original,re.S)
    after_formulas=re.findall(r'\$\$.*?\$\$',text,re.S)
    assert before_formulas==after_formulas
    write_atomic(REPORT,text.encode('utf-8'))
    print('Revised LSE/LRE to two classes and MMLE to actual retained-sample comparisons; renumbered 21 figures.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='render',choices=['render','revise','verify'])
    action=parser.parse_args().action
    globals()[action]()
