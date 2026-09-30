import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

ROOT = Path(r"D:\weibull")
sys.path.insert(0, str(ROOT / "python"))
from methods.lse import log_weibull_order_stat_means


def global_refine(func, lower, upper, points=3001):
    grid = np.linspace(lower, upper, points)
    vals = np.array([func(float(g)) for g in grid])
    idx = int(np.nanargmax(vals))
    lo = grid[max(idx - 1, 0)]
    hi = grid[min(idx + 1, points - 1)]
    if hi > lo:
        res = minimize_scalar(lambda g: -func(g), bounds=(lo, hi), method="bounded")
        if res.success and -res.fun >= vals[idx]:
            return float(res.x), float(-res.fun)
    return float(grid[idx]), float(vals[idx])


payload = json.loads((ROOT / "tmp/w3-cases-20260907/payload.json").read_text(encoding="utf-8"))
for case in payload["cases"]:
    print("\n", case["label"])
    for n in (7, 15):
        rows = case["results"][str(n)]["0.10"]
        ls_zero = [r["sample_id"] for r in rows if r["LS"]["location_hat"] == 0]
        lre_zero = [r["sample_id"] for r in rows if r["LRE"]["location_hat"] == 0]
        print(n, "LS", len(ls_zero), "LRE", len(lre_zero), "overlap", len(set(ls_zero)&set(lre_zero)))

case = next(c for c in payload["cases"] if c["label"] == "W(3,1000,500)")
for sid in (2, 12, 13):
    t = np.asarray(case["samples"]["7"][sid - 1], dtype=float)
    n = len(t)
    p = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    y_lre = np.log(-np.log(1 - p))
    X = log_weibull_order_stat_means(n)
    xbar = X.mean()
    sxx = np.sum((X-xbar)**2)

    def lre_obj(g):
        if g >= t[0]: return -np.inf
        x = np.log(t-g)
        return float(np.corrcoef(x, y_lre)[0,1]**2)

    def ls_obj(g):
        if g >= t[0]: return -np.inf
        yy=np.log(t-g); ybar=yy.mean()
        slope=np.sum((X-xbar)*(yy-ybar))/sxx
        if slope <= 0: return -np.inf
        resid=yy-(ybar-slope*xbar+slope*X)
        sy2=np.sum((yy-ybar)**2)/(n-1)
        sr2=np.sum(resid**2)/(n-2)
        return float(sy2/sr2) if sr2>0 else np.inf

    print("\nSAMPLE", sid, "min", t[0], "gap12", t[1]-t[0])
    for name, fun in (("LRE",lre_obj),("LS",ls_obj)):
        h=0.01
        right_deriv=(fun(h)-fun(0))/h
        gneg,vneg=global_refine(fun,-5000,0)
        print(name, "obj0",fun(0),"right_deriv",right_deriv,"best[-5000,0]",gneg,vneg,"obj+100",fun(100))
