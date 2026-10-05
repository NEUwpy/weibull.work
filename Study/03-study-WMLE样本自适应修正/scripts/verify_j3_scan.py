"""Independent row, equation, selection and source-integrity checks."""
from pathlib import Path
import importlib.util
import hashlib
import json
import sys
import numpy as np
import pandas as pd
STUDY=Path(__file__).resolve().parents[1]
ROOT=STUDY.parents[1]
OUT=STUDY/"results/j3_scan_v1"
sys.path.insert(0,str(OUT/"runtime"))
sys.path.insert(1,str(ROOT/"python"))
from studies.common.sample import generate_sample


def main():
    spec=importlib.util.spec_from_file_location("verify_wmle",OUT/"runtime/wmle.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    protocol=json.loads((OUT/"protocol.json").read_text(encoding="utf-8"))
    index=pd.read_csv(OUT/"sample_index.csv").set_index("row_id")
    parts=[]
    for file in manifest["files"]:
        p=OUT/file["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest()==file["sha256"]
        parts.append(pd.read_csv(p))
    d=pd.concat(parts,ignore_index=True)
    assert len(d)==81000
    assert d.groupby("row_id").size().eq(18).all()
    assert not d.duplicated(["row_id","c"]).any()
    assert d.protocol_hash.eq(protocol["protocol_hash"]).all()
    for name,value in protocol["runtime_sha256"].items():
        assert hashlib.sha256((OUT/"runtime"/name).read_bytes()).hexdigest()==value
    assert hashlib.sha256((ROOT/"python/methods/wmle.py").read_bytes()).hexdigest()==protocol["runtime_sha256"]["wmle.py"]
    residual_max=0.;scale_rel_max=0.;valid_count=0
    for row_id,g in d.groupby("row_id"):
        r=index.loc[row_id]
        x=generate_sample(float(r.beta),float(r.eta),float(r.gamma),int(r.sample_size),
                          int(r.repeat_id),seed=int(r.seed_namespace))
        v=g[g.valid]
        for fit in v.itertuples():
            b,e,loc=fit.beta_hat,fit.eta_hat,fit.gamma_hat
            assert 0<b<9.99 and 0<=loc<x.min()
            z=x-loc;logs=np.log(z);weights=np.exp(b*(logs-logs.max()))
            r1=module.get_weight_j2(len(x))/b+logs.mean()-np.sum(weights*logs)/weights.sum()
            r2=np.mean(1/z)*weights.sum()/np.sum(weights/z)-fit.c*module.get_weight_j3(len(x),b)
            residual=r1*r1+r2*r2
            assert residual<=1.001e-8, (row_id,fit.c,residual)
            eta=np.exp(logs.max()+np.log(weights.mean()/module.get_weight_j1(len(x)))/b)
            assert np.isclose(eta,e,rtol=1e-9)
            residual_max=max(residual_max,residual)
            scale_rel_max=max(scale_rel_max,abs(eta/e-1))
            valid_count+=1
    sel=pd.read_csv(OUT/"selected_rows.csv.gz")
    base=sel[sel.policy.eq("original")].set_index("row_id").sort_index()
    oracle=sel[sel.policy.eq("oracle")].set_index("row_id").sort_index()
    assert (oracle.bad<=base.bad).all()
    assert (oracle.loc[base.valid,"E"]<=base.loc[base.valid,"E"]+1e-10).all()
    assert len(sel)==31500 and not sel.duplicated(["row_id","policy"]).any()
    # Oracle row must be a real candidate; no synthetic corrected parameters.
    joined=sel.merge(d,on=["row_id","c"],suffixes=("","_scan"),validate="many_to_one")
    assert np.allclose(joined.beta_hat,joined.beta_hat_scan,equal_nan=True)
    assert np.allclose(joined.eta_hat,joined.eta_hat_scan,equal_nan=True)
    assert np.allclose(joined.gamma_hat,joined.gamma_hat_scan,equal_nan=True)
    result=dict(status="passed",candidate_rows=len(d),valid_candidates=valid_count,
                baseline_refits=4500,policies=7,selected_rows=len(sel),
                max_recomputed_residual=residual_max,max_relative_scale_delta=scale_rel_max,
                production_wmle_unchanged=True,oracle_no_harm=True,
                limits="Finite grid, same simulation domain; no trained NN or unseen-parameter validation.")
    result["scripts"] = [
        dict(path=str(p.relative_to(STUDY)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted((STUDY/"scripts").glob("*j3*.py"))
    ]
    (OUT/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))


if __name__=="__main__":main()
