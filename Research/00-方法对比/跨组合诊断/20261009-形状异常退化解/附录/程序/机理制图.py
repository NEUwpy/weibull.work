"""Draw R00-only diagnostic figures from existing results; no estimator run."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
REPORT=Path(__file__).resolve().parents[2];DATA=REPORT/'附录/机理验证';O=REPORT/'图片'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.dpi':600})
colors=['#0072B2','#D55E00','#009E73'];markers=['o','s','^'];styles=['-','--',':'];methods=['LSE','LRE','MLE'];ns=[7,15,30]
def rows(name):
    with (DATA/name).open(encoding='utf-8-sig',newline='') as f:r=list(csv.DictReader(f))
    assert all(q['project']=='R00' for q in r)
    return r
def save(fig,name):
    fig.tight_layout();fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.svg'),metadata={'Date':None});plt.close(fig)
    svg=O/(name+'.svg');svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n').encode())
d=rows('全部标记与分层对照.csv');f=rows('标记频率与参数条件.csv')
assert len(d)==3739 and len(f)==117
# Fig 4: same score axes and full observed range for the three method comparisons.
fig,axs=plt.subplots(1,3,figsize=(10.5,3.7),sharex=True,sharey=True)
limit=np.ceil(max(float(r['warning_score']) for r in d)/10)*10
for ax,m in zip(axs,methods):
    rr=[r for r in d if r['method']==m]
    for flag,col,line,lab in [('True',colors[1],'-','标记记录'),('False',colors[0],'--','分层未标记对照')]:
        vals=np.sort([float(r['warning_score']) for r in rr if r['flag']==flag]);ax.step(vals,np.arange(1,len(vals)+1)/len(vals),where='post',color=col,linestyle=line,lw=1.8,label=lab)
    ax.axvline(10,color='#666666',ls=':',lw=1.2,label='预警阈值10');ax.set(title=m,xlim=(0,limit),ylim=(0,1.01),xlabel=r'样本预警分数 $S_0$')
axs[0].set_ylabel('累积分布');axs[0].legend(frameon=False,fontsize=8,loc='lower right')
save(fig,'图4_只用样本的预警分离度')
# Fig 5: one R00 aggregate per method and n; denominator 13 x 50 = 650.
fig,ax=plt.subplots(figsize=(6.2,3.7))
for mi,m in enumerate(methods):
    rr=[r for r in f if r['method']==m]
    ys=[100*sum(int(r['flagged']) for r in rr if int(r['n'])==n)/sum(int(r['total']) for r in rr if int(r['n'])==n) for n in ns]
    ax.plot(ns,ys,marker=markers[mi],linestyle=styles[mi],color=colors[mi],label=m,lw=1.7,ms=5)
ax.set(xlabel='样本量 n',ylabel='指定规则标记频率（%）',xticks=ns,ylim=(0,16));ax.legend(frameon=False)
save(fig,'图5_标记频率随样本量')
# Figs 6/7: matching linear axes; every plotted cell has 50 stored samples.
fig,axs=plt.subplots(1,3,figsize=(10.5,3.7),sharex=True,sharey=True)
chosen=['W(1.5,100,500)','W(2,100,500)','W(3,100,500)','W(5,100,500)']
for ax,m in zip(axs,methods):
    for ni,n in enumerate(ns):
        rr=[r for r in f if r['method']==m and int(r['n'])==n and r['combination'] in chosen];rr.sort(key=lambda r:float(r['beta_truth']));assert len(rr)==4
        ax.plot([float(r['beta_truth']) for r in rr],[100*float(r['rate']) for r in rr],marker=markers[ni],linestyle=styles[ni],color=colors[ni],lw=1.6,ms=4,label=f'n={n}')
    ax.set(title=m,xlabel=r'真形状 $\beta_0$',xticks=[1.5,2,3,5],ylim=(0,32))
axs[0].set_ylabel('指定规则标记频率（%）');axs[-1].legend(frameon=False)
save(fig,'图6_同尺度位置下的形状与频率')
fig,axs=plt.subplots(1,3,figsize=(10.5,3.7),sharex=True,sharey=True)
for ax,m in zip(axs,methods):
    for ni,n in enumerate(ns):
        rr=[r for r in f if r['method']==m and int(r['n'])==n and float(r['beta_truth'])==2];rr.sort(key=lambda r:float(r['eta_gamma_ratio']));assert len(rr)==4
        ax.plot([float(r['eta_gamma_ratio']) for r in rr],[100*float(r['rate']) for r in rr],marker=markers[ni],linestyle=styles[ni],color=colors[ni],lw=1.6,ms=4,label=f'n={n}')
    ax.set(title=m,xlabel=r'真尺度与真位置之比 $\eta_0/\gamma_0$',xticks=[.2,1/3,1,2],ylim=(0,20));ax.set_xticklabels(['0.2','1/3','1','2'],rotation=60,ha='right')
axs[0].set_ylabel('指定规则标记频率（%）');axs[-1].legend(frameon=False)
save(fig,'图7_位置相对尺度与频率')
print('R00 figures 4-7: PNG and SVG written')
