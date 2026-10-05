"""Summarize saved estimates without refitting or repairing any solution."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;OUT=BATCH/'数据';REPO=HERE/'source_snapshot'
sys.path.insert(0,str(REPO/'python'))
from studies.common.metrics import check_status,summarize_standard_errors
METHODS=['MLE','K-R MMLE','WMLE'];NS=[7,10,15,20,50];PARAMS=['beta','eta','gamma'];TRUTH=json.loads((HERE/'config.json').read_text(encoding='utf-8'))['truth']
def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz');samples=np.load(HERE/'输入样本.npz')
    assert len(data)==18000 and not data.duplicated(['method_variant','n','block','repeat_id']).any()
    stats=[];checks=[];residuals=[]
    for (method,n),rows in data.groupby(['method_variant','n']):
        assert len(rows)==1200
        for row in rows.itertuples():
            x=samples[f'n{n}'][int(row.block)*100+int(row.repeat_id)]
            assert hashlib.sha256(x.tobytes()).hexdigest()==row.sample_sha256
            minimum=x[1] if method=='K-R MMLE' else x[0]
            status=check_status(row.beta_hat,row.eta_hat,row.gamma_hat,*TRUTH,converged=bool(row.converged),sample_min=minimum,boundary_tol=0.)
            assert status==row.status,(method,n,row.block,row.repeat_id)
            if method=='K-R MMLE' and status=='success':
                info=json.loads(row.extra)['solution_info'];assert info['deleted_observations']==1 and info['initial_shape']==1.
                assert info['no_firth'] and info['no_domain_caps'] and info['no_fallback']
                assert info['final_shape_step']<=1e-8 and abs(row.gamma_hat-x[0])<=1e-9
                z=x[1:]-x[0];logs=np.log(z);weights=np.exp(row.beta_hat*(logs-logs.max()));weights/=weights.sum()
                score=1/row.beta_hat+logs.mean()-weights@logs
                scale_relative=np.expm1(logsumexp(row.beta_hat*logs)-np.log(n-1)-row.beta_hat*np.log(row.eta_hat))
                assert abs(score)<1e-5 and abs(scale_relative)<1e-10
                residuals.append(dict(n=n,block=row.block,repeat_id=row.repeat_id,shape_score=score,
                    scale_relative_residual=scale_relative,gamma_minus_min=row.gamma_hat-x[0],iterations=info['iterations'],last_shape_step=info['final_shape_step']))
        valid=rows[rows.status=='success'];s=dict(method='MMLE' if method=='K-R MMLE' else method,n=int(n),total=1200,success=len(valid),success_rate=len(valid)/1200)
        for param,truth in zip(PARAMS,TRUTH):
            error=valid[param+'_hat'].to_numpy()-truth;shared=summarize_standard_errors(error)
            bias=shared['bias'];sd=float(np.std(error,ddof=0));rmse=shared['rmse']
            assert np.isclose(rmse**2,bias**2+sd**2,rtol=1e-12,atol=1e-10)
            s.update({param+'_bias':bias,param+'_sd':sd,param+'_rmse':rmse})
            checks.append(dict(method=method,n=n,parameter=param,rmse_squared=rmse**2,bias_squared_plus_sd_squared=bias**2+sd**2))
        s['joint_rmse']=float(np.sqrt(sum(s[p+'_rmse']**2 for p in PARAMS)));stats.append(s)
    summary=pd.DataFrame(stats);summary['order']=summary.method.map({'MLE':0,'MMLE':1,'WMLE':2})
    summary=summary.sort_values(['order','n']).drop(columns='order')
    summary.drop(columns='joint_rmse').to_csv(OUT/'三方法汇总.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(checks).to_csv(HERE/'统计恒等式核验.csv',index=False)
    pd.DataFrame(residuals).to_csv(HERE/'原版固定点结果核验.csv.gz',index=False,compression='gzip')
    data[data.status!='success'].to_csv(HERE/'失败逐样本.csv.gz',index=False,compression='gzip')
    # A paired descriptive subset is saved because MLE fails on many of the smallest samples.
    common=data.pivot(index=['n','block','repeat_id'],columns='method_variant',values='status').eq('success').all(axis=1)
    paired=data.set_index(['n','block','repeat_id']).loc[common[common].index].reset_index()
    common_stats=[]
    for (n,m),g in paired.groupby(['n','method_variant']):
        s=dict(n=n,method='MMLE' if m=='K-R MMLE' else m,success=len(g))
        for p,t in zip(PARAMS,TRUTH):
            e=g[p+'_hat'].to_numpy()-t;s[p+'_bias']=float(e.mean());s[p+'_sd']=float(e.std(ddof=0));s[p+'_rmse']=float(np.sqrt(np.mean(e*e)))
        s['joint_rmse']=float(np.sqrt(sum(s[p+'_rmse']**2 for p in PARAMS)));common_stats.append(s)
    pd.DataFrame(common_stats).to_csv(HERE/'共同成功统计.csv',index=False)
    summary=summary.drop(columns='joint_rmse');rows=summary.astype(object).values.tolist()
    (HERE/'汇总表数据.json').write_text(json.dumps(dict(columns=summary.columns.tolist(),rows=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    r=pd.DataFrame(residuals)
    verification=dict(records=18000,unique_samples=6000,summary_rows=15,identities=45,
         KR_gamma_original_min=True,KR_deleted_one=True,KR_solver='original fixed point, no recovery',
         max_shape_score=float(r.shape_score.abs().max()),max_scale_relative_residual=float(r.scale_relative_residual.abs().max()),
         max_gamma_serialization_difference=float(r.gamma_minus_min.abs().max()),
         iterations_min=int(r.iterations.min()),iterations_max=int(r.iterations.max()),
         SD_ddof=0,statistics_use_all_valid_estimates=True,paired_subset_sizes={str(n):int(v) for n,v in common[common].groupby(level=0).size().items()})
    (HERE/'统计核验.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary.to_string(index=False));print(json.dumps(verification,ensure_ascii=False))
if __name__=='__main__':main()
