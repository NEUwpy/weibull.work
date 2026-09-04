"""Formal 10-seed QCP confirmation with immutable comparator evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import config as CFG
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "qcp-constrained-confirm-v1.json"
PROTOCOL_PATH = ROOT / "protocols" / "16-Q主任务P约束正式确认合同.md"
OUT = ROOT / "artifacts" / "qcp_constrained_confirm"
EVIDENCE = OUT / "evidence"
METADATA = OUT / "fit_metadata"
ANALYSIS = OUT / "analysis"
IID = ROOT / "artifacts" / "pq_iid_main"
EXTRA = ROOT / "artifacts" / "pq_s5b_revision" / "grid_extra"
QP = (ROOT / "归档" / "旧实验" / "固定加权路线" / "artifacts" /
      "pq_regularized_confirm")


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


def comparator_root(seed: int) -> Path:
    return IID if int(seed) in {42, 2026, 3407} else EXTRA


def comparator_paths(n: int, fold: int, seed: int, route: str) -> tuple[Path, Path]:
    root = comparator_root(seed)
    fit = _fit_name(n, fold, seed, route)
    return root / "fit_metadata" / f"{fit}.json", root / "evidence" / f"{fit}.npz"


def _save_qcp(result: dict) -> None:
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
    meta["evidence_sha256"] = _sha(path)
    _json(METADATA / f"{fit}.json", meta)


def _load_meta(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def qp_paths(n: int, fold: int, seed: int) -> tuple[Path, Path]:
    fit = _fit_name(n, fold, seed, "QP")
    return QP / "fit_metadata" / f"{fit}.json", QP / "evidence" / f"{fit}.npz"


def _validate_pair(qcp_meta: dict, comparator: dict) -> None:
    fields = ["n", "fold", "seed", "init_param_sha", "batch_order_sha",
              "network_sha", "scaler_sha", "train_rows_sha", "val_rows_sha",
              "test_rows_sha", "split_strategy"]
    for field in fields:
        if qcp_meta.get(field) != comparator.get(field):
            raise RuntimeError(
                f"pairing mismatch {field}: QCP={qcp_meta.get(field)!r}, "
                f"comparator={comparator.get(field)!r}")


def run(cfg: dict, resume: bool = True,
        selected_seeds: set[int] | None = None) -> None:
    master = DATA.build_master()
    slack = float(cfg["selected_constraint"]["slack_multiplier"])
    rho = float(cfg["selected_constraint"]["rho"])
    budget = cfg["selected_budget"]
    for seed in cfg["design"]["seeds"]:
        if selected_seeds is not None and int(seed) not in selected_seeds:
            continue
        for n in cfg["design"]["n_grid"]:
            for fold in cfg["design"]["folds_1based"]:
                fit = _fit_name(n, fold, seed, "QCP")
                meta_path = METADATA / f"{fit}.json"
                ev_path = EVIDENCE / f"{fit}.npz"
                if resume and meta_path.exists() and ev_path.exists():
                    meta = _load_meta(meta_path)
                    if meta.get("evidence_sha256") == _sha(ev_path):
                        print(f"[resume] {fit}", flush=True)
                        continue
                p_meta_path, p_ev_path = comparator_paths(
                    int(n), int(fold), int(seed), "P")
                p_meta = _load_meta(p_meta_path)
                p_limit = slack * float(p_meta["best_val_loss"])
                result = TR.train_one_fit(
                    int(n), int(fold) - 1, int(seed), "QCP", master,
                    max_epochs=int(budget["max_epochs"]),
                    patience=int(budget["patience"]),
                    split_strategy="repeat_stratified",
                    p_constraint_limit=p_limit, constraint_rho=rho,
                    fit_suffix="", record_history=False, evaluate_test=True,
                )
                qcp = result["meta"]
                for route in ("P", "Q"):
                    comparator_meta, comparator_ev = comparator_paths(
                        int(n), int(fold), int(seed), route)
                    _validate_pair(qcp, _load_meta(comparator_meta))
                    if not comparator_ev.exists():
                        raise FileNotFoundError(comparator_ev)
                qp_meta_path, qp_ev_path = qp_paths(int(n), int(fold), int(seed))
                _validate_pair(qcp, _load_meta(qp_meta_path))
                if not qp_ev_path.exists() or not p_ev_path.exists():
                    raise FileNotFoundError(qp_ev_path if not qp_ev_path.exists() else p_ev_path)
                if not qcp.get("constraint_feasible_at_checkpoint", False):
                    raise RuntimeError(f"infeasible QCP checkpoint: {fit}")
                _save_qcp(result)
                print(f"[fit] {fit}: epoch={qcp['best_epoch']} "
                      f"test_rrmse={qcp['rrmse_x95']:.6f} "
                      f"val_p={qcp['best_val_p_loss']:.6g}/{p_limit:.6g}", flush=True)


def _load_evidence(n: int, fold: int, seed: int, route: str) -> dict[str, np.ndarray]:
    if route == "QCP":
        path = EVIDENCE / f"{_fit_name(n, fold, seed, route)}.npz"
    elif route == "QP":
        _, path = qp_paths(n, fold, seed)
    else:
        _, path = comparator_paths(n, fold, seed, route)
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path) as z:
        values = {name: np.asarray(z[name]) for name in z.files}
    # S5B kept a shared grid/continuous schema name although grid_extra stores
    # repeat ids.  Normalize the read-only alias without rewriting sealed evidence.
    if "keys_repeat_id" not in values and "keys_point_or_repeat_id" in values:
        values["keys_repeat_id"] = values["keys_point_or_repeat_id"]
    return values


def crossed_bootstrap(diff: np.ndarray, *, replicates: int, seed: int) -> tuple[float, float]:
    """Bootstrap a ``[n, fold, seed]`` paired mean-difference cube."""
    if diff.ndim != 3:
        raise ValueError("diff must have shape [n, fold, seed]")
    n_count, fold_count, seed_count = diff.shape
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=np.float64)
    chunk = 2000
    for start in range(0, replicates, chunk):
        size = min(chunk, replicates - start)
        seed_idx = rng.integers(0, seed_count, size=(size, seed_count))
        values = np.zeros(size, dtype=np.float64)
        for ni in range(n_count):
            fold_idx = rng.integers(0, fold_count, size=(size, fold_count))
            sampled = diff[ni][fold_idx[:, :, None], seed_idx[:, None, :]]
            values += sampled.mean(axis=(1, 2)) / n_count
        draws[start:start + size] = values
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return float(lo), float(hi)


def crossed_bootstrap_contrast(target: np.ndarray, comparator: np.ndarray, *,
                               replicates: int, seed: int) -> dict[str, list[float]]:
    """Paired CIs for MSE difference and relative rRMSE improvement."""
    if target.shape != comparator.shape or target.ndim != 3:
        raise ValueError("target and comparator must share shape [n, fold, seed]")
    n_count, fold_count, seed_count = target.shape
    rng = np.random.default_rng(seed)
    mse_diff = np.empty(replicates, dtype=np.float64)
    relative = np.empty(replicates, dtype=np.float64)
    chunk = 2000
    for start in range(0, replicates, chunk):
        size = min(chunk, replicates - start)
        seed_idx = rng.integers(0, seed_count, size=(size, seed_count))
        target_mean = np.zeros(size, dtype=np.float64)
        comparator_mean = np.zeros(size, dtype=np.float64)
        for ni in range(n_count):
            fold_idx = rng.integers(0, fold_count, size=(size, fold_count))
            target_sample = target[ni][fold_idx[:, :, None], seed_idx[:, None, :]]
            comparator_sample = comparator[ni][fold_idx[:, :, None], seed_idx[:, None, :]]
            target_mean += target_sample.mean(axis=(1, 2)) / n_count
            comparator_mean += comparator_sample.mean(axis=(1, 2)) / n_count
        mse_diff[start:start + size] = target_mean - comparator_mean
        relative[start:start + size] = \
            (np.sqrt(comparator_mean) - np.sqrt(target_mean)) / np.sqrt(comparator_mean)
    return {
        "mse_difference_95ci": np.quantile(mse_diff, [0.025, 0.975]).tolist(),
        "relative_rrmse_improvement_95ci":
            np.quantile(relative, [0.025, 0.975]).tolist(),
    }


def analyze(cfg: dict) -> dict:
    ns = list(map(int, cfg["design"]["n_grid"]))
    folds = list(map(int, cfg["design"]["folds_1based"]))
    seeds = list(map(int, cfg["design"]["seeds"]))
    routes = ("P", "Q", "QP", "QCP")
    sum_sq = {route: 0.0 for route in routes}
    count = {route: 0 for route in routes}
    rel_errors = {route: [] for route in routes}
    parameter_loss_sum = {route: 0.0 for route in routes}
    cancellation_sum = {route: 0.0 for route in routes}
    model_mse = {route: np.empty((len(ns), len(folds), len(seeds))) for route in routes}
    rows = []
    feasible_count = 0
    for ni, n in enumerate(ns):
        for fi, fold in enumerate(folds):
            for si, seed in enumerate(seeds):
                loaded = {route: _load_evidence(n, fold, seed, route) for route in routes}
                qcp_meta = _load_meta(
                    METADATA / f"{_fit_name(n, fold, seed, 'QCP')}.json")
                feasible_count += int(bool(qcp_meta.get("constraint_feasible_at_checkpoint")))
                key_fields = ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id")
                for field in key_fields:
                    if any(not np.array_equal(loaded["QCP"][field], loaded[route][field])
                           for route in ("P", "Q", "QP")):
                        raise RuntimeError(f"held-out key mismatch {n=} {fold=} {seed=} {field}")
                row = {"n": n, "fold": fold, "seed": seed}
                for route in routes:
                    sq = np.asarray(loaded[route]["rel_err_sq"], dtype=np.float64)
                    rel = np.asarray(loaded[route]["rel_err"], dtype=np.float64)
                    if not np.isfinite(sq).all():
                        raise RuntimeError(f"nonfinite evidence {route} {n=} {fold=} {seed=}")
                    mse = float(sq.mean())
                    model_mse[route][ni, fi, si] = mse
                    sum_sq[route] += float(sq.sum())
                    count[route] += int(sq.size)
                    rel_errors[route].append(rel)
                    beta = np.asarray(loaded[route]["keys_beta"], dtype=np.float64)
                    eta = np.full_like(beta, 1000.0)
                    gamma = np.asarray(loaded[route]["keys_gamma_over_eta"],
                                       dtype=np.float64) * 1000.0
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
                    c_gamma = (g_hat - gamma) / x
                    c_eta = 0.5 * (e_hat - eta) * (t0 + t1) / x
                    c_beta = 0.5 * (eta + e_hat) * (t1 - t0) / x
                    magnitude = np.abs(c_beta) + np.abs(c_eta) + np.abs(c_gamma)
                    cancellation = np.divide(
                        magnitude - np.abs(c_beta + c_eta + c_gamma), magnitude,
                        out=np.zeros_like(magnitude), where=magnitude > 0.0)
                    cancellation_sum[route] += float(cancellation.sum())
                    row[f"mse_{route.lower()}"] = mse
                rows.append(row)

    pooled = {route: float(np.sqrt(sum_sq[route] / count[route])) for route in routes}
    flat_rel = {route: np.concatenate(rel_errors[route]) for route in routes}
    diagnostics = {}
    for route in routes:
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
            "global_cvar90_absolute_error": float(absolute[absolute >= tail_cut].mean()),
            "mean_parameter_loss": float(parameter_loss_sum[route] / count[route]),
            "mean_exact_cancellation_index":
                float(cancellation_sum[route] / count[route]),
        }
    paired_win_rates = {
        "QCP_abs_error_better_than_QP":
            float(np.mean(np.abs(flat_rel["QCP"]) < np.abs(flat_rel["QP"]))),
        "QCP_abs_error_better_than_Q":
            float(np.mean(np.abs(flat_rel["QCP"]) < np.abs(flat_rel["Q"]))),
        "QCP_abs_error_better_than_P":
            float(np.mean(np.abs(flat_rel["QCP"]) < np.abs(flat_rel["P"]))),
    }
    contrasts = {}
    b = int(cfg["bootstrap"]["replicates"])
    boot_seed = int(cfg["bootstrap"]["seed"])
    for offset, comparator in enumerate(("QP", "Q", "P")):
        diff = model_mse["QCP"] - model_mse[comparator]
        boot = crossed_bootstrap_contrast(
            model_mse["QCP"], model_mse[comparator],
            replicates=b, seed=boot_seed + offset)
        seed_means = diff.mean(axis=(0, 1))
        contrasts[f"QCP_minus_{comparator}"] = {
            "mean_mse_difference": float(diff.mean()),
            "design_bootstrap_95ci": boot["mse_difference_95ci"],
            "relative_rrmse_improvement":
                float((pooled[comparator] - pooled["QCP"]) / pooled[comparator]),
            "relative_rrmse_improvement_95ci":
                boot["relative_rrmse_improvement_95ci"],
            "favorable_model_cells": int(np.sum(diff < 0.0)),
            "total_model_cells": int(diff.size),
            "favorable_seeds": int(np.sum(seed_means < 0.0)),
            "total_seeds": int(seed_means.size),
            "passes": bool(boot["mse_difference_95ci"][1] < 0.0),
        }
    expected = len(ns) * len(folds) * len(seeds)
    success = feasible_count == expected and \
        contrasts["QCP_minus_Q"]["passes"] and \
        contrasts["QCP_minus_QP"]["passes"]
    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "n_qcp_fits": len(rows),
        "n_test_rows_per_route": count["QCP"],
        "constraint_feasible_checkpoints": feasible_count,
        "constraint_total_checkpoints": expected,
        "pooled_rrmse": pooled,
        "diagnostics": diagnostics,
        "paired_win_rates": paired_win_rates,
        "contrasts": contrasts,
        "co_primary_success": success,
        "decision": "QCP_CONFIRMED" if success else "QCP_NOT_CONFIRMED",
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _json(ANALYSIS / "summary.json", summary)
    with (ANALYSIS / "model_cells.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return summary


def write_manifest(cfg: dict) -> None:
    expected = len(cfg["design"]["n_grid"]) * len(cfg["design"]["folds_1based"]) * \
        len(cfg["design"]["seeds"])
    evidence = sorted(EVIDENCE.glob("*.npz"))
    metadata = sorted(METADATA.glob("*.json"))
    if len(evidence) != expected or len(metadata) != expected:
        raise RuntimeError(f"expected {expected} QCP fits, got {len(evidence)}/{len(metadata)}")
    for meta_path, ev_path in zip(metadata, evidence):
        meta = _load_meta(meta_path)
        if meta.get("evidence_sha256") != _sha(ev_path):
            raise RuntimeError(f"evidence hash mismatch {ev_path.name}")
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip()
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "git_head_at_manifest": git_head,
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
        "qcp_fit_count": len(evidence),
        "comparator_fit_count_reused": expected * 3,
        "selected_constraint": cfg["selected_constraint"],
        "selected_budget": cfg["selected_budget"],
    }
    _json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files)
        + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--seed", action="append", type=int,
                        help="limit training to one or more frozen seeds")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for constrained confirmation")
    cfg = _cfg()
    if not args.analyze_only:
        selected = set(args.seed) if args.seed else None
        frozen = set(map(int, cfg["design"]["seeds"]))
        if selected is not None and not selected <= frozen:
            raise ValueError(f"seed outside frozen design: {sorted(selected - frozen)}")
        run(cfg, resume=not args.no_resume, selected_seeds=selected)
    if args.run_only:
        return
    summary = analyze(cfg)
    write_manifest(cfg)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
