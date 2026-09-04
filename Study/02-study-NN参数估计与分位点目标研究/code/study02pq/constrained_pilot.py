"""Validation-only pilot for Q minimized subject to an adaptive P constraint."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import config as CFG
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "qcp-constrained-pilot-v1.json"
PROTOCOL_PATH = ROOT / "protocols" / "14-Q主任务P约束增广拉格朗日筛选合同.md"
OUT = ROOT / "artifacts" / "qcp_constrained_pilot"
FITS = OUT / "fits"
ANALYSIS = OUT / "analysis"
QP_PILOT = (ROOT / "归档" / "旧实验" / "固定加权路线" / "artifacts" /
            "pq_regularized_pilot" / "fits")


def _json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _label(value: float) -> str:
    return f"{value:g}".replace(".", "p").replace("-", "m")


def _reference(n: int, fold: int, route: str) -> dict:
    if route == "P":
        path = QP_PILOT / "resource" / f"n{n}_f{fold}_s42_rP_baseline.json"
    elif route == "Q":
        path = QP_PILOT / "lambda" / f"n{n}_f{fold}_s42_rQP_lp0_baseline.json"
    elif route == "QP":
        path = QP_PILOT / "lambda" / f"n{n}_f{fold}_s42_rQP_lp1ep00_baseline.json"
    else:
        raise ValueError(route)
    return _load(path)


def _best_history_row(record: dict) -> dict:
    epoch = int(record["meta"]["best_epoch"])
    return next(row for row in record["history"] if int(row["epoch"]) == epoch)


def _assert_pairing(candidate: dict, reference: dict) -> None:
    fields = ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
              "train_rows_sha", "val_rows_sha", "test_rows_sha"]
    for field in fields:
        if candidate["meta"][field] != reference["meta"][field]:
            raise RuntimeError(f"pairing mismatch: {field}")


def run(resume: bool = True) -> dict:
    cfg = _load(CONFIG_PATH)
    design = cfg["screening_design"]
    master = DATA.build_master()
    records = []
    controls = {}
    for n in design["n_grid"]:
        for fold in design["folds_1based"]:
            p_ref = _reference(int(n), int(fold), "P")
            q_ref = _reference(int(n), int(fold), "Q")
            qp_ref = _reference(int(n), int(fold), "QP")
            key = (int(n), int(fold))
            controls[key] = {
                "p_reference_loss": float(p_ref["meta"]["best_val_loss"]),
                "q_validation_loss": float(q_ref["meta"]["best_val_loss"]),
                "qp_validation_loss": float(qp_ref["meta"]["best_val_loss"]),
            }
            for slack in cfg["constraint_grid"]["slack_multipliers"]:
                for rho in cfg["constraint_grid"]["rho_grid"]:
                    slack = float(slack)
                    rho = float(rho)
                    limit = slack * controls[key]["p_reference_loss"]
                    fit = (f"n{n}_f{fold}_s{design['seed']}_rQCP_"
                           f"c{_label(slack)}_rho{_label(rho)}")
                    path = FITS / f"{fit}.json"
                    if resume and path.exists():
                        record = _load(path)
                    else:
                        result = TR.train_one_fit(
                            int(n), int(fold) - 1, int(design["seed"]), "QCP", master,
                            max_epochs=int(design["max_epochs"]),
                            patience=int(design["patience"]),
                            batch_size=int(design["batch_size"]),
                            split_strategy=design["split_strategy"],
                            p_constraint_limit=limit, constraint_rho=rho,
                            fit_suffix=f"_c{_label(slack)}_rho{_label(rho)}",
                            record_history=True, evaluate_test=False,
                        )
                        record = {"meta": result["meta"], "history": result["history"],
                                  "slack_multiplier": slack, "rho": rho}
                        _json(path, record)
                    if record["meta"].get("test_evaluated") is not False:
                        raise RuntimeError("test seal violated")
                    _assert_pairing(record, q_ref)
                    best = _best_history_row(record)
                    records.append({
                        "key": key, "slack": slack, "rho": rho,
                        "record": record, "best": best, "limit": limit,
                    })
                    print(f"{fit}: valQ={record['meta']['best_val_loss']:.8g} "
                          f"valP={best['val_p_loss']:.8g} limit={limit:.8g} "
                          f"mu={best['dual_multiplier']:.6g}", flush=True)

    by_candidate = {}
    q_control_rrmse = math.sqrt(np.mean(
        [item["q_validation_loss"] for item in controls.values()]))
    qp_control_rrmse = math.sqrt(np.mean(
        [item["qp_validation_loss"] for item in controls.values()]))
    candidates = []
    for slack in map(float, cfg["constraint_grid"]["slack_multipliers"]):
        for rho in map(float, cfg["constraint_grid"]["rho_grid"]):
            subset = [row for row in records
                      if row["slack"] == slack and row["rho"] == rho]
            unit_q = {row["key"]: float(row["record"]["meta"]["best_val_loss"])
                      for row in subset}
            unit_p = {row["key"]: float(row["best"]["val_p_loss"])
                      for row in subset}
            rrmse = math.sqrt(np.mean(list(unit_q.values())))
            compliance = sum(unit_p[key] <= row["limit"] + 1e-12
                             for key, row in [(item["key"], item) for item in subset])
            improved = sum(unit_q[key] < controls[key]["q_validation_loss"]
                           for key in unit_q)
            summary = {
                "slack_multiplier": slack,
                "rho": rho,
                "validation_q_rrmse": rrmse,
                "relative_gain_vs_q": (q_control_rrmse - rrmse) / q_control_rrmse,
                "relative_gain_vs_weighted_qp":
                    (qp_control_rrmse - rrmse) / qp_control_rrmse,
                "constraint_compliant_units": compliance,
                "q_improved_units_vs_q": improved,
                "mean_validation_p_loss": float(np.mean(list(unit_p.values()))),
                "mean_constraint_limit": float(np.mean([row["limit"] for row in subset])),
                "best_epochs": [int(row["record"]["meta"]["best_epoch"])
                                for row in subset],
            }
            by_candidate[f"c={slack:g},rho={rho:g}"] = summary
            candidates.append(summary)

    feasible = [item for item in candidates if item["constraint_compliant_units"] >= 7]
    pool = feasible if feasible else candidates
    selected = min(pool, key=lambda item: item["validation_q_rrmse"])
    promising = (selected["relative_gain_vs_q"] >= 0.005 and
                 selected["q_improved_units_vs_q"] >= 6 and
                 selected["constraint_compliant_units"] >= 7)
    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "SCREENING COMPLETE / TEST METRICS SEALED",
        "n_new_fits": len(records),
        "test_metric_access_count": 0,
        "pure_q_validation_rrmse": q_control_rrmse,
        "weighted_qp_validation_rrmse": qp_control_rrmse,
        "by_candidate": by_candidate,
        "selected": selected,
        "advance_to_formal_confirmation": promising,
        "decision": "FORMAL_GATE_OPEN" if promising else "PILOT_ONLY",
    }
    _json(ANALYSIS / "summary.json", summary)
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip()
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "status": summary["status"],
        "git_head_at_manifest": git_head,
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
        "fit_count": len(records),
        "test_metric_access_count": 0,
        "selected": selected,
    }
    _json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}"
                  for path in files) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for constrained_pilot")
    OUT.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(resume=not args.no_resume), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
