"""Reuse preceding aggregation, audit samples and expose selection effects."""
import hashlib
import importlib.util
import json
import platform
import sys
import numpy as np
import pandas as pd
import scipy
import matplotlib
from experiment import HERE, PRIOR, REPO, CONFIG, METHODS, LABELS, namespace, source_hashes
from studies.common.sample import generate_sample
from refine import METHODS as REFINED_METHODS, refinement_hash

spec=importlib.util.spec_from_file_location('preceding_summary',PRIOR/'summarize.py')
preceding=importlib.util.module_from_spec(spec);spec.loader.exec_module(preceding)
summary=preceding.summary
KEY=['n','block','repeat_id']

def main():
    hashes=source_hashes();frames=[];manifests=[];changes=[]
    folders=sorted((HERE/'blocks').glob('n*_block*'))
    assert len(folders)==60,len(folders)
    for folder in folders:
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        assert manifest['source_sha256']==hashes,folder
        frame=pd.read_csv(folder/'results.csv')
        assert len(frame)==1500,(folder,len(frame))
        refined_folder=HERE/'refined_blocks'/folder.name
        refined_manifest=json.loads((refined_folder/'manifest.json').read_text(encoding='utf-8'))
        assert refined_manifest['source_sha256']==hashes
        assert refined_manifest['refinement_sha256']==refinement_hash()
        refined=pd.read_csv(refined_folder/'results.csv');assert len(refined)==1100
        compared=frame[frame.method_variant.isin(REFINED_METHODS)].merge(refined,
            on=['n','repeat_id','method_variant'],suffixes=('_initial','_refined'),validate='one_to_one')
        changed=compared.status_initial.ne(compared.status_refined)
        for parameter in ['beta_hat','eta_hat','gamma_hat']:
            changed |= ~np.isclose(compared[parameter+'_initial'],compared[parameter+'_refined'],
                                    rtol=1e-10,atol=1e-9 if parameter=='beta_hat' else 1e-6,equal_nan=True)
        amendments=compared.loc[changed,['n','repeat_id','method_variant','status_initial','status_refined']+[
            p+s for p in ['beta_hat','eta_hat','gamma_hat'] for s in ['_initial','_refined']]].copy()
        amendments['block']=manifest['block'];changes.append(amendments)
        frame=pd.concat([frame[~frame.method_variant.isin(REFINED_METHODS)],refined],ignore_index=True)
        frame['block']=manifest['block'];frames.append(frame);manifests.append(manifest)
    data=pd.concat(frames,ignore_index=True)
    amendments=pd.concat(changes,ignore_index=True)
    amendments.to_csv(HERE/'root_refinement_changes.csv',index=False)
    assert len(data)==90000 and not data.duplicated(KEY+['method_variant']).any()
    samples=[]
    for n,block,rid in data[KEY].drop_duplicates().itertuples(index=False,name=None):
        x=generate_sample(2.0,1000.0,1000.0,int(n),int(rid),seed=namespace(int(block)))
        samples.append(dict(n=n,block=block,repeat_id=rid,sample_min=float(x.min()),
                            sample_sha256=hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()))
    data=data.merge(pd.DataFrame(samples),on=KEY,validate='many_to_one')
    valid=data.status.eq('success')
    assert np.isfinite(data.loc[valid,['beta_hat','eta_hat','gamma_hat']]).all().all()
    assert (data.loc[valid,'gamma_hat']<data.loc[valid,'sample_min']).all()
    assert (data.loc[valid & ~data.method_variant.str.endswith('_paper'),'gamma_hat']>=0).all()
    for p in ['beta','eta','gamma']:
        data[f'{p}_raw_error']=data[f'{p}_error'];data[f'{p}_norm_error']=data[f'{p}_rel_error']
    data['joint_squared']=sum(data[f'{p}_norm_error']**2 for p in ['beta','eta','gamma'])
    info=data.extra.map(lambda v:json.loads(v).get('solution_info',{}) if isinstance(v,str) else {})
    data['failure_reason']=[('' if s=='success' else v.get('status','unknown')
                            if v.get('status','unknown')!='ok' else 'shared_quality_rejection:'+s)
                           for v,s in zip(info,data.status)]
    data['recovered']=[bool(v.get('recovered',False)) for v in info]
    data['production_status']=[v.get('production_status','') for v in info]
    data['roots_found']=[v.get('roots_found',np.nan) for v in info]
    data.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    own=summary(data,['method_variant','n']);own['success_rate']=own.valid/own.total
    own['joint_bias_norm']=np.sqrt(sum(own[f'{p}_norm_bias']**2 for p in ['beta','eta','gamma']))
    own.to_csv(HERE/'by_n_own_valid.csv',index=False)
    data[data.failure_reason.ne('')].groupby(['method_variant','n','failure_reason']).size().rename(
        'count').reset_index().to_csv(HERE/'failure_reasons.csv',index=False)
    branch=[]
    for (method,n),part in data.groupby(['method_variant','n']):
        good=part[part.status.eq('success')]
        branch.append(dict(method_variant=method,n=n,success=len(good),
            shape_equal_one=int(np.isclose(good.beta_hat,1,rtol=0,atol=1e-7).sum()),
            shape_below_one=int((good.beta_hat<1-1e-7).sum()),
            negative_location=int((good.gamma_hat<0).sum()),
            multiple_roots=int((good.roots_found>1).sum()),recovered=int(part.recovered.sum())))
    pd.DataFrame(branch).to_csv(HERE/'branch_diagnostics.csv',index=False)
    wide=[];markdown=['| 方法 | n=7 | n=10 | n=15 | n=20 | n=50 |',
                      '|---|---:|---:|---:|---:|---:|']
    for method in METHODS:
        item={'method_id':method,'method':LABELS[method]};cells=[]
        for n in CONFIG['n_values']:
            row=own[(own.method_variant==method)&(own.n==n)].iloc[0]
            for col in ['valid','total','success_rate','J1_valid','joint_bias_norm','J1_failure3']+[
                f'{p}_{scale}_{metric}' for p in ['beta','eta','gamma'] for scale in ['raw','norm']
                for metric in ['bias','rmse']]:
                item[f'n{n}_{col}']=row[col]
            cells.append(f'{row.success_rate*100:.1f}% / {row.J1_valid:.3f}')
        wide.append(item);markdown.append('| '+LABELS[method]+' | '+' | '.join(cells)+' |')
    pd.DataFrame(wide).to_csv(HERE/'汇总表.csv',index=False,encoding='utf-8-sig')
    (HERE/'汇总表.md').write_text('# 固定真值下的成功率与精度\n\n'
        '每格为 **成功率 / J1**；J1 越小越好，按各方法自己的成功样本计算。每 n 1200组，'
        '真值 β=2、η=1000、γ=1000。逐参数原始与归一化 Bias/RMSE 见汇总表.csv。\n\n'
        +'\n'.join(markdown)+'\n',encoding='utf-8')
    # Pairwise, same-sample uncertainty; no all-method intersection requirement.
    rng=np.random.default_rng(20260923);paired=[]
    wmle=data[data.method_variant.eq('wmle_checked') & valid][KEY+['joint_squared']]
    for method in METHODS:
        if method=='wmle_checked':continue
        candidate=data[data.method_variant.eq(method) & valid][KEY+['joint_squared']]
        common=candidate.merge(wmle,on=KEY,suffixes=('_method','_wmle'),validate='one_to_one')
        for n,part in common.groupby('n'):
            count=len(part);draws=np.zeros((2000,2))
            for _,block in part.groupby('block'):
                arr=block[['joint_squared_method','joint_squared_wmle']].to_numpy()
                idx=rng.integers(0,len(arr),size=(2000,len(arr)));draws+=arr[idx].sum(axis=1)
            boot=np.sqrt(draws[:,0]/count)-np.sqrt(draws[:,1]/count)
            jm=float(np.sqrt(part.joint_squared_method.mean()));jw=float(np.sqrt(part.joint_squared_wmle.mean()))
            paired.append(dict(method_variant=method,n=int(n),common_samples=count,J1_method=jm,J1_wmle=jw,
                delta_J1=jm-jw,ci95_low=float(np.quantile(boot,.025)),ci95_high=float(np.quantile(boot,.975)),
                bootstrap_draws=2000,bootstrap_seed=20260923))
    pd.DataFrame(paired).to_csv(HERE/'paired_vs_wmle.csv',index=False)
    old=pd.read_csv(PRIOR/'per_sample.csv.gz')
    old=old[(old.beta==2)&(old.eta==1000)&(old.gamma==1000)]
    mapping={'cw_i_nonnegative':'mmle_i','cw_i_paper_domain':'mmle_i_paper','wmle_checked':'wmle_checked'}
    old['method_variant']=old.method_variant.map(mapping)
    reused=data[(data.block==0)&data.method_variant.isin(mapping.values())].merge(old,
        on=['n','repeat_id','method_variant'],suffixes=('','_old'),validate='one_to_one')
    assert len(reused)==1500
    assert reused.sample_sha256.eq(reused.sample_sha256_old).all()
    assert reused.status.eq(reused.status_old).all()
    for p in ['beta_hat','eta_hat','gamma_hat']:
        assert np.allclose(reused[p],reused[p+'_old'],rtol=1e-12,atol=1e-9,equal_nan=True),p
    environment=dict(python=platform.python_version(),python_executable=sys.executable,numpy=np.__version__,pandas=pd.__version__,
                     scipy=scipy.__version__,matplotlib=matplotlib.__version__)
    (HERE/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
    manifest=dict(contract=CONFIG,methods=LABELS,total_samples=6000,total_rows=len(data),blocks=60,
                  source_sha256=hashes,code_version=manifests[0]['code_version'],
                  analysis_source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                    for name in ['summarize.py','verify.py','verify_results.py','plot.py','refine.py','verify_refinement.py']},
                  root_refinement=dict(initial_rows_retained=90000,refined_method_rows=66000,
                      changed_rows=len(amendments),refinement_sha256=refinement_hash(),
                      strategy='bounded local extrema; explicit MMLE-III beta1 root'),
                  reused_samples_verified=500,reused_method_rows_verified=1500,new_samples=5500,
                  precision_policy='own successful samples; pairwise common-success supplement',
                  J1_definition='sqrt(mean((beta_error/2)^2+(eta_error/1000)^2+(gamma_error/1000)^2))')
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(own[['method_variant','n','valid','success_rate','J1_valid']].to_string(index=False))

if __name__=='__main__':main()
