"""重画本轮已选方向；只读取存档，保留同一审阅页及未反馈内容。"""
from pathlib import Path
import hashlib
import json
import runpy
import shutil
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
ROOT = STUDY / 'reviewbyhtml/方法对比'
ASSETS = ROOT / 'assets'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)', 'MM']
LABELS = ['MDM', 'LSE', 'LRE', 'WMLE', 'MLE', 'MMLE', 'MM']
COLORS = ['#0072B2', '#009E73', '#CC79A7', '#D55E00', '#444444', '#56B4E9', '#E69F00']
NS = [50, 20, 15, 10, 7]
BETAS = [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
SYMBOLS = ['β', 'η', 'γ']


def save(fig, name):
    path = ASSETS / (name + '.png')
    fig.savefig(path, dpi=190, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def global_map(model):
    # A common scale avoids both saturation by a single extreme method and
    # independent panel scales that make equal colours mean different gaps.
    gap = (np.median(np.array(model['ratios'])[:3], axis=-1) - 1) * 100
    bounds = [0, 10, 20, 40, 80, 160, 240]
    assert gap.min() >= 0 and gap.max() < bounds[-1]
    cmap = ListedColormap(['#fff8eb', '#fee0a4', '#fcb867', '#f47d43', '#d83d31', '#9d1729'])
    norm = BoundaryNorm(bounds, cmap.N)
    fig, axes = plt.subplots(1, 3, figsize=(14.8, 4.4), layout='constrained')
    for p, ax in enumerate(axes):
        im = ax.imshow(gap[p], cmap=cmap, norm=norm, aspect='auto')
        ax.set_xticks(range(8), [f'{b:g}' for b in BETAS])
        ax.set_yticks(range(5), NS)
        ax.set_xlabel('β'); ax.set_ylabel('n'); ax.set_title(SYMBOLS[p])
        ax.set_xticks(np.arange(-.5, 8, 1), minor=True)
        ax.set_yticks(np.arange(-.5, 5, 1), minor=True)
        ax.grid(which='minor', color='white', lw=1.4)
        ax.tick_params(which='minor', bottom=False, left=False)
        for i, j in np.ndindex(5, 8):
            ax.text(j, i, f'+{gap[p,i,j]:.0f}%', ha='center', va='center',
                    fontsize=9.4, color='white' if gap[p,i,j] >= 80 else '#37271d')
    cb = fig.colorbar(im, ax=axes, location='bottom', fraction=.12, pad=.08,
                     ticks=bounds, spacing='uniform', shrink=.55)
    cb.ax.set_xticklabels([f'{v}%' for v in bounds])
    cb.set_label('Median RMSE above minimum')
    return save(fig, '修订_整体差距百分比'), gap


def rose(model):
    r = np.array(model['stats']['common']['rmse'])[:3, :, 7, :].copy()
    r /= np.array([5., 1000., 1000.])[:, None, None]
    # One common monotone transformation for every method, parameter, and n.
    # Ticks retain actual normalized RMSE values; nothing is clipped.
    transform = lambda x: np.log1p(np.asarray(x) / .01)
    extent = float(transform(100.))
    assert r.max() < 100
    param_colors = ['#648BB0', '#DEA273', '#88B5A4']
    order = [0, 3, 1, 2, 4, 5, 6]
    ticks = [.03, .1, .3, 1, 3, 10, 30, 100]
    fig = plt.figure(figsize=(28, 6.1), facecolor='white')
    angle = np.linspace(0, 2*np.pi, 600)
    step = 2*np.pi / 7
    for i, n in enumerate(NS):
        ax = fig.add_axes([.007 + .2*i, .13, .186, .78], projection='polar')
        ax.set_theta_zero_location('N'); ax.set_theta_direction(-1)
        ax.set_ylim(0, extent*1.19)
        ax.set_xticks([]); ax.set_yticks([]); ax.spines['polar'].set_visible(False)
        for k, m in enumerate(order):
            center = step * (k+.5)
            ax.bar(center, extent, width=step*.92, color='#f5f7f9', zorder=0)
            for p in range(3):
                theta = center + (p-1)*step*.265
                ax.bar(theta, float(transform(r[p,i,m])), width=step*.235,
                       color=param_colors[p], edgecolor='white', lw=.7, zorder=3)
            ax.text(center, extent*1.105, LABELS[m], ha='center', va='center',
                    color='#304c63', fontsize=12, weight='bold')
        for t in ticks:
            rad = float(transform(t))
            ax.plot(angle, np.full_like(angle, rad), color='#c9d2da', lw=.7, zorder=4)
            ax.text(0, rad, f'{t:g}', fontsize=8.7, ha='center', va='center',
                    color='#586b7a', zorder=5,
                    bbox=dict(facecolor='white', edgecolor='none', pad=.2))
        # The extreme MM shape value is labelled directly; all values retain
        # their actual positions, including nonmonotone peaks at n=15.
        theta = step * 6.5 - step*.265
        ax.text(theta, transform(r[0,i,6])+.23, f'{r[0,i,6]:.2f}', ha='center',
                va='center', fontsize=10, color='#304c63', zorder=6)
        fig.text(.10+.2*i, .955, f'n = {n}', ha='center', fontsize=18,
                 color='#304c63', weight='bold')
    fig.legend(handles=[Patch(facecolor=c, label=s) for c,s in zip(param_colors, SYMBOLS)],
               loc='lower center', bbox_to_anchor=(.5, .018), ncol=3, frameon=False,
               fontsize=13, columnspacing=3, title='Normalized RMSE · compressed radius')
    return save(fig, '修订_七法玫瑰图_五档n'), r


def distributions(model, beta=5):
    windows = [(0,10), (0,2000), (0,1500)]
    ticks = [[0,2,4,6,8,10], [0,500,1000,1500,2000], [0,500,1000,1500]]
    truths = [beta,1000,500]
    j = BETAS.index(beta)
    audit = []
    fig, axes = plt.subplots(2, 3, figsize=(14.5, 7.3))
    fig.subplots_adjust(left=.085, right=.985, top=.86, bottom=.09, wspace=.16, hspace=.29)
    for row, n in enumerate([50,7]):
        df = pd.read_csv(STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv', float_precision='round_trip')
        for p, ax in enumerate(axes[row]):
            lo, hi = windows[p]
            ax.axvline(truths[p], color='#69757d', ls='--', lw=1, zorder=1)
            for m, method in enumerate(METHODS):
                mask = df[method+'_状态'].eq('success')
                values = df.loc[mask, method+'_'+['形状','尺度','位置'][p]+'估计'].to_numpy(float)
                assert len(values) == model['counts'][NS.index(n)][j][m]
                assert np.isfinite(values).all()
                rmse = np.sqrt(np.mean((values-truths[p])**2))
                assert np.isclose(rmse,model['stats']['own']['rmse'][p][NS.index(n)][j][m],rtol=2e-11)
                # Preserve the original window-local density convention.
                # Mean and quartiles still use every valid estimate.
                visible = values[(values>=lo)&(values<=hi)]
                grid = np.linspace(visible.min(), visible.max(), 500) if len(visible) else np.array([])
                if len(visible)>1 and np.ptp(visible) > 1e-9:
                    density = gaussian_kde(visible)(grid)
                    width = density / density.max() * .31
                    ax.fill_between(grid, m-width, m+width, color=COLORS[m],
                                    alpha=.6, lw=.7, edgecolor=COLORS[m], zorder=2)
                q25, q75 = np.quantile(values, [.25,.75])
                ax.plot([q25,q75], [m,m], color='#3e4b54', lw=2.3, solid_capstyle='butt', zorder=3)
                mean = values.mean()
                if lo <= mean <= hi:
                    ax.scatter(mean, m, s=24, color='#a31f32', edgecolor='white', lw=.7, zorder=4)
                audit.append(dict(beta=beta,n=n, method=method, parameter=SYMBOLS[p], count=len(values),rmse=float(rmse),
                                  outside=int(((values<lo)|(values>hi)).sum()), mean=float(mean)))
            ax.set_xlim(lo,hi); ax.set_xticks(ticks[p]); ax.set_ylim(6.65,-.65)
            ax.set_yticks(range(7), LABELS if p==0 else ['']*7)
            ax.set_xlabel(SYMBOLS[p]+' estimate')
            ax.tick_params(axis='y', length=0)
            ax.grid(axis='x', alpha=.13)
            if p==0:
                ax.set_ylabel(f'n = {n}', labelpad=17, fontsize=12)
    fig.legend(handles=[Line2D([0],[0],color='#69757d',ls='--',label='Truth'),
                       Line2D([0],[0],marker='o',ls='',color='#a31f32',label='Mean'),
                       Line2D([0],[0],color='#3e4b54',lw=2.3,label='25–75%')],
               loc='upper center', bbox_to_anchor=(.5,.965), ncol=3, frameon=False,
               columnspacing=3)
    stem='修订_估计值分布_两档n' if beta==5 else f'估计值分布_β{beta:g}_两档n'
    return save(fig, stem), audit


def main():
    board_path = ROOT/'board.json'
    board = json.loads(board_path.read_text(encoding='utf-8'))
    assert board['revision'] == 5 and board.get('last_applied_submission_id') == '6d713f35-f6ef-4966-bb5c-581184e38eb4'
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10,
                         'axes.spines.top':False, 'axes.spines.right':False})
    model = json.loads((HERE.parent/'分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for rel, digest in model['sources'].items():
        assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest() == digest
    global_path, gap = global_map(model)
    rose_path, rose_data = rose(model)
    distribution_path, audit = distributions(model)
    before = {u['id']:json.dumps(u,ensure_ascii=False,sort_keys=True) for u in board['units']}
    def change(uid, oid, label, path, scope, what, tradeoff):
        unit = next(u for u in board['units'] if u['id']==uid)
        option = next(o for o in unit['options'] if o['id']==oid)
        option['label'] = oid+' · '+label
        for b in option['blocks']:
            if b['id']=='preview': b.update(src='assets/'+path.name, alt=label)
            elif b['id']=='scope': b['html'] = '<p>'+scope+'</p>'
            elif b['id']=='what': b['html'] = '<p><strong>能讲清：</strong>'+what+'</p>'
            elif b['id']=='tradeoff': b['html'] = '<p><strong>会省略／还要补：</strong>'+tradeoff+'</p>'
    change('figure-global','A','主体差距：直接读多出百分之多少',global_path,
           '按“一眼能看出差异”的要求，缩为三个面板；每格为七法RMSE中位数相对本条件最小值多出的百分比。三列共用同一分档色标，数字可直接读；极端差距留到风险部分。',
           '哪些n、β区域的方法差距更明显，以及三个参数的差距是否相同；七种方法中至少四种的RMSE达到该格中位水平。',
           '中位数仍压缩了具体方法身份；颜色只帮助辨认幅度，不是优劣门槛。若仍需解释很久才能读懂，应继续换表达。')
    change('figure-change','C','七法玫瑰图逐档展开',rose_path,
           'β=5，n=50→20→15→10→7，补齐七法。形状RMSE除以5，尺度与位置RMSE除以1000。所有面板共用压缩半径r=ln(1+标准化RMSE/0.01)，圆环标实际标准化RMSE；没有截断MM，也不改变它在n=15的峰值。',
           '同一刻度下，误差轮廓怎样随n变化，哪些变化并不一致；此处是RMSE的变化，系统偏差另看下一张分布图。',
           '压缩半径使七法能同图出现，但半径长度与扇形面积不能直接当成线性误差倍数。这里只有β=5，其余β仍需核对。')
    change('figure-error','C','估计值分布：减为两档n',distribution_path,
           '保留β=5及七法，n纵向、三参数横向；只显示n=50和7两行。移除逐样本散点及中位数符号，仅留密度形状、均值、25%—75%区间和真值。沿用各方法自身有效结果与原显示窗口；密度显示窗口内的主体形状，均值及区间使用全部有效值，风险在3b另看。',
           '均值是否偏离真值，以及分布是否变宽；保留原分布图的读法，减少面板与叠加标记。',
           '这里看不到中间三档n，也不能从显示窗口判断全部极端输出。精度主图用共同有效集合，本图用自身有效集合，二者数值不直接对照。')
    changed = [u['id'] for u in board['units'] if json.dumps(u,ensure_ascii=False,sort_keys=True)!=before[u['id']]]
    assert set(changed) <= {'figure-global','figure-change','figure-error'}
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    runpy.run_path(str(HERE/'表达发散.py'))['write_markdown'](board)
    verification = dict(revision=5, changed_units=changed, source_files_verified=len(model['sources']),
                        sources_unchanged=True, global_gap_range=[float(gap.min()),float(gap.max())],
                        rose_normalized_rmse=rose_data.tolist(), distribution=audit,
                        outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [global_path,rose_path,distribution_path]})
    (HERE.parent/'分析数据/表达修订核验.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in verification.items() if k not in ['distribution','rose_normalized_rmse']},ensure_ascii=False))


def focus_six():
    """第三轮：恢复六法线性主图，MM保留为同图的独立数值带。"""
    board_path=ROOT/'board.json'
    board=json.loads(board_path.read_text(encoding='utf-8'))
    assert board['revision']==7
    assert board.get('last_applied_submission_id')=='880d2b44-92d4-4975-8734-b4daaaf2a530'
    before={u['id']:json.dumps(u,ensure_ascii=False,sort_keys=True) for u in board['units']}
    model=json.loads((HERE.parent/'分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for rel,digest in model['sources'].items():
        assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest()==digest
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    old=runpy.run_path(str(HERE.parent/'绘制RMSE玫瑰图.py'))
    rmse=np.array(model['stats']['common']['rmse'])[:3,:,7,:].copy()
    rmse/=np.array([5.,1000.,1000.])[:,None,None]
    extent,ticks=old['radial_scale'](rmse[:,:,:6].max())
    core=old['METHODS'][:-1]
    fig=plt.figure(figsize=(28.,8.0),facecolor='white')
    for i,n in enumerate(NS):
        rows=[dict(method=METHODS[m],parameter=old['PARAMS'][p][0],
                   normalized_rmse=float(rmse[p,i,m])) for p in range(3) for m in range(6)]
        ax=fig.add_axes([.006+.2*i,.325,.188,.635],projection='polar')
        old['panel'](ax,pd.DataFrame(rows),core,extent,ticks,label_size=8)
        fig.text(.1+.2*i,.975,f'n = {n}',ha='center',fontsize=17,weight='bold',color='#304c63')
    fig.legend(handles=[Patch(facecolor=c,label=s) for c,s in zip(old['COLORS'],SYMBOLS)],
               loc='lower center',bbox_to_anchor=(.5,.255),ncol=3,frameon=False,
               columnspacing=3,fontsize=12,title='Normalized RMSE · linear radius')
    # Actual MM values, aligned with the five n columns. This row is not a
    # second, silently rescaled rose and does not omit a method's results.
    for p,y in enumerate([.19,.12,.05]):
        fig.text(.008,y,'MM '+SYMBOLS[p],ha='left',va='center',fontsize=13,
                 weight='bold',color=old['COLORS'][p])
        for i in range(5):
            fig.text(.1+.2*i,y,f'{rmse[p,i,6]:.3f}',ha='center',va='center',
                     fontsize=16,color=old['COLORS'][p],weight='bold')
    fig.add_artist(Line2D([.025,.985],[.235,.235],transform=fig.transFigure,color='#d9e1e6',lw=1))
    path=save(fig,'修订_六法线性玫瑰图与MM数值带')
    change=next(u for u in board['units'] if u['id']=='figure-change')
    option=next(o for o in change['options'] if o['id']=='C')
    option['label']='C · 六法线性玫瑰图＋MM数值带'
    for b in option['blocks']:
        if b['id']=='preview':b.update(src='assets/'+path.name,alt='六法线性玫瑰图与MM数值带')
        elif b['id']=='scope':b['html']='<p>β=5，n=50→20→15→10→7。上方六法恢复原有线性半径，五图同一量程；下方三行是MM的实际标准化RMSE，分别与五档n对齐。仍是七法共同有效口径；形状除以5，尺度与位置除以1000。</p>'
        elif b['id']=='what':b['html']='<p><strong>能讲清：</strong>六法的误差轮廓及差距怎样随n变化，同时保留MM的完整数值；不让MM的量级决定主图半径。</p>'
        elif b['id']=='tradeoff':b['html']='<p><strong>会省略／还要补：</strong>MM改用数值呈现，其极端形状估计放到风险部分解释。这里只展示β=5，其他β仍需核对。</p>'
    mechanism=next(u for u in board['units'] if u['id']=='figure-mechanism')
    a=next(o for o in mechanism['options'] if o['id']=='A')
    a['label']='A · 方法过程与偏差传递：系统偏移及明显异常'
    source=STUDY.parent.parent/'Research/00-方法对比/交付/结果/报告2/配对情形_MMLE_low.png'
    target=ASSETS/'R00_配对情形_MMLE_low.png'
    shutil.copy2(source,target)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    if not any(b['id']=='abnormal-process' for b in a['blocks']):
        pos=next(i for i,b in enumerate(a['blocks']) if b['id']=='what')
        a['blocks'][pos:pos]=[
            dict(id='abnormal-process',kind='image',src='assets/'+target.name,
                 alt='Research00报告2图19：MMLE正常与明显异常的参数估计过程'),
            dict(id='abnormal-caption',kind='text',html='<p>同一过程形式再看明显异常：复用报告2图19，W(5,100,500)、n=7，上排正常第10组，下排异常第11组。异常样本先以575.95定位，保留距离更分散，形状峰落在1.54，低于5/3；尺度随之得到28.69。三列依次读“怎样定位—形状怎样确定—尺度怎样恢复”。</p>')]
    for b in a['blocks']:
        if b['id']=='scope':b['html']='<p>先保留报告1第2.6节、图15，作为系统偏移的过程例：MMLE由最小值定位，再拟合保留距离；高β例呈现位置偏高、形状和尺度偏低。这幅50组历史图展示有规律的偏移。</p>'
        elif b['id']=='what':b['html']='<p><strong>能讲清：</strong>沿方法实际步骤追踪，看到位置选择怎样带动形状和尺度；用同一形式分别讲系统偏移与明显异常。正式讲述可只展开其中一例。</p>'
        elif b['id']=='tradeoff':b['html']='<p><strong>会省略／还要补：</strong>两幅都是Research00原案例，不并入本轮频率。报告1图15用于有规律的偏移，报告2图19中的第11组达到明显异常判据；选定后再精简面板。</p>'
    e=next(o for o in mechanism['options'] if o['id']=='E')
    for b in e['blocks']:
        if b['id']=='what':b['html']='<p><strong>能讲清：</strong>小n、大β时，样本对起点的约束不足，参数又能相互补偿。可先用它交代共同背景，再用A的过程图说明具体方法怎样形成偏移或异常。</p>'
    mechanism['context']='按本轮批注：E可交代小n、大β的背景，A用方法过程与偏差传递解释具体案例；两者可前后承接。其余候选保留。'
    changed=[u['id'] for u in board['units'] if json.dumps(u,ensure_ascii=False,sort_keys=True)!=before[u['id']]]
    assert changed==['figure-change','figure-mechanism']
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runpy.run_path(str(HERE/'表达发散.py'))['write_markdown'](board)
    result=dict(revision=7,changed_units=changed,source_files_verified=40,
                six_method_extent=extent,mm_values=rmse[:,:,6].tolist(),
                original_case_source=str(source),original_case_sha256=digest,new_estimates=0)
    (HERE.parent/'分析数据/第三轮表达修订核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


def distribution_sequence(render_only=False):
    """重绘已有图组；render_only不改动任何审阅内容。"""
    if not render_only:
        board_path=ROOT/'board.json'
        board=json.loads(board_path.read_text(encoding='utf-8'))
        assert board['revision']==9 and not board.get('processing')
        before={u['id']:json.dumps(u,ensure_ascii=False,sort_keys=True) for u in board['units']}
    model=json.loads((HERE.parent/'分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for rel,digest in model['sources'].items():
        assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest()==digest
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False})
    images=[];audit=[]
    for beta in BETAS:
        path,records=distributions(model,beta)
        images.append(dict(id=f'beta-{beta:g}',src='assets/'+path.name,label=f'β = {beta:g}',
                           alt=f'β={beta:g}，n=50与7的七法三参数估计分布'))
        audit.extend(records)
        print(f'已生成 β={beta:g}',flush=True)
    if render_only:
        return images
    unit=next(u for u in board['units'] if u['id']=='figure-error')
    unit['title']='偏移与波动：随β切换的估计值分布'
    option=unit['options'][0]
    for b in option['blocks']:
        if b['id']=='preview':
            b.clear();b.update(id='preview',kind='gallery',images=images,aspect_ratio=2715/1320)
        elif b['id']=='scope':b['html']='<p>β按1.5、2、2.5、3、3.5、4、4.5、5依次切换。每张图均为n=50和7纵向、三参数横向、七法同序；三列显示范围分别固定为0—10、0—2000、0—1500。虚线随真实β移动，便于区分真值变化与估计偏移。</p>'
        elif b['id']=='what':b['html']='<p><strong>能讲清：</strong>先在一张图中比较三参数与两档n，再顺序切换β，观察偏移方向和分布宽度是否改变。用于报告时可按同一顺序逐张播放。</p>'
        elif b['id']=='tradeoff':b['html']='<p><strong>统计与显示：</strong>各法自身有效结果；密度只展示窗口内主体，均值及25%—75%区间用全部有效值，窗外结果未从统计删除。这里只比较两档n，中间三档仍在原数据中。</p>'
    assert [u['id'] for u in board['units'] if json.dumps(u,ensure_ascii=False,sort_keys=True)!=before[u['id']]]==['figure-error']
    # Recheck no submitted work arrived while rendering the plots.
    latest=json.loads((ROOT/'feedback.json').read_text(encoding='utf-8'))
    assert latest['board_revision']<board['revision'],'有新提交，先处理后接入图组'
    board.update(revision=10,processing=True,review_complete=False)
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runpy.run_path(str(HERE/'表达发散.py'))['write_markdown'](board)
    (HERE.parent/'分析数据/β分布图组核验.json').write_text(json.dumps(dict(
        revision=10,betas=BETAS,n=[50,7],methods=METHODS,metrics_verified=len(audit),
        windows=[[0,10],[0,2000],[0,1500]],new_estimates=0,records=audit,
        outputs={item['src']:hashlib.sha256((ROOT/item['src']).read_bytes()).hexdigest() for item in images}
    ),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(revision=10,images=len(images),metrics_verified=len(audit),new_estimates=0),ensure_ascii=False))


def rose_n_sequence(render_only=False):
    """重绘已有图组；render_only不改动任何审阅内容。"""
    if not render_only:
        board_path=ROOT/'board.json'
        board=json.loads(board_path.read_text(encoding='utf-8'))
        assert board['revision']==10 and not board.get('processing')
        before={u['id']:json.dumps(u,ensure_ascii=False,sort_keys=True) for u in board['units']}
    model=json.loads((HERE.parent/'分析数据/比较论证-v0.4.json').read_text(encoding='utf-8'))
    for rel,digest in model['sources'].items():
        assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest()==digest
    raw=np.array(model['stats']['common']['rmse'])[:3]
    # Recheck each parameter/method against the same seven-method intersection.
    counts=[]
    for i,n in enumerate(NS):
        for j,beta in enumerate(BETAS):
            df=pd.read_csv(STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv',float_precision='round_trip')
            assert df['样本编号'].tolist()==list(range(1200))
            common=np.logical_and.reduce([df[m+'_状态'].eq('success').to_numpy() for m in METHODS])
            assert int(common.sum())==model['common_counts'][i][j]
            counts.append(dict(n=n,beta=beta,common=int(common.sum())))
            for p,(suffix,truth) in enumerate(zip(['形状','尺度','位置'],[beta,1000,500])):
                values=df.loc[common,[m+'_'+suffix+'估计' for m in METHODS]].to_numpy(float)
                assert np.isfinite(values).all()
                calculated=np.sqrt(np.mean((values-truth)**2,axis=0))
                assert np.allclose(calculated,raw[p,i,j],rtol=2e-11,atol=1e-10)
    denominators=np.array([BETAS,[1000]*len(BETAS),[1000]*len(BETAS)])
    normalized=raw/denominators[:,None,:,None]
    old=runpy.run_path(str(HERE.parent/'绘制RMSE玫瑰图.py'))
    extent,ticks=old['radial_scale'](normalized[:,:,:,:6].max())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    images=[]
    for i,n in enumerate(NS):
        fig=plt.figure(figsize=(24,17),facecolor='white')
        for j,beta in enumerate(BETAS):
            row,col=divmod(j,4)
            bottom=.60-.49*row
            rows=[dict(method=METHODS[m],parameter=old['PARAMS'][p][0],
                       normalized_rmse=float(normalized[p,i,j,m])) for p in range(3) for m in range(6)]
            ax=fig.add_axes([.007+.25*col,bottom,.236,.32],projection='polar')
            old['panel'](ax,pd.DataFrame(rows),old['METHODS'][:-1],extent,ticks,label_size=8)
            fig.text(.125+.25*col,.955-.49*row,f'β = {beta:g}',ha='center',
                     fontsize=18,weight='bold',color='#304c63')
            for p,y in enumerate([.582,.556,.530]):
                if col==0:
                    fig.text(.012,y-.49*row,'MM '+SYMBOLS[p],ha='left',va='center',
                             fontsize=12,weight='bold',color=old['COLORS'][p])
                fig.text(.125+.25*col,y-.49*row,f'{normalized[p,i,j,6]:.3f}',ha='center',
                         va='center',fontsize=14,color=old['COLORS'][p],weight='bold')
        fig.legend(handles=[Patch(facecolor=c,label=s) for c,s in zip(old['COLORS'],SYMBOLS)],
                   loc='center',bbox_to_anchor=(.5,.495),ncol=3,frameon=False,
                   columnspacing=3,fontsize=13,title='Normalized RMSE · linear radius')
        path=ASSETS/f'RMSE玫瑰图_n{n}_八档β.png'
        # Fixed canvas keeps the slot and rose positions identical when switching n.
        fig.savefig(path,dpi=190,facecolor='white')
        plt.close(fig)
        images.append(dict(id=f'n-{n}',label=f'n = {n}',src='assets/'+path.name,
                           alt=f'n={n}，β=1.5至5的八组RMSE玫瑰图与MM数值'))
        print(f'已生成 n={n}',flush=True)
    if render_only:
        return images
    unit=next(u for u in board['units'] if u['id']=='figure-change')
    unit['title']='差距变化：按n切换，各β并列'
    for block in unit['options'][0]['blocks']:
        if block['id']=='preview':
            block.clear();block.update(id='preview',kind='gallery',images=images,aspect_ratio=24/17)
        elif block['id']=='scope':
            block['html']='<p>按n=50→20→15→10→7切换。每张将β=1.5～5排为两行四列，六法玫瑰图与其下的MM数值一一对应。五张图、四十个面板共用0～'+f'{extent:g}'+'的线性半径；形状RMSE除以真实β，尺度与位置RMSE除以1000。</p>'
        elif block['id']=='what':
            block['html']='<p><strong>能讲清：</strong>同一n下先比较不同β的误差轮廓；再向右切换，让n逐档减小，观察各β下哪些方法的误差和方法间差距变化更明显。半径不随页面重设，变化可直接对照。</p>'
        elif block['id']=='tradeoff':
            block['html']='<p><strong>统计与显示：</strong>仍按每个条件的七法共同有效结果计算，MM完整数值单列。半径长度对应标准化RMSE，扇形面积不代表误差倍数；条件间共同有效的样本数可不同，异常与失败另图分析。</p>'
    assert [u['id'] for u in board['units'] if json.dumps(u,ensure_ascii=False,sort_keys=True)!=before[u['id']]]==['figure-change']
    latest=json.loads((ROOT/'feedback.json').read_text(encoding='utf-8'))
    assert latest['board_revision']<board['revision'],'有新提交，先处理后接入图组'
    board.update(revision=11,processing=True,review_complete=False)
    board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runpy.run_path(str(HERE/'表达发散.py'))['write_markdown'](board)
    (HERE.parent/'分析数据/n切换玫瑰图组核验.json').write_text(json.dumps(dict(
        revision=11,sample_sizes=NS,betas=BETAS,source_files_verified=len(model['sources']),
        metrics_verified=int(raw.size),common_counts=counts,new_estimates=0,
        radius_extent=extent,radius_ticks=ticks,normalization=['true beta','1000','1000'],
        normalized_rmse=normalized.tolist(),
        outputs={item['src']:hashlib.sha256((ROOT/item['src']).read_bytes()).hexdigest() for item in images}
    ),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(revision=11,images=len(images),metrics_verified=int(raw.size),
                          radius_extent=extent,new_estimates=0),ensure_ascii=False))


if __name__=='__main__':
    if sys.argv[1:]==['--focus-six']:focus_six()
    elif sys.argv[1:]==['--distribution-sequence']:distribution_sequence()
    elif sys.argv[1:]==['--rose-n-sequence']:rose_n_sequence()
    elif not sys.argv[1:]:main()
    else:raise SystemExit('可选参数：--focus-six、--distribution-sequence 或 --rose-n-sequence')
