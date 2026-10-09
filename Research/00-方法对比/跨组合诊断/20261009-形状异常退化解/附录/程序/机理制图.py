"""Draw four diagnostic questions from archived outputs; no simulation or estimation."""
from pathlib import Path
import csv, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
REPORT=Path(__file__).resolve().parents[2];DATA=REPORT/'附录/机理验证';O=REPORT/'图片'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.dpi':600})
colors=['#0072B2','#D55E00','#009E73','#CC79A7','#E69F00']
markers=['o','s','^','D','v'];styles=['-','--',':','-.',(0,(5,2,1,2))]
def rows(name):
    with (DATA/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(fig,name):
    fig.tight_layout();fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.svg'));plt.close(fig)
d=rows('全部标记与分层对照.csv');f=rows('标记频率与参数条件.csv')
fig,axs=plt.subplots(2,2,figsize=(9,6),sharex=True,sharey=True)
limit=max(float(r['warning_score']) for r in d);limit=np.ceil(limit/10)*10
for ax,(p,m) in zip(axs.flat,[('R00','LSE'),('R00','LRE'),('R00','MLE'),('R09','MLE')]):
    rr=[r for r in d if r['project']==p and r['method']==m]
    for flag,col,line,lab in [('True',colors[1],'-','标记记录'),('False',colors[0],'--','分层未标记对照')]:
        vals=np.sort([float(r['warning_score']) for r in rr if r['flag']==flag]);ax.step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',color=col,linestyle=line,lw=1.8,label=lab)
    ax.axvline(10,color='#666666',ls=':',lw=1.2,label='预警阈值10');ax.set(title=f'{p} · {m}',xlim=(0,limit),ylim=(0,1.01))
axs[0,0].legend(frameon=False,fontsize=9,loc='lower right');fig.supxlabel(r'样本预警分数 $S_0$');fig.supylabel('累积分布')
save(fig,'图4_只用样本的预警分离度')
fig,axs=plt.subplots(1,2,figsize=(9,3.5),sharey=True)
for ax,p in zip(axs,['R00','R09']):
    for mi,m in enumerate(['LSE','LRE','MLE'] if p=='R00' else ['MLE']):
        rr=[r for r in f if r['project']==p and r['method']==m];ns=sorted({int(r['n']) for r in rr});ys=[100*sum(int(r['flagged']) for r in rr if int(r['n'])==n)/sum(int(r['total']) for r in rr if int(r['n'])==n) for n in ns]
        ax.plot(ns,ys,'o-',color=colors[mi],label=m,lw=1.7,ms=4)
    ax.set(title=p,xlabel='样本量 n');ax.set_xticks(ns);ax.legend(frameon=False)
axs[0].set_ylabel('指定规则标记频率（%）');axs[0].set_ylim(bottom=0)
save(fig,'图5_标记频率随样本量')
fig,ax=plt.subplots(figsize=(5.5,3.5))
for ni,n in enumerate([7,10,15,20,50]):
    rr=[r for r in f if r['project']=='R09' and r['method']=='MLE' and int(r['n'])==n and r['combination'] in ['W(1.5,1000,500)','W(2,1000,500)','W(3,1000,500)','W(5,1000,500)']];rr.sort(key=lambda r:float(r['beta_truth']))
    ax.plot([float(r['beta_truth']) for r in rr],[100*float(r['rate']) for r in rr],marker=markers[ni],linestyle=styles[ni],color=colors[ni],lw=1.6,ms=4,label=f'n={n}')
ax.set(xlabel=r'真形状 $\beta_0$',ylabel='指定规则标记频率（%）',ylim=(0,None));ax.set_xticks([1.5,2,3,5]);ax.legend(frameon=False,ncol=2)
save(fig,'图6_同尺度位置下的形状与频率')
fig,ax=plt.subplots(figsize=(5.5,3.5))
for ni,n in enumerate([7,10,15,20,50]):
    rr=[r for r in f if r['project']=='R09' and r['method']=='MLE' and int(r['n'])==n and float(r['beta_truth'])==2];rr.sort(key=lambda r:float(r['eta_gamma_ratio']))
    ax.plot([float(r['eta_gamma_ratio']) for r in rr],[100*float(r['rate']) for r in rr],marker=markers[ni],linestyle=styles[ni],color=colors[ni],lw=1.6,ms=4,label=f'n={n}')
ax.set(xlabel=r'真尺度与真位置之比 $\eta_0/\gamma_0$',ylabel='指定规则标记频率（%）',ylim=(0,None));ax.set_xticks([.2,1/3,1,2]);ax.set_xticklabels(['0.2','1/3','1','2']);ax.legend(frameon=False,ncol=2)
save(fig,'图7_位置相对尺度与频率')
print('four figures PNG/SVG written',flush=True)
