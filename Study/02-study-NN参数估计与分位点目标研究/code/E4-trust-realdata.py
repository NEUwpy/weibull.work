"""Lean E4: real-data holdout validation and ensemble conformal trust signals."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_ROOT = SCRIPT_DIR.parent
REPO_ROOT = STUDY_ROOT.parent.parent
SPEC = importlib.util.spec_from_file_location("study02_lean_e2", SCRIPT_DIR / "E2-comparison-generalization.py")
E2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E2)
from study02a.representations import decode_targets


def load_fixed_plan(run_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()]
    selected = [
        row for row in rows
        if row["rule_id"] == config["model"]["rule_id"]
        and row["route"] == config["model"]["route"]
        and int(row["fixed_n"]) in config["sample_sizes"]
        and 420101 <= int(row["seed"]) <= 420110
    ]
    if len(selected) != 50:
        raise ValueError(f"expected 50 frozen fixed checkpoints, got {len(selected)}")
    return sorted(selected, key=lambda row: (int(row["fixed_n"]), int(row["seed"])))


def load_lifetimes(path: Path, expected_sha: str, expected_n: int) -> np.ndarray:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("NIST lifetimes SHA-256 mismatch")
    with path.open(encoding="utf-8", newline="") as handle:
        values = [float(row["failure_time"]) for row in csv.DictReader(handle)]
    result = np.asarray(values, dtype=float)
    if result.size != expected_n or not np.isfinite(result).all():
        raise ValueError("NIST lifetimes count/values mismatch")
    return result


def real_splits(
    lifetimes: np.ndarray,
    n_values: list[int],
    splits: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[np.ndarray], dict[str, np.ndarray]]:
    rows, samples, holdouts = [], [], {}
    for n in n_values:
        rng = np.random.default_rng(seed + n)
        for split_id in range(splits):
            indices = rng.permutation(len(lifetimes))
            train = np.sort(lifetimes[indices[:n]])
            holdout = np.sort(lifetimes[indices[n:]])
            q25, q75 = np.quantile(train, [0.25, 0.75])
            scale = max(float(q75 - q25), float(train[-1] - train[0]), 1.0)
            point_id = f"real-n{n}-s{split_id:04d}"
            rows.append({
                "point_id": point_id,
                "layer": "nist_real",
                "n": n,
                "repeat_id": split_id,
                "beta": 2.0,
                "eta": scale,
                "gamma": float(train[0] - scale),
            })
            samples.append(train)
            holdouts[point_id] = holdout
    return rows, samples, holdouts


def encoded_prediction(record: dict[str, Any]) -> np.ndarray:
    scale = float(record["_anchor_scale"])
    location = float(record["sample_min"])
    return np.array([
        math.log(float(record["beta_hat"])),
        math.log(float(record["eta_hat"]) / scale),
        math.log((location - float(record["gamma_hat"])) / scale),
    ])


def ensemble_rows(
    nn_records: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    samples: list[np.ndarray],
    *,
    include_truth: bool,
) -> list[dict[str, Any]]:
    by_key = {(row["point_id"], int(row["n"]), int(row["repeat_id"])): (row, sample)
              for row, sample in zip(rows, samples)}
    output = []
    keys = sorted(by_key)
    for point_id, n, repeat_id in keys:
        row, sample = by_key[(point_id, n, repeat_id)]
        group = [
            dict(record, _anchor_scale=E2.anchor_sample(sample).scale)
            for record in nn_records
            if record["point_id"] == point_id and int(record["n"]) == n and int(record["repeat_id"]) == repeat_id
        ]
        if len(group) != 10:
            raise ValueError(f"ensemble requires 10 seeds for {point_id}, got {len(group)}")
        encoded = np.stack([encoded_prediction(record) for record in group])
        mean_y = encoded.mean(axis=0)
        anchor = E2.anchor_sample(sample)
        beta_hat, eta_hat, gamma_hat = decode_targets(mean_y, anchor)
        item = {
            "point_id": point_id,
            "layer": row["layer"],
            "n": n,
            "repeat_id": repeat_id,
            "beta_hat": beta_hat,
            "eta_hat": eta_hat,
            "gamma_hat": gamma_hat,
            "sample_min": float(sample[0]),
            "anchor_scale": float(anchor.scale),
            "ensemble_sd_y0": float(encoded[:, 0].std(ddof=1)),
            "ensemble_sd_y1": float(encoded[:, 1].std(ddof=1)),
            "ensemble_sd_y2": float(encoded[:, 2].std(ddof=1)),
            "legal": bool(beta_hat > 0 and eta_hat > 0 and gamma_hat < float(sample[0])),
        }
        if include_truth:
            true_y = E2.encode_targets(row["beta"], row["eta"], row["gamma"], anchor)
            item.update({
                "beta": float(row["beta"]), "eta": float(row["eta"]), "gamma": float(row["gamma"]),
                "true_y0": float(true_y[0]), "true_y1": float(true_y[1]), "true_y2": float(true_y[2]),
                "mean_y0": float(mean_y[0]), "mean_y1": float(mean_y[1]), "mean_y2": float(mean_y[2]),
            })
        output.append(item)
    return output


def weibull_cdf(x: np.ndarray, beta: float, eta: float, gamma: float) -> np.ndarray:
    result = np.zeros_like(x, dtype=float)
    mask = x > gamma
    result[mask] = 1.0 - np.exp(-np.maximum((x[mask] - gamma) / eta, 0.0) ** beta)
    return result


def ks_distance(holdout: np.ndarray, beta: float, eta: float, gamma: float) -> float:
    y = np.sort(np.asarray(holdout, dtype=float))
    fitted = weibull_cdf(y, beta, eta, gamma)
    i = np.arange(1, len(y) + 1)
    return float(max(np.max(np.abs(fitted - i / len(y))), np.max(np.abs(fitted - (i - 1) / len(y)))))


def real_method_rows(
    ensemble: list[dict[str, Any]],
    traditional: list[dict[str, Any]],
    holdouts: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    output = []
    for record in ensemble:
        holdout = holdouts[record["point_id"]]
        output.append({
            **record,
            "method_id": "nn_ensemble",
            "holdout_ks": ks_distance(holdout, record["beta_hat"], record["eta_hat"], record["gamma_hat"]),
            "holdout_support_violation": bool(np.any(holdout < record["gamma_hat"])),
        })
    for record in traditional:
        holdout = holdouts[record["point_id"]]
        distance = (
            ks_distance(holdout, record["beta_hat"], record["eta_hat"], record["gamma_hat"])
            if record["legal"] else 1.0
        )
        output.append({
            **record,
            "holdout_ks": distance,
            "holdout_support_violation": bool(record["legal"] and np.any(holdout < record["gamma_hat"])),
        })
    return output


def paired_ks(real_rows: list[dict[str, Any]], n_boot: int, seed: int) -> list[dict[str, Any]]:
    output = []
    methods = sorted({r["method_id"] for r in real_rows if r["method_id"] != "nn_ensemble"})
    for n in sorted({int(r["n"]) for r in real_rows}):
        nn = sorted([r for r in real_rows if int(r["n"]) == n and r["method_id"] == "nn_ensemble"],
                    key=lambda r: r["repeat_id"])
        for method in methods:
            other = sorted([r for r in real_rows if int(r["n"]) == n and r["method_id"] == method],
                           key=lambda r: r["repeat_id"])
            delta = np.array([a["holdout_ks"] - b["holdout_ks"] for a, b in zip(nn, other)])
            rng = np.random.default_rng(seed + len(output))
            boot = np.array([np.mean(rng.choice(delta, len(delta), replace=True)) for _ in range(n_boot)])
            output.append({
                "n": n,
                "comparison": f"nn_ensemble_minus_{method}",
                "effect": float(delta.mean()),
                "ci_lower": float(np.percentile(boot, 2.5)),
                "ci_upper": float(np.percentile(boot, 97.5)),
                "nn_win_rate": float(np.mean(delta < 0)),
                "ties": int(np.sum(delta == 0)),
            })
    return output


def real_summary(real_rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    groups = []
    for n in config["sample_sizes"]:
        for method in ("nn_ensemble", *config["traditional_methods"]):
            group = [r for r in real_rows if int(r["n"]) == n and r["method_id"] == method]
            groups.append({
                "n": n, "method_id": method, "rows": len(group),
                "mean_holdout_ks": float(np.mean([r["holdout_ks"] for r in group])),
                "median_holdout_ks": float(np.median([r["holdout_ks"] for r in group])),
                "failure_rate": float(np.mean([not r["legal"] for r in group])),
                "support_violation_rate": float(np.mean([r["holdout_support_violation"] for r in group])),
            })
    return {
        "groups": groups,
        "paired": paired_ks(real_rows, int(config["bootstrap"]["replicates"]), int(config["bootstrap"]["seed"])),
    }


def build_simulation_role(config: dict[str, Any], role: str, *, pilot: bool) -> tuple[list[dict], list[np.ndarray]]:
    n_values = config["sample_sizes"]
    root = config[role]
    layers = ["core"] if role == "calibration" else ["core", "boundary_low", "boundary_high", "location_stress"]
    all_rows, all_samples = [], []
    for index, layer in enumerate(layers):
        budget = root if role == "calibration" else (root["core"] if layer == "core" else root["stress_each"])
        points = 4 if pilot else int(budget["parameter_points"])
        repeats = 1 if pilot else int(budget["repeats_per_point_n"])
        rows, samples = E2.build_samples(
            layer, config["layers"][layer], n_values, points, repeats,
            int(root["design_seed"]) + index,
            int(root["sample_seed"]) + index * 10_000_000,
        )
        all_rows.extend(rows)
        all_samples.extend(samples)
    return all_rows, all_samples


def conformal_quantile(values: np.ndarray, level: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=float))
    rank = min(len(ordered), int(math.ceil((len(ordered) + 1) * level)))
    return float(ordered[rank - 1])


def fit_conformal(calibration: list[dict[str, Any]], levels: list[float]) -> dict[str, Any]:
    quantiles: dict[str, Any] = {}
    for n in sorted({int(r["n"]) for r in calibration}):
        group = [r for r in calibration if int(r["n"]) == n]
        quantiles[str(n)] = {}
        for level in levels:
            quantiles[str(n)][str(level)] = [
                conformal_quantile(np.array([abs(r[f"true_y{k}"] - r[f"mean_y{k}"]) for r in group]), level)
                for k in range(3)
            ]
    return quantiles


def apply_conformal(test: list[dict[str, Any]], quantiles: dict[str, Any], levels: list[float]) -> list[dict[str, Any]]:
    output = []
    for row in test:
        for level in levels:
            q = np.asarray(quantiles[str(row["n"])][str(level)], dtype=float)
            mean = np.array([row[f"mean_y{k}"] for k in range(3)])
            true = np.array([row[f"true_y{k}"] for k in range(3)])
            low_y, high_y = mean - q, mean + q
            coverage = (true >= low_y) & (true <= high_y)
            beta_width = math.exp(high_y[0]) - math.exp(low_y[0])
            eta_width = row["anchor_scale"] * (math.exp(high_y[1]) - math.exp(low_y[1]))
            gamma_width = row["anchor_scale"] * (math.exp(high_y[2]) - math.exp(low_y[2]))
            estimate = np.array([row["beta_hat"], row["eta_hat"], row["gamma_hat"]])
            truth = np.array([row["beta"], row["eta"], row["gamma"]])
            row_loss = float(np.mean([
                ((estimate[0] - truth[0]) / truth[0]) ** 2,
                ((estimate[1] - truth[1]) / truth[1]) ** 2,
                ((estimate[2] - truth[2]) / truth[1]) ** 2,
            ]))
            uncertainty = (
                beta_width / max(abs(estimate[0]), 1e-12)
                + eta_width / max(abs(estimate[1]), 1e-12)
                + gamma_width / max(abs(estimate[1]), 1e-12)
            )
            output.append({
                **row,
                "level": level,
                "cover_beta": bool(coverage[0]),
                "cover_eta": bool(coverage[1]),
                "cover_gamma": bool(coverage[2]),
                "cover_joint": bool(np.all(coverage)),
                "width_beta_rel": beta_width / row["beta"],
                "width_eta_rel": eta_width / row["eta"],
                "width_gamma_over_eta": gamma_width / row["eta"],
                "uncertainty_score": uncertainty,
                "row_l_param": math.sqrt(row_loss),
            })
    return output


def conformal_summary(rows: list[dict[str, Any]], levels: list[float]) -> dict[str, Any]:
    groups = []
    for layer in sorted({r["layer"] for r in rows}):
        for n in sorted({int(r["n"]) for r in rows if r["layer"] == layer}):
            for level in levels:
                group = [r for r in rows if r["layer"] == layer and int(r["n"]) == n and r["level"] == level]
                groups.append({
                    "layer": layer, "n": n, "level": level, "rows": len(group),
                    "coverage_beta": float(np.mean([r["cover_beta"] for r in group])),
                    "coverage_eta": float(np.mean([r["cover_eta"] for r in group])),
                    "coverage_gamma": float(np.mean([r["cover_gamma"] for r in group])),
                    "coverage_joint": float(np.mean([r["cover_joint"] for r in group])),
                    "median_width_beta_rel": float(np.median([r["width_beta_rel"] for r in group])),
                    "median_width_eta_rel": float(np.median([r["width_eta_rel"] for r in group])),
                    "median_width_gamma_over_eta": float(np.median([r["width_gamma_over_eta"] for r in group])),
                })
    level95 = max(levels)
    core = [r for r in rows if r["layer"] == "core" and r["level"] == level95]
    ordered = sorted(core, key=lambda r: r["uncertainty_score"])
    selective = []
    for fraction in (0.25, 0.5, 0.75, 1.0):
        kept = ordered[:max(1, int(len(ordered) * fraction))]
        selective.append({
            "retained_fraction": fraction,
            "rows": len(kept),
            "mean_l_param": float(np.mean([r["row_l_param"] for r in kept])),
            "joint_coverage": float(np.mean([r["cover_joint"] for r in kept])),
        })
    correlation = float(spearmanr(
        [r["uncertainty_score"] for r in core], [r["row_l_param"] for r in core]
    ).statistic)
    return {"groups": groups, "selective_risk_95": selective, "uncertainty_error_spearman": correlation}


def write_gzip_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path, *, pilot: bool = False) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    frozen = E2.load_frozen_config(STUDY_ROOT)
    effective = E2.load_effective_formal_config(STUDY_ROOT)
    plan = load_fixed_plan(Path(config["source_run"]), config)
    cache_root = Path(config["cache_root"])

    # A11: real-data train/holdout splits.
    real_cfg = config["real_data"]
    lifetimes_path = REPO_ROOT / real_cfg["lifetimes_csv"]
    lifetimes = load_lifetimes(lifetimes_path, real_cfg["sha256"], int(real_cfg["n_total"]))
    split_count = 5 if pilot else int(real_cfg["splits"])
    real_rows, real_samples, holdouts = real_splits(
        lifetimes, list(real_cfg["sample_sizes"]), split_count, int(real_cfg["split_seed"])
    )
    real_nn_raw = E2.evaluate_nn_cohort(
        plan, real_rows, real_samples, route="V", architecture=config["model"]["architecture"],
        run_dir=Path(config["source_run"]), cache_root=cache_root, frozen=frozen, effective=effective,
    )
    real_ensemble = ensemble_rows(real_nn_raw, real_rows, real_samples, include_truth=False)
    real_traditional = E2.evaluate_traditional_confirmation(real_rows, real_samples, list(config["traditional_methods"]))
    real_results = real_method_rows(real_ensemble, real_traditional, holdouts)

    # A12: independent calibration and confirmation.
    calibration_rows, calibration_samples = build_simulation_role(config, "calibration", pilot=pilot)
    test_rows, test_samples = build_simulation_role(config, "confirmation", pilot=pilot)
    calibration_raw = E2.evaluate_nn_cohort(
        plan, calibration_rows, calibration_samples, route="V", architecture=config["model"]["architecture"],
        run_dir=Path(config["source_run"]), cache_root=cache_root, frozen=frozen, effective=effective,
    )
    test_raw = E2.evaluate_nn_cohort(
        plan, test_rows, test_samples, route="V", architecture=config["model"]["architecture"],
        run_dir=Path(config["source_run"]), cache_root=cache_root, frozen=frozen, effective=effective,
    )
    calibration_ensemble = ensemble_rows(calibration_raw, calibration_rows, calibration_samples, include_truth=True)
    test_ensemble = ensemble_rows(test_raw, test_rows, test_samples, include_truth=True)
    levels = [float(value) for value in config["conformal_levels"]]
    quantiles = fit_conformal(calibration_ensemble, levels)
    conformal_rows = apply_conformal(test_ensemble, quantiles, levels)

    summary = {
        "experiment_id": config["experiment_id"],
        "mode": "pilot" if pilot else "confirmation",
        "config_sha256": E2.canonical_hash(config),
        "source_commit": config["source_commit"],
        "real_data_sha256": real_cfg["sha256"],
        "A11_real_data": real_summary(real_results, config),
        "A12_quantiles": quantiles,
        "A12_conformal": conformal_summary(conformal_rows, levels),
        "counts": {
            "real_result_rows": len(real_results),
            "calibration_samples": len(calibration_ensemble),
            "confirmation_samples": len(test_ensemble),
            "conformal_rows": len(conformal_rows),
        },
    }
    out_dir = Path(config["output_root"]) / ("pilot" if pilot else "confirmation")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_gzip_csv(out_dir / "real_results.csv.gz", real_results)
    write_gzip_csv(out_dir / "conformal_results.csv.gz", conformal_rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    summary = run(args.config, pilot=args.pilot)
    print(json.dumps({"mode": summary["mode"], **summary["counts"],
                      "elapsed_seconds": round(time.monotonic() - started, 3)}))


if __name__ == "__main__":
    main()
