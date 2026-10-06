"""Original minimum-delete-one Kundu-Raqab MMLE; reuse the preceding MLE/WMLE fits."""
import argparse,hashlib,json,sys
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;REPO=BATCH.parents[3]
PREVIOUS=BATCH.parent/'20261005-MMLEI参数域与求解复核'
sys.path.insert(0,str(REPO/'python'))
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.sample import generate_sample
from studies.common.experiment import run_experiment
from studies.common.metrics import check_status,param_absolute_errors,param_relative_errors,aggregate_standard_metrics
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
class KROriginal(WeibullBase):
    def run(self):
        gamma=float(self.data[0]);y=self.data[1:]-gamma;logs=np.log(y);q=len(y)
        beta=float(CFG['initial_shape']);converged=False;history=[];difference=float('inf')
        for iteration in range(1,CFG['max_iterations']+1):
            weights=np.exp(beta*(logs-logs.max()));weights/=weights.sum()
            denominator=float(q*(weights@logs));next_beta=float((q+beta*logs.sum())/denominator)
            if not np.isfinite(next_beta) or next_beta<=0:break
            difference=abs(next_beta-beta)
            if iteration<=3:history.append(dict(iteration=iteration,shape_before=beta,shape_after=next_beta))
            beta=next_beta
            if difference<=CFG['shape_absolute_step_tolerance']:converged=True;break
        self.last_solution_info=dict(status='ok' if converged else 'fixed_point_not_converged',iterations=iteration,
             initial_shape=CFG['initial_shape'],final_shape_step=float(difference),deleted_observations=1,
             gamma_is_original_sample_minimum=True,effective_sample_min=float(self.data[1]),first_iterations=history,
             no_firth=True,no_domain_caps=True,no_fallback=True)
        if not converged:return [None,None,None,0.,False]
        eta=float(np.exp((logsumexp(beta*logs)-np.log(q))/beta))
        return [beta,eta,gamma,0.,True]
def namespace(b):return CFG['seed_namespace'] if b==0 else f"{CFG['seed_namespace']}:research09-versions:block{b:02d}"
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    files=[Path(__file__),HERE/'config.json',PREVIOUS/'三方法原文口径/per_sample.csv.gz',HERE/'输入样本.npz',
           REPO/'python/base.py',REPO/'python/methods/registry.py',REPO/'python/studies/common/sample.py',
           REPO/'python/studies/common/runner.py',REPO/'python/studies/common/experiment.py',REPO/'python/studies/common/metrics.py']
    return {str(p):digest(p) for p in files}
def block(args):
    n,b,hashes=args;dest=HERE/'blocks'/f'n{n:02d}_block{b:02d}';marker=dest/'manifest.json'
    if marker.exists():
        assert json.loads(marker.read_text(encoding='utf-8'))['source_sha256']==hashes
        return n,b,'existing'
    IMPLEMENTED['kr_original']=KROriginal
    run_experiment([('kr_original',dict(variant='K-R MMLE'))],[tuple(CFG['truth'])],[n],100,str(dest),seed_namespace=namespace(b),
                   code_version='original-minimum-delete-one-fixed-point',run_label=CFG['task_id'])
    rows=pd.read_csv(dest/'results.csv');rows['block']=b;rows['pipeline_initial_status']=rows.status
    aggregators=[]
    for index,row in rows.iterrows():
        raw=generate_sample(*CFG['truth'],n,int(row.repeat_id),seed=namespace(b));sha=hashlib.sha256(raw.tobytes()).hexdigest()
        rows.at[index,'sample_sha256']=sha;rows.at[index,'sample_min']=raw[0];rows.at[index,'retained_sample_min']=raw[1]
        finite=all(np.isfinite(row[key]) for key in ['beta_hat','eta_hat','gamma_hat'])
        status=check_status(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth'],converged=bool(row.converged),sample_min=raw[1],boundary_tol=0.) if finite else 'failure'
        rows.at[index,'status']=status
        if status=='success':
            for p,e in param_absolute_errors(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth']).items():rows.at[index,p+'_error']=e
            for p,e in param_relative_errors(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth']).items():rows.at[index,p+'_rel_error']=e
        aggregators.append(dict(beta_hat=row.beta_hat,eta_hat=row.eta_hat,gamma_hat=row.gamma_hat,
                    beta=2.,eta=1000.,gamma=1000.,converged=bool(row.converged),sample_min=raw[1],time=row.time))
    rows.to_csv(dest/'results.csv',index=False)
    (dest/'retained_support_summary.json').write_text(json.dumps(aggregate_standard_metrics(aggregators),ensure_ascii=False,indent=2),encoding='utf-8')
    metadata=json.loads(marker.read_text(encoding='utf-8'));metadata.update(block=b,source_sha256=hashes,
          support_evaluated_on_retained_observations=True,pipeline_initial_status_preserved=True)
    marker.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return n,b,'complete'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    hashes=sources();jobs=[(n,b,hashes) for n in CFG['n'] for b in range(12)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(block,j) for j in jobs]),1):
            if i%12==0:print(dict(finished=i,total=60,block=f.result()),flush=True)
            else:f.result()
    assert hashes==sources()
    kr=pd.concat([pd.read_csv(HERE/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b,_ in jobs],ignore_index=True)
    old=pd.read_csv(PREVIOUS/'三方法原文口径/per_sample.csv.gz');old=old[old.method_variant.isin(['MLE','WMLE'])].copy()
    assert set(kr.sample_sha256)==set(old.sample_sha256) and len(kr)==6000
    d=pd.concat([old,kr],ignore_index=True);d.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    (HERE/'运行核验.json').write_text(json.dumps(dict(source_sha256=hashes,rows=18000,reused_input_samples=6000,
        reused_MLE_WMLE_rows=12000,new_KR_estimates=6000,no_recovery=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print(d.groupby(['method_variant','n','status']).size().to_string())
if __name__=='__main__':main()
