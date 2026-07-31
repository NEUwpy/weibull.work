"""Lean E3 paired equivariance and outlier robustness evaluation."""

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

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_ROOT = SCRIPT_DIR.parent
E2_PATH = SCRIPT_DIR / "E2-comparison-generalization.py"
SPEC = importlib.util.spec_from_file_location("study02_lean_e2", E2_PATH)
E2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E2)


def transform_sample(
    sample: np.ndarray,
    row: dict[str, Any],
    variant: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    values = np.asarray(sample, dtype=float).copy()
    updated = dict(row)
    if variant.startswith("scale_"):
        factor = float(variant.removeprefix("scale_"))
        values *= factor
        updated["eta"] = float(row["eta"]) * factor
        updated["gamma"] = float(row["gamma"]) * factor
    elif variant.startswith("translate_"):
        multiplier = float(variant.removeprefix("translate_"))
        shift = multiplier * float(row["eta"])
        values += shift
        updated["gamma"] = float(row["gamma"]) + shift
    elif variant in {"high_3", "high_10"}:
        factor = float(variant.rsplit("_", 1)[1])
        anchor = float(values[0])
        values[-1] = anchor + factor * (float(values[-1]) - anchor)
    elif variant == "low_iqr":
        q25, q75 = np.quantile(values, [0.25, 0.75])
        values[0] = float(values[0]) - 0.5 * float(q75 - q25)
    elif variant == "bilateral_10pct":
        # n=20: one low + one high replacement is exactly 10% total contamination.
        q25, q75 = np.quantile(values, [0.25, 0.75])
        anchor = float(values[0])
        values[0] = anchor - 0.5 * float(q75 - q25)
        values[-1] = anchor + 10.0 * (float(values[-1]) - anchor)
    elif variant != "clean":
        raise ValueError(f"unknown variant: {variant}")
    return np.sort(values), updated


def variant_rows(
    base_rows: list[dict[str, Any]],
    base_samples: list[np.ndarray],
    variants: list[str],
) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    rows, samples = [], []
    for variant in variants:
        for base_index, (row, sample) in enumerate(zip(base_rows, base_samples)):
            transformed, updated = transform_sample(sample, row, variant)
            updated.update({
                "base_point_id": row["point_id"],
                "base_index": base_index,
                "variant": variant,
                "layer": variant,
                "point_id": f"{row['point_id']}|{variant}",
            })
            if float(updated["gamma"]) >= float(transformed[0]):
                q25, q75 = np.quantile(transformed, [0.25, 0.75])
                updated["_encoding_gamma"] = float(transformed[0] - max(float(q75 - q25), 1e-9))
            rows.append(updated)
            samples.append(transformed)
    return rows, samples


def load_fixed_plan(run_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()]
    selected = [
        row for row in rows
        if row["rule_id"] == config["model"]["rule_id"]
        and row["route"] == config["model"]["route"]
        and int(row["fixed_n"]) == int(config["confirmation"]["n"])
        and 420101 <= int(row["seed"]) <= 420110
    ]
    if len(selected) != 10:
        raise ValueError(f"expected 10 frozen n-specific checkpoints, got {len(selected)}")
    return sorted(selected, key=lambda row: int(row["seed"]))


def pairing_key(record: dict[str, Any]) -> tuple[str, int, str, int]:
    point, _variant = record["point_id"].rsplit("|", 1)
    return point, int(record["repeat_id"]), record["method_id"], int(record["seed"])


def equivariance_residual(
    clean: dict[str, Any],
    changed: dict[str, Any],
    variant: str,
) -> float:
    clean_hat = np.array([clean["beta_hat"], clean["eta_hat"], clean["gamma_hat"]], dtype=float)
    changed_hat = np.array([changed["beta_hat"], changed["eta_hat"], changed["gamma_hat"]], dtype=float)
    if not clean["legal"] or not changed["legal"]:
        return float("nan")
    if variant.startswith("scale_"):
        factor = float(variant.removeprefix("scale_"))
        expected = np.array([clean_hat[0], factor * clean_hat[1], factor * clean_hat[2]])
        denom = np.array([abs(clean_hat[0]), abs(factor * clean_hat[1]), abs(factor * clean["eta"])])
    elif variant.startswith("translate_"):
        shift = float(variant.removeprefix("translate_")) * float(clean["eta"])
        expected = np.array([clean_hat[0], clean_hat[1], clean_hat[2] + shift])
        denom = np.array([abs(clean_hat[0]), abs(clean_hat[1]), abs(clean["eta"])])
    else:
        raise ValueError("equivariance residual requires scale/translate variant")
    return float(np.max(np.abs(changed_hat - expected) / np.maximum(denom, 1e-12)))


def summarize_equivariance(records: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
    clean = {pairing_key(r): r for r in records if r["layer"] == "clean"}
    output = []
    variants = sorted({
        r["layer"] for r in records
        if r["layer"].startswith("scale_") or r["layer"].startswith("translate_")
    })
    methods = sorted({r["method_id"] for r in records})
    for variant in variants:
        for method in methods:
            changed = [r for r in records if r["layer"] == variant and r["method_id"] == method]
            residuals, mismatch = [], 0
            for record in changed:
                baseline = clean[pairing_key(record)]
                if bool(baseline["legal"]) != bool(record["legal"]):
                    mismatch += 1
                residual = equivariance_residual(baseline, record, variant)
                if math.isfinite(residual):
                    residuals.append(residual)
            output.append({
                "variant": variant,
                "method_id": method,
                "paired_rows": len(changed),
                "legal_pairs": len(residuals),
                "legality_mismatch_rate": mismatch / max(len(changed), 1),
                "residual_median": float(np.median(residuals)) if residuals else None,
                "residual_p95": float(np.percentile(residuals, 95)) if residuals else None,
                "residual_max": float(np.max(residuals)) if residuals else None,
                "within_nn_tolerance": (
                    bool(np.max(residuals) <= tolerance)
                    if method == "nn_fixed" and residuals else None
                ),
            })
    return output


def _point_seed_losses(records: list[dict[str, Any]]) -> tuple[list[str], list[int], np.ndarray, np.ndarray]:
    points = sorted({r["point_id"].split("|", 1)[0] for r in records})
    seeds = sorted({int(r["seed"]) for r in records})
    losses = np.empty((len(points), len(seeds)), dtype=float)
    legal = np.empty_like(losses)
    for i, point in enumerate(points):
        for j, seed in enumerate(seeds):
            group = [
                r for r in records
                if r["point_id"].split("|", 1)[0] == point and int(r["seed"]) == seed
            ]
            losses[i, j] = float(np.mean([r["row_loss"] for r in group]))
            legal[i, j] = float(np.mean([r["legal"] for r in group]))
    return points, seeds, losses, legal


def outlier_effect(
    clean: list[dict[str, Any]],
    contaminated: list[dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    points, seeds, clean_loss, clean_legal = _point_seed_losses(clean)
    points2, seeds2, dirty_loss, dirty_legal = _point_seed_losses(contaminated)
    if points != points2 or seeds != seeds2:
        raise ValueError("outlier comparison lost point/seed pairing")

    def effect(pi: np.ndarray, si: np.ndarray) -> tuple[float, float]:
        c = math.sqrt(float(np.mean(clean_loss[np.ix_(pi, si)])))
        d = math.sqrt(float(np.mean(dirty_loss[np.ix_(pi, si)])))
        legal_change = float(np.mean(dirty_legal[np.ix_(pi, si)]) - np.mean(clean_legal[np.ix_(pi, si)]))
        return d - c, legal_change

    observed = effect(np.arange(len(points)), np.arange(len(seeds)))
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, 2), dtype=float)
    for b in range(n_boot):
        pi = rng.integers(0, len(points), len(points))
        si = rng.integers(0, len(seeds), len(seeds))
        boot[b] = effect(pi, si)
    ci = np.percentile(boot, [2.5, 97.5], axis=0)
    return {
        "clean_l_param": math.sqrt(float(np.mean(clean_loss))),
        "contaminated_l_param": math.sqrt(float(np.mean(dirty_loss))),
        "l_param_increase": {"effect": observed[0], "ci_lower": float(ci[0, 0]), "ci_upper": float(ci[1, 0])},
        "clean_legality": float(np.mean(clean_legal)),
        "contaminated_legality": float(np.mean(dirty_legal)),
        "legality_change": {"effect": observed[1], "ci_lower": float(ci[0, 1]), "ci_upper": float(ci[1, 1])},
        "parameter_points": len(points),
        "seeds": len(seeds),
        "bootstrap_replicates": n_boot,
    }


def summarize_outliers(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    methods = sorted({r["method_id"] for r in records})
    for method in methods:
        clean = [r for r in records if r["layer"] == "clean" and r["method_id"] == method]
        for index, variant in enumerate(config["outliers"]):
            contaminated = [r for r in records if r["layer"] == variant and r["method_id"] == method]
            output.append({
                "variant": variant,
                "method_id": method,
                **outlier_effect(
                    clean, contaminated,
                    n_boot=int(config["bootstrap"]["replicates"]),
                    seed=int(config["bootstrap"]["seed"]) + len(output) + index,
                ),
            })
    return output


def write_source(path: Path, records: list[dict[str, Any]]) -> None:
    fields = sorted({field for record in records for field in record})
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def run(config_path: Path, *, pilot: bool = False) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    count = 4 if pilot else int(config["confirmation"]["parameter_points"])
    repeats = 1 if pilot else int(config["confirmation"]["repeats_per_point"])
    n = int(config["confirmation"]["n"])
    base_rows, base_samples = E2.build_samples(
        "core",
        config["core"],
        [n],
        count,
        repeats,
        int(config["confirmation"]["design_seed"]),
        int(config["confirmation"]["sample_seed"]),
    )
    scale = [f"scale_{value:g}" for value in config["scale_factors"]]
    translate = [f"translate_{value:g}" for value in config["translation_eta_multipliers"]]
    variants = ["clean", *scale, *translate, *config["outliers"]]
    rows, samples = variant_rows(base_rows, base_samples, variants)

    fixed_plan = load_fixed_plan(Path(config["source_run"]), config)
    frozen = E2.load_frozen_config(STUDY_ROOT)
    effective = E2.load_effective_formal_config(STUDY_ROOT)
    nn = E2.evaluate_nn_cohort(
        fixed_plan, rows, samples,
        route="V", architecture=config["model"]["architecture"],
        run_dir=Path(config["source_run"]), cache_root=Path(config["cache_root"]),
        frozen=frozen, effective=effective,
    )
    traditional = E2.evaluate_traditional_confirmation(rows, samples, list(config["traditional_methods"]))
    penalty = float(config["failure_penalty"])
    records = [E2.row_metrics(record, penalty) for record in nn + traditional]
    summary = {
        "experiment_id": config["experiment_id"],
        "mode": "pilot" if pilot else "confirmation",
        "config_sha256": E2.canonical_hash(config),
        "source_run": config["source_run"],
        "source_commit": config["source_commit"],
        "records": len(records),
        "datasets": len(rows),
        "equivariance": summarize_equivariance(records, float(config["equivariance_relative_tolerance"])),
        "outlier_effects": summarize_outliers(records, config),
    }
    out_dir = Path(config["output_root"]) / ("pilot" if pilot else "confirmation")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_source(out_dir / "source.csv.gz", records)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    result = run(args.config, pilot=args.pilot)
    print(json.dumps({
        "mode": result["mode"],
        "datasets": result["datasets"],
        "records": result["records"],
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }))


if __name__ == "__main__":
    main()
