"""Study/02 P-Q 正式运行器：可续接逐 fit 训练、配对验证、汇总与 manifest。

用法：
    python code/study02pq/run.py --seed 42             # 正式 seed 42（40 fits）
    python code/study02pq/run.py --seed 2026 --seed 3407
    python code/study02pq/run.py --seed 42 --resume    # 幂等续接
    python code/study02pq/run.py --aggregate           # 只重建汇总/manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import training as TR  # noqa: E402


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _git_short_head():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=CFG.PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def ensure_dirs():
    for d in (CFG.ARTIFACT_DIR, CFG.PREDICTIONS_DIR, CFG.CHECKPOINTS_DIR):
        os.makedirs(d, exist_ok=True)


def prediction_csv_path(fit: str) -> str:
    return os.path.join(CFG.PREDICTIONS_DIR, f"{fit}.csv")


def checkpoint_json_path(fit: str) -> str:
    return os.path.join(CFG.CHECKPOINTS_DIR, f"{fit}.json")


def fit_complete(fit: str) -> bool:
    return os.path.isfile(prediction_csv_path(fit)) and os.path.isfile(checkpoint_json_path(fit))


def save_fit(fit: str, result: dict):
    p = result["predictions"]
    keys = p["keys"]
    df = pd.DataFrame({
        "beta": keys[:, 0], "gamma_over_eta": keys[:, 1], "n": keys[:, 2],
        "repeat_id": keys[:, 3].astype(int),
        "beta_hat": p["beta_hat"], "eta_hat": p["eta_hat"], "gamma_hat": p["gamma_hat"],
        "x95_hat": p["x95_hat"], "x95_true": p["x95_true"],
        "rel_err": p["rel_err"], "rel_err_sq": p["rel_err_sq"],
        "rel_b": p["rel_b"], "rel_e": p["rel_e"], "rel_g": p["rel_g"],
    })
    df.to_csv(prediction_csv_path(fit), index=False)
    meta = dict(result["meta"])
    meta["predictions_sha256"] = _sha256_file(prediction_csv_path(fit))
    with open(checkpoint_json_path(fit), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run_fits_for_seeds(seeds, master, resume=True):
    ensure_dirs()
    done, skipped = 0, 0
    for seed in seeds:
        for n in CFG.N_GRID:
            for fold_idx in range(CFG.N_FOLDS):
                for route in CFG.ROUTES:
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    if resume and fit_complete(fit):
                        skipped += 1
                        continue
                    print(f"[pq] train {fit} ...", flush=True)
                    result = TR.train_one_fit(n, fold_idx, seed, route, master)
                    save_fit(fit, result)
                    done += 1
    print(f"[pq] done={done} skipped={skipped}")


def write_splits_manifest(master):
    rec = {"generated_at": _now_iso(), "git_head": _git_short_head(),
           "split_rule": "combo_idx % 5 == fold_idx; combos=product(beta,goe,n)",
           "validation": {"fraction": CFG.VAL_FRACTION,
                          "salt": CFG.VAL["salt"]},
           "folds": {}}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            tr, va, te = DATA.split_fold(master, n, fold_idx)
            rec["folds"][f"n{n}_f{fold_idx + 1}"] = {
                "train_rows_sha": DATA.sha_rows(tr),
                "val_rows_sha": DATA.sha_rows(va),
                "test_rows_sha": DATA.sha_rows(te),
                "n_train": int(len(tr)), "n_val": int(len(va)),
                "n_test": int(len(te)),
            }
    with open(CFG.SPLITS_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def load_fit_meta(fit: str) -> dict:
    with open(checkpoint_json_path(fit), encoding="utf-8") as f:
        return json.load(f)


def load_rel_sq(route_fits: dict) -> tuple[np.ndarray, np.ndarray]:
    """从 P/Q 两 fit 预测读同一测试行上的 rel_err_sq。"""
    ps = pd.read_csv(prediction_csv_path(route_fits["P"]))
    qs = pd.read_csv(prediction_csv_path(route_fits["Q"]))
    key_cols = ["beta", "gamma_over_eta", "n", "repeat_id"]
    assert len(ps) == len(qs)
    merged = ps.merge(qs, on=key_cols, suffixes=("_p", "_q"))
    assert len(merged) == len(ps)
    return merged["rel_err_sq_p"].to_numpy(), merged["rel_err_sq_q"].to_numpy()


def pairing_report(seeds, master) -> pd.DataFrame:
    """对每个 (n, fold, seed) 验证 P/Q 除 loss 外全部一致。"""
    rows = []
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                mp = load_fit_meta(TR.fit_id(n, fold_idx, seed, "P"))
                mq = load_fit_meta(TR.fit_id(n, fold_idx, seed, "Q"))
                same = {
                    "init_param_sha": mp["init_param_sha"] == mq["init_param_sha"],
                    "batch_order_sha": mp["batch_order_sha"] == mq["batch_order_sha"],
                    "network_sha": mp["network_sha"] == mq["network_sha"],
                    "scaler_sha": mp["scaler_sha"] == mq["scaler_sha"],
                    "train_rows_sha": mp["train_rows_sha"] == mq["train_rows_sha"],
                    "val_rows_sha": mp["val_rows_sha"] == mq["val_rows_sha"],
                    "test_rows_sha": mp["test_rows_sha"] == mq["test_rows_sha"],
                }
                rows.append({
                    "n": n, "fold": fold_idx + 1, "seed": seed,
                    **same,
                    "all_match": all(same.values()),
                })
    return pd.DataFrame(rows)


def per_fit_metrics(seeds) -> pd.DataFrame:
    rows = []
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                for route in CFG.ROUTES:
                    m = load_fit_meta(TR.fit_id(n, fold_idx, seed, route))
                    rows.append(m)
    cols = ["fit_id", "n", "fold", "seed", "route", "converged", "nan_flag",
            "best_epoch", "stopped_epoch", "best_val_loss", "last_train_loss",
            "rrmse_x95", "n_test", "n_nonfinite", "n_illegal", "n_support_viol",
            "runtime_s", "init_param_sha", "batch_order_sha", "network_sha",
            "scaler_sha", "train_rows_sha", "val_rows_sha", "test_rows_sha"]
    return pd.DataFrame(rows)[cols]


def summarize_cells(seeds, metric_col="rrmse_x95") -> pd.DataFrame:
    """逐 (n, seed, fold) P/Q 配对汇总 + pooled。"""
    rows = []
    rel_sq_p_all, rel_sq_q_all = [], []
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                rp, rq = load_rel_sq({
                    "P": TR.fit_id(n, fold_idx, seed, "P"),
                    "Q": TR.fit_id(n, fold_idx, seed, "Q")})
                m = EVAL.bootstrap_ci_paired(rp, rq)
                rows.append(EVAL.summary_row(
                    m, fit_id=f"n{n}_f{fold_idx + 1}_s{seed}",
                    n_val=n, seed=seed, fold=fold_idx + 1, group="cell"))
                rel_sq_p_all.append(rp); rel_sq_q_all.append(rq)
    # pooled
    rp_all = np.concatenate(rel_sq_p_all)
    rq_all = np.concatenate(rel_sq_q_all)
    m_pool = EVAL.bootstrap_ci_paired(rp_all, rq_all)
    rows.append(EVAL.summary_row(m_pool, group="pooled_all_seeds"))
    return pd.DataFrame(rows)


def write_aggregates(seeds, master, run_label=""):
    ensure_dirs()
    pm = per_fit_metrics(seeds)
    pm.to_csv(os.path.join(CFG.ARTIFACT_DIR, "per_fit_metrics.csv"), index=False)
    pr = pairing_report(seeds, master)
    pr.to_csv(os.path.join(CFG.ARTIFACT_DIR, "pairing_report.csv"), index=False)
    sc = summarize_cells(seeds)
    sc.to_csv(os.path.join(CFG.ARTIFACT_DIR, "paired_summary.csv"), index=False)
    splits = write_splits_manifest(master)
    # 运行环境
    env = {"python": sys.version, "torch": _torch_version(), "numpy": np.__version__,
           "pandas": pd.__version__}
    manifest = {
        "run_label": run_label,
        "git_head": _git_short_head(),
        "config_path": "configs/pq-protocol-v1.json",
        "config_sha256": _sha256_file(CFG.CONFIG_PATH),
        "created_at": _now_iso(),
        "seeds": list(seeds),
        "n_fits_expected": len(seeds) * len(CFG.N_GRID) * CFG.N_FOLDS * len(CFG.ROUTES),
        "data_integrity": DATA.verify_integrity(master),
        "env": env,
        "output_files": ["per_fit_metrics.csv", "pairing_report.csv",
                         "paired_summary.csv", "splits_manifest.json",
                         "SHA256SUMS"],
    }
    with open(os.path.join(CFG.ARTIFACT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    _write_sha256sums()
    return manifest


def _torch_version():
    import torch
    return torch.__version__


def _write_sha256sums():
    """对不可变科学产物写 SHA256SUMS（含 gitignore 的逐 fit 预测）。"""
    lines = []
    names = ["per_fit_metrics.csv", "pairing_report.csv", "paired_summary.csv",
             "splits_manifest.json", "manifest.json"]
    for name in names:
        path = os.path.join(CFG.ARTIFACT_DIR, name)
        if os.path.isfile(path):
            lines.append(f"{_sha256_file(path)}  {name}")
    # 逐 fit checkpoint JSON（tracked）与预测（gitignore 但哈希记录）
    for fit in sorted(f[:-5] for f in os.listdir(CFG.CHECKPOINTS_DIR)
                      if f.endswith(".json")):
        lines.append(f"{_sha256_file(checkpoint_json_path(fit))}  checkpoints/{fit}.json")
        if os.path.isfile(prediction_csv_path(fit)):
            lines.append(f"{_sha256_file(prediction_csv_path(fit))}  predictions/{fit}.csv")
    with open(os.path.join(CFG.ARTIFACT_DIR, "SHA256SUMS"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(lines)) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", type=int, default=None)
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--aggregate", action="store_true")
    args = ap.parse_args()

    master = DATA.build_master()
    DATA.verify_integrity(master)

    if args.aggregate:
        seeds = args.seed if args.seed else CFG.SEEDS
        write_aggregates(seeds, master, run_label=f"aggregate_{_git_short_head()}")
        print(f"[pq] aggregates written; seeds={seeds}")
        return

    if not args.seed:
        ap.error("need --seed (or --aggregate)")
    run_fits_for_seeds(args.seed, master, resume=args.resume)
    write_aggregates(args.seed, master, run_label=f"seed{'_'.join(map(str, args.seed))}")


if __name__ == "__main__":
    main()
