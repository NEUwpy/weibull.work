"""Two compact R00 figures for the six-section main report."""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];A=R/'附录';O=R/'图片'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.dpi':600})
methods=['LSE','LRE','MLE'];colors=['#0072B2','#D55E00','#009E73']
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
    assert all(r.get('project','R00')=='R00' for r in rr)
    return rr
def save(fig,name):
    fig.savefig(O/(name+'.png'),dpi=600);fig.savefig(O/(name+'.svg'),metadata={'Date':None});plt.close(fig)
    svg=O/(name+'.svg');svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n').encode())
rr=rows(A/'定位复核.csv');case=[next(r for r in rr if r['combination']=='W(2,100,500)' and int(r['n'])==15 and int(r['group'])==36 and r['method']==m) for m in methods]
fig,axs=plt.subplots(1,3,figsize=(10,3.3),layout='constrained')
for ax,field,label,limit in zip(axs,['beta','eta','gamma'],['形状','尺度','位置'],[13,7,1.2]):
    vals=[float(r[field+'_hat'])/float(r[field+'_truth']) for r in case]
    bars=ax.bar(methods,vals,color=colors,width=.55);ax.axhline(1,color='#666666',ls='--',lw=1.2)
    ax.set(title=label,ylabel='估计值 / 真值',ylim=(0,limit))
    for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+limit*.025,f'{v:.2f}',ha='center',va='bottom',fontsize=10)
save(fig,'图A_R00离谱估计现象')
f=rows(A/'机理验证/标记频率与参数条件.csv');combs=sorted({r['combination'] for r in f},key=lambda c:tuple(float(v) for v in c[2:-1].split(',')));ns=[7,15,30]
assert len(combs)==13 and len(f)==117
fig,axs=plt.subplots(1,3,figsize=(10,6),sharey=True,layout='constrained')
for ax,m in zip(axs,methods):
    v=np.array([[100*float(next(r['rate'] for r in f if r['combination']==c and int(r['n'])==n and r['method']==m)) for n in ns] for c in combs])
    im=ax.imshow(v,cmap='YlOrRd',vmin=0,vmax=40,aspect='auto',interpolation='nearest')
    ax.set(title=m,xticks=np.arange(3),xticklabels=ns,xlabel='样本量 n',yticks=np.arange(13),yticklabels=combs)
    ax.spines[['top','right','left','bottom']].set_visible(False);ax.tick_params(axis='y',length=0,labelsize=9)
    for i in range(13):
        for j in range(3):ax.text(j,i,f'{v[i,j]:.0f}%',ha='center',va='center',fontsize=8.5,color='white' if v[i,j]>=25 else '#333333')
axs[0].set_ylabel('参数组合 W(β,η,γ)')
fig.colorbar(im,ax=axs,shrink=.85,pad=.025,label='指定规则标记频率（%）')
save(fig,'图B_R00风险条件分布')
print('R00 main figures A/B written')
