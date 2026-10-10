"""Trace the shape changes used in report2 section2.1 on archived samples.

Read preserved estimates and samples, evaluate derived relations, and save
the quantities quoted in the report and appendix. No formal estimator run().
"""
from pathlib import Path
import csv
import hashlib
import json

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log_metrics(x, gamma, beta):
    distance = np.asarray(x, dtype=float) - gamma
    assert np.all(distance > 0)
    logs = np.log(distance)
    weights = np.exp(beta * (logs - logs.max()))
    weights /= weights.sum()
    weighted_gap = float(weights @ logs - logs.mean())
    return dict(
        min_distance=float(distance.min()),
        log_sd=float(np.std(logs, ddof=1)),
        log_range=float(np.ptp(logs)),
        log_max_minus_mean=float(logs.max() - logs.mean()),
        weighted_log_gap=weighted_gap,
        weighted_inverse_distance=float(weights @ (1 / distance)),
        mean_inverse_distance=float(np.mean(1 / distance)),
        beta=float(beta),
    )


def main():
    paired_path = HERE / "逐方法机制复核.json"
    full_path = HERE / "全量流程定位.json"
    csv_path = HERE / "全量流程定位.csv"
    paired = json.loads(paired_path.read_text(encoding="utf-8"))
    full = json.loads(full_path.read_text(encoding="utf-8"))
    sources = dict(full["source_sha256"])
    sources.update({str(p): digest(p) for p in [paired_path, full_path, csv_path, Path(__file__)]})
    assert all(digest(p) == h for p, h in sources.items())
    cases = {}
    for label, rec in paired["samples"].items():
        x = np.asarray(rec["values"])
        truth_beta, _, truth_gamma = rec["truth"]
        out = dict(combination=rec["combination"], n=rec["n"], group=rec["group"],
                   high_threshold=3 * truth_beta, low_threshold=truth_beta / 3, methods={})
        for method, original in rec["methods"].items():
            archived = original["archived"]
            selected = original["at_selected_location"]
            at_truth = original.get("at_true_location",
                                    original.get("at_true_location_same_retained_sample"))
            retained = x[1:] if method == "MMLE" else x
            a = log_metrics(retained, truth_gamma, at_truth["beta"])
            b = log_metrics(retained, archived["gamma_hat"], selected["beta"])
            assert abs(np.log(b["beta"] / archived["beta_hat"])) < 2e-5
            flagged = b["beta"] >= out["high_threshold"] or b["beta"] <= out["low_threshold"]
            assert flagged == (not label.endswith("control"))
            if method == "LSE":
                a.update(slope=1 / a["beta"], criterion=at_truth["fisher_ratio"])
                b.update(slope=1 / b["beta"], criterion=selected["fisher_ratio"])
            elif method == "LRE":
                a["r2"], b["r2"] = at_truth["r2"], selected["r2"]
                # beta = r * sd(z) / sd(y), using the same reference points.
                sz_a = a["beta"] * a["log_sd"] / np.sqrt(a["r2"])
                sz_b = b["beta"] * b["log_sd"] / np.sqrt(b["r2"])
                assert abs(sz_a - sz_b) < 1e-9
                a["reference_sd"] = b["reference_sd"] = float(sz_a)
            elif method == "MLE":
                for metrics, profile in [(a, at_truth), (b, selected)]:
                    assert abs(metrics["weighted_log_gap"] - 1 / metrics["beta"]) < 1e-10
                    metrics["shape_lower_bound"] = 1 / metrics["log_max_minus_mean"]
                    assert metrics["beta"] >= metrics["shape_lower_bound"]
                    score = len(retained) * (
                        metrics["beta"] * metrics["weighted_inverse_distance"]
                        - (metrics["beta"] - 1) * metrics["mean_inverse_distance"]
                    )
                    assert abs(score - profile["location_score"]) < 1e-9
                    metrics.update(location_score=float(score), log_likelihood=profile["ll"])
            elif method == "MDM":
                a["gradient"], b["gradient"] = at_truth["gradient"], selected["gradient"]
                b["delta"] = original["delta"]
                assert abs(b["gradient"] - b["delta"]) < 1e-5
            elif method == "WMLE":
                for metrics, profile in [(a, at_truth), (b, selected)]:
                    assert abs(metrics["weighted_log_gap"] - profile["j2"] / metrics["beta"]) < 1e-10
                    metrics.update(t2=profile["t2"], inverse_distance_product=profile["inverse_distance_product"],
                                   j2=profile["j2"], j3=profile["j3"])
                assert abs(b["t2"]) < 1e-7
            elif method == "MMLE":
                for metrics in [a, b]:
                    assert abs(metrics["weighted_log_gap"] - 1 / metrics["beta"]) < 1e-10
            out["methods"][method] = dict(at_true_location=a, at_selected_location=b)
        cases[label] = out

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    high_mmle = next(r for r in rows if (r["combination"], r["n"], r["group"], r["method"])
                     == ("W(2,1000,3000)", "7", "5", "MMLE"))
    deletion = dict(combination=high_mmle["combination"], n=7, group=5, true_beta=2,
                    complete_at_true_gamma=float(high_mmle["beta_full_sample_fixed_true"]),
                    retained_at_true_gamma=float(high_mmle["beta_fixed_true_location"]),
                    original_mmle_beta=float(high_mmle["beta_hat"]))
    assert deletion["complete_at_true_gamma"] < 6 <= deletion["retained_at_true_gamma"]
    assert deletion["original_mmle_beta"] >= 6
    report = ROOT / "报告2：小样本情况下的明显异常估计.md"
    report_text = report.read_text(encoding="utf-8")
    appendix_path = HERE.parent / "README.md"
    appendix_text = appendix_path.read_text(encoding="utf-8")
    mle = cases["high"]["methods"]["MLE"]["at_selected_location"]
    assert mle["shape_lower_bound"] > cases["high"]["high_threshold"]
    quotes = [f"{cases['high']['methods']['LSE']['at_selected_location']['beta']:.2f}",
              f"{cases['high']['methods']['LRE']['at_true_location']['log_sd']:.3f}",
              f"{mle['shape_lower_bound']:.2f}",
              f"{cases['low']['methods']['MDM']['at_selected_location']['min_distance']:.2f}",
              f"{cases['low']['methods']['WMLE']['at_selected_location']['min_distance']:.2f}",
              f"{deletion['original_mmle_beta']:.2f}"]
    assert all(value in report_text + appendix_text for value in quotes)
    output = dict(scope="R00 archived pairs and one existing MMLE deletion comparison",
                  pairs=cases, mmle_deletion=deletion,
                  document_checks=dict(report_sha256=digest(report),
                      appendix_sha256=digest(appendix_path),
                      quoted_relation_values_match=True,
                      chapter2_has_two_sections="### 2.1　各方法的异常形成机制" in report_text
                      and "### 2.2　样本条件与方法差异" in report_text and "### 2.3" not in report_text),
                  source_sha256=sources, sources_unchanged=all(digest(p) == h for p, h in sources.items()))
    assert output["sources_unchanged"]
    (HERE / "20261010-异常形成关系核验.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: archived pair shape relations, likelihood direction, thresholds and MMLE deletion comparison; sources unchanged")


if __name__ == "__main__":
    main()
