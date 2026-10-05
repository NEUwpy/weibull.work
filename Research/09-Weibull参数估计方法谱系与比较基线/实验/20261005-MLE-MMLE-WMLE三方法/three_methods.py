"""Reuse preceding samples and MLE/MMLE; run only native WMLE, no recovery."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib,json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
PREVIOUS=HERE.parent/'20261005-MLE-MMLE全版本固定真值比较'
sys.path.insert(0,str(PREVIOUS))
import experiment as previous
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.runner import run_method
from studies.common.experiment import run_experiment

CONFIG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
REPO=previous.REPO

class WMLEFirst(WeibullBase):
    def run(self):
        result=run_method('wmle',self.data/CONFIG['unit_divisor'])
        extra=result.get('extra') or {}
        self.last_solution_info=extra.get('solution_info',{}).copy()
        self.last_solution_info.setdefault('status',extra.get('raw_status','unknown'))
        self.last_solution_info['profile_recovery_used']=False
        if not result['converged']:return [None,None,None,0.0,False]
        return [result['beta_hat'],result['eta_hat']*1000,result['gamma_hat']*1000,
                result.get('r_squared') or 0.0,True]

def sources():
    paths=[HERE/'three_methods.py',HERE/'config.json',PREVIOUS/'per_sample.csv.gz',
           PREVIOUS/'manifest.json',PREVIOUS/'experiment.py',previous.PRIOR/'run.py',
           previous.PRIOR/'config.json',REPO/'python/methods/mle.py',REPO/'python/methods/wmle.py',
           REPO/'python/methods/j3_weights.tsv',REPO/'python/studies/common/sample.py',
           REPO/'python/studies/common/runner.py',REPO/'python/studies/common/experiment.py',
           REPO/'python/studies/common/metrics.py']
    return {str(p.relative_to(REPO)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def run_block(args):
    n,block,hashes,commit=args;dest=HERE/'wmle_blocks'/f'n{n:02d}_block{block:02d}'
    marker=dest/'manifest.json'
    if marker.exists():
        old=json.loads(marker.read_text(encoding='utf-8'));assert old['source_sha256']==hashes
        return n,block,'existing'
    IMPLEMENTED['wmle_first']=WMLEFirst
    run_experiment(['wmle_first'],[tuple(CONFIG['truth'])],[n],100,str(dest),
                   seed_namespace=previous.namespace(block),code_version=commit,
                   run_label=f"{CONFIG['task_id']}:n{n}:block{block}")
    record=json.loads(marker.read_text(encoding='utf-8'));record.update(block=block,source_sha256=hashes,
                         profile_recovery_used=False)
    marker.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    return n,block,'complete'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    hashes=sources();old=json.loads((PREVIOUS/'manifest.json').read_text(encoding='utf-8'))
    # Check current production/shared source against the already verified batch.
    for name,digest in old['source_sha256'].items():
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==digest,name
    jobs=[(n,b,hashes,old['code_version']) for n in CONFIG['n_values'] for b in range(12)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(run_block,j) for j in jobs]),1):
            print(dict(finished=i,total=60,block=f.result()),flush=True)
    assert hashes==sources(),'Source changed during experiment'

if __name__=='__main__':main()
