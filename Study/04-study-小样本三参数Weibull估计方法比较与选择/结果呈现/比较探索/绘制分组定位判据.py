"""Ten actual paths; one n per row, one gamma-selection rule per column."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from 验证MDM偏移量与廓线群体 import STUDY,OUT,HERE,NS,sha,dump,table
from 绘制嵌套样本拟合 import nested_samples
from 第三章机制候选图 import gradient
from methods.conditional_profiles import mle_profile
from 绘制偏移量与代表廓线 import ASSETS


def select_ten():
    d=pd.read_csv(OUT/'嵌套四法/results.csv',float_precision='round_trip')
    ids=list(range(0,1200,10));rows=[]
    for rid in range(120):
        sub=d[d.repeat_id.eq(rid)];endpoint=sub[sub.n.eq(7)].set_index('method_variant')
        mle=endpoint.loc['MLE'];mdm=endpoint.loc['MDM-0']
        kind='failure' if mle.status!='success' else 'zero' if mle.gamma_hat==0 else 'interior'
        r=dict(source_id=ids[rid],branch='MLE-'+kind+'_MDM0-'+('zero' if mdm.gamma_hat==0 else 'interior'))
        for method in ['MLE','MMLE','MDM-0','MDM-0.1']:
            for n in [50,7]:
                row=sub[sub.n.eq(n)&sub.method_variant.eq(method)].iloc[0]
                for p,truth,scale in [('beta',5,5),('eta',1000,1000),('gamma',500,1000)]:
                    r[f'{method}_{n}_{p}']=(row[p+'_hat']-truth)/scale if row.status=='success' else np.nan
        rows.append(r)
    features=pd.DataFrame(rows).set_index('source_id')
    counts=features.branch.value_counts().sort_index();desired=counts/120*10
    quota=np.maximum(np.floor(desired).astype(int),1)
    while quota.sum()<10:quota.loc[(desired-quota).idxmax()]+=1
    while quota.sum()>10:
        allowed=quota[quota>1].index;quota.loc[(quota-desired).loc[allowed].idxmax()]-=1
    selected=[]
    for branch,count in counts.items():
        values=features[features.branch.eq(branch)].drop(columns='branch').dropna(axis=1,how='all').sort_index()
        assert values.notna().all().all()
        center=values.median();mad=(values-center).abs().median();iqr=values.quantile(.75)-values.quantile(.25)
        scale=mad.where(mad>0,iqr).where(lambda a:a>0,values.std(ddof=0)).where(lambda a:a>0,1.)
        z=((values-center)/scale).to_numpy();dist=np.abs(z[:,None,:]-z[None,:,:]).mean(axis=2)
        pool=values.index.to_list();locked=pool.index(670) if 670 in pool else None
        centers=[locked if locked is not None else int(np.argmin(np.abs(z).mean(axis=1)))]
        while len(centers)<quota[branch]:
            nearest=dist[:,centers].min(axis=1);nearest[centers]=-1
            centers.append(int(np.argmax(nearest)))
        for _ in range(40):
            assignment=np.argmin(dist[:,centers],axis=1);changed=list(centers)
            for j,c in enumerate(centers):
                if c==locked:continue
                members=np.flatnonzero(assignment==j);assert len(members)
                changed[j]=int(members[np.argmin(dist[np.ix_(members,members)].sum(axis=1))])
            if changed==centers:break
            centers=changed
        assignment=np.argmin(dist[:,centers],axis=1)
        for j,c in enumerate(centers):
            selected.append(dict(source_id=int(pool[c]),branch=branch,branch_count=int(count),
                represented_path_count=int((assignment==j).sum()),
                represented_source_ids=[int(pool[i]) for i in np.flatnonzero(assignment==j)],
                failed_n=[int(n) for n in NS if d[d.repeat_id.eq(pool[c]//10)&d.n.eq(n)&d.method_variant.eq('MLE')].iloc[0].status!='success']))
    selected.sort(key=lambda q:(q['source_id']!=670,-q['represented_path_count'],q['source_id']))
    assert len(selected)==10 and len({q['source_id'] for q in selected})==10
    assert sum(q['represented_path_count'] for q in selected)==120
    assert sorted(i for q in selected for i in q['represented_source_ids'])==ids
    return selected


def draw(item):
    sid=item['source_id'];paths=nested_samples(table(50).reset_index(),[sid])
    data=pd.read_csv(OUT/'嵌套四法/results.csv',float_precision='round_trip')
    data=data[data.repeat_id.eq(sid//10)]
    fig,axs=plt.subplots(5,4,figsize=(16,16),sharex='col')
    fig.subplots_adjust(left=.10,right=.985,bottom=.055,top=.955,hspace=.27,wspace=.32)
    rows=[];mle_min=0.;mle_max=0.
    gamma_max=max(paths[sid,n][0] for n in NS)
    for i,n in enumerate(NS):
        x=paths[sid,n];v=data[data.n.eq(n)].set_index('method_variant');xmax=float(x[0])
        grid=np.unique(np.r_[np.linspace(0,xmax*.97,140),xmax-np.geomspace(xmax*.03,xmax*.001,30),
            v.loc[['MLE','MDM-0','MDM-0.1'],'gamma_hat'].dropna().to_numpy()])
        grid=grid[(grid>=0)&(grid<xmax)]
        ll=np.array([mle_profile(x,g)['ll'] for g in grid]);r=v.loc['MLE']
        ref=mle_profile(x,float(r.gamma_hat))['ll'] if r.status=='success' else float(ll.max())
        loss=(ref-ll)/n;mle_min=min(mle_min,float(loss.min()));mle_max=max(mle_max,float(loss.max()))
        axs[i,0].plot(grid,loss,color='#8064A2',lw=1.8)
        if r.status=='success':axs[i,0].scatter(r.gamma_hat,0,s=30,color='#8064A2',zorder=4,clip_on=False)
        axs[i,0].text(-.31,.5,rf'$n={n}$',transform=axs[i,0].transAxes,ha='right',va='center',fontsize=14)
        axs[i,0].set_ylabel(r'$-\Delta\bar{\ell}_p(\gamma)$',fontsize=12)
        axs[i,1].scatter(x[1:],np.zeros(n-1),marker='|',s=110,color='#b7c0c7',lw=1.2)
        axs[i,1].scatter(x[0],0,s=55,color='#CC79A7',zorder=4)
        assert float(v.loc['MMLE','gamma_hat'])==float(x[0])
        axs[i,1].set(ylim=(-.6,.6),yticks=[])
        grads=np.array([gradient(x,g) for g in grid])
        for j,method,target,marker,color in [(2,'MDM-0',0.,'o','#6B7780'),(3,'MDM-0.1',.1,'s','#0072B2')]:
            ax=axs[i,j];ax.plot(grid,grads,color=color,lw=1.8);ax.axhline(target,color='#777',ls='--',lw=1)
            r=v.loc[method]
            if r.status=='success':
                ax.scatter(r.gamma_hat,gradient(x,float(r.gamma_hat)),marker=marker,s=36,
                    facecolors='white' if marker=='o' else color,edgecolors=color,zorder=4,clip_on=False)
            ax.set(ylim=(-.12,.25),yticks=[-.1,0,.1,.2],ylabel=r'$g_n(\gamma)$')
        rows.append(dict(n=n,observations=x.tolist(),
            estimates={m:{p:None if pd.isna(v.loc[m,p+'_hat']) else float(v.loc[m,p+'_hat']) for p in ['beta','eta','gamma']} for m in v.index},
            states=v.status.to_dict(),gamma_grid=grid.tolist(),mdm_gradient=grads.tolist(),mle_relative_per_observation_loss=loss.tolist()))
    for i in range(5):
        axs[i,0].set(ylim=(mle_min-.02*max(mle_max,1),mle_max*1.05+.01),xlim=(0,gamma_max))
        axs[i,1].set_xlim(float(paths[sid,50][0])*.9,float(paths[sid,50][-1])*1.03)
        for j in [2,3]:axs[i,j].set_xlim(0,gamma_max)
        for j in range(4):
            axs[i,j].tick_params(labelbottom=True,labelsize=10)
    for j,title in enumerate(['MLE',r'MMLE: $\hat\gamma=x_{(1)}$','MDM(0)','MDM(0.1)']):axs[0,j].set_title(title,pad=13,fontsize=14)
    for j in [0,2,3]:axs[-1,j].set_xlabel(r'$\gamma$',fontsize=13)
    axs[-1,1].set_xlabel(r'$x,\ \hat\gamma$',fontsize=13)
    p=ASSETS/f'31T_分行定位判据_样本{sid}.png';fig.savefig(p,dpi=200,facecolor='white');plt.close(fig)
    dump(OUT/f'十组分行/样本{sid}.json',dict(selection=item,rows=rows,figure_sha256=sha(p)))
    return dict(**item,path=p.relative_to(STUDY).as_posix(),sha256=sha(p),aspect_ratio=1.)


def main():
    selected=select_ten();outputs=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(draw,item) for item in selected]
        for i,f in enumerate(as_completed(futures),1):
            r=f.result();outputs.append(r);print(json.dumps(dict(completed=i,total=10,source_id=r['source_id'])),flush=True)
    order={q['source_id']:i for i,q in enumerate(selected)};outputs.sort(key=lambda q:order[q['source_id']])
    record=dict(source_sha256=sha(OUT/'嵌套四法/results.csv'),candidate_paths=120,display_paths=10,
        layout='One n per row (50/20/15/10/7); columns MLE/MMLE/MDM(0)/MDM(.1).',
        purpose='Gamma selection only; Bias and SD in separate figures.',
        selection='Endpoint MLE state and MDM0 zero/interior strata, proportional quotas with >=1/stratum; robust L1 medoids within strata, retaining shared-center670. Ten examples do not replace statistics from all120.',
        examples=outputs)
    dump(HERE/'3.1十组定位判据选例.json',record)
    print(json.dumps(dict(status='complete',selected=[q['source_id'] for q in outputs]),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
