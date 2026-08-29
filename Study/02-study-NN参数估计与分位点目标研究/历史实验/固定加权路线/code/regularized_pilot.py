"""Validation-only screening for Study02 Q + lambda*P.

The screening has two sequential gates:
1. compare the frozen 300/20 budget with a 600/60 extension using P and Q;
2. screen lambda_p under the selected common budget.

No candidate evaluates the test split.  A separate frozen confirmation is required
before any test comparison or paper claim.

Run from ``Study/02-.../code`` with ``PQ_PROTOCOL=iid-v1``::

    python -m study02pq.regularized_pilot --stage resource
    python -m study02pq.regularized_pilot --stage lambda
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np

from . import config as CFG
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "pq-regularized-pilot-v1.json"
OUT = ROOT / "artifacts" / "pq_regularized_pilot"
FITS = OUT / "fits"
ANALYSIS = OUT / "analysis"
PROTOCOL_PATH = ROOT / "protocols" / "12-PQ辅助参数约束与训练边界合同.md"


def _read_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _lambda_label(value: float) -> str:
    if value == 0.0:
        return "0"
    return f"{value:.0e}".replace("-", "m").replace("+", "p")


def _fit_path(stage: str, fit_name: str) -> Path:
    return FITS / stage / f"{fit_name}.json"


def _run_or_load(*, stage: str, fit_name: str, resume: bool, kwargs: dict) -> dict:
    path = _fit_path(stage, fit_name)
    if resume and path.exists():
        return _load_json(path)
    result = TR.train_one_fit(
        **kwargs, record_history=True, evaluate_test=False)
    if result["meta"]["test_evaluated"] or "predictions" in result:
        raise RuntimeError("screening contract violation: test output was produced")
    if not result["meta"]["converged"] or result["meta"]["nan_flag"]:
        raise RuntimeError(f"screening fit failed: {fit_name}")
    serializable = {"meta": result["meta"], "history": result["history"]}
    _json(path, serializable)
    return serializable


def _assert_pairing(records: list[dict], grouping: tuple[str, ...]) -> None:
    pairing_keys = ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
                    "train_rows_sha", "val_rows_sha", "test_rows_sha"]
    groups: dict[tuple, list[dict]] = {}
    for record in records:
        meta = record["meta"]
        key = tuple(meta[name] for name in grouping)
        groups.setdefault(key, []).append(meta)
    for key, metas in groups.items():
        for field in pairing_keys:
            if len({meta[field] for meta in metas}) != 1:
                raise RuntimeError(f"pairing mismatch {field} in group {key}")


def _pooled_validation_rrmse(records: list[dict]) -> float:
    losses = [float(record["meta"]["best_val_loss"]) for record in records]
    if not losses or not np.isfinite(losses).all():
        raise RuntimeError("non-finite or empty validation losses")
    return float(math.sqrt(np.mean(losses)))


def _write_integrity_manifest(cfg: dict) -> None:
    resource_path = ANALYSIS / "resource_summary.json"
    lambda_path = ANALYSIS / "lambda_summary.json"
    resource = _load_json(resource_path) if resource_path.exists() else None
    lambda_summary = _load_json(lambda_path) if lambda_path.exists() else None
    fit_files = sorted((FITS / "resource").glob("*.json")) + \
        sorted((FITS / "lambda").glob("*.json"))
    violations = []
    for path in fit_files:
        value = _load_json(path)
        meta = value.get("meta", {})
        if meta.get("test_evaluated") is not False or "predictions" in value or \
                "rrmse_x95" in meta:
            violations.append(path.name)
    if violations:
        raise RuntimeError(f"test-seal violations: {violations}")
    try:
        git_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "status": "SCREENING COMPLETE / TEST METRICS SEALED" if lambda_summary else
                  "RESOURCE GATE COMPLETE",
        "git_head_at_manifest": git_head,
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
        "fit_counts": {
            "resource": len(list((FITS / "resource").glob("*.json"))),
            "lambda": len(list((FITS / "lambda").glob("*.json"))),
            "total": len(fit_files),
        },
        "test_metric_access_count": 0,
        "test_predictions_saved": 0,
        "seal_violations": violations,
        "selected_budget": resource.get("selected_budget") if resource else None,
        "selected_lambda_p": lambda_summary.get("selected_lambda_p")
                             if lambda_summary else None,
        "advance_to_formal_confirmation":
            lambda_summary.get("advance_to_formal_confirmation")
            if lambda_summary else None,
    }
    _json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    lines = [f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_resource(master: DATA.Master, cfg: dict, resume: bool) -> dict:
    design = cfg["screening_design"]
    records = []
    for budget in cfg["resource_gate"]["budgets"]:
        for n in design["n_grid"]:
            for fold in design["folds_1based"]:
                for route in cfg["resource_gate"]["routes"]:
                    fit_name = f"n{n}_f{fold}_s{design['seed']}_r{route}_{budget['id']}"
                    record = _run_or_load(
                        stage="resource", fit_name=fit_name, resume=resume,
                        kwargs=dict(
                            n=int(n), fold_idx=int(fold) - 1, seed=int(design["seed"]),
                            route=route, master=master,
                            max_epochs=int(budget["max_epochs"]),
                            patience=int(budget["patience"]),
                            split_strategy="repeat_stratified",
                            fit_suffix=f"_{budget['id']}",
                        ),
                    )
                    record["budget_id"] = budget["id"]
                    records.append(record)
                    print(f"resource {fit_name}: best={record['meta']['best_epoch']} "
                          f"stop={record['meta']['stopped_epoch']} "
                          f"val={record['meta']['best_val_loss']:.8g}", flush=True)

    _assert_pairing(records, grouping=("n", "fold", "seed", "split_strategy"))
    by_budget = {}
    q_units = {}
    for budget in cfg["resource_gate"]["budgets"]:
        bid = budget["id"]
        route_summary = {}
        for route in cfg["resource_gate"]["routes"]:
            selected = [r for r in records
                        if r["budget_id"] == bid and r["meta"]["route"] == route]
            route_summary[route] = {
                "validation_rrmse": _pooled_validation_rrmse(selected),
                "best_epochs": [r["meta"]["best_epoch"] for r in selected],
                "stopped_epochs": [r["meta"]["stopped_epoch"] for r in selected],
                "ceiling_hits": sum(
                    r["meta"]["stopped_epoch"] >= int(budget["max_epochs"])
                    for r in selected),
            }
            if route == "Q":
                q_units[bid] = {
                    (r["meta"]["n"], r["meta"]["fold"]): r["meta"]["best_val_loss"]
                    for r in selected
                }
        by_budget[bid] = route_summary

    base = by_budget["baseline"]["Q"]["validation_rrmse"]
    ext = by_budget["extended"]["Q"]["validation_rrmse"]
    gain = (base - ext) / base
    no_worse = sum(q_units["extended"][key] <= q_units["baseline"][key]
                   for key in q_units["baseline"])
    ceiling_hit = by_budget["baseline"]["Q"]["ceiling_hits"] > 0
    choose_extended = (gain >= 0.005 and no_worse >= 6) or (ceiling_hit and ext < base)
    chosen = "extended" if choose_extended else "baseline"
    summary = {
        "protocol_id": cfg["protocol_id"],
        "stage": "resource_gate",
        "config_sha256": _sha(CONFIG_PATH),
        "test_access_count": 0,
        "n_fits": len(records),
        "by_budget": by_budget,
        "q_extended_relative_validation_rrmse_gain": gain,
        "q_extended_no_worse_units": no_worse,
        "q_baseline_ceiling_hit": ceiling_hit,
        "selected_budget": chosen,
        "decision": "advance_to_lambda_gate",
    }
    _json(ANALYSIS / "resource_summary.json", summary)
    return summary


def run_lambda(master: DATA.Master, cfg: dict, resume: bool) -> dict:
    resource_path = ANALYSIS / "resource_summary.json"
    if not resource_path.exists():
        raise RuntimeError("resource gate must complete before lambda screening")
    resource = _load_json(resource_path)
    budget_id = resource["selected_budget"]
    budget = next(item for item in cfg["resource_gate"]["budgets"]
                  if item["id"] == budget_id)
    design = cfg["screening_design"]
    records = []
    for lam in cfg["lambda_gate"]["lambda_p_grid"]:
        lam = float(lam)
        label = _lambda_label(lam)
        for n in design["n_grid"]:
            for fold in design["folds_1based"]:
                fit_name = f"n{n}_f{fold}_s{design['seed']}_rQP_lp{label}_{budget_id}"
                record = _run_or_load(
                    stage="lambda", fit_name=fit_name, resume=resume,
                    kwargs=dict(
                        n=int(n), fold_idx=int(fold) - 1, seed=int(design["seed"]),
                        route="QP", master=master,
                        max_epochs=int(budget["max_epochs"]),
                        patience=int(budget["patience"]),
                        split_strategy="repeat_stratified", lambda_p=lam,
                        fit_suffix=f"_lp{label}_{budget_id}",
                    ),
                )
                record["lambda_p"] = lam
                records.append(record)
                print(f"lambda {label} n{n} f{fold}: best={record['meta']['best_epoch']} "
                      f"stop={record['meta']['stopped_epoch']} "
                      f"valQ={record['meta']['best_val_loss']:.8g}", flush=True)

    _assert_pairing(records, grouping=("n", "fold", "seed", "split_strategy"))
    by_lambda = {}
    unit_losses = {}
    for lam in map(float, cfg["lambda_gate"]["lambda_p_grid"]):
        selected = [r for r in records if r["lambda_p"] == lam]
        rrmse = _pooled_validation_rrmse(selected)
        unit_losses[lam] = {
            (r["meta"]["n"], r["meta"]["fold"]): r["meta"]["best_val_loss"]
            for r in selected
        }
        by_lambda[str(lam)] = {
            "validation_rrmse": rrmse,
            "best_epochs": [r["meta"]["best_epoch"] for r in selected],
            "stopped_epochs": [r["meta"]["stopped_epoch"] for r in selected],
        }

    best_rrmse = min(item["validation_rrmse"] for item in by_lambda.values())
    near_best = [lam for lam in unit_losses
                 if by_lambda[str(lam)]["validation_rrmse"] <= best_rrmse * 1.001]
    selected_lambda = min(near_best)
    pure_q = by_lambda["0.0"]["validation_rrmse"]
    selected_rrmse = by_lambda[str(selected_lambda)]["validation_rrmse"]
    gain = (pure_q - selected_rrmse) / pure_q
    improved_units = sum(
        unit_losses[selected_lambda][key] < unit_losses[0.0][key]
        for key in unit_losses[0.0]
    )
    advance = selected_lambda > 0.0 and gain >= 0.005 and improved_units >= 6
    summary = {
        "protocol_id": cfg["protocol_id"],
        "stage": "lambda_gate",
        "config_sha256": _sha(CONFIG_PATH),
        "test_access_count": 0,
        "selected_budget": budget_id,
        "n_fits": len(records),
        "by_lambda": by_lambda,
        "selected_lambda_p": selected_lambda,
        "selected_relative_validation_rrmse_gain_vs_q": gain,
        "selected_improved_units": improved_units,
        "advance_to_formal_confirmation": advance,
        "decision": "mentor_and_user_gate" if advance else "stop_hybrid_route",
    }
    _json(ANALYSIS / "lambda_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("resource", "lambda", "all"),
                        default="all")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for regularized_pilot")
    cfg = _read_config()
    OUT.mkdir(parents=True, exist_ok=True)
    master = DATA.build_master()
    resume = not args.no_resume
    if args.stage in ("resource", "all"):
        resource = run_resource(master, cfg, resume)
        print(json.dumps(resource, ensure_ascii=False, indent=2), flush=True)
    if args.stage in ("lambda", "all"):
        result = run_lambda(master, cfg, resume)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    _write_integrity_manifest(cfg)


if __name__ == "__main__":
    main()
