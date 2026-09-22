"""Paired target-only pilot: joint loss vs gamma loss, same MLP and five folds.

Reuses old samples; this is a development comparison, not fresh confirmation.
The held-out parameter cells and network initialization seed are matched.
"""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REPO = STUDY.parents[1]
sys.path[:0] = [str(STUDY/"code"), str(REPO/"python")]
import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
from run_E7_scale_invariant_input_screen import represent_sample
from studies.common.sample import generate_sample
from paper_support import j1_from_loss

OUT = HERE / "results/training"
RUNTIME = OUT / "runtime"
CELLS = list(product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID))
KEYS = E6.SAMPLE_KEYS
GRID = np.asarray(CFG.DELTA_GRID)
SEED = 42


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    OUT.mkdir(exist_ok=True)
    RUNTIME.mkdir(exist_ok=True)
    receipt = json.loads((HERE/"results/summary.json").read_text(encoding="utf-8"))
    for name, value in receipt["inputs"].items():
        assert sha(STUDY/name) == value
    contract = dict(seed=SEED, objectives=["joint", "gamma"], n_values=CFG.N_GRID,
                    folds=5, split="Original 160-cell index modulo 5; within n, hold out a full gamma/eta layer",
                    train_per_fold=9600, test_per_fold=2400, repeated_samples=48000,
                    representation="sort(X)/mean(X), with training-only per-position StandardScaler",
                    targets="26 candidate loss values; joint is sum of three normalized squared errors; gamma is squared error normalized by eta",
                    layers=list(CFG.MLP_HIDDEN_LAYERS), max_iter=CFG.MLP_MAX_ITER,
                    alpha=CFG.MLP_ALPHA, learning_rate=CFG.MLP_LR,batch_size=CFG.MLP_BATCH_SIZE,
                    early_stopping=True,validation_fraction=CFG.MLP_VALIDATION_FRACTION,
                    n_iter_no_change=CFG.MLP_N_ITER_NO_CHANGE,
                    target_scaling="training-only StandardScaler, independently fitted for each objective",
                    selection="Clip predicted candidate losses at zero then argmin, first/lower delta on ties, same as existing learned pipeline",
                    scope="Single-seed paired development test, old samples; no tuning, no independent confirmation",
                    dependencies={str(p.relative_to(REPO)).replace("\\","/"):sha(p) for p in (
                        Path(__file__), Path(E6.__file__), STUDY/"code/dim_raw_config.py",
                        STUDY/"code/run_E7_scale_invariant_input_screen.py", REPO/"python/studies/common/sample.py")},
                    source_receipt_sha256=sha(HERE/"results/summary.json"))
    path=OUT/"contract.json"
    if path.exists():
        assert json.loads(path.read_text(encoding="utf-8"))==contract
    else:
        path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return sha(path)


def train_n(n, receipt, smoke=False):
    chunks = []
    for i, cell in enumerate(CELLS):
        if cell[2] == n:
            p=STUDY/f"artifacts/formal/E5_normalized_raw/shared_data/chunks/chunk_{i:04d}_mdm.csv"
            chunks.append(pd.read_csv(p))
    frame=E6.compute_per_sample_loss(pd.concat(chunks,ignore_index=True))
    assert frame.status.eq("success").all()
    frame=frame.set_index(KEYS+["delta"]).sort_index()
    joint=frame.loss.unstack("delta").sort_index()
    keys=joint.index.to_frame(index=False)
    assert len(keys)==12000
    errors={}
    for name,scale in (("beta","beta"),("eta","eta"),("gamma","eta")):
        estimate=frame[name+"_hat"].unstack("delta").reindex(joint.index).to_numpy()
        errors[name]=((estimate-keys[name].to_numpy()[:,None])/keys[scale].to_numpy()[:,None])**2
    labels={"joint":joint.to_numpy(), "gamma":errors["gamma"]}
    np.testing.assert_allclose(sum(errors.values()),labels["joint"],atol=1e-12)
    x=np.stack([represent_sample(generate_sample(float(r.beta),float(r.eta),float(r.gamma),int(r.n),int(r.repeat_id),seed=CFG.SEED_NAMESPACE),"mean") for r in keys.itertuples()])
    fold_map={cell:i%5 for i,cell in enumerate(CELLS)}
    folds=np.array([fold_map[(r.beta,r.gamma_over_eta,r.n)] for r in keys.itertuples()])
    for fold in ([0] if smoke else range(5)):
        train=folds!=fold; test=~train; idx=np.flatnonzero(test)
        assert train.sum()==9600 and test.sum()==2400
        assert set(keys.loc[train,"gamma_over_eta"]).isdisjoint(set(keys.loc[test,"gamma_over_eta"]))
        for objective in ("joint","gamma"):
            tag=f"{objective}_n{n}_fold{fold+1}_seed42"
            meta_path=RUNTIME/f"{tag}.json"
            csv_path=RUNTIME/f"{tag}.csv"
            model_path=RUNTIME/f"{tag}.joblib"
            pred_path=RUNTIME/f"{tag}_prediction.npy"
            if meta_path.exists():
                meta=json.loads(meta_path.read_text(encoding="utf-8"))
                assert meta["contract_sha256"]==receipt
                assert all(sha(RUNTIME/name)==value for name,value in meta["files"].items())
                continue
            started=time.perf_counter()
            predicted,iters,ins,outs,model=E6.train_specialist(x[train],labels[objective][train],x[test],SEED)
            assert np.isfinite(predicted).all()
            chosen=predicted.argmin(axis=1)
            result=keys.loc[test].copy()
            result["objective"]=objective;result["fold"]=fold+1
            result["selected_delta"]=GRID[chosen]
            result["joint_loss"]=labels["joint"][idx,chosen]
            result["default_loss"]=labels["joint"][idx,5]
            for name in errors:
                result[name+"_se"]=errors[name][idx,chosen]
                result["default_"+name+"_se"]=errors[name][idx,5]
            result.to_csv(csv_path,index=False)
            np.save(pred_path,predicted)
            joblib.dump(dict(model=model,input_scaler=ins,target_scaler=outs,objective=objective,
                             n=n,fold=fold+1,seed=SEED,delta_grid=GRID),model_path,compress=3)
            # Round-trip model serialization must preserve candidate predictions.
            check=joblib.load(model_path)
            recovered=np.maximum(check["target_scaler"].inverse_transform(check["model"].predict(check["input_scaler"].transform(x[test][:3]))),0)
            np.testing.assert_allclose(recovered,predicted[:3],rtol=1e-10,atol=1e-10)
            meta=dict(tag=tag,contract_sha256=receipt,iterations=iters,seconds=time.perf_counter()-started,
                      train_rows=int(train.sum()),test_rows=int(test.sum()),
                      files={p.name:sha(p) for p in (csv_path,model_path,pred_path)})
            meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(f"{tag} done; {iters} iterations; {meta['seconds']:.1f}s",flush=True)
    return n


def summarize():
    paths=sorted(RUNTIME.glob("*_seed42.csv"));assert len(paths)==40
    data=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
    assert len(data)==96000 and not data.duplicated(KEYS+["objective"]).any()
    joint=data[data.objective=="joint"].set_index(KEYS).sort_index()
    gamma=data[data.objective=="gamma"].set_index(KEYS).sort_index()
    assert joint.index.equals(gamma.index)
    records=[];groups=[]
    for name,part in (("fixed_010",joint),("joint_target_retrained",joint),("gamma_target_trained",gamma)):
        prefix="default_" if name=="fixed_010" else ""
        loss_col="default_loss" if name=="fixed_010" else "joint_loss"
        def metrics(g):
            out=dict(count=len(g),J1=j1_from_loss(g[loss_col]),loss_p99=float(g[loss_col].quantile(.99)))
            for param in ("beta","eta","gamma"):
                out[param+"_RMSE"]=float(np.sqrt(g[prefix+param+"_se"].mean()))
            return out
        records.append(dict(rule=name,**metrics(part)))
        for grouping in (["n"],["beta"],["gamma_over_eta"],KEYS[:-1]):
            for key,g in part.reset_index().groupby(grouping):
                values=key if isinstance(key,tuple) else (key,)
                groups.append(dict(rule=name,group="cell" if len(grouping)>1 else grouping[0],**dict(zip(grouping,values)),**metrics(g)))
    result=pd.DataFrame(records)
    result.to_csv(OUT/"comparison.csv",index=False)
    pd.DataFrame(groups).to_csv(OUT/"by_group.csv",index=False)
    # Paired resampling within each design cell; conditional on this single trained seed.
    arrays=np.stack([joint.joint_loss.to_numpy(),gamma.joint_loss.to_numpy(),joint.gamma_se.to_numpy(),gamma.gamma_se.to_numpy()],axis=-1).reshape(160,300,4)
    rng=np.random.default_rng(20260923);boot=[]
    for _ in range(2000):
        picks=rng.integers(300,size=(160,300))
        rms=np.sqrt(arrays[np.arange(160)[:,None],picks].mean(axis=(0,1)))
        boot.append([100*(1-rms[1]/rms[0]),100*(1-rms[3]/rms[2])])
    intervals=np.quantile(boot,[.025,.975],axis=0)
    summary=dict(comparison=records,
                 gamma_target_vs_joint_J1_improvement_ci=intervals[:,0].tolist(),
                 gamma_target_vs_joint_gamma_RMSE_improvement_ci=intervals[:,1].tolist(),
                 equal_selected_delta=int((joint.selected_delta==gamma.selected_delta).sum()),
                 gamma_better_joint_worse=int(((gamma.gamma_se<joint.gamma_se-1e-12)&(gamma.joint_loss>joint.joint_loss+1e-12)).sum()),
                 scope="Matched single-seed five-fold development comparison, not untouched confirmation or multi-seed evidence",
                 contract_sha256=sha(OUT/"contract.json"),
                 model_receipts=[json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNTIME.glob("*_seed42.json"))])
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(result.to_string(index=False),flush=True)
    print('gamma vs joint improvement intervals:',intervals.tolist(),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--summary',action='store_true');args=parser.parse_args()
    receipt=freeze()
    if args.summary:summarize()
    elif args.smoke:train_n(7,receipt,True)
    else:
        with ProcessPoolExecutor(max_workers=2) as pool:
            for future in as_completed([pool.submit(train_n,n,receipt) for n in CFG.N_GRID]):
                print('n completed:',future.result(),flush=True)
        summarize()
