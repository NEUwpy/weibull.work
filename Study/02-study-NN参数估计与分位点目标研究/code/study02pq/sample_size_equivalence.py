"""Post-test sample-size and P-equivalent sample-size analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
INPUT = ROOT / "artifacts" / "qcp_main_analysis" / "analysis" / "model_cells.csv"
PROTOCOL = ROOT / "protocols" / "19-任务诱导度量与等效样本量分析合同.md"
OUT = ROOT / "artifacts" / "qcp_sample_size_analysis"
ANALYSIS = OUT / "analysis"
N_GRID = np.asarray([7, 10, 15, 20], dtype=np.int64)
ROUTES = ("P", "Q", "QCP")
DEFAULT_SEEDS = (42, 2026, 3407, 17, 73, 314, 2718, 4099, 8128, 12011)


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_cells(path: Path = INPUT) -> tuple[np.ndarray, tuple[int, ...]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seeds = tuple(int(value) for value in DEFAULT_SEEDS)
    seed_index = {seed: idx for idx, seed in enumerate(seeds)}
    n_index = {int(n): idx for idx, n in enumerate(N_GRID)}
    values = np.full((len(N_GRID), 5, len(seeds), len(ROUTES)), np.nan, dtype=np.float64)
    for row in rows:
        n = int(row["n"])
        fold = int(row["fold"])
        seed = int(row["seed"])
        key = (n_index[n], fold - 1, seed_index[seed])
        if np.isfinite(values[key][0]):
            raise RuntimeError(f"duplicate model cell: n={n}, fold={fold}, seed={seed}")
        values[key] = [float(row["mse_p"]), float(row["mse_q"]), float(row["mse_qcp"])]
    if not np.isfinite(values).all():
        raise RuntimeError("incomplete or non-finite model-cell grid")
    return values, seeds


def _fit_power_law(p_rrmse: np.ndarray) -> tuple[float, float, float]:
    x = np.log(N_GRID.astype(np.float64))
    y = np.log(np.asarray(p_rrmse, dtype=np.float64))
    slope, intercept = np.polyfit(x, y, 1)
    exponent = float(-slope)
    if exponent <= 0:
        raise RuntimeError(f"non-decreasing P error curve: exponent={exponent}")
    fitted = np.exp(intercept) * N_GRID.astype(np.float64) ** (-exponent)
    r2 = 1.0 - float(np.sum((p_rrmse - fitted) ** 2) / np.sum((p_rrmse - np.mean(p_rrmse)) ** 2))
    return float(np.exp(intercept)), exponent, r2


def _effective_n(rrmse: np.ndarray, exponent: float) -> np.ndarray:
    ratios = rrmse[:, [0]] / rrmse[:, 1:]
    return N_GRID[:, None] * np.power(ratios, 1.0 / exponent)


def _bootstrap(values: np.ndarray, *, draws: int, seed: int, chunk: int = 5000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    rrmse_draws = np.empty((draws, len(N_GRID), len(ROUTES)), dtype=np.float32)
    effective_draws = np.empty((draws, len(N_GRID), 2), dtype=np.float32)
    exponent_draws = np.empty(draws, dtype=np.float32)
    x = np.log(N_GRID.astype(np.float64))
    xc = x - np.mean(x)
    denom = float(np.sum(xc * xc))
    offset = 0
    while offset < draws:
        size = min(chunk, draws - offset)
        seed_pick = rng.integers(0, values.shape[2], size=(size, values.shape[2]))
        fold_pick = rng.integers(0, values.shape[1], size=(size, len(N_GRID), values.shape[1]))
        mse = np.empty((size, len(N_GRID), len(ROUTES)), dtype=np.float64)
        for n_idx in range(len(N_GRID)):
            selected = values[n_idx][
                fold_pick[:, n_idx, :, None],
                seed_pick[:, None, :],
                :,
            ]
            mse[:, n_idx, :] = np.mean(selected, axis=(1, 2))
        rrmse = np.sqrt(mse)
        y = np.log(rrmse[:, :, 0])
        slopes = np.sum((y - np.mean(y, axis=1, keepdims=True)) * xc[None, :], axis=1) / denom
        exponents = -slopes
        if np.any(exponents <= 0):
            raise RuntimeError("bootstrap produced a non-decreasing P error curve")
        ratios = rrmse[:, :, [0]] / rrmse[:, :, 1:]
        effective = N_GRID[None, :, None] * np.power(ratios, 1.0 / exponents[:, None, None])
        sl = slice(offset, offset + size)
        rrmse_draws[sl] = rrmse.astype(np.float32)
        effective_draws[sl] = effective.astype(np.float32)
        exponent_draws[sl] = exponents.astype(np.float32)
        offset += size
    return rrmse_draws, effective_draws, exponent_draws


def run(*, draws: int = 200_000, seed: int = 20260828) -> dict:
    values, seeds = _load_cells()
    rrmse = np.sqrt(np.mean(values, axis=(1, 2)))
    coefficient, exponent, r2 = _fit_power_law(rrmse[:, 0])
    effective = _effective_n(rrmse, exponent)
    r_draws, e_draws, b_draws = _bootstrap(values, draws=draws, seed=seed)
    r_ci = np.quantile(r_draws, [0.025, 0.975], axis=0)
    e_ci = np.quantile(e_draws, [0.025, 0.975], axis=0)
    b_ci = np.quantile(b_draws, [0.025, 0.975])

    by_n = []
    for i, n in enumerate(N_GRID):
        row: dict[str, float | int] = {"n": int(n)}
        for j, route in enumerate(ROUTES):
            key = route.lower()
            row[f"{key}_rrmse"] = float(rrmse[i, j])
            row[f"{key}_rrmse_ci_low"] = float(r_ci[0, i, j])
            row[f"{key}_rrmse_ci_high"] = float(r_ci[1, i, j])
        for j, route in enumerate(("Q", "QCP")):
            key = route.lower()
            row[f"{key}_p_equivalent_n"] = float(effective[i, j])
            row[f"{key}_p_equivalent_n_ci_low"] = float(e_ci[0, i, j])
            row[f"{key}_p_equivalent_n_ci_high"] = float(e_ci[1, i, j])
            row[f"{key}_equivalent_added_n"] = float(effective[i, j] - n)
            row[f"{key}_equivalent_added_n_ci_low"] = float(e_ci[0, i, j] - n)
            row[f"{key}_equivalent_added_n_ci_high"] = float(e_ci[1, i, j] - n)
        by_n.append(row)

    summary = {
        "protocol_id": "study02-task-metric-effective-sample-size-v1",
        "status": "COMPLETE",
        "evidence_level": "post-test exploratory analysis derived from frozen evidence",
        "new_training_fits": 0,
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
        "model_cells": int(values.shape[0] * values.shape[1] * values.shape[2]),
        "seeds": list(seeds),
        "p_power_law": {
            "coefficient": coefficient,
            "exponent": exponent,
            "exponent_95ci": [float(b_ci[0]), float(b_ci[1])],
            "r_squared": r2,
            "formula": "P_rRMSE(n) = coefficient * n ** (-exponent)",
        },
        "by_n": by_n,
        "interpretation_boundary": (
            "Equivalent n is a descriptive translation conditional on the fitted P error curve; "
            "it is not observed extra data or a confirmatory extrapolation."
        ),
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    _write_json(ANALYSIS / "summary.json", summary)
    fieldnames = list(by_n[0].keys())
    with (ANALYSIS / "by_n.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(by_n)
    manifest = {
        "protocol_id": summary["protocol_id"],
        "status": "COMPLETE",
        "new_training_fits": 0,
        "input_model_cells_sha256": _sha(INPUT),
        "protocol_sha256": _sha(PROTOCOL),
        "analysis_code_sha256": _sha(Path(__file__)),
    }
    _write_json(OUT / "manifest.json", manifest)
    tracked = [ANALYSIS / "summary.json", ANALYSIS / "by_n.csv", OUT / "manifest.json"]
    (OUT / "SHA256SUMS").write_text(
        "".join(f"{_sha(path)}  {path.relative_to(OUT).as_posix()}\n" for path in tracked),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=20260828)
    args = parser.parse_args()
    print(json.dumps(run(draws=args.draws, seed=args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
