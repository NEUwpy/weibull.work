"""Paired delta experiment on archived Study04 data, through frozen pipeline."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
CORE=STUDY/'程序/计算实现-20261016'
OUT=STUDY/'结果呈现/分析数据/3.1-MDM偏移量与廓线群体'
sys.path.insert(0,str(CORE))
from studies.common.experiment import run_experiment
from 绘制嵌套样本拟合 import nested_samples

NS=[50,20,15,10,7]
METHODS=[('mdm',{'offset':0.,'variant':'MDM-0'}),('mdm',{'offset':.1,'variant':'MDM-0.1'})]
_TABLES={}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def validate():
    config=json.loads((STUDY/'程序/实验配置.json').read_text(encoding='utf-8'))
    meta=json.loads((STUDY/'结果/数据说明.json').read_text(encoding='utf-8'))
    files={}
    for name,digest in config['source_sha256'].items():
        assert sha(CORE/name)==digest,name
        files['程序/计算实现-20261016/'+name]=digest
    for name,digest in meta['file_sha256'].items():
        if name.startswith('W5,1000,500/'):
            assert sha(STUDY/'结果'/name)==digest,name
            files['结果/'+name]=digest
    files['结果呈现/比较探索/3.1偏移量与廓线群体验证-方案.md']=sha(HERE/'3.1偏移量与廓线群体验证-方案.md')
    return files


def table(n):
    if n not in _TABLES:
        p=STUDY/f'结果/W5,1000,500/估计结果/n{n}.csv'
        d=pd.read_csv(p,float_precision='round_trip').set_index('样本编号')
        assert len(d)==1200 and d.index.tolist()==list(range(1200))
        _TABLES[n]=d
    return _TABLES[n]


def saved(n,rid):
    row=table(n).loc[rid]
    x=row[[f'观测值{i}' for i in range(1,n+1)]].to_numpy(float)
    assert row['MDM-0.1_状态']=='success'
    result=dict(method_id='mdm',method_variant='MDM-0.1',
        beta_hat=float(row['MDM-0.1_形状估计']),eta_hat=float(row['MDM-0.1_尺度估计']),
        gamma_hat=float(row['MDM-0.1_位置估计']),r_squared=None,converged=True,time=0.,
        sample_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
        extra={'archived_variant':'MDM-0.1','archive_source':f'结果/W5,1000,500/估计结果/n{n}.csv'})
    return x,result


def row_result(row):
    extra=json.loads(row.extra) if isinstance(row.extra,str) else dict(row.extra)
    return dict(method_id='mdm',method_variant=row.method_variant,
                **{k:None if pd.isna(row[k]) else float(row[k]) for k in ['beta_hat','eta_hat','gamma_hat','r_squared']},
                converged=str(row.converged).lower()=='true',time=float(row.time),extra=extra,
                sample_sha256=extra['experiment']['sample_sha256'])


def run_job(job):
    kind,n,ids=job
    dest=OUT/'分片'/kind/f'n{n}-id{ids[0]:04d}'
    done=dest/'完成.json'
    identity=dict(kind=kind,n=n,source_ids=ids,methods=METHODS,boundary_tol=0.,
                  source_sha256=sha(STUDY/f'结果/W5,1000,500/估计结果/n{50 if kind=="nested" else n}.csv'))
    # JSON converts tuple method specs to lists.
    identity=json.loads(json.dumps(identity))
    if done.exists():
        record=json.loads(done.read_text(encoding='utf-8'))
        previous=dict(record['identity']);previous.pop('program_sha256',None)
        assert previous==identity
        assert sha(dest/'results.csv')==record['results_sha256']
        return dict(kind=kind,n=n,first_id=ids[0],cached=True)
    samples={};cache={}
    primary=None
    if kind=='nested':
        primary=pd.read_csv(OUT/'正式样本/results.csv',float_precision='round_trip')
        primary=primary[primary.n.eq(50)].set_index(['repeat_id','method_variant'],drop=False)
        frame=table(50).reset_index()
        paths=nested_samples(frame,ids)
    for rid,sid in enumerate(ids):
        if kind=='primary':
            x,result=saved(n,sid)
            cache[5.,1000.,500.,n,rid,'MDM-0.1']=result
        else:
            x=paths[sid,n]
            if n==50:
                for variant in ['MDM-0','MDM-0.1']:
                    result=row_result(primary.loc[sid,variant])
                    cache[5.,1000.,500.,n,rid,variant]=result
        samples[rid]=x
    run_experiment(METHODS,[(5.,1000.,500.)],[n],len(ids),str(dest),
                   sample_provider=lambda b,e,g,count,rid:samples[rid],
                   precomputed_results=cache,boundary_tol=0.,
                   code_version='Study04 frozen 20261016 '+sha(CORE/'methods/mdm.py')[:12],
                   run_label='Study04 delta contrast '+kind+'; source_ids in 完成.json')
    dump(done,dict(identity=identity,program_sha256=sha(Path(__file__)),results_sha256=sha(dest/'results.csv')))
    return dict(kind=kind,n=n,first_id=ids[0],cached=False)


def assemble(kind,ids):
    destination=OUT/('正式样本' if kind=='primary' else '嵌套路径')
    cache={}
    for done in sorted((OUT/'分片'/kind).glob('*/完成.json')):
        record=json.loads(done.read_text(encoding='utf-8'))
        p=done.parent/'results.csv';assert sha(p)==record['results_sha256']
        d=pd.read_csv(p,float_precision='round_trip')
        source_ids=record['identity']['source_ids']
        for _,row in d.iterrows():
            sid=source_ids[int(row.repeat_id)]
            rid=ids.index(sid)
            key=(5.,1000.,500.,int(row.n),rid,row.method_variant)
            assert key not in cache
            cache[key]=row_result(row)
    assert len(cache)==len(ids)*len(NS)*2,(kind,len(cache))
    paths=nested_samples(table(50).reset_index(),ids) if kind=='nested' else None
    def provider(b,e,g,n,rid):
        return saved(n,ids[rid])[0] if paths is None else paths[ids[rid],n]
    summaries=run_experiment(METHODS,[(5.,1000.,500.)],NS,len(ids),str(destination),
        sample_provider=provider,precomputed_results=cache,boundary_tol=0.,
        code_version='Study04 frozen 20261016 '+sha(CORE/'methods/mdm.py')[:12],
        run_label='Study04 paired delta contrast '+kind+'; all rows assembled from verified shards')
    dump(destination/'来源映射.json',dict(kind=kind,repeat_id_to_source_id=ids,
        sample_kind='independent formal cells' if kind=='primary' else 'paired nested subsets of n50',
        n=NS,seed_rule=None if kind=='primary' else '20261023+source_id',
        results_sha256=sha(destination/'results.csv')))
    return summaries


def compute(kind,workers):
    ids=list(range(1200)) if kind=='primary' else list(range(0,1200,10))
    chunk=100 if kind=='primary' else 30
    jobs=[(kind,n,ids[i:i+chunk]) for n in NS for i in range(0,len(ids),chunk)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_job,j):j for j in jobs}
        for i,future in enumerate(as_completed(futures),1):
            result=future.result()
            print(json.dumps(dict(completed=i,total=len(jobs),**result)),flush=True)
    assemble(kind,ids)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['primary','nested','both'],default='both')
    parser.add_argument('--workers',type=int,default=min(8,os.cpu_count() or 1))
    args=parser.parse_args()
    sources=validate()
    OUT.mkdir(parents=True,exist_ok=True)
    identity=dict(sources=sources,program_sha256=sha(Path(__file__)),
                  git_base=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  new_weibull_samples=0,formal_conditions=dict(beta=5.,eta=1000.,gamma=500.,n=NS,repeats=1200),
                  nested_source_ids=list(range(0,1200,10)),seed_rule='20261023+source_id')
    path=OUT/'输入与设计.json'
    if path.exists():
        previous=json.loads(path.read_text(encoding='utf-8'))
        # Wrapper bookkeeping fixes do not invalidate unchanged sample/method caches.
        initial=previous.pop('program_sha256');current=identity.pop('program_sha256')
        assert previous==identity
        if initial!=current:dump(OUT/'包装修复.json',dict(initial_program_sha256=initial,
            current_program_sha256=current,change='Preserve method_variant when indexing cached n50 rows; frozen estimator and sampling contract unchanged.'))
    else:dump(path,identity)
    for kind in ['primary','nested'] if args.kind=='both' else [args.kind]:compute(kind,args.workers)
    assert validate()==sources
    print(json.dumps(dict(status='complete',kind=args.kind,output=str(OUT)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
