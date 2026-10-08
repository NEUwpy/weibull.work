import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.special import gamma as gamma_fn

ROOT = Path(r"D:\weibull")
sys.path.insert(0, str(ROOT / "python"))

from methods.mdm import MDM


def cdf_r2(sample, shape, scale, location, p):
    x = np.log(sample - location)
    y = np.log(-np.log(1 - p))
    yhat = shape * x - shape * np.log(scale)
    return 1.0 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2)


payload = json.loads((ROOT / "tmp/w3-cases-20260907/payload.json").read_text(encoding="utf-8"))
case = next(c for c in payload["cases"] if c["label"] == "W(3,1000,500)")
n = 7
p = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
z = -np.log(1 - p)
true_q = 500 + 1000 * z ** (1 / 3)

print("bernard_p", p.tolist())
print("true_quantiles", true_q.tolist())
print("true_mean", 500 + 1000 * gamma_fn(1 + 1 / 3))

for sample_id in (12, 13):
    sample = np.asarray(case["samples"]["7"][sample_id - 1], dtype=float)
    result = case["results"]["7"]["0.10"][sample_id - 1]["MDM"]
    shape = result["shape_hat"]
    scale = result["scale_hat"]
    loc = result["location_hat"]
    fitted_q = loc + scale * z ** (1 / shape)
    eta_hat_i = (sample - loc) / z ** (1 / shape)
    eta_true_i = (sample - 500) / z ** (1 / 3)
    algo = MDM(sample.tolist())
    raw = algo.run(trace=True, offset=0.10, gamma_steps=240)
    trace = algo.trace_data
    ll_true = np.sum(
        np.log(3 / 1000)
        + 2 * np.log((sample - 500) / 1000)
        - ((sample - 500) / 1000) ** 3
    )
    ll_fit = np.sum(
        np.log(shape / scale)
        + (shape - 1) * np.log((sample - loc) / scale)
        - ((sample - loc) / scale) ** shape
    )
    print(f"\nSAMPLE {sample_id}")
    print("sample", sample.tolist())
    print("summary", dict(mean=sample.mean(), sd=sample.std(ddof=1), min=sample.min(), max=sample.max(), span=np.ptp(sample)))
    print("true_q_residual", (sample - true_q).tolist())
    print("fit_q", fitted_q.tolist())
    print("fit_q_residual", (sample - fitted_q).tolist())
    print("estimate", dict(shape=shape, scale=scale, location=loc, r2=result["r_squared"]))
    print("objective", dict(eta_hat_mean=eta_hat_i.mean(), eta_hat_sd=eta_hat_i.std(ddof=1), eta_true_mean=eta_true_i.mean(), eta_true_sd=eta_true_i.std(ddof=1)))
    print("r2_true", cdf_r2(sample, 3, 1000, 500, p))
    print("gradient", dict(g0=trace["probe_gradient_at_zero"], root=loc, target=trace["target_offset"], strategy=trace["solution_strategy"], iterations=trace["root_solver_iterations"]))
    print("loglik", dict(true=ll_true, fitted=ll_fit, diff=ll_fit-ll_true))
    print("delta_sensitivity")
    for delta in ("0.10", "0.15", "0.20"):
        r = case["results"]["7"][delta][sample_id - 1]["MDM"]
        print(delta, r["shape_hat"], r["scale_hat"], r["location_hat"], r["r_squared"])

rows = [r["MDM"] for r in case["results"]["7"]["0.10"]]
arr = np.array([[r["shape_hat"], r["scale_hat"], r["location_hat"]] for r in rows], dtype=float)
print("\nALL50 summary")
for j, name in enumerate(("shape", "scale", "location")):
    print(name, dict(min=float(arr[:,j].min()), q1=float(np.quantile(arr[:,j],.25)), median=float(np.median(arr[:,j])), q3=float(np.quantile(arr[:,j],.75)), max=float(arr[:,j].max())))
print("correlation")
print(np.corrcoef(arr.T))
for sid in (12,13):
    vals=arr[sid-1]
    print("percentile", sid, {name: float(np.mean(arr[:,j] <= vals[j])) for j,name in enumerate(("shape","scale","location"))})
