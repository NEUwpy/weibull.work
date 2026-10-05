"""Repeat only CW-I on the original 6000 shared samples, with two declared domains."""
import argparse,hashlib,json,sys
from functools import lru_cache
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
sys.path.insert(0,str(REPO/'python'))
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.experiment import run_experiment
from studies.common.sample import generate_sample
from domain_solver import analyze,CFG
BASE=HERE.parent/'20261005-MLE-MMLE-WMLE三方法'
OLD=pd.read_csv(BASE/'per_sample.csv.gz')
OLD=OLD[OLD.method_variant=='MMLE'].copy()
FAILED=set(OLD.loc[OLD.status!='success','sample_sha256'])

def namespace(block):
    return CFG['base_seed_namespace'] if block==0 else f"{CFG['base_seed_namespace']}:research09-versions:block{block:02d}"

@lru_cache(maxsize=4)
def solve(values):
    raw=np.array(values,float);sha=hashlib.sha256(raw.tobytes()).hexdigest()
    record,curve=analyze(raw,sha in FAILED)
    if sha in FAILED:
        dest=HERE/'逐样本曲线';dest.mkdir(exist_ok=True)
        np.savez_compressed(dest/f'{sha}.npz',sample=raw,**curve)
    return record

class CWEngineering(WeibullBase):
    policy='engineering'
    def run(self):
        record=solve(tuple(self.data));fit=record['fits'][self.policy]
        self.last_solution_info=dict(status=fit['status'],policy=self.policy,diagnostic=record)
        estimate=fit['estimate']
        if estimate is None:return [None,None,None,0.0,False]
        return [estimate['beta'],estimate['eta'],estimate['gamma'],0.0,True]

class CWPaper(CWEngineering):policy='paper'

def sources():
    paths=[HERE/'run_domains.py',HERE/'domain_solver.py',HERE/'config.json',BASE/'per_sample.csv.gz',
           REPO/'python/studies/common/sample.py',REPO/'python/studies/common/runner.py',
           REPO/'python/studies/common/experiment.py',REPO/'python/studies/common/metrics.py']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def run_block(args):
    n,block,hashes=args;dest=HERE/'blocks'/f'n{n:02d}_block{block:02d}';marker=dest/'manifest.json'
    if marker.exists():
        assert json.loads(marker.read_text(encoding='utf-8'))['source_sha256']==hashes
        return n,block,'existing'
    IMPLEMENTED['cw_engineering']=CWEngineering;IMPLEMENTED['cw_paper']=CWPaper
    run_experiment(['cw_engineering','cw_paper'],[tuple(CFG['truth'])],[n],CFG['repeats'],str(dest),
                   seed_namespace=namespace(block),code_version='research-wrapper-006',run_label=CFG['task_id'])
    rows=pd.read_csv(dest/'results.csv');rows['block']=block
    shas={rid:hashlib.sha256(generate_sample(*CFG['truth'],n,rid,seed=namespace(block)).tobytes()).hexdigest() for rid in range(CFG['repeats'])}
    rows['sample_sha256']=rows.repeat_id.map(shas)
    assert set(shas.values())==set(OLD.loc[(OLD.n==n)&(OLD.block==block),'sample_sha256'])
    rows.to_csv(dest/'results.csv',index=False)
    record=json.loads(marker.read_text(encoding='utf-8'));record.update(source_sha256=hashes,block=block)
    marker.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return n,block,'complete'

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);args=p.parse_args();hashes=sources()
    jobs=[(n,b,hashes) for n in CFG['n_values'] for b in range(CFG['blocks'])]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(run_block,j) for j in jobs]),1):
            print(dict(finished=i,total=len(jobs),block=f.result()),flush=True)
    assert hashes==sources()
    all_rows=pd.concat([pd.read_csv(HERE/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b,_ in jobs],ignore_index=True)
    all_rows.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    assert len(all_rows)==12000 and all_rows.sample_sha256.nunique()==6000
    (HERE/'运行核验.json').write_text(json.dumps(dict(source_sha256=hashes,rows=12000,samples=6000,
            curves=len(list((HERE/'逐样本曲线').glob('*.npz'))),counts=all_rows.groupby(['method_variant','n','status']).size().to_dict().__str__()),ensure_ascii=False,indent=2),encoding='utf-8')
    print(all_rows.groupby(['method_variant','n','status']).size().to_string(),flush=True)

if __name__=='__main__':main()
