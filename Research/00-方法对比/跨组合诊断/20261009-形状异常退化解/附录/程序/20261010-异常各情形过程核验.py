"""Evaluate the process behind every representative abnormal case in report2.

Use archived samples, parameters and frozen reference/weight tables. Conditional
fits and nearby criterion probes explain each recorded case; no method run(),
resampling, replacement estimate, status change, or figure generation.
"""
from pathlib import Path
import csv
import importlib.util
import json
import re
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load(HERE / "逐方法机制复核.py", "case_process_helper")
relations = load(HERE / "20261010-异常形成关系核验.py", "case_process_relations")
classifier = load(HERE / "20261010-六方法异常情形整理.py", "case_process_classifier")
curve = load(HERE / "20261010-LSE异常来源全量核验.py", "case_process_curve")
EXAMPLES = {
    "LSE_zero": ("W(2,100,500)", 15, 36, "LSE"),
    "LSE_left": ("W(2,1000,3000)", 7, 1, "LSE"),
    "LSE_right": ("W(2,1000,500)", 7, 19, "LSE"),
    **classifier.EXAMPLES,
}


def main():
    case_path = HERE / "20261010-六方法异常情形核验.json"
    flow_path = HERE / "全量流程定位.csv"
    catalog_path = ROOT / "跨组合汇总/程序/20261007-新增五组合/13组合取数.json"
    previous = json.loads(case_path.read_text(encoding="utf-8"))
    hashes = dict(previous["source_sha256"])
    hashes.update({str(p): helper.digest(p) for p in [case_path, Path(__file__),
                   HERE / "逐方法机制复核.py", HERE / "20261010-异常形成关系核验.py",
                   HERE / "20261010-LSE异常来源全量核验.py"]})
    assert all(helper.digest(Path(p)) == h for p, h in hashes.items())
    png_hashes = dict(previous["protected_png_sha256"])
    assert all(helper.digest(Path(p)) == h for p, h in png_hashes.items())
    sources = {s["combination"]: s for s in json.loads(catalog_path.read_text(encoding="utf-8"))["sources"]}
    with flow_path.open(encoding="utf-8-sig", newline="") as handle:
        records = {(r["combination"], int(r["n"]), int(r["group"]), r["method"]): r
                   for r in csv.DictReader(handle)}
    cache, details, rows = {}, {}, []
    for label, key in EXAMPLES.items():
        combo, n, group, method = key
        source = sources[combo]
        if combo not in cache:
            program = Path(source["program"])
            base = program if program.name == "程序" else program.parent
            path = base / "中间数据/matrix.json" if program.name == "程序" else base / "完整矩阵/数据/matrix.json"
            matrix = json.loads(path.read_text(encoding="utf-8"))
            assert helper.digest(path) == hashes[str(path)]
            snapshot = base / "依赖快照/python"
            sys.path.insert(0, str(snapshot))
            index = len(cache)
            lse = load(snapshot / "methods/lse.py", "process_frozen_lse_" + str(index))
            wmle = load(snapshot / "methods/wmle.py", "process_frozen_wmle_" + str(index))
            cache[combo] = (matrix, lse, wmle)
        matrix, lse, wmle = cache[combo]
        x = np.sort(np.asarray(next(s["values"] for s in matrix["samples"]
                                    if s["n"] == n and s["id"] == group), float))
        truth_beta, _, truth_gamma = map(float, matrix["config"]["truth"])
        record = records[key]
        assert record["abnormal"] == "True"
        selected_gamma = float(record["gamma_hat"])
        diagnostic_gamma = np.nextafter(x[0], 0.0) if selected_gamma >= x[0] and method != "MMLE" else selected_gamma
        retained = x[1:] if method == "MMLE" else x
        z = None
        if method == "LSE":
            z = lse.log_weibull_order_stat_means(n)
        elif method == "LRE":
            ranks = np.arange(1, n + 1)
            if source["protocol"] == "historical-eight":
                p = (ranks - .3) / (n + .4)
            else:
                p = (ranks - 3/8) / (n + 1/4) if n <= 10 else (ranks - .5) / n
            z = np.log(-np.log1p(-p))

        def evaluate(gamma):
            if method in ("LSE", "LRE"):
                profile = helper.regression(x, gamma, z, method)
                profile["slope"] = 1 / profile["beta"] if method == "LSE" else profile["beta"]
                logs = np.log(x - gamma)
                predictor, response = (z, logs) if method == "LSE" else (logs, z)
                intercept = response.mean() - profile["slope"] * predictor.mean()
                profile["reference_values"] = z.tolist()
                profile["fit_residuals"] = (response - intercept - profile["slope"] * predictor).tolist()
                profile["criterion_derivative"] = float(curve.fit_curve(x, z, gamma / x[0])[2][0] / x[0])
                if method == "LSE":
                    profile["first_observed_log_gap"] = float(logs[1] - logs[0])
                    profile["first_fitted_log_gap"] = float(profile["slope"] * (z[1] - z[0]))
            elif method == "MLE" or method == "MMLE":
                profile = helper.shape_profile(retained, gamma)
            elif method.startswith("MDM"):
                profile = helper.mdm_profile(x, gamma)
            else:
                profile = helper.wmle_profile(x, gamma, wmle)
            profile.update(gamma=float(gamma), **relations.log_metrics(retained, gamma, profile["beta"]))
            profile["distances"] = (retained - gamma).tolist()
            profile["log_distances"] = np.log(retained - gamma).tolist()
            return profile

        at_truth = evaluate(truth_gamma)
        at_selected = evaluate(diagnostic_gamma)
        assert abs(np.log(at_selected["beta"] / float(record["beta_hat"]))) < 2e-5
        assert abs(np.log(at_selected["eta"] / float(record["eta_hat"]))) < 2e-5
        for metrics in [at_truth, at_selected]:
            if method in ("MLE", "MMLE"):
                assert abs(metrics["weighted_log_gap"] - 1 / metrics["beta"]) < 1e-10
            if method == "WMLE":
                assert abs(metrics["weighted_log_gap"] - metrics["j2"] / metrics["beta"]) < 1e-10
        probes = []
        if method in ("LSE", "LRE"):
            step = min(x[0] * .01, (x[0] - selected_gamma) * .25)
            for gamma in dict.fromkeys([0.0, truth_gamma, max(0.0, selected_gamma - step),
                                        selected_gamma, selected_gamma + step]):
                probe = helper.regression(x, gamma, z, method)
                probes.append(dict(gamma=float(gamma), loss=probe["relative_residual"], beta=probe["beta"]))
        if label == "MLE_stop":
            for gamma in [selected_gamma, 1.0, 100.0, truth_gamma]:
                probe = helper.shape_profile(x, gamma)
                probes.append(dict(gamma=float(gamma), ll=probe["ll"], beta=probe["beta"],
                                   gain=probe["ll"] - at_selected["ll"]))
        extra = {}
        if method == "MMLE":
            complete = helper.shape_profile(x, truth_gamma)
            extra["complete_sample_at_true_location"] = dict(complete, **relations.log_metrics(x, truth_gamma, complete["beta"]))
        if label == "MDM_edge":
            # Preserve the fallback label; an endpoint gradient is unresolved.
            extra["root_solver"] = record["archived_root_solver"]
            extra["endpoint_gradient_unresolved"] = True
            for beta in [2.0, at_selected["beta"], 10.0, 15.0]:
                p = (np.arange(1, n+1) - .3) / (n + .4)
                u = -np.log1p(-p)
                pseudo_scales = (x-diagnostic_gamma)*u**(-1/beta)
                probes.append(dict(beta=float(beta), sigma=float(np.std(pseudo_scales,ddof=1)),
                                   pseudo_scales=pseudo_scales.tolist()))
        details[label] = dict(combination=combo, n=n, group=group, method=method,
                              case=classifier.classify(record), values=x.tolist(),
                              true_beta=truth_beta, true_gamma=truth_gamma,
                              archived_beta=float(record["beta_hat"]), archived_gamma=selected_gamma,
                              at_true_location=at_truth, at_selected_location=at_selected,
                              probes=probes, **extra)
        for stage, metrics in [("true_location", at_truth), ("selected_location", at_selected)]:
            scalar = {name: value for name, value in metrics.items() if not isinstance(value, list)}
            rows.append(dict(example=label, combination=combo, n=n, group=group, method=method,
                             case=classifier.classify(record), stage=stage, **scalar))
        print(label, json.dumps({stage: {k: round(metrics[k], 7) for k in metrics
                 if k in ["gamma", "beta", "slope", "r2", "relative_residual", "ll", "location_score",
                          "log_sd", "log_range", "weighted_log_gap", "gradient", "t2", "inverse_distance_product", "j3"]}
                 for stage,metrics in [("true",at_truth),("selected",at_selected)]},ensure_ascii=False))
    csv_path = HERE / "20261010-异常各情形过程.csv"
    fieldnames = list(dict.fromkeys(name for row in rows for name in row))
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle,fieldnames=fieldnames,lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    observed = {(case["method"],case["case"]) for case in details.values()}
    expected = {(method,name) for method,counts in classifier.EXPECTED.items() for name in counts}
    assert observed == expected and len(observed) == 15
    local_checks = {}
    for label,case in details.items():
        if case["method"] in ("LSE","LRE"):
            center = case["at_selected_location"]["relative_residual"]
            local_checks[label] = all(probe["loss"] >= center - 1e-9 for probe in case["probes"])
            assert local_checks[label]
    assert all(probe["gain"] > 0 for probe in details["MLE_stop"]["probes"][1:])
    assert details["MDM_edge"]["probes"][1]["sigma"] < details["MDM_edge"]["probes"][0]["sigma"]
    assert all(abs(details[label]["at_selected_location"]["t2"]) < 1e-8
               for label in ["WMLE_low","WMLE_high"])
    report_path = ROOT / "报告2：小样本情况下的明显异常估计.md"
    report = report_path.read_text(encoding="utf-8")
    body = report.split("### 2.1　各方法的异常形成机制",1)[1].split("### 2.2　样本条件与方法差异",1)[0]
    quoted_beta = {label: [f"{case['at_true_location']['beta']:.2f}",
                          f"{case['at_selected_location']['beta']:.2f}"]
                   for label,case in details.items() if label != "MDM_edge"}
    quoted_beta["MDM_edge"] = [f"{details['MDM_edge']['at_selected_location']['beta']:.2f}",
                                 f"{details['MDM_edge']['probes'][0]['sigma']:.2f}",
                                 f"{details['MDM_edge']['probes'][1]['sigma']:.2f}"]
    quoted_beta["LSE_left"].append(f"{details['LSE_left']['at_true_location']['first_fitted_log_gap']:.3f}")
    assert all(value in body for values in quoted_beta.values() for value in values)
    document_checks = dict(report_sha256=helper.digest(report_path), quoted_values=quoted_beta,
                           quoted_values_match=True,
                           six_method_headings=len(re.findall(r"^#### 2\.1\.\d+　",body,re.M)) == 6)
    assert document_checks["six_method_headings"]
    output = dict(scope="16 representative archived records covering all 15 six-method cases",
                  purpose="criterion selection, sample spacing and parameter relation for each case",
                  cases=details, all_15_cases_covered=True, local_regression_criterion_checks=local_checks,
                  document_checks=document_checks, source_sha256=hashes, protected_png_sha256=png_hashes,
                  sources_unchanged=all(helper.digest(Path(p)) == h for p,h in hashes.items()),
                  figures_unchanged=all(helper.digest(Path(p)) == h for p,h in png_hashes.items()))
    assert output["sources_unchanged"] and output["figures_unchanged"]
    (HERE / "20261010-异常各情形过程核验.json").write_text(
        json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
    print("PASS: every representative matches its archived parameters; source data, dependencies and PNG unchanged")


if __name__ == "__main__":
    main()
