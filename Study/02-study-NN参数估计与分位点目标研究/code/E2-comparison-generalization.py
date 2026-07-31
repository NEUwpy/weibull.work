"""Lean E2: read-only comparison and generalization evaluation.

Answers A2/A3/A9/A10/A19 by evaluating the frozen A-E3 fixed and shared
checkpoint cohorts on an independent confirmation design.  It does not train,
select, unseal, or consume any formal artifact.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from scipy.stats import qmc, spearmanr

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_ROOT = SCRIPT_DIR.parent
REPO_ROOT = STUDY_ROOT.parent.parent
sys.path[:0] = [str(SCRIPT_DIR), str(REPO_ROOT / "python")]

from study02a.config import load_frozen_config
from study02a.formal_config import load_effective_formal_config
from study02a.formal_data import (
    FormalFixedExample,
    FormalSetExample,
    collate_fixed_features,
    collate_set_features,
)
from study02a.formal_executor import resolve_model_factory
from study02a.formal_runner import (
    _standardize,
    build_training_spec,
    cache_dataset,
    fit_training_scaler,
)
from study02a.representations import SetFeatures, anchor_sample, build_features, encode_targets
from study02a.training import load_checkpoint


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_plan_rows(run_dir: Path, config: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    rows = [json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()]
    formal_seeds = set(range(420101, 420111))
    fixed_cfg = config["models"]["fixed"]
    shared_cfg = config["models"]["shared"]
    fixed = [
        row for row in rows
        if row["rule_id"] == fixed_cfg["rule_id"]
        and row["route"] == fixed_cfg["route"]
        and int(row["seed"]) in formal_seeds
        and int(row["fixed_n"]) in config["sample_sizes"]["core"]
    ]
    shared = [
        row for row in rows
        if row["rule_id"] == shared_cfg["rule_id"]
        and row["route"] == shared_cfg["route"]
        and int(row["seed"]) in formal_seeds
    ]
    if len(fixed) != 50 or len(shared) != 10:
        raise ValueError(f"expected frozen cohorts fixed=50/shared=10, got {len(fixed)}/{len(shared)}")
    return sorted(fixed, key=lambda r: (int(r["fixed_n"]), int(r["seed"]))), sorted(shared, key=lambda r: int(r["seed"]))


def parameter_points(layer: str, spec: dict[str, list[float]], count: int, seed: int) -> list[dict[str, Any]]:
    power = int(math.ceil(math.log2(count)))
    unit = qmc.Sobol(d=3, scramble=True, seed=int(seed)).random_base2(power)[:count]
    beta = np.exp(np.log(spec["beta"][0]) + unit[:, 0] * np.log(spec["beta"][1] / spec["beta"][0]))
    eta = np.exp(np.log(spec["eta"][0]) + unit[:, 1] * np.log(spec["eta"][1] / spec["eta"][0]))
    rho = spec["rho"][0] + unit[:, 2] * (spec["rho"][1] - spec["rho"][0])
    return [
        {
            "point_id": f"{layer}-{i:04d}",
            "layer": layer,
            "beta": float(beta[i]),
            "eta": float(eta[i]),
            "rho": float(rho[i]),
            "gamma": float(rho[i] * eta[i]),
        }
        for i in range(count)
    ]


def build_samples(
    layer: str,
    layer_spec: dict[str, list[float]],
    n_values: Iterable[int],
    point_count: int,
    repeats: int,
    design_seed: int,
    sample_seed: int,
) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    points = parameter_points(layer, layer_spec, point_count, design_seed)
    rows: list[dict[str, Any]] = []
    samples: list[np.ndarray] = []
    for point_index, point in enumerate(points):
        for n in n_values:
            for repeat_id in range(repeats):
                row = {**point, "n": int(n), "repeat_id": repeat_id}
                seed = int(sample_seed + point_index * 100_000 + int(n) * 1_000 + repeat_id)
                rng = np.random.default_rng(seed)
                u = rng.uniform(0.0, 1.0, int(n))
                sample = np.sort(
                    point["gamma"] + point["eta"] * (-np.log1p(-u)) ** (1.0 / point["beta"])
                )
                rows.append(row)
                samples.append(sample)
    return rows, samples


def row_metrics(record: dict[str, Any], failure_penalty: float) -> dict[str, Any]:
    legal = bool(record["legal"])
    if legal:
        e_beta = (float(record["beta_hat"]) - float(record["beta"])) / float(record["beta"])
        e_eta = (float(record["eta_hat"]) - float(record["eta"])) / float(record["eta"])
        e_gamma = (float(record["gamma_hat"]) - float(record["gamma"])) / float(record["eta"])
        row_loss = (e_beta**2 + e_eta**2 + e_gamma**2) / 3.0
    else:
        e_beta = e_eta = e_gamma = float(failure_penalty)
        row_loss = float(failure_penalty) ** 2
    return {**record, "e_beta": e_beta, "e_eta": e_eta, "e_gamma": e_gamma, "row_loss": row_loss}


def evaluate_traditional_confirmation(
    rows: list[dict[str, Any]],
    samples: list[np.ndarray],
    method_ids: list[str],
) -> list[dict[str, Any]]:
    """Call production estimators, including MDM's required default offset."""
    from methods.registry import IMPLEMENTED

    output = []
    for row, sample in zip(rows, samples):
        for method_id in method_ids:
            try:
                estimator = IMPLEMENTED[method_id](sample.tolist())
                result = estimator.run(offset=0.1) if method_id == "mdm" else estimator.run()
                if hasattr(result, "to_list"):
                    result = result.to_list()
                beta_hat, eta_hat, gamma_hat = map(float, result[:3])
                converged = bool(result[4]) if len(result) > 4 else True
            except Exception:
                beta_hat = eta_hat = gamma_hat = float("nan")
                converged = False
            legal = bool(
                math.isfinite(beta_hat) and math.isfinite(eta_hat) and math.isfinite(gamma_hat)
                and beta_hat > 0.0 and eta_hat > 0.0 and gamma_hat < float(sample[0])
                and converged
            )
            output.append({
                "point_id": row["point_id"],
                "layer": row["layer"],
                "sample_id": f"confirmation:{row['point_id']}:n{row['n']}:r{row['repeat_id']}",
                "method_id": method_id,
                "method_role": "traditional",
                "n": int(row["n"]),
                "repeat_id": int(row["repeat_id"]),
                "seed": 0,
                "fit_id": "",
                "checkpoint_sha256": "",
                "beta_hat": beta_hat,
                "eta_hat": eta_hat,
                "gamma_hat": gamma_hat,
                "beta": float(row["beta"]),
                "eta": float(row["eta"]),
                "gamma": float(row["gamma"]),
                "sample_min": float(sample[0]),
                "legal": legal,
                "converged": converged,
            })
    return output


def _nn_batch(rows: list[dict], samples: list[np.ndarray], route: str):
    examples = []
    for row, sample in zip(rows, samples):
        anchor = anchor_sample(sample)
        features = build_features(route, sample, int(row["n"]))
        target = encode_targets(row["beta"], row["eta"], row["gamma"], anchor)
        if isinstance(features, SetFeatures):
            examples.append(FormalSetExample(features, target, anchor.location, anchor.scale))
        else:
            examples.append(FormalFixedExample(features, target, anchor.location, anchor.scale))
    return collate_set_features(examples) if route == "S" else collate_fixed_features(examples)


def evaluate_nn_cohort(
    plan_rows: list[dict],
    rows: list[dict],
    samples: list[np.ndarray],
    *,
    route: str,
    architecture: str,
    run_dir: Path,
    cache_root: Path,
    frozen: Any,
    effective: Any,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    groups = {None: list(range(len(rows)))} if route == "S" else {
        n: [i for i, row in enumerate(rows) if int(row["n"]) == n]
        for n in sorted({int(row["n"]) for row in rows})
    }
    for n, indices in groups.items():
        subset_rows = [rows[i] for i in indices]
        subset_samples = [samples[i] for i in indices]
        batch = _nn_batch(subset_rows, subset_samples, route)
        spec = build_training_spec(
            route=route,
            distribution="core_continuous",
            n_mode="shared_n" if route == "S" else "fixed_n",
            fixed_n=None if route == "S" else int(n),
            training_rows=100000,
            frozen_config=frozen,
            effective_config=effective,
        )
        scaler = fit_training_scaler(cache_dataset(spec, frozen, effective, cache_root), frozen, effective)
        if route == "S":
            batch = replace(batch, model_n=_standardize(batch.n.reshape(-1, 1), scaler).reshape(-1))
        else:
            batch = replace(batch, features=_standardize(batch.features, scaler))
        applicable = plan_rows if route == "S" else [r for r in plan_rows if int(r["fixed_n"]) == int(n)]
        for plan_row in applicable:
            model = resolve_model_factory(
                architecture,
                frozen,
                None if route == "S" else int(n),
                output_form="joint",
            )()
            checkpoint = run_dir / "outputs" / plan_row["fit_id"] / "checkpoint.pt"
            model.load_state_dict(load_checkpoint(checkpoint))
            model.eval()
            with torch.no_grad():
                raw = (
                    model(batch.values, batch.mask, batch.model_n)
                    if route == "S" else model(batch.features)
                ).cpu().numpy().astype(float)
            loc = batch.location.cpu().numpy().astype(float)
            scale = batch.scale.cpu().numpy().astype(float)
            estimates = np.column_stack([
                np.exp(raw[:, 0]),
                scale * np.exp(raw[:, 1]),
                loc - scale * np.exp(raw[:, 2]),
            ])
            checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            for i, (row, estimate) in enumerate(zip(subset_rows, estimates)):
                beta_hat, eta_hat, gamma_hat = map(float, estimate)
                legal = (
                    np.isfinite(estimate).all()
                    and beta_hat > 0.0 and eta_hat > 0.0 and gamma_hat < float(loc[i])
                )
                output.append({
                    "point_id": row["point_id"],
                    "layer": row["layer"],
                    "sample_id": f"confirmation:{row['point_id']}:n{row['n']}:r{row['repeat_id']}",
                    "method_id": f"nn_{'shared' if route == 'S' else 'fixed'}",
                    "method_role": "nn",
                    "n": int(row["n"]),
                    "repeat_id": int(row["repeat_id"]),
                    "seed": int(plan_row["seed"]),
                    "fit_id": plan_row["fit_id"],
                    "checkpoint_sha256": checkpoint_sha,
                    "beta_hat": beta_hat,
                    "eta_hat": eta_hat,
                    "gamma_hat": gamma_hat,
                    "beta": float(row["beta"]),
                    "eta": float(row["eta"]),
                    "gamma": float(row["gamma"]),
                    "sample_min": float(loc[i]),
                    "legal": bool(legal),
                    "converged": True,
                })
    return output


def summarize_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    loss = np.asarray([r["row_loss"] for r in records], dtype=float)
    return {
        "rows": len(records),
        "parameter_points": len({r["point_id"] for r in records}),
        "seeds": len({int(r["seed"]) for r in records}),
        "l_param": float(np.sqrt(np.mean(loss))),
        "failure_rate": float(np.mean([not r["legal"] for r in records])),
        "rmse_beta_rel": float(np.sqrt(np.mean([r["e_beta"] ** 2 for r in records]))),
        "rmse_eta_rel": float(np.sqrt(np.mean([r["e_eta"] ** 2 for r in records]))),
        "rmse_gamma_over_eta": float(np.sqrt(np.mean([r["e_gamma"] ** 2 for r in records]))),
    }


def grouped_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["layer"], int(r["n"]), r["method_id"]) for r in records})
    return [
        {"layer": layer, "n": n, "method_id": method, **summarize_group([
            r for r in records if (r["layer"], int(r["n"]), r["method_id"]) == (layer, n, method)
        ])}
        for layer, n, method in keys
    ]


def seed_stability(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for n in sorted({int(r["n"]) for r in records}):
        values = []
        for seed in sorted({int(r["seed"]) for r in records}):
            group = [r for r in records if int(r["n"]) == n and int(r["seed"]) == seed]
            if group:
                values.append((seed, summarize_group(group)["l_param"]))
        scores = np.asarray([value for _, value in values])
        points = sorted({r["point_id"] for r in records if int(r["n"]) == n})
        point_seed = np.empty((len(points), len(values)), dtype=float)
        for i, point in enumerate(points):
            for j, (seed, _) in enumerate(values):
                losses = [
                    r["row_loss"] for r in records
                    if int(r["n"]) == n and int(r["seed"]) == seed and r["point_id"] == point
                ]
                point_seed[i, j] = math.sqrt(float(np.mean(losses)))
        total_variance = float(np.var(point_seed, ddof=1))
        between_seed_variance = float(np.var(np.mean(point_seed, axis=0), ddof=1))
        rank_correlations = [
            float(spearmanr(point_seed[:, a], point_seed[:, b]).statistic)
            for a in range(point_seed.shape[1])
            for b in range(a + 1, point_seed.shape[1])
        ]
        result.append({
            "n": n,
            "seed_scores": [{"seed": seed, "l_param": score} for seed, score in values],
            "mean": float(scores.mean()),
            "sd": float(scores.std(ddof=1)),
            "worst": float(scores.max()),
            "coefficient_of_variation": float(scores.std(ddof=1) / scores.mean()),
            "seed_variance_share": float(between_seed_variance / max(total_variance, 1e-15)),
            "point_difficulty_rank_spearman_mean": float(np.mean(rank_correlations)),
            "point_difficulty_rank_spearman_min": float(np.min(rank_correlations)),
            "rank_order": [seed for seed, _ in sorted(values, key=lambda item: item[1])],
        })
    return result


def paired_comparison(
    nn_records: list[dict[str, Any]],
    traditional_records: list[dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Point-cluster bootstrap with NN training seed as the second level."""
    points = sorted({r["point_id"] for r in nn_records})
    seeds = sorted({int(r["seed"]) for r in nn_records})
    fields = ("row_loss", "e_beta", "e_eta", "e_gamma")
    nn = {field: np.empty((len(points), len(seeds)), dtype=float) for field in fields}
    trad = {field: np.empty(len(points), dtype=float) for field in fields}
    nn_fail = np.empty((len(points), len(seeds)), dtype=float)
    trad_fail = np.empty(len(points), dtype=float)
    for i, point in enumerate(points):
        trad_point = [r for r in traditional_records if r["point_id"] == point]
        if not trad_point:
            raise ValueError(f"missing paired traditional point {point}")
        for field in fields:
            values = np.asarray([r[field] for r in trad_point], dtype=float)
            trad[field][i] = float(np.mean(values if field == "row_loss" else values**2))
        trad_fail[i] = float(np.mean([not r["legal"] for r in trad_point]))
        for j, training_seed in enumerate(seeds):
            group = [r for r in nn_records if r["point_id"] == point and int(r["seed"]) == training_seed]
            if not group:
                raise ValueError(f"missing NN point/seed pair {point}/{training_seed}")
            for field in fields:
                values = np.asarray([r[field] for r in group], dtype=float)
                nn[field][i, j] = float(np.mean(values if field == "row_loss" else values**2))
            nn_fail[i, j] = float(np.mean([not r["legal"] for r in group]))

    def effects(point_index: np.ndarray, seed_index: np.ndarray) -> tuple[float, float, list[float]]:
        nn_loss = math.sqrt(float(np.mean(nn["row_loss"][np.ix_(point_index, seed_index)])))
        trad_loss = math.sqrt(float(np.mean(trad["row_loss"][point_index])))
        improvement = (trad_loss - nn_loss) / max(abs(trad_loss), 1e-12)
        failure_difference = (
            float(np.mean(nn_fail[np.ix_(point_index, seed_index)]))
            - float(np.mean(trad_fail[point_index]))
        )
        worsening = []
        for field in ("e_beta", "e_eta", "e_gamma"):
            nn_rmse = math.sqrt(float(np.mean(nn[field][np.ix_(point_index, seed_index)])))
            trad_rmse = math.sqrt(float(np.mean(trad[field][point_index])))
            worsening.append((nn_rmse - trad_rmse) / max(abs(trad_rmse), 1e-12))
        return improvement, failure_difference, worsening

    observed = effects(np.arange(len(points)), np.arange(len(seeds)))
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, 5), dtype=float)
    for b in range(n_boot):
        sampled_points = rng.integers(0, len(points), size=len(points))
        sampled_seeds = rng.integers(0, len(seeds), size=len(seeds))
        improvement, failure_difference, worsening = effects(sampled_points, sampled_seeds)
        boot[b] = [improvement, failure_difference, *worsening]
    ci = np.percentile(boot, [2.5, 97.5], axis=0)
    labels = ("l_param_relative_improvement", "failure_rate_difference",
              "beta_rmse_relative_worsening", "eta_rmse_relative_worsening",
              "gamma_rmse_relative_worsening")
    result = {
        label: {
            "effect": float(value),
            "ci_lower": float(ci[0, index]),
            "ci_upper": float(ci[1, index]),
        }
        for index, (label, value) in enumerate(zip(labels, [observed[0], observed[1], *observed[2]]))
    }
    result["global_better"] = bool(
        result["failure_rate_difference"]["ci_upper"] <= 0.01
        and result["l_param_relative_improvement"]["ci_lower"] > 0.0
        and all(result[label]["ci_upper"] <= 0.05 for label in labels[2:])
    )
    result["parameter_points"] = len(points)
    result["training_seeds"] = len(seeds)
    result["bootstrap_replicates"] = n_boot
    return result


def all_comparisons(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    nn_all = [r for r in records if r["method_id"] == "nn_fixed"]
    for layer in sorted({r["layer"] for r in nn_all}):
        for n in sorted({int(r["n"]) for r in nn_all if r["layer"] == layer}):
            nn = [r for r in nn_all if r["layer"] == layer and int(r["n"]) == n]
            for index, method in enumerate(config["traditional_methods"]):
                traditional = [
                    r for r in records
                    if r["method_id"] == method and r["layer"] == layer and int(r["n"]) == n
                ]
                output.append({
                    "layer": layer,
                    "n": n,
                    "traditional_method": method,
                    **paired_comparison(
                        nn,
                        traditional,
                        n_boot=int(config["bootstrap"]["replicates"]),
                        seed=int(config["bootstrap"]["seed"]) + len(output) + index,
                    ),
                })
    return output


def monotonic_trend(records: list[dict[str, Any]]) -> dict[str, Any]:
    n_values = sorted({int(r["n"]) for r in records})
    means = {n: summarize_group([r for r in records if int(r["n"]) == n])["l_param"] for n in n_values}
    by_point = []
    for point in sorted({r["point_id"] for r in records}):
        point_means = []
        for n in n_values:
            group = [r["row_loss"] for r in records if r["point_id"] == point and int(r["n"]) == n]
            point_means.append(float(np.sqrt(np.mean(group))))
        by_point.append(sum(b > a for a, b in zip(point_means, point_means[1:])) / max(len(n_values) - 1, 1))
    return {
        "n_l_param": means,
        "overall_direction_improves": bool(means[n_values[-1]] < means[n_values[0]]),
        "adjacent_mean_violations": int(sum(means[b] > means[a] for a, b in zip(n_values, n_values[1:]))),
        "point_adjacent_violation_proportion": float(np.mean(by_point)),
    }


def write_source(path: Path, records: list[dict[str, Any]]) -> None:
    fields = sorted({field for record in records for field in record})
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def run(config_path: Path, *, pilot: bool = False) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run_dir = Path(config["source_run"])
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    fixed_plan, shared_plan = load_plan_rows(run_dir, config)
    confirmation = config["confirmation"]
    point_scale = 8 if pilot else 1
    repeat_scale = 5 if pilot else 1
    fixed_rows: list[dict] = []
    fixed_samples: list[np.ndarray] = []
    layer_names = ["core", "boundary_low", "boundary_high", "location_stress"]
    for layer_index, layer in enumerate(layer_names):
        budget = confirmation["core"] if layer == "core" else confirmation["stress_each"]
        rows, samples = build_samples(
            layer,
            config["layers"][layer],
            config["sample_sizes"]["core"],
            max(2, int(budget["parameter_points"]) // point_scale),
            max(1, int(budget["repeats_per_point_n"]) // repeat_scale),
            int(confirmation["design_seed"]) + layer_index,
            int(confirmation["sample_seed"]) + layer_index * 10_000_000,
        )
        fixed_rows.extend(rows)
        fixed_samples.extend(samples)
    unseen_rows, unseen_samples = build_samples(
        "unseen_n",
        config["layers"]["core"],
        config["sample_sizes"]["unseen_interpolation"] + config["sample_sizes"]["unseen_extrapolation"],
        max(2, int(confirmation["unseen_n"]["parameter_points"]) // point_scale),
        max(1, int(confirmation["unseen_n"]["repeats_per_point_n"]) // repeat_scale),
        int(confirmation["design_seed"]) + 10,
        int(confirmation["sample_seed"]) + 100_000_000,
    )
    frozen = load_frozen_config(STUDY_ROOT)
    effective = load_effective_formal_config(STUDY_ROOT)
    cache_root = Path(config["cache_root"])
    records = evaluate_nn_cohort(
        fixed_plan, fixed_rows, fixed_samples,
        route="V", architecture=config["models"]["fixed"]["architecture"],
        run_dir=run_dir, cache_root=cache_root, frozen=frozen, effective=effective,
    )
    records.extend(evaluate_nn_cohort(
        shared_plan, unseen_rows, unseen_samples,
        route="S", architecture=config["models"]["shared"]["architecture"],
        run_dir=run_dir, cache_root=cache_root, frozen=frozen, effective=effective,
    ))
    traditional = evaluate_traditional_confirmation(
        fixed_rows, fixed_samples, list(config["traditional_methods"])
    )
    penalty = float(config["failure_penalty"])
    records = [row_metrics(record, penalty) for record in records + traditional]
    fixed_nn = [r for r in records if r["method_id"] == "nn_fixed" and r["layer"] == "core"]
    shared_nn = [r for r in records if r["method_id"] == "nn_shared"]
    summary = {
        "experiment_id": config["experiment_id"],
        "mode": "pilot" if pilot else "confirmation",
        "config_sha256": canonical_hash(config),
        "source_commit": config["source_commit"],
        "source_run": str(run_dir),
        "records": len(records),
        "groups": grouped_summary(records),
        "A2_paired_comparisons": all_comparisons(records, config),
        "A9_seed_stability": seed_stability(fixed_nn),
        "A10_legality": {
            "fixed_core": float(np.mean([r["legal"] for r in fixed_nn])),
            "shared_unseen_n": float(np.mean([r["legal"] for r in shared_nn])),
            "all_nn": float(np.mean([r["legal"] for r in records if r["method_role"] == "nn"])),
        },
        "A19_fixed_core_trend": monotonic_trend(fixed_nn),
        "A19_shared_unseen_trend": monotonic_trend(shared_nn),
    }
    out_dir = Path(config["output_root"]) / ("pilot" if pilot else "confirmation")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_source(out_dir / "source.csv.gz", records)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    summary = run(args.config, pilot=args.pilot)
    print(json.dumps({
        "mode": summary["mode"],
        "records": summary["records"],
        "groups": len(summary["groups"]),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }))


if __name__ == "__main__":
    main()
