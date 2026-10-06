"""Run MLE, original Kundu-Raqab MMLE and WMLE through the frozen shared pipeline."""
import argparse, hashlib, json, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp

HERE=Path(__file__).resolve().parent
REPO=HERE/'source_snapshot'
sys.path.insert(0,str(REPO/'python'))
sys.path.insert(0,str(REPO))
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.sample import generate_sample
from studies.common.experiment import run_experiment
from studies.common.metrics import check_status, param_absolute_errors, param_relative_errors, aggregate_standard_metrics
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
# WMLE 口径回退（2026-10-06）：WMLE 由 methods/wmle.py 经典实现计算，与 Research00 生产程序逐字节相同。
CODE_VERSION='same-frozen-methods-gamma500-013+classic-mle-wmle-20261006'

# MLE 与 WMLE 均改用注册表里的经典实现（methods/mle.py、methods/wmle.py），
# 与 Research00 生产程序逐字节相同，口径与旧批一致；不再使用 paper_solver 求根。

# WMLE 不再用 paper_solver 求根，改用注册表里的经典实现 methods/wmle.py
# （与 Research00 生产程序逐字节相同），口径与旧批一致。

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


def namespace(b):
    return CFG['seed_namespace'] if b==0 else f"{CFG['seed_namespace']}:research09-versions:block{b:02d}"

def sources():
    paths=[HERE/'compute.py',HERE/'config.json',*(REPO.rglob('*'))]
    return {str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file() and '__pycache__' not in p.parts}

def block(job):
    n,b,hashes=job
    dest=HERE/'blocks'/f'n{n:02d}_block{b:02d}'
    marker=dest/'manifest.json'
    if marker.exists():
        assert json.loads(marker.read_text(encoding='utf-8'))['source_sha256']==hashes
        return n,b,'existing'
    IMPLEMENTED['kr_original']=KROriginal
    run_experiment([('mle',dict(variant='MLE')),('kr_original',dict(variant='K-R MMLE')),
                    ('wmle',dict(variant='WMLE'))], [tuple(CFG['truth'])],[n],100,str(dest),
                   seed_namespace=namespace(b),code_version=CODE_VERSION,run_label=CFG['task_id'])
    rows=pd.read_csv(dest/'results.csv')
    rows['block']=b
    rows['pipeline_initial_status']=rows.status
    aggregators=[]
    for index,row in rows.iterrows():
        sample=generate_sample(*CFG['truth'],n,int(row.repeat_id),seed=namespace(b))
        rows.at[index,'sample_sha256']=hashlib.sha256(sample.tobytes()).hexdigest()
        rows.at[index,'sample_min']=sample[0]
        minimum=sample[1] if row.method_variant=='K-R MMLE' else sample[0]
        rows.at[index,'retained_sample_min']=minimum
        finite=all(np.isfinite(row[p+'_hat']) for p in ['beta','eta','gamma'])
        status=check_status(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth'],
                            converged=bool(row.converged),sample_min=minimum,boundary_tol=0.) if finite else 'failure'
        rows.at[index,'status']=status
        if status=='success':
            for p,v in param_absolute_errors(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth']).items():rows.at[index,p+'_error']=v
            for p,v in param_relative_errors(row.beta_hat,row.eta_hat,row.gamma_hat,*CFG['truth']).items():rows.at[index,p+'_rel_error']=v
        aggregators.append(dict(beta_hat=row.beta_hat,eta_hat=row.eta_hat,gamma_hat=row.gamma_hat,
                                beta=CFG['truth'][0],eta=CFG['truth'][1],gamma=CFG['truth'][2],
                                converged=bool(row.converged),sample_min=minimum,time=row.time,method=row.method_variant))
    rows.to_csv(dest/'results.csv',index=False)
    checks={m:aggregate_standard_metrics([a for a in aggregators if a['method']==m])
            for m in ['MLE','K-R MMLE','WMLE']}
    (dest/'retained_support_summary.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    metadata=json.loads(marker.read_text(encoding='utf-8'))
    metadata.update(block=b,source_sha256=hashes,support_evaluated_on_retained_observations=True)
    marker.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return n,b,'complete'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    hashes=sources()
    jobs=[(n,b,hashes) for n in CFG['n'] for b in range(CFG['blocks'])]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, future in enumerate(as_completed([pool.submit(block,j) for j in jobs]),1):
            print(json.dumps(dict(finished=i,total=len(jobs),block=future.result())),flush=True)
    assert hashes==sources()
    raw=pd.concat([pd.read_csv(HERE/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b,_ in jobs],ignore_index=True)
    assert len(raw)==18000 and raw.sample_sha256.nunique()==6000
    raw.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    arrays={f'n{n}':np.array([generate_sample(*CFG['truth'],n,rid,seed=namespace(b))
                             for b in range(CFG['blocks']) for rid in range(CFG['repeats'])]) for n in CFG['n']}
    np.savez_compressed(HERE/'输入样本.npz',**arrays)
    (HERE/'运行核验.json').write_text(json.dumps(dict(source_sha256=hashes,rows=18000,samples=6000,
          new_estimates=dict(MLE=6000,MMLE=6000,WMLE=6000),truth=CFG['truth'],seed_includes_truth_gamma=True),
          ensure_ascii=False,indent=2),encoding='utf-8')
    print(raw.groupby(['method_variant','n','status']).size().to_string())

if __name__=='__main__':
    main()
