"""Post-test bias--variance decomposition of frozen P/Q/QCP predictions."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
OUT = ROOT / "artifacts" / "qcp_bias_variance"
ANALYSIS = OUT / "analysis"
QCP_ROOT = ROOT / "artifacts" / "qcp_constrained_confirm"
SOURCE_CANDIDATES = (
    ROOT / "artifacts" / "equal_budget_sensitivity",
    ROOT / "历史实验" / "四路线同预算敏感性" / "artifacts" /
    "equal_budget_sensitivity",
)
PROTOCOL = ROOT / "protocols" / "20-寿命点误差偏差方差分解合同.md"
MAIN_SUMMARY = ROOT / "artifacts" / "qcp_main_analysis" / "analysis" / "summary.json"
MODEL_CELLS = ROOT / "artifacts" / "qcp_main_analysis" / "analysis" / "model_cells.csv"
ROUTES = ("P", "Q", "QCP")
KEY_FIELDS = ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id")


def _source_root() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if (candidate / "evidence").exists():
            return candidate
    raise FileNotFoundError("frozen common-budget evidence was not found")


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        return {name: np.asarray(data[name]) for name in data.files}


def _fit_name(n: int, fold: int, seed: int, route: str) -> str:
    return f"n{n}_f{fold}_s{seed}_r{route}"


def _evidence_path(source: Path, n: int, fold: int, seed: int, route: str) -> Path:
    root = QCP_ROOT if route == "QCP" else source
    return root / "evidence" / f"{_fit_name(n, fold, seed, route)}.npz"


def main() -> None:
    source = _source_root()
    with MODEL_CELLS.open("r", encoding="utf-8", newline="") as handle:
        model_rows = list(csv.DictReader(handle))
    if len(model_rows) != 200:
        raise RuntimeError(f"expected 200 model cells, got {len(model_rows)}")

    chunks: dict[str, dict[tuple[int, float, float], list[np.ndarray]]] = {
        route: defaultdict(list) for route in ROUTES
    }
    evidence_hashes: list[str] = []
    for row in model_rows:
        n, fold, seed = int(row["n"]), int(row["fold"]), int(row["seed"])
        loaded = {}
        for route in ROUTES:
            path = _evidence_path(source, n, fold, seed, route)
            if not path.exists():
                raise FileNotFoundError(path)
            loaded[route] = _load(path)
            evidence_hashes.append(_sha(path))
        for field in KEY_FIELDS:
            if any(not np.array_equal(loaded["P"][field], loaded[route][field])
                   for route in ("Q", "QCP")):
                raise RuntimeError(f"held-out key mismatch: {n=} {fold=} {seed=} {field}")

        beta = loaded["P"]["keys_beta"].astype(np.float64)
        gamma = loaded["P"]["keys_gamma_over_eta"].astype(np.float64)
        n_key = loaded["P"]["keys_n"].astype(np.int64)
        if not np.all(n_key == n):
            raise RuntimeError(f"n key mismatch for {n=} {fold=} {seed=}")
        for beta_value in np.unique(beta):
            for gamma_value in np.unique(gamma):
                mask = (beta == beta_value) & (gamma == gamma_value)
                key = (n, float(beta_value), float(gamma_value))
                for route in ROUTES:
                    rel = loaded[route]["rel_err"].astype(np.float64)
                    if not np.isfinite(rel[mask]).all():
                        raise RuntimeError(f"nonfinite relative error: {route=} {key=}")
                    chunks[route][key].append(rel[mask])

    cell_rows: list[dict] = []
    summaries: dict[str, dict] = {}
    main_summary = json.loads(MAIN_SUMMARY.read_text(encoding="utf-8"))
    for route in ROUTES:
        route_rows = []
        for key in sorted(chunks[route]):
            values = np.concatenate(chunks[route][key])
            if values.size != 3000:
                raise RuntimeError(f"expected 3000 predictions for {route=} {key=}, got {values.size}")
            bias = float(values.mean())
            variance = float(np.mean((values - bias) ** 2))
            mse = float(np.mean(values ** 2))
            residual = float(mse - bias ** 2 - variance)
            record = {
                "route": route,
                "n": key[0],
                "beta": key[1],
                "gamma_over_eta": key[2],
                "count": int(values.size),
                "relative_bias": bias,
                "within_cell_variance": variance,
                "cell_mse": mse,
                "identity_residual": residual,
            }
            route_rows.append(record)
            cell_rows.append(record)
        if len(route_rows) != 160:
            raise RuntimeError(f"expected 160 truth cells for {route}, got {len(route_rows)}")
        bias = np.asarray([row["relative_bias"] for row in route_rows])
        variance = np.asarray([row["within_cell_variance"] for row in route_rows])
        mse = np.asarray([row["cell_mse"] for row in route_rows])
        rms_bias = float(np.sqrt(np.mean(bias ** 2)))
        within_sd = float(np.sqrt(np.mean(variance)))
        rmsre = float(np.sqrt(np.mean(mse)))
        pooled_error_sd = float(np.sqrt(rmsre ** 2 - float(np.mean(bias)) ** 2))
        expected = float(main_summary["pooled_rrmse"][route])
        if not np.isclose(rmsre, expected, atol=1e-9, rtol=0.0):
            raise RuntimeError(f"RMSRE mismatch for {route}: {rmsre} != {expected}")
        summaries[route] = {
            "signed_relative_bias": float(np.mean(bias)),
            "rms_cell_bias_component": rms_bias,
            "within_truth_cell_sd_component": within_sd,
            "pooled_relative_error_sd": pooled_error_sd,
            "rmsre": rmsre,
            "decomposition_residual": float(rmsre ** 2 - rms_bias ** 2 - within_sd ** 2),
        }

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    with (ANALYSIS / "cell_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
        writer.writeheader()
        writer.writerows(cell_rows)
    truth_keys = sorted(chunks["P"])
    x95_values = [
        1000.0 * gamma_ratio + 1000.0 * (-np.log(0.95)) ** (1.0 / beta)
        for _, beta, gamma_ratio in truth_keys
    ]
    summary = {
        "protocol_id": "study02-qcp-bias-variance-v1",
        "status": "COMPLETE",
        "evidence_level": "post-test descriptive decomposition of frozen evidence",
        "new_training_fits": 0,
        "truth_cells_per_route": 160,
        "predictions_per_truth_cell": 3000,
        "x95_true_range": {
            "minimum": float(np.min(x95_values)),
            "maximum": float(np.max(x95_values)),
        },
        "routes": summaries,
        "interpretation_boundary": (
            "Within-cell SD is computed at fixed (n,beta,gamma/eta); pooled error SD additionally "
            "contains between-cell bias heterogeneity. All values are descriptive post-test evidence."
        ),
    }
    _write_json(ANALYSIS / "summary.json", summary)
    manifest = {
        "protocol_id": summary["protocol_id"],
        "status": "COMPLETE",
        "new_training_fits": 0,
        "protocol_sha256": _sha(PROTOCOL),
        "analysis_code_sha256": _sha(Path(__file__)),
        "main_summary_sha256": _sha(MAIN_SUMMARY),
        "model_cells_sha256": _sha(MODEL_CELLS),
        "evidence_file_count": len(evidence_hashes),
        "evidence_hash_set_sha256": hashlib.sha256(
            "\n".join(sorted(evidence_hashes)).encode("ascii")
        ).hexdigest(),
    }
    _write_json(OUT / "manifest.json", manifest)
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (OUT / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
