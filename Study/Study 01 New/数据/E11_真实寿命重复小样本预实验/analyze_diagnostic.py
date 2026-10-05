"""Derive diagnostic tables without changing models, samples or metrics."""
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'扩展诊断'

def main():
    df=pd.read_csv(OUT/'per_sample.csv.gz')
    ref=pd.read_csv(HERE/'reference_fits.csv')[['beta_hat','eta_hat','gamma_hat']].iloc[0].to_numpy()
    rows=[];parameter=[];cases=[];extremes=[];tail_behavior=[]
    for (regime,n),g in df.groupby(['regime','n']):
        a=g[g.method=='AMDM'].set_index('repeat').sort_index()
        b=g[g.method=='MDM-0.1'].set_index('repeat').sort_index()
        valid=a.valid & b.valid
        a=a.loc[valid];b=b.loc[valid]
        dp=a.param_loss-b.param_loss;dc=a.cdf_empirical-b.cdf_empirical
        row=dict(regime=regime,n=n,paired=len(a),parameter_improves_cdf_worsens=float(((dp<0)&(dc>0)).mean()),parameter_worsens_cdf_improves=float(((dp>0)&(dc<0)).mean()),both_improve=float(((dp<0)&(dc<0)).mean()),both_worsen=float(((dp>0)&(dc>0)).mean()))
        for metric,power in [('param_loss',.5),('cdf_empirical',1),('cdf_fitted',1)]:
            av=a[metric].to_numpy();bv=b[metric].to_numpy();diff=av-bv
            # The exact leave-one-repeat range measures single-case influence.
            loo=100*(1-((av.sum()-av)/(bv.sum()-bv))**power)
            row[metric+'_leave_one_gain_min']=loo.min();row[metric+'_leave_one_gain_max']=loo.max()
            row[metric+'_top1pct_abs_share']=float(np.sort(abs(diff))[-max(1,len(diff)//100):].sum()/abs(diff).sum())
            for tag,rep in [('largest_harm',a[metric].sub(b[metric]).idxmax()),('largest_help',a[metric].sub(b[metric]).idxmin())]:
                cases.append(dict(regime=regime,n=n,metric=metric,case=tag,repeat=rep,delta=a.loc[rep,'delta'],amdm_loss=a.loc[rep,metric],fixed_loss=b.loc[rep,metric],amdm_param_loss=a.loc[rep,'param_loss'],fixed_param_loss=b.loc[rep,'param_loss'],amdm_cdf=a.loc[rep,'cdf_empirical'],fixed_cdf=b.loc[rep,'cdf_empirical']))
        rows.append(row)
        for method,vals in [('AMDM',a),('MDM-0.1',b)]:
            for j,p in enumerate(['beta','eta','gamma']):
                error=(vals[p+'_hat'].to_numpy()-ref[j])/ref[0 if j==0 else 1]
                parameter.append(dict(regime=regime,n=n,method=method,parameter=p,bias=error.mean(),sd=np.std(error,ddof=0),rmse=np.sqrt(np.mean(error**2))))
        if regime=='real_without_replacement':
            with np.load(OUT/f'{regime}_n{n}_samples.npz') as z: x=z['x'][a.index]
            for label,flag in [('includes_min370',x[:,0]==370),('includes_max2440',x[:,-1]==2440)]:
                for state in [False,True]:
                    ix=flag==state
                    extremes.append(dict(n=n,stratum=label,present=state,count=int(ix.sum()),param_gain=100*(1-np.sqrt(a.param_loss.to_numpy()[ix].mean()/b.param_loss.to_numpy()[ix].mean())),cdf_gain=100*(1-a.cdf_empirical.to_numpy()[ix].mean()/b.cdf_empirical.to_numpy()[ix].mean())))
            for method,vals in [('AMDM',a),('MDM-0.1',b)]:
                for flag in [False,True]:
                    part=vals[(x[:,0]==370)==flag]
                    tail_behavior.append(dict(n=n,method=method,includes370=flag,count=len(part),delta_mean=part.delta.mean(),delta_median=part.delta.median(),gamma_mean=part.gamma_hat.mean(),gamma_zero=(part.gamma_hat==0).mean(),beta_rmse=np.sqrt(part.beta_loss.mean()),eta_rmse=np.sqrt(part.eta_loss.mean()),gamma_rmse=np.sqrt(part.gamma_loss.mean()),cdf_mean=part.cdf_empirical.mean()))
    pd.DataFrame(rows).to_csv(OUT/'metric_agreement_and_influence.csv',index=False)
    pd.DataFrame(parameter).to_csv(OUT/'parameter_bias_sd.csv',index=False)
    pd.DataFrame(cases).to_csv(OUT/'extreme_case_diagnostic.csv',index=False)
    pd.DataFrame(extremes).to_csv(OUT/'tail_inclusion_diagnostic.csv',index=False)
    pd.DataFrame(tail_behavior).to_csv(OUT/'tail_selector_behavior.csv',index=False)
    scan=pd.read_csv(OUT/'candidate_scan.csv.gz')
    oracle_rows=[]
    for (regime,n),g in scan.groupby(['regime','n']):
        oracle_delta={}
        for metric in ['param_loss','cdf_empirical','cdf_fitted']:
            best=g.loc[g.groupby('repeat')[metric].idxmin()].set_index('repeat')
            oracle_delta[metric]=best.delta
            sub=df[(df.regime==regime)&(df.n==n)&(df.repeat<100)]
            a=sub[sub.method=='AMDM'].set_index('repeat')[metric]
            b=sub[sub.method=='MDM-0.1'].set_index('repeat')[metric]
            power=.5 if metric=='param_loss' else 1
            oracle_rows.append(dict(regime=regime,n=n,metric=metric,count=len(best),amdm=a.mean()**power,fixed=b.mean()**power,oracle=best[metric].mean()**power,oracle_gain_percent=100*(1-(best[metric].mean()/b.mean())**power),selected_gain_percent=100*(1-(a.mean()/b.mean())**power),oracle_delta_median=best.delta.median()))
        print(regime,n,'param/CDF oracle offsets differ',float((oracle_delta['param_loss']!=oracle_delta['cdf_empirical']).mean()))
    pd.DataFrame(oracle_rows).to_csv(OUT/'oracle_summary.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))

def check_cdf_grid():
    from run_pilot import cdf
    df=pd.read_csv(OUT/'per_sample.csv.gz').query("regime=='real_without_replacement'")
    ref=pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    grid=np.linspace(0,max(ref),16001)
    ecdf=np.searchsorted(np.sort(ref),grid,side='right')/len(ref)
    rows=[]
    for r in df.itertuples():
        value=np.trapezoid((cdf(grid,(r.beta_hat,r.eta_hat,r.gamma_hat))-ecdf)**2,grid)/max(ref)
        rows.append(dict(n=r.n,repeat=r.repeat,method=r.method,fine_cdf=value,coarse_cdf=r.cdf_empirical))
    fine=pd.DataFrame(rows).groupby(['n','method'])[['fine_cdf','coarse_cdf']].mean().unstack('method')
    out=[]
    for n,row in fine.iterrows():
        gains={key:100*(1-row[(key,'AMDM')]/row[(key,'MDM-0.1')]) for key in ['fine_cdf','coarse_cdf']}
        assert abs(gains['fine_cdf']-gains['coarse_cdf'])<.05
        out.append(dict(n=n,**gains,difference_percentage_points=gains['fine_cdf']-gains['coarse_cdf']))
    pd.DataFrame(out).to_csv(OUT/'cdf_grid_verification.csv',index=False)

if __name__=='__main__':
    main()
    check_cdf_grid()
