"""Original-author domain main comparison, following the in-flight task supplement."""
import argparse,hashlib,json,sys
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];DEST=HERE/'三方法原文口径'
sys.path.insert(0,str(REPO/'python'))
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.sample import generate_sample
from studies.common.experiment import run_experiment
from paper_solver import solve
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
CW=pd.read_csv(HERE/'per_sample.csv.gz');CW=CW[CW.method_variant=='cw_paper'].set_index('sample_sha256')

class PaperMLE(WeibullBase):
    method='MLE'
    def run(self):
        record=solve(self.data,self.method)
        self.last_solution_info=record;fit=record['estimate']
        if fit is None:return [None,None,None,0.,False]
        return [fit['beta'],fit['eta'],fit['gamma'],0.,True]
class PaperWMLE(PaperMLE):method='WMLE'
class PaperCW(WeibullBase):
    def run(self):
        sha=hashlib.sha256(self.data.tobytes()).hexdigest();old=CW.loc[sha]
        diagnostic=json.loads(old.extra)['solution_info']['diagnostic'];record=diagnostic['fits']['paper']
        self.last_solution_info=dict(status=record['status'],estimate=record['estimate'],reused_verified_profile=True)
        fit=record['estimate']
        if fit is None:return [None,None,None,0.,False]
        return [fit['beta'],fit['eta'],fit['gamma'],0.,True]
def namespace(b):return CFG['base_seed_namespace'] if b==0 else f"{CFG['base_seed_namespace']}:research09-versions:block{b:02d}"
def sources():
    files=[HERE/'run_paper_comparison.py',HERE/'paper_solver.py',HERE/'config.json',HERE/'per_sample.csv.gz',DEST/'config.json',
           REPO/'python/base.py',REPO/'python/methods/registry.py',REPO/'python/methods/wmle.py',REPO/'python/methods/j3_weights.tsv',
           REPO/'python/studies/common/sample.py',REPO/'python/studies/common/runner.py',
           REPO/'python/studies/common/experiment.py',REPO/'python/studies/common/metrics.py']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
def block(job):
    n,b,hashes=job;output=DEST/'blocks'/f'n{n:02d}_block{b:02d}';marker=output/'manifest.json'
    if marker.exists():
        assert json.loads(marker.read_text(encoding='utf-8'))['source_sha256']==hashes
        return n,b,'existing'
    IMPLEMENTED['paper_mle']=PaperMLE;IMPLEMENTED['paper_cw']=PaperCW;IMPLEMENTED['paper_wmle']=PaperWMLE
    run_experiment([('paper_mle',dict(variant='MLE')),('paper_cw',dict(variant='MMLE-I')),('paper_wmle',dict(variant='WMLE'))],
        [tuple(CFG['truth'])],[n],100,str(output),seed_namespace=namespace(b),code_version='original-equations-research-wrapper-006',run_label=CFG['task_id']+':supplement')
    rows=pd.read_csv(output/'results.csv');rows['block']=b
    hashes_by_rid={rid:hashlib.sha256(generate_sample(*CFG['truth'],n,rid,seed=namespace(b)).tobytes()).hexdigest() for rid in range(100)}
    rows['sample_sha256']=rows.repeat_id.map(hashes_by_rid);assert set(rows.sample_sha256)<=set(CW.index)
    rows.to_csv(output/'results.csv',index=False)
    metadata=json.loads(marker.read_text(encoding='utf-8'));metadata.update(block=b,source_sha256=hashes)
    marker.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return n,b,'complete'
def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);args=p.parse_args();DEST.mkdir(exist_ok=True)
    config=dict(task_id=CFG['task_id'],goal_version='g1',supplement='Original-author primary comparison',truth=CFG['truth'],n=CFG['n_values'],samples_per_n=1200,
        common_location='sample mean - 10 sample SD(ddof=1) <= gamma <= sample minimum - 1e-4 raw',common_shape_upper=15.,
        author_shape_lower=dict(MLE=1.01,MMLE_I=.1,WMLE=.1),common_equation_residual_squared_tolerance=1e-8,
        no_extra_gamma_nonnegative=True,no_beta_9_99=True,no_boundaries_substituted_for_equation_roots=True,
        wmle_weights='Saved Cousineau J1,J2,J3 table; original interpolation with clamping at shape 5',precision='All own accepted estimates; SD ddof=0',
        main_comparison='Original MLE likelihood score / CW-I modified location score / Cousineau weighted scores')
    if not (DEST/'config.json').exists():(DEST/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    hashes=sources();jobs=[(n,b,hashes) for n in CFG['n_values'] for b in range(12)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(block,j) for j in jobs]),1):print(dict(finished=i,total=60,block=f.result()),flush=True)
    assert hashes==sources()
    d=pd.concat([pd.read_csv(DEST/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b,_ in jobs],ignore_index=True)
    assert len(d)==18000 and d.sample_sha256.nunique()==6000;d.to_csv(DEST/'per_sample.csv.gz',index=False,compression='gzip')
    (DEST/'运行核验.json').write_text(json.dumps(dict(source_sha256=hashes,rows=18000,samples=6000,new_samples=0,new_MLE_WMLE_estimates=12000,reused_CW_estimates=6000),ensure_ascii=False,indent=2),encoding='utf-8')
    print(d.groupby(['method_variant','n','status']).size().to_string())
if __name__=='__main__':main()
