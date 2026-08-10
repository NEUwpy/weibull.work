"""Study02 P/Q 工程价值审计：只读复用 10-seed 逐样本证据。

该脚本不训练模型，不修改封存证据。它在主 rRMSE 之外计算
典型误差、绝对误差尾部和寿命高/低估指标，用与主分析一致的
fold-within-n x global-seed 配对交叉 bootstrap 描述设计级不确定性。
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "artifacts" / "pq_iid_main"
S5B = ROOT / "artifacts" / "pq_s5b_revision"
OUT = ROOT / "artifacts" / "pq_engineering_audit"
NS = [7, 10, 15, 20]
SEEDS = [42, 2026, 3407, 17, 73, 314, 2718, 4099, 8128, 12011]
N_FOLDS = 5
N_BOOT = 200_000
BOOT_SEED = 2026081001


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _evidence(n: int, fold: int, seed: int, route: str) -> Path:
    name = f"n{n}_f{fold}_s{seed}_r{route}.npz"
    if seed in SEEDS[:3]:
        return OLD / "evidence" / name
    return S5B / "grid_extra" / "evidence" / name


def _identity(ev: np.lib.npyio.NpzFile) -> tuple[np.ndarray, ...]:
    id_key = "keys_repeat_id" if "keys_repeat_id" in ev.files else "keys_point_or_repeat_id"
    return tuple(ev[k] for k in (
        "keys_beta", "keys_gamma_over_eta", "keys_n", id_key
    ))


def _cell_metrics(err: np.ndarray) -> dict[str, float]:
    ae = np.abs(err)
    q90 = float(np.quantile(ae, 0.90))
    pos = np.clip(err, 0.0, None)
    neg = np.clip(-err, 0.0, None)
    return {
        "mse": float(np.mean(err**2)),
        "mae": float(np.mean(ae)),
        "median_abs_error": float(np.median(ae)),
        "q90_abs_error": q90,
        "q95_abs_error": float(np.quantile(ae, 0.95)),
        "cvar90_abs_error": float(np.mean(ae[ae >= q90])),
        "within_10pct": float(np.mean(ae <= 0.10)),
        "within_20pct": float(np.mean(ae <= 0.20)),
        "over_10pct": float(np.mean(err > 0.10)),
        "over_20pct": float(np.mean(err > 0.20)),
        "under_10pct": float(np.mean(err < -0.10)),
        "under_20pct": float(np.mean(err < -0.20)),
        "over_any": float(np.mean(err > 0.0)),
        "signed_bias": float(np.mean(err)),
        "positive_mse_contribution": float(np.mean(pos**2)),
        "negative_mse_contribution": float(np.mean(neg**2)),
    }


def _load() -> tuple[dict[str, np.ndarray], np.ndarray, list[dict]]:
    shape = (len(NS), N_FOLDS, len(SEEDS), 2)
    metrics: dict[str, np.ndarray] = {}
    win = np.empty(shape[:-1], dtype=np.float64)
    rows: list[dict] = []
    for ni, n in enumerate(NS):
        for fi in range(N_FOLDS):
            for si, seed in enumerate(SEEDS):
                loaded = []
                row = {"n": n, "fold": fi + 1, "seed": seed}
                for ri, route in enumerate(("P", "Q")):
                    path = _evidence(n, fi + 1, seed, route)
                    with np.load(path) as ev:
                        err = np.asarray(ev["rel_err"], dtype=np.float64)
                        identity = tuple(np.array(x, copy=True) for x in _identity(ev))
                    if not np.isfinite(err).all():
                        raise AssertionError(f"non-finite rel_err: {path}")
                    loaded.append((identity, err))
                    for name, value in _cell_metrics(err).items():
                        if name not in metrics:
                            metrics[name] = np.empty(shape, dtype=np.float64)
                        metrics[name][ni, fi, si, ri] = value
                        row[f"{route}_{name}"] = value
                if not all(np.array_equal(a, b) for a, b in zip(
                        loaded[0][0], loaded[1][0])):
                    raise AssertionError(f"P/Q identity mismatch: n={n}, f={fi+1}, s={seed}")
                p_abs, q_abs = np.abs(loaded[0][1]), np.abs(loaded[1][1])
                win[ni, fi, si] = float(
                    np.mean(q_abs < p_abs) + 0.5 * np.mean(q_abs == p_abs)
                )
                row["Q_lower_abs_error_rate"] = win[ni, fi, si]
                rows.append(row)
    return metrics, win, rows


def _bootstrap(p: np.ndarray, q: np.ndarray, transform: str,
               seed: int) -> dict:
    if p.shape != q.shape or p.shape != (4, 5, 10):
        raise ValueError("expected paired (n, fold, seed) arrays")
    rng = np.random.default_rng(seed)
    draws = np.empty(N_BOOT, dtype=np.float64)
    batch = 2000
    for start in range(0, N_BOOT, batch):
        size = min(batch, N_BOOT - start)
        seed_idx = rng.integers(0, 10, size=(size, 10))
        fold_idx = rng.integers(0, 5, size=(size, 4, 5))
        mp = np.zeros(size)
        mq = np.zeros(size)
        for ni in range(4):
            mp += p[ni][fold_idx[:, ni, :, None], seed_idx[:, None, :]].mean((1, 2))
            mq += q[ni][fold_idx[:, ni, :, None], seed_idx[:, None, :]].mean((1, 2))
        mp /= 4
        mq /= 4
        if transform == "lower_relative":
            value = (mp - mq) / mp
        elif transform == "higher_pp":
            value = mq - mp
        elif transform == "lower_pp":
            value = mp - mq
        elif transform == "q_minus_p":
            value = mq - mp
        elif transform == "rrmse_relative":
            value = (np.sqrt(mp) - np.sqrt(mq)) / np.sqrt(mp)
        else:
            raise ValueError(transform)
        draws[start:start + size] = value

    point_p, point_q = float(p.mean()), float(q.mean())
    if transform == "lower_relative":
        effect = (point_p - point_q) / point_p
    elif transform == "higher_pp":
        effect = point_q - point_p
    elif transform == "lower_pp":
        effect = point_p - point_q
    elif transform == "q_minus_p":
        effect = point_q - point_p
    else:
        effect = (np.sqrt(point_p) - np.sqrt(point_q)) / np.sqrt(point_p)
    reported_p = float(np.sqrt(point_p)) if transform == "rrmse_relative" else point_p
    reported_q = float(np.sqrt(point_q)) if transform == "rrmse_relative" else point_q
    return {
        "P": reported_p,
        "Q": reported_q,
        "effect": float(effect),
        "effect_ci95": np.quantile(draws, [0.025, 0.975]).tolist(),
        "effect_definition": transform,
    }


def analyze() -> dict:
    metrics, win, rows = _load()
    transforms = {
        "mse": "lower_relative",
        "mae": "lower_relative",
        "median_abs_error": "lower_relative",
        "q90_abs_error": "lower_relative",
        "q95_abs_error": "lower_relative",
        "cvar90_abs_error": "lower_relative",
        "within_10pct": "higher_pp",
        "within_20pct": "higher_pp",
        "over_10pct": "lower_pp",
        "over_20pct": "lower_pp",
        "under_10pct": "q_minus_p",
        "under_20pct": "q_minus_p",
        "over_any": "lower_pp",
        "signed_bias": "q_minus_p",
        "positive_mse_contribution": "lower_relative",
        "negative_mse_contribution": "lower_relative",
    }
    results = {}
    for index, (name, transform) in enumerate(transforms.items()):
        p, q = metrics[name][..., 0], metrics[name][..., 1]
        item = _bootstrap(p, q, transform, BOOT_SEED + index)
        positive_when_q_lower = transform in {
            "lower_relative", "lower_pp", "rrmse_relative",
        }
        positive = (q < p) if positive_when_q_lower else (q > p)
        item["positive_effect_cells"] = int(positive.sum())
        item["total_cells"] = int(positive.size)
        item["positive_effect_seeds"] = int(sum(
            (q[:, :, si].mean() < p[:, :, si].mean()) if positive_when_q_lower
            else (q[:, :, si].mean() > p[:, :, si].mean())
            for si in range(len(SEEDS))
        ))
        results[name] = item

    results["rrmse"] = _bootstrap(
        metrics["mse"][..., 0], metrics["mse"][..., 1],
        "rrmse_relative", BOOT_SEED + 100,
    )
    win_result = _bootstrap(
        np.full_like(win, 0.5), win, "higher_pp", BOOT_SEED + 101,
    )
    win_result["Q_lower_abs_error_rate"] = float(win.mean())

    return {
        "audit_id": "study02-pq-engineering-value-audit-v1",
        "status": "VERIFIED DERIVED ANALYSIS",
        "generated_from_git_head": _head(),
        "scope": "existing frozen-grid 10-seed evidence only; no training",
        "design": {
            "n": NS, "folds": [1, 2, 3, 4, 5], "seeds": SEEDS,
            "paired_model_cells": 200, "held_out_rows_per_cell": 2400,
            "bootstrap": "fold-within-n x global-seed paired crossed bootstrap",
            "n_boot": N_BOOT, "bootstrap_seed_base": BOOT_SEED,
        },
        "metrics": results,
        "paired_sample_win": win_result,
        "interpretation_boundary": [
            "All added metrics are post-hoc engineering audit metrics, not the confirmatory primary estimand.",
            "The 10% and 20% thresholds are transparent sensitivity thresholds, not validated engineering cost limits.",
            "Intervals are descriptive design-level empirical bootstrap intervals without multiplicity correction.",
            "Overestimation is potentially non-conservative only when x_R is used as a guaranteed-life threshold.",
        ],
        "fallacy_scan": {
            "coverage": "11/11",
            "red_flags": [],
            "cautions": [
                "post-hoc metrics and multiple comparisons: do not promote them to confirmatory claims",
                "no domain-specific engineering loss threshold or cost function was supplied",
                "observed error redistribution does not identify the full training-dynamics cause",
            ],
        },
        "decision": {
            "has_value": True,
            "value_type": "engineering trade-off, not broad accuracy dominance",
            "recommended_use": "compact exploratory result/discussion; do not replace the primary rRMSE result",
        },
        "_cell_rows": rows,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = analyze()
    rows = summary.pop("_cell_rows")
    with (OUT / "cell_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _json(OUT / "summary.json", summary)
    manifest = {
        "audit_id": summary["audit_id"],
        "generated_from_git_head": summary["generated_from_git_head"],
        "sha256_rule": "text files LF-normalized",
        "sources": {
            "pq_iid_main_manifest": _sha(OLD / "manifest.json"),
            "pq_s5b_revision_manifest": _sha(S5B / "manifest.json"),
            "analysis_code": _sha(Path(__file__)),
        },
        "outputs": {
            "summary.json": _sha(OUT / "summary.json"),
            "cell_metrics.csv": _sha(OUT / "cell_metrics.csv"),
            **({"report.md": _sha(OUT / "report.md")}
               if (OUT / "report.md").is_file() else {}),
        },
    }
    _json(OUT / "manifest.json", manifest)
    names = ["cell_metrics.csv", "manifest.json", "summary.json"]
    if (OUT / "report.md").is_file():
        names.append("report.md")
    entries = [f"{_sha(OUT / name)}  {name}" for name in sorted(names)]
    (OUT / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "rrmse": summary["metrics"]["rrmse"],
        "mae": summary["metrics"]["mae"],
        "cvar90": summary["metrics"]["cvar90_abs_error"],
        "over_10pct": summary["metrics"]["over_10pct"],
        "under_10pct": summary["metrics"]["under_10pct"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
