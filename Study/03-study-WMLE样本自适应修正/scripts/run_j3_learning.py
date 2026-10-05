"""Bounded J3 sample-selector pilot: freeze on validation, then test on fresh draws."""
from pathlib import Path
import os
for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"]:
    os.environ[key]="1"
import argparse
import concurrent.futures as cf
import hashlib
import json
import warnings
import sys
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor

STUDY=Path(__file__).resolve().parents[1]
ROOT=STUDY.parents[1]
OUT=STUDY/"results/j3_learning_v1"
sys.path[:0]=[str(STUDY/"scripts"),str(ROOT/"python")]
import run_j3_scan as scan
from studies.common.sample import generate_sample
GRID=np.array(scan.GRID)
BASE=int(np.where(GRID==1)[0][0])
GATES=[0.,.02,.05]
NAMES=["ridge","tree4","mlp32_ensemble"]
TEST_SEED=2026092303


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(r):
    return generate_sample(float(r["beta"]),float(r["eta"]),float(r["gamma"]),
                           int(r["sample_size"]),int(r["repeat_id"]),seed=int(r["seed_namespace"]))


def features(x):
    """No truth, seed, cohort, sample id, or fitted parameters enter this function."""
    span=np.ptp(x)
    z=(x-x.min())/span
    gaps=np.diff(z)
    mean=z.mean();std=z.std(ddof=1)
    return np.r_[np.log(len(x)),np.log1p(x.min()/span),
                 np.quantile(z,np.arange(.05,1,.05)),mean,std,
                 np.mean((z-mean)**3)/(std**3),
                 gaps[0],gaps[1],np.max(gaps),
                 np.sum(np.sort(gaps)[-2:])]


def matrix(index,rows):
    index=index.sort_values("row_id").reset_index(drop=True)
    context=index[["row_id","beta","eta","gamma"]]
    d=rows.merge(context,on="row_id",validate="many_to_one")
    valid=d.valid.to_numpy(bool)
    errors=np.column_stack([(d.beta_hat-d.beta)/d.beta,(d.eta_hat-d.eta)/d.eta,
                            (d.gamma_hat-d.gamma)/d.eta])
    d["E"]=np.max(abs(errors),axis=1)
    v=d.pivot(index="row_id",columns="c",values="valid").reindex(index=index.row_id,columns=GRID).to_numpy(bool)
    e=d.pivot(index="row_id",columns="c",values="E").reindex(index=index.row_id,columns=GRID).to_numpy(float)
    assert not d.duplicated(["row_id","c"]).any()
    assert len(d)==len(index)*len(GRID)
    # Deployable fallback: only after chosen solver fails, run original c=1 once.
    effective_e=np.where(v,e,e[:,BASE,None])
    effective_v=np.where(v,True,v[:,BASE,None])
    bad=~effective_v|(effective_e>=.5)
    cap=np.nan_to_num(np.minimum(effective_e,2),nan=2)
    return index,d,v,e,effective_v,effective_e,bad,cap


def build(kind):
    if kind=="ridge":
        return [make_pipeline(StandardScaler(),Ridge(alpha=10.))]
    if kind=="tree4":
        return [DecisionTreeRegressor(max_depth=4,min_samples_leaf=40,random_state=42)]
    return [make_pipeline(StandardScaler(),MLPRegressor(
        hidden_layer_sizes=(32,32),activation="relu",alpha=.01,
        learning_rate_init=.001,batch_size=128,max_iter=500,
        early_stopping=True,validation_fraction=.15,n_iter_no_change=30,
        random_state=seed)) for seed in [42,43,44]]


def fit_models(kind,x,y):
    models=build(kind)
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        for model in models:model.fit(x,y)
    return models,[str(w.message) for w in ws]


def predict(models,x):
    return np.mean([model.predict(x) for model in models],axis=0)


def choose(scores,gate):
    # Stable tie preference: c closest to original; no labels inspected here.
    order=np.argsort(abs(GRID-1),kind="stable")
    chosen=order[np.argmin(scores[:,order],axis=1)]
    margin=scores[:,BASE]-scores[np.arange(len(scores)),chosen]
    return np.where(margin>gate,chosen,BASE)


def risk(bad,cap,valid,indices):
    ii=np.arange(len(indices))
    return dict(bad_rate=float(bad[ii,indices].mean()),
                cap_loss=float(cap[ii,indices].mean()),
                failure_rate=float((~valid[ii,indices]).mean()))


def best_fixed(bad,cap,valid):
    return min(range(len(GRID)),key=lambda j:(bad[:,j].mean(),cap[:,j].mean(),
                     (~valid[:,j]).mean(),abs(GRID[j]-1),GRID[j]))


def train():
    OUT.mkdir(parents=True,exist_ok=True)
    source=scan.OUT
    source_manifest=json.loads((source/"manifest.json").read_text(encoding="utf-8"))
    index=pd.read_csv(source/"sample_index.csv")
    index=index[index.cohort.eq("controlled_20260922")].copy()
    rows=pd.concat([pd.read_csv(source/r["path"]) for r in source_manifest["files"]])
    rows=rows[rows.row_id.isin(index.row_id)]
    config=dict(id="S03-J3-02",grid=GRID.tolist(),test_seed=TEST_SEED,test_repeats=50,
        split="3300 development draws: repeat_id % 5 == 0 validation (660), others training (2640)",
        features="28 observed-only: log(n), log1p(min/range), 19 range-normalized quantiles, normalized mean/sd/skew, first two gaps, maximum gap, sum top two gaps",
        targets="For each c, realized bad event (failure or E>=0.5) + .05*min(E,2)/2; failure E is 2; includes fallback to original on chosen solver failure",
        models=dict(ridge="alpha10",tree4="depth4,minleaf40,seed42",
            mlp32_ensemble="StandardScaler; 32x32 ReLU; alpha .01; max500 epochs; internal early-stop15%; seeds42,43,44 averaged"),
        gates=GATES,
        selection="validation bad_rate, then capped loss, then failure, then simpler model and smaller gate",
        refit="Each model at its validation-selected gate refit on all3300 before test; overall primary fixed by validation",
        test="same 33 parameter/n cells, 50 fresh draws per cell, independent seed; no unseen-parameter generalization",
        comparisons="original, training-selected global/n fixed with same fallback; each model, grid oracle",
        source_manifest_sha256=sha(source/"manifest.json"),
        source_index_sha256=sha(source/"sample_index.csv"))
    protocol=OUT/"protocol.json"
    if protocol.exists():
        assert json.loads(protocol.read_text(encoding="utf-8"))==config
    else:write_json(protocol,config)
    if (OUT/"frozen_model.json").exists():
        print("Training already frozen; retained",flush=True);return
    index,d,v,e,ev,ee,bad,cap=matrix(index,rows)
    x=np.array([features(sample(r)) for r in index.to_dict("records")])
    assert x.shape==(3300,28) and np.isfinite(x).all()
    # Audit measurement-unit invariance of the feature vector.
    xx=sample(index.iloc[0].to_dict())
    assert np.allclose(features(xx),features(xx*100),atol=1e-12)
    y=bad.astype(float)+.05*cap/2
    val=index.repeat_id.mod(5).eq(0).to_numpy()
    assert val.sum()==660 and (~val).sum()==2640
    records=[];training_warnings={};selected_gates={}
    for kind in NAMES:
        models,ws=fit_models(kind,x[~val],y[~val])
        training_warnings[kind]=ws
        scores=predict(models,x[val])
        for gate in GATES:
            choice=choose(scores,gate)
            records.append(dict(model=kind,gate=gate,**risk(bad[val],cap[val],ev[val],choice)))
        selected_gates[kind]=min([r for r in records if r["model"]==kind],
                key=lambda r:(r["bad_rate"],r["cap_loss"],r["failure_rate"],r["gate"]))["gate"]
        print("Validation",kind,[r for r in records if r["model"]==kind],flush=True)
    winner=min(records,key=lambda r:(r["bad_rate"],r["cap_loss"],r["failure_rate"],
                                   NAMES.index(r["model"]),r["gate"]))
    baselines=[]
    original=np.full(val.sum(),BASE)
    baselines.append(dict(model="original",gate=0,**risk(bad[val],cap[val],ev[val],original)))
    jf=best_fixed(bad[~val],cap[~val],ev[~val])
    baselines.append(dict(model="train_fixed",gate=0,**risk(bad[val],cap[val],ev[val],np.full(val.sum(),jf))))
    pd.DataFrame(records+baselines).to_csv(OUT/"validation_summary.csv",index=False,encoding="utf-8-sig")
    index["split"]=np.where(val,"validation","training")
    index.to_csv(OUT/"development_index.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(x,columns=[f"x{i:02d}" for i in range(28)]).assign(row_id=index.row_id).to_csv(
        OUT/"development_features.csv",index=False,encoding="utf-8-sig")
    models={}
    for kind in NAMES:
        models[kind],ws=fit_models(kind,x,y)
        training_warnings[kind+"_refit"]=ws
    joblib.dump(models,OUT/"models.joblib")
    fixed=best_fixed(bad,cap,ev)
    by_n={}
    for n in [7,15,30]:
        mask=index.sample_size.eq(n).to_numpy()
        by_n[str(n)]=best_fixed(bad[mask],cap[mask],ev[mask])
    frozen=dict(primary=winner,selected_gates=selected_gates,
                fixed_index=fixed,fixed_c=float(GRID[fixed]),by_n_indices=by_n,
                models_sha256=sha(OUT/"models.joblib"),protocol_sha256=sha(protocol),
                warnings=training_warnings,
                feature_shape=list(x.shape),train=2640,validation=660,refit=3300)
    write_json(OUT/"frozen_model.json",frozen)
    print("FROZEN",json.dumps(frozen,ensure_ascii=False),flush=True)


def test_cell(job):
    cell_id,records,freeze_hash=job
    dest=OUT/"test_cells"/f"cell_{cell_id:02d}.csv.gz"
    if dest.exists():
        prior=pd.read_csv(dest)
        assert len(prior)==len(records)*18 and prior.freeze_hash.eq(freeze_hash).all()
        return cell_id
    rows=[]
    for r in records:
        xx=sample(r)
        for c in GRID:
            out=scan.fit(xx,float(c))
            out.update(row_id=r["row_id"],cell_id=cell_id,freeze_hash=freeze_hash)
            rows.append(out)
    temp=dest.with_name(dest.name+".partial")
    pd.DataFrame(rows).to_csv(temp,index=False,compression="gzip")
    temp.replace(dest)
    return cell_id


def test(workers):
    assert (OUT/"frozen_model.json").exists(),"Freeze training/validation first"
    frozen=json.loads((OUT/"frozen_model.json").read_text(encoding="utf-8"))
    assert sha(OUT/"models.joblib")==frozen["models_sha256"]
    assert sha(OUT/"protocol.json")==frozen["protocol_sha256"]
    freeze_hash=sha(OUT/"frozen_model.json")
    dev=pd.read_csv(OUT/"development_index.csv")
    cells=dev[["beta","eta","gamma","sample_size"]].drop_duplicates().sort_values(["beta","eta","gamma","sample_size"])
    records=[]
    for cell_id,r in enumerate(cells.to_dict("records")):
        for repeat in range(50):
            records.append(dict(**r,cell_id=cell_id,row_id=len(records),
                                repeat_id=repeat,seed_namespace=TEST_SEED,cohort="fresh_test"))
    idx=pd.DataFrame(records)
    idx.to_csv(OUT/"test_index.csv",index=False,encoding="utf-8-sig")
    # Predict from samples before test labels exist. Persist hashes for evaluation.
    x=np.array([features(sample(r)) for r in records])
    models=joblib.load(OUT/"models.joblib")
    predictions=pd.DataFrame({"row_id":idx.row_id})
    for kind in NAMES:
        predictions[kind]=choose(predict(models[kind],x),frozen["selected_gates"][kind])
    predpath=OUT/"test_choices_before_labels.csv"
    if predpath.exists():
        assert predictions.equals(pd.read_csv(predpath))
    else:
        predictions.to_csv(predpath,index=False)
    (OUT/"test_cells").mkdir(exist_ok=True)
    start=time.perf_counter()
    jobs=[(int(k),g.to_dict("records"),freeze_hash) for k,g in idx.groupby("cell_id")]
    with cf.ProcessPoolExecutor(max_workers=workers,initializer=scan.init_worker) as pool:
        futures=[pool.submit(test_cell,job) for job in jobs]
        for count,f in enumerate(cf.as_completed(futures),1):
            cell=f.result()
            progress=dict(completed_cells=count,total=33,last_cell=cell,
                          elapsed_seconds=round(time.perf_counter()-start,1))
            write_json(OUT/"progress.json",progress);print(progress,flush=True)
    files=sorted((OUT/"test_cells").glob("*.csv.gz"))
    assert sum(len(pd.read_csv(p)) for p in files)==29700
    write_json(OUT/"test_manifest.json",dict(status="complete",samples=1650,candidate_fits=29700,
            freeze_hash=freeze_hash,predictions_sha256=sha(predpath),
            files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p)) for p in files]))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["train","test"])
    parser.add_argument("--workers",type=int,default=8)
    args=parser.parse_args()
    if args.phase=="train":train()
    else:test(args.workers)
