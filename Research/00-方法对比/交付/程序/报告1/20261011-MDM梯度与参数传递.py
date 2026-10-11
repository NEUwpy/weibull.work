"""MDM mechanism: beta=2/5 by n=7/15/30; then gamma -> beta -> eta.

Reuse all n=7/15 samples, estimates and curve nodes. Reuse the saved n=30
paired observations and beta=5 estimates, and compute beta=2 estimates with
the same frozen MDM. Generate no random samples and replace no archived fit.
Keep a task-specific program/data/check record and export two PNGs only.
The first figure compares the threshold crossings. The second follows the
same sample 48 as the existing MDM representative, with numbered actual nodes.
The derivative argument concerns an interior conditional shape optimum and
the large-shape expansion, not a general monotonicity or bias theorem.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, RESULT, setup_runtime, save_png, write_atomic

FROZEN = HERE / '依赖快照/python'
sys.path.insert(0, str(FROZEN))
sys.path.insert(0, str(FROZEN / 'methods'))
spec = importlib.util.spec_from_file_location('r1_mdm_mechanism_frozen', FROZEN / 'methods/mdm.py')
mdm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mdm)
INPUT = RESULT / '报告1/中间数据'
N30 = HERE / '20261010-导入图n30样本.json'
MATRIX = HERE.parent / 'W5,1000,500/完整矩阵/数据/matrix.json'
CACHE = HERE / '20261011-MDM梯度与参数传递.json'
QA = HERE / '20261011-MDM梯度与参数传递核验.json'
FIGURE = RESULT / '报告1/图3_MDM六格机制.png'
TRANSFER = RESULT / '报告1/图4_MDM参数传递.png'
FIGURE1 = RESULT / '报告1/图1_原案例参数分布.png'
FIGURE_QA = INPUT / '逐法图核验.json'
REPORT = ROOT / '报告1：高形状参数下的估计偏移.md'
README = ROOT / 'README.md'
SELECTED = 48
BLUE, RETURN = '#345D7E', '#B55E3E'
CONDITIONS = [(b, n) for n in [7, 15, 30] for b in [2, 5]]
AXIS = dict(x_limits=[-25., 1400.], x_ticks=[0., 500., 1000.],
            y_limits=[-.12, .4], y_ticks=[-.1, 0., .1, .2, .3, .4],
            x_scale='linear', y_scale='linear')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    write_atomic(path, (json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':')) + '\n').encode('utf-8'))


def sources():
    names = ['样本.json', '实际估计.json', '逐法过程曲线.json', '配对单例与推导核验.json']
    hashes = {f'paired/{name}': sha(INPUT / name) for name in names}
    hashes.update({str(p.relative_to(ROOT.parents[1])): sha(p)
                   for p in [N30, MATRIX, FROZEN / 'methods/mdm.py', FROZEN / 'base.py']})
    return hashes


def protected_results():
    out = RESULT / '报告1'
    return {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*')
            if p.is_file() and p not in (FIGURE, TRANSFER, FIGURE1, FIGURE_QA)}


def other_figure_metadata():
    record = read(FIGURE_QA)
    record['process_figures'] = [r for r in record['process_figures'] if r['method'] != 'mdm']
    record.pop('mdm_parameter_transfer', None)
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def profile_functions(x):
    x = np.asarray(x, float)
    n, minimum = len(x), float(min(x))
    probabilities = (np.arange(1, n + 1) - .3) / (n + .4)
    factors = -np.log1p(-probabilities)
    cache = {}

    def conditional(gamma):
        gamma = float(gamma)
        if gamma not in cache:
            result = minimize_scalar(lambda beta: np.std((x - gamma) / factors**(1 / beta), ddof=1),
                                     bounds=(.1, 15), method='bounded')
            pseudo = (x - gamma) / factors**(1 / result.x)
            cache[gamma] = [float(result.x), float(pseudo.mean()), float(result.fun)]
        return cache[gamma]

    def gradient(gamma):
        gamma = float(gamma)
        scale = max(abs(minimum), 1.)
        nominal = scale * 1e-5
        right = minimum - gamma
        assert right > 0
        if gamma <= nominal:
            h = max(min(nominal, right * .25), np.finfo(float).eps * scale)
            return (conditional(gamma + h)[2] - conditional(gamma)[2]) / h
        if right <= nominal:
            h = max(min(nominal, gamma * .25, right * .5), np.finfo(float).eps * scale)
            return (conditional(gamma)[2] - conditional(gamma - h)[2]) / h
        h = min(nominal, gamma * .25, right * .25)
        return (conditional(gamma + h)[2] - conditional(gamma - h)[2]) / (2 * h)

    return conditional, gradient, factors


def n30_curve(task):
    sample, archived = task
    x = np.asarray(sample['observations'], float)
    estimator = mdm.MDM(x)
    result = estimator.run(offset=.1, gamma_steps=240, rank_method='bernard')
    fit = dict(beta_hat=float(result[0]), eta_hat=float(result[1]), gamma_hat=float(result[2]),
               converged=bool(result[4]), extra={'solution_info': estimator.last_solution_info})
    if archived is not None:
        expected = [archived[k] for k in ['beta_hat', 'eta_hat', 'gamma_hat']]
        assert np.allclose(result[:3], expected, rtol=1e-9, atol=1e-6)
        fit = copy.deepcopy(archived)
        fit['extra'] = archived['original_record']['extra']
    conditional, gradient, _ = profile_functions(x)
    top = x[0] - max(1e-5, x[0] * 1e-7)
    returned = fit['gamma_hat']
    grid = np.unique(np.r_[np.linspace(0, top, 141), 500., returned,
                            returned - 2, returned + 2, returned - 10, returned + 10])
    grid = grid[(grid >= 0) & (grid <= top)]
    points = [[float(g), float(gradient(g)), *conditional(g)[:2], False, None] for g in grid]
    return dict(source='paired_n30', beta=sample['beta'], n=30, sample_id=sample['sample_id'], method='mdm',
                observations=sample['observations'], sample_min=float(x[0]), fit=fit, points=points,
                truth=next(p for p in points if p[0] == 500),
                returned=next(p for p in points if p[0] == returned),
                estimate_origin='archived_beta5' if archived is not None else 'frozen_MDM_beta2')


def build():
    if CACHE.exists():
        assert read(CACHE)['source_hashes'] == sources()
        print('REUSED：MDM三档n与参数传递数据。', flush=True)
        return
    hashes, protected, metadata = sources(), protected_results(), other_figure_metadata()
    samples = read(INPUT / '样本.json')
    index = {(s['beta'], s['n'], s['sample_id']): s for s in samples}
    rows = [copy.deepcopy(r) for r in read(INPUT / '逐法过程曲线.json')['curves']
            if r['method'] == 'mdm' and r['source'] == 'paired']
    for row in rows:
        row['observations'] = index[row['beta'], row['n'], row['sample_id']]['observations']
    n30 = read(N30)
    matrix = read(MATRIX)
    assert n30['source_sha256'] == sha(MATRIX)
    archived = {r['id']: r for r in matrix['results']
                if r['n'] == 30 and r['method_id'] == 'mdm' and r['delta'] == .1}
    for sample in n30['samples']:
        if sample['beta'] == 5:
            x = next(s['values'] for s in matrix['samples'] if s['n'] == 30 and s['id'] == sample['sample_id'])
            assert sample['observations'] == x
    tasks = [(s, archived[s['sample_id']] if s['beta'] == 5 else None) for s in n30['samples']]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for i, row in enumerate(pool.map(n30_curve, tasks, chunksize=5), 1):
            rows.append(row)
            if i % 25 == 0:
                print(f'MDM n=30：{i}/100', flush=True)
    summaries = []
    for beta, n in CONDITIONS:
        rr = [r for r in rows if r['beta'] == beta and r['n'] == n]
        assert len(rr) == 50
        values = np.array([r['truth'][1] for r in rr])
        summaries.append(dict(beta=beta, n=n, truth_gradient_quartiles=np.quantile(values, [.25, .5, .75]).tolist(),
                              truth_gradient_sd=float(np.std(values, ddof=1)),
                              truth_below_offset=int(np.sum(values < .1)),
                              median_gamma=float(np.median([r['fit']['gamma_hat'] for r in rr])),
                              median_beta=float(np.median([r['fit']['beta_hat'] for r in rr])),
                              median_eta=float(np.median([r['fit']['eta_hat'] for r in rr])),
                              return_gamma_above_truth=sum(r['fit']['gamma_hat'] > 500 for r in rr),
                              root_solvers={name: sum(r['fit']['extra']['solution_info']['root_solver'] == name for r in rr)
                                            for name in ['brent', 'right_edge_fit', None]}))
    selection = next(s for s in read(INPUT / '配对单例与推导核验.json')['methods'] if s['method'] == 'mdm')
    assert selection['sample_id'] == SELECTED
    assert hashes == sources() and protected == protected_results() and metadata == other_figure_metadata()
    write(CACHE, dict(source_hashes=hashes, protected_results=protected, protected_figure_metadata=metadata,
                     conditions=CONDITIONS, selected_id=SELECTED, selection='reuse prior paired representative, same ID for beta=2/5',
                     offset=.1, new_random_samples=0, reused_curves=200, added_n30_curves=100,
                     reused_n30_estimates=50, added_mapped_beta2_n30_estimates=50, replaced_archived_estimates=0,
                     n30_provenance={k:v for k,v in n30.items() if k!='samples'},
                     summaries=summaries, curves=rows, axes=AXIS))


def style():
    setup_runtime()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
                         'font.size':7, 'axes.labelsize':7, 'axes.titlesize':7.2, 'xtick.labelsize':6.5,
                         'ytick.labelsize':6.5, 'axes.linewidth':.7, 'axes.spines.right':False,
                         'axes.spines.top':False, 'axes.unicode_minus':False})
    return plt


def axis(ax, label, beta, n, settings, letter):
    ax.set_xlim(settings['x_limits']); ax.set_xticks(settings['x_ticks'])
    ax.set_ylim(settings['y_limits']); ax.set_yticks(settings['y_ticks'])
    ax.set_xlabel('γ'); ax.set_ylabel(label)
    ax.axvline(500, color='black', ls=':', lw=.85)
    ax.set_title(f'β={beta}，n={n}',loc='left',pad=9)
    ax.text(-.13,1.10,letter,transform=ax.transAxes,fontsize=8,weight='bold')
    return dict(x_limits=list(ax.get_xlim()), y_limits=list(ax.get_ylim()),
                x_ticks=ax.get_xticks().tolist(), y_ticks=ax.get_yticks().tolist(),
                x_scale=ax.get_xscale(), y_scale=ax.get_yscale())


def gradient_figure(data):
    plt = style()
    fig, axes = plt.subplots(3,2,figsize=(7.2,7.2))
    panels, states = [], []
    for i,(beta,n) in enumerate(CONDITIONS):
        ax=axes.flat[i]
        rr=[r for r in data['curves'] if r['beta']==beta and r['n']==n]
        for row in rr:
            pp=np.array(row['points'],dtype=object)
            ax.plot(pp[:,0],pp[:,1],color=BLUE,alpha=.22,lw=.65)
            ax.scatter(500,row['truth'][1],s=7,color=BLUE,linewidths=0,alpha=.5,zorder=3)
            returned=row['returned']
            ax.scatter(returned[0],returned[1],color=RETURN,marker='x',s=12,linewidths=.7,alpha=.65,zorder=4)
            ax.plot(row['fit']['gamma_hat'],.018,marker='|',color=RETURN,ms=5,
                    transform=ax.get_xaxis_transform(),alpha=.45,zorder=4)
        if n==7:
            representative=next(r for r in rr if r['sample_id']==SELECTED)
            pp=representative['points']
            ax.plot([p[0] for p in pp],[p[1] for p in pp],color=BLUE,lw=1.15,zorder=3)
        ax.axhline(.1,color='black',ls='--',lw=.85)
        states.append(axis(ax,r'$\nabla(\gamma)$',beta,n,AXIS,chr(97+i)))
        panels.append(dict(beta=beta,n=n,curves=50,
                           truth_gradient_values=[r['truth'][1] for r in rr],
                           displayed_criterion_window=AXIS['y_limits'],
                           hidden_truth_ids=[r['sample_id'] for r in rr if not -.12<=r['truth'][1]<=.4],
                           highlighted_sample_id=SELECTED if n==7 else None))
    assert all(s==states[0] for s in states)
    fig.subplots_adjust(left=.115,right=.985,top=.945,bottom=.075,hspace=.64,wspace=.36)
    save_png(fig,FIGURE,dpi=450);plt.close(fig)
    return dict(method='mdm',file=FIGURE.stem,criterion='profile standard deviation finite-difference gradient',
                panels=panels,axis_settings=states,six_panel_axes_identical=True,
                png_dimensions=[3240,3240],source_data=CACHE.relative_to(ROOT).as_posix())


def transfer_figure(data):
    plt=style()
    fig,axes=plt.subplots(3,2,figsize=(7.2,7.2))
    panels,states=[],[]
    for row_index,(column,label,limits,ticks) in enumerate([
            (1,r'$\nabla(\gamma)$',[-.12,.4],[-.1,0,.1,.2,.3,.4]),
            (2,r'$\hat\beta(\gamma)$',[0.,10.],[0.,2.,4.,6.,8.,10.]),
            (3,r'$\hat\eta(\gamma)$',[0.,1600.],[0.,500.,1000.,1500.])]):
        for col,beta in enumerate([2,5]):
            row=next(r for r in data['curves'] if r['beta']==beta and r['n']==7 and r['sample_id']==SELECTED)
            pp=row['points'];ax=axes[row_index,col]
            ax.plot([p[0] for p in pp],[p[column] for p in pp],color=BLUE,lw=1.25)
            ax.scatter([p[0] for p in pp],[p[column] for p in pp],s=4.5,facecolor='white',edgecolor=BLUE,linewidth=.4,zorder=3)
            returned=row['returned'];truth=row['truth']
            ax.axvline(row['fit']['gamma_hat'],color=RETURN,ls='--',lw=.8)
            reference=.1 if column==1 else (beta if column==2 else 1000.)
            ax.axhline(reference,color='black' if column==1 else '.55',ls='--',lw=.75)
            ax.scatter(500,truth[column],color=BLUE,s=16,linewidths=0,zorder=5)
            ax.scatter(returned[0],returned[column],color=RETURN,marker='x',s=27,linewidths=1,zorder=5)
            if row_index==0:
                for p,offset,color in [(truth,(8,10),BLUE),(returned,(8,-16),RETURN)]:
                    pid=f'G{next(i for i,v in enumerate(pp,1) if v[0]==p[0])}'
                    ax.annotate(pid,(p[0],p[column]),xytext=offset,textcoords='offset points',fontsize=6,color=color)
            settings={**AXIS,'y_limits':limits,'y_ticks':ticks}
            states.append(axis(ax,label,beta,7,settings,chr(97+row_index*2+col)))
            panels.append(dict(beta=beta,n=7,sample_id=SELECTED,column=column,
                               truth=truth,returned=returned,points_identical_to_multi_sample=True))
    assert all(s['x_limits']==AXIS['x_limits'] and s['x_ticks']==AXIS['x_ticks'] for s in states)
    assert all(states[i]==states[i+1] for i in [0,2,4])
    fig.subplots_adjust(left=.115,right=.985,top=.945,bottom=.075,hspace=.64,wspace=.36)
    save_png(fig,TRANSFER,dpi=450);plt.close(fig)
    return dict(file=TRANSFER.stem,panels=panels,axis_settings=states,
                png_dimensions=[3240,3240],source_data=CACHE.relative_to(ROOT).as_posix())


def render():
    data=read(CACHE)
    assert data['source_hashes']==sources()
    first,second=gradient_figure(data),transfer_figure(data)
    restored=restore_missing_figure1()
    record=read(QA) if QA.exists() else {}
    record['figures']={'gradient':first,'transfer':second}
    record['figure_hashes']={FIGURE.name:sha(FIGURE),TRANSFER.name:sha(TRANSFER)}
    if restored is not None:record['restored_missing_figure1']=restored
    write(QA,record)
    metadata=read(FIGURE_QA)
    metadata['process_figures']=[first if r['method']=='mdm' else r for r in metadata['process_figures']]
    metadata['mdm_parameter_transfer']=second
    write(FIGURE_QA,metadata)
    print('EXPORTED：MDM三档n梯度图与参数传递图。',flush=True)
    return first


def restore_missing_figure1():
    """Repair the report's result image link using saved estimates only.

    Leave the separate distribution generator's data/QA untouched: this is
    recovery of a missing PNG, not a new distribution-analysis task.
    """
    target=FIGURE1
    if target.exists() or '](交付/结果/报告1/图1_原案例参数分布.png)' not in REPORT.read_text(encoding='utf-8'):
        return None
    import 绘制图1小提琴 as violin
    original_write=violin.write_atomic
    try:
        violin.write_atomic=lambda path,value:None
        violin.main()
    finally:
        violin.write_atomic=original_write
    return dict(path=target.relative_to(ROOT).as_posix(),sha256=sha(target),
                source='existing distribution generator and saved estimates',
                estimates_recomputed=0,other_results_modified=False)


def revise():
    text=REPORT.read_text(encoding='utf-8')
    original=text
    text=text.replace('](图1_原案例参数分布.png)','](交付/结果/报告1/图1_原案例参数分布.png)')
    if '图5　MDM的位置选择与参数传递' not in text:
        start=text.index('其中，β̂、η̂、γ̂分别为形状、尺度和位置估计。图4按式（6）')
        end=text.index('### 2.2 ',start)
        before,after=text[:start],text[end:]
        # Two derived identities and one new main figure; shift existing references once.
        after=re.sub(r'\\tag\{(\d+)\}',lambda m:r'\tag{'+str(int(m[1])+2)+'}',after)
        def shift_equation(m):
            number=int(m[1]);return '式（'+str(number+2 if number>=9 else number)+'）'
        after=re.sub(r'式（(\d+)）',shift_equation,after)
        after=re.sub(r'图(\d+)(?![\d_])',lambda m:'图'+str(int(m[1])+1) if 5<=int(m[1])<=9
                     and after[max(0,m.start()-2):m.start()]!='补充' else m[0],after)
        after=after.replace('图4–9','图4–10')
        section=r'''其中，β̂、η̂、γ̂分别为形状、尺度和位置估计。图4以中心差分近似计算式（6）的梯度，横虚线为式（7）的补偿值0.10，竖点线为真γ=500。

![图4　MDM在不同形状与样本量下的梯度](交付/结果/报告1/图3_MDM六格机制.png)

**图4｜高β时梯度曲线较集中，补偿值交点总体右移；随n增大，右移程度减轻。**

β=5时，真γ处的梯度多数低于0.10，曲线比β=2更集中，交点因而集中于真γ右侧。随n增大，β=5的位置估计向真值靠近。

这一差别来自伪尺度对γ的响应。固定β，对式（5）求导并在β较大时作一阶展开：

$$\frac{\partial\hat\eta_i}{\partial\gamma}
=-[-\ln(1-\hat F(t_{(i)}))]^{-1/\beta}
\approx -1+\frac{\ln[-\ln(1-\hat F(t_{(i)}))]}{\beta}.
\tag{9}$$

式（9）中，各伪尺度的变化率随β增大而接近共同值−1。共同平移不改变标准差，标准差梯度的大小受这些变化率之间的差异限制；差异缩小，梯度便集中在零附近。在条件最优β为内部平滑解时，重新优化β不增加一阶响应。高β对照中，真γ附近的条件β也较大，因此固定的0.10补偿值多数要在更右侧达到。这一展开解释曲线的压缩趋势，梯度的正负仍由具体样本决定。

n增大使最小观测更靠近真γ（图2），收紧位置上移空间；同时，概率位置与样本间距的随机偏差减小，原本不同的β、γ组合更容易被区分。图4所示交点仍受固定补偿值影响，但右移程度随n增大而减轻。

位置确定后，MDM在该γ处取使伪尺度标准差最小的β，再按式（8）计算η。图5展开图4a、b中加深的第48组曲线：每个候选γ对应的β̂(γ)、η̂(γ)分别由这两步得到。

![图5　MDM的位置选择与参数传递](交付/结果/报告1/图4_MDM参数传递.png)

**图5｜偏高γ对应较低β，并通过伪尺度均值得到较低η。** 蓝点为固定真γ的条件估计，橙叉为最终估计。

在伪尺度接近一致时，由式（5）可得：

$$\frac{t_{(j)}-\gamma}{t_{(i)}-\gamma}
\approx\left[\frac{-\ln(1-\hat F(t_{(j)}))}{-\ln(1-\hat F(t_{(i)}))}\right]^{1/\beta},\qquad j>i.
\tag{10}$$

其中，j为较大观测的序号。γ上移时，小距离缩短的比例更大，式（10）左侧的距离比增大，而右侧的概率比不变，需要较小β维持伪尺度一致性。图5d显示了这一变化；缩短后的距离与对应β代入式（8），尺度均值也随之降低（图5f）。该高β样本最终返回W(3.89,535,974)，说明梯度补偿先选中了偏高的位置，再带动形状与尺度偏低。

'''
        text=before+section+after
    # Keep an already numbered report in sync with this task's final wording.
    text=text.replace('图4按式（6）绘制梯度，', '图4以中心差分近似计算式（6）的梯度，')
    text=text.replace('式（9）中，各伪尺度的变化率随β增大而接近共同值−1；共同平移不改变标准差，因此其最小标准差对γ的响应较弱。在条件最优β为内部平滑解的区间，重新优化β不产生额外的一阶变化。高β对照中，真位置附近的条件β也较大，梯度因而压缩在零附近，固定的0.10补偿值则需要在更右侧达到。这里的一阶展开用于解释压缩趋势，不规定每个样本梯度的正负。',
                      '式（9）中，各伪尺度的变化率随β增大而接近共同值−1。共同平移不改变标准差，标准差梯度的大小受这些变化率之间的差异限制；差异缩小，梯度便集中在零附近。在条件最优β为内部平滑解时，重新优化β不增加一阶响应。高β对照中，真γ附近的条件β也较大，因此固定的0.10补偿值多数要在更右侧达到。这一展开解释曲线的压缩趋势，梯度的正负仍由具体样本决定。')
    text=text.replace('图5展开图4a、b中的同一组样本，展示这两步如何形成参数补偿。',
                      '图5展开图4a、b中加深的第48组曲线：每个候选γ对应的β̂(γ)、η̂(γ)分别由这两步得到。')
    if '蓝点为固定真γ的条件估计' not in text:
        text=text.replace('**图5｜偏高γ对应较低β，并通过伪尺度均值得到较低η。**',
                          '**图5｜偏高γ对应较低β，并通过伪尺度均值得到较低η。** 蓝点为固定真γ的条件估计，橙叉为最终估计。')
    if '当γ=0处的梯度已达到或超过0.10时' not in text:
        text=text.replace('β̂取该位置对应的形状参数，最终尺度取伪尺度均值：',
                          '当γ=0处的梯度已达到或超过0.10时，取γ̂=0。β̂取该位置对应的形状参数，最终尺度取伪尺度均值：',1)
    link='[MDM梯度与参数传递数据](交付/程序/报告1/20261011-MDM梯度与参数传递.json)'
    if link not in text:
        text=text.replace('**数据与程序。** ','**数据与程序。** '+link+'、',1)
    if text!=original:write_atomic(REPORT,text.encode('utf-8'))
    readme=README.read_text(encoding='utf-8')
    note=('报告1的MDM分析按“梯度与交点—曲线压缩原因—γ到β、η的传递”组织。'
          '[20261011-MDM梯度与参数传递.py](交付/程序/报告1/20261011-MDM梯度与参数传递.py)提供`build`、`render`、`revise`、`verify`；'
          '[数据](交付/程序/报告1/20261011-MDM梯度与参数传递.json)和'
          '[核验](交付/程序/报告1/20261011-MDM梯度与参数传递核验.json)放在程序目录。'
          '图4为β=2/5、n=7/15/30的六格梯度；图5仍用原代表第48组展示梯度、条件β和伪尺度均值；后续各方法图顺延为图6—10。'
          'n=7/15曲线及估计不变；n=30复用已保存的β=5样本和估计，β=2沿用已保存的同潜在变量转换样本，按冻结MDM新增50次估计。'
          '无新抽样、不替换存档结果，补偿值仍为0.10，PNG为唯一图像输出，统一制图入口已接入。\n\n')
    marker='报告1的MDM分析按“梯度与交点—曲线压缩原因—γ到β、η的传递”组织。'
    readme=readme.replace('报告1的WMLE图7','报告1的WMLE图8')
    readme=readme.replace('第2.6节与图9解释','第2.6节与图10解释').replace('图9固定删除同一个最小观测','图10固定删除同一个最小观测')
    if marker in readme:
        start=readme.index(marker);end=readme.index('\n\n',start)+2
        readme=readme[:start]+note+readme[end:]
    else:
        readme=readme.replace('## 整理与恢复\n',note+'## 整理与恢复\n',1)
    if readme!=README.read_text(encoding='utf-8'):
        write_atomic(README,readme.encode('utf-8'))


def verify():
    data,qa=read(CACHE),read(QA)
    assert data['source_hashes']==sources()
    assert data['protected_results']==protected_results()
    assert data['protected_figure_metadata']==other_figure_metadata()
    old={(r['beta'],r['n'],r['sample_id']):r for r in read(INPUT/'逐法过程曲线.json')['curves']
         if r['source']=='paired' and r['method']=='mdm'}
    max_error=0.;checked=0;derivatives=[]
    for row in data['curves']:
        if row['n'] in [7,15]:
            previous=old[row['beta'],row['n'],row['sample_id']]
            assert row['points']==previous['points'] and row['fit']==previous['fit']
        conditional,gradient,factors=profile_functions(row['observations'])
        points=[row['truth'],row['returned']]
        if row['n']==7 and row['sample_id']==SELECTED:points=row['points']
        for point in points:
            b,eta,sigma=conditional(point[0]);g=gradient(point[0])
            difference=max(abs(b-point[2]),abs(eta-point[3]),abs(g-point[1]))
            assert np.allclose([g,b,eta],point[1:4],rtol=1e-6,atol=1e-5)
            max_error=max(max_error,difference);checked+=1
        if row['fit']['extra']['solution_info']['root_solver']=='brent':
            assert abs(row['returned'][1]-.1)<1e-6
        beta,eta,sigma=conditional(500.)
        x=np.asarray(row['observations'])
        pseudo=(x-500.)/factors**(1/beta)
        slopes=-factors**(-1/beta)
        # Differentiate the sample standard deviation directly; its derivative
        # is bounded by the spread of the pseudo-scale slopes (Cauchy-Schwarz).
        analytic=float(np.dot(pseudo-eta,slopes-slopes.mean())/((len(x)-1)*sigma))
        h=.001
        fixed_fd=float((np.std((x-500.-h)/factors**(1/beta),ddof=1)
                        -np.std((x-500.+h)/factors**(1/beta),ddof=1))/(2*h))
        bound=float(np.std(slopes,ddof=1))
        assert abs(fixed_fd-analytic)<1e-7
        assert abs(analytic)<=bound+1e-12
        # Frozen inner optimization makes the numerical envelope identity
        # approximate. This tolerance is below 0.03% of the 0.10 criterion.
        assert abs(gradient(500.)-analytic)<3e-5
        derivatives.append(dict(beta=row['beta'],n=row['n'],conditional_beta=beta,
                                fixed_derivative_error=abs(fixed_fd-analytic),
                                profile_derivative_error=abs(gradient(500.)-analytic),
                                slope_spread=bound))
    ratio_error=0.
    for row in data['curves']:
        if row['n']!=7 or row['sample_id']!=SELECTED:continue
        conditional,_,factors=profile_functions(row['observations'])
        x=np.asarray(row['observations'])
        for point in [row['truth'],row['returned']]:
            beta,eta,sigma=conditional(point[0])
            pseudo=(x-point[0])/factors**(1/beta)
            observed=(x[-1]-point[0])/(x[0]-point[0])
            exact=(pseudo[-1]/pseudo[0])*(factors[-1]/factors[0])**(1/beta)
            ratio_error=max(ratio_error,abs(observed-exact))
            assert abs(observed-exact)<1e-10
    from PIL import Image
    for path in [FIGURE,TRANSFER]:
        assert sha(path)==qa['figure_hashes'][path.name]
        with Image.open(path) as image:assert image.size==(3240,3240)
    if 'restored_missing_figure1' in qa:
        restored=qa['restored_missing_figure1']
        assert sha(ROOT/restored['path'])==restored['sha256']
    text=REPORT.read_text(encoding='utf-8')
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}',text)]==list(range(1,34))
    assert '图5　MDM的位置选择与参数传递' in text
    metadata=read(FIGURE_QA)
    assert next(r for r in metadata['process_figures'] if r['method']=='mdm')==qa['figures']['gradient']
    assert metadata['mdm_parameter_transfer']==qa['figures']['transfer']
    qa['checks']=dict(profile_nodes_checked=checked,max_profile_difference=max_error,
                      n7_n15_curves_and_fits_unchanged=True,other_results_unchanged=True,
                      single_sample_id=SELECTED,no_new_random_samples=True,
                      archived_estimates_not_replaced=True,script_sha256=sha(__file__),
                      derivative_cases=len(derivatives),derivative_bound_verified=True,
                      max_fixed_derivative_error=max(r['fixed_derivative_error'] for r in derivatives),
                      max_profile_derivative_error=max(r['profile_derivative_error'] for r in derivatives),
                      max_exact_ratio_identity_error=ratio_error)
    qa['mechanism_checks']=[dict(beta=beta,n=n,
        median_conditional_beta=float(np.median([r['conditional_beta'] for r in derivatives if r['beta']==beta and r['n']==n])),
        median_slope_spread=float(np.median([r['slope_spread'] for r in derivatives if r['beta']==beta and r['n']==n])))
        for beta,n in CONDITIONS]
    write(QA,qa)
    print(f'PASS：{checked}个过程节点；原曲线、估计和其他结果保持一致。',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','render','revise','verify'])
    args=parser.parse_args();globals()[args.action]()


if __name__=='__main__':main()
