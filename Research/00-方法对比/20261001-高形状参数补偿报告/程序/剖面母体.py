"""Reproduce the archived seeds and diagnose the actual estimators on the same samples.

Run with the project's Python 3.11 environment. All method code and inputs are local.
The independent profiles diagnose each estimator; they do not replace its returned fit.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp, gamma as gamma_function

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
OUT = BATCH / '结果'
DATA = OUT / '中间数据'
# The project environment has SciPy. Plotting and read-only XLSX extraction use
# installed, matching-Python plotting packages and the bundled pure Python reader.
PLOT_FALLBACK = Path('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages')
READER_FALLBACK = Path('C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
for path in (PLOT_FALLBACK, READER_FALLBACK):
    if path.exists():
        sys.path.append(str(path))
os.environ.setdefault('MPLCONFIGDIR', str(Path(os.environ.get('TEMP', '.')) / 'research00-bias-figures'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from openpyxl import load_workbook
sys.path.insert(0, str(HERE / '依赖快照' / 'python'))
from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import aggregate_standard_metrics
from methods import registry
from methods.lre_park import LRE as ParkLRE
from methods.lse import log_weibull_order_stat_means
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3, SHAPE_UPPER
registry.IMPLEMENTED['lre_park'] = ParkLRE

LABELS = {'mdm':'MDM δ=0.10','lse':'LSE','lre':'LRE Bernard','lre_park':'LRE Park','wmle':'WMLE','mle':'MLE'}
METHODS = list(LABELS)
COLORS = dict(zip(METHODS, ['#666666','#0072B2','#009E73','#56B4E9','#D55E00','#CC79A7']))
SEEDS = {2:20260826, 5:20260906}
plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
    'font.size':9, 'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
    'pdf.fonttype':42, 'svg.fonttype':'none', 'legend.frameon':False})

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def shape_root(logd, weight, upper):
    def equation(b):
        w = np.exp(b*logd-logsumexp(b*logd))
        return weight/b + float(logd.mean()) - float(w@logd)
    if equation(upper) >= 0:
        return None
    return float(brentq(equation, .010001, upper, xtol=1e-11))

def profile(x, method, g):
    """Use the exact fit criterion/weighted equation of the saved implementation."""
    d = x-g
    if g < 0 or np.any(d <= 0): return None
    logd = np.log(d); n=len(x)
    if method in ('lse','lre','lre_park'):
        ranks=np.arange(1,n+1,dtype=float)
        if method=='lse':
            z=log_weibull_order_stat_means(n)
            slope, intercept=np.polyfit(z,logd,1)
            b=1/slope; eta=float(np.exp(intercept))
        else:
            p=((ranks-3/8)/(n+1/4) if n<=10 else (ranks-.5)/n) if method=='lre_park' else (ranks-.3)/(n+.4)
            z=np.log(-np.log1p(-p))
            b, intercept=np.polyfit(logd,z,1)
            eta=float(np.exp(-intercept/b))
        r=float(np.corrcoef(logd,z)[0,1])
        return {'b':float(b),'eta':eta,'value':max(1-r*r,1e-16),'ll':None,'clipped':False}
    if method in ('wmle','mle'):
        b=shape_root(logd,get_weight_j2(n) if method=='wmle' else 1., SHAPE_UPPER if method=='wmle' else 1000.)
        if b is None or (method=='mle' and b<=1.): return None
        log_s=logsumexp(b*logd)
        eta=float(np.exp((log_s-math.log(n*(get_weight_j1(n) if method=='wmle' else 1.)))/b))
        ratio=float(np.exp(log_s-logsumexp((b-1)*logd)))
        if method=='wmle':
            value=float(np.mean(1/d)*ratio-get_weight_j3(n,b))
            ll=None
        else:
            value=float(1000*(b/ratio-(b-1)*np.mean(1/d)))
            ll=float(n*math.log(b)-n*b*math.log(eta)+(b-1)*logd.sum()-n)
        return {'b':b,'eta':eta,'value':value,'ll':ll,'clipped':bool(method=='wmle' and b>5)}
    if method=='mdm':
        p=(np.arange(1,n+1)-.3)/(n+.4); z=-np.log1p(-p)
        def sigma(loc):
            r=minimize_scalar(lambda b:np.std((x-loc)/z**(1/b),ddof=1),bounds=(.1,15),method='bounded')
            return r
        fit=sigma(g); h=min(max(float(x[0]),1)*1e-5,g*.25 if g else 1.,float(x[0]-g)*.25)
        grad=(sigma(g+h).fun-sigma(g-h).fun)/(2*h) if g else (sigma(h).fun-fit.fun)/h
        return {'b':float(fit.x),'eta':float(np.mean(d/z**(1/fit.x))),'value':float(grad),'ll':None,'clipped':False}
    raise ValueError(method)

def audit_inputs():
    samples={}; archived={}; audits=[]; sample_records=[]
    for beta in (2,5):
        src=HERE/'输入快照'/f'beta{beta}'
        rr=read_csv(src/'samples.csv')
        grouped={}
        for row in rr:
            key=(int(row['sample_size']),int(row['sample_id']))
            grouped.setdefault(key,[]).append(float(row['value']))
        old=read_csv(src/'mdm_estimates.csv')+read_csv(src/'other_method_estimates.csv')
        wb=load_workbook(src/'原估计表.xlsx',read_only=True,data_only=True)
        sheet_values={n:list(wb[f'估计结果_n{n}'].values) for n in (7,15)}
        samples_values={n:list(wb[f'生成样本_n{n}'].values) for n in (7,15)}
        max_sample=0.; max_mapping=0.; wrong_swap_min=[]; triples=0
        for (n,sid), values in grouped.items():
            x=np.array(values)
            regen=generate_sample(float(beta),1000.,500.,n,sid-1,seed=SEEDS[beta])
            seed_text=f'{SEEDS[beta]}|{float(beta)!r}|1000.0|500.0|{n}|{sid-1}'
            seed_int=int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:4],'big')
            uniforms=np.random.default_rng(seed_int).uniform(0,1,n)
            direct=np.sort(500.+1000.*(-np.log(1-uniforms))**(1/float(beta)))
            sheet=np.array(samples_values[n][sid][1:n+1],float)
            err=max(float(np.max(abs(x-regen))),float(np.max(abs(x-sheet))),float(np.max(abs(x-direct))))
            max_sample=max(max_sample,err)
            swapped=generate_sample(float(beta),500.,1000.,n,sid-1,seed=SEEDS[beta])
            wrong_swap_min.append(float(np.max(abs(x-swapped))))
            assert err<1e-9, (beta,n,sid,err)
            samples[(beta,n,sid)]=x
            sample_records.append({'beta_true':beta,'n':n,'sample_id':sid,'seed':SEEDS[beta],
                'sample_min':float(x[0]),'sample_max':float(x[-1]),'sample_mean':float(x.mean()),
                'regeneration_max_error':err,'swapped_parameters_max_error':wrong_swap_min[-1],
                'minimum_below_1000':bool(x[0]<1000),'observations':x.tolist()})
        for row in old:
            method=row['method_id']; n=int(row['sample_size']); sid=int(row['sample_id'])
            delta=float(row['offset']) if row['offset'] else .1
            valid=row['converged'].lower()=='true'
            start={'mdm':1,'lse':4,'lre':7,'wmle':10,'mle':13}[method]
            for displayed_delta in ([delta] if method=='mdm' else [.1,.15,.2]):
                base={.1:4,.15:62,.2:120}[displayed_delta]
                cells=sheet_values[n][base+sid-1][start:start+3]
                if valid:
                    nums=np.array([float(row[k]) for k in ('beta_hat','eta_hat','gamma_hat')])
                    error=float(np.max(abs(nums-np.array(cells,float))))
                    assert error<1e-9,(beta,n,sid,method,error)
                    max_mapping=max(max_mapping,error)
                else:
                    assert all(c is None or str(c) in ('—','-','无解') for c in cells),(method,cells)
                triples+=1
            if method!='mdm' or abs(delta-.1)<1e-9:
                archived[(beta,n,sid,method)]=row
        wb.close()
        audits.append({'beta_true':beta,'eta_true':1000,'gamma_true':500,'seed':SEEDS[beta],
            'sample_groups':len(grouped),'observations':len(rr),'sample_and_excel_max_error':max_sample,
            'mapped_estimate_triples':triples,'estimate_column_mapping_max_error':max_mapping,
            'swapped_regeneration_min_max_error':min(wrong_swap_min),
            'groups_with_observation_below_1000':sum(r['minimum_below_1000'] for r in sample_records if r['beta_true']==beta)})
    dump(DATA/'输入核验.json',{'audit':audits,'samples':sample_records})
    return samples,archived,sample_records,audits

def calculate(samples,archived):
    fits=[]; checks=[]; curves=[]; profiles={}; selected=[]
    curve_checks=[]
    for (beta,n,sid),x in samples.items():
        local={}
        for method in METHODS:
            r=run_method(method,x,**({'offset':.1,'gamma_steps':240,'trace':True} if method=='mdm' else {}))
            r.update({'beta':beta,'eta':1000.,'gamma':500.,'n':n,'sample_id':sid,'sample_min':float(x[0]),'method':method})
            # registry resolves the Park sensitivity under its own name.
            old=archived.get((beta,n,sid,method))
            if old:
                prior=old['converged'].lower()=='true'
                err=None
                match=r['converged']==prior
                if prior and r['converged']:
                    a=np.array([r[k] for k in ('beta_hat','eta_hat','gamma_hat')]); b=np.array([float(old[k]) for k in ('beta_hat','eta_hat','gamma_hat')])
                    err=float(np.max(abs(a-b))); match=bool(np.allclose(a,b,rtol=1e-6,atol=1e-5))
                checks.append({'beta':beta,'n':n,'id':sid,'method':method,'matches':match,'max_error':err})
            conditional=profile(x,method,500.)
            r['conditional_beta']=conditional['b'] if conditional else None
            r['conditional_eta']=conditional['eta'] if conditional else None
            r['criterion_at_truth']=conditional['value'] if conditional else None
            if method=='mdm':
                trace=(r.get('trace_data') or {}).get('grad_gamma_curve',[])
                pp=[{'g':p['gamma'],'b':None,'eta':None,'value':p['gradient'],'ll':None,'clipped':False}
                    for p in trace if not p.get('virtual') and p.get('source')=='trace_grid' and math.isfinite(p['gradient'])]
                pp.append({'g':500.,**conditional})
            else:
                upper=float(x[0])*(1-1e-7)
                grid=np.unique(np.r_[np.linspace(0,upper,161),float(x[0])-np.geomspace(float(x[0])*1e-7,float(x[0]),35),500.,
                    r['gamma_hat'] if r['converged'] else 500.])
                pp=[]
                for g in grid:
                    p=profile(x,method,float(g))
                    pp.append({'g':float(g),**p} if p else {'g':float(g),'b':None,'eta':None,'value':None,'ll':None,'clipped':False})
            pp.sort(key=lambda p:p['g'])
            profiles[(beta,n,sid,method)]=pp
            for p in pp:
                curves.append({'beta_true':beta,'n':n,'sample_id':sid,'method':method,'gamma_candidate':p['g'],
                    'beta_conditional':p['b'],'eta_conditional':p['eta'],'criterion':p['value'],
                    'profile_loglikelihood':p['ll'],'J3_clamped_above_beta5':p['clipped']})
            if r['converged']:
                at=profile(x,method,r['gamma_hat'])
                v={'beta':beta,'n':n,'id':sid,'method':method,'gamma_hat':r['gamma_hat'],
                   'profile_valid_at_fit':at is not None,'beta_formula_error':abs(at['b']-r['beta_hat']) if at else None,
                   'eta_formula_error':abs(at['eta']-r['eta_hat']) if at else None,
                   'criterion_at_fit':at['value'] if at else None}
                if method in ('lse','lre','lre_park') and at:
                    v['grid_improvement_over_returned_loss']=at['value']-min(p['value'] for p in pp if p['value'] is not None)
                if method=='mle' and at:
                    h=min(.01,max(r['gamma_hat']*.25,1e-4),(x[0]-r['gamma_hat'])*.1)
                    left=profile(x,method,max(0,r['gamma_hat']-h));right=profile(x,method,r['gamma_hat']+h)
                    v['local_loglikelihood_maximum']=bool((not left or at['ll']>=left['ll']-1e-6) and (not right or at['ll']>=right['ll']-1e-6))
                curve_checks.append(v)
            # Derived curves are saved once in 过程曲线.csv.
            r.pop('trace_data',None)
            local[method]=r;fits.append(r)
        if sid%10==0:print(f'computed beta={beta} n={n} {sid}/50',flush=True)
    for beta in (2,5):
        for n in (7,15):
            for method in METHODS:
                valid=[r for r in fits if r['beta']==beta and r['n']==n and r['method']==method and r['converged']]
                med=float(np.median([r['gamma_hat'] for r in valid]))
                chosen=min(valid,key=lambda r:(abs(r['gamma_hat']-med),r['sample_id']))
                selected.append({'beta_true':beta,'n':n,'method':method,'selected_sample_id':chosen['sample_id'],
                    'median_gamma':med,'selected_gamma':chosen['gamma_hat'],'selected_eta':chosen['eta_hat'],
                    'selection':'closest to median gamma among successful fits; tie by sample_id'})
    dump(DATA/'复算核验.json',{'comparisons':checks,'total':len(checks),'mismatches':[r for r in checks if not r['matches']],
         'profile_checks':curve_checks,'representative_samples':selected})
    write_csv(DATA/'过程曲线.csv',curves)
    dump(DATA/'实际估计.json',fits)
    return fits,profiles,selected,checks,curve_checks

def summarize(fits,sample_records):
    summaries=[]; tail=[]
    for beta in (2,5):
        for n in (7,15):
            ss=[r for r in sample_records if r['beta_true']==beta and r['n']==n]
            tail.append({'beta':beta,'n':n,'mean_minimum_theoretical':500+1000*float(gamma_function(1+1/beta))*n**(-1/beta),
                'probability_all_above_1000':math.exp(-n*.5**beta),'actual_groups_minimum_above_1000':sum(r['sample_min']>1000 for r in ss),
                'median_sample_minimum':float(np.median([r['sample_min'] for r in ss]))})
            for method in METHODS:
                rr=[r for r in fits if r['beta']==beta and r['n']==n and r['method']==method]
                valid=[r for r in rr if r['converged']]; num=len(valid)
                standard=aggregate_standard_metrics(rr,include_diagnostics=False)
                conditional=[r for r in valid if r['conditional_eta'] is not None]
                s={'beta_true':beta,'n':n,'method':LABELS[method],'method_id':method,'total':50,'valid':num,'failed':50-num,
                   'gamma_above_500':sum(r['gamma_hat']>500 for r in valid),
                   'eta_below_1000':sum(r['eta_hat']<1000 for r in valid),
                   'joint_gamma_high_eta_low':sum(r['gamma_hat']>500 and r['eta_hat']<1000 for r in valid),
                   'gamma_zero':sum(r['gamma_hat']==0 for r in valid),
                   'median_beta':float(np.median([r['beta_hat'] for r in valid])),
                   'median_gamma':float(np.median([r['gamma_hat'] for r in valid])),
                   'median_eta':float(np.median([r['eta_hat'] for r in valid])),
                   'median_gamma_plus_eta':float(np.median([r['gamma_hat']+r['eta_hat'] for r in valid])),
                   'median_abs_error_gamma_plus_eta':float(np.median([abs(r['gamma_hat']+r['eta_hat']-1500) for r in valid])),
                   'median_abs_error_eta_free_paired':float(np.median([abs(r['eta_hat']-1000) for r in conditional])),
                   'median_abs_error_eta_fixed_gamma_paired':float(np.median([abs(r['conditional_eta']-1000) for r in conditional])),
                   'conditional_pairs':len(conditional),
                   'truth_criterion_positive':sum(r['criterion_at_truth'] is not None and r['criterion_at_truth']>0 for r in rr),
                   'mdm_truth_below_delta':sum(r['criterion_at_truth'] is not None and r['criterion_at_truth']<.1 for r in rr) if method=='mdm' else None,
                   **{k:standard.get(k.lower()) for k in ('Bias_beta','Bias_eta','Bias_gamma','SD_beta','SD_eta','SD_gamma','RMSE_beta','RMSE_eta','RMSE_gamma','MAE_beta','MAE_eta','MAE_gamma')}}
                summaries.append(s)
    dump(DATA/'汇总.json',{'summary':summaries,'lower_tail':tail})
    write_csv(DATA/'汇总.csv',summaries)
    return summaries,tail

def save_figure(fig,name):
    fig.savefig(OUT/f'{name}.png',dpi=350,facecolor='white')
    fig.savefig(OUT/f'{name}.pdf',facecolor='white')
    plt.close(fig)

def plot_processes(fits,profiles,selected):
    selection={(r['beta_true'],r['n'],r['method']):r for r in selected}
    for method in METHODS:
        fig,axes=plt.subplots(2,2,figsize=(10.4,7),sharex=True)
        for row,n in enumerate((7,15)):
            for col,beta in enumerate((2,5)):
                ax=axes[row,col]; pick=selection[(beta,n,method)]; sid=pick['selected_sample_id']
                for i in range(1,51):
                    pp=profiles[(beta,n,i,method)]
                    ax.plot([p['g'] for p in pp],[np.nan if p['value'] is None else p['value'] for p in pp],color='0.72',lw=.45,alpha=.45)
                pp=profiles[(beta,n,sid,method)]; yy=[np.nan if p['value'] is None else p['value'] for p in pp]
                ax.plot([p['g'] for p in pp],yy,color='#0072B2',lw=1.65)
                clipped=[p for p in pp if p['clipped']]
                if clipped:
                    ax.plot([p['g'] for p in clipped],[p['value'] for p in clipped],color='#E69F00',ls='--',lw=1.7)
                fit=next(r for r in fits if r['beta']==beta and r['n']==n and r['sample_id']==sid and r['method']==method)
                at=profile(np.array(next(r for r in SAMPLE_RECORDS if r['beta_true']==beta and r['n']==n and r['sample_id']==sid)['observations']),method,fit['gamma_hat'])
                ax.axvline(500,color='black',ls='--',lw=1)
                if at:ax.scatter(fit['gamma_hat'],at['value'],marker='D' if fit['gamma_hat'] else '^',s=30,color='#D55E00',zorder=5)
                if method in ('lse','lre','lre_park'):
                    ax.set_yscale('log');ax.set_ylim(1e-5,1)
                    ylabel='归一化回归损失 1−ρ²（越低越优）'
                elif method=='wmle':
                    ax.axhline(0,color='0.25',lw=.9);ax.set_ylim(-.5,.5);ylabel=r'加权位置方程残差 $T_2$（交零点）'
                elif method=='mle':
                    ax.axhline(0,color='0.25',lw=.9);ax.set_ylim(-3,3);ylabel=r'剖面位置分数 $\eta_0 U_\gamma/n$（正→负极大）'
                else:
                    ax.axhline(.1,color='#D55E00',ls='-.',lw=1);ax.set_ylim(-.05,.3);ylabel='MDM 剖面标准差梯度（与0.10相交）'
                ax.set_xlim(0,1500)
                ax.set_title(f'β={beta}，n={n}，50组；代表样本#{sid}',loc='left',fontsize=10)
                rr=[r for r in fits if r['beta']==beta and r['n']==n and r['method']==method]
                valid=[r for r in rr if r['converged']]
                ax.text(.025,.035,f'成功 {len(valid)}/50；γ估计>500：{sum(r["gamma_hat"]>500 for r in valid)}/{len(valid)}\nγ估计中位数 {pick["median_gamma"]:.0f}；代表解 {fit["gamma_hat"]:.0f}',transform=ax.transAxes,
                    fontsize=8,bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
                if row==1:ax.set_xlabel('位置参数候选 γ')
                if col==0:ax.set_ylabel(ylabel)
        handles=[Line2D([],[],color='0.7',lw=1,label='所有50组'),Line2D([],[],color='#0072B2',lw=1.5,label='预定规则代表样本'),
                 Line2D([],[],color='black',ls='--',label='真 γ=500'),Line2D([],[],marker='D',ls='',color='#D55E00',label='实际程序返回解')]
        if method=='wmle':handles.append(Line2D([],[],color='#E69F00',ls='--',label=r'代表曲线β>5：$J_3$按表端点取值'))
        fig.suptitle(LABELS[method]+'：实际估计准则如何选择位置参数',fontsize=14,y=.985)
        fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.942),ncol=3 if method=='wmle' else 4,fontsize=8)
        fig.subplots_adjust(left=.11,right=.985,bottom=.10,top=.835 if method=='wmle' else .865,hspace=.28,wspace=.2)
        save_figure(fig,'过程_'+method)

def plot_compensation(fits,tail):
    fig,axes=plt.subplots(2,2,figsize=(10.3,7.4),sharex=True,sharey=True)
    for row,n in enumerate((7,15)):
        for col,beta in enumerate((2,5)):
            ax=axes[row,col]
            for method in METHODS:
                if method=='lre_park':continue
                rr=[r for r in fits if r['beta']==beta and r['n']==n and r['method']==method and r['converged']]
                ax.scatter([r['gamma_hat']-500 for r in rr],[r['eta_hat']-1000 for r in rr],s=15,alpha=.65,c=COLORS[method],label=LABELS[method],marker={'mdm':'o','lse':'s','lre':'^','wmle':'D','mle':'x'}[method])
            ax.plot([-550,1000],[550,-1000],color='black',ls='--',lw=1)
            ax.axvline(0,color='0.8',lw=.7);ax.axhline(0,color='0.8',lw=.7)
            ax.set_title(f'β={beta}，n={n}；每点为一组成功估计',loc='left',fontsize=10)
            ax.set_xlim(-550,1000);ax.set_ylim(-1000,900)
            if row==1:ax.set_xlabel(r'位置误差 $\Delta\gamma=\hat\gamma-500$')
            if col==0:ax.set_ylabel(r'尺度误差 $\Delta\eta=\hat\eta-1000$')
    handles,labels=axes[0,0].get_legend_handles_labels()
    handles.append(Line2D([],[],color='black',ls='--'));labels.append('Δη=−Δγ：保持γ+η=1500')
    fig.suptitle('位置上移时，尺度沿补偿方向下降',fontsize=14,y=.99)
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.95),ncol=3,fontsize=9)
    fig.subplots_adjust(left=.10,right=.985,bottom=.085,top=.82,hspace=.28,wspace=.15)
    save_figure(fig,'参数补偿')
    fig,axes=plt.subplots(1,2,figsize=(10.2,4.5),sharey=True)
    for ax,n in zip(axes,(7,15)):
        for beta,color,marker in ((2,'#0072B2','o'),(5,'#D55E00','s')):
            rr=[r for r in SAMPLE_RECORDS if r['beta_true']==beta and r['n']==n]
            xs=np.arange(1,51);ys=np.sort([r['sample_min'] for r in rr])
            ax.plot(xs,ys,color=color,marker=marker,ms=3,lw=1,label=f'β={beta}')
            theoretical=next(t for t in tail if t['beta']==beta and t['n']==n)
            ax.axhline(theoretical['mean_minimum_theoretical'],color=color,ls=':',lw=1)
        ax.axhline(500,color='black',ls='--',label='真γ=500');ax.axhline(1000,color='0.5',ls='-.',label='交换参数后的支持起点1000')
        ax.set_title(f'n={n}，原种子50组',loc='left');ax.set_xlabel('按最小观测值排序后的样本组序号')
    axes[0].set_ylabel(r'每组样本最小观测值 $t_{(1)}$');axes[1].legend(fontsize=8,loc='lower right')
    fig.suptitle('β=5的小样本往往离真位置参数很远',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.94));save_figure(fig,'样本下尾信息')

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    redraw='--redraw' in sys.argv
    if (DATA/'实际估计.json').exists() and not redraw:raise RuntimeError('Output exists: create another task batch for a new computation.')
    global SAMPLE_RECORDS
    samples,archived,SAMPLE_RECORDS,audits=audit_inputs()
    print('INPUT_AUDIT',json.dumps(audits,ensure_ascii=False),flush=True)
    if redraw:
        fits=json.loads((DATA/'实际估计.json').read_text(encoding='utf-8'))
        for r in fits:r.pop('trace_data',None)
        dump(DATA/'实际估计.json',fits)
        verification=json.loads((DATA/'复算核验.json').read_text(encoding='utf-8'))
        selected=verification['representative_samples'];checks=verification['comparisons']
        profiles={}
        for r in read_csv(DATA/'过程曲线.csv'):
            key=(int(r['beta_true']),int(r['n']),int(r['sample_id']),r['method'])
            profiles.setdefault(key,[]).append({'g':float(r['gamma_candidate']),
                'b':float(r['beta_conditional']) if r['beta_conditional'] else None,
                'eta':float(r['eta_conditional']) if r['eta_conditional'] else None,
                'value':float(r['criterion']) if r['criterion'] else None,
                'll':float(r['profile_loglikelihood']) if r['profile_loglikelihood'] else None,
                'clipped':r['J3_clamped_above_beta5']=='True'})
    else:
        fits,profiles,selected,checks,curve_checks=calculate(samples,archived)
    summary,tail=summarize(fits,SAMPLE_RECORDS)
    plot_processes(fits,profiles,selected);plot_compensation(fits,tail)
    code_files=[p for p in (HERE/'依赖快照').rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    input_files=[p for p in (HERE/'输入快照').rglob('*') if p.is_file()]
    dump(DATA/'manifest.json',{'task':'original beta2/beta5 parameter mapping and criterion diagnostics','truth':[[2,1000,500],[5,1000,500]],
        'n':[7,15],'groups_per_cell':50,'seeds':SEEDS,'methods':LABELS,'offset':.1,
        'new_sampling':False,'conditional_fit':'gamma fixed at true500; WMLE solves only T1, not full two-equation estimator',
        'runtime':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,
            'python_executable':sys.executable,'matplotlib_location':matplotlib.__file__},
        'code_hashes':{str(p.relative_to(BATCH)):hash_file(p) for p in code_files+[p for p in HERE.iterdir() if p.is_file()]},
        'input_hashes':{str(p.relative_to(BATCH)):hash_file(p) for p in input_files},
        'output_hashes':{str(p.relative_to(BATCH)):hash_file(p) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'},
        'historical_fit_recomputations':len(checks),'historical_mismatches':sum(not r['matches'] for r in checks),
        'profile_range_notes':'LSE/LRE lower better loss; WMLE beta<10 and J3 clamped above5; MLE beta>1 finite branch; displayed WMLE/MLE/MDM axes zoomed, full CSV retained'})
    print('COMPLETE',len(fits),'fits;',sum(not r['matches'] for r in checks),'historical mismatches',flush=True)

if __name__=='__main__':main()
