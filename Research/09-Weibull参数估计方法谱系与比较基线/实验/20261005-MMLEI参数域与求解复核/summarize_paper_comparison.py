"""Three original-equation methods: common checks, own/common subsets and variance decomposition."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;DEST=HERE/'三方法原文口径';REPO=HERE.parents[3]
sys.path.insert(0,str(REPO/'python'))
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3
METHODS=['MLE','MMLE-I','WMLE'];N=[7,10,15,20,50]
def stats(part):
    out={}
    for p in ['beta','eta','gamma']:
        e=part[p+'_error'].to_numpy();b=float(e.mean());s=float(e.std(ddof=0));r=float(np.sqrt(np.mean(e**2)))
        assert np.isclose(r*r,b*b+s*s,rtol=1e-12)
        out.update({p+'_bias':b,p+'_sd':s,p+'_rmse':r,p+'_squared_bias_fraction':b*b/(r*r)})
    for metric in ['bias','sd','rmse']:out['joint_'+metric]=float(np.sqrt(sum(out[p+'_'+metric]**2 for p in ['beta','eta','gamma'])))
    assert np.isclose(out['joint_rmse']**2,out['joint_bias']**2+out['joint_sd']**2,rtol=1e-12)
    return out
def main():
    d=pd.read_csv(DEST/'per_sample.csv.gz');samples=np.load(HERE/'samples.npz');assert len(d)==18000
    maxeq=np.zeros(3);verified=0;details=[];failure=[];low_ml_max=0
    for row in d.itertuples():
        raw=samples[f'n{row.n}'][int(row.block)*100+int(row.repeat_id)]
        assert hashlib.sha256(raw.tobytes()).hexdigest()==row.sample_sha256
        record=json.loads(row.extra)['solution_info'];candidates=record.get('candidates',[])
        if row.method_variant=='MLE':low_ml_max+=sum(c['local_maximum'] and .1<c['beta']<=1.01 for c in candidates)
        if row.status!='success':
            failure.append(dict(method=row.method_variant,n=row.n,block=row.block,repeat_id=row.repeat_id,sample_sha256=row.sample_sha256,
                reason=record['status'],stationary_roots=len(candidates),stationary_minima=sum(not c['local_maximum'] for c in candidates)))
            continue
        b,e,g=row.beta_hat,row.eta_hat,row.gamma_hat;lo=raw.mean()-10*raw.std(ddof=1)
        assert lo-1e-7<=g<=raw[0]-1e-4+1e-7 and .1<b<15 and e>0
        z=raw-g;logs=np.log(z);w=np.exp(b*(logs-logs.max()));w/=w.sum();dinv=(raw[0]-g)/z
        if row.method_variant=='WMLE':
            j1=get_weight_j1(row.n);j2=get_weight_j2(row.n)
            equations=np.array([j2/b+logs.mean()-w@logs,dinv.mean()/(w@dinv)-get_weight_j3(row.n,b),np.mean(np.exp(b*np.log(z/e)))-j1])
        elif row.method_variant=='MMLE-I':
            equations=np.array([1/b+logs.mean()-w@logs,-np.expm1(-np.exp(b*np.log((raw[0]-g)/e)))-1/(row.n+1),np.mean(np.exp(b*np.log(z/e)))-1])
        else:
            equations=np.array([1/b+logs.mean()-w@logs,b*(w@(dinv-dinv.mean()))+dinv.mean(),np.mean(np.exp(b*np.log(z/e)))-1])
            assert b>1.01
        assert np.sum(equations**2)<=1e-8;maxeq=np.maximum(maxeq,np.abs(equations));verified+=1
        details.append(dict(method=row.method_variant,n=row.n,block=row.block,repeat_id=row.repeat_id,sample_sha256=row.sample_sha256,
            beta_hat=b,eta_hat=e,gamma_hat=g,negative_gamma=g<0,shape_below_1_01=b<=1.01,shape_above_weight_calibration_5=b>5,
            max_absolute_residual=float(np.max(np.abs(equations)))))
    pd.DataFrame(details).to_csv(DEST/'有效估计核验.csv.gz',index=False,compression='gzip')
    pd.DataFrame(failure).to_csv(DEST/'失败逐样本.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(failure).groupby(['method','n','reason']).size().rename('count').reset_index().to_csv(DEST/'失败分类.csv',index=False,encoding='utf-8-sig')
    summary=[];wide=[];common=[];pairs=[]
    accepted={method:set(d.loc[(d.method_variant==method)&(d.status=='success'),'sample_sha256']) for method in METHODS}
    allcommon=set.intersection(*accepted.values())
    for method in METHODS:
        wide_row=dict(method=method)
        for n in N:
            part=d[(d.method_variant==method)&(d.n==n)];good=part[part.status=='success']
            out=dict(method=method,n=n,total=len(part),accepted=len(good),acceptance_rate=len(good)/len(part),**stats(good))
            summary.append(out);wide_row.update({f'n{n}_{k}':v for k,v in out.items() if k not in ['method','n']})
            shared=part[part.sample_sha256.isin(allcommon)]
            common.append(dict(method=method,n=n,accepted=len(shared),**stats(shared)))
        wide.append(wide_row)
    for a,b in [('MMLE-I','MLE'),('WMLE','MLE'),('WMLE','MMLE-I')]:
        keys=accepted[a]&accepted[b]
        for n in N:
            subset=d[(d.n==n)&d.sample_sha256.isin(keys)]
            sa=stats(subset[subset.method_variant==a]);sb=stats(subset[subset.method_variant==b])
            pairs.append(dict(method_a=a,method_b=b,n=n,paired_samples=len(subset[subset.method_variant==a]),
                              **{k+'_difference_a_minus_b':sa[k]-sb[k] for k in sa}))
    pd.DataFrame(summary).to_csv(DEST/'分n统计.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(wide).to_csv(DEST/'三行汇总表.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(common).to_csv(DEST/'共同成功统计.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(pairs).to_csv(DEST/'配对差异.csv',index=False,encoding='utf-8-sig')
    diagnostic=pd.DataFrame(details).groupby(['method','n']).agg(accepted=('sample_sha256','size'),negative_gamma=('negative_gamma','sum'),
                below_1_01=('shape_below_1_01','sum'),wmle_above_5=('shape_above_weight_calibration_5','sum')).reset_index()
    diagnostic.to_csv(DEST/'参数域例外诊断.csv',index=False,encoding='utf-8-sig')
    protection=json.loads((HERE/'原主目录保护.json').read_text(encoding='utf-8'))
    for path,sha in protection.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
    verification=dict(rows=18000,samples_sha256_verified=6000,equation_checks=verified,max_absolute_residual=maxeq.tolist(),
        common_shape_lower_exception_MLE_maxima_in_0_1_to_1_01=low_ml_max,common_success_samples=len(allcommon),
        bias_sd_rmse_identities=60,old_main_files_unchanged=len(protection),common_acceptance_residual_squared=1e-8,
        no_nonnegative_location_filter=True,no_fit_quality_or_truth_error_filter=True,all_passed=True)
    (DEST/'复核记录.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(summary)[['method','n','accepted','acceptance_rate','beta_bias','beta_sd','beta_rmse','eta_rmse','gamma_rmse','joint_rmse']].to_string(index=False))
    print(diagnostic.to_string(index=False));print('Verification',json.dumps(verification,ensure_ascii=False));print('Common success',pd.DataFrame(common).to_string(index=False))
if __name__=='__main__':main()
