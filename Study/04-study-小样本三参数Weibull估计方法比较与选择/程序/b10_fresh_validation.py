"""Independent bounded validation using the Study04 frozen shared experiment pipeline."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import time

import numpy as np
import b10_feature_selector as selector
from studies.common.experiment import run_experiment
from studies.common.sample import generate_sample

COHORTS = [
    ('fresh_in_domain', 3.,1000.,500.,10),
    ('beta_interpolation', 2.25,1000.,500.,10),
    ('n_interpolation', 3.,1000.,500.,30),
    ('scale_location', 3.,500.,250.,10),
    ('zero_location', 3.,1000.,0.,10),
]
SEED = 2026102401


def run_cohort(job):
    name,beta,eta,gamma,n,repeats,root = job
    dest = Path(root)/name
    if dest.exists():
        raise FileExistsError(f'Fresh experiment output already exists: {dest}')
    start = time.monotonic()
    run_experiment(selector.CONFIG['methods'], [(beta,eta,gamma)], [n], repeats, str(dest),
        R_levels=(.9,), diagnostic_R_levels=(.9,), seed_namespace=SEED,
        code_version=selector.CONFIG['solver_version'],run_label=f'{selector.VERSION}: {name}',
        boundary_tol=selector.CONFIG['boundary_tol'])
    return dict(name=name,beta=beta,eta=eta,gamma=gamma,n=n,repeats=repeats,
                seconds=time.monotonic()-start)


def run(repeats,workers,smoke):
    selector.verify_source_files()
    root = selector.OUT/('fresh_smoke' if smoke else 'fresh')
    jobs = [(*c,repeats,str(root)) for c in COHORTS]
    records=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_cohort,j) for j in jobs]
        for f in as_completed(futures):
            record=f.result()
            records.append(record)
            print(json.dumps(record),flush=True)
    selector.json_write(root/'cohorts.json',records)


def load_cohort(spec):
    name,beta,eta,gamma,n=spec
    path=selector.OUT/'fresh'/name/'results.csv'
    with path.open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    repeats=max(int(r['repeat_id']) for r in rows)+1
    x=np.array([selector.features(generate_sample(beta,eta,gamma,n,rid,seed=SEED)) for rid in range(repeats)])
    e=np.full((repeats,7),np.nan)
    valid=np.zeros((repeats,7),bool)
    seen=set()
    for r in rows:
        i=int(r['repeat_id']);j=selector.METHODS.index(r['method_variant'])
        assert (i,j) not in seen
        seen.add((i,j))
        if r['status']=='success':
            e[i,j]=selector.quantile_est(*[float(r[k]) for k in ['beta_hat','eta_hat','gamma_hat']],.9)-selector.quantile_true(beta,eta,gamma,.9)
            valid[i,j]=True
    assert len(seen)==repeats*7
    return dict(x=x,e=e,valid=valid,beta=np.full(repeats,beta),eta=np.full(repeats,eta),
                gamma=np.full(repeats,gamma),n=np.full(repeats,n),rid=np.arange(repeats),
                cell=np.full(repeats,name))


def evaluate():
    training=selector.load_data()
    selection=json.loads((selector.OUT/'selection.json').read_text(encoding='utf-8'))
    paths=[selector.OUT/p for p in selection['models']]
    results={}
    rows=[]
    for spec in COHORTS:
        target=load_cohort(spec)
        scores=selector.training_rules(training,training['split']==0,target)
        scores['network']=selector.ensemble(paths,target['x'])
        metrics,chosen=selector.evaluate_scores(target,scores)
        ratios={m:float(scores['network'][target['valid'][:,j],j].mean()/np.mean(target['e'][target['valid'][:,j],j]**2))
                for j,m in enumerate(selector.METHODS) if target['valid'][:,j].any()}
        results[spec[0]]=dict(condition=list(spec[1:]),samples=len(target['x']),metrics=metrics,risk_calibration_ratios=ratios)
        for i in range(len(target['x'])):
            rows.append(dict(cohort=spec[0],rid=i,network_error=float(chosen['network'][0][i]),
                fixed_error=float(chosen['fixed'][0][i]),network_first=selector.METHODS[chosen['network'][1][i]],
                network_final=selector.METHODS[chosen['network'][2][i]]))
    selector.json_write(selector.OUT/'fresh_evaluation.json',results)
    selector.csv_write(selector.OUT/'fresh_predictions.csv',rows)
    print(json.dumps({k:dict(network_rmse=v['metrics']['network']['all_attempts']['rmse'],
        fixed_rmse=v['metrics']['fixed']['all_attempts']['rmse'],
        improvement=v['metrics']['network']['improvement_all_pct']) for k,v in results.items()}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['run','evaluate'])
    parser.add_argument('--repeats',type=int,default=200)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    if args.phase=='run':
        run(args.repeats,args.workers,args.smoke)
    else:
        evaluate()
