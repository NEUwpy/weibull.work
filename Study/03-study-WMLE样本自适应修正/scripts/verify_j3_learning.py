"""Independent fresh-test integrity, observed-only inference and equation checks."""
import importlib.util
import importlib.metadata
import json
import hashlib
import numpy as np
import pandas as pd
import joblib
import run_j3_learning as exp
from predict_j3_sample import predict_sample

OUT=exp.OUT


def main():
    frozen=json.loads((OUT/"frozen_model.json").read_text(encoding="utf-8"))
    manifest=json.loads((OUT/"test_manifest.json").read_text(encoding="utf-8"))
    assert manifest["freeze_hash"]==exp.sha(OUT/"frozen_model.json")
    assert frozen["models_sha256"]==exp.sha(OUT/"models.joblib")
    assert frozen["protocol_sha256"]==exp.sha(OUT/"protocol.json")
    assert exp.sha(exp.ROOT/"python/methods/wmle.py")==exp.sha(exp.scan.OUT/"runtime/wmle.py")
    assert manifest["predictions_sha256"]==exp.sha(OUT/"test_choices_before_labels.csv")
    dev=pd.read_csv(OUT/"development_index.csv")
    idx=pd.read_csv(OUT/"test_index.csv").sort_values("row_id")
    assert len(dev)==3300 and len(idx)==1650
    assert set(dev.seed_namespace).isdisjoint(set(idx.seed_namespace))
    hashes=set()
    for r in dev.to_dict("records"):
        hashes.add(hashlib.sha256(exp.sample(r).tobytes()).hexdigest())
    samples=[];test_hashes=set();long=[]
    for r in idx.to_dict("records"):
        x=exp.sample(r)
        h=hashlib.sha256(x.tobytes()).hexdigest()
        assert h not in hashes and h not in test_hashes
        samples.append(x);test_hashes.add(h)
        for i,value in enumerate(x,1):
            long.append(dict(row_id=r["row_id"],observation_index=i,value=value))
    pd.DataFrame(long).to_csv(OUT/"test_samples_long.csv",index=False,encoding="utf-8-sig")
    features=np.array([exp.features(x) for x in samples])
    models=joblib.load(OUT/"models.joblib")
    saved=pd.read_csv(OUT/"test_choices_before_labels.csv")
    for kind in exp.NAMES:
        actual=exp.choose(exp.predict(models[kind],features),frozen["selected_gates"][kind])
        assert np.array_equal(actual,saved[kind].to_numpy())
    rows=[]
    for file in manifest["files"]:
        p=OUT/file["path"]
        assert exp.sha(p)==file["sha256"]
        rows.append(pd.read_csv(p))
    raw=pd.concat(rows,ignore_index=True)
    assert len(raw)==29700 and not raw.duplicated(["row_id","c"]).any()
    assert raw.groupby("row_id").size().eq(18).all()
    spec=importlib.util.spec_from_file_location("verify_weights",exp.scan.OUT/"runtime/wmle.py")
    wmle=importlib.util.module_from_spec(spec);spec.loader.exec_module(wmle)
    max_residual=0
    for r in raw[raw.valid].itertuples():
        x=samples[r.row_id];z=x-r.gamma_hat;b=r.beta_hat;log=np.log(z)
        w=np.exp(b*(log-log.max()))
        a=wmle.get_weight_j2(len(x))/b+log.mean()-sum(w*log)/sum(w)
        bres=np.mean(1/z)*sum(w)/sum(w/z)-r.c*wmle.get_weight_j3(len(x),b)
        resid=a*a+bres*bres
        assert resid<1.001e-8
        max_residual=max(max_residual,resid)
        scale=np.exp(log.max()+np.log(w.mean()/wmle.get_weight_j1(len(x)))/b)
        assert np.isclose(scale,r.eta_hat,rtol=1e-9)
    selected=pd.read_csv(OUT/"test_selected_rows.csv.gz")
    primary=selected[selected.policy.eq(frozen["primary"]["model"])].set_index("row_id")
    # Include fallback and direct cases across n; actually solve inference without truth.
    audit_ids=set(idx.groupby("sample_size").head(2).row_id)
    audit_ids.update(primary[primary.fallback].head(3).index)
    audit_ids.update(primary[~primary.fallback].tail(3).index)
    for row_id in sorted(audit_ids):
        result=predict_sample(samples[row_id])
        stored=primary.loc[row_id]
        assert result["requested_c"]==stored.requested_c
        assert result["fallback"]==stored.fallback and result["valid"]==stored.valid
        if result["valid"]:
            assert np.allclose([result[k] for k in ["beta_hat","eta_hat","gamma_hat"]],
                               stored[["beta_hat","eta_hat","gamma_hat"]].to_numpy(float),rtol=1e-8,atol=1e-6)
    # Separate requested solver output from fallback outcome in the selected table.
    merged=selected.merge(raw[["row_id","c","valid","beta_hat","eta_hat","gamma_hat"]],
                          on=["row_id","c"],suffixes=("","_raw"),validate="many_to_one")
    assert merged.valid.eq(merged.valid_raw).all()
    assert np.allclose(merged.beta_hat,merged.beta_hat_raw,equal_nan=True)
    assert not selected.duplicated(["row_id","policy"]).any()
    result=dict(status="passed",dev_samples=len(dev),test_samples=len(idx),
                candidate_rows=len(raw),valid_candidates=int(raw.valid.sum()),
                sample_hash_overlap=0,observed_only_predictions_reproduced=4950,
                online_inference_cases=len(audit_ids),maximum_equation_residual=max_residual,
                models_frozen_hash_verified=True,
                packages={k:(np.__version__ if k=="numpy" else importlib.metadata.version(k)) for k in ["numpy","scipy","pandas","scikit-learn","joblib"]},
                scripts=[dict(path=str(p.relative_to(exp.STUDY)),sha256=exp.sha(p)) for p in
                         [exp.STUDY/"scripts"/n for n in ["run_j3_learning.py","analyze_j3_learning.py","predict_j3_sample.py","verify_j3_learning.py"]]],
                limitation="Independent seed at seen parameter grid; exploratory pilot; no training-seed uncertainty interval.")
    exp.write_json(OUT/"verification.json",result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
