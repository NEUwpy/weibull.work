"""B5 真值点敏感度矩阵最小 pilot：24 个新增 M95 fits。

必须在 ``PQ_PROTOCOL=iid-v1`` 下运行。既有 P/Q 证据只读复用，新产物隔离写入
``artifacts/pq_target_matrix_pilot``。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as CFG
from . import data as DATA
from . import run as RUN
from . import training as TR

assert CFG.PROTOCOL_VERSION == "iid-v1", \
    "target_matrix_pilot 必须设置 PQ_PROTOCOL=iid-v1"

CONFIG_PATH = Path(CFG.STUDY02_ROOT) / "configs" / "pq-target-matrix-pilot-v1.json"
PROTOCOL_PATH = Path(CFG.STUDY02_ROOT) / "protocols" / "10-目标敏感度矩阵研究合同.md"
ART_ROOT = Path(CFG.STUDY02_ROOT) / "artifacts" / "pq_target_matrix_pilot"
SOURCE_ROOT = Path(CFG.STUDY02_ROOT) / "artifacts" / "pq_iid_main"
CODE_PATH = Path(__file__)
ENV_PATH = Path(CFG.STUDY02_ROOT) / "configs" / "pq-environment-v2.json"


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


PILOT = _load_config()
SEEDS = [int(v) for v in PILOT["design"]["seeds"]]
FOLDS = [int(v) - 1 for v in PILOT["design"]["folds_1based"]]
TARGET_R = float(PILOT["target"]["reliability_R"])
PAIR_FIELDS = ("init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
               "train_rows_sha", "val_rows_sha", "test_rows_sha", "sample_bytes_sha")
IMPLEMENTATION_PATHS = {
    "pilot": CODE_PATH,
    "losses": Path(CFG.STUDY02_ROOT) / "code" / "study02pq" / "losses.py",
    "training": Path(CFG.STUDY02_ROOT) / "code" / "study02pq" / "training.py",
    "model": Path(CFG.STUDY02_ROOT) / "code" / "study02pq" / "model.py",
    "data": Path(CFG.STUDY02_ROOT) / "code" / "study02pq" / "data.py",
    "run": Path(CFG.STUDY02_ROOT) / "code" / "study02pq" / "run.py",
    "active_config": Path(CFG.CONFIG_PATH),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT).decode().strip()


def _sha(path: Path) -> str:
    return RUN.sha256_file_canonical(str(path))


def _raw_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _implementation_shas() -> dict[str, str]:
    return {name: _sha(path) for name, path in IMPLEMENTATION_PATHS.items()}


def _assert_frozen_implementation() -> None:
    """正式运行代码/合同必须已跟踪且相对 HEAD 无 diff；允许产物目录在续接时 dirty。"""
    project = Path(CFG.PROJECT_ROOT).resolve()
    paths = [Path(path).resolve().relative_to(project).as_posix()
             for path in (*IMPLEMENTATION_PATHS.values(), CONFIG_PATH, PROTOCOL_PATH)]
    for path in paths:
        subprocess.check_call(["git", "ls-files", "--error-unmatch", path],
                              cwd=CFG.PROJECT_ROOT, stdout=subprocess.DEVNULL)
    for cached in (False, True):
        cmd = ["git", "diff", "--quiet"]
        if cached:
            cmd.append("--cached")
        cmd.extend(["HEAD", "--", *paths])
        if subprocess.call(cmd, cwd=CFG.PROJECT_ROOT) != 0:
            raise RuntimeError("matrix implementation/config/protocol must match committed HEAD before training")


def _redirect(root: Path) -> None:
    CFG.ARTIFACT_DIR = str(root)
    CFG.PREDICTIONS_DIR = str(root / "predictions")
    CFG.CHECKPOINTS_DIR = str(root / "fit_metadata")
    CFG.EVIDENCE_DIR = str(root / "evidence")
    CFG.SPLITS_MANIFEST_PATH = str(root / "splits_manifest.json")
    for path in (root, root / "predictions", root / "fit_metadata",
                 root / "evidence", root / "analysis"):
        path.mkdir(parents=True, exist_ok=True)


def _source_meta(n: int, fold_idx: int, seed: int, route: str) -> dict:
    fit = TR.fit_id(n, fold_idx, seed, route)
    path = SOURCE_ROOT / "fit_metadata" / f"{fit}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _source_sha_map() -> dict[str, str]:
    mapping = {}
    for line in (SOURCE_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(maxsplit=1)
        mapping[rel.replace("\\", "/")] = digest
    return mapping


def _audit_evidence(ev: dict) -> tuple[int, int, int]:
    fields = ("beta_hat", "eta_hat", "gamma_hat", "x95_hat", "x95_true",
              "min_x", "rel_err", "rel_err_sq")
    nonfinite = sum(int(np.sum(~np.isfinite(ev[name]))) for name in fields)
    support = int(np.sum(ev["gamma_hat"].astype(np.float64) >=
                         ev["min_x"].astype(np.float64) - 1e-9))
    return int(len(ev["keys_beta"])), nonfinite, support


def _audit_source_selection() -> dict:
    expected = _source_sha_map()
    selected = []
    rows = nonfinite = support = 0
    for seed in SEEDS:
        for n in CFG.N_GRID:
            for fold_idx in FOLDS:
                for route in ("P", "Q"):
                    fit = TR.fit_id(n, fold_idx, seed, route)
                    meta_path = SOURCE_ROOT / "fit_metadata" / f"{fit}.json"
                    ev_path = SOURCE_ROOT / "evidence" / f"{fit}.npz"
                    for path in (meta_path, ev_path):
                        rel = path.relative_to(SOURCE_ROOT).as_posix()
                        if rel not in expected:
                            raise AssertionError(f"source SHA256SUMS missing selected file: {rel}")
                        got = _sha(path)
                        if got != expected[rel]:
                            raise AssertionError(f"source SHA mismatch: {rel}")
                        selected.append({"path": rel, "sha256": got})
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if _raw_sha(ev_path) != meta["evidence_sha256"]:
                        raise AssertionError(f"source evidence raw SHA mismatch: {fit}")
                    ev = _load_npz(ev_path)
                    n_rows, n_bad, n_support = _audit_evidence(ev)
                    rows += n_rows; nonfinite += n_bad; support += n_support
    if nonfinite or support:
        raise AssertionError(f"source evidence invalid: nonfinite={nonfinite}, support={support}")
    return {"selected_files": selected, "n_metadata": 48, "n_evidence": 48,
            "n_rows": rows, "nonfinite_values": nonfinite,
            "support_violations": support,
            "source_sha256sums_sha256": _sha(SOURCE_ROOT / "SHA256SUMS")}


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as archive:
        return {name: archive[name] for name in archive.files}


def _source_evidence(n: int, fold_idx: int, seed: int, route: str) -> dict:
    fit = TR.fit_id(n, fold_idx, seed, route)
    return _load_npz(SOURCE_ROOT / "evidence" / f"{fit}.npz")


def _matrix_evidence(n: int, fold_idx: int, seed: int) -> dict:
    fit = TR.fit_id(n, fold_idx, seed, "M95")
    return _load_npz(ART_ROOT / "evidence" / f"{fit}.npz")


def _save_matrix_fit(fit: str, result: dict) -> None:
    """沿用正式 schema，但以 float64 保存支持域审计所需的 gamma_hat/min_x。

    通用 P/Q 证据为 float32；M95 可能逼近 decoder 上边界，float32 会把仍有约 1e-5
    正间隙的两数舍入成相等。这里仅提高两个审计字段精度，不改变训练或预测数值。
    """
    RUN.save_fit(fit, result)
    active_root = Path(CFG.ARTIFACT_DIR)
    ev_path = active_root / "evidence" / f"{fit}.npz"
    arrays = _load_npz(ev_path)
    arrays["gamma_hat"] = np.asarray(result["predictions"]["gamma_hat"], dtype=np.float64)
    arrays["min_x"] = np.asarray(result["predictions"]["min_x"], dtype=np.float64)
    tmp_ev = ev_path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp_ev, **arrays)
    os.replace(tmp_ev, ev_path)

    meta_path = active_root / "fit_metadata" / f"{fit}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["evidence_sha256"] = _raw_sha(ev_path)
    meta["matrix_evidence_float64_fields"] = ["gamma_hat", "min_x"]
    tmp_meta = meta_path.with_suffix(".tmp.json")
    tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp_meta, meta_path)


def _fit_complete_verified(fit: str, implementation: dict[str, str]) -> bool:
    meta_path = ART_ROOT / "fit_metadata" / f"{fit}.json"
    ev_path = ART_ROOT / "evidence" / f"{fit}.npz"
    if not meta_path.exists() and not ev_path.exists():
        return False
    if not meta_path.exists() or not ev_path.exists():
        raise RuntimeError(f"partial fit cannot be resumed safely: {fit}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    expected = {
        "route": "M95", "target_R": TARGET_R,
        "matrix_contract_id": PILOT["contract_id"],
        "matrix_config_sha256": _sha(CONFIG_PATH),
        "matrix_implementation_sha256": implementation,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            raise RuntimeError(f"resume provenance mismatch for {fit}: {key}")
    if _raw_sha(ev_path) != meta.get("evidence_sha256"):
        raise RuntimeError(f"resume evidence SHA mismatch for {fit}")
    ev = _load_npz(ev_path)
    _, nonfinite, support = _audit_evidence(ev)
    if nonfinite or support:
        raise RuntimeError(f"resume evidence invalid for {fit}")
    return True


def _keys_match(*archives: dict) -> bool:
    names = ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id")
    return all(np.array_equal(archives[0][name], other[name])
               for other in archives[1:] for name in names)


def _sensitivity(beta: np.ndarray, eta: np.ndarray, gamma: np.ndarray,
                 R: float) -> np.ndarray:
    a = -np.log(float(R))
    t = a ** (1.0 / beta)
    x = gamma + eta * t
    return np.column_stack((-(eta * t * np.log(a)) / (beta * x),
                            eta * t / x, eta / x))


def _diagnostics(ev: dict, R: float = TARGET_R) -> tuple[float, float]:
    beta = ev["keys_beta"].astype(np.float64)
    eta = np.full_like(beta, CFG.ETA)
    gamma = ev["keys_gamma_over_eta"].astype(np.float64) * CFG.ETA
    u = np.column_stack(((ev["beta_hat"].astype(np.float64) - beta) / beta,
                         (ev["eta_hat"].astype(np.float64) - eta) / eta,
                         (ev["gamma_hat"].astype(np.float64) - gamma) / eta))
    s = _sensitivity(beta, eta, gamma, R)
    return float(np.mean(np.sum(u * u, axis=1))), \
        float(np.mean(np.sum(s * u, axis=1) ** 2))


def run_fits(resume: bool = True) -> None:
    _assert_frozen_implementation()
    _redirect(ART_ROOT)
    master = DATA.build_master()
    DATA.verify_integrity(master)
    implementation = _implementation_shas()
    log_path = ART_ROOT / "run.txt"
    done = skipped = 0
    with log_path.open("a", encoding="utf-8") as log:
        for seed in SEEDS:
            for n in CFG.N_GRID:
                for fold_idx in FOLDS:
                    fit = TR.fit_id(n, fold_idx, seed, "M95")
                    if resume and _fit_complete_verified(fit, implementation):
                        skipped += 1
                        continue
                    msg = f"[matrix] train {fit}"
                    print(msg, flush=True); log.write(msg + "\n"); log.flush()
                    result = TR.train_one_fit(
                        n, fold_idx, seed, "M95", master, target_R=TARGET_R,
                        split_strategy=CFG.SPLIT_STRATEGY)
                    result["meta"].update({
                        "matrix_contract_id": PILOT["contract_id"],
                        "matrix_config_sha256": _sha(CONFIG_PATH),
                        "matrix_implementation_sha256": implementation,
                    })
                    _save_matrix_fit(fit, result)
                    done += 1
        msg = f"[matrix] completed={done} skipped={skipped} expected={len(SEEDS)*len(CFG.N_GRID)*len(FOLDS)}"
        print(msg, flush=True); log.write(msg + "\n")


def smoke() -> None:
    master = DATA.build_master()
    DATA.verify_integrity(master)
    with tempfile.TemporaryDirectory(prefix="study02-matrix-smoke-") as tmp:
        root = Path(tmp)
        _redirect(root)
        result = TR.train_one_fit(
            10, 0, 42, "M95", master, target_R=TARGET_R,
            split_strategy=CFG.SPLIT_STRATEGY, max_epochs=3, patience=2)
        result["meta"].update({
            "matrix_contract_id": PILOT["contract_id"],
            "matrix_config_sha256": _sha(CONFIG_PATH),
            "matrix_implementation_sha256": _implementation_shas(),
        })
        _save_matrix_fit(TR.fit_id(10, 0, 42, "M95"), result)
        meta = result["meta"]
        for route in ("P", "Q"):
            source = _source_meta(10, 0, 42, route)
            assert all(meta[name] == source[name] for name in PAIR_FIELDS)
        assert meta["n_nonfinite"] == meta["n_support_viol"] == 0
        saved = _load_npz(root / "evidence" / "n10_f1_s42_rM95.npz")
        assert len(saved["rel_err_sq"]) == meta["n_test"]
        assert saved["gamma_hat"].dtype == saved["min_x"].dtype == np.float64
    print("target-matrix production smoke: PASS")


def _cell_rows() -> list[dict]:
    rows: list[dict] = []
    for seed in SEEDS:
        for n in CFG.N_GRID:
            for fold_idx in FOLDS:
                ev_p = _source_evidence(n, fold_idx, seed, "P")
                ev_q = _source_evidence(n, fold_idx, seed, "Q")
                ev_m = _matrix_evidence(n, fold_idx, seed)
                assert _keys_match(ev_p, ev_q, ev_m)
                meta_m = json.loads((ART_ROOT / "fit_metadata" /
                                     f"{TR.fit_id(n, fold_idx, seed, 'M95')}.json").read_text(encoding="utf-8"))
                for route in ("P", "Q"):
                    meta = _source_meta(n, fold_idx, seed, route)
                    assert all(meta_m[name] == meta[name] for name in PAIR_FIELDS)
                row = {"n": int(n), "fold": int(fold_idx + 1), "seed": int(seed)}
                for route, ev in (("P", ev_p), ("M95", ev_m), ("Q", ev_q)):
                    param_loss, matrix_loss = _diagnostics(ev)
                    row[f"mse_{route}"] = float(np.mean(ev["rel_err_sq"].astype(np.float64)))
                    row[f"p_equal_test_{route}"] = param_loss
                    row[f"matrix_test_{route}"] = matrix_loss
                row["diff_M_minus_P"] = row["mse_M95"] - row["mse_P"]
                row["diff_M_minus_Q"] = row["mse_M95"] - row["mse_Q"]
                rows.append(row)
    return rows


def _stratified(df: pd.DataFrame, group: str) -> list[dict]:
    out = []
    for value, part in df.groupby(group, sort=True):
        rec = {group: int(value)}
        for route in ("P", "M95", "Q"):
            rec[f"rrmse_{route}"] = float(np.sqrt(part[f"mse_{route}"].mean()))
        rec["M_better_than_P_cells"] = int((part["diff_M_minus_P"] < 0).sum())
        rec["M_better_than_Q_cells"] = int((part["diff_M_minus_Q"] < 0).sum())
        out.append(rec)
    return out


def _write_sensitivity_grid() -> tuple[pd.DataFrame, dict]:
    rows = []
    for R, label in ((0.90, "B10"), (0.95, "B5"), (0.99, "B1")):
        for beta in CFG.BETA_GRID:
            for goe in CFG.GAMMA_OVER_ETA_GRID:
                s = _sensitivity(np.array([beta]), np.array([CFG.ETA]),
                                 np.array([goe * CFG.ETA]), R)[0]
                W = np.outer(s, s)
                rows.append({
                    "R": R, "target": label, "beta": beta, "gamma_over_eta": goe,
                    "s_beta": s[0], "s_eta": s[1], "s_gamma": s[2],
                    "s_norm": float(np.linalg.norm(s)),
                    "W_bb": W[0, 0], "W_be": W[0, 1], "W_bg": W[0, 2],
                    "W_ee": W[1, 1], "W_eg": W[1, 2], "W_gg": W[2, 2],
                    "rank": 1,
                })
    frame = pd.DataFrame(rows)
    summary = {}
    for (R, label), part in frame.groupby(["R", "target"]):
        summary[label] = {
            "R": float(R), "n_grid_points": int(len(part)),
            "s_norm_min": float(part.s_norm.min()),
            "s_norm_max": float(part.s_norm.max()),
            "s_beta_over_s_gamma_range": [
                float((part.s_beta / part.s_gamma).min()),
                float((part.s_beta / part.s_gamma).max())],
            "s_eta_over_s_gamma_range": [
                float((part.s_eta / part.s_gamma).min()),
                float((part.s_eta / part.s_gamma).max())],
        }
    return frame, summary


def _plot(df: pd.DataFrame, sensitivity: pd.DataFrame, out: Path) -> None:
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    routes = ("P", "M95", "Q")
    colors = ("#4477AA", "#228833", "#EE7733")
    vals = [np.sqrt(df[f"mse_{r}"].mean()) for r in routes]
    axes[0].bar(routes, vals, color=colors, width=0.62)
    for i, route in enumerate(routes):
        seed_vals = [np.sqrt(part[f"mse_{route}"].mean())
                     for _, part in df.groupby("seed", sort=True)]
        axes[0].scatter(np.full(len(seed_vals), i), seed_vals, color="black", s=20, zorder=3)
    axes[0].set_ylabel("B5 held-out rRMSE")
    axes[0].set_title("(a) Held-out B5 rRMSE by training loss")

    for (R, label), part in sensitivity.groupby(["R", "target"], sort=False):
        by_beta = part.groupby("beta", as_index=False).first()
        axes[1].plot(by_beta.beta, by_beta.s_beta / by_beta.s_gamma,
                     marker="o", label=f"{label}: beta/gamma")
        axes[1].plot(by_beta.beta, by_beta.s_eta / by_beta.s_gamma,
                     marker="s", linestyle="--", label=f"{label}: eta/gamma")
    axes[1].axhline(1.0, color="0.7", linewidth=0.8)
    axes[1].set_xlabel("Weibull shape beta")
    axes[1].set_ylabel("dimensionless sensitivity ratio")
    axes[1].set_title("(b) B1/B5/B10 imply different parameter geometry")
    axes[1].legend(fontsize=7, ncol=2)
    fig.suptitle("Study02 target-sensitivity matrix pilot", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "target_matrix_pilot.png", dpi=220, bbox_inches="tight")
    fig.savefig(out / "target_matrix_pilot.pdf", bbox_inches="tight")
    plt.close(fig)


def _write_sha256sums() -> None:
    paths = []
    for sub in ("fit_metadata", "evidence", "analysis"):
        paths.extend(p for p in (ART_ROOT / sub).glob("*") if p.is_file())
    for name in ("run.txt", "per_fit_metrics.csv", "pairing_report.csv", "manifest.json"):
        path = ART_ROOT / name
        if path.is_file():
            paths.append(path)
    lines = [f"{_sha(path)}  {path.relative_to(ART_ROOT).as_posix()}" for path in sorted(paths)]
    (ART_ROOT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze() -> dict:
    _redirect(ART_ROOT)
    implementation = _implementation_shas()
    for seed in SEEDS:
        for n in CFG.N_GRID:
            for fold_idx in FOLDS:
                fit = TR.fit_id(n, fold_idx, seed, "M95")
                if not _fit_complete_verified(fit, implementation):
                    raise AssertionError(f"missing matrix evidence: {fit}")
    source_audit = _audit_source_selection()
    rows = _cell_rows()
    if len(rows) != 24:
        raise AssertionError(f"expected 24 matrix cells, got {len(rows)}")
    df = pd.DataFrame(rows)
    analysis = ART_ROOT / "analysis"
    df.to_csv(analysis / "cell_metrics.csv", index=False)

    rrmse = {route: float(np.sqrt(df[f"mse_{route}"].mean()))
             for route in ("P", "M95", "Q")}
    mse = {route: float(df[f"mse_{route}"].mean()) for route in ("P", "M95", "Q")}
    denom = mse["P"] - mse["Q"]
    sensitivity, sensitivity_summary = _write_sensitivity_grid()
    sensitivity.to_csv(analysis / "sensitivity_matrices.csv", index=False)
    (analysis / "source_selection.json").write_text(
        json.dumps(source_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "contract_id": PILOT["contract_id"], "generated_at": _now(),
        "status": "COMPLETE / NOT PAPER EVIDENCE", "target": {"R": TARGET_R, "name": "B5"},
        "design": {"seeds": SEEDS, "folds_1based": [f + 1 for f in FOLDS],
                   "n_grid": list(CFG.N_GRID), "n_cells": 24, "new_fits": 24},
        "rrmse": rrmse, "mean_cell_mse": mse,
        "relative_change_percent": {
            "M95_vs_P": 100.0 * (rrmse["M95"] / rrmse["P"] - 1.0),
            "Q_vs_P": 100.0 * (rrmse["Q"] / rrmse["P"] - 1.0),
            "M95_vs_Q": 100.0 * (rrmse["M95"] / rrmse["Q"] - 1.0)},
        "q_mse_gap_recovered_by_M95": ((mse["P"] - mse["M95"]) / denom
                                        if denom != 0 else None),
        "cell_directions": {
            "M95_better_than_P": int((df.diff_M_minus_P < 0).sum()),
            "M95_better_than_Q": int((df.diff_M_minus_Q < 0).sum()),
            "n_cells": 24},
        "by_n": _stratified(df, "n"), "by_seed": _stratified(df, "seed"),
        "by_fold": _stratified(df, "fold"),
        "test_diagnostics": {
            route: {"mean_P_equal_parameter_loss": float(df[f"p_equal_test_{route}"].mean()),
                    "mean_truth_matrix_loss": float(df[f"matrix_test_{route}"].mean())}
            for route in ("P", "M95", "Q")},
        "analytic_sensitivity": sensitivity_summary,
        "inference_boundary": "descriptive 3-seed x 2-fold pilot; no bootstrap CI or significance claim",
    }
    (analysis / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(df, sensitivity, analysis)

    metas = []
    pairs = []
    for seed in SEEDS:
        for n in CFG.N_GRID:
            for fold_idx in FOLDS:
                fit = TR.fit_id(n, fold_idx, seed, "M95")
                meta = json.loads((ART_ROOT / "fit_metadata" / f"{fit}.json").read_text(encoding="utf-8"))
                metas.append(meta)
                rec = {"n": n, "fold": fold_idx + 1, "seed": seed}
                for field in PAIR_FIELDS:
                    rec[field] = (meta[field] == _source_meta(n, fold_idx, seed, "P")[field]
                                  == _source_meta(n, fold_idx, seed, "Q")[field])
                rec["all_match"] = all(rec[field] for field in PAIR_FIELDS)
                pairs.append(rec)
    pd.DataFrame(metas).to_csv(ART_ROOT / "per_fit_metrics.csv", index=False)
    pd.DataFrame(pairs).to_csv(ART_ROOT / "pairing_report.csv", index=False)
    assert all(r["all_match"] for r in pairs)
    assert all(m["n_nonfinite"] == m["n_support_viol"] == 0 for m in metas)

    source_manifest = SOURCE_ROOT / "manifest.json"
    manifest = {
        "contract_id": PILOT["contract_id"], "created_at": _now(),
        "git_full_sha": _git_head(), "paper_freeze_tag": PILOT["paper_freeze_tag"],
        "paper_freeze_commit": PILOT["paper_freeze_commit"],
        "config_sha256": _sha(CONFIG_PATH), "protocol_sha256": _sha(PROTOCOL_PATH),
        "implementation_sha256": _implementation_shas(),
        "environment_lock_sha256": _sha(ENV_PATH),
        "source_iid_manifest_sha256": _sha(source_manifest),
        "source_iid_sha256sums_sha256": source_audit["source_sha256sums_sha256"],
        "source_selection_sha256": _sha(analysis / "source_selection.json"),
        "source_selection": {k: v for k, v in source_audit.items() if k != "selected_files"},
        "new_fits": 24, "pairing_all_match": True,
        "nonfinite_predictions": int(sum(m["n_nonfinite"] for m in metas)),
        "support_violations": int(sum(m["n_support_viol"] for m in metas)),
        "paper_admission": "EXCLUDED pending explicit user decision",
        "sha256_rule": "text LF-normalized; binary raw",
    }
    (ART_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_sha256sums()
    print(json.dumps(summary["rrmse"], ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    args = parser.parse_args()
    if not (args.smoke or args.run or args.analyze or args.all):
        parser.error("choose --smoke, --run, --analyze or --all")
    if args.smoke:
        smoke()
    if args.run or args.all:
        run_fits(resume=args.resume)
    if args.analyze or args.all:
        analyze()


if __name__ == "__main__":
    main()
