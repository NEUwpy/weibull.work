"""Study/02 P-Q v2 正式运行器：可续接逐 fit 训练、配对验证、汇总与 manifest。

证据策略（协议 v2 §9，Codex R1 REVISE 修正）：
- evidence/<fit_id>.npz（float32 压缩逐样本证据，tracked）→ 干净 clone 可获取/校验/重算；
- fit_metadata/<fit_id>.json（fit 元数据：无模型 state，含确定性命约 + 全部配对 SHA，
  tracked）；
- predictions/<fit_id>.csv（完整精度 CSV，gitignore，仅本机计算用；SHA 不入 SHA256SUMS，
  因干净 clone 无此文件）；
- SHA256SUMS 只列 tracked 文件（evidence / fit_metadata / 汇总 / manifest / splits）。

用法：
    python code/study02pq/run.py --seed 42
    python code/study02pq/run.py --seed 2026 --seed 3407
    python code/study02pq/run.py --seed 42 --resume
    python code/study02pq/run.py --aggregate
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


def _git_full_head():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=CFG.PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure_dirs():
    for d in (CFG.ARTIFACT_DIR, CFG.PREDICTIONS_DIR, CFG.CHECKPOINTS_DIR,
              CFG.EVIDENCE_DIR):
        os.makedirs(d, exist_ok=True)


def prediction_csv_path(fit: str) -> str:
    return os.path.join(CFG.PREDICTIONS_DIR, f"{fit}.csv")


def metadata_json_path(fit: str) -> str:
    return os.path.join(CFG.CHECKPOINTS_DIR, f"{fit}.json")


def evidence_npz_path(fit: str) -> str:
    return os.path.join(CFG.EVIDENCE_DIR, f"{fit}.npz")


def fit_complete(fit: str) -> bool:
    return (os.path.isfile(metadata_json_path(fit))
            and os.path.isfile(evidence_npz_path(fit)))


def save_fit(fit: str, result: dict):
    p = result["predictions"]
    keys = p["keys"]
    df = pd.DataFrame({
        "beta": keys[:, 0], "gamma_over_eta": keys[:, 1], "n": keys[:, 2],
        "repeat_id": keys[:, 3].astype(int),
        "beta_hat": p["beta_hat"], "eta_hat": p["eta_hat"], "gamma_hat": p["gamma_hat"],
        "x95_hat": p["x95_hat"], "x95_true": p["x95_true"],
        "min_x": p["min_x"],
        "rel_err": p["rel_err"], "rel_err_sq": p["rel_err_sq"],
        "rel_b": p["rel_b"], "rel_e": p["rel_e"], "rel_g": p["rel_g"],
    })
    # 完整精度 CSV（gitignore，本机计算用）
    df.to_csv(prediction_csv_path(fit), index=False)
    # 压缩逐样本证据（tracked）
    np.savez_compressed(
        evidence_npz_path(fit),
        keys=keys.astype(np.int32),
        beta_hat=p["beta_hat"].astype(np.float32),
        eta_hat=p["eta_hat"].astype(np.float32),
        gamma_hat=p["gamma_hat"].astype(np.float32),
        x95_hat=p["x95_hat"].astype(np.float32),
        x95_true=p["x95_true"].astype(np.float32),
        min_x=p["min_x"].astype(np.float32),
        rel_err=p["rel_err"].astype(np.float32),
        rel_err_sq=p["rel_err_sq"].astype(np.float32),
    )
    meta = dict(result["meta"])
    meta["predictions_sha256"] = _sha256_file(prediction_csv_path(fit))
    meta["evidence_sha256"] = _sha256_file(evidence_npz_path(fit))
    meta["git_full_sha"] = _git_full_head()
    with open(metadata_json_path(fit), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


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


def load_evidence(fit: str) -> dict:
    d = np.load(evidence_npz_path(fit))
    return {k: d[k] for k in d.files}


def load_rel_sq_from_evidence(fit_p: str, fit_q: str) -> tuple[np.ndarray, np.ndarray]:
    ep = load_evidence(fit_p)
    eq = load_evidence(fit_q)
    kp = ep["keys"].view(np.int32).reshape(-1, 4)
    kq = eq["keys"].view(np.int32).reshape(-1, 4)
    # 对齐到相同测试行
    assert kp.shape == kq.shape and len(kp) == len(kq)
    assert np.array_equal(kp, kq), f"P/Q evidence keys mismatch for {fit_p}/{fit_q}"
    return ep["rel_err_sq"], eq["rel_err_sq"]


def write_splits_manifest(master):
    rec = {"generated_at": _now_iso(), "git_head": _git_full_head(),
           "split_rule": "combo_idx % 5 == fold_idx; combos=product(beta,goe,n)",
           "validation": {"fraction": CFG.VAL_FRACTION, "salt": CFG.VAL["salt"]},
           "folds": {}}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            tr, va, te = DATA.split_fold(master, n, fold_idx)
            rec["folds"][f"n{n}_f{fold_idx + 1}"] = {
                "train_rows_sha": DATA.sha_rows(tr),
                "val_rows_sha": DATA.sha_rows(va),
                "test_rows_sha": DATA.sha_rows(te),
                "test_sample_bytes_sha": DATA.sample_bytes_sha(master, te),
                "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
            }
    with open(CFG.SPLITS_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def load_fit_meta(fit: str) -> dict:
    with open(metadata_json_path(fit), encoding="utf-8") as f:
        return json.load(f)


def pairing_report(seeds, master) -> pd.DataFrame:
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
                    **same, "all_match": all(same.values()),
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
            "support_legality_ok", "sample_bytes_sha", "evidence_sha256",
            "runtime_s", "init_param_sha", "batch_order_sha", "network_sha",
            "scaler_sha", "train_rows_sha", "val_rows_sha", "test_rows_sha"]
    return pd.DataFrame(rows)[cols]


def write_aggregates(seeds, master, run_label=""):
    ensure_dirs()
    pm = per_fit_metrics(seeds)
    pm.to_csv(os.path.join(CFG.ARTIFACT_DIR, "per_fit_metrics.csv"), index=False)
    pr = pairing_report(seeds, master)
    pr.to_csv(os.path.join(CFG.ARTIFACT_DIR, "pairing_report.csv"), index=False)
    splits = write_splits_manifest(master)

    # 环境锁
    env_lock = os.path.join(CFG.STUDY02_ROOT, "configs", "pq-environment-v2.json")
    # Study01 输入 SHA（协议 §0）
    s01 = {}
    for key, rel in CFG.STUDY01_ALIGN.items():
        if isinstance(rel, str) and rel.endswith((".py", ".csv", ".json", ".txt")):
            p = CFG.study01_abs_path(rel)
            if os.path.isfile(p):
                s01[key] = _sha256_file(p)

    manifest = {
        "protocol": "pq-protocol-v2.json",
        "run_label": run_label,
        "git_full_sha": _git_full_head(),
        "git_head_short": _git_full_head()[:7],
        "config_sha256": _sha256_file(CFG.CONFIG_PATH),
        "protocol_sha256": _sha256_file(CFG.PROTOCOL_PATH),
        "env_lock": "configs/pq-environment-v2.json",
        "env_lock_sha256": _sha256_file(env_lock) if os.path.isfile(env_lock) else None,
        "study01_input_shas": s01,
        "main_sample_bytes_sha": DATA.sample_bytes_sha(master, np.arange(len(master.keys))),
        "created_at": _now_iso(),
        "seeds": list(seeds),
        "n_fits_expected": len(seeds) * len(CFG.N_GRID) * CFG.N_FOLDS * len(CFG.ROUTES),
        "data_integrity": DATA.verify_integrity(master),
        "output_files": ["per_fit_metrics.csv", "pairing_report.csv",
                         "splits_manifest.json", "SHA256SUMS",
                         "evidence/<fit_id>.npz", "fit_metadata/<fit_id>.json"],
    }
    with open(os.path.join(CFG.ARTIFACT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    _write_sha256sums()
    return manifest


def _write_sha256sums():
    """只列 tracked 文件（干净 clone 可获得）。predictions/*.csv 不入列。"""
    lines = []
    names = ["per_fit_metrics.csv", "pairing_report.csv", "splits_manifest.json",
             "manifest.json"]
    for name in names:
        path = os.path.join(CFG.ARTIFACT_DIR, name)
        if os.path.isfile(path):
            lines.append(f"{_sha256_file(path)}  {name}")
    for fit in sorted(f[:-5] for f in os.listdir(CFG.CHECKPOINTS_DIR)
                      if f.endswith(".json")):
        lines.append(f"{_sha256_file(metadata_json_path(fit))}  fit_metadata/{fit}.json")
    for fit in sorted(f[:-4] for f in os.listdir(CFG.EVIDENCE_DIR)
                      if f.endswith(".npz")):
        lines.append(f"{_sha256_file(evidence_npz_path(fit))}  evidence/{fit}.npz")
    for name in ("analysis",):
        adir = os.path.join(CFG.ARTIFACT_DIR, name)
        if os.path.isdir(adir):
            for f in sorted(os.listdir(adir)):
                p = os.path.join(adir, f)
                if os.path.isfile(p):
                    lines.append(f"{_sha256_file(p)}  {name}/{f}")
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
        write_aggregates(seeds, master, run_label=f"aggregate_{_git_full_head()[:7]}")
        print(f"[pq] aggregates written; seeds={seeds}")
        return

    if not args.seed:
        ap.error("need --seed (or --aggregate)")
    run_fits_for_seeds(args.seed, master, resume=args.resume)
    write_aggregates(args.seed, master, run_label=f"seed{'_'.join(map(str, args.seed))}")


if __name__ == "__main__":
    main()
