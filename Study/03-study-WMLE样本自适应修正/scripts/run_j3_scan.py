"""Isolated, resumable J3 multiplier experiment using frozen production solver."""
from pathlib import Path
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
import argparse

for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ[name] = "1"
import numpy as np
import pandas as pd

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
OUT = STUDY / "results/j3_scan_v1"
sys.path.insert(0, str(ROOT / "python"))
from studies.common.sample import generate_sample

GRID = [.70, .80, .85, .90, .92, .94, .96, .98, 1., 1.02, 1.04, 1.06, 1.08, 1.10, 1.15, 1.20, 1.30, 1.50]
MODEL = None
MULTIPLIER = 1.


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def init_worker():
    global MODEL
    sys.path.insert(0, str(OUT / "runtime"))
    spec = importlib.util.spec_from_file_location("study03_isolated_wmle", OUT / "runtime/wmle.py")
    MODEL = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MODEL)
    original = MODEL.get_weight_j3
    MODEL.get_weight_j3 = lambda n, b: original(n, b) * MULTIPLIER


def fit(x, c):
    global MULTIPLIER
    MULTIPLIER = c
    model = MODEL.WMLE(x)
    start = time.perf_counter()
    values = model.run()
    info = model.last_solution_info
    valid = info["status"] == "ok" and np.isfinite(values[:3]).all()
    row = dict(c=c, valid=bool(valid), status=info["status"],
               objective=info.get("objective"), selected_start=info.get("selected_start"),
               runtime_seconds=time.perf_counter()-start)
    row.update({k:float(v) if valid else np.nan for k,v in
                zip(["beta_hat","eta_hat","gamma_hat"],values[:3])})
    return row


def baseline_check(result, r):
    assert result["valid"] == bool(r["valid"]), (r["row_id"], result, "valid mismatch")
    if r["valid"]:
        assert np.allclose([result[k] for k in ["beta_hat","eta_hat","gamma_hat"]],
                           [r[k] for k in ["beta_hat","eta_hat","gamma_hat"]],
                           rtol=1e-9, atol=1e-6), (r["row_id"], "estimate mismatch")


def scan_cell(job):
    cell_id, records, protocol_hash = job
    dest = OUT / "cells" / f"cell_{cell_id:02d}.csv.gz"
    if dest.exists():
        prior = pd.read_csv(dest)
        assert len(prior) == len(records)*len(GRID)
        assert prior.protocol_hash.eq(protocol_hash).all()
        return cell_id, len(prior), "retained"
    rows = []
    for r in records:
        x = generate_sample(float(r["beta"]),float(r["eta"]),float(r["gamma"]),
                            int(r["sample_size"]),int(r["repeat_id"]),seed=int(r["seed_namespace"]))
        assert np.isclose(x.min(),r["sample_min"],rtol=0,atol=1e-7)
        for c in [1.] + [c for c in GRID if c != 1.]:
            result = fit(x,c)
            if c == 1.:
                baseline_check(result,r)
            result.update(row_id=r["row_id"],cell_id=cell_id,protocol_hash=protocol_hash)
            rows.append(result)
    frame = pd.DataFrame(rows)
    temp = dest.with_name(dest.name+".partial")
    frame.to_csv(temp,index=False,compression="gzip")
    temp.replace(dest)
    return cell_id,len(frame),"completed"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--smoke",action="store_true")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"cells").mkdir(exist_ok=True)
    (OUT/"runtime").mkdir(exist_ok=True)
    source=STUDY/"results/analysis_v1/all_case_rows.csv"
    runtime = [("python/methods/wmle.py","wmle.py"),("python/methods/j3_weights.tsv","j3_weights.tsv"),
               ("python/base.py","base.py"),("python/studies/common/sample.py","sample.py")]
    for src,name in runtime:
        dst=OUT/"runtime"/name
        if dst.exists():
            assert sha(dst)==sha(ROOT/src), "Runtime changed; use new protocol"
        else:
            shutil.copy2(ROOT/src,dst)
    protocol=dict(id="S03-J3-01", version=1, grid=GRID,
                  intervention="J3_star(n,beta)=c*J3(n,beta); c fixed during each fit",
                  source=str(source.relative_to(STUDY)),source_sha256=sha(source),
                  runtime_sha256={name:sha(OUT/"runtime"/name) for _,name in runtime},
                  baseline="c=1 refit every sample and check existing estimates/status",
                  primary="failure_or_E_ge_0.5; failure counted in denominator",
                  E="max(abs((bhat-b)/b),abs((ehat-e)/e),abs((ghat-g)/e))",
                  fixed_selection="minimum bad-event rate, then mean capped E (cap 2, failure 2), then failure rate, then closest c to 1",
                  oracle_selection="valid minimum E; ties prefer closest c to 1; all-failed fallback c=1",
                  cohorts="historical_complete (1200) and controlled_20260922 (3300) analyzed separately",
                  selection_scope="descriptive same-data best fixed and known-truth per-sample oracle; not deployed NN",
                  crossfit="five repeat_id modulo 5 folds within each cohort/cell for supplemental fixed and n-fixed selection",
                  frozen_before_scan=True)
    fingerprint=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    protocol["protocol_hash"]=fingerprint
    p=OUT/"protocol.json"
    if p.exists():
        assert json.loads(p.read_text(encoding="utf-8"))==protocol
    else:
        p.write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding="utf-8")
    data=pd.read_csv(source)
    data["row_id"]=np.arange(len(data))
    keys=["cohort","beta","eta","gamma","sample_size"]
    data["cell_id"]=data.groupby(keys,sort=True).ngroup()
    data.to_csv(OUT/"sample_index.csv",index=False,encoding="utf-8-sig")
    if args.smoke:
        init_worker()
        subset=data.groupby("cell_id").head(1)
        subset=pd.concat([subset,data[~data.valid].head(5),
                          data[data.cohort.eq("historical_complete") & data.beta.eq(2) &
                               data.eta.eq(1000) & data.gamma.eq(500) & data.sample_size.eq(7) &
                               data.repeat_id.eq(46)]]).drop_duplicates("row_id")
        checks=[]
        for r in subset.to_dict("records"):
            x=generate_sample(float(r["beta"]),float(r["eta"]),float(r["gamma"]),int(r["sample_size"]),int(r["repeat_id"]),seed=int(r["seed_namespace"]))
            result=fit(x,1.)
            baseline_check(result,r)
            checks.append(dict(row_id=r["row_id"],status=result["status"],passed=True))
        (OUT/"smoke.json").write_text(json.dumps(dict(status="passed",checks=checks),indent=2),encoding="utf-8")
        print("Smoke passed",len(checks),flush=True)
        return
    assert (OUT/"smoke.json").exists(),"Run --smoke first"
    jobs=[(int(k),g.to_dict("records"),fingerprint) for k,g in data.groupby("cell_id")]
    start=time.perf_counter()
    with cf.ProcessPoolExecutor(max_workers=args.workers,initializer=init_worker) as pool:
        futures=[pool.submit(scan_cell,job) for job in jobs]
        for completed,future in enumerate(cf.as_completed(futures),1):
            result=future.result()
            progress=dict(completed_cells=completed,total_cells=len(jobs),last_cell=result[0],
                          elapsed_seconds=round(time.perf_counter()-start,1))
            (OUT/"progress.json").write_text(json.dumps(progress),encoding="utf-8")
            print(progress,flush=True)
    parts=sorted((OUT/"cells").glob("*.csv.gz"))
    total=sum(len(pd.read_csv(p)) for p in parts)
    assert total==len(data)*len(GRID)
    manifest=dict(status="complete",samples=len(data),cells=len(parts),candidate_fits=total,
                  workers=args.workers,elapsed_seconds=time.perf_counter()-start,protocol_hash=fingerprint,
                  files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p)) for p in parts])
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("COMPLETE",total,flush=True)


if __name__=="__main__":
    main()
