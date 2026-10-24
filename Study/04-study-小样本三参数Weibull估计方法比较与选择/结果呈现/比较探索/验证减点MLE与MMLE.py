"""Add MLE/MMLE on exactly the preselected MDM nested samples."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json,hashlib,sys
import numpy as np
import pandas as pd
from 验证MDM偏移量与廓线群体 import (STUDY,CORE,OUT,HERE,NS,sha,dump,table,
                                           validate,row_result)
from 绘制嵌套样本拟合 import nested_samples
from studies.common.experiment import run_experiment

METHODS=[('mle',{'variant':'MLE'}),('mmle',{'variant':'MMLE'})]
IDS=list(range(0,1200,10))


def archived(sid,variant,x):
    row=table(50).loc[sid];column='MMLE(KR)' if variant=='MMLE' else 'MLE'
    values={k:None if pd.isna(row[f'{column}_{c}估计']) else float(row[f'{column}_{c}估计'])
            for k,c in [('beta_hat','形状'),('eta_hat','尺度'),('gamma_hat','位置')]}
    mid='mmle' if variant=='MMLE' else 'mle'
    extra=dict(archive_source='结果/W5,1000,500/估计结果/n50.csv',
               archive_converged_inferred_from_saved_validity=True)
    if mid=='mmle':extra['solution_info']=dict(deleted_observations=1,
        gamma_is_original_sample_minimum=True,effective_sample_min=float(x[1]))
    return dict(method_id=mid,method_variant=variant,**values,r_squared=None,
                converged=row[f'{column}_状态']=='success',time=0.,extra=extra,
                sample_sha256=hashlib.sha256(x.tobytes()).hexdigest())


def result(row):
    r=row_result(row);r['method_id']=row.method_id
    return r


def job(args):
    n,ids=args;dest=OUT/'分片/nested-extra'/f'n{n}-id{ids[0]:04d}'
    identity=dict(n=n,source_ids=ids,program_sha256=sha(Path(__file__)),
                  source_sha256=sha(STUDY/'结果/W5,1000,500/估计结果/n50.csv'))
    done=dest/'完成.json'
    if done.exists():
        a=json.loads(done.read_text(encoding='utf-8'));assert a['identity']==identity
        assert sha(dest/'results.csv')==a['results_sha256']
        return dict(n=n,first_id=ids[0],cached=True)
    paths=nested_samples(table(50).reset_index(),ids);cache={}
    if n==50:
        for rid,sid in enumerate(ids):
            for v in ['MLE','MMLE']:cache[5.,1000.,500.,n,rid,v]=archived(sid,v,paths[sid,n])
    run_experiment(METHODS,[(5.,1000.,500.)],[n],len(ids),str(dest),
        sample_provider=lambda b,e,g,count,rid:paths[ids[rid],n],precomputed_results=cache,
        boundary_tol=0.,code_version='Study04 frozen 20261016',
        run_label='Study04 four-method nested extension; source_ids in 完成.json')
    dump(done,dict(identity=identity,results_sha256=sha(dest/'results.csv')))
    return dict(n=n,first_id=ids[0],cached=False)


def assemble():
    cache={}
    for done in sorted((OUT/'分片/nested-extra').glob('*/完成.json')):
        a=json.loads(done.read_text(encoding='utf-8'));p=done.parent/'results.csv'
        assert sha(p)==a['results_sha256']
        for _,row in pd.read_csv(p,float_precision='round_trip').iterrows():
            sid=a['identity']['source_ids'][int(row.repeat_id)]
            key=(5.,1000.,500.,int(row.n),IDS.index(sid),row.method_variant)
            assert key not in cache;cache[key]=result(row)
    assert len(cache)==1200
    mdm=OUT/'嵌套路径/results.csv'
    if not mdm.exists():
        print('MLE/MMLE finished; waiting for separate MDM phase before assembly.',flush=True)
        return
    for _,row in pd.read_csv(mdm,float_precision='round_trip').iterrows():
        key=(5.,1000.,500.,int(row.n),int(row.repeat_id),row.method_variant)
        assert key not in cache;cache[key]=result(row)
    assert len(cache)==2400
    paths=nested_samples(table(50).reset_index(),IDS)
    methods=METHODS+[('mdm',{'offset':0.,'variant':'MDM-0'}),('mdm',{'offset':.1,'variant':'MDM-0.1'})]
    dest=OUT/'嵌套四法'
    run_experiment(methods,[(5.,1000.,500.)],NS,120,str(dest),
        sample_provider=lambda b,e,g,n,rid:paths[IDS[rid],n],precomputed_results=cache,
        boundary_tol=0.,code_version='Study04 frozen 20261016',
        run_label='Study04 four methods on identical nested paths; verified shards')
    dump(dest/'来源映射.json',dict(repeat_id_to_source_id=IDS,n=NS,seed_rule='20261023+source_id',
        results_sha256=sha(dest/'results.csv'),mdm_results_sha256=sha(mdm)))
    print('Four-method nested results assembled.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--assemble-only',action='store_true');args=parser.parse_args()
    before=validate()
    if not args.assemble_only:
        jobs=[(n,IDS[i:i+15]) for n in NS for i in range(0,len(IDS),15)]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            fs=[pool.submit(job,j) for j in jobs]
            for i,f in enumerate(as_completed(fs),1):print(json.dumps(dict(completed=i,total=len(fs),**f.result())),flush=True)
    assemble();assert validate()==before


if __name__=='__main__':main()
