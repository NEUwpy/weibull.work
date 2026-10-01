"""Supplementary figures from saved data; main figures use 绘制逐法分析图.py."""
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


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        path = OUT / f'{name}.{ext}'
        fig.savefig(path, dpi=450, facecolor='white')
        if ext == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)


def tag(ax, label):
    ax.text(-.12, 1.10, label, transform=ax.transAxes, fontsize=8, weight='bold')


def get(beta, n, method):
    return next(s for s in summary['summary'] if s['beta'] == beta and s['n'] == n and s['method'] == method)


def legend_methods(fig, y=.99):
    fig.legend([Line2D([], [], color=COLORS[m], marker='o', ms=3, lw=1) for m in PRIMARY],
        [NAMES[m] for m in PRIMARY], ncol=5, loc='upper center', bbox_to_anchor=(.5, y), columnspacing=1.7)




def lower_tail():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={'width_ratios': [1.2, 1]})
    for n, color, marker in [(7, '#345D7E', 'o'), (15, '#B27448', 's')]:
        rr = [s for s in summary['tail'] if s['n'] == n]
        q = np.array([s['minimum_q'] for s in rr])
        axes[0].fill_between(BETAS, q[:, 1], q[:, 3], color=color, alpha=.14)
        axes[0].plot(BETAS, q[:, 2], marker=marker, ms=3, lw=1.2, color=color, label=f'n={n}')
        axes[0].plot(BETAS, [s['theoretical_mean_minimum'] for s in rr], color=color, ls=':', lw=1)
        axes[1].plot(BETAS, [s['theoretical_probability_minimum_above_1000'] for s in rr], marker=marker, ms=3, color=color, lw=1.2, label=f'n={n}')
    axes[0].axhline(500, ls='--', color='black', lw=.8)
    axes[0].set_ylabel(r'最小观测值 $t_{(1)}$'); axes[0].set_ylim(440, 1290)
    axes[1].set_ylabel(r'全部观测大于1000的概率'); axes[1].set_ylim(0, 1)
    for i, ax in enumerate(axes):
        ax.set_xlabel('真实形状参数 β'); ax.set_xticks(BETAS); tag(ax, chr(97+i))
    axes[1].legend(loc='upper left')
    fig.subplots_adjust(left=.09, right=.985, bottom=.20, top=.84, wspace=.32)
    save(fig, '补充图3_形状与下尾信息')


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
    save(fig, '补充图4_连续形状估计变化')






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
    ax.set_title('β=5，n=7',loc='left',pad=9)
    for i,method in enumerate(PRIMARY):
        s=get(5.,7,method)
        a,b=s['eta_error_free_q'][2],s['eta_error_fixed_q'][2]
        right.plot([a,b],[i,i],color=COLORS[method],lw=1.5)
        right.scatter([a],[i],color=COLORS[method],s=24,marker='o')
        right.scatter([b],[i],facecolor='white',edgecolor=COLORS[method],s=24,marker='o',zorder=3)
    right.set_yticks(range(5),[NAMES[m] for m in PRIMARY]);right.set_ylim(4.6,-.6)
    right.set_xlabel('尺度绝对误差中位数');right.set_xlim(0,750)
    tag(ax,'a');tag(right,'b');legend_methods(fig)
    fig.subplots_adjust(left=.10,right=.985,bottom=.25,top=.79,wspace=.36)
    save(fig,'补充图5_参数补偿与固定位置')


def supplement():
    fig, axes=plt.subplots(1,2,figsize=(7.2,2.8))
    for ax,n in zip(axes,NS):
        for m in PRIMARY:
            ax.plot(BETAS,[get(b,n,m)['success']/50 for b in BETAS],color=COLORS[m],marker='o',ms=3,label=NAMES[m])
        ax.set_ylim(0,1.05);ax.set_xticks(BETAS);ax.set_xlabel('真实形状参数 β');ax.set_title(f'n={n}',loc='left')
    axes[0].set_ylabel('成功估计比例');tag(axes[0],'a');tag(axes[1],'b');legend_methods(fig)
    fig.subplots_adjust(left=.10,right=.98,top=.78,bottom=.20,wspace=.25)
    save(fig,'补充图1_成功比例')
    fig, axes=plt.subplots(1,2,figsize=(7.2,2.8))
    for ax,n in zip(axes,NS):
        for m,label,color in [('lre','LRE','#8A7398'),('lre_park','LRE Park','#345D7E')]:
            qq=np.array([get(b,n,m)['gamma_hat_q'] for b in BETAS])
            ax.fill_between(BETAS,qq[:,1],qq[:,3],color=color,alpha=.12)
            ax.plot(BETAS,qq[:,2],color=color,marker='o',ms=3,label=label)
        ax.axhline(500,color='black',ls='--',lw=.8);ax.set_xticks(BETAS);ax.set_xlabel('真实形状参数 β');ax.set_title(f'n={n}',loc='left')
    axes[0].set_ylabel('位置估计中位数');axes[1].legend();tag(axes[0],'a');tag(axes[1],'b')
    fig.subplots_adjust(left=.10,right=.98,top=.84,bottom=.20,wspace=.26)
    save(fig,'补充图2_LRE版本')



if __name__ == "__main__":
    lower_tail(); continuous_estimates(); compensation(); supplement()
    print("EXPORTED 5 supplementary figures, PNG/PDF/SVG")
