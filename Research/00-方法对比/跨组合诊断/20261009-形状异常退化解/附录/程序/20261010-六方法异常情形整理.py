"""Classify all 963 archived R00 shape anomalies by actual method rules.

Reuse the full conditional-relation audit and the original matrices. Every
record receives one descriptive method-specific case. Known-location contrasts
are retained as controlled comparisons, without an exclusive causal split.
No method run(), resampling, estimation replacement, or failure relabeling.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
METHODS = ("LSE", "LRE", "MLE", "MDM δ=0.20", "WMLE", "MMLE")
EXPECTED = {
    "LSE": {"zero_high": 105, "interior_left_high": 28, "interior_right_low": 110},
    "LRE": {"zero_high": 104, "interior_left_high": 35, "interior_right_low": 116},
    "MLE": {"left_higher_likelihood_high": 158, "right_higher_likelihood_low": 27, "search_stop_high": 12},
    "MDM δ=0.20": {"right_threshold_low": 99, "right_edge_high": 1},
    "WMLE": {"right_joint_intersection_low": 82, "left_joint_intersection_high": 2},
    "MMLE": {"minimum_shift_low": 80, "concentrated_retained_high": 4},
}
EXAMPLES = {
    "LRE_zero": ("W(2,1000,3000)", 7, 5, "LRE"),
    "LRE_left": ("W(2,100,500)", 15, 36, "LRE"),
    "LRE_right": ("W(2,1000,500)", 7, 19, "LRE"),
    "MLE_high": ("W(2,100,500)", 15, 36, "MLE"),
    "MLE_low": ("W(5,1000,500)", 7, 4, "MLE"),
    "MLE_stop": ("W(2,1000,3000)", 7, 37, "MLE"),
    "MDM_low": ("W(5,100,500)", 7, 11, "MDM δ=0.20"),
    "MDM_edge": ("W(2,1000,3000)", 7, 5, "MDM δ=0.20"),
    "WMLE_low": ("W(5,100,500)", 7, 11, "WMLE"),
    "WMLE_high": ("W(1.5,100,500)", 7, 9, "WMLE"),
    "MMLE_low": ("W(5,100,500)", 7, 11, "MMLE"),
    "MMLE_high_deletion": ("W(2,1000,3000)", 7, 5, "MMLE"),
    "MMLE_high_concentrated": ("W(1.5,100,500)", 7, 9, "MMLE"),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classify(row):
    method = row["method"]
    direction = row["direction"]
    gamma, truth = float(row["gamma_hat"]), float(row["gamma_true"])
    if method in ("LSE", "LRE"):
        assert float(row["selected_minus_true"]) > 0
        if gamma == 0:
            assert direction == "over"
            return "zero_high"
        if gamma < truth:
            assert direction == "over"
            return "interior_left_high"
        assert direction == "under"
        return "interior_right_low"
    if method == "MLE":
        if float(row["selected_minus_true"]) < -1e-8:
            assert direction == "over" and gamma < truth
            return "search_stop_high"
        if direction == "over":
            assert gamma < truth
            return "left_higher_likelihood_high"
        assert direction == "under" and gamma > truth
        return "right_higher_likelihood_low"
    if method.startswith("MDM"):
        if row["archived_root_solver"] == "right_edge_fit":
            assert direction == "over"
            return "right_edge_high"
        assert direction == "under" and gamma > truth
        assert float(row["gradient_fixed_true"]) < .2
        assert abs(float(row["finite_gradient_original"]) - .2) < 1e-5
        return "right_threshold_low"
    if method == "WMLE":
        assert float(row["equation_residual"]) < 1e-8
        if direction == "over":
            assert gamma < truth and float(row["t2_fixed_true"]) > 0
            return "left_joint_intersection_high"
        assert gamma > truth and float(row["t2_fixed_true"]) < 0
        return "right_joint_intersection_low"
    assert method == "MMLE" and gamma == float(row["sample_min"])
    assert float(row["beta_hat"]) < float(row["beta_fixed_true_location"])
    return "minimum_shift_low" if direction == "under" else "concentrated_retained_high"


def main():
    flow_path = HERE / "全量流程定位.csv"
    full_path = HERE / "全量流程定位.json"
    catalog_path = ROOT / "跨组合汇总/程序/20261007-新增五组合/13组合取数.json"
    full = json.loads(full_path.read_text(encoding="utf-8"))
    sources = json.loads(catalog_path.read_text(encoding="utf-8"))["sources"]
    hashes = dict(full["source_sha256"])
    hashes.update({str(p): digest(p) for p in [flow_path, full_path, catalog_path, Path(__file__)]})
    assert all(digest(p) == h for p, h in hashes.items())
    images = {str(p): digest(p) for p in HERE.parents[1].rglob("*.png")}
    with flow_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["abnormal"] == "True"]
    assert len(rows) == 963
    classified = []
    for row in rows:
        fields = ("combination", "n", "group", "method", "beta_true", "eta_true", "gamma_true",
                  "beta_hat", "eta_hat", "gamma_hat", "direction", "sample_min",
                  "selected_minus_true", "archived_root_solver", "finite_gradient_original",
                  "equation_residual", "t2_fixed_true")
        classified.append(dict(case=classify(row), **{k: row[k] for k in fields}))
    counts = {m: dict(Counter(r["case"] for r in classified if r["method"] == m)) for m in METHODS}
    assert counts == EXPECTED
    raw_lookup, sample_lookup = {}, {}
    for source in sources:
        program = Path(source["program"])
        base = program if program.name == "程序" else program.parent
        path = base / "中间数据/matrix.json" if program.name == "程序" else base / "完整矩阵/数据/matrix.json"
        matrix = json.loads(path.read_text(encoding="utf-8"))
        assert digest(path) == hashes[str(path)]
        combo = source["combination"]
        for sample in matrix["samples"]:
            sample_lookup[(combo, sample["n"], sample["id"])] = sorted(sample["values"])
        for rec in matrix["results"]:
            method = "MDM δ=0.20" if rec["method_id"] == "mdm" else rec["method_id"].upper()
            if method.startswith("MDM") and rec["delta"] != .2:
                continue
            raw_lookup[(combo, rec["n"], rec["id"], method)] = rec
    key_row = {(r["combination"], int(r["n"]), int(r["group"]), r["method"]): r for r in rows}
    examples = {}
    for label, key in EXAMPLES.items():
        row = key_row[key]
        raw = raw_lookup[key]
        assert float(row["beta_hat"]) == float(raw["beta_hat"])
        examples[label] = dict(case=classify(row), values=sample_lookup[key[:3]], record=row,
                               original_record=raw.get("original_record", {}))
    stops = []
    for row in rows:
        if row["method"] != "MLE" or classify(row) != "search_stop_high":
            continue
        key = (row["combination"], int(row["n"]), int(row["group"]), row["method"])
        old = raw_lookup[key].get("original_record", {})
        info = old.get("solution_info", "{}")
        info = json.loads(info) if isinstance(info, str) else info
        stops.append(dict(combination=key[0], n=key[1], group=key[2],
                          gamma_hat=float(row["gamma_hat"]),
                          gain_at_true_location=-float(row["selected_minus_true"]),
                          solution_info=info))
    deletions = []
    for row in rows:
        if row["method"] != "MMLE" or row["direction"] != "over":
            continue
        truth = float(row["beta_true"])
        complete, retained = float(row["beta_full_sample_fixed_true"]), float(row["beta_fixed_true_location"])
        assert retained > complete
        deletions.append(dict(combination=row["combination"], n=int(row["n"]), group=int(row["group"]),
                              true_beta=truth, complete_at_true_gamma=complete,
                              retained_at_true_gamma=retained,
                              original_mmle_beta=float(row["beta_hat"]),
                              complete_already_high=complete >= 3 * truth))
    assert len(deletions) == 4 and sum(r["complete_already_high"] for r in deletions) == 3
    detail_path = HERE / "20261010-六方法异常情形.csv"
    with detail_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(classified[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(classified)
    output = dict(scope="963 finite original R00 shape anomalies; six original methods",
                  classification="Descriptive cases of the actual criterion, intersection, stop or construction",
                  counts=counts, examples=examples, mle_stops=stops,
                  mmle_same_true_location_deletion_comparisons=deletions,
                  source_sha256=hashes, protected_png_sha256=images,
                  sources_unchanged=all(digest(p) == h for p, h in hashes.items()),
                  figures_unchanged=all(digest(p) == h for p, h in images.items()))
    assert output["sources_unchanged"] and output["figures_unchanged"]
    (HERE / "20261010-六方法异常情形核验.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    print("PASS: all 963 records classified; archived estimates, method versions, labels and PNG unchanged")


if __name__ == "__main__":
    main()
