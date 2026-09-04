"""Validation-only resource boundary for the selected QCP constraint."""

from __future__ import annotations

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
CONFIG_PATH = ROOT / "configs" / "qcp-constrained-resource-v1.json"
PROTOCOL_PATH = ROOT / "protocols" / "15-Q主任务P约束训练资源边界合同.md"
PILOT = ROOT / "artifacts" / "qcp_constrained_pilot"
P_REF = (ROOT / "归档" / "旧实验" / "固定加权路线" / "artifacts" /
         "pq_regularized_pilot" / "fits" / "resource")
OUT = ROOT / "artifacts" / "qcp_constrained_resource"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _best(record: dict) -> dict:
    epoch = int(record["meta"]["best_epoch"])
    return next(row for row in record["history"] if int(row["epoch"]) == epoch)


def run() -> dict:
    cfg = _load(CONFIG_PATH)
    design = cfg["design"]
    slack = float(cfg["selected_constraint"]["slack_multiplier"])
    rho = float(cfg["selected_constraint"]["rho"])
    master = DATA.build_master()
    baseline = {}
    extended = {}
    for n in design["n_grid"]:
        for fold in design["folds_1based"]:
            key = (int(n), int(fold))
            base_path = PILOT / "fits" / f"n{n}_f{fold}_s42_rQCP_c1p5_rho0p1.json"
            base = _load(base_path)
            baseline[key] = base
            p_ref = _load(P_REF / f"n{n}_f{fold}_s42_rP_baseline.json")
            limit = slack * float(p_ref["meta"]["best_val_loss"])
            result = TR.train_one_fit(
                int(n), int(fold) - 1, int(design["seed"]), "QCP", master,
                max_epochs=int(cfg["extended_budget"]["max_epochs"]),
                patience=int(cfg["extended_budget"]["patience"]),
                batch_size=int(design["batch_size"]),
                split_strategy=design["split_strategy"],
                p_constraint_limit=limit, constraint_rho=rho,
                fit_suffix="_c1p5_rho0p1_extended",
                record_history=True, evaluate_test=False,
            )
            rec = {"meta": result["meta"], "history": result["history"]}
            _json(OUT / "fits" / f"n{n}_f{fold}_s42_rQCP_extended.json", rec)
            extended[key] = rec
            for field in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
                          "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
                if base["meta"][field] != rec["meta"][field]:
                    raise RuntimeError(f"pairing mismatch {key}: {field}")
            print(f"n{n} f{fold}: base={base['meta']['best_val_loss']:.8g} "
                  f"ext={rec['meta']['best_val_loss']:.8g} "
                  f"best/stop={rec['meta']['best_epoch']}/{rec['meta']['stopped_epoch']} "
                  f"feasible={rec['meta']['constraint_feasible_at_checkpoint']}", flush=True)

    base_rrmse = math.sqrt(np.mean([rec["meta"]["best_val_loss"]
                                    for rec in baseline.values()]))
    ext_rrmse = math.sqrt(np.mean([rec["meta"]["best_val_loss"]
                                   for rec in extended.values()]))
    gain = (base_rrmse - ext_rrmse) / base_rrmse
    no_worse = sum(extended[key]["meta"]["best_val_loss"] <=
                   baseline[key]["meta"]["best_val_loss"] for key in baseline)
    base_ceiling = any(rec["meta"]["stopped_epoch"] >= 300 for rec in baseline.values())
    all_feasible = all(rec["meta"]["constraint_feasible_at_checkpoint"]
                       for rec in extended.values())
    choose_extended = all_feasible and (
        (gain >= 0.005 and no_worse >= 6) or (base_ceiling and ext_rrmse < base_rrmse))
    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE / TEST METRICS SEALED",
        "n_new_fits": len(extended),
        "test_metric_access_count": 0,
        "baseline_validation_q_rrmse": base_rrmse,
        "extended_validation_q_rrmse": ext_rrmse,
        "extended_relative_gain": gain,
        "extended_no_worse_units": no_worse,
        "baseline_ceiling_hit": base_ceiling,
        "extended_all_constraints_feasible": all_feasible,
        "selected_budget": "extended" if choose_extended else "baseline",
    }
    _json(OUT / "analysis" / "summary.json", summary)
    manifest = {
        **summary,
        "git_head_at_manifest": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip(),
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
    }
    _json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*")
                   if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}"
                  for path in files) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for constrained_resource")
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
