"""Summarize observed fits, compute real diagnostics, and make report figures."""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import numpy as np
from scipy.special import gamma as gamma_fn

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
DATA = BATCH/'数据'
FIG = BATCH/'图'
sys.path.insert(0,str(HERE))
import diagnostic_profiles as diag
from studies.common.sample import generate_sample
from studies.common.metrics import check_status
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

METHODS=['mdm','lse','lre_park','wmle','mle']
HIST_METHODS=['mdm','lse','lre','lre_park','wmle','mle']
LABEL={'mdm':'MDM δ=0.10','lse':'LSE','lre':'LRE（旧 Bernard）','lre_park':'LRE（Park）','wmle':'WMLE','mle':'MLE'}
COL={'mdm':'#0072B2','lse':'#009E73','lre':'#777777','lre_park':'#7B61A8','wmle':'#D55E00','mle':'#B08A18'}
BETAS=[2.,2.5,3.,3.5,4.,4.5,5.]
BLUE='#0072B2'; ORANGE='#D55E00'; TRUE='#333333'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
 'font.size':10,'axes.unicode_minus':False,'svg.fonttype':'none','pdf.fonttype':42,
 'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})

def readj(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def writecsv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(fig,name):
    fig.savefig(FIG/f'{name}.png',dpi=220,facecolor='white',bbox_inches='tight')
    fig.savefig(FIG/f'{name}.svg',facecolor='white',bbox_inches='tight')
    fig.savefig(FIG/f'{name}.pdf',facecolor='white',bbox_inches='tight')
    svg=FIG/f'{name}.svg'
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)
def subset(rows,b,n,m):
    return [r for r in rows if r['beta']==b and r['n']==n and r['method']==m]
def valid(rows): return [r for r in rows if r['valid']]
def q(rows,k,ps=(10,25,50,75,90)):
    return [float(v) for v in np.percentile([r[k] for r in rows],ps)]
def cdf(t,b,e,g):
    return -np.expm1(-np.maximum((np.asarray(t)-g)/e,0.)**b)
def summary(rows):
    ss=[]
    for b in sorted(set(r['beta'] for r in rows)):
        for n in (7,15):
            for m in HIST_METHODS:
                rr=subset(rows,b,n,m)
                if not rr: continue
                v=valid(rr); paired=[r for r in v if r.get('conditional_eta') is not None]
                s={'beta':b,'n':n,'method':m,'total':len(rr),'valid':len(v),'failed':len(rr)-len(v),
                   'joint_high_gamma_low_eta':sum(r['gamma_hat']>500 and r['eta_hat']<1000 for r in v),
                   'gamma_zero':sum(r['gamma_hat']==0 for r in v)}
                for k in ['beta_hat','eta_hat','gamma_hat']:
                    for pp,value in zip([10,25,50,75,90],q(v,k)):
                        s[f'{k}_p{pp}']=value
                    truth={'beta_hat':b,'eta_hat':1000,'gamma_hat':500}[k]
                    s[f'{k}_mean_error']=float(np.mean([r[k]-truth for r in v]))
                s['paired_fixed_gamma']=len(paired)
                s['eta_free_med_abs_error']=float(np.median([abs(r['eta_hat']-1000) for r in paired])) if paired else None
                s['eta_fixed_med_abs_error']=float(np.median([abs(r['conditional_eta']-1000) for r in paired])) if paired else None
                s['gamma_plus_eta_med_abs_error']=float(np.median([abs(r['gamma_hat']+r['eta_hat']-1500) for r in v]))
                ss.append(s)
    return ss

def compute():
    hist=readj(DATA/'历史'/'实际估计.json')
    for r in hist:r['valid']=bool(r['converged'])
    cache=DATA/'扫描诊断.json'
    if cache.exists(): scan=readj(cache)
    else:
        scan=[]
        for b in BETAS:
            for n in (7,15):
                path=DATA/'扫描'/f'b{b:g}_n{n}'/'results.csv'
                with path.open(encoding='utf-8') as f:rr=list(csv.DictReader(f))
                samples={rid:generate_sample(b,1000.,500.,n,rid,seed=2026100101) for rid in range(100)}
                for r in rr:
                    m=r['method_id'];rid=int(r['repeat_id']);x=samples[rid]
                    cond=diag.profile(x,m,500.)
                    a={'beta':b,'n':n,'method':m,'sample_id':rid+1,
                       'valid':r['status']=='success','converged':r['converged'].lower()=='true','status':r['status'],
                       'sample_min':float(x[0]),'conditional_eta':cond['eta'] if cond else None,
                       'conditional_beta':cond['b'] if cond else None,'criterion_at_truth':cond['value'] if cond else None}
                    for k in ('beta_hat','eta_hat','gamma_hat'):
                        a[k]=float(r[k]) if r[k] not in ('','None') else None
                    assert a['valid']==(r['status']=='success')
                    scan.append(a)
                print(f'diagnostics beta={b:g} n={n}',flush=True)
        dump(cache,scan)
    sh=summary(hist);sc=summary(scan)
    dump(DATA/'报告统计.json',{'historical':sh,'scan':sc})
    writecsv(DATA/'历史估计分布.csv',sh);writecsv(DATA/'连续扫描统计.csv',sc)
    return hist,scan,sh,sc

def fig1(hist):
    samples=readj(DATA/'历史'/'输入核验.json')['samples']
    fig,axs=plt.subplots(1,2,figsize=(11.4,4.2),sharex=True,sharey=True)
    t=np.linspace(450,2100,900)
    for ax,n in zip(axs,(7,15)):
        x=np.sort(np.concatenate([r['observations'] for r in samples if r['beta_true']==5 and r['n']==n]))
        ax.step(x,np.arange(1,len(x)+1)/len(x),where='post',color=BLUE,lw=1.8,label=f'保存样本的经验分布（{len(x)}点）')
        ax.plot(t,cdf(t,5,1000,500),color=TRUE,lw=1.8,label='生成设定 W(5,1000,500)')
        ax.plot(t,cdf(t,5,500,1000),color=ORANGE,lw=1.8,ls='--',label='单纯互换 W(5,500,1000)')
        ax.axvline(500,color=TRUE,ls=':',lw=1);ax.axvline(1000,color=ORANGE,ls=':',lw=1)
        ax.set_title(f'n={n}，50组独立样本',loc='left');ax.set_xlabel('寿命观测值 t')
        ax.set_xlim(450,2100);ax.set_ylim(0,1.03)
    axs[0].set_ylabel('累计概率 F(t)');axs[1].legend(loc='lower right',fontsize=8.5)
    fig.tight_layout();save(fig,'F01_样本来自正确分布')

def fig2(hist):
    fig,axs=plt.subplots(2,3,figsize=(12.3,7.5))
    specs=[('beta_hat',5,'形状 β：真值 5',(-.5,13.5)),('eta_hat',1000,'尺度 η：真值 1000',(-80,1800)),('gamma_hat',500,'位置 γ：真值 500',(-80,1450))]
    for ri,n in enumerate((7,15)):
        for ci,(k,truth,title,lim) in enumerate(specs):
            ax=axs[ri,ci]
            for j,m in enumerate(HIST_METHODS):
                v=valid(subset(hist,5,n,m));vals=q(v,k)
                ax.plot([vals[0],vals[4]],[j,j],color=COL[m],lw=1.3)
                ax.plot([vals[1],vals[3]],[j,j],color=COL[m],lw=7,solid_capstyle='butt')
                ax.plot(vals[2],j,'o',color=COL[m],ms=5,mec='white',mew=.6)
                text=f'{vals[2]:.1f}' if k=='beta_hat' else f'{vals[2]:.0f}'
                ax.annotate(text,(vals[2],j),xytext=(0,9),textcoords='offset points',ha='center',fontsize=8,color=COL[m])
            ax.axvline(truth,color=TRUE,ls='--',lw=1.1);ax.set_xlim(*lim);ax.set_ylim(5.7,-.65)
            ax.set_yticks(range(6))
            ax.set_yticklabels([LABEL[m]+f'  {len(valid(subset(hist,5,n,m)))}/50' for m in HIST_METHODS] if ci==0 else [])
            ax.set_title(title+f'；n={n}',loc='left',fontsize=11)
            ax.grid(axis='x',alpha=.16)
    fig.tight_layout(h_pad=2.1,w_pad=1);save(fig,'F02_三参数估计集中范围')

def fig3(sc):
    fig,axs=plt.subplots(3,2,figsize=(11.4,9),sharex=True)
    for ci,n in enumerate((7,15)):
        for ri,k in enumerate(('beta_hat','eta_hat','gamma_hat')):
            ax=axs[ri,ci]
            for m in METHODS:
                rr=[next(s for s in sc if s['beta']==b and s['n']==n and s['method']==m) for b in BETAS]
                ax.plot(BETAS,[s[k+'_p50'] for s in rr],color=COL[m],marker='o',ms=3.5,lw=1.7,label=LABEL[m])
            if ri==0:ax.plot(BETAS,BETAS,color=TRUE,ls='--',lw=1,label='真值')
            else:ax.axhline(1000 if ri==1 else 500,color=TRUE,ls='--',lw=1)
            ax.set_ylabel({'beta_hat':'形状估计中位数','eta_hat':'尺度估计中位数','gamma_hat':'位置估计中位数'}[k])
            ax.set_title(f'n={n}',loc='left');ax.set_xticks(BETAS);ax.grid(alpha=.16)
            if ri==0:ax.set_ylim(1,8)
            if ri==1:ax.set_ylim(300,1500)
            if ri==2:ax.set_ylim(-30,1100)
            if ri==2:ax.set_xlabel('真实形状参数 β')
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.52,1.01),ncol=3,fontsize=9)
    fig.tight_layout(rect=(0,0,1,.945));save(fig,'F03_偏移随真实形状变化')

def fig4():
    b=np.linspace(2,5,151)
    fig,axs=plt.subplots(1,2,figsize=(11.4,4.2))
    for n,color in [(7,ORANGE),(15,BLUE)]:
        mean=500+1000*gamma_fn(1+1/b)*n**(-1/b)
        axs[0].plot(b,mean,color=color,lw=2,label=f'n={n}')
        axs[1].plot(b,np.exp(-n*.5**b)*100,color=color,lw=2,label=f'n={n}')
        for bx in (2,5):
            yy=500+1000*float(gamma_fn(1+1/bx))*n**(-1/bx)
            axs[0].plot(bx,yy,'o',color=color);axs[0].annotate(f'{yy:.0f}',(bx,yy),xytext=(-20 if bx==5 else 6,7),textcoords='offset points',color=color,fontsize=9)
    axs[0].axhline(500,color=TRUE,ls='--',lw=1);axs[0].text(2.08,515,'真位置 γ=500',fontsize=9)
    axs[0].axhline(1000,color='0.65',ls=':',lw=1);axs[0].set_ylim(470,1200)
    axs[0].set_ylabel('一组样本最小值的理论期望');axs[0].set_title('样本最小值逐渐远离真实支持起点',loc='left')
    axs[1].set_ylabel('整组观测均大于 1000 的概率（%）');axs[1].set_ylim(0,100)
    axs[1].set_title('下尾缺少观测的概率随 β 上升',loc='left')
    for ax in axs:ax.set_xlabel('真实形状参数 β');ax.set_xticks(BETAS);ax.legend(loc='upper left',fontsize=9)
    fig.tight_layout();save(fig,'F04_高形状时下尾信息减弱')

def reps(hist):
    selected=[]
    for m in METHODS:
        for b in (2,5):
            v=valid(subset(hist,b,7,m));med=float(np.median([r['gamma_hat'] for r in v]))
            r=min(v,key=lambda r:(abs(r['gamma_hat']-med),r['sample_id']))
            selected.append({'method':m,'beta':b,'n':7,'sample_id':r['sample_id'],
                            'gamma_hat':r['gamma_hat'],'eta_hat':r['eta_hat'],'beta_hat':r['beta_hat'],
                            'pool_valid':len(v),'median_gamma':med})
    dump(DATA/'代表样本.json',selected)
    return selected

def realcurve(samples,pick,method):
    x=np.array(next(r['observations'] for r in samples if r['beta_true']==pick['beta'] and r['n']==7 and r['sample_id']==pick['sample_id']))
    hi=float(x[0])*(1-1e-7)
    grid=np.unique(np.r_[np.linspace(0,hi,241),500.,pick['gamma_hat']])
    out=[]
    for g in grid:
        p=diag.profile(x,method,float(g))
        out.append({'gamma':float(g),**p} if p else {'gamma':float(g),'b':None,'eta':None,'value':None,'ll':None,'clipped':False})
    return x,out

def fig5(hist,scan,selected):
    fig,axs=plt.subplots(1,2,figsize=(11.4,4.4))
    stats=[]
    for n,color in [(7,ORANGE),(15,BLUE)]:
        vals=[]
        for b in BETAS:
            rr=subset(scan,b,n,'mdm');v=[r['criterion_at_truth'] for r in rr]
            ps=[float(y) for y in np.percentile(v,[10,25,50,75,90])]
            stats.append({'beta':b,'n':n,'p10':ps[0],'p25':ps[1],'p50':ps[2],'p75':ps[3],'p90':ps[4],
                          'below_delta':sum(y<.1 for y in v),'total':len(v)})
            vals.append(ps)
        a=np.array(vals);axs[0].plot(BETAS,a[:,2],color=color,marker='o',lw=1.8,label=f'n={n} 中位数')
        axs[0].fill_between(BETAS,a[:,0],a[:,4],color=color,alpha=.15)
    axs[0].axhline(.1,color=TRUE,ls='--',label='估计判据 δ=0.10');axs[0].axhline(0,color='0.7',lw=.7)
    axs[0].set_xlabel('真实形状参数 β');axs[0].set_ylabel('真实 γ=500 处的 MDM 梯度')
    axs[0].set_title('高 β 时，真 γ 处梯度收缩到 0 附近',loc='left',fontsize=11)
    axs[0].legend(fontsize=8.5,loc='upper right');axs[0].set_xticks(BETAS)
    samples=readj(DATA/'历史'/'输入核验.json')['samples'];curves=[]
    axs[1].set_xlim(0,1300);axs[1].set_ylim(-.06,.28)
    for b,color in [(2,BLUE),(5,ORANGE)]:
        pick=next(r for r in selected if r['beta']==b and r['method']=='mdm')
        x,pp=realcurve(samples,pick,'mdm');curves += [{'method':'mdm','beta':b,'sample_id':pick['sample_id'],**p} for p in pp]
        axs[1].plot([p['gamma'] for p in pp],[p['value'] for p in pp],color=color,lw=2,label=f'β={b}，γ估计 {pick["gamma_hat"]:.0f}')
        axs[1].scatter(pick['gamma_hat'],.1,s=40,c=color,zorder=5)
        y=diag.profile(x,'mdm',500)['value'];axs[1].scatter(500,y,s=35,c=color,zorder=5)
    axs[1].axvline(500,color=TRUE,ls='--',lw=1);axs[1].axhline(.1,color=TRUE,ls='--',lw=1)
    axs[1].text(505,.255,'真 γ=500',fontsize=9);axs[1].text(15,.11,'判据 δ=0.10',fontsize=9)
    axs[1].set_xlabel('位置参数候选 γ');axs[1].set_ylabel('MDM 剖面标准差梯度')
    axs[1].set_title('达到固定梯度判据，需要向右寻找交点',loc='left',fontsize=11)
    axs[1].legend(fontsize=8.5,loc='lower right')
    fig.tight_layout();save(fig,'F05_MDM梯度收缩与位置上移')
    dump(DATA/'MDM真位置梯度统计.json',stats)
    return curves

def fig6(hist,selected):
    fig,axs=plt.subplots(2,2,figsize=(11.4,7.8))
    samples=readj(DATA/'历史'/'输入核验.json')['samples'];curves=[];checks=[]
    for ax,m in zip(axs.ravel(),['lse','lre_park','wmle','mle']):
        ax.set_xlim(0,1300)
        if m in ('lse','lre_park'):ax.set_ylim(-.035,1.8);ylabel='相对回归损失（本曲线真值处=1）'
        elif m=='wmle':ax.set_ylim(-.22,.22);ylabel=r'加权位置方程残差 $T_2$'
        else:ax.set_ylim(-1.8,.15);ylabel='相对似然差（本曲线真值处=−1）'
        for b,color in [(2,BLUE),(5,ORANGE)]:
            pick=next(r for r in selected if r['beta']==b and r['method']==m)
            x,pp=realcurve(samples,pick,m);at=diag.profile(x,m,pick['gamma_hat']);truth=diag.profile(x,m,500.)
            checks.append({'beta':b,'method':m,'sample_id':pick['sample_id'],'beta_formula_error':abs(at['b']-pick['beta_hat']),
                           'eta_formula_error':abs(at['eta']-pick['eta_hat']),'truth_criterion':truth['value'] if truth else None,
                           'fit_criterion':at['value'],'truth_ll':truth['ll'] if truth else None,'fit_ll':at['ll']})
            if m in ('lse','lre_park'):
                denom=truth['value']-at['value']
                assert denom>1e-10
                yy=[(p['value']-at['value'])/denom if p['value'] is not None else np.nan for p in pp];yf=0.;yt=1.
            elif m=='wmle':yy=[p['value'] if p['value'] is not None else np.nan for p in pp];yf=at['value'];yt=truth['value'] if truth else np.nan
            else:
                denom=at['ll']-truth['ll']
                assert denom>1e-10
                yy=[(p['ll']-at['ll'])/denom if p['ll'] is not None else np.nan for p in pp];yf=0.;yt=-1.
            ax.plot([p['gamma'] for p in pp],yy,color=color,lw=1.9,label=f'β={b}：γ估计 {pick["gamma_hat"]:.0f}')
            if m=='wmle':
                cy=[p['value'] if p['clipped'] else np.nan for p in pp]
                ax.plot([p['gamma'] for p in pp],cy,color=color,ls='--',lw=2.7)
            ax.scatter(pick['gamma_hat'],yf,c=color,s=35,zorder=5);ax.scatter(500,yt,c=color,marker='x',s=35,zorder=5)
            curves += [{'method':m,'beta':b,'sample_id':pick['sample_id'],**p} for p in pp]
        ax.axvline(500,color=TRUE,ls='--',lw=1);ax.axhline(0,color='0.5',lw=.7)
        ax.set_xlabel('位置参数候选 γ');ax.set_ylabel(ylabel,fontsize=9)
        ax.set_title(LABEL[m]+('：最低损失点' if m in ('lse','lre_park') else '：加权方程的根' if m=='wmle' else '：有限局部似然极大'),loc='left',fontsize=11)
        ax.legend(fontsize=8.5,loc='upper right' if m!='mle' else 'lower left')
    fig.tight_layout(h_pad=2.3,w_pad=1.8);save(fig,'F06_各方法实际准则选择偏移解')
    dump(DATA/'代表曲线公式核对.json',checks)
    return curves

def fig7(hist):
    fig,axs=plt.subplots(1,2,figsize=(11.4,4.5))
    for m in METHODS:
        rr=valid(subset(hist,5,7,m))
        axs[0].scatter([r['gamma_hat']-500 for r in rr],[r['eta_hat']-1000 for r in rr],s=19,alpha=.55,c=COL[m],label=LABEL[m])
    axs[0].plot([-550,900],[550,-900],ls='--',color=TRUE,lw=1.3,label='Δη=−Δγ：γ+η 保持1500')
    axs[0].axhline(0,color='0.75',lw=.7);axs[0].axvline(0,color='0.75',lw=.7)
    axs[0].set_xlim(-550,900);axs[0].set_ylim(-1000,1100)
    axs[0].set_xlabel('位置误差 Δγ');axs[0].set_ylabel('尺度误差 Δη');axs[0].set_title('同组估计沿“位置增、尺度减”方向补偿',loc='left',fontsize=11)
    axs[0].legend(fontsize=8,loc='upper right')
    t=np.linspace(450,2100,1000)
    for b,e,g,col,ls,lab in [(5,1000,500,TRUE,'-','真实 W(5,1000,500)'),(5,500,1000,'#AAAAAA','--','仅互换 W(5,500,1000)'),(2.5,500,1000,ORANGE,'-','联动补偿 W(2.5,500,1000)')]:
        axs[1].plot(t,cdf(t,b,e,g),color=col,ls=ls,lw=2,label=lab)
    axs[1].scatter(1500,1-math.exp(-1),s=30,color=TRUE,zorder=5)
    axs[1].annotate('三者的 63.2% 分位点都为1500',(1500,1-math.exp(-1)),xytext=(930,.85),arrowprops={'arrowstyle':'->','color':TRUE},fontsize=9)
    axs[1].set_xlim(450,2100);axs[1].set_ylim(0,1.04);axs[1].set_xlabel('寿命 t');axs[1].set_ylabel('累计概率 F(t)')
    axs[1].set_title('形状同步改变后，分布中部更接近真实',loc='left',fontsize=11);axs[1].legend(fontsize=8,loc='lower right')
    fig.tight_layout(w_pad=2);save(fig,'F07_三参数联动补偿')

def fig8(sh):
    fig,axs=plt.subplots(1,2,figsize=(11.4,4.3),sharex=True,sharey=True)
    for ax,n in zip(axs,(7,15)):
        for j,m in enumerate(HIST_METHODS):
            s=next(r for r in sh if r['beta']==5 and r['n']==n and r['method']==m)
            a=s['eta_free_med_abs_error'];b=s['eta_fixed_med_abs_error']
            ax.plot([b,a],[j,j],color='0.7',lw=1.3);ax.plot(a,j,'o',color=ORANGE,ms=6);ax.plot(b,j,'o',color=BLUE,ms=6)
            ax.text(a+13,j,f'{a:.0f}',va='center',fontsize=9,color=ORANGE)
            ax.text(b+13,j,f'{b:.0f}',va='center',fontsize=9,color=BLUE)
        ax.set_yticks(range(6),[LABEL[m] for m in HIST_METHODS]);ax.set_ylim(5.6,-.6);ax.set_xlim(0,710)
        ax.set_xlabel('尺度绝对误差的中位数');ax.set_title(f'n={n}：同组样本配对诊断',loc='left')
    fig.legend([Line2D([],[],marker='o',color=ORANGE,ls=''),Line2D([],[],marker='o',color=BLUE,ls='')],
               ['自由估计 γ','固定真 γ=500'],loc='upper center',ncol=2,bbox_to_anchor=(.55,1.05))
    fig.tight_layout(rect=(0,0,1,.97));save(fig,'F08_固定位置后尺度误差收缩')

def main():
    hist,scan,sh,sc=compute()
    selected=reps(hist)
    fig1(hist);fig2(hist);fig3(sc);fig4();curves=fig5(hist,scan,selected)
    curves+=fig6(hist,selected);fig7(hist);fig8(sh)
    dump(DATA/'绘图实际过程曲线.json',curves)
    qa={'historical_rows':len(hist),'historical_valid':sum(r['valid'] for r in hist),
        'scan_rows':len(scan),'scan_valid':sum(r['valid'] for r in scan),
        'scan_converged':sum(r['converged'] for r in scan),'figure_count':len(list(FIG.glob('*.png'))),
        'max_representative_beta_formula_error':max(r['beta_formula_error'] for r in readj(DATA/'代表曲线公式核对.json')),
        'max_representative_eta_formula_error':max(r['eta_formula_error'] for r in readj(DATA/'代表曲线公式核对.json'))}
    assert len(scan)==7000 and len(hist)==1200 and qa['figure_count']==8
    dump(DATA/'核对.json',qa);print(json.dumps(qa,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
