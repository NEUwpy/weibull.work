"""Locate shape anomalies using conditional restoration of archived results.

Read all six-method R00 records. Hold each sample and method construction fixed,
restore the conditional shape at its archived location, then fix location at
the generating truth. This is retrospective diagnosis, not a usable estimator.
No run(), resampling, source overwrite, failure reclassification or new bounds.
"""
from collections import Counter
from pathlib import Path
import csv
import importlib.util
import json
import math
import sys

import numpy as np
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
METHODS = ["MDM δ=0.20", "LSE", "LRE", "MLE", "WMLE", "MMLE"]
spec = importlib.util.spec_from_file_location("criterion_check", HERE/"逐方法机制复核.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def flag(value, truth):
    return value >= 3*truth or value <= truth/3


def finite(row):
    return row["converged"] and all(isinstance(row[k], (float, int)) and math.isfinite(row[k])
                                    for k in ("beta_hat", "eta_hat", "gamma_hat"))


def raw_scores(x, beta, eta, location, wmle=None):
    t = np.log(x-location)
    z = t-t.mean()
    w = np.exp(beta*(z-z.max()))
    w /= w.sum()
    if wmle:
        t1 = wmle.get_weight_j2(len(x))/beta-float(w@z)
        ratio = np.exp(t.mean()+logsumexp(beta*z)-logsumexp((beta-1)*z))
        t2 = float(np.mean(1/(x-location))*ratio-wmle.get_weight_j3(len(x), beta))
        return t1, t2
    ll = len(x)*np.log(beta)+(beta-1)*np.sum(t)-len(x)*beta*np.log(eta)
    ll -= np.sum(np.exp(np.clip(beta*(t-np.log(eta)), -745, 700)))
    return float(1/beta-w@z), float(ll)


def main():
    catalog = ROOT/"跨组合汇总/程序/20261007-新增五组合/13组合取数.json"
    sources = json.loads(catalog.read_text(encoding="utf-8"))["sources"]
    hashes = {str(catalog): helper.digest(catalog), str(Path(__file__)): helper.digest(Path(__file__)),
              str(HERE/"逐方法机制复核.py"): helper.digest(HERE/"逐方法机制复核.py")}
    records, failures = [], []
    for i, source in enumerate(sources):
        program = Path(source["program"])
        base = program if program.name == "程序" else program.parent
        path = base/"中间数据/matrix.json" if program.name == "程序" else base/"完整矩阵/数据/matrix.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        hashes[str(path)] = helper.digest(path)
        snapshot = base/"依赖快照/python"
        sys.path.insert(0, str(snapshot))
        lse = helper.load_module(snapshot/"methods/lse.py", "flow_lse_"+str(i))
        wmle = helper.load_module(snapshot/"methods/wmle.py", "flow_wmle_"+str(i))
        for f in ("methods/lse.py", "methods/lre.py", "methods/mdm.py", "methods/mle.py", "methods/wmle.py", "methods/mmle.py", "methods/j3_weights.tsv"):
            dep = snapshot/f
            hashes[str(dep)] = helper.digest(dep)
            assert hashes[str(dep)] == data["config"]["dependency_hashes"][f]
        b0, e0, g0 = map(float, data["config"]["truth"])
        samples = {(s["n"], s["id"]): np.sort(np.asarray(s["values"], float)) for s in data["samples"]}
        truth_cache, references = {}, {}
        version = "Bernard" if source["protocol"] == "historical-eight" else "Park Proposed+Plot"
        for row in data["results"]:
            method = "MDM δ=0.20" if row["method_id"] == "mdm" else row["method_id"].upper()
            if method not in METHODS or (row["method_id"] == "mdm" and row["delta"] != .2):
                continue
            rec = dict(combination=source["combination"], n=row["n"], group=row["id"], method=method,
                       version=version if method=="LRE" else "", beta_true=b0, eta_true=e0, gamma_true=g0)
            if not finite(row):
                failures.append(dict(rec, status=row.get("status", "")))
                continue
            x = samples[(row["n"], row["id"])]
            g = float(row["gamma_hat"])
            at_endpoint = bool(method != "MMLE" and g >= x[0])
            # No exact positive support for MDM at the represented endpoint.
            # Its limiting conditional calculation is kept explicitly separate.
            diagnostic_g = float(np.nextafter(x[0], 0.0)) if at_endpoint else g
            key = (row["n"], row["id"], method)

            def conditional(location):
                if method.startswith("MDM"):
                    return helper.mdm_profile(x, location)
                if method in ("LSE", "LRE"):
                    refkey = (len(x), method)
                    if refkey not in references:
                        if method=="LSE":
                            references[refkey] = lse.log_weibull_order_stat_means(len(x))
                        else:
                            ranks = np.arange(1, len(x)+1)
                            p = (ranks-.3)/(len(x)+.4) if version=="Bernard" else ((ranks-3/8)/(len(x)+1/4) if len(x)<=10 else (ranks-.5)/len(x))
                            references[refkey] = np.log(-np.log1p(-p))
                    return helper.regression(x, location, references[refkey], method)
                if method=="WMLE":
                    return helper.wmle_profile(x, location, wmle)
                return helper.shape_profile(x[1:] if method=="MMLE" else x, location)

            selected = conditional(diagnostic_g)
            truth = truth_cache.setdefault(key, conditional(g0))
            original_flag = flag(row["beta_hat"], b0)
            selected_flag, truth_flag = flag(selected["beta"], b0), flag(truth["beta"], b0)
            rec.update(beta_hat=row["beta_hat"], eta_hat=row["eta_hat"], gamma_hat=g,
                       abnormal=original_flag, direction="over" if row["beta_hat"]>=3*b0 else ("under" if row["beta_hat"]<=b0/3 else "none"),
                       beta_conditional_original_location=selected["beta"], beta_fixed_true_location=truth["beta"],
                       fixed_true_abnormal=truth_flag, conditional_original_abnormal=selected_flag,
                       fixed_true_direction="over" if truth["beta"]>=3*b0 else ("under" if truth["beta"]<=b0/3 else "none"),
                       removed_by_location_fix=original_flag and not truth_flag,
                       removed_by_conditional_restore=original_flag and not selected_flag and not at_endpoint,
                       conditional_beta_log_error=float(abs(np.log(selected["beta"]/row["beta_hat"]))),
                       eta_conditional_original_location=selected["eta"],
                       conditional_eta_log_error=float(abs(np.log(selected["eta"]/row["eta_hat"]))),
                       endpoint_limit_used=at_endpoint, sample_min=float(x[0]),
                       min_gap_over_eta=float((x[0]-g0)/e0), location_error_over_eta=(g-g0)/e0,
                       raw_cv=float(x.std()/x.mean()),
                       true_shifted_cv=float(x.std()/(x.mean()-g0)))
            if method in ("LSE", "LRE"):
                rec.update(criterion_selected=selected["r2"], criterion_fixed_true=truth["r2"],
                           selected_minus_true=selected["r2"]-truth["r2"])
            elif method=="MLE":
                score, raw_ll = raw_scores(x, row["beta_hat"], row["eta_hat"], g)
                rec.update(shape_score_original=score, criterion_original=raw_ll,
                           criterion_selected=selected["ll"], criterion_fixed_true=truth["ll"],
                           conditional_ll_gain=selected["ll"]-raw_ll,
                           selected_minus_true=selected["ll"]-truth["ll"])
            elif method=="WMLE":
                t1, t2 = raw_scores(x, row["beta_hat"], row["eta_hat"], g, wmle)
                rec.update(t1_original=t1, t2_original=t2, equation_residual=t1*t1+t2*t2,
                           t2_fixed_true=truth["t2"], t2_conditional_original=selected["t2"], j2=truth["j2"])
            elif method.startswith("MDM"):
                near_edge = x[0]-g <= 64*np.finfo(float).eps*max(x[0],1.)
                old = row.get("original_record", {})
                info = old.get("extra", {}).get("solution_info", {})
                solver = old.get("root_solver", info.get("root_solver", ""))
                rec.update(gradient_original=selected["gradient"], finite_gradient_original=None if near_edge else selected["finite_gradient"],
                           gradient_fixed_true=truth["gradient"], gradient_bound_fixed_true=truth["gradient_bound"],
                           delta=.2, near_endpoint_gradient_unresolved=bool(near_edge), archived_root_solver=solver)
            elif method=="MMLE":
                assert g==x[0]
                full = helper.shape_profile(x, g0)
                rec.update(beta_full_sample_fixed_true=full["beta"],
                           full_sample_fixed_true_abnormal=flag(full["beta"], b0),
                           removal_changes_true_flag=truth_flag != flag(full["beta"], b0))
            records.append(rec)
        print("checked", source["combination"], flush=True)
    assert len(records)==11199 and len(failures)==501
    assert sum(r["abnormal"] for r in records)==963
    summary = {}
    for method in METHODS:
        rows = [r for r in records if r["method"]==method]
        bad = [r for r in rows if r["abnormal"]]
        normal = [r for r in rows if not r["abnormal"]]
        summary[method] = dict(attempts=1950, success=len(rows), failed=sum(r["method"]==method for r in failures),
                              abnormal=len(bad), over=sum(r["direction"]=="over" for r in bad), under=sum(r["direction"]=="under" for r in bad),
                              removed_at_true_location=sum(r["removed_by_location_fix"] for r in bad),
                              persists_at_true_location=sum(r["fixed_true_abnormal"] for r in bad),
                              persists_same_direction=sum(r["fixed_true_abnormal"] and r["fixed_true_direction"]==r["direction"] for r in bad),
                              switches_abnormal_direction=sum(r["fixed_true_abnormal"] and r["fixed_true_direction"]!=r["direction"] for r in bad),
                              removed_by_conditional_restore=sum(r["removed_by_conditional_restore"] for r in bad),
                              normal_becomes_abnormal_at_true=sum(r["fixed_true_abnormal"] for r in normal),
                              all_fixed_true_abnormal=sum(r["fixed_true_abnormal"] for r in rows),
                              parameter_mismatch_abnormal=sum(max(r["conditional_beta_log_error"], r["conditional_eta_log_error"])>2e-5 and not r["endpoint_limit_used"] for r in bad),
                              max_conditional_beta_log_error=max(r["conditional_beta_log_error"] for r in bad),
                              max_conditional_eta_log_error=max(r["conditional_eta_log_error"] for r in bad),
                              zero_position_abnormal=sum(r["gamma_hat"]==0 for r in bad),
                              endpoint_abnormal=sum(r["endpoint_limit_used"] for r in bad))
        if method.startswith("MDM"):
            summary[method]["archived_right_edge_fit_abnormal"] = sum(r["archived_root_solver"]=="right_edge_fit" for r in bad)
    bad = [r for r in records if r["abnormal"]]
    remaining = [r for r in bad if r["fixed_true_abnormal"]]
    by_method = {m: [r for r in bad if r["method"]==m] for m in METHODS}
    mdm_under = [r for r in by_method["MDM δ=0.20"] if r["direction"]=="under"]
    wmle_bad = by_method["WMLE"]
    checks = dict(
        conditional_parameter_log_tolerance=2e-5,
        original_abnormal_parameter_matches=sum(max(r["conditional_beta_log_error"], r["conditional_eta_log_error"])<=2e-5 for r in bad),
        lse_selected_r2_above_true=sum(r["selected_minus_true"]>0 for r in by_method["LSE"]),
        lre_selected_r2_above_true=sum(r["selected_minus_true"]>0 for r in by_method["LRE"]),
        mle_selected_ll_not_below_true=sum(r["selected_minus_true"]>=-1e-8 for r in by_method["MLE"]),
        mle_true_ll_above_selected=sum(r["selected_minus_true"]<-1e-8 for r in by_method["MLE"]),
        mdm_under_true_gradient_below_delta=sum(r["gradient_fixed_true"]<r["delta"] for r in mdm_under),
        mdm_under_selected_location_right=sum(r["gamma_hat"]>r["gamma_true"] for r in mdm_under),
        mdm_under_max_finite_gradient_delta_error=max(abs(r["finite_gradient_original"]-r["delta"]) for r in mdm_under),
        wmle_max_squared_residual=max(r["equation_residual"] for r in wmle_bad),
        wmle_direction_matches_equation_sign=sum(
            (r["direction"]=="under" and r["t2_fixed_true"]<0 and r["gamma_hat"]>r["gamma_true"])
            or (r["direction"]=="over" and r["t2_fixed_true"]>0 and r["gamma_hat"]<r["gamma_true"]) for r in wmle_bad),
        original_abnormal_remaining_at_true=len(remaining),
        remaining_all_n7=all(r["n"]==7 for r in remaining),
        remaining_all_fixed_true_over=all(r["fixed_true_direction"]=="over" for r in remaining),
        remaining_direction_switches=sum(r["fixed_true_direction"]!=r["direction"] for r in remaining),
    )
    assert checks["original_abnormal_parameter_matches"]==963
    assert checks["lse_selected_r2_above_true"]==243 and checks["lre_selected_r2_above_true"]==255
    assert checks["mle_selected_ll_not_below_true"]==185 and checks["mle_true_ll_above_selected"]==12
    assert checks["mdm_under_true_gradient_below_delta"]==99 and checks["mdm_under_selected_location_right"]==99
    assert checks["mdm_under_max_finite_gradient_delta_error"]<1e-5
    assert checks["wmle_max_squared_residual"]<1e-8 and checks["wmle_direction_matches_equation_sign"]==84
    assert len(remaining)==15 and checks["remaining_all_n7"] and checks["remaining_all_fixed_true_over"]
    assert checks["remaining_direction_switches"]==2
    keys = list(dict.fromkeys(k for r in records for k in r))
    with (HERE/"全量流程定位.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader(); writer.writerows(records)
    summary_out = dict(scope="all 11,199 finite converged records; 501 original failures excluded from conditional calculations",
                       interpretation="Fixing true location is retrospective; classification is not an estimator and is not an exclusive causal proof.",
                       mmle_intervention="Retain original deletion of first observation; only fix location. Full retained/complete sample contrasts recorded separately.",
                       methods=summary, mechanism_checks=checks, source_sha256=hashes,
                       sources_unchanged=all(helper.digest(Path(p))==h for p,h in hashes.items()))
    assert summary_out["sources_unchanged"]
    (HERE/"全量流程定位.json").write_text(json.dumps(summary_out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
