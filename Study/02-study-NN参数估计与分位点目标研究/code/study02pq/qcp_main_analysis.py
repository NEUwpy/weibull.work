"""Derive the current P/Q/QCP presentation from frozen evidence.

No model is trained here. The output is a post-test sensitivity summary for the
current manuscript narrative, with the original evidence left immutable.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import config as CFG
from . import constrained_confirm as QCP_CONFIRM


ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT / "artifacts" / "qcp_main_analysis"
ANALYSIS = OUT / "analysis"
QCP_ROOT = ROOT / "artifacts" / "qcp_constrained_confirm"
SOURCE_CANDIDATES = (
    ROOT / "artifacts" / "equal_budget_sensitivity",
    ROOT / "历史实验" / "四路线同预算敏感性" / "artifacts" /
    "equal_budget_sensitivity",
)
ROUTES = ("P", "Q", "QCP")


def _source_root() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if (candidate / "analysis" / "summary.json").exists():
            return candidate
    raise FileNotFoundError("frozen common-budget evidence was not found")


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_cells(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _contrast(
    target: np.ndarray,
    comparator: np.ndarray,
    pooled_target: float,
    pooled_comparator: float,
    *,
    replicates: int,
    seed: int,
) -> dict:
    diff = target - comparator
    boot = QCP_CONFIRM.crossed_bootstrap_contrast(
        target, comparator, replicates=replicates, seed=seed
    )
    seed_means = diff.mean(axis=(0, 1))
    return {
        "mean_mse_difference": float(diff.mean()),
        "mse_difference_95ci": boot["mse_difference_95ci"],
        "relative_rrmse_improvement": float(
            (pooled_comparator - pooled_target) / pooled_comparator
        ),
        "relative_rrmse_improvement_95ci":
            boot["relative_rrmse_improvement_95ci"],
        "favorable_model_cells": int(np.sum(diff < 0.0)),
        "total_model_cells": int(diff.size),
        "favorable_seeds": int(np.sum(seed_means < 0.0)),
        "total_seeds": int(seed_means.size),
    }


def _resource_rows(source: Path) -> list[dict]:
    rows: list[dict] = []
    for route in ROUTES:
        root = QCP_ROOT if route == "QCP" else source
        for path in sorted((root / "fit_metadata").glob(f"*_r{route}.json")):
            meta = json.loads(path.read_text(encoding="utf-8"))
            rows.append({
                "n": int(meta["n"]),
                "fold": int(meta["fold"]),
                "seed": int(meta["seed"]),
                "route": route,
                "best_epoch": int(meta["best_epoch"]),
                "stopped_epoch": int(meta["stopped_epoch"]),
                "runtime_s": float(meta["runtime_s"]),
            })
    if len(rows) != 600:
        raise RuntimeError(f"expected 600 resource rows, got {len(rows)}")
    return rows


def main() -> None:
    source = _source_root()
    source_summary_path = source / "analysis" / "summary.json"
    source_cells_path = source / "analysis" / "model_cells.csv"
    source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
    rows = _load_cells(source_cells_path)
    if len(rows) != 200:
        raise RuntimeError(f"expected 200 model cells, got {len(rows)}")
    if source_summary.get("common_budget") != {"max_epochs": 600, "patience": 60}:
        raise RuntimeError("source evidence does not use the frozen 600/60 budget")
    if int(source_summary.get("constraint_feasible_checkpoints", -1)) != 200:
        raise RuntimeError("QCP feasibility count is not 200/200")

    ns = sorted({int(row["n"]) for row in rows})
    folds = sorted({int(row["fold"]) for row in rows})
    seeds = sorted({int(row["seed"]) for row in rows})
    arrays = {
        route: np.empty((len(ns), len(folds), len(seeds)), dtype=np.float64)
        for route in ROUTES
    }
    n_index = {value: idx for idx, value in enumerate(ns)}
    fold_index = {value: idx for idx, value in enumerate(folds)}
    seed_index = {value: idx for idx, value in enumerate(seeds)}
    current_rows = []
    for row in rows:
        idx = (
            n_index[int(row["n"])],
            fold_index[int(row["fold"])],
            seed_index[int(row["seed"])],
        )
        current = {"n": int(row["n"]), "fold": int(row["fold"]),
                   "seed": int(row["seed"])}
        for route in ROUTES:
            value = float(row[f"mse_{route.lower()}"])
            arrays[route][idx] = value
            current[f"mse_{route.lower()}"] = value
        current_rows.append(current)

    pooled = {route: float(source_summary["pooled_rrmse"][route]) for route in ROUTES}
    contrasts = {
        "Q_minus_P": _contrast(
            arrays["Q"], arrays["P"], pooled["Q"], pooled["P"],
            replicates=200_000, seed=2026082811,
        ),
        "QCP_minus_Q": _contrast(
            arrays["QCP"], arrays["Q"], pooled["QCP"], pooled["Q"],
            replicates=200_000, seed=2026082812,
        ),
        "QCP_minus_P": _contrast(
            arrays["QCP"], arrays["P"], pooled["QCP"], pooled["P"],
            replicates=200_000, seed=2026082813,
        ),
    }
    summary = {
        "protocol_id": "study02-pq-qcp-current-analysis-v1",
        "status": "COMPLETE",
        "evidence_level": "post-test three-route sensitivity derived from frozen evidence",
        "common_budget": {"max_epochs": 600, "patience": 60},
        "model_cells_per_route": 200,
        "test_rows_per_route": int(source_summary["n_test_rows_per_route"]),
        "constraint_feasible_checkpoints": 200,
        "pooled_rrmse": pooled,
        "diagnostics": {
            route: source_summary["diagnostics"][route] for route in ROUTES
        },
        "resource_diagnostics": {
            route: source_summary["resource_diagnostics"][route] for route in ROUTES
        },
        "contrasts": contrasts,
        "decision": "P_Q_QCP_CURRENT_NARRATIVE_SUPPORTED",
    }

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _write_json(ANALYSIS / "summary.json", summary)
    with (ANALYSIS / "model_cells.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(current_rows[0]))
        writer.writeheader()
        writer.writerows(current_rows)
    resource_rows = _resource_rows(source)
    with (ANALYSIS / "resource_cells.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(resource_rows[0]))
        writer.writeheader()
        writer.writerows(resource_rows)

    manifest = {
        "protocol_id": summary["protocol_id"],
        "status": "COMPLETE",
        "new_training_fits": 0,
        "source_summary_sha256": _sha(source_summary_path),
        "source_model_cells_sha256": _sha(source_cells_path),
        "qcp_manifest_sha256": _sha(QCP_ROOT / "manifest.json"),
        "analysis_code_sha256": _sha(Path(__file__)),
        "git_head_at_derivation": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True
        ).strip(),
    }
    _write_json(OUT / "manifest.json", manifest)
    files = sorted(
        path for path in OUT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
