"""Paired delta comparison on archived n50/n7 samples; default beta2, configurable."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from functools import lru_cache
import json,hashlib,os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from 验证MDM偏移量与廓线群体 import STUDY,CORE,HERE,sha,dump,METHODS,row_result
from studies.common.experiment import run_experiment
from studies.common.metrics import summarize_standard_errors
from 绘制偏移量与代表廓线 import ASSETS

BETA=float(os.environ.get('STUDY04_MDM_BETA','2'))
assert BETA in [2.,3.]
DEST=STUDY/f'结果呈现/分析数据/3.1-MDM偏移量-beta{BETA:g}'
NS=[50,7]

@lru_cache(maxsize=2)
def table(n):
    p=STUDY/f'结果/W{BETA:g},1000,500/估计结果/n{n}.csv'
    d=pd.read_csv(p,float_precision='round_trip').set_index('样本编号');assert len(d)==1200
    return d

def original(n,sid):
    row=table(n).loc[sid];x=row[[f'观测值{i}' for i in range(1,n+1)]].to_numpy(float)
    assert row['MDM-0.1_状态']=='success'
    result=dict(method_id='mdm',method_variant='MDM-0.1',
        beta_hat=float(row['MDM-0.1_形状估计']),eta_hat=float(row['MDM-0.1_尺度估计']),gamma_hat=float(row['MDM-0.1_位置估计']),
        r_squared=None,converged=True,time=0.,sample_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
        extra=dict(archived_variant='MDM-0.1',archive_source=f'结果/W{BETA:g},1000,500/估计结果/n{n}.csv'))
    return x,result

def job(arg):
    n,start=arg;ids=list(range(start,start+100));path=DEST/'分片'/f'n{n}-id{start:04d}';done=path/'完成.json'
    identity=dict(n=n,source_ids=ids,source_sha256=sha(STUDY/f'结果/W{BETA:g},1000,500/估计结果/n{n}.csv'),mdm_sha256=sha(CORE/'methods/mdm.py'))
    if done.exists():
        previous=json.loads(done.read_text(encoding='utf-8'));assert previous['identity']==identity and previous['results_sha256']==sha(path/'results.csv')
        return dict(n=n,start=start,cached=True)
    frame=table(n);samples={};cache={}
    for rid,sid in enumerate(ids):
        row=frame.loc[sid];x=row[[f'观测值{i}' for i in range(1,n+1)]].to_numpy(float)
        assert row['MDM-0.1_状态']=='success'
        _,saved=original(n,sid);samples[rid]=x;cache[BETA,1000.,500.,n,rid,'MDM-0.1']=saved
    run_experiment(METHODS,[(BETA,1000.,500.)],[n],100,str(path),
        sample_provider=lambda b,e,g,count,rid:samples[rid],precomputed_results=cache,boundary_tol=0.,
        code_version='Study04 frozen20261016 '+sha(CORE/'methods/mdm.py')[:12],run_label=f'Beta{BETA:g} original samples paired delta0/.1; source ids in completion record')
    dump(done,dict(identity=identity,results_sha256=sha(path/'results.csv')))
    return dict(n=n,start=start,cached=False)

def assemble():
    cache={}
    for done in sorted((DEST/'分片').glob('*/完成.json')):
        a=json.loads(done.read_text(encoding='utf-8'));assert a['results_sha256']==sha(done.parent/'results.csv')
        d=pd.read_csv(done.parent/'results.csv',float_precision='round_trip');ids=a['identity']['source_ids']
        for _,row in d.iterrows():
            sid=ids[int(row.repeat_id)];key=(BETA,1000.,500.,int(row.n),sid,row.method_variant)
            assert key not in cache;cache[key]=row_result(row)
    assert len(cache)==4800
    run_experiment(METHODS,[(BETA,1000.,500.)],NS,1200,str(DEST/'正式样本'),
        sample_provider=lambda b,e,g,n,rid:original(n,rid)[0],precomputed_results=cache,boundary_tol=0.,
        code_version='Study04 frozen20261016 '+sha(CORE/'methods/mdm.py')[:12],run_label='Verified shards assembled without new estimator calls')

def figure_and_stats():
    data=pd.read_csv(DEST/'正式样本/results.csv',float_precision='round_trip');stats=[]
    fig,axs=plt.subplots(2,3,figsize=(16,7),sharex='col',sharey='col')
    fig.subplots_adjust(left=.065,right=.985,bottom=.13,top=.86,hspace=.22,wspace=.25)
    for j,(p,truth) in enumerate([('beta',BETA),('eta',1000.),('gamma',500.)]):
        maximum=float(data[p+'_hat'].max());upper=np.ceil(maximum/(1 if p=='beta' else 100))*(1 if p=='beta' else 100)+(0.1 if p=='beta' else 30)
        edges=np.linspace(0,upper,41);ymax=0.
        for i,n in enumerate(NS):
            ax=axs[i,j]
            for method,color in [('MDM-0','#6B7780'),('MDM-0.1','#0072B2')]:
                rows=data[data.n.eq(n)&data.method_variant.eq(method)];assert len(rows)==1200 and rows.status.eq('success').all()
                values=rows[p+'_hat'].to_numpy(float);counts,_=np.histogram(values,bins=edges);assert counts.sum()==1200
                ymax=max(ymax,float(counts.max()/1200))
                ax.stairs(counts/1200,edges,color=color,lw=1.8,fill=True,alpha=.15);ax.stairs(counts/1200,edges,color=color,lw=1.5)
                st=summarize_standard_errors(values-truth);stats.append(dict(n=n,method=method,parameter=p,valid=1200,
                    **{k:st[k] for k in ['bias','sd','rmse']},zero_gamma=int(rows.gamma_hat.eq(0).sum())))
            ax.axvline(truth,color='#222',ls='--',lw=1.2);ax.text(.96,.88,rf'$n={n}$',transform=ax.transAxes,ha='right')
            ax.set(xlim=(0,upper),ylabel='比例')
            if i==1:ax.set_xlabel([r'$\hat\beta$',r'$\hat\eta$',r'$\hat\gamma$'][j])
        for ax in axs[:,j]:ax.set_ylim(0,ymax*1.08)
    fig.legend(handles=[Line2D([],[],color='#6B7780',lw=2,label=r'$\mathrm{MDM}\ (\delta=0)$'),
        Line2D([],[],color='#0072B2',lw=2,label=r'$\mathrm{MDM}\ (\delta=0.1)$'),
        Line2D([],[],color='#222',ls='--',label='真实参数')],loc='upper center',ncol=3,frameon=False)
    p=ASSETS/f'31N_MDM两偏移量估计分布_beta{BETA:g}.png';fig.savefig(p,dpi=220,facecolor='white');plt.close(fig)
    record=dict(beta=BETA,eta=1000.,gamma=500.,n=NS,repeats=1200,total_rows=4800,new_method_calls=2400,new_weibull_samples=0,
        source_sha256={f'结果/W{BETA:g},1000,500/估计结果/n{n}.csv':sha(STUDY/f'结果/W{BETA:g},1000,500/估计结果/n{n}.csv') for n in NS},
        results_sha256=sha(DEST/'正式样本/results.csv'),figure=dict(path=p.relative_to(STUDY).as_posix(),sha256=sha(p)),metrics=stats)
    dump(HERE/f'3.1-MDM偏移量-beta{BETA:g}核对.json',record)
    print(json.dumps(dict(status='complete',figure=record['figure'],metrics=stats),ensure_ascii=False),flush=True)

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    dump(DEST/'输入约定.json',dict(beta=BETA,n=NS,repeats=1200,delta=[0,.1],new_calls=2400,new_samples=0,
        source=f'Existing Study04 W{BETA:g},1000,500 samples; existing delta.1 estimates reused; frozen shared pipeline; original files unchanged.'))
    jobs=[(n,k) for n in NS for k in range(0,1200,100)]
    with ProcessPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(job,arg) for arg in jobs]
        for i,future in enumerate(as_completed(futures),1):print(json.dumps(dict(completed=i,total=24,**future.result())),flush=True)
    assemble();figure_and_stats()

if __name__=='__main__':main()
