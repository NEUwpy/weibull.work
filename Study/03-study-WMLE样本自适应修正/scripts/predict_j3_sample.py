"""Executable inference with observed samples only; no true parameters."""
import argparse
import json
import joblib
import numpy as np
import run_j3_learning as exp


def predict_sample(values):
    x=np.sort(np.asarray(values,dtype=float))
    if len(x)<3 or not np.isfinite(x).all() or np.any(x<=0) or np.ptp(x)<=0:
        raise ValueError("Need at least three positive finite values with nonzero range.")
    frozen=json.loads((exp.OUT/"frozen_model.json").read_text(encoding="utf-8"))
    assert exp.sha(exp.OUT/"models.joblib")==frozen["models_sha256"]
    kind=frozen["primary"]["model"]
    models=joblib.load(exp.OUT/"models.joblib")[kind]
    scores=exp.predict(models,exp.features(x)[None,:])
    j=int(exp.choose(scores,frozen["selected_gates"][kind])[0])
    exp.scan.init_worker()
    result=exp.scan.fit(x,float(exp.GRID[j]))
    fallback=False
    if not result["valid"] and j!=exp.BASE:
        result=exp.scan.fit(x,1.)
        fallback=True
    return dict(model=kind,requested_c=float(exp.GRID[j]),fallback=fallback,
                support="pilot evaluated at n=7/15/30, finite parameter grid",**result)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("values",nargs="+",type=float)
    args=parser.parse_args()
    print(json.dumps(predict_sample(args.values),ensure_ascii=False))
