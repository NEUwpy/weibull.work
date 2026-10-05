"""Rebuild verified three-method data and requested Bias/SD/RMSE/violin outputs."""
import hashlib,importlib.util,json,platform,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp
import matplotlib
matplotlib.use('Agg')
from three_methods import HERE,PREVIOUS,CONFIG,REPO,previous,sources
from studies.common.sample import generate_sample
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3

KEY=['n','block','repeat_id'];METHODS=['MLE','MMLE','WMLE']
CORE=['beta','eta','gamma','n','repeat_id','block','method_id','method_variant',
      'beta_hat','eta_hat','gamma_hat','r_squared','converged','time','status',
      'beta_error','eta_error','gamma_error','beta_rel_error','eta_rel_error','gamma_rel_error','extra']

def main():
    hashes=sources();old=pd.read_csv(PREVIOUS/'per_sample.csv.gz')
    inherited=old[old.method_variant.isin(['mle_local','mmle_i'])][CORE].copy()
    inherited['method_variant']=inherited.method_variant.map({'mle_local':'MLE','mmle_i':'MMLE'})
    inherited['method_id']=inherited.method_variant
    frames=[];folders=sorted((HERE/'wmle_blocks').glob('n*_block*'));assert len(folders)==60
    for folder in folders:
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        assert manifest['source_sha256']==hashes and manifest['profile_recovery_used'] is False
        frame=pd.read_csv(folder/'results.csv');assert len(frame)==100
        frame['block']=manifest['block'];frame['method_variant']='WMLE';frame['method_id']='WMLE'
        frames.append(frame[CORE])
    data=pd.concat([inherited]+frames,ignore_index=True)
    assert len(data)==18000 and not data.duplicated(KEY+['method_variant']).any()
    originals=old[old.method_variant.eq('wmle_checked')].copy()
    assert len(originals)==6000
    sample_records=[];max_squared=0.0;wmle_checked=0
    for row in originals.itertuples():
        raw=generate_sample(2.0,1000.0,1000.0,int(row.n),int(row.repeat_id),seed=previous.namespace(int(row.block)))
        digest=hashlib.sha256(raw.astype('<f8').tobytes()).hexdigest();assert digest==row.sample_sha256
        sample_records.append(dict(n=row.n,block=row.block,repeat_id=row.repeat_id,
                                   sample_min=float(raw.min()),sample_sha256=digest))
    data=data.merge(pd.DataFrame(sample_records),on=KEY,validate='many_to_one')
    wmle=data[data.method_variant.eq('WMLE')]
    compared=wmle.merge(originals,on=KEY,suffixes=('','_old'),validate='one_to_one')
    expected=compared.status_old.eq('success') & ~compared.recovered.astype(bool)
    assert compared.status.eq('success').eq(expected).all()
    for p in ['beta_hat','eta_hat','gamma_hat']:
        assert np.allclose(compared.loc[expected,p],compared.loc[expected,p+'_old'],rtol=1e-12,atol=1e-9)
    for row in wmle.itertuples():
        info=json.loads(row.extra)['solution_info'];assert info['profile_recovery_used'] is False
        assert 'recovered' not in info
        if row.status!='success':continue
        x=generate_sample(2.0,1000.0,1000.0,int(row.n),int(row.repeat_id),seed=previous.namespace(int(row.block)))/1000
        b,e,g=row.beta_hat,row.eta_hat/1000,row.gamma_hat/1000
        logs=np.log(x-g);weights=np.exp(b*(logs-logs.max()));z=x-g
        rr=np.array([get_weight_j2(int(row.n))/b+logs.mean()-np.dot(weights,logs)/weights.sum(),
                      np.mean(1/z)*weights.sum()/np.sum(weights/z)-get_weight_j3(int(row.n),b)])
        err=float(np.sum(rr*rr));assert err<=1.0001e-8
        scale=(logsumexp(b*logs)-np.log(row.n*get_weight_j1(int(row.n))))/b-np.log(e)
        assert abs(scale)<1e-8 and 0<=row.gamma_hat<row.sample_min
        max_squared=max(max_squared,err);wmle_checked+=1
    good=data.status.eq('success')
    assert (data.loc[good,'gamma_hat']>=0).all() and (data.loc[good,'gamma_hat']<data.loc[good,'sample_min']).all()
    for p in ['beta','eta','gamma']:
        data[f'{p}_raw_error']=data[f'{p}_error'];data[f'{p}_norm_error']=data[f'{p}_rel_error']
    data['joint_squared']=sum(data[f'{p}_norm_error']**2 for p in ['beta','eta','gamma'])
    info=data.extra.map(lambda s:json.loads(s).get('solution_info',{}))
    data['failure_reason']=[('' if s=='success' else v.get('status','unknown') if v.get('status')!='ok'
                             else 'shared_quality_rejection:'+s) for v,s in zip(info,data.status)]
    data.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    verification=dict(samples_reused_verified=6000,inherited_mle_mmle_rows=12000,
        wmle_success_equations_checked=wmle_checked,max_wmle_squared_residual=max_squared,
        first_solve_status_and_estimates_match_prior=True,profile_recovery_used=False,
        formerly_recovered_rows_now_failed=int(compared.recovered.sum()),all_passed=True)
    (HERE/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    # Load the local scripts explicitly: inherited imports add other batches to sys.path.
    for script in ['summarize_metrics.py','violin.py']:
        spec=importlib.util.spec_from_file_location('current_'+Path(script).stem,HERE/script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.main()
    common_keys=data[good].groupby(KEY).method_variant.nunique()
    counts=common_keys[common_keys.eq(3)].reset_index().groupby('n').size().to_dict()
    analysis_policy=json.loads((HERE/'analysis_policy.json').read_text(encoding='utf-8'))
    outputs=['per_sample.csv.gz','汇总表.csv','汇总表.md','估计分布小提琴.png',
        'by_n_own_valid.csv','by_n_common.csv','paired_vs_wmle.csv','failure_reasons.csv',
        'verification.json','metrics_verification.json','绘图记录.json']
    script_files=['make_outputs.py','summarize_metrics.py','violin.py',
        'style_snapshot/绘图母体.py','style_snapshot/绘制图1小提琴.py']
    digest=lambda name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    assert hashes==sources(),'Calculation sources changed during output creation'
    manifest=dict(calculation_contract={k:v for k,v in CONFIG.items() if not k.startswith('precision_')},
        analysis_policy=analysis_policy,rows=18000,total_samples=6000,new_samples=0,
        common_success_counts={str(k):int(v) for k,v in counts.items()},source_sha256=hashes,
        output_script_sha256=digest('make_outputs.py'),analysis_script_sha256={name:digest(name) for name in script_files},
        output_sha256={name:digest(name) for name in outputs},analysis_policy_sha256=digest('analysis_policy.json'),
        python=sys.executable,numpy=np.__version__,pandas=pd.__version__,matplotlib=matplotlib.__version__)
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(verification))

if __name__=='__main__':main()
