"""Study/02 S3 可信性与边界（E1/E2/E3）运行器 + 每根聚合/manifest/SHA。

在 `PQ_PROTOCOL=iid-v1` 下运行（继承同分布主协议设计，`11-PQ-可信性与边界协议.md` +
`configs/pq-s3-boundary-v1.json`）。只训练 Codex mailbox 000016 授权的有限矩阵：

  E1 目标可靠度水平：新训 Q0.90、Q0.99（全 iid 设计，各 60 fits；P/Q0.95 复用 S1）
  E2 网络容量：small 64-32、large 512-256-128（固定 folds {1,3}，P/Q，96 fits）
  E3 域内插值：pq_s3_interp 中确定性重训 120 基线 P/Q fits + 中点样本评价（120 fits）

产物根（互不覆盖）：artifacts/pq_s3_target、artifacts/pq_s3_capacity、
artifacts/pq_s3_interp。绝不写入 pq_iid_main / pq_v3 / pq_v2 / 历史证据。

用法（cwd = code/；PQ_PROTOCOL=iid-v1）：
    python -m study02pq.s3_boundary --e1 --seed 42 --seed 2026 --seed 3407
    python -m study02pq.s3_boundary --e2 --seed 42 --seed 2026 --seed 3407
    python -m study02pq.s3_boundary --e3 --seed 42 --seed 2026 --seed 3407
    python -m study02pq.s3_boundary --e1 --e2 --e3 --seed 42 --seed 2026 --seed 3407
    python -m study02pq.s3_boundary --aggregate       # 重写各根 manifest/SHA（幂等）
    python -m study02pq.s3_boundary --smoke           # 缩小设计生产路径 smoke（临时根）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import losses as LOSS  # noqa: E402
from study02pq import model as MODEL  # noqa: E402
from study02pq import run as RUN  # noqa: E402
from study02pq import training as TR  # noqa: E402

assert CFG.PROTOCOL_VERSION == "iid-v1", "s3_boundary 必须在 PQ_PROTOCOL=iid-v1 下运行"

S3_CFG_PATH = os.path.join(CFG.STUDY02_ROOT, "configs", "pq-s3-boundary-v1.json")
S3_PROTOCOL_PATH = os.path.join(CFG.STUDY02_ROOT, "11-PQ-可信性与边界协议.md")

S1_EVIDENCE_DIR = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_iid_main", "evidence")
# S3 产物根（与 S1/S2 的 pq_iid_main 隔离）
ART_ROOTS = {
    "target": os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_target"),
    "capacity": os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_capacity"),
    "interp": os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_interp"),
}

_log_paths: list[str] = []


def _log(msg: str):
    print(msg, flush=True)
    for p in _log_paths:
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError:
            pass


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _git_full_head():
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def load_s3_config() -> dict:
    with open(S3_CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


S3CFG = load_s3_config()


def _redirect(root: str):
    """把产物路径切到给定根（幂等；绝不触碰 pq_iid_main）。"""
    CFG.ARTIFACT_DIR = root
    CFG.PREDICTIONS_DIR = os.path.join(root, "predictions")
    CFG.CHECKPOINTS_DIR = os.path.join(root, "fit_metadata")
    CFG.EVIDENCE_DIR = os.path.join(root, "evidence")
    CFG.SPLITS_MANIFEST_PATH = os.path.join(root, "splits_manifest.json")
    for d in (CFG.ARTIFACT_DIR, CFG.PREDICTIONS_DIR, CFG.CHECKPOINTS_DIR,
              CFG.EVIDENCE_DIR, os.path.join(root, "interp"),
              os.path.join(root, "analysis")):
        os.makedirs(d, exist_ok=True)


def _start_log(root: str):
    _log_paths.clear()
    p = os.path.join(root, "run_all_seeds.log")
    _log_paths.append(p)
    open(p, "a", encoding="utf-8").close()


# ----------------------------------------------------------------------
# E1 目标可靠度水平（Q0.90 / Q0.99）
# ----------------------------------------------------------------------

def run_e1(seeds, resume=True):
    root = ART_ROOTS["target"]
    _redirect(root)
    _start_log(root)
    targets = [float(p) for p in S3CFG["target_levels"]["train_new"]]
    done, skipped = 0, 0
    for p in targets:
        route = f"Q{int(round(p * 100))}"
        for n in CFG.N_GRID:
            for fold_idx in range(CFG.N_FOLDS):
                for seed in seeds:
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    if resume and RUN.fit_complete(fit):
                        skipped += 1
                        continue
                    _log(f"[s3/e1] train {fit} (R={p}) ...")
                    result = TR.train_one_fit(
                        n, fold_idx, seed, route, master, target_R=p,
                        split_strategy=CFG.SPLIT_STRATEGY)
                    RUN.save_fit(fit, result)
                    done += 1
    _log(f"[s3/e1] done={done} skipped={skipped} (new fits: Q90/Q99 x 4n x 5fold x {len(seeds)}seed)")


# ----------------------------------------------------------------------
# E2 网络容量（small 64-32 / large 512-256-128，folds {1,3}）
# ----------------------------------------------------------------------

def run_e2(seeds, resume=True):
    root = ART_ROOTS["capacity"]
    _redirect(root)
    _start_log(root)
    caps = S3CFG["capacity"]
    folds_1b = [int(f) for f in caps["folds_1based"]]
    variants = (("sm64", tuple(caps["small"])), ("lg512", tuple(caps["large"])))
    done, skipped = 0, 0
    for label, hidden in variants:
        for fold_idx in [f - 1 for f in folds_1b]:
            for n in CFG.N_GRID:
                for seed in seeds:
                    for route in CFG.ROUTES:
                        suffix = f"_{label}"
                        fit = TR.fit_id(n, fold_idx, seed, route, suffix)
                        if resume and RUN.fit_complete(fit):
                            skipped += 1
                            continue
                        _log(f"[s3/e2] train {fit} (hidden={hidden}) ...")
                        result = TR.train_one_fit(
                            n, fold_idx, seed, route, master, hidden=hidden,
                            fit_suffix=suffix, split_strategy=CFG.SPLIT_STRATEGY)
                        RUN.save_fit(fit, result)
                        done += 1
    _log(f"[s3/e2] done={done} skipped={skipped} "
         f"(2 caps x {len(CFG.N_GRID)}n x {len(folds_1b)}fold x {len(seeds)}seed x 2route)")


# ----------------------------------------------------------------------
# E3 域内插值：pq_s3_interp 中确定性重训 120 基线 fits + 中点样本评价
# ----------------------------------------------------------------------

def build_interp_master() -> tuple[np.ndarray, np.ndarray]:
    """确定性中点插值样本主表。键 (beta_mid, goe_mid, n, repeat_id)。"""
    ip = S3CFG["interpolation"]
    beta_mids = [float(b) for b in ip["beta_midpoints"]]
    gamma_list = [float(g) for g in ip["gamma"]]
    eta = float(ip["eta"])
    n_grid = [int(v) for v in CFG.N_GRID]
    repeats = int(ip["repeats_per_combo"])
    ns = ip["namespace"]
    keys, X_list = [], []
    for beta in beta_mids:
        for gamma in gamma_list:
            goe = gamma / eta
            for n in n_grid:
                for rid in range(repeats):
                    s = DATA.generate_sample(float(beta), float(eta), float(gamma),
                                             int(n), int(rid), seed=ns)
                    s = np.asarray(s, dtype=np.float64)
                    keys.append((float(beta), float(goe), float(n), int(rid)))
                    X_list.append(s)
    keys = np.asarray(keys, dtype=np.float64)
    X = np.empty(len(X_list), dtype=object)
    for i, s in enumerate(X_list):
        X[i] = s
    return keys, X


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _interp_rows_for_n(keys_i, X_i, n: int):
    n_mask = keys_i[:, 2].astype(np.int64) == int(n)
    idx = np.flatnonzero(n_mask)
    X_n = np.zeros((len(idx), int(n)), dtype=np.float64)
    min_x = np.zeros(len(idx), dtype=np.float64)
    for j, r in enumerate(idx):
        s = X_i[int(r)]
        X_n[j] = s
        min_x[j] = s.min()
    return idx, X_n, min_x, n_mask


def eval_interp(model_state, n: int, seed: int, keys_i, X_i, scaler) -> dict:
    """用 best state 在插值样本（该 n 的 8400 行）上评价，返回预测数组。

    scaler 按 S1 合同只 fit 该 (n, fold) 的 train 行，由调用方传入经过校验的
    scaler（见 run_e3）；推理前必须先 scaler.transform(X_n)，模型只接收标准化
    输入（与 training 合同一致，否则原始 ~eta 量级输入直接进入网络）。模型结构
    = CFG.HIDDEN_LAYERS（E3 基线容量）。
    """
    idx, X_n, min_x, _ = _interp_rows_for_n(keys_i, X_i, n)
    X_n_s = scaler.transform(X_n)
    model = MODEL.build_model(n, seed)
    model.load_state_dict(model_state)
    model.eval()
    with torch.no_grad():
        out = model(torch.tensor(X_n_s, dtype=torch.float64))
        b_hat, e_hat, g_hat = LOSS.decode_params(
            out, torch.tensor(min_x, dtype=torch.float64))
        x95_hat = LOSS.weibull_quantile(b_hat, e_hat, g_hat).numpy()
        b_hat = b_hat.numpy(); e_hat = e_hat.numpy(); g_hat = g_hat.numpy()
    keys = keys_i[idx]
    beta = keys[:, 0]; goe = keys[:, 1]
    gamma = goe * CFG.ETA
    x95_true = gamma + CFG.ETA * (-np.log(CFG.X0_95_R)) ** (1.0 / beta)
    rel_err = (x95_hat - x95_true) / x95_true
    return {
        "keys_beta": np.ascontiguousarray(beta, dtype=np.float64),
        "keys_gamma_over_eta": np.ascontiguousarray(goe, dtype=np.float64),
        "keys_n": np.ascontiguousarray(keys[:, 2], dtype=np.int32),
        "keys_repeat_id": np.ascontiguousarray(keys[:, 3], dtype=np.int32),
        "beta_hat": b_hat.astype(np.float32), "eta_hat": e_hat.astype(np.float32),
        "gamma_hat": g_hat.astype(np.float32), "min_x": min_x.astype(np.float32),
        "x95_hat": x95_hat.astype(np.float32), "x95_true": x95_true.astype(np.float32),
        "rel_err": rel_err.astype(np.float32), "rel_err_sq": (rel_err ** 2).astype(np.float32),
    }


def run_e3(seeds, resume=True):
    root = ART_ROOTS["interp"]
    _redirect(root)
    _start_log(root)
    keys_i, X_i = build_interp_master()
    ip = S3CFG["interpolation"]
    expected = int(len(keys_i))
    assert expected == int(ip["n_samples"]), (expected, ip["n_samples"])
    _log(f"[s3/e3] interpolation master: {expected} midpoint samples "
         f"(7 beta-mid x 4 goe-mid x 4 n x {ip['repeats_per_combo']} repeats)")

    # scaler 只 fit 该 (n, fold) 的 train 行（S1 合同）；校验后复用于插值评价
    scalers = {}
    done, skipped = 0, 0
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            tr, _, _ = DATA.split_repeat_fold(master, n, fold_idx)
            X_tr, _, _ = DATA.make_arrays(master, tr)
            scalers[(n, fold_idx)] = DATA.PerPositionScaler().fit(X_tr)
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                for route in CFG.ROUTES:
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    interp_path = os.path.join(root, "interp", f"{fit}.npz")
                    if resume and RUN.fit_complete(fit) and os.path.isfile(interp_path):
                        skipped += 1
                        continue
                    _log(f"[s3/e3] train {fit} (baseline retrain, interp root) ...")
                    result = TR.train_one_fit(
                        n, fold_idx, seed, route, master,
                        split_strategy=CFG.SPLIT_STRATEGY, return_state=True)
                    # scaler 校验（必须与 fit meta 一致）
                    scaler = scalers[(n, fold_idx)]
                    assert scaler.params_sha() == result["meta"]["scaler_sha"], \
                        f"scaler mismatch for {fit}"
                    RUN.save_fit(fit, result)
                    # 插值评价（best state；scaler 按该 (n, fold) 训练折，eval_interp
                    # 内部先 transform 再喂模型）
                    ipred = eval_interp(result["model_state"], n, seed, keys_i, X_i,
                                        scalers[(n, fold_idx)])
                    assert len(ipred["x95_true"]) == int(
                        ip["repeats_per_combo"]) * len(ip["beta_midpoints"]) * len(
                        ip["gamma"]), len(ipred["x95_true"])
                    np.savez_compressed(interp_path, **ipred)
                    done += 1
    _log(f"[s3/e3] done={done} skipped={skipped} (120 baseline retrains + interp eval)")
    _log("[s3/e3] verifying byte-identity of retrained iid-test evidence vs S1 ...")
    n_ident = 0
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                for route in CFG.ROUTES:
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    a = _sha_bytes(open(os.path.join(root, "evidence", f"{fit}.npz"),
                                        "rb").read())
                    b = _sha_bytes(open(os.path.join(S1_EVIDENCE_DIR, f"{fit}.npz"),
                                        "rb").read())
                    if a != b:
                        raise AssertionError(f"S3 retrain evidence differs from S1: {fit}")
                    n_ident += 1
    _log(f"[s3/e3] EVIDENCE IDENTITY PASS: {n_ident}/120 retrained iid-test evidence "
         f"byte-identical to S1 pq_iid_main")


# ----------------------------------------------------------------------
# 每根聚合：per_fit_metrics / manifest / SHA256SUMS
# ----------------------------------------------------------------------

TEXT_EXTS = {".json", ".csv", ".md", ".txt", ".log", ".sha256"}


def _canonical(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        data = f.read()
    if ext in TEXT_EXTS:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _per_fit_metrics_from_disk(root: str) -> pd.DataFrame:
    md = os.path.join(root, "fit_metadata")
    rows = []
    for f in sorted(os.listdir(md)):
        if f.endswith(".json"):
            with open(os.path.join(md, f), encoding="utf-8") as fh:
                rows.append(json.load(fh))
    cols = ["fit_id", "n", "fold", "seed", "route", "converged", "nan_flag",
            "best_epoch", "stopped_epoch", "best_val_loss", "last_train_loss",
            "rrmse_x95", "n_test", "n_nonfinite", "n_illegal", "n_support_viol",
            "support_legality_ok", "sample_bytes_sha", "evidence_sha256",
            "runtime_s", "init_param_sha", "batch_order_sha", "network_sha",
            "scaler_sha", "train_rows_sha", "val_rows_sha", "test_rows_sha",
            "target_R", "hidden_layers", "split_strategy"]
    if rows:
        return pd.DataFrame(rows)[[c for c in cols if c in rows[0]]]
    return pd.DataFrame(columns=cols)


def _sha256sums(root: str):
    lines = []
    for name in ("per_fit_metrics.csv", "manifest.json", "run_all_seeds.log"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            lines.append(f"{_canonical(p)}  {name}")
    for sub, ext in (("fit_metadata", ".json"), ("evidence", ".npz"), ("interp", ".npz")):
        d = os.path.join(root, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(ext):
                    lines.append(f"{_canonical(os.path.join(d, f))}  {sub}/{f}")
    adir = os.path.join(root, "analysis")
    if os.path.isdir(adir):
        for f in sorted(os.listdir(adir)):
            p = os.path.join(adir, f)
            if os.path.isfile(p):
                lines.append(f"{_canonical(p)}  analysis/{f}")
    with open(os.path.join(root, "SHA256SUMS"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(lines)) + "\n")


def _study01_input_shas() -> dict:
    s01 = {}
    for key, rel in CFG.STUDY01_ALIGN.items():
        if isinstance(rel, str) and rel.endswith((".py", ".csv", ".json", ".txt")):
            p = CFG.study01_abs_path(rel)
            if os.path.isfile(p):
                s01[key] = _canonical(p)
    return s01


def _analysis_sha(root: str) -> dict:
    out = {}
    adir = os.path.join(root, "analysis")
    if os.path.isdir(adir):
        for f in sorted(os.listdir(adir)):
            p = os.path.join(adir, f)
            if os.path.isfile(p):
                out[f] = _canonical(p)
    return out


def aggregate_roots(seeds):
    head = _git_full_head()
    for key, root in ART_ROOTS.items():
        if not os.path.isdir(root):
            continue
        pm = _per_fit_metrics_from_disk(root)
        if len(pm):
            pm.to_csv(os.path.join(root, "per_fit_metrics.csv"), index=False)
        env_lock = os.path.join(CFG.STUDY02_ROOT, "configs", "pq-environment-v2.json")
        run_log = os.path.join(root, "run_all_seeds.log")
        interp_sha = None
        ip = os.path.join(root, "interp")
        if os.path.isdir(ip) and os.listdir(ip):
            # 插值样本字节流 SHA：按 interp 证据键序重算（确定性）
            keys_i, X_i = build_interp_master()
            buf = np.concatenate([X_i[int(r)] for r in range(len(X_i))])
            interp_sha = _sha_bytes(np.ascontiguousarray(buf, dtype=np.float64).tobytes())
        manifest = {
            "protocol": os.path.basename(S3_CFG_PATH),
            "protocol_version": "s3-boundary-v1",
            "inherits": "configs/pq-iid-protocol-v1.json",
            "artifact_root": key,
            "run_label": f"aggregate_{head[:7]}",
            "git_full_sha": head,
            "git_head_short": head[:7],
            "run_code_sha": head,          # 执行提交 == 实现提交（训练在冻结实现提交上运行）
            "config_sha256": _canonical(S3_CFG_PATH),
            "inherited_iid_config_sha256": _canonical(
                os.path.join(CFG.STUDY02_ROOT, "configs", "pq-iid-protocol-v1.json")),
            "protocol_sha256": _canonical(S3_PROTOCOL_PATH),
            "env_lock": "configs/pq-environment-v2.json",
            "env_lock_sha256": (_canonical(env_lock) if os.path.isfile(env_lock) else None),
            "study01_input_shas": _study01_input_shas(),
            "main_sample_bytes_sha": DATA.sample_bytes_sha(master, np.arange(len(master.keys))),
            "interp_sample_bytes_sha": interp_sha,
            "analysis_sha256": _analysis_sha(root),
            "run_all_seeds_log_sha256": (_canonical(run_log) if os.path.isfile(run_log) else None),
            "sha256_rule": "tracked files only; text LF-normalized; .npz binary raw",
            "created_at": _now_iso(),
            "seeds": list(seeds),
            "n_fits_expected": S3CFG["fit_counts"][
                "E1_target_levels" if key == "target"
                else "E2_capacity" if key == "capacity" else "E3_interpolation"],
            "data_integrity": DATA.verify_integrity(master),
            "output_files": ["per_fit_metrics.csv", "manifest.json", "SHA256SUMS",
                             "run_all_seeds.log", "fit_metadata/<fit_id>.json",
                             "evidence/<fit_id>.npz"]
                             + (["interp/<fit_id>.npz"] if interp_sha else [])
                             + ["analysis/<summary files>"],
        }
        with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        _sha256sums(root)
        print(f"[s3/aggregate] {key}: manifest + SHA256SUMS written "
              f"(fits={len(pm)})", flush=True)


# ----------------------------------------------------------------------
# smoke（生产路径，缩小设计，全部产物进系统临时目录）
# ----------------------------------------------------------------------

def _smoke():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="pq_s3_smoke_")
    print(f"[s3/smoke] temp roots -> {tmp}", flush=True)
    global master, ART_ROOTS
    # 缩小设计（与 smoke_iid 一致：beta 2/3, gamma 全, n 7/10, repeats 15）
    small_master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                                     n_grid=[7, 10], repeats=15)
    _orig_cfg = (CFG.MAX_EPOCHS, CFG.PATIENCE, CFG.N_GRID, CFG.REPEATS)
    CFG.MAX_EPOCHS, CFG.PATIENCE, CFG.N_GRID, CFG.REPEATS = 6, 3, [7, 10], 15
    master = small_master
    # run_e1/e2/e3 生产路径内部用 ART_ROOTS[...] 自行 _redirect；smoke 必须把
    # ART_ROOTS 整体指向临时根，否则会写进真实封存根（此前 E1 smoke 曾因此把
    # 20 fits 写入真实 pq_s3_target，留下需手工删除的“部分运行”残留）。
    _orig_roots = ART_ROOTS
    try:
        ART_ROOTS = {"target": os.path.join(tmp, "target"),
                     "capacity": os.path.join(tmp, "capacity"),
                     "interp": os.path.join(tmp, "interp")}
        for r in ART_ROOTS.values():
            os.makedirs(r, exist_ok=True)
        # E1 smoke：Q0.90+Q0.99（单 seed）
        run_e1([42], resume=True)
        n_e1 = len([f for f in os.listdir(CFG.EVIDENCE_DIR) if f.endswith(".npz")])
        assert n_e1 == 2 * len(CFG.N_GRID) * CFG.N_FOLDS, n_e1  # 2 targets x 2n x 5fold x 1seed
        print(f"[s3/smoke] E1 smoke PASS: {n_e1} target fits (Q0.90 + Q0.99)")
        # E2 smoke：单容量 small（folds 1,3）
        root = ART_ROOTS["capacity"]
        _redirect(root)
        _run_e2_smoke([42])
        n_e2 = len([f for f in os.listdir(CFG.EVIDENCE_DIR) if f.endswith(".npz")])
        assert n_e2 == len(CFG.N_GRID) * 2 * 2, n_e2  # 1 cap x 2n x 2fold x 1seed x 2route
        print(f"[s3/smoke] E2 smoke PASS: {n_e2} capacity fits")
        # E3 smoke：基线重训 + 插值评价（单 seed）
        root = ART_ROOTS["interp"]
        _redirect(root)
        _run_e3_smoke([42])
        n_e3 = len([f for f in os.listdir(CFG.EVIDENCE_DIR) if f.endswith(".npz")])
        n_ip = len([f for f in os.listdir(os.path.join(root, "interp"))
                    if f.endswith(".npz")])
        assert n_e3 == 2 * len(CFG.N_GRID) * CFG.N_FOLDS, n_e3
        assert n_ip == n_e3, (n_ip, n_e3)
        print(f"[s3/smoke] E3 smoke PASS: {n_e3} baseline retrains + {n_ip} interp evals")
    finally:
        CFG.MAX_EPOCHS, CFG.PATIENCE, CFG.N_GRID, CFG.REPEATS = _orig_cfg
        ART_ROOTS = _orig_roots
    print("[s3/smoke] SMOKE PASS (s3-boundary)")


def _run_e2_smoke(seeds):
    caps = S3CFG["capacity"]
    folds_1b = [int(f) for f in caps["folds_1based"]]
    for label, hidden in (("sm64", tuple(caps["small"])),):
        for fold_idx in [f - 1 for f in folds_1b]:
            for n in CFG.N_GRID:
                for seed in seeds:
                    for route in CFG.ROUTES:
                        suffix = f"_{label}"
                        fit = TR.fit_id(n, fold_idx, seed, route, suffix)
                        result = TR.train_one_fit(n, fold_idx, seed, route, master,
                                                  hidden=hidden, fit_suffix=suffix,
                                                  split_strategy=CFG.SPLIT_STRATEGY)
                        RUN.save_fit(fit, result)


def _run_e3_smoke(seeds):
    keys_i, X_i = build_interp_master()
    scalers = {}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            tr, _, _ = DATA.split_repeat_fold(master, n, fold_idx)
            X_tr, _, _ = DATA.make_arrays(master, tr)
            scalers[(n, fold_idx)] = DATA.PerPositionScaler().fit(X_tr)
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                for route in CFG.ROUTES:
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    result = TR.train_one_fit(n, fold_idx, seed, route, master,
                                              split_strategy=CFG.SPLIT_STRATEGY,
                                              return_state=True)
                    scaler = scalers[(n, fold_idx)]
                    assert scaler.params_sha() == result["meta"]["scaler_sha"]
                    RUN.save_fit(fit, result)
                    ipred = eval_interp(result["model_state"], n, seed, keys_i, X_i,
                                        scalers[(n, fold_idx)])
                    np.savez_compressed(os.path.join(CFG.ARTIFACT_DIR, "interp",
                                                     f"{fit}.npz"), **ipred)


# 正式 master（模块级，供 runner 使用）。测试可用 PQ_S3_SKIP_MASTER=1 快速导入，
# 由测试自行构建缩小 master；生产路径（未设该变量）在导入时构建 48,000 样本主表。
if os.environ.get("PQ_S3_SKIP_MASTER"):
    master = None
else:
    master = DATA.build_master()


def main():
    global master
    ap = argparse.ArgumentParser()
    ap.add_argument("--e1", action="store_true")
    ap.add_argument("--e2", action="store_true")
    ap.add_argument("--e3", action="store_true")
    ap.add_argument("--seed", action="append", type=int, default=None)
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seed] if args.seed else [int(s) for s in CFG.SEEDS]

    if args.smoke:
        _smoke()
        return
    if args.aggregate:
        aggregate_roots(seeds)
        return
    if not (args.e1 or args.e2 or args.e3):
        ap.error("need --e1/--e2/--e3 (or --aggregate / --smoke)")

    master = DATA.build_master()
    DATA.verify_integrity(master)
    if args.e1:
        run_e1(seeds, resume=True)
    if args.e2:
        run_e2(seeds, resume=True)
    if args.e3:
        run_e3(seeds, resume=True)
    aggregate_roots(seeds)
    print("[s3] runs complete; per-root manifest + SHA256SUMS written", flush=True)


if __name__ == "__main__":
    main()
