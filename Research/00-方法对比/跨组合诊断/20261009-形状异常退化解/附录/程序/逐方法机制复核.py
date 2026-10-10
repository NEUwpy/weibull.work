"""Check six method criteria on two abnormal/control pairs, without run().

Outputs stay beside this script. Conditional calculations explain the archived
estimates; they do not replace estimates, convergence states, or frequencies.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUTS = {
    "high": ("W(2,100,500)", 15, 36),
    "high_control": ("W(2,100,500)", 15, 35),
    "low": ("W(5,100,500)", 7, 11),
    "low_control": ("W(5,100,500)", 7, 10),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cov(a, b):
    return float(np.mean((a - a.mean()) * (b - b.mean())))


def shape_profile(x, gamma, j2=1.0):
    """Fixed-location shape score; j2=1 gives ordinary conditional MLE."""
    t = np.log(x - gamma)
    z = t - t.mean()

    def score(beta):
        w = np.exp(beta * (z - z.max()))
        w /= w.sum()
        return j2 / beta - float(w @ z)

    upper = 2.0
    while score(upper) > 0:
        upper *= 2
    beta = brentq(score, 1e-8, upper, xtol=1e-11, rtol=2e-14)
    log_eta = t.mean() + (logsumexp(beta * z) - np.log(len(x))) / beta
    ll = len(x) * (np.log(beta) - t.mean() - logsumexp(beta*z) + np.log(len(x)) - 1)
    w = np.exp(beta * (z - z.max()))
    w /= w.sum()
    grad = len(x) * (beta * float(w @ (1/(x-gamma))) - (beta-1)*np.mean(1/(x-gamma)))
    return dict(beta=float(beta), eta=float(np.exp(log_eta)), ll=float(ll),
                location_score=float(grad), shape_score=float(score(beta)))


def regression(x, gamma, z, method):
    y = np.log(x-gamma)
    c, vy, vz = cov(y, z), cov(y, y), cov(z, z)
    r2 = c*c/(vy*vz)
    beta = vz/c if method == "LSE" else c/vy
    eta = np.exp(y.mean()-z.mean()/beta)
    return dict(beta=float(beta), eta=float(eta), r2=float(r2),
                relative_residual=float(1-r2),
                fisher_ratio=float((len(x)-2)/(len(x)-1)/(1-r2)))


def mdm_profile(x, gamma):
    p = (np.arange(1, len(x)+1)-.3)/(len(x)+.4)
    u = -np.log1p(-p)

    def sigma(beta):
        return float(np.std((x-gamma)*u**(-1/beta), ddof=1))

    fit = minimize_scalar(sigma, bounds=(.1, 15), method="bounded")
    w = u**(-1/fit.x)
    eta_i = (x-gamma)*w
    grad = float(-np.cov(eta_i, w, ddof=1)[0, 1]/fit.fun)
    bound = float(np.std(w, ddof=1))
    assert abs(grad) <= bound+1e-10
    step = min(x[0]*1e-5, (x[0]-gamma)*.25)
    if gamma > step:
        finite_grad = (mdm_sigma(x, gamma+step, u)-mdm_sigma(x, gamma-step, u))/(2*step)
    else:
        finite_grad = (mdm_sigma(x, gamma+step, u)-fit.fun)/step
    return dict(beta=float(fit.x), eta=float(np.mean(eta_i)), sigma=float(fit.fun),
                gradient=grad, gradient_bound=bound, finite_gradient=float(finite_grad))


def mdm_sigma(x, gamma, u):
    return float(minimize_scalar(lambda b: np.std((x-gamma)*u**(-1/b), ddof=1),
                                bounds=(.1, 15), method="bounded").fun)


def wmle_profile(x, gamma, weights):
    n = len(x)
    j1, j2 = weights.get_weight_j1(n), weights.get_weight_j2(n)
    profile = shape_profile(x, gamma, j2)
    beta = profile["beta"]
    t = np.log(x-gamma)
    # Center before powers to avoid overflow; the ratio retains one distance.
    z = t-t.mean()
    log_ratio = t.mean()+logsumexp(beta*z)-logsumexp((beta-1)*z)
    product = float(np.mean(1/(x-gamma))*np.exp(log_ratio))
    j3 = float(weights.get_weight_j3(n, beta))
    return dict(beta=beta, eta=float(profile["eta"]*j1**(-1/beta)),
                t1=profile["shape_score"], t2=float(product-j3),
                inverse_distance_product=product, j1=float(j1), j2=float(j2), j3=j3)


def main():
    provenance = json.loads((ROOT / "跨组合汇总/程序/20261007-新增五组合/13组合取数.json").read_text(encoding="utf-8"))
    sources = {s["combination"]: s for s in provenance["sources"]}
    output = {
        "scope": "two archived illustrative pairs; no formal re-estimation or frequency change",
        "control_selection": "same combination and n; nearest group id with all three relevant methods finite, converged and within (beta/3, 3*beta); lower id breaks ties",
        "samples": {},
    }
    hashes = {}
    for label, (combination, n, group) in INPUTS.items():
        program = Path(sources[combination]["program"])
        path = program / "中间数据/matrix.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        hashes[str(path)] = digest(path)
        snapshot = program / "依赖快照/python"
        sys.path.insert(0, str(snapshot))
        lse = load_module(snapshot / "methods/lse.py", "criterion_lse_"+label)
        wmle = load_module(snapshot / "methods/wmle.py", "criterion_wmle_"+label)
        for filename in ("methods/lse.py", "methods/lre.py", "methods/mdm.py", "methods/mle.py", "methods/wmle.py", "methods/mmle.py", "methods/j3_weights.tsv"):
            dep = snapshot / filename
            hashes[str(dep)] = digest(dep)
            assert hashes[str(dep)] == data["config"]["dependency_hashes"][filename]
        x = np.sort(np.asarray(next(s["values"] for s in data["samples"] if (s["n"], s["id"]) == (n, group)), float))
        truth = data["config"]["truth"]
        rows = {r["method_id"].upper(): r for r in data["results"]
                if (r["n"], r["id"]) == (n, group) and (r["method_id"] != "mdm" or r["delta"] == .2)}
        record = dict(combination=combination, n=n, group=group, truth=truth,
                      values=x.tolist(), sample_min=float(x[0]), methods={})
        record["archived_all_six"] = {
            m: {k: r[k] for k in ("beta_hat", "eta_hat", "gamma_hat", "converged", "status")}
            for m, r in rows.items()
        }
        relevant = ("LSE", "LRE", "MLE") if label.startswith("high") else ("MDM", "WMLE", "MMLE")
        if label.endswith("control"):
            reference_id = INPUTS[label.removesuffix("_control")][2]
            candidates = []
            for sample in data["samples"]:
                if sample["n"] != n:
                    continue
                candidates_rows = [r for r in data["results"]
                                   if (r["n"], r["id"]) == (n, sample["id"])
                                   and r["method_id"].upper() in relevant
                                   and (r["method_id"] != "mdm" or r["delta"] == .2)]
                if len(candidates_rows) == 3 and all(
                    r["converged"] and r["beta_hat"] is not None
                    and truth[0]/3 < r["beta_hat"] < 3*truth[0] for r in candidates_rows
                ):
                    candidates.append(sample["id"])
            assert group == min(candidates, key=lambda i: (abs(i-reference_id), i))
        else:
            assert all(rows[m]["beta_hat"] >= 3*truth[0] if label=="high"
                       else rows[m]["beta_hat"] <= truth[0]/3 for m in relevant)
        if label.startswith("high"):
            rank = np.arange(1, n+1)
            p = (rank-3/8)/(n+1/4) if n <= 10 else (rank-.5)/n
            for method, z in (("LSE", lse.log_weibull_order_stat_means(n)),
                              ("LRE", np.log(-np.log1p(-p)))):
                row = rows[method]
                selected = regression(x, row["gamma_hat"], z, method)
                at_truth = regression(x, truth[2], z, method)
                at_zero = regression(x, 0.0, z, method)
                assert abs(selected["beta"]-row["beta_hat"]) < 1e-7
                assert abs(selected["eta"]-row["eta_hat"]) < 1e-7
                assert selected["r2"] > at_truth["r2"]
                record["methods"][method] = dict(archived=row, at_true_location=at_truth,
                                                 at_selected_location=selected, at_zero_location=at_zero,
                                                 zero_minus_true_r2=at_zero["r2"]-at_truth["r2"],
                                                 version="White" if method=="LSE" else "Park Proposed+Plot")
            row = rows["MLE"]
            selected = shape_profile(x, row["gamma_hat"])
            at_truth = shape_profile(x, truth[2])
            at_zero = shape_profile(x, 0.0)
            assert abs(selected["beta"]-row["beta_hat"]) < 1e-3
            assert abs(selected["eta"]-row["eta_hat"]) < 1e-3
            assert selected["ll"] > at_truth["ll"]
            if label == "high":
                assert selected["location_score"] < 0
            record["methods"]["MLE"] = dict(archived=row, at_true_location=at_truth, at_selected_location=selected,
                                             at_zero_location=at_zero, zero_minus_true_ll=at_zero["ll"]-at_truth["ll"])
        else:
            row = rows["MDM"]
            selected = mdm_profile(x, row["gamma_hat"])
            at_truth = mdm_profile(x, truth[2])
            assert abs(selected["gradient"]-.2) < 1e-5
            assert abs(selected["finite_gradient"]-.2) < 1e-5
            assert at_truth["gradient"] < .2 and row["gamma_hat"] > truth[2]
            record["methods"]["MDM"] = dict(archived=row, delta=.2, at_true_location=at_truth, at_selected_location=selected)
            row = rows["WMLE"]
            selected = wmle_profile(x, row["gamma_hat"], wmle)
            at_truth = wmle_profile(x, truth[2], wmle)
            assert abs(selected["t2"]) < 1e-7 and abs(selected["beta"]-row["beta_hat"]) < 1e-6
            assert at_truth["t2"] < 0 and row["gamma_hat"] > truth[2]
            record["methods"]["WMLE"] = dict(archived=row, at_true_location=at_truth, at_selected_location=selected)
            row = rows["MMLE"]
            selected = shape_profile(x[1:], x[0])
            at_truth = shape_profile(x[1:], truth[2])
            assert row["gamma_hat"] == x[0]
            assert abs(selected["beta"]-row["beta_hat"]) < 1e-6
            assert abs(selected["eta"]-row["eta_hat"]) < 1e-6
            record["methods"]["MMLE"] = dict(archived=row, minimum_gap=float(x[0]-truth[2]),
                                               at_true_location_same_retained_sample=at_truth, at_selected_location=selected)
        output["samples"][label] = record
    output["source_sha256"] = hashes
    output["sources_unchanged"] = all(digest(Path(p)) == h for p, h in hashes.items())
    assert output["sources_unchanged"]
    (HERE / "逐方法机制复核.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for label, record in output["samples"].items():
        print(record["combination"], record["n"], record["group"])
        for method, diagnostic in record["methods"].items():
            print(method, {k: v for k, v in diagnostic.items() if k != "archived"})
    print("PASS: six criteria; source hashes unchanged")


if __name__ == "__main__":
    main()
