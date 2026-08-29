"""Post-test 600/60 sensitivity comparison for P, Q, QP, and QCP.

P, Q, and QP are retrained under the same 600-epoch / patience-60 ceiling
already used by the frozen QCP route. Existing QCP evidence is reused without
modification. This module never labels the result as a first-open confirmation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import config as CFG
from . import constrained_confirm as QCP_CONFIRM
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "equal-budget-sensitivity-v1.json"
PROTOCOL_PATH = ROOT / "protocols" / "17-四路线同预算敏感性验证合同.md"
OUT = ROOT / "artifacts" / "equal_budget_sensitivity"
EVIDENCE = OUT / "evidence"
METADATA = OUT / "fit_metadata"
ANALYSIS = OUT / "analysis"
QCP_ROOT = ROOT / "artifacts" / "qcp_constrained_confirm"
QCP_CONFIG = ROOT / "configs" / "qcp-constrained-confirm-v1.json"
TRAINED_ROUTES = ("P", "Q", "QP")
ALL_ROUTES = ("P", "Q", "QP", "QCP")


def _json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _cfg() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _fit_name(n: int, fold: int, seed: int, route: str) -> str:
    return f"n{n}_f{fold}_s{seed}_r{route}"


def _paths(root: Path, n: int, fold: int, seed: int,
           route: str) -> tuple[Path, Path]:
    fit = _fit_name(n, fold, seed, route)
    return (root / "fit_metadata" / f"{fit}.json",
            root / "evidence" / f"{fit}.npz")


def _load_meta(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_pair(left: dict, right: dict) -> None:
    fields = ["n", "fold", "seed", "init_param_sha", "batch_order_sha",
              "network_sha", "scaler_sha", "train_rows_sha", "val_rows_sha",
              "test_rows_sha", "split_strategy"]
    for field in fields:
        if left.get(field) != right.get(field):
            raise RuntimeError(
                f"pairing mismatch {field}: {left.get(field)!r} != "
                f"{right.get(field)!r}")


def _save_result(result: dict, budget: dict) -> None:
    meta = dict(result["meta"])
    fit = meta["fit_id"]
    pred = result["predictions"]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)
    keys = pred["keys"]
    path = EVIDENCE / f"{fit}.npz"
    np.savez_compressed(
        path,
        keys_beta=np.ascontiguousarray(keys[:, 0], dtype=np.float64),
        keys_gamma_over_eta=np.ascontiguousarray(keys[:, 1], dtype=np.float64),
        keys_n=np.ascontiguousarray(keys[:, 2], dtype=np.int32),
        keys_repeat_id=np.ascontiguousarray(keys[:, 3], dtype=np.int32),
        beta_hat=np.asarray(pred["beta_hat"], dtype=np.float32),
        eta_hat=np.asarray(pred["eta_hat"], dtype=np.float32),
        gamma_hat=np.asarray(pred["gamma_hat"], dtype=np.float32),
        x95_hat=np.asarray(pred["x95_hat"], dtype=np.float32),
        x95_true=np.asarray(pred["x95_true"], dtype=np.float32),
        min_x=np.asarray(pred["min_x"], dtype=np.float32),
        rel_err=np.asarray(pred["rel_err"], dtype=np.float32),
        rel_err_sq=np.asarray(pred["rel_err_sq"], dtype=np.float32),
    )
    meta["sensitivity_budget"] = dict(budget)
    meta["evidence_level"] = "post-test equal-budget sensitivity"
    meta["evidence_sha256"] = _sha(path)
    _json(METADATA / f"{fit}.json", meta)


def run(cfg: dict, *, resume: bool = True,
        selected_seeds: set[int] | None = None,
        selected_routes: set[str] | None = None) -> None:
    master = DATA.build_master()
    budget = cfg["common_budget"]
    routes = TRAINED_ROUTES if selected_routes is None else tuple(
        route for route in TRAINED_ROUTES if route in selected_routes)
    for seed in cfg["design"]["seeds"]:
        if selected_seeds is not None and int(seed) not in selected_seeds:
            continue
        for n in cfg["design"]["n_grid"]:
            for fold in cfg["design"]["folds_1based"]:
                qcp_meta_path, qcp_ev_path = _paths(
                    QCP_ROOT, int(n), int(fold), int(seed), "QCP")
                qcp_meta = _load_meta(qcp_meta_path)
                if not qcp_ev_path.exists():
                    raise FileNotFoundError(qcp_ev_path)
                if not qcp_meta.get("constraint_feasible_at_checkpoint", False):
                    raise RuntimeError(f"infeasible reused QCP checkpoint: {qcp_meta_path.name}")
                for route in routes:
                    fit = _fit_name(int(n), int(fold), int(seed), route)
                    meta_path = METADATA / f"{fit}.json"
                    ev_path = EVIDENCE / f"{fit}.npz"
                    if resume and meta_path.exists() and ev_path.exists():
                        meta = _load_meta(meta_path)
                        if meta.get("evidence_sha256") == _sha(ev_path):
                            print(f"[resume] {fit}", flush=True)
                            continue
                    result = TR.train_one_fit(
                        int(n), int(fold) - 1, int(seed), route, master,
                        max_epochs=int(budget["max_epochs"]),
                        patience=int(budget["patience"]),
                        split_strategy="repeat_stratified",
                        lambda_p=(float(cfg["frozen_route_settings"]["QP"]["lambda_p"])
                                  if route == "QP" else None),
                        fit_suffix="", record_history=False, evaluate_test=True,
                    )
                    meta = result["meta"]
                    _validate_pair(meta, qcp_meta)
                    _save_result(result, budget)
                    print(f"[fit] {fit}: epoch={meta['best_epoch']} "
                          f"stop={meta['stopped_epoch']} "
                          f"test_rrmse={meta['rrmse_x95']:.6f}", flush=True)


def _load_evidence(n: int, fold: int, seed: int,
                   route: str) -> dict[str, np.ndarray]:
    root = QCP_ROOT if route == "QCP" else OUT
    _, path = _paths(root, n, fold, seed, route)
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path) as z:
        values = {name: np.asarray(z[name]) for name in z.files}
    if "keys_repeat_id" not in values and "keys_point_or_repeat_id" in values:
        values["keys_repeat_id"] = values["keys_point_or_repeat_id"]
    return values


def _route_meta(n: int, fold: int, seed: int, route: str) -> dict:
    root = QCP_ROOT if route == "QCP" else OUT
    path, _ = _paths(root, n, fold, seed, route)
    return _load_meta(path)


def analyze(cfg: dict) -> dict:
    ns = list(map(int, cfg["design"]["n_grid"]))
    folds = list(map(int, cfg["design"]["folds_1based"]))
    seeds = list(map(int, cfg["design"]["seeds"]))
    sum_sq = {route: 0.0 for route in ALL_ROUTES}
    count = {route: 0 for route in ALL_ROUTES}
    rel_errors = {route: [] for route in ALL_ROUTES}
    parameter_loss_sum = {route: 0.0 for route in ALL_ROUTES}
    cancellation_sum = {route: 0.0 for route in ALL_ROUTES}
    model_mse = {
        route: np.empty((len(ns), len(folds), len(seeds)))
        for route in ALL_ROUTES
    }
    resource_rows = {route: [] for route in ALL_ROUTES}
    rows = []
    feasible_count = 0
    for ni, n in enumerate(ns):
        for fi, fold in enumerate(folds):
            for si, seed in enumerate(seeds):
                loaded = {
                    route: _load_evidence(n, fold, seed, route)
                    for route in ALL_ROUTES
                }
                metas = {
                    route: _route_meta(n, fold, seed, route)
                    for route in ALL_ROUTES
                }
                for route in ("P", "Q", "QP"):
                    _validate_pair(metas["QCP"], metas[route])
                feasible_count += int(bool(
                    metas["QCP"].get("constraint_feasible_at_checkpoint")))
                key_fields = (
                    "keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id")
                for field in key_fields:
                    if any(not np.array_equal(
                            loaded["QCP"][field], loaded[route][field])
                           for route in ("P", "Q", "QP")):
                        raise RuntimeError(
                            f"held-out key mismatch {n=} {fold=} {seed=} {field}")
                row = {"n": n, "fold": fold, "seed": seed}
                for route in ALL_ROUTES:
                    sq = np.asarray(loaded[route]["rel_err_sq"], dtype=np.float64)
                    rel = np.asarray(loaded[route]["rel_err"], dtype=np.float64)
                    if not np.isfinite(sq).all():
                        raise RuntimeError(
                            f"nonfinite evidence {route} {n=} {fold=} {seed=}")
                    mse = float(sq.mean())
                    model_mse[route][ni, fi, si] = mse
                    sum_sq[route] += float(sq.sum())
                    count[route] += int(sq.size)
                    rel_errors[route].append(rel)
                    beta = np.asarray(loaded[route]["keys_beta"], dtype=np.float64)
                    eta = np.full_like(beta, 1000.0)
                    gamma = np.asarray(
                        loaded[route]["keys_gamma_over_eta"], dtype=np.float64) * 1000.0
                    b_hat = np.asarray(loaded[route]["beta_hat"], dtype=np.float64)
                    e_hat = np.asarray(loaded[route]["eta_hat"], dtype=np.float64)
                    g_hat = np.asarray(loaded[route]["gamma_hat"], dtype=np.float64)
                    p_loss = ((b_hat - beta) / beta) ** 2 + \
                        ((e_hat - eta) / eta) ** 2 + ((g_hat - gamma) / eta) ** 2
                    parameter_loss_sum[route] += float(p_loss.sum())
                    a = -np.log(0.95)
                    t0 = a ** (1.0 / beta)
                    t1 = a ** (1.0 / b_hat)
                    x = gamma + eta * t0
                    components = (
                        0.5 * (eta + e_hat) * (t1 - t0) / x,
                        0.5 * (e_hat - eta) * (t0 + t1) / x,
                        (g_hat - gamma) / x,
                    )
                    magnitude = sum(np.abs(component) for component in components)
                    signed = sum(components)
                    cancellation = np.divide(
                        magnitude - np.abs(signed), magnitude,
                        out=np.zeros_like(magnitude), where=magnitude > 0.0)
                    cancellation_sum[route] += float(cancellation.sum())
                    row[f"mse_{route.lower()}"] = mse
                    resource_rows[route].append({
                        "best_epoch": int(metas[route]["best_epoch"]),
                        "stopped_epoch": int(metas[route]["stopped_epoch"]),
                        "runtime_s": float(metas[route]["runtime_s"]),
                    })
                rows.append(row)

    expected = len(ns) * len(folds) * len(seeds)
    if feasible_count != expected:
        raise RuntimeError(
            f"expected {expected} feasible QCP checkpoints, got {feasible_count}")
    pooled = {
        route: float(np.sqrt(sum_sq[route] / count[route]))
        for route in ALL_ROUTES
    }
    flat_rel = {
        route: np.concatenate(rel_errors[route]) for route in ALL_ROUTES
    }
    diagnostics = {}
    resource_diagnostics = {}
    ceiling = int(cfg["common_budget"]["max_epochs"])
    for route in ALL_ROUTES:
        rel = flat_rel[route]
        absolute = np.abs(rel)
        tail_cut = np.quantile(absolute, 0.90)
        diagnostics[route] = {
            "mae": float(absolute.mean()),
            "median_absolute_error": float(np.median(absolute)),
            "within_10pct": float(np.mean(absolute <= 0.10)),
            "overestimate_gt_10pct": float(np.mean(rel > 0.10)),
            "underestimate_gt_10pct": float(np.mean(rel < -0.10)),
            "signed_bias": float(rel.mean()),
            "q95_absolute_error": float(np.quantile(absolute, 0.95)),
            "global_cvar90_absolute_error":
                float(absolute[absolute >= tail_cut].mean()),
            "mean_parameter_loss": float(parameter_loss_sum[route] / count[route]),
            "mean_exact_cancellation_index":
                float(cancellation_sum[route] / count[route]),
        }
        best = np.asarray(
            [item["best_epoch"] for item in resource_rows[route]], dtype=float)
        stopped = np.asarray(
            [item["stopped_epoch"] for item in resource_rows[route]], dtype=float)
        runtime = np.asarray(
            [item["runtime_s"] for item in resource_rows[route]], dtype=float)
        resource_diagnostics[route] = {
            "best_epoch_median": float(np.median(best)),
            "best_epoch_p90": float(np.quantile(best, 0.90)),
            "best_epoch_max": int(best.max()),
            "stopped_at_600_count": int(np.sum(stopped >= ceiling)),
            "runtime_s_sum": float(runtime.sum()),
            "runtime_s_median": float(np.median(runtime)),
        }

    contrasts = {}
    contrast_pairs = (
        ("QCP", "QP"), ("QCP", "Q"), ("QCP", "P"),
        ("QP", "Q"), ("QP", "P"),
    )
    replicates = int(cfg["bootstrap"]["replicates"])
    boot_seed = int(cfg["bootstrap"]["seed"])
    for offset, (target, comparator) in enumerate(contrast_pairs):
        diff = model_mse[target] - model_mse[comparator]
        boot = QCP_CONFIRM.crossed_bootstrap_contrast(
            model_mse[target], model_mse[comparator],
            replicates=replicates, seed=boot_seed + offset)
        seed_means = diff.mean(axis=(0, 1))
        contrasts[f"{target}_minus_{comparator}"] = {
            "mean_mse_difference": float(diff.mean()),
            "mse_difference_95ci": boot["mse_difference_95ci"],
            "relative_rrmse_improvement":
                float((pooled[comparator] - pooled[target]) / pooled[comparator]),
            "relative_rrmse_improvement_95ci":
                boot["relative_rrmse_improvement_95ci"],
            "favorable_model_cells": int(np.sum(diff < 0.0)),
            "total_model_cells": int(diff.size),
            "favorable_seeds": int(np.sum(seed_means < 0.0)),
            "total_seeds": int(seed_means.size),
        }

    primary = contrasts["QCP_minus_QP"]
    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "evidence_level": cfg["evidence_level"],
        "common_budget": cfg["common_budget"],
        "n_new_fits": expected * len(TRAINED_ROUTES),
        "n_reused_qcp_fits": expected,
        "n_test_rows_per_route": count["QCP"],
        "constraint_feasible_checkpoints": feasible_count,
        "pooled_rrmse": pooled,
        "diagnostics": diagnostics,
        "resource_diagnostics": resource_diagnostics,
        "contrasts": contrasts,
        "primary_sensitivity_direction_favors_qcp":
            bool(primary["mean_mse_difference"] < 0.0),
        "primary_sensitivity_interval_below_zero":
            bool(primary["mse_difference_95ci"][1] < 0.0),
        "decision": "POST_TEST_EQUAL_BUDGET_SENSITIVITY_COMPLETE",
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _json(ANALYSIS / "summary.json", summary)
    with (ANALYSIS / "model_cells.csv").open(
            "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return summary


def write_manifest(cfg: dict) -> None:
    expected = len(cfg["design"]["n_grid"]) * \
        len(cfg["design"]["folds_1based"]) * len(cfg["design"]["seeds"])
    evidence = sorted(EVIDENCE.glob("*.npz"))
    metadata = sorted(METADATA.glob("*.json"))
    expected_new = expected * len(TRAINED_ROUTES)
    if len(evidence) != expected_new or len(metadata) != expected_new:
        raise RuntimeError(
            f"expected {expected_new} new fits, got {len(evidence)}/{len(metadata)}")
    for meta_path in metadata:
        meta = _load_meta(meta_path)
        ev_path = EVIDENCE / f"{meta_path.stem}.npz"
        if not ev_path.exists() or meta.get("evidence_sha256") != _sha(ev_path):
            raise RuntimeError(f"evidence hash mismatch {ev_path.name}")
    qcp_config = json.loads(QCP_CONFIG.read_text(encoding="utf-8"))
    if qcp_config.get("selected_budget") != cfg.get("common_budget"):
        raise RuntimeError("reused QCP budget does not match common budget")
    qcp_evidence = sorted((QCP_ROOT / "evidence").glob("*.npz"))
    qcp_metadata = sorted((QCP_ROOT / "fit_metadata").glob("*.json"))
    if len(qcp_evidence) != expected or len(qcp_metadata) != expected:
        raise RuntimeError("reused QCP artifact is incomplete")
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip()
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "evidence_level": cfg["evidence_level"],
        "git_head_at_manifest": git_head,
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
        "qcp_source_config_sha256": _sha(QCP_CONFIG),
        "new_fit_count": len(evidence),
        "new_fit_count_by_route": {route: expected for route in TRAINED_ROUTES},
        "reused_qcp_fit_count": len(qcp_evidence),
        "common_budget": cfg["common_budget"],
        "test_was_already_open": True,
    }
    _json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(
            f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files)
        + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--seed", action="append", type=int,
                        help="limit training to one or more frozen seeds")
    parser.add_argument("--route", action="append",
                        choices=TRAINED_ROUTES,
                        help="limit training to P, Q, and/or QP")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for equal-budget sensitivity")
    cfg = _cfg()
    selected_seeds = set(args.seed) if args.seed else None
    frozen_seeds = set(map(int, cfg["design"]["seeds"]))
    if selected_seeds is not None and not selected_seeds <= frozen_seeds:
        raise ValueError(
            f"seed outside frozen design: {sorted(selected_seeds - frozen_seeds)}")
    selected_routes = set(args.route) if args.route else None
    if not args.analyze_only:
        run(cfg, resume=not args.no_resume,
            selected_seeds=selected_seeds, selected_routes=selected_routes)
    if args.run_only:
        return
    summary = analyze(cfg)
    write_manifest(cfg)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

