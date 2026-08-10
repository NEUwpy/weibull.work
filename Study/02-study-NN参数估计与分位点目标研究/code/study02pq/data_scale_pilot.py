"""Study02 训练数据量学习曲线最小筛选。

基线180条/组合直接读取 iid-v1 seed42、fold 1/3 的封存证据；只训练360和720两档。
验证与测试始终固定为原始 repeat_id 0..299 中的对应余数类。输出位于独立 pilot
命名空间，不修改任何既有证据。

运行（Study02/code）：
    $env:PQ_PROTOCOL='iid-v1'
    python -m study02pq.data_scale_pilot
"""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from . import config as CFG
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "pq-data-scale-pilot-v1.json"
OUT = ROOT / "artifacts" / "pq_data_scale_pilot"
EVIDENCE = OUT / "evidence"
METADATA = OUT / "fit_metadata"
ANALYSIS = OUT / "analysis"
BASELINE_EVIDENCE = ROOT / "artifacts" / "pq_iid_main" / "evidence"


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _fit_id(n: int, fold_idx: int, seed: int, route: str, level: int) -> str:
    return f"n{n}_f{fold_idx + 1}_s{seed}_r{route}_tr{level}"


def _evidence_path(fit: str) -> Path:
    return EVIDENCE / f"{fit}.npz"


def _meta_path(fit: str) -> Path:
    return METADATA / f"{fit}.json"


def _save_fit(fit: str, result: dict, level: int, config_sha: str, code_sha: str) -> None:
    p = result["predictions"]
    keys = p["keys"]
    np.savez_compressed(
        _evidence_path(fit),
        keys_beta=np.ascontiguousarray(keys[:, 0], dtype=np.float64),
        keys_gamma_over_eta=np.ascontiguousarray(keys[:, 1], dtype=np.float64),
        keys_n=np.ascontiguousarray(keys[:, 2], dtype=np.int32),
        keys_repeat_id=np.ascontiguousarray(keys[:, 3], dtype=np.int32),
        beta_hat=np.asarray(p["beta_hat"], dtype=np.float32),
        eta_hat=np.asarray(p["eta_hat"], dtype=np.float32),
        gamma_hat=np.asarray(p["gamma_hat"], dtype=np.float32),
        x95_hat=np.asarray(p["x95_hat"], dtype=np.float32),
        x95_true=np.asarray(p["x95_true"], dtype=np.float32),
        min_x=np.asarray(p["min_x"], dtype=np.float32),
        rel_err=np.asarray(p["rel_err"], dtype=np.float32),
        rel_err_sq=np.asarray(p["rel_err_sq"], dtype=np.float32),
    )
    meta = dict(result["meta"])
    meta.update({
        "train_repeats_per_combo": int(level),
        "screening_only": True,
        "pilot_config_sha256": config_sha,
        "pilot_code_sha256": code_sha,
        "evidence_sha256": _sha(_evidence_path(fit)),
    })
    _json(_meta_path(fit), meta)


def _load_evidence(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def _keys(ev: dict[str, np.ndarray]) -> tuple[np.ndarray, ...]:
    return tuple(ev[k] for k in (
        "keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"
    ))


def _same_keys(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> bool:
    return all(np.array_equal(x, y) for x, y in zip(_keys(a), _keys(b)))


def _write_summary(cfg: dict, config_sha: str, code_sha: str, elapsed_s: float) -> dict:
    levels = [int(x) for x in cfg["train_repeats_per_combo"]]
    n_grid = [int(x) for x in cfg["n_grid"]]
    folds = [int(x) - 1 for x in cfg["folds_1based"]]
    seed = int(cfg["seed"])
    rows: list[dict] = []
    pooled: dict[str, dict] = {}

    for level in levels:
        by_route: dict[str, list[np.ndarray]] = {"P": [], "Q": []}
        by_n: dict[int, dict[str, list[np.ndarray]]] = {
            n: {"P": [], "Q": []} for n in n_grid
        }
        q_better = 0
        for n in n_grid:
            for fold_idx in folds:
                ev = {}
                for route in ("P", "Q"):
                    if level == 180:
                        path = BASELINE_EVIDENCE / f"n{n}_f{fold_idx + 1}_s{seed}_r{route}.npz"
                    else:
                        path = _evidence_path(_fit_id(n, fold_idx, seed, route, level))
                    ev[route] = _load_evidence(path)
                    arr = np.asarray(ev[route]["rel_err_sq"], dtype=np.float64)
                    by_route[route].append(arr)
                    by_n[n][route].append(arr)
                if not _same_keys(ev["P"], ev["Q"]):
                    raise AssertionError(f"P/Q test keys differ: level={level}, n={n}, fold={fold_idx+1}")
                p_mse = float(np.mean(ev["P"]["rel_err_sq"], dtype=np.float64))
                q_mse = float(np.mean(ev["Q"]["rel_err_sq"], dtype=np.float64))
                q_better += int(q_mse < p_mse)
                rows.append({
                    "train_repeats": level, "n": n, "fold": fold_idx + 1,
                    "seed": seed, "p_mse": p_mse, "q_mse": q_mse,
                    "q_minus_p_mse": q_mse - p_mse,
                })

        p_rrmse = float(np.sqrt(np.mean(np.concatenate(by_route["P"]))))
        q_rrmse = float(np.sqrt(np.mean(np.concatenate(by_route["Q"]))))
        per_n = {}
        for n in n_grid:
            pn = float(np.sqrt(np.mean(np.concatenate(by_n[n]["P"]))))
            qn = float(np.sqrt(np.mean(np.concatenate(by_n[n]["Q"]))))
            per_n[str(n)] = {
                "P_rrmse": pn, "Q_rrmse": qn,
                "Q_relative_improvement_vs_P": (pn - qn) / pn,
            }
        pooled[str(level)] = {
            "P_rrmse": p_rrmse,
            "Q_rrmse": q_rrmse,
            "Q_relative_improvement_vs_P": (p_rrmse - q_rrmse) / p_rrmse,
            "Q_better_model_cells": q_better,
            "n_model_cells": len(n_grid) * len(folds),
            "per_n": per_n,
        }

    q180 = pooled["180"]["Q_rrmse"]
    for level in levels:
        pooled[str(level)]["Q_relative_improvement_vs_level180"] = (
            q180 - pooled[str(level)]["Q_rrmse"]
        ) / q180
    q_curve = [pooled[str(level)]["Q_rrmse"] for level in levels]
    monotonic = all(q_curve[i + 1] < q_curve[i] for i in range(len(q_curve) - 1))

    with (ANALYSIS / "cell_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "SCREENING COMPLETE",
        "screening_only": True,
        "design": {
            "train_repeats_per_combo": levels,
            "n_grid": n_grid,
            "folds_1based": cfg["folds_1based"],
            "seed": seed,
            "fixed_validation_and_test": True,
            "baseline_180_reused": True,
            "new_fits": cfg["new_fits"],
        },
        "pooled": pooled,
        "learning_curve": {
            "Q_rrmse": {str(level): pooled[str(level)]["Q_rrmse"] for level in levels},
            "strictly_monotonic_decrease": monotonic,
            "interpretation": "descriptive screening; no formal significance claim",
        },
        "integrity": {
            "all_P_Q_test_keys_match": True,
            "config_sha256": config_sha,
            "pilot_code_sha256": code_sha,
            "elapsed_s_new_fits": elapsed_s,
        },
    }
    _json(ANALYSIS / "summary.json", summary)
    return summary


def _write_manifest(cfg: dict, config_sha: str, code_sha: str) -> None:
    bound = {
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": config_sha},
        "pilot_code": {
            "path": "code/study02pq/data_scale_pilot.py", "sha256": code_sha,
        },
        "data_code": {
            "path": "code/study02pq/data.py", "sha256": _sha(ROOT / "code/study02pq/data.py"),
        },
        "training_code": {
            "path": "code/study02pq/training.py",
            "sha256": _sha(ROOT / "code/study02pq/training.py"),
        },
        "environment": {
            "path": "configs/pq-environment-v2.json",
            "sha256": _sha(ROOT / "configs/pq-environment-v2.json"),
        },
    }
    baseline = {}
    for n in cfg["n_grid"]:
        for fold in cfg["folds_1based"]:
            for route in cfg["routes"]:
                p = BASELINE_EVIDENCE / f"n{n}_f{fold}_s{cfg['seed']}_r{route}.npz"
                baseline[str(p.relative_to(ROOT)).replace("\\", "/")] = _sha(p)
    outputs = {}
    for directory in (EVIDENCE, METADATA, ANALYSIS):
        for p in sorted(directory.glob("*")):
            if p.is_file():
                outputs[str(p.relative_to(ROOT)).replace("\\", "/")] = _sha(p)
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "screening_only": True,
        "no_existing_evidence_modified": True,
        "sha256_rule": "text files LF-normalized; NPZ binary raw",
        "bound_sources": bound,
        "baseline_evidence_sha256": baseline,
        "output_sha256": outputs,
    }
    _json(OUT / "manifest.json", manifest)

    entries = []
    for p in sorted(list(EVIDENCE.glob("*")) + list(METADATA.glob("*"))
                    + list(ANALYSIS.glob("*")) + [OUT / "manifest.json"]):
        if p.is_file():
            entries.append(f"{_sha(p)}  {str(p.relative_to(OUT)).replace(os.sep, '/')}")
    (OUT / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")


def _reseal_existing(cfg: dict, config_sha: str, code_sha: str) -> None:
    for mp in sorted(METADATA.glob("*.json")):
        meta = json.loads(mp.read_text(encoding="utf-8"))
        ep = EVIDENCE / f"{mp.stem}.npz"
        if not ep.is_file():
            raise FileNotFoundError(ep)
        meta["pilot_config_sha256"] = config_sha
        meta["pilot_code_sha256"] = code_sha
        meta["evidence_sha256"] = _sha(ep)
        _json(mp, meta)
    old_summary = ANALYSIS / "summary.json"
    elapsed = 0.0
    if old_summary.is_file():
        elapsed = float(json.loads(old_summary.read_text(encoding="utf-8"))
                        .get("integrity", {}).get("elapsed_s_new_fits", 0.0))
    _write_summary(cfg, config_sha, code_sha, elapsed)
    _write_manifest(cfg, config_sha, code_sha)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reseal-only", action="store_true",
                    help="refresh portable hashes/summary from existing fits; never train")
    args = ap.parse_args()
    if CFG.PROTOCOL_VERSION != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 before running data_scale_pilot")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for d in (OUT, EVIDENCE, METADATA, ANALYSIS):
        d.mkdir(parents=True, exist_ok=True)
    config_sha = _sha(CONFIG_PATH)
    code_sha = _sha(Path(__file__).resolve())
    if args.reseal_only:
        _reseal_existing(cfg, config_sha, code_sha)
        print("[data-scale] resealed existing evidence; no training")
        return 0
    max_repeats = int(cfg["max_repeat_id_exclusive"])
    print(f"[data-scale] rebuild deterministic master: repeats={max_repeats}", flush=True)
    master = DATA.build_master(repeats=max_repeats)

    started = time.time()
    done = skipped = 0
    for level in [int(x) for x in cfg["train_repeats_per_combo"] if int(x) > 180]:
        for n in [int(x) for x in cfg["n_grid"]]:
            for fold_1 in [int(x) for x in cfg["folds_1based"]]:
                fold_idx = fold_1 - 1
                rows = DATA.split_data_scale_fixed_eval(master, n, fold_idx, level)
                for route in cfg["routes"]:
                    fit = _fit_id(n, fold_idx, int(cfg["seed"]), route, level)
                    ep, mp = _evidence_path(fit), _meta_path(fit)
                    if ep.is_file() and mp.is_file():
                        meta = json.loads(mp.read_text(encoding="utf-8"))
                        if (meta.get("pilot_config_sha256") == config_sha
                                and meta.get("pilot_code_sha256") == code_sha
                                and meta.get("evidence_sha256") == _sha(ep)):
                            skipped += 1
                            print(f"[data-scale] skip verified {fit}", flush=True)
                            continue
                    print(f"[data-scale] train {fit}", flush=True)
                    result = TR.train_one_fit(
                        n, fold_idx, int(cfg["seed"]), route, master,
                        split_strategy="data_scale_fixed_eval", split_rows=rows,
                        fit_suffix=f"_tr{level}",
                    )
                    _save_fit(fit, result, level, config_sha, code_sha)
                    done += 1
                    m = result["meta"]
                    print(
                        f"[data-scale] done {fit}: rRMSE={m['rrmse_x95']:.6f}, "
                        f"epoch={m['best_epoch']}, runtime={m['runtime_s']:.1f}s",
                        flush=True,
                    )

    elapsed = time.time() - started
    summary = _write_summary(cfg, config_sha, code_sha, elapsed)
    _write_manifest(cfg, config_sha, code_sha)
    print(f"[data-scale] completed new={done} skipped={skipped} elapsed={elapsed:.1f}s")
    for level, result in summary["pooled"].items():
        print(
            f"  train={level}: P={result['P_rrmse']:.6f} Q={result['Q_rrmse']:.6f} "
            f"Q-vs-P={100*result['Q_relative_improvement_vs_P']:.2f}% "
            f"Q-vs-180={100*result['Q_relative_improvement_vs_level180']:.2f}%"
        )
    print("  monotonic Q decrease:", summary["learning_curve"]["strictly_monotonic_decrease"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
