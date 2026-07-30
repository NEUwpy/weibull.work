"""P4 formal comparison: complete execution adapter.

Two-layer architecture (P4-R5):
  Layer 1 (estimation): one parameter estimate per physical sample per method.
  Layer 2 (evaluation): broadcast traditional to fold×seed contexts, apply
    fold-specific P99 penalty, compute true_loss. Symmetric across methods.

Implements all four frozen tracks × six methods (P4-R1).
Authorization contract binds parent commit, worktree, hashes, paths (P4-R2).
Fail-closed sealing with run lock and recursive allowlist (P4-R8).
Result tables: Bias/RMSE/MAE, quantiles, stratification, paired (P4-R9).
Prediction validity for Direct-MLP (P4-R7).
Track-aware seed namespaces (P4-R6).

NO new experiment framework, NO second large pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

import p4_config as cfg
import run_p3_direct_mlp as direct
import run_p3_fair_compare as compare
import run_E4_formal_validation as e4

from studies.common.sample import generate_sample
from studies.common.runner import run_method


# ════════════════════════════════════════════════════════════════════════
# Schemas
# ════════════════════════════════════════════════════════════════════════

ESTIMATION_COLUMNS = [
    "track", "method", "fold", "seed",
    "beta", "gamma_over_eta", "n", "repeat_id",
    "beta_hat", "eta_hat", "gamma_hat",
    "failed", "failure_reason",
]

EVALUATION_COLUMNS = [
    "track", "method", "fold", "seed",
    "beta", "gamma_over_eta", "n", "repeat_id",
    "beta_hat", "eta_hat", "gamma_hat",
    "true_loss", "true_loss_complete_case",
    "failed", "failure_reason", "failure_penalty",
]

SAMPLE_KEY_COLS = ["beta", "gamma_over_eta", "n", "repeat_id"]


# ════════════════════════════════════════════════════════════════════════
# Prediction validity (P4-R7)
# ════════════════════════════════════════════════════════════════════════

def check_prediction_validity(beta_hat, eta_hat, gamma_hat):
    """Check if a prediction is valid (finite, positive constraints).

    Returns (is_valid, failure_reason).
    Reuses P3 output constraints: beta>0, eta>0, gamma>=0, all finite.
    """
    vals = [beta_hat, eta_hat, gamma_hat]
    if any(not np.isfinite(v) for v in vals):
        return False, "non_finite_prediction"
    if beta_hat <= 0:
        return False, "beta_hat_not_positive"
    if eta_hat <= 0:
        return False, "eta_hat_not_positive"
    if gamma_hat < 0:
        return False, "gamma_hat_negative"
    return True, ""


def make_estimation_row(track, method, fold, seed, beta, goe, n, repeat_id,
                        beta_hat, eta_hat, gamma_hat, failed, failure_reason):
    return {
        "track": track, "method": method, "fold": fold, "seed": seed,
        "beta": beta, "gamma_over_eta": goe, "n": n, "repeat_id": repeat_id,
        "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
        "failed": failed, "failure_reason": failure_reason,
    }


# ════════════════════════════════════════════════════════════════════════
# Evaluation layer construction (P4-R5)
# ════════════════════════════════════════════════════════════════════════

def build_evaluation_layer(df_est, fold_penalties, fold_assignment=None, seeds=None):
    """Build evaluation layer from estimation layer.

    For traditional methods:
      - If fold_assignment is provided (Track 1): each sample is broadcast only
        to its assigned fold's seeds. fold_assignment maps sample_key → fold_name.
      - If fold_assignment is None (Tracks 2/3/4): broadcast to ALL folds × seeds.
    For learning methods: each row already has fold/seed.

    fold_penalties: dict mapping fold_name → P99 penalty. Missing fold raises.
    seeds: list of seeds to broadcast traditional methods to. Defaults to cfg.SEEDS.
    """
    if seeds is None:
        seeds = cfg.SEEDS
    eval_rows = []

    for _, row in df_est.iterrows():
        method = row["method"]
        is_learning = method in cfg.LEARNING_METHODS
        beta_true = row["beta"]
        eta_true = 1.0
        gamma_true = row["gamma_over_eta"] * eta_true
        failed = row["failed"]

        if is_learning:
            fold = row["fold"]
            seed = row["seed"]
            if fold not in fold_penalties:
                raise ValueError(f"Missing fold penalty for fold={fold}")
            penalty = fold_penalties[fold]
            eval_rows.append(_make_eval_row(row, fold, seed, penalty, beta_true, eta_true, gamma_true, failed))
        else:
            if fold_assignment is not None:
                sample_key = (row["beta"], row["gamma_over_eta"], row["n"], row["repeat_id"])
                assigned_fold = fold_assignment.get(sample_key)
                if assigned_fold is None:
                    raise ValueError(f"Traditional sample {sample_key} has no fold assignment")
                if assigned_fold not in fold_penalties:
                    raise ValueError(f"Missing fold penalty for fold={assigned_fold}")
                penalty = fold_penalties[assigned_fold]
                for seed in seeds:
                    eval_rows.append(_make_eval_row(row, assigned_fold, seed, penalty, beta_true, eta_true, gamma_true, failed))
            else:
                for fold, penalty in fold_penalties.items():
                    for seed in seeds:
                        eval_rows.append(_make_eval_row(row, fold, seed, penalty, beta_true, eta_true, gamma_true, failed))

    return pd.DataFrame(eval_rows, columns=EVALUATION_COLUMNS)


def _make_eval_row(est_row, fold, seed, penalty, beta_true, eta_true, gamma_true, failed):
    if failed:
        loss = penalty
        loss_complete = float("nan")
    else:
        loss_complete = direct.compute_param_loss(
            est_row["beta_hat"], beta_true,
            est_row["eta_hat"], eta_true,
            est_row["gamma_hat"], gamma_true,
        )
        loss = loss_complete
    return {
        "track": est_row["track"], "method": est_row["method"],
        "fold": fold, "seed": seed,
        "beta": est_row["beta"], "gamma_over_eta": est_row["gamma_over_eta"],
        "n": est_row["n"], "repeat_id": est_row["repeat_id"],
        "beta_hat": est_row["beta_hat"], "eta_hat": est_row["eta_hat"],
        "gamma_hat": est_row["gamma_hat"],
        "true_loss": loss, "true_loss_complete_case": loss_complete,
        "failed": failed, "failure_reason": est_row["failure_reason"],
        "failure_penalty": penalty,
    }


# ════════════════════════════════════════════════════════════════════════
# Model-first aggregation
# ════════════════════════════════════════════════════════════════════════

def model_first_aggregate(df_eval, method_name, track=None):
    """Per-model J1 first, then summarize distribution."""
    if track is not None:
        df = df_eval[(df_eval["method"] == method_name) & (df_eval["track"] == track)].copy()
    else:
        df = df_eval[df_eval["method"] == method_name].copy()

    if df.empty:
        return {"method": method_name, "n_rows": 0, "error": "empty"}

    per_model = df.groupby(["fold", "seed"]).apply(
        lambda x: compare.pooled_j1(x["true_loss"].values.astype(float)),
        include_groups=False,
    )
    return {
        "method": method_name,
        "n_models": len(per_model),
        "median_J1": float(per_model.median()),
        "mean_J1": float(per_model.mean()),
        "SD_J1": float(per_model.std(ddof=1)) if len(per_model) > 1 else 0.0,
        "min_J1": float(per_model.min()),
        "max_J1": float(per_model.max()),
        "n_failures": int(df["failed"].sum()),
        "n_rows": len(df),
    }


# ════════════════════════════════════════════════════════════════════════
# Sample key verification (P4-R3: track-aware, cross-type)
# ════════════════════════════════════════════════════════════════════════

def verify_sample_keys_identical(df_eval, track=None):
    """Verify all methods share identical evaluation-layer keys.

    In the evaluation layer, ALL methods (traditional and learning) have
    (fold, seed, sample_key) rows. Checks:
    1. Key uniqueness within each method.
    2. Cross-method alignment: all methods have identical key sets.
    3. Per-fold consistency: within each fold, all seeds have same sample keys.
    """
    if track is not None:
        df = df_eval[df_eval["track"] == track].copy()
    else:
        df = df_eval.copy()

    if df.empty:
        return {"ok": False, "reason": "no rows"}

    methods = sorted(df["method"].unique())
    issues = []
    key_cols = SAMPLE_KEY_COLS + ["fold", "seed"]

    method_key_sets = {}
    for method in methods:
        sub = df[df["method"] == method]
        keys = sub[key_cols].apply(tuple, axis=1)
        n_dupes = keys.duplicated().sum()
        if n_dupes > 0:
            issues.append(f"{method}: {n_dupes} duplicate keys")
        method_key_sets[method] = set(keys)

        for fold in sub["fold"].unique():
            fold_sub = sub[sub["fold"] == fold]
            seed_key_sets = []
            for seed in fold_sub["seed"].unique():
                sk = set(fold_sub[fold_sub["seed"] == seed][SAMPLE_KEY_COLS].apply(tuple, axis=1))
                seed_key_sets.append((seed, sk))
            if len(seed_key_sets) > 1:
                ref_seed, ref_keys = seed_key_sets[0]
                for other_seed, other_keys in seed_key_sets[1:]:
                    if other_keys != ref_keys:
                        issues.append(
                            f"{method} fold={fold}: seed {other_seed} keys differ from seed {ref_seed}"
                        )
                        break

    if len(methods) > 1:
        ref_method = methods[0]
        ref_keys = method_key_sets[ref_method]
        for other_method in methods[1:]:
            if method_key_sets[other_method] != ref_keys:
                only_ref = ref_keys - method_key_sets[other_method]
                only_other = method_key_sets[other_method] - ref_keys
                issues.append(
                    f"key mismatch {ref_method} vs {other_method}: "
                    f"{len(only_ref)} only in {ref_method}, {len(only_other)} only in {other_method}"
                )

    if issues:
        return {"ok": False, "issues": issues}
    return {"ok": True, "n_methods": len(methods)}


# ════════════════════════════════════════════════════════════════════════
# Valid-only filtering check (fail-closed)
# ════════════════════════════════════════════════════════════════════════

def verify_no_valid_only_filtering(df_eval, track=None, expected_rows_per_method=None):
    """Fail-closed: row counts must match EXACTLY, failed rows must have penalty as loss.

    Rejects both deficits (survivor filtering) and extras (contamination).
    """
    if track is not None:
        df = df_eval[df_eval["track"] == track].copy()
    else:
        df = df_eval.copy()

    if df.empty:
        raise ValueError("verify_no_valid_only_filtering: no rows")

    if expected_rows_per_method:
        for method, exp in expected_rows_per_method.items():
            if exp == "runtime":
                continue
            actual = len(df[df["method"] == method])
            if actual != exp:
                raise ValueError(
                    f"row count mismatch: {method} has {actual} rows, expected exactly {exp}"
                )

    failed_rows = df[df["failed"] == True]
    if len(failed_rows) > 0:
        bad = failed_rows[failed_rows["true_loss"] != failed_rows["failure_penalty"]]
        if len(bad) > 0:
            raise ValueError(f"{len(bad)} failed rows have true_loss != failure_penalty")
        zero_pen = failed_rows[failed_rows["failure_penalty"] <= 0]
        if len(zero_pen) > 0:
            raise ValueError(f"{len(zero_pen)} failed rows have penalty <= 0")

    return True


# ════════════════════════════════════════════════════════════════════════
# Paired comparison (P4-R4: evaluation-layer keyed)
# ════════════════════════════════════════════════════════════════════════

def paired_comparison(df_eval, method_a, method_b, track=None):
    """Per-sample paired comparison on evaluation layer.

    Both methods are keyed by (sample_key, fold, seed) — no ambiguity.
    """
    if track is not None:
        df = df_eval[df_eval["track"] == track].copy()
    else:
        df = df_eval.copy()

    idx_cols = SAMPLE_KEY_COLS + ["fold", "seed"]
    df_a = df[df["method"] == method_a].set_index(idx_cols)
    df_b = df[df["method"] == method_b].set_index(idx_cols)

    common_idx = df_a.index.intersection(df_b.index)
    if len(common_idx) == 0:
        return {"error": "no common samples", "n_paired": 0}

    diff = df_a.loc[common_idx, "true_loss"].values - df_b.loc[common_idx, "true_loss"].values
    return {
        "n_paired": len(common_idx),
        "a_wins": int(np.sum(diff < 0)),
        "b_wins": int(np.sum(diff > 0)),
        "draws": int(np.sum(diff == 0)),
        "median_diff": float(np.median(diff)),
        "mean_diff": float(np.mean(diff)),
    }


# ════════════════════════════════════════════════════════════════════════
# Result tables (P4-R9)
# ════════════════════════════════════════════════════════════════════════

def compute_result_tables(df_eval, track):
    """Compute frozen P4 result tables from evaluation layer.

    Produces:
    - Model-first J1 summary (per-model pooled J1, then distribution)
    - Full-sample loss quantiles (P25/P50/P75/P90/P95/P99, includes failures)
    - Complete-case parameter Bias/RMSE/MAE (explicitly labeled)
    - Failure/support-set rates
    - Stratification by n, beta, generalization axis (model-first per stratum)
    - Paired win/loss/difference
    """
    df = df_eval[df_eval["track"] == track].copy()
    results = {"track": track, "methods": {}}

    for method in sorted(df["method"].unique()):
        m_df = df[df["method"] == method]
        j1_summary = model_first_aggregate(df, method, track=track)

        n_total = len(m_df)
        n_failed = int(m_df["failed"].sum())
        support_rate = 1.0 - (n_failed / n_total) if n_total > 0 else 0.0

        all_losses = m_df["true_loss"].values.astype(float)
        loss_quantiles = {
            "P25": float(np.percentile(all_losses, 25)),
            "P50": float(np.percentile(all_losses, 50)),
            "P75": float(np.percentile(all_losses, 75)),
            "P90": float(np.percentile(all_losses, 90)),
            "P95": float(np.percentile(all_losses, 95)),
            "P99": float(np.percentile(all_losses, 99)),
        }

        valid = m_df[~m_df["failed"]]
        if len(valid) > 0:
            beta_bias = float((valid["beta_hat"] - valid["beta"]).mean())
            eta_bias = float((valid["eta_hat"] - 1.0).mean())
            gamma_bias = float((valid["gamma_hat"] - valid["gamma_over_eta"]).mean())
            beta_rmse = float(np.sqrt(((valid["beta_hat"] - valid["beta"]) ** 2).mean()))
            eta_rmse = float(np.sqrt(((valid["eta_hat"] - 1.0) ** 2).mean()))
            gamma_rmse = float(np.sqrt(((valid["gamma_hat"] - valid["gamma_over_eta"]) ** 2).mean()))
            beta_mae = float(np.abs(valid["beta_hat"] - valid["beta"]).mean())
            eta_mae = float(np.abs(valid["eta_hat"] - 1.0).mean())
            gamma_mae = float(np.abs(valid["gamma_hat"] - valid["gamma_over_eta"]).mean())
        else:
            beta_bias = eta_bias = gamma_bias = float("nan")
            beta_rmse = eta_rmse = gamma_rmse = float("nan")
            beta_mae = eta_mae = gamma_mae = float("nan")

        strat_n = _stratify_model_first(m_df, "n")
        strat_beta = _stratify_model_first(m_df, "beta")
        strat_goe = _stratify_model_first(m_df, "gamma_over_eta")

        results["methods"][method] = {
            "j1_summary": j1_summary,
            "loss_quantiles_full_sample": loss_quantiles,
            "complete_case_parametrics": {
                "note": "Computed on non-failed rows only",
                "n_valid": len(valid),
                "bias": {"beta": beta_bias, "eta": eta_bias, "gamma": gamma_bias},
                "rmse": {"beta": beta_rmse, "eta": eta_rmse, "gamma": gamma_rmse},
                "mae": {"beta": beta_mae, "eta": eta_mae, "gamma": gamma_mae},
            },
            "failure_rate": n_failed / n_total if n_total > 0 else 0.0,
            "support_rate": support_rate,
            "n_total": n_total,
            "n_failed": n_failed,
            "stratification_by_n": strat_n,
            "stratification_by_beta": strat_beta,
            "stratification_by_gamma_over_eta": strat_goe,
        }

    paired_results = {}
    methods = sorted(df["method"].unique())
    for i, ma in enumerate(methods):
        for mb in methods[i + 1:]:
            key = f"{ma}_vs_{mb}"
            paired_results[key] = paired_comparison(df, ma, mb, track=track)
    results["paired_comparisons"] = paired_results

    return results


def _stratify_model_first(m_df, group_col):
    """Stratify by a column, computing model-first J1 per stratum."""
    result = {}
    for val, grp in m_df.groupby(group_col):
        per_model = grp.groupby(["fold", "seed"]).apply(
            lambda x: compare.pooled_j1(x["true_loss"].values.astype(float)),
            include_groups=False,
        )
        key = int(val) if isinstance(val, (np.integer,)) else float(val)
        result[key] = {
            "median_J1": float(per_model.median()),
            "n_models": len(per_model),
            "n_rows": len(grp),
            "failure_rate": float(grp["failed"].mean()),
        }
    return result


# ════════════════════════════════════════════════════════════════════════
# Checkpoint / resume (P4-R8: full context binding)
# ════════════════════════════════════════════════════════════════════════

class CheckpointDriftError(ValueError):
    pass


CHECKPOINT_REQUIRED_COLS = [
    "config_git_commit", "config_input_sha256", "config_p4_authorized",
    "config_script_sha256",
]


def checkpoint_path(output_dir, track, method):
    return Path(output_dir) / f"checkpoint_{track}_{method}.csv"


def load_checkpoint(output_dir, track, method):
    cp = checkpoint_path(output_dir, track, method)
    if cp.exists():
        return pd.read_csv(cp)
    return None


def save_checkpoint(output_dir, track, method, df, run_context):
    df = df.copy()
    df["config_git_commit"] = run_context["git_commit"]
    df["config_input_sha256"] = run_context["input_sha256"]
    df["config_p4_authorized"] = run_context["p4_authorized"]
    df["config_script_sha256"] = run_context["script_sha256"]
    atomic_write_csv(df, checkpoint_path(output_dir, track, method))


def verify_checkpoint_config(checkpoint_df, run_context):
    """Verify checkpoint matches current run context. All fields mandatory."""
    for col in CHECKPOINT_REQUIRED_COLS:
        if col not in checkpoint_df.columns:
            raise CheckpointDriftError(f"checkpoint missing required column: {col}")

    checks = [
        ("config_git_commit", run_context["git_commit"]),
        ("config_input_sha256", run_context["input_sha256"]),
        ("config_p4_authorized", run_context["p4_authorized"]),
        ("config_script_sha256", run_context["script_sha256"]),
    ]
    for col, expected in checks:
        vals = checkpoint_df[col].unique()
        if len(vals) != 1:
            raise CheckpointDriftError(f"checkpoint {col} has multiple values: {vals}")
        if vals[0] != expected:
            raise CheckpointDriftError(
                f"checkpoint {col}={vals[0]} != expected={expected}"
            )
    return True


# ════════════════════════════════════════════════════════════════════════
# Atomic write and fail-closed sealing (P4-R8)
# ════════════════════════════════════════════════════════════════════════

def atomic_write_csv(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    df.to_csv(tmp, index=False)
    os.replace(str(tmp), str(path))


def atomic_write_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    os.replace(str(tmp), str(path))


def atomic_write_text(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(str(tmp), str(path))


def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_script_sha256():
    return compute_sha256(Path(__file__).resolve())


def seal_outputs(output_dir, expected_files):
    """Fail-closed seal: ALL expected files must exist. Atomic SHA256SUMS."""
    output_dir = Path(output_dir)
    for fname in expected_files:
        if not (output_dir / fname).exists():
            raise FileNotFoundError(f"seal_outputs: missing expected file: {fname}")

    lines = []
    for fname in sorted(expected_files):
        h = compute_sha256(output_dir / fname)
        lines.append(f"{h}  {fname}")
    atomic_write_text("\n".join(lines) + "\n", output_dir / "SHA256SUMS")
    return compute_sha256(output_dir / "SHA256SUMS")


def seal_recursive(output_dir, allowlist):
    """Recursively seal all files in allowlist. Reject missing or extra.

    Only ignores the owned run.lock file (not arbitrary *.lock files).
    """
    output_dir = Path(output_dir)
    actual_files = set()
    for f in output_dir.rglob("*"):
        if f.is_file() and f.name != "SHA256SUMS" and f.name != "run.lock":
            actual_files.add(f.relative_to(output_dir).as_posix())

    expected = set(allowlist)
    missing = expected - actual_files
    extra = actual_files - expected
    if missing:
        raise FileNotFoundError(f"seal_recursive: missing files: {sorted(missing)}")
    if extra:
        raise ValueError(f"seal_recursive: unexpected files: {sorted(extra)}")

    lines = []
    for fname in sorted(allowlist):
        h = compute_sha256(output_dir / fname)
        lines.append(f"{h}  {fname}")
    atomic_write_text("\n".join(lines) + "\n", output_dir / "SHA256SUMS")
    return compute_sha256(output_dir / "SHA256SUMS")


# ════════════════════════════════════════════════════════════════════════
# Run lock (P4-R8: exclusive)
# ════════════════════════════════════════════════════════════════════════

def acquire_run_lock(output_dir):
    """Acquire exclusive run lock atomically (O_CREAT|O_EXCL)."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    lock_path = Path(output_dir) / "run.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(
            f"Run lock exists: {lock_path}. Another P4 run may be active."
        )
    lock_info = json.dumps({
        "pid": os.getpid(),
        "git_commit": get_git_commit(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
    })
    os.write(fd, lock_info.encode())
    os.close(fd)
    return lock_path


def release_run_lock(output_dir):
    lock_path = Path(output_dir) / "run.lock"
    if lock_path.exists():
        try:
            info = json.loads(lock_path.read_text())
            if info.get("pid") != os.getpid():
                raise RuntimeError("Cannot release lock owned by another PID")
        except (json.JSONDecodeError, KeyError):
            pass
        lock_path.unlink()


# ════════════════════════════════════════════════════════════════════════
# Manifest and provenance
# ════════════════════════════════════════════════════════════════════════

def get_git_commit():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[3]
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def get_git_dirty():
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[3]
        )
        return len(r.stdout.strip()) > 0
    except Exception:
        return True


def build_run_context(input_sha256):
    """Build run context for checkpoint binding and drift detection."""
    return {
        "git_commit": get_git_commit(),
        "input_sha256": input_sha256,
        "p4_authorized": cfg.P4_FORMAL_AUTHORIZED,
        "script_sha256": compute_script_sha256(),
    }


def build_manifest(tracks_run, methods_run):
    import scipy
    import sklearn
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        torch_version = "not installed"

    return {
        "manifest_version": "study01-p4-formal-compare-v3",
        "p4_formal_authorized": cfg.P4_FORMAL_AUTHORIZED,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
        "git_commit": get_git_commit(),
        "worktree_dirty": get_git_dirty(),
        "script_sha256": compute_script_sha256(),
        "config_sha256": compute_sha256(Path(_CODE_DIR) / "p4_config.py"),
        "baseline_commit": cfg.BASELINE_COMMIT,
        "approved_parent_commit": cfg.APPROVED_PARENT_COMMIT,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "sklearn_version": sklearn.__version__,
        "torch_version": torch_version,
        "tracks": tracks_run,
        "methods": methods_run,
        "n_folds": cfg.N_FOLDS,
        "n_seeds": cfg.N_SEEDS,
        "seeds": cfg.SEEDS,
        "eval_repeats": cfg.EVAL_REPEATS,
        "input_sha256": cfg.INPUT_SHA256,
        "track_seed_namespaces": cfg.TRACK_SEED_NAMESPACE,
        "mdm_default_delta": cfg.MDM_DEFAULT_DELTA,
        "row_count_contract": cfg.ROW_COUNT_CONTRACT,
        "failure_contract": "Per-fold P99 of ALL 26 delta training losses",
        "j1_formula": "sqrt(mean(((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2))",
    }


# ════════════════════════════════════════════════════════════════════════
# Authorization contract verification (P4-R2)
# ════════════════════════════════════════════════════════════════════════

def verify_authorization_contract(output_dir, tracks, seeds, resume):
    """Verify all authorization bindings before formal run.

    Binds exact output_dir, tracks, seeds, resume to prevent arbitrary args.
    Fail-closed checks:
    1. P4_FORMAL_AUTHORIZED == True
    2. APPROVED_PARENT_COMMIT is set and matches HEAD~1
    3. Worktree is clean
    4. output_dir == cfg.FORMAL_OUTPUT_DIR (no arbitrary paths)
    5. tracks == cfg.ALL_TRACKS (no subsets)
    6. seeds == cfg.SEEDS (no subsets)
    7. Fresh run: output dir must not exist. Resume: must exist with manifest.
    8. Script/config SHA256 computable and recorded in manifest.
    """
    cfg.assert_formal_authorized()

    if Path(output_dir).resolve() != cfg.FORMAL_OUTPUT_DIR.resolve():
        raise RuntimeError(
            f"Authorization contract: output_dir must be {cfg.FORMAL_OUTPUT_DIR}, "
            f"got {output_dir}"
        )

    if list(tracks) != list(cfg.ALL_TRACKS):
        raise RuntimeError(
            f"Authorization contract: tracks must be {cfg.ALL_TRACKS}, got {tracks}"
        )

    if list(seeds) != list(cfg.SEEDS):
        raise RuntimeError(
            f"Authorization contract: seeds must be {cfg.SEEDS}, got {seeds}"
        )

    if get_git_dirty():
        raise RuntimeError("Authorization contract: worktree is dirty")

    if cfg.APPROVED_PARENT_COMMIT is None:
        raise RuntimeError("Authorization contract: APPROVED_PARENT_COMMIT not set.")

    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[3]
        )
        parent = r.stdout.strip()
        if parent != cfg.APPROVED_PARENT_COMMIT:
            raise RuntimeError(
                f"Authorization contract: HEAD~1={parent} != "
                f"APPROVED_PARENT_COMMIT={cfg.APPROVED_PARENT_COMMIT}"
            )
    except FileNotFoundError:
        raise RuntimeError("Authorization contract: cannot determine parent commit")

    output_path = Path(output_dir)
    if resume:
        if not output_path.exists():
            raise RuntimeError("Authorization contract: resume=True but output dir missing")
        manifest_path = output_path / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("Authorization contract: resume=True but manifest.json missing")
    else:
        if output_path.exists():
            raise RuntimeError(
                f"Authorization contract: fresh run but output dir exists: {output_path}"
            )

    script_hash = compute_script_sha256()
    if len(script_hash) != 64:
        raise RuntimeError("Authorization contract: cannot compute script SHA256")

    config_hash = compute_sha256(Path(_CODE_DIR) / "p4_config.py")
    if len(config_hash) != 64:
        raise RuntimeError("Authorization contract: cannot compute config SHA256")

    return {
        "script_sha256": script_hash,
        "config_sha256": config_hash,
        "start_head": get_git_commit(),
        "output_dir": str(Path(output_dir).resolve()),
        "tracks": list(tracks),
        "seeds": list(seeds),
        "resume": resume,
        "approved_parent_commit": cfg.APPROVED_PARENT_COMMIT,
    }


def verify_pre_seal_state(output_dir, auth_hashes):
    """Re-verify HEAD/worktree/script/config/input state immediately before sealing.

    Checks: HEAD unchanged, worktree clean, script/config hashes match start,
    all frozen input files still match their sealed SHA256.
    """
    if get_git_dirty():
        raise RuntimeError("Pre-seal: worktree became dirty during execution")

    current_head = get_git_commit()
    if current_head != auth_hashes["start_head"]:
        raise RuntimeError(
            f"Pre-seal: HEAD drifted: {current_head} != {auth_hashes['start_head']}"
        )

    current_script = compute_script_sha256()
    if current_script != auth_hashes["script_sha256"]:
        raise RuntimeError("Pre-seal: script SHA256 drifted during execution")

    current_config = compute_sha256(Path(_CODE_DIR) / "p4_config.py")
    if current_config != auth_hashes["config_sha256"]:
        raise RuntimeError("Pre-seal: config SHA256 drifted during execution")

    study_dir = Path(__file__).resolve().parents[1]
    input_paths = {
        "E3b_risk_curves_csv": study_dir / "artifacts/formal/E3b_vector_mlp/risk_curves.csv",
        "E3b_sample_features_csv": study_dir / "artifacts/formal/E3b_vector_mlp/sample_features.csv",
        "P2_baseline_per_sample_csv": study_dir / "artifacts/formal/extended_validation/p2_generalization_v2/p2_baseline_per_sample.csv",
        "P2_vector_per_sample_csv": study_dir / "artifacts/formal/extended_validation/p2_generalization_v2/p2_vector_per_sample.csv",
        "E4d_selector_extrapolation_csv": study_dir / "artifacts/formal/E4_robustness/E4d_selector_extrapolation.csv",
    }
    for name, expected_hash in cfg.INPUT_SHA256.items():
        path = input_paths.get(name)
        if path is None or not path.exists():
            raise RuntimeError(f"Pre-seal: input file missing for {name}")
        actual = compute_sha256(path)
        if actual != expected_hash:
            raise RuntimeError(
                f"Pre-seal: input {name} SHA256 drifted: {actual[:16]}... != {expected_hash[:16]}..."
            )

    current_output = str(Path(output_dir).resolve())
    if current_output != auth_hashes["output_dir"]:
        raise RuntimeError(
            f"Pre-seal: output_dir drifted: {current_output} != {auth_hashes['output_dir']}"
        )

    if list(cfg.ALL_TRACKS) != auth_hashes["tracks"]:
        raise RuntimeError("Pre-seal: tracks drifted during execution")

    if list(cfg.SEEDS) != auth_hashes["seeds"]:
        raise RuntimeError("Pre-seal: seeds drifted during execution")

    if cfg.APPROVED_PARENT_COMMIT != auth_hashes["approved_parent_commit"]:
        raise RuntimeError("Pre-seal: approved_parent_commit drifted during execution")


# ════════════════════════════════════════════════════════════════════════
# MDM parameter rebuild (P4-R6: track-specific namespace)
# ════════════════════════════════════════════════════════════════════════

def rebuild_mdm_params(beta, eta, gamma, n, repeat_id, delta, seed_namespace):
    """Regenerate sample with track-specific namespace, run MDM(delta)."""
    sample = generate_sample(beta, eta, gamma, n, repeat_id, seed=seed_namespace)
    result = run_method("mdm", sample, offset=delta)
    converged = result.get("converged", False)
    beta_hat = result.get("beta_hat", 0.0) if converged else 0.0
    eta_hat = result.get("eta_hat", 0.0) if converged else 0.0
    gamma_hat = result.get("gamma_hat", 0.0) if converged else 0.0

    if converged:
        valid, reason = check_prediction_validity(beta_hat, eta_hat, gamma_hat)
        if not valid:
            return {"beta_hat": 0.0, "eta_hat": 0.0, "gamma_hat": 0.0,
                    "failed": True, "failure_reason": reason}

    return {
        "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
        "failed": not converged,
        "failure_reason": "" if converged else "mdm_not_converged",
    }


def verify_sample_content_hash(beta, eta, gamma, n, repeat_id, seed_namespace,
                               expected_sha256=None):
    """Verify a reconstructed sample matches its approved artifact hash (P4-R6).

    Generates the sample deterministically and computes its SHA256. If
    expected_sha256 is provided, raises RuntimeError on mismatch.
    Returns the computed hash for logging/auditing.
    """
    sample = generate_sample(beta, eta, gamma, n, repeat_id, seed=seed_namespace)
    sample_bytes = np.asarray(sample, dtype=np.float64).tobytes()
    computed = hashlib.sha256(sample_bytes).hexdigest()
    if expected_sha256 is not None and computed != expected_sha256:
        raise RuntimeError(
            f"Sample content hash mismatch for ({beta},{gamma},{n},{repeat_id}) "
            f"ns={seed_namespace}: computed={computed[:16]}... != expected={expected_sha256[:16]}..."
        )
    return computed


# ════════════════════════════════════════════════════════════════════════
# Track execution functions (P4-R1: all tracks × all methods)
# ════════════════════════════════════════════════════════════════════════

def run_traditional_method(method, samples_df, track, seed_namespace):
    """Run a traditional method on samples. Returns estimation rows."""
    rows = []
    method_id = {"MDM-Default": "mdm", "MLE": "mle", "LSE": "lse", "WMLE": "wmle"}[method]

    for _, s in samples_df.iterrows():
        beta, goe, n_val, rid = s["beta"], s["gamma_over_eta"], int(s["n"]), int(s["repeat_id"])
        eta = 1.0
        gamma = goe * eta
        sample = generate_sample(beta, eta, gamma, n_val, rid, seed=seed_namespace)

        kwargs = {}
        if method == "MDM-Default":
            kwargs["offset"] = cfg.MDM_DEFAULT_DELTA

        try:
            result = run_method(method_id, sample, **kwargs)
            converged = result.get("converged", False)
            beta_hat = result.get("beta_hat", 0.0) if converged else 0.0
            eta_hat = result.get("eta_hat", 0.0) if converged else 0.0
            gamma_hat = result.get("gamma_hat", 0.0) if converged else 0.0

            if converged:
                valid, reason = check_prediction_validity(beta_hat, eta_hat, gamma_hat)
                if not valid:
                    converged = False
                    beta_hat = eta_hat = gamma_hat = 0.0
                else:
                    reason = ""
            else:
                reason = f"{method_id}_not_converged"

            rows.append(make_estimation_row(
                track, method, cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                beta, goe, n_val, rid, beta_hat, eta_hat, gamma_hat,
                not converged, reason if not converged else "",
            ))
        except Exception as exc:
            rows.append(make_estimation_row(
                track, method, cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                beta, goe, n_val, rid, 0.0, 0.0, 0.0,
                True, f"exception:{type(exc).__name__}",
            ))
    return rows


def run_direct_mlp_track(df_train_features, folds, seeds, track,
                         run_context, output_dir, df_eval_features=None):
    """Train Direct-MLP on E3b main-grid folds, evaluate on target features.

    df_train_features: E3b sample_features.csv (training source).
    df_eval_features: if provided, evaluate ALL these samples under every model
      (Tracks 2/3/4). If None, evaluate per-fold test combos from df_train_features
      (Track 1 main holdout).
    """
    rows = []
    for fold in folds:
        fold_name = fold["fold_name"]
        train_combos = fold["train_combos"]

        if df_eval_features is None:
            test_combos = fold["test_combos"]
            test_mask = df_train_features.apply(
                lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
            )
            df_eval = df_train_features[test_mask]
        else:
            df_eval = df_eval_features

        for seed in seeds:
            cp_key = f"Direct-MLP_{fold_name}_{seed}"
            cp = load_checkpoint(output_dir, track, cp_key)
            if cp is not None:
                verify_checkpoint_config(cp, run_context)
                for _, row in cp.iterrows():
                    rows.append(make_estimation_row(
                        track, "Direct-MLP", fold_name, seed,
                        row["beta"], row["gamma_over_eta"], int(row["n"]), int(row["repeat_id"]),
                        row["beta_hat"], row["eta_hat"], row["gamma_hat"],
                        bool(row["failed"]), row.get("failure_reason", ""),
                    ))
                continue

            X_train, Y_train, x_bar_train, meta = direct.build_training_data(
                df_train_features, train_combos
            )
            model, info = direct.train_direct_mlp(X_train, Y_train, x_bar_train, seed=seed)

            df_eval_si = direct.make_scale_invariant(df_eval)
            X_eval = direct.build_scale_invariant_X(df_eval_si, meta["zscore_means"], meta["zscore_stds"])
            x_bar_eval = df_eval["x_bar"].values.astype(np.float64)
            preds = direct.predict_direct_mlp(model, info, X_eval, x_bar_eval)

            model_rows = []
            for i, (_, feat_row) in enumerate(df_eval.iterrows()):
                beta_hat, eta_hat, gamma_hat = preds[i]
                valid, reason = check_prediction_validity(beta_hat, eta_hat, gamma_hat)
                if not valid:
                    beta_hat = eta_hat = gamma_hat = 0.0

                row = make_estimation_row(
                    track, "Direct-MLP", fold_name, seed,
                    feat_row["beta"], feat_row["gamma_over_eta"],
                    int(feat_row["n"]), int(feat_row["repeat_id"]),
                    beta_hat, eta_hat, gamma_hat,
                    not valid, reason,
                )
                model_rows.append(row)
                rows.append(row)

            save_checkpoint(output_dir, track, cp_key, pd.DataFrame(model_rows), run_context)

    return rows


def run_vector_mlp_track(df_features, df_risk, folds, seeds, track, seed_namespace,
                         fold_penalties, run_context, output_dir):
    """Train Vector-MLP, select deltas, rebuild MDM params. Returns estimation rows."""
    rows = []
    loss_cols = [c for c in df_risk.columns if c.startswith("loss_d")]

    for fold in folds:
        fold_name = fold["fold_name"]
        train_combos = fold["train_combos"]
        test_combos = fold["test_combos"]
        fold_penalty = fold_penalties[fold_name]

        train_mask = df_features.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos, axis=1
        )
        test_mask = df_features.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
        )
        df_train = df_features[train_mask]
        df_test = df_features[test_mask]

        train_keys = set((b, g, n) for b, g, n in train_combos)
        df_risk_train = df_risk[
            df_risk.apply(lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_keys, axis=1)
        ]

        train_keys_set = set(zip(
            df_train["beta"].astype(float), df_train["gamma_over_eta"].astype(float),
            df_train["n"].astype(int), df_train["repeat_id"].astype(int),
        ))
        loss_long = []
        for _, row in df_risk_train.iterrows():
            key = (float(row["beta"]), float(row["gamma_over_eta"]), int(row["n"]), int(row["repeat_id"]))
            if key in train_keys_set:
                for d_idx, col in enumerate(loss_cols):
                    d = e4.DELTA_GRID[d_idx]
                    val = float(row[col])
                    if np.isnan(val):
                        val = fold_penalty
                    loss_long.append({
                        "beta": key[0], "eta": 1.0, "gamma": key[1],
                        "gamma_over_eta": key[1], "n": key[2], "repeat_id": key[3],
                        "delta": d, "loss": val,
                    })
        df_loss_long = pd.DataFrame(loss_long)

        feat_cols_no_n = [c for c in e4.SAMPLE_FEATURE_COLS if c != "n"]
        df_train_merge = df_train[["beta", "gamma_over_eta", "n", "repeat_id"] + feat_cols_no_n].copy()
        df_loss_merged = df_loss_long.merge(df_train_merge, on=["beta", "gamma_over_eta", "n", "repeat_id"])

        samples_df, Y_vector = e4._pivot_risk_vectors(df_loss_merged, "loss", fold_penalty)
        X_vector = e4._build_X_from_samples(samples_df, *e4._fit_zscore_params(samples_df))
        means_vec, stds_vec = e4._fit_zscore_params(df_train)

        for seed in seeds:
            cp_key = f"Vector-MLP_{fold_name}_{seed}"
            cp = load_checkpoint(output_dir, track, cp_key)
            if cp is not None:
                verify_checkpoint_config(cp, run_context)
                for _, row in cp.iterrows():
                    rows.append(make_estimation_row(
                        track, "MDM-Vector-MLP", fold_name, seed,
                        row["beta"], row["gamma_over_eta"], int(row["n"]), int(row["repeat_id"]),
                        row["beta_hat"], row["eta_hat"], row["gamma_hat"],
                        bool(row["failed"]), row.get("failure_reason", ""),
                    ))
                continue

            vector_model, vector_scaler = e4._train_mlp(X_vector, Y_vector, seed=seed)

            test_keys_set = set(zip(
                df_test["beta"].astype(float), df_test["gamma_over_eta"].astype(float),
                df_test["n"].astype(int), df_test["repeat_id"].astype(int),
            ))
            test_risk = df_risk[
                df_risk.apply(lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1)
            ]
            test_loss_long = []
            for _, row in test_risk.iterrows():
                key = (float(row["beta"]), float(row["gamma_over_eta"]), int(row["n"]), int(row["repeat_id"]))
                if key in test_keys_set:
                    for d_idx, col in enumerate(loss_cols):
                        d = e4.DELTA_GRID[d_idx]
                        val = float(row[col])
                        if np.isnan(val):
                            val = fold_penalty
                        test_loss_long.append({
                            "beta": key[0], "gamma_over_eta": key[1],
                            "n": key[2], "repeat_id": key[3], "delta": d, "loss": val,
                        })
            df_test_loss = pd.DataFrame(test_loss_long)

            vector_eval_rows = e4._evaluate_single_model(
                vector_model, vector_scaler, df_test, df_test_loss,
                means_vec, stds_vec, fold_penalty, fold_name, seed,
            )

            model_rows = []
            for vrow in vector_eval_rows:
                beta = vrow["beta"]
                goe = vrow["gamma_over_eta"]
                n_val = vrow["n"]
                rid = vrow["repeat_id"]
                sel_delta = vrow["selected_delta"]

                params = rebuild_mdm_params(beta, 1.0, goe, n_val, rid, sel_delta, seed_namespace)
                row = make_estimation_row(
                    track, "MDM-Vector-MLP", fold_name, seed,
                    beta, goe, n_val, rid,
                    params["beta_hat"], params["eta_hat"], params["gamma_hat"],
                    params["failed"], params["failure_reason"],
                )
                model_rows.append(row)
                rows.append(row)

            save_checkpoint(output_dir, track, cp_key, pd.DataFrame(model_rows), run_context)

    return rows


# ════════════════════════════════════════════════════════════════════════
# Formal entry point (P4-R1: all tracks, P4-R2: authorization contract)
# ════════════════════════════════════════════════════════════════════════

def main(output_dir=None, tracks=None, seeds=None, resume=False):
    """P4 formal comparison entry point. Requires full authorization contract."""
    if output_dir is None:
        output_dir = cfg.FORMAL_OUTPUT_DIR
    output_dir = Path(output_dir)

    if tracks is None:
        tracks = cfg.ALL_TRACKS
    if seeds is None:
        seeds = cfg.SEEDS

    auth_hashes = verify_authorization_contract(output_dir, tracks, seeds, resume)

    lock_path = acquire_run_lock(output_dir)
    try:
        _run_formal(output_dir, tracks, seeds, resume, auth_hashes)
    finally:
        release_run_lock(output_dir)


def _validate_resume_manifest(output_dir, auth_hashes, tracks, seeds):
    """Validate existing manifest before resume. Fail-closed on any drift.

    Checks: git_commit, script/config hashes, tracks, seeds, authorization,
    output_dir, approved_parent_commit. Rejects unknown files in output dir.
    Returns the old manifest hash for lineage preservation.
    """
    output_path = Path(output_dir)
    manifest_path = output_path / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        old_manifest = json.load(f)

    old_manifest_hash = compute_sha256(manifest_path)

    if old_manifest.get("git_commit") != auth_hashes["start_head"]:
        raise RuntimeError(
            f"Resume: manifest git_commit={old_manifest.get('git_commit')} "
            f"!= current HEAD={auth_hashes['start_head']}"
        )
    if old_manifest.get("script_sha256") != auth_hashes["script_sha256"]:
        raise RuntimeError("Resume: manifest script_sha256 drifted")
    if old_manifest.get("config_sha256") != auth_hashes["config_sha256"]:
        raise RuntimeError("Resume: manifest config_sha256 drifted")
    if old_manifest.get("tracks") != list(tracks):
        raise RuntimeError("Resume: manifest tracks mismatch")
    if old_manifest.get("seeds") != list(seeds):
        raise RuntimeError("Resume: manifest seeds mismatch")
    if old_manifest.get("p4_formal_authorized") is not True:
        raise RuntimeError("Resume: manifest was not authorized")
    if old_manifest.get("approved_parent_commit") != auth_hashes.get("approved_parent_commit"):
        raise RuntimeError("Resume: manifest approved_parent_commit mismatch")

    allowed_prefixes = ("manifest.json", "run.lock", "checkpoint_", "SHA256SUMS")
    allowed_dirs = set(tracks)
    allowed_track_files = {"estimation.csv", "evaluation.csv", "results.json", "sample_hash_receipt.json"}
    for f in output_path.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(output_path).as_posix()
        top_dir = rel.split("/")[0] if "/" in rel else rel
        if top_dir in allowed_dirs:
            fname = f.name
            if fname.startswith("checkpoint_"):
                continue
            if fname not in allowed_track_files:
                raise RuntimeError(f"Resume: unknown file in track dir: {rel}")
            continue
        if any(rel.startswith(p) for p in allowed_prefixes):
            continue
        raise RuntimeError(f"Resume: unknown file in output dir: {rel}")

    return old_manifest_hash


def _run_formal(output_dir, tracks, seeds, resume, auth_hashes):
    """Internal formal execution (called under lock)."""
    folds = e4.get_combo_split()
    git_commit = get_git_commit()

    if resume:
        previous_manifest_sha256 = _validate_resume_manifest(output_dir, auth_hashes, tracks, seeds)
    else:
        previous_manifest_sha256 = None

    manifest = build_manifest(tracks, cfg.P4_METHODS)
    if previous_manifest_sha256:
        manifest["previous_manifest_sha256"] = previous_manifest_sha256
        manifest["resume_lineage"] = True
    atomic_write_json(manifest, output_dir / "manifest.json")

    study_dir = Path(__file__).resolve().parents[1]
    e3b_dir = study_dir / "artifacts" / "formal" / "E3b_vector_mlp"

    fold_penalties = _compute_frozen_fold_penalties(e3b_dir, folds)

    all_eval_dfs = []
    result_tables = {}

    for track in tracks:
        print(f"[P4] Track: {track}")
        ns = cfg.TRACK_SEED_NAMESPACE[track]
        input_sha = cfg._track_input_sha256(track)
        run_context = build_run_context(input_sha)

        if track == cfg.TRACK_MAIN_HOLDOUT:
            est_rows, fold_assignment = _execute_track_main(
                output_dir, folds, seeds, ns, run_context, e3b_dir, resume,
                fold_penalties
            )
        elif track in (cfg.TRACK_PARAM_INTERP, cfg.TRACK_N_INTERP):
            est_rows, fold_assignment = _execute_track_p2(
                output_dir, folds, seeds, ns, run_context, track, resume,
                fold_penalties
            )
        else:
            est_rows, fold_assignment = _execute_track_extrap(
                output_dir, folds, seeds, ns, run_context, resume,
                fold_penalties
            )

        df_est = pd.DataFrame(est_rows, columns=ESTIMATION_COLUMNS)
        df_eval = build_evaluation_layer(df_est, fold_penalties, fold_assignment=fold_assignment, seeds=seeds)
        all_eval_dfs.append(df_eval)

        contract = cfg.ROW_COUNT_CONTRACT[track]
        expected_eval = {m: contract["evaluation_per_method"] for m in cfg.P4_METHODS}
        verify_no_valid_only_filtering(df_eval, track=track, expected_rows_per_method=expected_eval)
        key_check = verify_sample_keys_identical(df_eval, track=track)
        if not key_check["ok"]:
            raise RuntimeError(f"Sample key verification failed for {track}: {key_check}")

        result_tables[track] = compute_result_tables(df_eval, track)

        track_dir = output_dir / track
        track_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_csv(df_est, track_dir / "estimation.csv")
        atomic_write_csv(df_eval, track_dir / "evaluation.csv")
        atomic_write_json(result_tables[track], track_dir / "results.json")

    df_eval_all = pd.concat(all_eval_dfs, ignore_index=True)
    atomic_write_csv(df_eval_all, output_dir / "evaluation_all.csv")
    atomic_write_json(result_tables, output_dir / "result_tables.json")

    _remove_checkpoints(output_dir)

    verify_pre_seal_state(output_dir, auth_hashes)

    allowlist = ["manifest.json", "evaluation_all.csv", "result_tables.json"]
    for track in tracks:
        allowlist.extend([
            f"{track}/estimation.csv",
            f"{track}/evaluation.csv",
            f"{track}/results.json",
        ])
        if track in (cfg.TRACK_PARAM_INTERP, cfg.TRACK_N_INTERP):
            receipt_path = output_dir / track / "sample_hash_receipt.json"
            if receipt_path.exists():
                allowlist.append(f"{track}/sample_hash_receipt.json")
    seal_recursive(output_dir, allowlist)
    print(f"[P4] Complete. Output: {output_dir}")


def _remove_checkpoints(output_dir):
    """Remove disposable checkpoint files before final sealing."""
    output_dir = Path(output_dir)
    for cp in output_dir.glob("checkpoint_*.csv"):
        cp.unlink()


def _verify_p2_sample_hashes(df_track, seed_namespace, expected_key_count=None):
    """Verify ALL reconstructed P2 samples match sealed per-sample hashes (P4-R6).

    STRICT requirements:
    - sample_sha256 column MUST exist
    - Every unique sample key MUST have exactly one valid 64-char SHA256
    - All rows with the same key MUST have the same hash (consistency)
    - No silent skipping of empty/nan/short hashes
    - If expected_key_count is provided, verified count must match
    Returns a receipt dict for sealing.
    """
    if "sample_sha256" not in df_track.columns:
        raise RuntimeError(
            "P2 sample hash verification: sample_sha256 column missing. "
            "Cannot proceed without sealed hashes."
        )

    checked = 0
    seen_keys = {}
    missing_hash_keys = []
    inconsistent_keys = []

    for _, row in df_track.iterrows():
        key = (row["beta"], row["gamma_over_eta"], int(row["n"]), int(row["repeat_id"]))
        expected = row.get("sample_sha256")
        expected_str = str(expected) if expected is not None else ""

        if not expected or expected_str == "nan" or len(expected_str) != 64:
            if key not in seen_keys:
                missing_hash_keys.append(key)
                seen_keys[key] = None
            continue

        if key in seen_keys:
            if seen_keys[key] is not None and seen_keys[key] != expected_str:
                inconsistent_keys.append(key)
            continue

        seen_keys[key] = expected_str
        verify_sample_content_hash(
            key[0], 1.0, key[1], key[2], key[3], seed_namespace,
            expected_sha256=expected_str
        )
        checked += 1

    if missing_hash_keys:
        raise RuntimeError(
            f"P2 sample hash verification: {len(missing_hash_keys)} keys missing valid "
            f"SHA256 (e.g. {missing_hash_keys[:3]}). All keys must have sealed hashes."
        )

    if inconsistent_keys:
        raise RuntimeError(
            f"P2 sample hash verification: {len(inconsistent_keys)} keys have "
            f"inconsistent hashes across rows (e.g. {inconsistent_keys[:3]})."
        )

    if checked == 0:
        raise RuntimeError("P2 sample hash verification: no samples to verify")

    if expected_key_count is not None and checked != expected_key_count:
        raise RuntimeError(
            f"P2 sample hash verification: verified {checked} keys but expected "
            f"{expected_key_count}. Possible missing or extra samples."
        )

    receipt = {
        "verified_samples": checked,
        "expected_key_count": expected_key_count,
        "total_unique_keys": len(seen_keys),
        "seed_namespace": seed_namespace,
        "status": "all_verified",
        "source_file_sha256": cfg.INPUT_SHA256.get("P2_baseline_per_sample_csv", "unknown"),
    }
    print(f"    P2 sample hash verification: {checked}/{len(seen_keys)} samples OK")
    return receipt


def _compute_frozen_fold_penalties(e3b_dir, folds):
    """Compute the 5 frozen P99 fold penalties from E3b training data.

    These are reused for ALL tracks and ALL methods.
    """
    import run_p3_direct_mlp as direct_mod
    df_features = pd.read_csv(e3b_dir / "sample_features.csv")
    df_risk = pd.read_csv(e3b_dir / "risk_curves.csv")

    penalties = {}
    for fold in folds:
        train_keys = set((b, g, n) for b, g, n in fold["train_combos"])
        train_mask = df_features.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in fold["train_combos"], axis=1
        )
        df_risk_train = df_risk[
            df_risk.apply(lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_keys, axis=1)
        ]
        penalties[fold["fold_name"]] = direct_mod.compute_fold_penalty(
            df_features[train_mask], df_risk_train, fold["train_combos"]
        )
    return penalties


def _execute_track_main(output_dir, folds, seeds, ns, run_context, e3b_dir, resume,
                        fold_penalties):
    """Execute Track 1: main_holdout.

    Returns (est_rows, fold_assignment) where fold_assignment maps
    sample_key → fold_name for traditional broadcast (each sample belongs
    to exactly one fold's test set).
    """
    features_path = e3b_dir / "sample_features.csv"
    risk_path = e3b_dir / "risk_curves.csv"

    actual = compute_sha256(features_path)
    if actual != cfg.INPUT_SHA256["E3b_sample_features_csv"]:
        raise RuntimeError(f"E3b sample_features SHA256 mismatch: {actual}")
    actual = compute_sha256(risk_path)
    if actual != cfg.INPUT_SHA256["E3b_risk_curves_csv"]:
        raise RuntimeError(f"E3b risk_curves SHA256 mismatch: {actual}")

    df_features = pd.read_csv(features_path)
    df_risk = pd.read_csv(risk_path)

    fold_assignment = {}
    for fold in folds:
        for beta, goe, n in fold["test_combos"]:
            for rid in range(cfg.EVAL_REPEATS):
                fold_assignment[(beta, goe, n, rid)] = fold["fold_name"]

    all_test_combos = set()
    for fold in folds:
        all_test_combos.update(fold["test_combos"])
    test_mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in all_test_combos, axis=1
    )
    df_test_features = df_features[test_mask]

    est_rows = []
    for method in cfg.TRADITIONAL_METHODS:
        print(f"  {method}...")
        est_rows.extend(run_traditional_method(method, df_test_features, cfg.TRACK_MAIN_HOLDOUT, ns))

    print("  Direct-MLP (15 models)...")
    est_rows.extend(run_direct_mlp_track(
        df_features, folds, seeds, cfg.TRACK_MAIN_HOLDOUT, run_context, output_dir,
        df_eval_features=None
    ))

    print("  MDM-Vector-MLP (15 models)...")
    est_rows.extend(run_vector_mlp_track(
        df_features, df_risk, folds, seeds, cfg.TRACK_MAIN_HOLDOUT, ns,
        fold_penalties, run_context, output_dir
    ))

    return est_rows, fold_assignment


def _execute_track_p2(output_dir, folds, seeds, ns, run_context, track, resume,
                      fold_penalties):
    """Execute Track 2/3: param_interp or n_interp (P2 samples).

    Uses sealed E3b fold penalties (same 5 P99 values for all tracks).
    P2 labels are P2-PI / P2-NI (not param_interp / n_interp).
    """
    study_dir = Path(__file__).resolve().parents[1]
    p2_dir = study_dir / "artifacts" / "formal" / "extended_validation" / "p2_generalization_v2"

    baseline_path = p2_dir / "p2_baseline_per_sample.csv"
    actual = compute_sha256(baseline_path)
    if actual != cfg.INPUT_SHA256["P2_baseline_per_sample_csv"]:
        raise RuntimeError(f"P2 baseline SHA256 mismatch: {actual}")

    df_p2 = pd.read_csv(baseline_path)
    p2_label = "P2-PI" if track == cfg.TRACK_PARAM_INTERP else "P2-NI"
    df_track = df_p2[df_p2["track"] == p2_label].copy()
    if len(df_track) == 0:
        raise RuntimeError(f"No P2 rows for label={p2_label}")

    samples_df = df_track.drop_duplicates(SAMPLE_KEY_COLS)

    hash_receipt = _verify_p2_sample_hashes(df_track, ns)
    receipt_dir = Path(output_dir) / track
    receipt_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(hash_receipt, receipt_dir / "sample_hash_receipt.json")

    est_rows = []
    for method in cfg.TRADITIONAL_METHODS:
        print(f"  {method}...")
        est_rows.extend(run_traditional_method(method, samples_df, track, ns))

    print("  Direct-MLP (15 models on P2 samples)...")
    e3b_dir = study_dir / "artifacts" / "formal" / "E3b_vector_mlp"
    df_features = pd.read_csv(e3b_dir / "sample_features.csv")

    p2_feat_rows = []
    for _, s in samples_df.iterrows():
        beta, goe, n_val, rid = s["beta"], s["gamma_over_eta"], int(s["n"]), int(s["repeat_id"])
        sample = generate_sample(beta, 1.0, goe, n_val, rid, seed=ns)
        feats = e4.compute_sample_features(sample)
        p2_feat_rows.append({"beta": beta, "eta": 1.0, "gamma": goe,
                             "gamma_over_eta": goe, "n": n_val,
                             "repeat_id": rid, **feats})
    df_p2_features = pd.DataFrame(p2_feat_rows)

    est_rows.extend(run_direct_mlp_track(
        df_features, folds, seeds, track, run_context, output_dir,
        df_eval_features=df_p2_features
    ))

    print("  MDM-Vector-MLP (15 models, P2 sealed deltas)...")
    vector_path = p2_dir / "p2_vector_per_sample.csv"
    actual_vec = compute_sha256(vector_path)
    if actual_vec != cfg.INPUT_SHA256["P2_vector_per_sample_csv"]:
        raise RuntimeError(f"P2 vector SHA256 mismatch: {actual_vec}")
    df_p2_vec = pd.read_csv(vector_path)
    df_p2_vec_track = df_p2_vec[df_p2_vec["track"] == p2_label].copy()

    for fold in folds:
        fold_name = fold["fold_name"]
        for seed in seeds:
            model_rows = df_p2_vec_track[
                (df_p2_vec_track["fold"] == fold_name) & (df_p2_vec_track["seed"] == seed)
            ]
            for _, row in model_rows.iterrows():
                beta = row["beta"]
                goe = row["gamma_over_eta"]
                n_val = int(row["n"])
                rid = int(row["repeat_id"])
                sel_delta = row["selected_delta"]
                params = rebuild_mdm_params(beta, 1.0, goe, n_val, rid, sel_delta, ns)
                est_rows.append(make_estimation_row(
                    track, "MDM-Vector-MLP", fold_name, seed,
                    beta, goe, n_val, rid,
                    params["beta_hat"], params["eta_hat"], params["gamma_hat"],
                    params["failed"], params["failure_reason"],
                ))

    return est_rows, None


def _execute_track_extrap(output_dir, folds, seeds, ns, run_context, resume,
                          fold_penalties):
    """Execute Track 4: extrap_diag (E4c_offgrid combos).

    Uses shared E3b fold penalties. E4d file contains E4b_boundary and
    E4c_offgrid tracks; we use ONLY E4c_offgrid.
    """
    study_dir = Path(__file__).resolve().parents[1]
    e4d_path = study_dir / "artifacts" / "formal" / "E4_robustness" / "E4d_selector_extrapolation.csv"

    actual = compute_sha256(e4d_path)
    if actual != cfg.INPUT_SHA256["E4d_selector_extrapolation_csv"]:
        raise RuntimeError(f"E4d SHA256 mismatch: {actual}")

    df_e4d = pd.read_csv(e4d_path, low_memory=False)
    df_e4d = df_e4d[df_e4d["track"] == "E4c_offgrid"].copy()
    if len(df_e4d) == 0:
        raise RuntimeError("No E4c_offgrid rows in E4d file")
    samples_df = df_e4d.drop_duplicates(SAMPLE_KEY_COLS)

    est_rows = []
    for method in cfg.TRADITIONAL_METHODS:
        print(f"  {method}...")
        est_rows.extend(run_traditional_method(method, samples_df, cfg.TRACK_EXTRAP, ns))

    print("  Direct-MLP (15 models on E4c_offgrid samples)...")
    e3b_dir = study_dir / "artifacts" / "formal" / "E3b_vector_mlp"
    df_features = pd.read_csv(e3b_dir / "sample_features.csv")

    e4d_feat_rows = []
    for _, s in samples_df.iterrows():
        beta, goe, n_val, rid = s["beta"], s["gamma_over_eta"], int(s["n"]), int(s["repeat_id"])
        sample = generate_sample(beta, 1.0, goe, n_val, rid, seed=ns)
        feats = e4.compute_sample_features(sample)
        e4d_feat_rows.append({"beta": beta, "eta": 1.0, "gamma": goe,
                              "gamma_over_eta": goe, "n": n_val,
                              "repeat_id": rid, **feats})
    df_e4d_features = pd.DataFrame(e4d_feat_rows)

    est_rows.extend(run_direct_mlp_track(
        df_features, folds, seeds, cfg.TRACK_EXTRAP, run_context, output_dir,
        df_eval_features=df_e4d_features
    ))

    print("  MDM-Vector-MLP (15 models, E4c_offgrid sealed deltas)...")
    for fold in folds:
        fold_name = fold["fold_name"]
        for seed in seeds:
            e4d_model = df_e4d[(df_e4d["fold"] == fold_name) & (df_e4d["seed"] == seed)]
            for _, row in e4d_model.iterrows():
                beta = row["beta"]
                goe = row["gamma_over_eta"]
                n_val = int(row["n"])
                rid = int(row["repeat_id"])
                sel_delta = row["selected_delta"]
                params = rebuild_mdm_params(beta, 1.0, goe, n_val, rid, sel_delta, ns)
                est_rows.append(make_estimation_row(
                    cfg.TRACK_EXTRAP, "MDM-Vector-MLP", fold_name, seed,
                    beta, goe, n_val, rid,
                    params["beta_hat"], params["eta_hat"], params["gamma_hat"],
                    params["failed"], params["failure_reason"],
                ))

    return est_rows, None


# ════════════════════════════════════════════════════════════════════════
# Legacy compatibility (used by smoke and tests)
# ════════════════════════════════════════════════════════════════════════

def make_per_sample_row(track, fold, seed, method, beta, goe, n, repeat_id,
                        beta_hat, eta_hat, gamma_hat, beta_true, eta_true, gamma_true,
                        failed, failure_reason, failure_penalty):
    """Legacy per-sample row (evaluation-layer format)."""
    if failed:
        loss = failure_penalty
        loss_complete = float("nan")
    else:
        loss_complete = direct.compute_param_loss(beta_hat, beta_true, eta_hat, eta_true, gamma_hat, gamma_true)
        loss = loss_complete
    return {
        "track": track, "fold": fold, "seed": seed, "method": method,
        "beta": beta_true, "gamma_over_eta": goe, "n": n, "repeat_id": repeat_id,
        "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
        "true_loss": loss, "true_loss_complete_case": loss_complete,
        "failed": failed, "failure_reason": failure_reason, "failure_penalty": failure_penalty,
    }


def apply_failure_contract_p4(rows):
    for row in rows:
        penalty = row.get("failure_penalty", 0.0)
        if penalty <= 0:
            raise direct.PenaltyError(f"failure_penalty must be > 0, got {penalty}")
        if row["failed"]:
            row["true_loss"] = penalty
    return rows


def verify_model_first_not_merged(df_all, method_name):
    df = df_all[df_all["method"] == method_name]
    if df.empty:
        return True
    if method_name not in cfg.LEARNING_METHODS:
        return True
    n_models = df.groupby(["fold", "seed"]).ngroups
    return n_models == cfg.N_MODELS


if __name__ == "__main__":
    main()
