"""Single-condition exploratory check; not a manuscript figure or new test set."""
from pathlib import Path
import sys
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[2]
REPO = STUDY.parents[1]
sys.path.insert(0,str(REPO/'python'))
from studies.common.sample import generate_sample
from studies.common.runner import run_method

E09 = STUDY/'数据/E09_六方法共同测试/per_sample.csv.gz'
GRID = np.round(np.arange(26)*.02,2)
SEED = 'study01_selector_confirmation_20260922_v1'


def evaluate(record):
    repeat=int(record['repeat_id'])
    x=generate_sample(2.,1000.,1000.,7,repeat,seed=SEED)
    h=hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()
    assert h==record['sample_sha256']
    out=[]
    for delta in GRID:
        fit=run_method('mdm',x,offset=float(delta),gamma_steps=60)
        estimates=np.array([fit.get(k+'_hat') for k in ['beta','eta','gamma']],dtype=float)
        valid=bool(fit['converged']) and np.isfinite(estimates).all() and (estimates[:2]>0).all() and estimates[2]>=0
        loss=float(np.sum(((estimates-[2,1000,1000])/[2,1000,1000])**2)) if valid else np.nan
        out.append(dict(repeat_id=repeat,sample_sha256=h,delta=delta,valid=valid,loss=loss,
                        beta_hat=estimates[0],eta_hat=estimates[1],gamma_hat=estimates[2]))
    return out


def main():
    source=pd.read_csv(E09)
    source=source[(source.beta==2)&(source.eta==1000)&(source.gamma==1000)&(source.n==7)]
    base=source[source.method=='MDM-0.1'].sort_values('repeat_id')
    adaptive=source[source.method=='AMDM'].set_index('repeat_id')
    assert len(base)==100
    with ProcessPoolExecutor(max_workers=2) as pool:
        batches=[]
        for i,result in enumerate(pool.map(evaluate,base.to_dict('records')),1):
            batches.extend(result)
            if i%10==0: print(f'{i}/100 samples scanned',flush=True)
    scan=pd.DataFrame(batches)
    scan.to_csv(HERE/'候选损失.csv',index=False,encoding='utf-8-sig')
    assert scan.valid.all(), 'Review failed candidates before constructing the diagnostic.'
    wide=scan.pivot(index='repeat_id',columns='delta',values='loss').reindex(columns=GRID)
    np.testing.assert_allclose(wide[.1],base.squared_loss,rtol=1e-9,atol=1e-11)
    chosen=wide.idxmin(axis=1)
    best=wide.min(axis=1)
    actual=np.array([wide.loc[i,round(float(adaptive.loc[i,'delta']),2)] for i in wide.index])
    np.testing.assert_allclose(actual,adaptive.loc[wide.index,'squared_loss'],rtol=1e-9,atol=1e-11)
    summary=pd.DataFrame(dict(repeat_id=wide.index,oracle_delta=chosen.values,oracle_loss=best.values,
                             fixed_loss=wide[.1].values,AMDM_loss=actual,
                             AMDM_delta=adaptive.loc[wide.index,'delta'].values,
                             exact_min_count=np.isclose(wide,best.values[:,None],rtol=1e-10,atol=1e-12).sum(axis=1),
                             within_1pct_min_count=(wide.values<=best.values[:,None]*1.01+1e-12).sum(axis=1)))
    summary.to_csv(HERE/'逐样本诊断.csv',index=False,encoding='utf-8-sig')
    counts=chosen.value_counts().reindex(GRID,fill_value=0)
    counts.rename_axis('delta').rename('count').to_csv(HERE/'最优偏移频数.csv',encoding='utf-8-sig')
    metrics={name:dict(mean_loss=float(values.mean()),J1=float(np.sqrt(values.mean())))
             for name,values in [('fixed',wide[.1]),('oracle',best),('AMDM',pd.Series(actual))]}
    report=dict(condition={'beta':2,'eta':1000,'gamma':1000,'n':7},samples=100,delta_grid=GRID.tolist(),
                criterion='Sum of squared errors standardized by beta, eta, eta; candidate oracle uses true parameters.',
                ties='Smallest delta breaks numerical argmin ties; exact and 1% near-optimal multiplicities saved.',
                reuse='Same E09 test samples; not a new independent confirmation. Condition chosen before scanning.',
                source_sha256=hashlib.sha256(E09.read_bytes()).hexdigest(),metrics=metrics,
                oracle_range=[float(chosen.min()),float(chosen.max())],occupied_bins=int((counts>0).sum()),
                boundary_minima=int(((chosen==0)|(chosen==.5)).sum()),
                exact_tied_samples=int((summary.exact_min_count>1).sum()),
                median_near_optimal_count=float(summary.within_1pct_min_count.median()),
                median_fixed_loss_excess=float((wide[.1]-best).median()),
                oracle_J1_gain=1-metrics['oracle']['J1']/metrics['fixed']['J1'],
                AMDM_J1_gain=1-metrics['AMDM']['J1']/metrics['fixed']['J1'],
                verification='All 100 hashes checked; fixed and AMDM scan results match E09; all 2600 candidates valid.',
                code_hashes={name:hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in
                             ['python/methods/mdm.py','python/studies/common/sample.py','python/studies/common/runner.py']})
    (HERE/'结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                         'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,'font.size':10})
    fig,axes=plt.subplots(1,2,figsize=(10.4,4.4),gridspec_kw={'width_ratios':[1.3,1]})
    fig.subplots_adjust(left=.08,right=.98,bottom=.16,top=.85,wspace=.28)
    ax=axes[0]
    for i,row in wide.iterrows():
        ax.plot(GRID,row.values,color='#AAB5BD',alpha=.3,lw=.6)
    # First six repeat IDs are highlighted by order, never selected by result.
    colors=['#3C7196','#A36946','#509A82','#8A6F9C','#B49A45','#4D9DA9']
    for i,color in zip(wide.index[:6],colors):
        ax.plot(GRID,wide.loc[i],color=color,lw=1.25)
        ax.scatter(chosen.loc[i],best.loc[i],color=color,s=23,zorder=5)
    ax.axvline(.1,color='#A35340',ls='--',lw=1,label='固定 δ=0.1')
    ax.set_yscale('log')
    ax.set(xlabel='偏移量 δ',ylabel='三参数联合平方损失 L（对数刻度）',xlim=(-.01,.51))
    ax.set_title('(a) 同一总体下的样本损失曲线',loc='left',fontweight='bold')
    ax.legend(frameon=False,fontsize=9)
    ax=axes[1]
    ax.bar(GRID,counts.values,width=.016,color='#648BB0',edgecolor='white',lw=.5)
    ax.axvline(.1,color='#A35340',ls='--',lw=1)
    ax.set(xlabel='候选集合内事后最优偏移 δ*',ylabel='样本数',xlim=(-.02,.52))
    ax.set_title('(b) 100组样本的最优偏移分布',loc='left',fontweight='bold')
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.tick_params(direction='out')
    for ext in ['png','svg','pdf']:
        fig.savefig(HERE/('D01_逐样本最优偏移.'+ext),dpi=300,facecolor='white')
    plt.close(fig)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
