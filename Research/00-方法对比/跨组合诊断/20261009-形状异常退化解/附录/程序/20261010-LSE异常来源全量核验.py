"""Check the LSE criterion for all 243 archived shape anomalies in R00.

Use frozen White reference coordinates and preserved samples/results. Evaluate
the original criterion, scan its entire implemented location interval, and
refine every detected stationary point. No run(), resampling, replacement of
estimates, or changes to success/failure labels.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOSS_TOL = 1e-9


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_curve(x, z, fractions):
    """Return normalized residual, shape, and d(residual)/d(gamma/x_min)."""
    fractions = np.atleast_1d(fractions)
    d = x[None, :] / x[0] - fractions[:, None]
    y = np.log(d)
    y -= y.mean(axis=1, keepdims=True)
    zc = z - z.mean()
    slope = (y @ zc) / (zc @ zc)
    residual = y - slope[:, None] * zc
    total = np.einsum("ij,ij->i", y, y)
    unexplained = np.einsum("ij,ij->i", residual, residual)
    dy = -1 / d
    dy -= dy.mean(axis=1, keepdims=True)
    dtotal = 2 * np.einsum("ij,ij->i", y, dy)
    # Regression residuals are orthogonal to zc, so the slope derivative drops out.
    dunexplained = 2 * np.einsum("ij,ij->i", residual, dy)
    derivative = (dunexplained * total - unexplained * dtotal) / total**2
    return unexplained / total, 1 / slope, derivative


def scan(x, z, gamma, density):
    # Same upper support guard as the frozen LSE geometric location grid.
    min_gap = max(abs(float(x[0])) * 1e-9, 1e-12)
    upper = (x[0] - min_gap) / x[0]
    grid = np.unique(np.r_[np.linspace(0, upper, density),
                           1 - np.geomspace(min_gap / x[0], 1, density)])
    losses, _, slopes = fit_curve(x, z, grid)
    candidates = [0.0, float(upper), float(grid[np.argmin(losses)])]
    stationary = []
    maxima = []
    for index in np.flatnonzero(np.signbit(slopes[:-1]) != np.signbit(slopes[1:])):
        root = brentq(lambda t: float(fit_curve(x, z, t)[2][0]),
                      float(grid[index]), float(grid[index + 1]),
                      xtol=2e-14, rtol=2e-14)
        stationary.append(float(root))
        if slopes[index] > 0 and slopes[index + 1] < 0:
            maxima.append(float(root))
        candidates.append(float(root))
    for index in np.flatnonzero((losses[1:-1] <= losses[:-2]) &
                               (losses[1:-1] <= losses[2:])) + 1:
        optimum = minimize_scalar(lambda t: float(fit_curve(x, z, t)[0][0]),
                                  bounds=(float(grid[index - 1]), float(grid[index + 1])),
                                  method="bounded", options={"xatol": 1e-13})
        candidates.append(float(optimum.x))
    refined_losses, refined_beta, _ = fit_curve(x, z, candidates)
    best = int(np.argmin(refined_losses))
    selected_loss, selected_beta, selected_derivative = fit_curve(x, z, gamma / x[0])
    same_basin = sum(v < gamma / x[0] for v in maxima) == sum(v < candidates[best] for v in maxima)
    return dict(best_gamma=float(candidates[best] * x[0]),
                best_loss=float(refined_losses[best]), best_beta=float(refined_beta[best]),
                selected_loss=float(selected_loss[0]), selected_beta=float(selected_beta[0]),
                selected_derivative=float(selected_derivative[0]),
                loss_gain=float(selected_loss[0] - refined_losses[best]),
                detected_stationary_gammas=[v * float(x[0]) for v in stationary],
                selected_and_best_same_basin=bool(same_basin),
                grid_points=len(grid), upper_gamma=float(upper * x[0]))


def main():
    catalog_path = ROOT / "跨组合汇总/程序/20261007-新增五组合/13组合取数.json"
    flow_path = HERE / "全量流程定位.csv"
    sources = json.loads(catalog_path.read_text(encoding="utf-8"))["sources"]
    with flow_path.open(encoding="utf-8-sig", newline="") as handle:
        archived_flow = {(r["combination"], int(r["n"]), int(r["group"])): r
                         for r in csv.DictReader(handle)
                         if r["method"] == "LSE" and r["abnormal"] == "True"}
    assert len(archived_flow) == 243
    hashes = {str(p): digest(p) for p in [catalog_path, flow_path, Path(__file__)]}
    images = list(HERE.parents[1].rglob("*.png"))
    image_hashes = {str(p): digest(p) for p in images}
    records, samples = [], {}
    frozen_hash = None
    lse = None
    for source in sources:
        program = Path(source["program"])
        base = program if program.name == "程序" else program.parent
        matrix_path = (base / "中间数据/matrix.json" if program.name == "程序"
                       else base / "完整矩阵/数据/matrix.json")
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        snapshot = base / "依赖快照/python"
        lse_path = snapshot / "methods/lse.py"
        assert digest(lse_path) == matrix["config"]["dependency_hashes"]["methods/lse.py"]
        for path in [matrix_path, lse_path, snapshot / "base.py"]:
            hashes[str(path)] = digest(path)
        if lse is None:
            sys.path.insert(0, str(snapshot))
            spec = importlib.util.spec_from_file_location("archived_lse_reference", lse_path)
            lse = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(lse)
            frozen_hash = digest(lse_path)
        assert digest(lse_path) == frozen_hash
        truth_beta, truth_eta, truth_gamma = map(float, matrix["config"]["truth"])
        combination = source["combination"]
        lookup = {(s["n"], s["id"]): np.sort(np.asarray(s["values"], float))
                  for s in matrix["samples"]}
        for original in matrix["results"]:
            key = (combination, original["n"], original["id"])
            if original["method_id"] != "lse" or key not in archived_flow:
                continue
            row = archived_flow[key]
            gamma = float(original["gamma_hat"])
            beta = float(original["beta_hat"])
            assert gamma == float(row["gamma_hat"]) and beta == float(row["beta_hat"])
            x = lookup[(original["n"], original["id"])]
            z = lse.log_weibull_order_stat_means(len(x))
            coarse = scan(x, z, gamma, 2049)
            dense = scan(x, z, gamma, 4097)
            assert abs(coarse["best_loss"] - dense["best_loss"]) < LOSS_TOL
            assert abs(np.log(dense["selected_beta"] / beta)) < 1e-11
            assert abs(dense["selected_loss"] - (1 - float(row["criterion_selected"]))) < 1e-12
            direction = row["direction"]
            if gamma == 0:
                location_class = "zero_boundary"
            elif gamma < truth_gamma:
                location_class = "interior_left"
            else:
                location_class = "interior_right"
            if not dense["selected_and_best_same_basin"]:
                status = "different_minimum_found"
            elif dense["loss_gain"] > LOSS_TOL:
                status = "small_refinement_at_same_minimum"
            else:
                status = "criterion_minimum_reproduced"
            best_flag = dense["best_beta"] >= 3 * truth_beta or dense["best_beta"] <= truth_beta / 3
            assert best_flag
            rec = dict(combination=combination, n=len(x), group=original["id"],
                       beta_true=truth_beta, eta_true=truth_eta, gamma_true=truth_gamma,
                       beta_hat=beta, eta_hat=float(original["eta_hat"]), gamma_hat=gamma,
                       direction=direction, location_class=location_class, search_check=status,
                       best_candidate_still_abnormal=bool(best_flag),
                       selected_slope=1 / beta, sample_min=float(x[0]),
                       min_distance=float(x[0] - gamma),
                       beta_at_true_gamma=float(row["beta_fixed_true_location"]),
                       abnormal_at_true_gamma=row["fixed_true_abnormal"] == "True",
                       criterion_gain_over_true=float(row["selected_minus_true"]),
                       **dense,
                       scan_repeat_best_loss_difference=abs(coarse["best_loss"] - dense["best_loss"]))
            records.append(rec)
            samples[key] = x.tolist()
        print("checked", combination, flush=True)
    assert len(records) == 243
    counts = Counter((r["location_class"], r["direction"]) for r in records)
    assert counts == {("zero_boundary", "over"): 105,
                      ("interior_left", "over"): 28,
                      ("interior_right", "under"): 110}
    exceptions = [r for r in records if r["search_check"] == "different_minimum_found"]
    refinements = [r for r in records if r["loss_gain"] > LOSS_TOL]
    representative_keys = [
        ("W(2,100,500)", 15, 36),
        ("W(2,1000,3000)", 7, 1),
        ("W(2,1000,500)", 7, 19),
    ]
    examples = []
    for key in representative_keys:
        rec = next(r for r in records if (r["combination"], r["n"], r["group"]) == key)
        examples.append(dict(rec, values=samples[key]))
    details_path = HERE / "20261010-LSE异常来源逐条.csv"
    serial = [dict(r, detected_stationary_gammas=json.dumps(r["detected_stationary_gammas"])) for r in records]
    with details_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(serial[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(serial)
    report = dict(scope="All 243 original LSE anomalies among 1950 R00 LSE estimates",
                  criterion="SSE/SST = 1 - regression R^2, using frozen White reference points",
                  location_interval="[0, x_min - max(abs(x_min)*1e-9,1e-12)] from original LSE",
                  counts=[dict(location_class=c, direction=d, count=n) for (c, d), n in counts.items()],
                  different_minimum_basin_found=len(exceptions), exceptions=exceptions,
                  improvements_above_loss_tolerance=len(refinements), precision_refinements=refinements,
                  refined_candidates_still_abnormal=sum(r["best_candidate_still_abnormal"] for r in records),
                  loss_comparison_absolute_tolerance=LOSS_TOL,
                  max_criterion_loss_improvement=max(r["loss_gain"] for r in records),
                  max_relative_shape_change=max(abs(r["best_beta"] / r["beta_hat"] - 1) for r in records),
                  max_scan_repeat_best_loss_difference=max(r["scan_repeat_best_loss_difference"] for r in records),
                  max_detected_stationary_points=max(len(r["detected_stationary_gammas"]) for r in records),
                  examples=examples,
                  source_sha256=hashes, protected_png_sha256=image_hashes,
                  sources_unchanged=all(digest(p) == h for p, h in hashes.items()),
                  figures_unchanged=all(digest(p) == h for p, h in image_hashes.items()))
    assert report["sources_unchanged"] and report["figures_unchanged"]
    (HERE / "20261010-LSE异常来源核验.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["counts", "different_minimum_basin_found",
                                           "improvements_above_loss_tolerance",
                                           "refined_candidates_still_abnormal",
                                           "max_criterion_loss_improvement",
                                           "max_detected_stationary_points"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
