"""Bounded submission controls, reusing the shared training and sample pipeline."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import torch
from . import config as CFG, data as DATA, losses as LOSS, model as MODEL, training as TR

ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT/'artifacts/submission_controls_v1'
SEEDS = [42,2026,3407,17,73,314,2718,4099,8128,12011]
MASTER = None

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def clean(value):
    if isinstance(value, dict): return {k:clean(v) for k,v in value.items()}
    if isinstance(value, list): return [clean(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value): return None
    return value

def init():
    global MASTER
    if CFG.PROTOCOL_ID != 'iid-v1': raise RuntimeError('Set PQ_PROTOCOL=iid-v1')
    torch.set_num_threads(1)
    MASTER = DATA.build_master()

def save_predictions(path, pred):
    keys = pred['keys']
    np.savez_compressed(path, keys_beta=keys[:,0], keys_gamma_over_eta=keys[:,1],
        keys_n=keys[:,2].astype(np.int16), keys_repeat_id=keys[:,3].astype(np.int32),
        **{k:pred[k] for k in ('beta_hat','eta_hat','gamma_hat','min_x','rel_err')})

class FeasibleObserver:
    def __init__(self, limit):
        self.limit=limit; self.state=None; self.best=float('inf'); self.epoch=None; self.history=[]
    def __call__(self, epoch, model, val_out, params, minima):
        q,p=LOSS.parameter_target_loss_components(val_out,params,minima)
        q,p=float(q),float(p)
        self.history.append({'epoch':epoch,'val_q':q,'val_p':p,'feasible':p<=self.limit})
        if p<=self.limit and q<self.best-1e-12:
            self.best=q;self.epoch=epoch;self.state=copy.deepcopy(model.state_dict())

def worker(job):
    n,fold,seed,route=job
    label=f'n{n}_f{fold}_s{seed}_r{route}'
    meta_path=OUT/'fits'/f'{label}.json'
    if meta_path.exists(): return label+' cached'
    obs=None
    if route=='Q':
        refroot=ROOT/'artifacts'/('pq_iid_main' if seed in SEEDS[:3] else 'pq_s5b_revision/grid_extra')
        ref=json.loads((refroot/'fit_metadata'/f'n{n}_f{fold}_s{seed}_rP.json').read_text(encoding='utf-8'))
        obs=FeasibleObserver(1.5*ref['best_val_loss'])
    result=TR.train_one_fit(n,fold-1,seed,route,MASTER,max_epochs=600,patience=60,
        split_strategy='repeat_stratified',record_history=True,return_state=True,
        validation_observer=obs)
    assert result['meta']['converged'] and result['meta']['support_legality_ok']
    for sub in ('fits','predictions','states'): (OUT/sub).mkdir(parents=True,exist_ok=True)
    save_predictions(OUT/'predictions'/f'{label}.npz', result['predictions'])
    torch.save(result['model_state'], OUT/'states'/f'{label}.pt')
    if obs is not None:
        feaslabel=f'n{n}_f{fold}_s{seed}_rQ_FEAS'
        record={'n':n,'fold':fold,'seed':seed,'route':'Q_FEAS','available':obs.state is not None,
                'limit':obs.limit,'epoch':obs.epoch,'history':obs.history,
                'trajectory':'Q native validation-Q early stopping'}
        if obs.state is not None:
            tr,va,te=DATA.split_repeat_fold(MASTER,n,fold-1)
            xtr,_,_=DATA.make_arrays(MASTER,tr);xt,_,truth=DATA.make_arrays(MASTER,te)
            scaler=DATA.PerPositionScaler().fit(xtr)
            model=MODEL.build_model(n,seed);model.load_state_dict(obs.state);model.eval()
            minima=DATA.sample_min(MASTER,te)
            with torch.no_grad():
                bh,eh,gh=LOSS.decode_params(model(TR._tensor(scaler.transform(xt))),TR._tensor(minima))
                err=(LOSS.weibull_quantile(bh,eh,gh).numpy()-truth)/truth
            save_predictions(OUT/'predictions'/f'{feaslabel}.npz',dict(keys=MASTER.keys[te],
                beta_hat=bh.numpy(),eta_hat=eh.numpy(),gamma_hat=gh.numpy(),min_x=minima,rel_err=err))
            torch.save(obs.state,OUT/'states'/f'{feaslabel}.pt')
        dump(OUT/'fits'/f'{feaslabel}.json',clean(record))
    dump(meta_path,clean({'meta':result['meta'],'history':result['history']}))
    return f'{label} RMSRE={result["meta"]["rrmse_x95"]:.7f}'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    jobs=[(n,f,s,r) for s in SEEDS for n in (7,10,15,20) for f in range(1,6) for r in ('P_QSELECT','Q','QMULTI')]
    if args.smoke: jobs=[(7,1,42,r) for r in ('P_QSELECT','Q','QMULTI')]
    if args.workers==1:
        init()
        for j in jobs:print(worker(j),flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers,initializer=init) as pool:
            futures={pool.submit(worker,j):j for j in jobs}
            for i,f in enumerate(as_completed(futures),1):print(f'{i}/{len(jobs)} {f.result()}',flush=True)
    files=[p for d in ('fits','predictions','states') for p in (OUT/d).glob('*')]
    dump(OUT/'manifest.json',{'protocol':'protocols/25-投稿修订补充对照.md','complete_jobs':len(jobs),
        'smoke':args.smoke,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__),Path(TR.__file__),Path(LOSS.__file__),Path(DATA.__file__),Path(MODEL.__file__),Path(CFG.CONFIG_PATH),ROOT/'protocols/25-投稿修订补充对照.md']},
        'output_sha256':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})

if __name__=='__main__':main()
