"""Compare archived MDM traces without modifying samples or estimates."""
from pathlib import Path
import csv
import json
import sys
import os
import hashlib

import numpy as np
from scipy.optimize import minimize_scalar

# Reuse an available same-version Python plotting library; no installation or environment edits.
sys.path.append(r'C:\Users\36089\AppData\Local\hermes\hermes-agent\venv\Lib\site-packages')
WORK = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(WORK / 'mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

ROOT = Path('D:/weibull')
sys.path.insert(0, str(ROOT/'python'))
from methods.mdm import MDM

BASE = ROOT/'docs/临时任务/工作输出'
SOURCES = {2:BASE/'20260826-gamma500-six-figures-table',
           5:BASE/'20260906-W5-parameters/W5-1000-500'}
OUT = ROOT/'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260929-MDM形状2与5梯度对比'
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
    'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':.8,'pdf.fonttype':42,'svg.fonttype':'none','legend.frameon':False})

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def gradient_at(x,g):
    z=-np.log1p(-(np.arange(1,len(x)+1)-.3)/(len(x)+.4))
    def profile(loc):
        res=minimize_scalar(lambda b:np.std((x-loc)/z**(1/b),ddof=1),bounds=(.1,15),method='bounded')
        return float(res.fun)
    h=max(abs(x[0]),1)*1e-5
    return (profile(g+h)-profile(g-h))/(2*h)

data={}; provenance=[]
for beta,source in SOURCES.items():
    samples={}; curves={}
    for r in read_csv(source/'samples.csv'):
        key=(int(r['sample_size']),int(r['sample_id']))
        samples.setdefault(key,[]).append(float(r['value']))
    for r in read_csv(source/'gradient_curves.csv'):
        key=(int(r['sample_size']),int(r['sample_id']))
        curves.setdefault(key,[]).append((float(r['gamma_candidate']),float(r['std_gradient'])))
    rows=read_csv(source/'mdm_estimates.csv')
    for n in [7,15]:
        estimates=[r for r in rows if int(r['sample_size'])==n and abs(float(r['offset'])-.1)<1e-9]
        estimates.sort(key=lambda r:int(r['sample_id']))
        assert len(estimates)==50
        gh=np.array([float(r['gamma_hat']) for r in estimates])
        bh=np.array([float(r['beta_hat']) for r in estimates])
        chosen=min(estimates,key=lambda r:(abs(float(r['gamma_hat'])-np.median(gh)),int(r['sample_id'])))
        sid=int(chosen['sample_id']); sample=np.array(samples[(n,sid)])
        solver=MDM(sample)
        result=solver.run(trace=True,offset=.1,gamma_steps=1200)
        assert result[-1] is True
        assert abs(result[2]-float(chosen['gamma_hat']))<1e-4
        assert abs(result[0]-float(chosen['beta_hat']))<1e-4
        selected=sorted([p for p in solver.trace_data['grad_gamma_curve'] if not p.get('virtual')],key=lambda p:p['gamma'])
        all_curves=[np.array(sorted(curves[(n,i)])) for i in range(1,51)]
        at_truth=[gradient_at(np.array(samples[(n,i)]),500.) for i in range(1,51)]
        record={'beta_true':beta,'eta_true':1000,'gamma_true':500,'n':n,'groups':50,
                'selected_sample_id':sid,'selected_sample':sample.tolist(),'selected_estimate':list(result[:3]),
                'selection':'minimum absolute distance to median gamma_hat, tie by sample_id',
                'median_gamma_hat':float(np.median(gh)),'median_beta_hat':float(np.median(bh)),
                'median_gradient_at_true_gamma':float(np.median(at_truth)),
                'gradient_at_true_gamma_below_delta_count':int(sum(v<.1 for v in at_truth)),
                'source_directory':str(source),'source_sha256':{f:hashlib.sha256((source/f).read_bytes()).hexdigest()
                    for f in ['samples.csv','gradient_curves.csv','mdm_estimates.csv']},
                'selected_root_gradient':min(selected,key=lambda p:abs(p['gamma']-result[2]))['gradient']}
        provenance.append(record)
        data[(n,beta)]={'all':all_curves,'selected':selected,'record':record,'result':result}
        print(json.dumps({k:v for k,v in record.items() if k not in ['source_sha256','selected_sample','source_directory']}),flush=True)

def draw(zoom):
    fig,axes=plt.subplots(2,2,figsize=(11,7.6),sharex=True,sharey=True)
    fig.subplots_adjust(left=.092,right=.982,bottom=.14,top=.86,wspace=.14,hspace=.25)
    ylim=(-.05,.30) if zoom else (-.8,1.6)
    colors={2:'#296EA3',5:'#C47725'}
    for row,n in enumerate([7,15]):
        for col,beta in enumerate([2,5]):
            ax=axes[row,col]; d=data[(n,beta)]; rec=d['record']; color=colors[beta]
            ax.set_xlim(0,1500); ax.set_ylim(*ylim)
            for curve in d['all']:
                ax.plot(curve[:,0],curve[:,1],color='#858C94',lw=.65,alpha=.37,zorder=1)
            p=d['selected']
            ax.plot([v['gamma'] for v in p],[v['gradient'] for v in p],color=color,lw=2,zorder=4)
            ax.axhline(0,color='#91969C',lw=.7,zorder=0)
            ax.axhline(.1,color='#AD3D48',lw=1.35,ls=(0,(7,3,1.5,3)),zorder=3)
            ax.axvline(500,color='#3F454B',lw=1.15,ls=(0,(4,3)),zorder=3)
            gh=d['result'][2]
            rootgrad=rec['selected_root_gradient']
            ax.plot(gh,rootgrad,'o',ms=5,mfc='white',mec=color,mew=1.4,zorder=5)
            ax.vlines(gh,ylim[0],rootgrad,color=color,lw=.9,ls=':',zorder=3)
            ax.set_title(f'{"abcd"[row*2+col]}   形状参数 β = {beta}，样本量 n = {n}',loc='left',fontsize=11,pad=10)
            ax.text(.97,.95,f'真实 γ 处梯度 < 0.1：{rec["gradient_at_true_gamma_below_delta_count"]}/50',
                    ha='right',va='top',transform=ax.transAxes,fontsize=9,color='#353B41',
                    bbox={'fc':'white','ec':'none','alpha':.88,'pad':2})
            ax.text(.97,.83,'代表样本：'+rf'$\hat{{\gamma}}={gh:.1f}$，$\hat{{\beta}}={d["result"][0]:.2f}$',
                    ha='right',va='top',transform=ax.transAxes,fontsize=9,color=color,
                    bbox={'fc':'white','ec':'none','alpha':.88,'pad':2})
            ax.xaxis.set_major_locator(MultipleLocator(250))
            ax.yaxis.set_major_locator(MultipleLocator(.05 if zoom else .4))
            ax.tick_params(direction='in',labelsize=9)
            if row==1: ax.set_xlabel('候选位置参数 γ',labelpad=8)
            if col==0: ax.set_ylabel('MDM 梯度 g(γ) = dS(γ)/dγ',labelpad=9)
    handles=[Line2D([0],[0],color='#858C94',lw=1,label='全部50组样本'),
             Line2D([0],[0],color='#296EA3',lw=2,label='β=2 代表样本'),
             Line2D([0],[0],color='#C47725',lw=2,label='β=5 代表样本'),
             Line2D([0],[0],color='#AD3D48',ls='-.',lw=1.3,label='偏移量 δ=0.10'),
             Line2D([0],[0],color='#3F454B',ls='--',lw=1.1,label='真实位置 γ=500')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.955),ncol=5,fontsize=9,
               columnspacing=1.35,handlelength=2.6)
    fig.text(.5,.048,'尺度参数 η=1000；沿用历史样本，两种形状使用不同随机种子。\n圆点为代表样本的 δ=0.10 交点；超出纵轴范围的曲线截断显示。',
             ha='center',va='center',fontsize=9,color='#454B52',linespacing=1.7)
    name='MDM梯度对比_形状2与5_阈值附近放大' if zoom else 'MDM梯度对比_形状2与5_完整纵轴'
    fig.savefig(OUT/f'{name}.png',dpi=240)
    fig.savefig(OUT/f'{name}.pdf')
    assert len(fig.axes)==4
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    # Text axes annotations and titles must lie within the canvas.
    for ax in axes.flat:
        for txt in ax.texts+[ax.title,ax._left_title]:
            bb=txt.get_window_extent(renderer)
            assert bb.x0>=0 and bb.y0>=0 and bb.x1<=fig.bbox.width and bb.y1<=fig.bbox.height
    plt.close(fig)
    print('SAVED',str(OUT/f'{name}.png'),flush=True)

draw(False); draw(True)
(WORK/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
with (WORK/'selected_curve_data.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(['beta_true','n','sample_id','gamma','gradient','best_beta','best_eta'])
    for (n,beta),d in data.items():
        for p in d['selected']:
            w.writerow([beta,n,d['record']['selected_sample_id'],p['gamma'],p['gradient'],p['best_beta'],p['best_eta']])
