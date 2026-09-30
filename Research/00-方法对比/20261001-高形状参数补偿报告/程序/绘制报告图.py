"""Nature-style report figures from saved data only; Python/Matplotlib exclusively."""
import json
from pathlib import Path
import numpy as np
from 连续形状实验 import mother, BETAS, NS, METHODS
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
OUT = BATCH / '结果'
DATA = OUT / '中间数据'
PRIMARY = ['mdm', 'lse', 'lre', 'wmle', 'mle']
NAMES = dict(mdm='MDM', lse='LSE', lre='LRE', wmle='WMLE', mle='MLE', lre_park='LRE Park')
COLORS = dict(mdm='#345D7E', lse='#589CA3', lre='#8A7398', wmle='#B27448', mle='#5F6570', lre_park='#A291AF')
SHAPE_COLORS = ['#A9BCCB', '#8EADBF', '#719DB3', '#568CA6', '#3F7794', '#2C6080', '#214A68']
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
    'font.size': 7, 'axes.titlesize': 7, 'axes.labelsize': 7, 'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.linewidth': .7,
    'axes.spines.right': False, 'axes.spines.top': False, 'axes.unicode_minus': False,
    'pdf.fonttype': 42, 'svg.fonttype': 'none', 'legend.frameon': False})
fits = json.loads((DATA / '实际估计.json').read_text(encoding='utf-8'))
summary = json.loads((DATA / '汇总.json').read_text(encoding='utf-8'))
curves = json.loads((DATA / '代表样本曲线.json').read_text(encoding='utf-8'))
manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
old = json.loads((HERE / '输入快照' / '原案例估计.json').read_text(encoding='utf-8'))


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=450, facecolor='white')
    plt.close(fig)


def tag(ax, label):
    ax.text(-.12, 1.10, label, transform=ax.transAxes, fontsize=8, weight='bold')


def get(beta, n, method):
    return next(s for s in summary['summary'] if s['beta'] == beta and s['n'] == n and s['method'] == method)


def legend_methods(fig, y=.99):
    fig.legend([Line2D([], [], color=COLORS[m], marker='o', ms=3, lw=1) for m in PRIMARY],
        [NAMES[m] for m in PRIMARY], ncol=5, loc='upper center', bbox_to_anchor=(.5, y), columnspacing=1.7)


def original_distributions():
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.3))
    params = [('beta_hat', 5, '形状参数 β', (0, 18)), ('eta_hat', 1000, '尺度参数 η', (0, 1800)),
              ('gamma_hat', 500, '位置参数 γ', (0, 1500))]
    rng = np.random.default_rng(8)
    for row, n in enumerate(NS):
        for col, (param, truth, title, lim) in enumerate(params):
            ax = axes[row, col]
            for i, m in enumerate(PRIMARY):
                values = np.array([r[param] for r in old if r['beta'] == 5 and r['n'] == n and r['method'] == m and r['converged']])
                ax.scatter(values, i+rng.uniform(-.16, .16, len(values)), s=5, color='#7992A5', alpha=.48, linewidths=0, zorder=1)
                box = ax.boxplot([values], positions=[i], orientation='horizontal', widths=.46, patch_artist=True,
                    showfliers=False, whis=(0, 100), manage_ticks=False,
                    medianprops=dict(color='#203E55', linewidth=1.3), boxprops=dict(facecolor='#D8E4EC', edgecolor='#56748B', linewidth=.7),
                    whiskerprops=dict(color='#56748B', linewidth=.6), capprops=dict(color='#56748B', linewidth=.6))
                for artist in box['boxes']:
                    artist.set_alpha(.8)
            ax.axvline(truth, ls='--', color='black', lw=.85, zorder=0)
            ax.set_xlim(lim); ax.set_ylim(4.6, -.6)
            ax.set_yticks(range(5))
            ax.set_yticklabels([f'{NAMES[m]} ({sum(r["converged"] for r in old if r["beta"] == 5 and r["n"] == n and r["method"] == m)}/50)' for m in PRIMARY] if col == 0 else [])
            ax.set_xlabel(title)
            if col == 0:
                ax.set_title(f'n = {n}', loc='left', weight='bold', pad=8)
            tag(ax, chr(97+row*3+col))
    fig.legend([Line2D([], [], color='black', ls='--', lw=.8), Line2D([], [], color='#203E55', lw=2),
                Line2D([], [], marker='o', ls='', color='#7992A5', ms=3)],
               ['真实参数', '箱体为中间50%，线为中位数', '每点为一组成功估计'],
               ncol=3, loc='upper center', bbox_to_anchor=(.53, .995))
    fig.subplots_adjust(left=.14, right=.98, top=.86, bottom=.10, wspace=.23, hspace=.55)
    save(fig, '图1_原案例参数分布')


def lower_tail():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={'width_ratios': [1.2, 1]})
    for n, color, marker in [(7, '#345D7E', 'o'), (15, '#B27448', 's')]:
        rr = [s for s in summary['tail'] if s['n'] == n]
        q = np.array([s['minimum_q'] for s in rr])
        axes[0].fill_between(BETAS, q[:, 1], q[:, 3], color=color, alpha=.14)
        axes[0].plot(BETAS, q[:, 2], marker=marker, ms=3, lw=1.2, color=color, label=f'n={n}，样本中位数')
        axes[0].plot(BETAS, [s['theoretical_mean_minimum'] for s in rr], color=color, ls=':', lw=1, label=f'n={n}，理论期望')
        axes[1].plot(BETAS, [s['theoretical_probability_minimum_above_1000'] for s in rr], marker=marker, ms=3, color=color, lw=1.2, label=f'n={n}')
    axes[0].axhline(500, ls='--', color='black', lw=.8)
    axes[0].text(4.5, 515, '真 γ=500', fontsize=6.5)
    axes[0].set_ylabel(r'最小观测值 $t_{(1)}$'); axes[0].set_ylim(440, 1290)
    axes[1].set_ylabel(r'全部观测大于1000的概率'); axes[1].set_ylim(0, 1)
    axes[0].set_title('最小观测逐渐远离真实位置', loc='left', pad=9)
    axes[1].set_title('“没有低于1000的观测”越来越常见', loc='left', pad=9)
    for i, ax in enumerate(axes):
        ax.set_xlabel('真实形状参数 β'); ax.set_xticks(BETAS); tag(ax, chr(97+i))
    axes[0].legend(loc='upper left', fontsize=5.7); axes[1].legend(loc='upper left')
    fig.subplots_adjust(left=.09, right=.985, bottom=.20, top=.84, wspace=.32)
    save(fig, '图2_形状与下尾信息')


def continuous_estimates():
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.7))
    params = [('beta_hat', None, '形状估计中位数'), ('eta_hat', 1000, '尺度估计中位数'), ('gamma_hat', 500, '位置估计中位数')]
    for row, n in enumerate(NS):
        for col, (param, truth, ylabel) in enumerate(params):
            ax = axes[row, col]
            for m in PRIMARY:
                ax.plot(BETAS, [get(b, n, m)[param+'_q'][2] for b in BETAS], color=COLORS[m], marker='o', ms=2.7, lw=1.15)
            if truth is None:
                ax.plot(BETAS, BETAS, color='black', lw=.8, ls='--')
            else:
                ax.axhline(truth, ls='--', color='black', lw=.8)
            ax.set_ylabel(ylabel); ax.set_xticks([2,3,4,5])
            if row == 1: ax.set_xlabel('真实形状参数 β')
            if col == 0: ax.set_title(f'n = {n}', loc='left', pad=8, weight='bold')
            tag(ax, chr(97+row*3+col))
    legend_methods(fig)
    fig.subplots_adjust(left=.09, right=.98, top=.86, bottom=.10, wspace=.42, hspace=.50)
    save(fig, '图3_连续形状估计变化')


def mdm_mechanism():
    fig = plt.figure(figsize=(7.2, 3.15))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2,1], wspace=.34)
    left, right = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    for n, color, marker in [(7, '#345D7E', 'o'), (15, '#B27448', 's')]:
        qq = np.array([get(b,n,'mdm')['criterion_at_truth_q'] for b in BETAS])
        left.fill_between(BETAS, qq[:,1], qq[:,3], color=color, alpha=.14)
        left.plot(BETAS, qq[:,2], marker=marker, ms=3.2, lw=1.2, color=color, label=f'n={n}')
    left.axhline(.1, ls='--', color='black', lw=.9)
    left.text(4.95,.104,'δ=0.10',ha='right',fontsize=6.5)
    left.set_xlabel('真实形状参数 β'); left.set_ylabel(r'真 γ=500 处的梯度 $g(500)$')
    left.set_xticks(BETAS); left.set_title('梯度在真位置处低于求解阈值',loc='left',pad=9)
    left.legend(loc='upper right'); left.set_ylim(-.10,.55)
    for beta, color in zip(BETAS, SHAPE_COLORS):
        pp=[r for r in curves if r['n']==7 and r['beta']==beta and r['method']=='mdm']
        right.plot([r['gamma'] for r in pp],[np.nan if r['criterion'] is None else r['criterion'] for r in pp],color=color,lw=1.1)
        sid=manifest['representatives']['7']
        fit=next(r for r in fits if r['n']==7 and r['beta']==beta and r['sample_id']==sid and r['method']=='mdm')
        if fit['converged']: right.scatter(fit['gamma_hat'],.1,color=color,s=13,marker='o')
    right.axhline(.1, ls='--', color='black', lw=.9); right.axvline(500, ls=':', color='black', lw=.8)
    right.set_xlim(300,1400); right.set_ylim(-.025,.22)
    right.set_xlabel('候选位置 γ'); right.set_ylabel(r'剖面标准差梯度 $g(\gamma)$')
    right.set_title(f'同一随机分位点，n=7，组#{sid}',loc='left',pad=9)
    right.annotate('β=2',xy=(next(r['gamma_hat'] for r in fits if r['n']==7 and r['beta']==2 and r['sample_id']==sid and r['method']=='mdm'),.1),xytext=(400,.18),
                   arrowprops=dict(arrowstyle='-',lw=.6), fontsize=6.5)
    right.annotate('β=5',xy=(next(r['gamma_hat'] for r in fits if r['n']==7 and r['beta']==5 and r['sample_id']==sid and r['method']=='mdm'),.1),xytext=(1120,.17),
                   arrowprops=dict(arrowstyle='-',lw=.6), fontsize=6.5)
    tag(left,'a');tag(right,'b')
    fig.legend([Line2D([],[],color=c,lw=1.4) for c in SHAPE_COLORS],[f'β={b:g}' for b in BETAS],
               ncol=7,loc='upper center',bbox_to_anchor=(.53,.995),columnspacing=1.3)
    fig.subplots_adjust(left=.10,right=.985,bottom=.18,top=.78)
    save(fig,'图4_MDM阈值与交点')


def other_criteria():
    fig,axes=plt.subplots(2,2,figsize=(7.2,4.7))
    source_rows=[]
    selections=[]
    limits={'lse':(1e-4,.1),'lre':(1e-4,.1),'wmle':(-.22,.22),'mle':(-.12,.06)}
    titles={'lse':'LSE：回归损失最小处','lre':'LRE：回归损失最小处','wmle':'WMLE：位置方程的零点','mle':'MLE：有限极大或 γ=0 边界'}
    for index,method in enumerate(['lse','lre','wmle','mle']):
        ax=axes.flat[index]
        minima=[]
        for beta,color in [(2.,SHAPE_COLORS[0]),(3.5,SHAPE_COLORS[3]),(5.,SHAPE_COLORS[-1])]:
            pp=[r for r in curves if r['n']==7 and r['beta']==beta and r['method']==method]
            xx=np.array([r['gamma'] for r in pp]); yy=np.array([np.nan if r['criterion'] is None else r['criterion'] for r in pp])
            ax.plot(xx,yy,color=color,lw=1)
            if method=='wmle':
                mask=np.array([r['J3_clamped'] for r in pp]);clamped=np.where(mask,yy,np.nan)
                ax.plot(xx,clamped,color='#B27448',ls=(0,(2,2)),lw=1)
            sid=manifest['representatives']['7']
            fit=next(r for r in fits if r['n']==7 and r['beta']==beta and r['sample_id']==sid and r['method']==method)
            if fit['converged']:
                actual=min(pp,key=lambda r:abs(r['gamma']-fit['gamma_hat']))
                if actual['criterion'] is not None:
                    ax.scatter(fit['gamma_hat'],actual['criterion'],s=13,color=color,zorder=4)
                    if method in ('lse','lre'):minima.append(actual['criterion'])
        historical=[r for r in old if r['beta']==5 and r['n']==7 and r['method']==method and r['converged']]
        center=np.median([r['gamma_hat'] for r in historical])
        chosen=min(historical,key=lambda r:(abs(r['gamma_hat']-center),r['sample_id']))
        selections.append(dict(method=method, sample_id=chosen['sample_id'], gamma_hat=chosen['gamma_hat'],
            selection='Original beta5 n7 successful gamma closest to method median; tie by id'))
        audit=json.loads((HERE/'输入快照'/'原案例核验.json').read_text(encoding='utf-8'))
        x=np.array(next(r['observations'] for r in audit['samples'] if r['beta_true']==5 and r['n']==7 and r['sample_id']==chosen['sample_id']))
        grid=np.unique(np.r_[np.linspace(0,x[0]*(1-1e-6),181),chosen['gamma_hat']])
        values=[mother.profile(x,method,float(g)) for g in grid]
        source_rows.extend(dict(method=method, beta=5, n=7, sample_id=chosen['sample_id'],
            gamma=float(g), criterion=p['value'] if p else None,
            conditional_beta=p['b'] if p else None, J3_clamped=p['clipped'] if p else False)
            for g,p in zip(grid,values))
        ax.plot(grid,[p['value'] if p else np.nan for p in values],color='#B27448',ls='--',lw=1.15)
        at=mother.profile(x,method,chosen['gamma_hat'])
        ax.scatter(chosen['gamma_hat'],at['value'],s=23,color='#B27448',marker='D',zorder=5)
        if method in ('lse','lre'):minima.append(at['value'])
        ax.axvline(500,ls=':',color='black',lw=.8)
        if method in ('lse','lre'):
            ax.set_yscale('log');ax.set_ylabel(r'回归损失 $1-r^2$（越低越好）')
        else:
            ax.axhline(0,ls='--',color='black',lw=.8)
            ax.set_ylabel(r'位置残差 $T_2$' if method=='wmle' else r'剖面分数 $1000\,U_\gamma/n$')
        ax.set_ylim((max(min(minima)*.55,1e-8),.15) if minima else limits[method]);ax.set_xlim(-20,1400);ax.set_xlabel('候选位置 γ')
        ax.set_title(titles[method],loc='left',pad=8);tag(ax,chr(97+index))
    fig.legend([Line2D([],[],color=c,lw=1.3) for c in [SHAPE_COLORS[0],SHAPE_COLORS[3],SHAPE_COLORS[-1]]]+[Line2D([],[],color='#B27448',ls='--',marker='D',ms=3,lw=1.2)],
               ['配对 β=2','配对 β=3.5','配对 β=5','原 β=5 案例：γ中位数附近的组'],
               ncol=2,loc='upper center',bbox_to_anchor=(.52,1.01),columnspacing=1.2)
    fig.subplots_adjust(left=.095,right=.98,top=.84,bottom=.10,hspace=.52,wspace=.36)
    save(fig,'图5_其他方法准则')
    mother.write_csv(DATA/'图5原案例曲线.csv',source_rows)
    mother.dump(DATA/'图5原案例选择.json',selections)


def compensation():
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.35),gridspec_kw={'width_ratios':[1.15,1]})
    ax,right=axes
    for method in PRIMARY:
        rr=[r for r in fits if r['beta']==5 and r['n']==7 and r['method']==method and r['converged']]
        ax.scatter([r['gamma_hat']-500 for r in rr],[r['eta_hat']-1000 for r in rr],s=9,alpha=.55,color=COLORS[method],linewidths=0)
    ax.plot([-500,1000],[500,-1000],ls='--',color='black',lw=.9)
    ax.axvline(0,color='.75',lw=.5);ax.axhline(0,color='.75',lw=.5)
    ax.set_xlim(-520,1050);ax.set_ylim(-1100,800)
    ax.set_xlabel(r'位置误差 $\hat{\gamma}-500$');ax.set_ylabel(r'尺度误差 $\hat{\eta}-1000$')
    ax.set_title('β=5，n=7：位置与尺度沿负方向补偿',loc='left',pad=9)
    ax.text(110,-980,r'$\Delta\eta=-\Delta\gamma$',fontsize=7)
    for i,method in enumerate(PRIMARY):
        s=get(5.,7,method)
        a,b=s['eta_error_free_q'][2],s['eta_error_fixed_q'][2]
        right.plot([a,b],[i,i],color=COLORS[method],lw=1.5)
        right.scatter([a],[i],color=COLORS[method],s=24,marker='o')
        right.scatter([b],[i],facecolor='white',edgecolor=COLORS[method],s=24,marker='o',zorder=3)
        right.text(max(a,b)+14,i,f'{s["conditional_pairs"]}组',va='center',fontsize=6)
    right.set_yticks(range(5),[NAMES[m] for m in PRIMARY]);right.set_ylim(4.6,-.6)
    right.set_xlabel('尺度绝对误差中位数');right.set_xlim(0,750)
    right.set_title('固定真实 γ 后，η 误差减小',loc='left',pad=9)
    right.legend([Line2D([],[],color='.3',marker='o',lw=0),Line2D([],[],color='.3',marker='o',markerfacecolor='white',lw=0)],
                 ['自由估计 γ','固定 γ=500'],loc='lower right',bbox_to_anchor=(1.02,-.32),fontsize=6)
    tag(ax,'a');tag(right,'b');legend_methods(fig)
    fig.subplots_adjust(left=.10,right=.985,bottom=.25,top=.79,wspace=.36)
    save(fig,'图6_参数补偿与固定位置')


def supplement():
    fig, axes=plt.subplots(1,2,figsize=(7.2,2.8))
    for ax,n in zip(axes,NS):
        for m in PRIMARY:
            ax.plot(BETAS,[get(b,n,m)['success']/50 for b in BETAS],color=COLORS[m],marker='o',ms=3,label=NAMES[m])
        ax.set_ylim(0,1.05);ax.set_xticks(BETAS);ax.set_xlabel('真实形状参数 β');ax.set_title(f'n={n}',loc='left')
    axes[0].set_ylabel('成功估计比例（分母50）');tag(axes[0],'a');tag(axes[1],'b');legend_methods(fig)
    fig.subplots_adjust(left=.10,right=.98,top=.78,bottom=.20,wspace=.25)
    save(fig,'补充图1_成功比例')
    fig, axes=plt.subplots(1,2,figsize=(7.2,2.8))
    for ax,n in zip(axes,NS):
        for m,label,color in [('lre','历史Bernard','#8A7398'),('lre_park','当前Park','#345D7E')]:
            qq=np.array([get(b,n,m)['gamma_hat_q'] for b in BETAS])
            ax.fill_between(BETAS,qq[:,1],qq[:,3],color=color,alpha=.12)
            ax.plot(BETAS,qq[:,2],color=color,marker='o',ms=3,label=label)
        ax.axhline(500,color='black',ls='--',lw=.8);ax.set_xticks(BETAS);ax.set_xlabel('真实形状参数 β');ax.set_title(f'n={n}',loc='left')
    axes[0].set_ylabel('位置估计中位数与中间50%范围');axes[1].legend();tag(axes[0],'a');tag(axes[1],'b')
    fig.subplots_adjust(left=.10,right=.98,top=.84,bottom=.20,wspace=.26)
    save(fig,'补充图2_LRE版本')


if __name__ == '__main__':
    original_distributions();lower_tail();continuous_estimates();mdm_mechanism();other_criteria();compensation();supplement()
    print('EXPORTED 6 main figures and 2 supplementary figures, PNG/PDF/SVG')
