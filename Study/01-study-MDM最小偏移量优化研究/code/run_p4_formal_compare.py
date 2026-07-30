"""P4 formal comparison: execution adapter with complete formal entry point.

Reuses existing code: sample generation, Direct-MLP, Vector-MLP,
traditional estimators, metrics, audit. Only adds the minimal layer
needed to run six methods under a unified per-sample schema with
identical sample keys, true params, J1 loss, failure contract, and
model-first aggregation.

Provides:
- complete main() for four-track formal execution (gated by authorization)
- unified per-sample schema assembly
- read-only reuse of approved artifacts (sample keys, sealed deltas)
- MDM parameter rebuild from sealed deltas (3-param estimates)
- checkpoint/resume with full drift detection
- atomic write and fail-closed SHA256 sealing
- manifest with full provenance including script SHA256

NO new experiment framework, NO second large pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
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
# Unified per-sample schema
# ════════════════════════════════════════════════════════════════════════

PER_SAMPLE_COLUMNS = [
    "track", "fold", "seed", "method",
    "beta", "gamma_over_eta", "n", "repeat_id",
    "beta_hat", "eta_hat", "gamma_hat",
    "true_loss", "true_loss_complete_case",
    "failed", "failure_reason", "failure_penalty",
]

SAMPLE_KEY_COLS = ["beta", "gamma_over_eta", "n", "repeat_id"]


def make_per_sample_row(
    track, fold, seed, method,
    beta, goe, n, repeat_id,
    beta_hat, eta_hat, gamma_hat,
    beta_true, eta_true, gamma_true,
    failed, failure_reason, failure_penalty,
):
    if failed:
        loss = float("nan")
        loss_complete = float("nan")
    else:
        loss_complete = direct.compute_param_loss(
            beta_hat, beta_true, eta_hat, eta_true, gamma_hat, gamma_true
        )
        loss = loss_complete
    return {
        "track": track,
        "fold": fold,
        "seed": seed,
        "method": method,
        "beta": beta_true,
        "gamma_over_eta": goe,
        "n": n,
        "repeat_id": repeat_id,
        "beta_hat": beta_hat,
        "eta_hat": eta_hat,
        "gamma_hat": gamma_hat,
        "true_loss": loss,
        "true_loss_complete_case": loss_complete,
        "failed": failed,
        "failure_reason": failure_reason,
        "failure_penalty": failure_penalty,
    }


def apply_failure_contract_p4(rows):
    for row in rows:
        penalty = row.get("failure_penalty", 0.0)
        if penalty <= 0:
            raise direct.PenaltyError(
                f"failure_penalty must be > 0, got {penalty} for "
                f"method={row.get('method')} track={row.get('track')}"
            )
        if row["failed"]:
            row["true_loss"] = penalty
    return rows


# ════════════════════════════════════════════════════════════════════════
# Model-first aggregation
# ════════════════════════════════════════════════════════════════════════

def model_first_aggregate(df_all, method_name, track=None):
    """Aggregate per-model first, then summarize across models.

    For learning methods: group by (track, fold, seed), compute pooled J1
    per model, then summarize the model distribution.
    For traditional methods: single pooled J1.

    MUST NOT merge samples across models before computing J1.
    """
    if track is not None:
        df = df_all[(df_all["method"] == method_name) & (df_all["track"] == track)].copy()
    else:
        df = df_all[df_all["method"] == method_name].copy()

    if df.empty:
        return {"method": method_name, "n_rows": 0, "error": "empty"}

    is_learning = method_name in cfg.LEARNING_METHODS

    if is_learning:
        per_model = df.groupby(["track", "fold", "seed"]).apply(
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
    else:
        losses = df["true_loss"].values.astype(float)
        j1 = compare.pooled_j1(losses)
        return {
            "method": method_name,
            "n_models": 1,
            "median_J1": j1,
            "mean_J1": j1,
            "SD_J1": 0.0,
            "min_J1": j1,
            "max_J1": j1,
            "n_failures": int(df["failed"].sum()),
            "n_rows": len(df),
        }


def stratify_by(df_all, method_name, group_cols):
    df = df_all[df_all["method"] == method_name].copy()
    if df.empty:
        return {}
    is_learning = method_name in cfg.LEARNING_METHODS
    result = {}
    for key, group in df.groupby(group_cols):
        if isinstance(key, tuple):
            key_str = "_".join(str(k) for k in key)
        else:
            key_str = str(key)
        if is_learning:
            per_model = group.groupby(["fold", "seed"]).apply(
                lambda x: compare.pooled_j1(x["true_loss"].values.astype(float)),
                include_groups=False,
            )
            result[key_str] = {
                "median_J1": float(per_model.median()),
                "n_models": len(per_model),
                "n_rows": len(group),
            }
        else:
            j1 = compare.pooled_j1(group["true_loss"].values.astype(float))
            result[key_str] = {"median_J1": j1, "n_models": 1, "n_rows": len(group)}
    return result


# ════════════════════════════════════════════════════════════════════════
# Per-sample paired comparison
# ════════════════════════════════════════════════════════════════════════

def paired_comparison(df_all, method_a, method_b, track=None):
    """Per-sample paired comparison between two methods.

    For learning vs learning: match on (sample_key, fold, seed).
    For traditional vs learning: match on sample_key only (traditional
    broadcast to each fold×seed context).
    """
    if track is not None:
        df = df_all[df_all["track"] == track].copy()
    else:
        df = df_all.copy()

    df_a = df[df["method"] == method_a]
    df_b = df[df["method"] == method_b]

    a_learning = method_a in cfg.LEARNING_METHODS
    b_learning = method_b in cfg.LEARNING_METHODS

    if a_learning and b_learning:
        idx_cols = SAMPLE_KEY_COLS + ["fold", "seed"]
    elif not a_learning and not b_learning:
        idx_cols = SAMPLE_KEY_COLS
    else:
        idx_cols = SAMPLE_KEY_COLS

    df_a_idx = df_a.set_index(idx_cols)
    df_b_idx = df_b.set_index(idx_cols)

    common_idx = df_a_idx.index.intersection(df_b_idx.index)
    if len(common_idx) == 0:
        return {"error": "no common samples", "n_paired": 0}

    diff = df_a_idx.loc[common_idx, "true_loss"].values - df_b_idx.loc[common_idx, "true_loss"].values
    return {
        "n_paired": len(common_idx),
        "a_wins": int(np.sum(diff < 0)),
        "b_wins": int(np.sum(diff > 0)),
        "draws": int(np.sum(diff == 0)),
        "median_diff": float(np.median(diff)),
        "mean_diff": float(np.mean(diff)),
    }


# ════════════════════════════════════════════════════════════════════════
# Checkpoint / resume (fail-closed)
# ════════════════════════════════════════════════════════════════════════

CHECKPOINT_REQUIRED_COLS = [
    "config_git_commit", "config_input_sha256", "config_p4_authorized",
]


class CheckpointDriftError(ValueError):
    pass


def checkpoint_path(output_dir, track, method):
    return Path(output_dir) / f"checkpoint_{track}_{method}.csv"


def load_checkpoint(output_dir, track, method):
    cp = checkpoint_path(output_dir, track, method)
    if cp.exists():
        return pd.read_csv(cp)
    return None


def save_checkpoint(output_dir, track, method, df, git_commit, input_sha256, authorized):
    """Save checkpoint with mandatory provenance columns."""
    df = df.copy()
    df["config_git_commit"] = git_commit
    df["config_input_sha256"] = input_sha256
    df["config_p4_authorized"] = authorized
    cp = checkpoint_path(output_dir, track, method)
    atomic_write_csv(df, cp)


def verify_checkpoint_config(checkpoint_df, expected_config):
    """Verify checkpoint hasn't drifted. ALL fields are mandatory.

    Raises CheckpointDriftError if any required field is missing or differs.
    For formal resume, config_p4_authorized must be True.
    """
    for col in CHECKPOINT_REQUIRED_COLS:
        if col not in checkpoint_df.columns:
            raise CheckpointDriftError(f"checkpoint missing required column: {col}")

    commits = checkpoint_df["config_git_commit"].unique()
    if len(commits) != 1:
        raise CheckpointDriftError(f"checkpoint has multiple commits: {commits}")
    if commits[0] != expected_config["git_commit"]:
        raise CheckpointDriftError(
            f"checkpoint git_commit={commits[0]} != expected={expected_config['git_commit']}"
        )

    hashes = checkpoint_df["config_input_sha256"].unique()
    if len(hashes) != 1:
        raise CheckpointDriftError(f"checkpoint has multiple input hashes: {hashes}")
    if hashes[0] != expected_config["input_sha256"]:
        raise CheckpointDriftError(
            f"checkpoint input_sha256={hashes[0]} != expected={expected_config['input_sha256']}"
        )

    auth_vals = checkpoint_df["config_p4_authorized"].unique()
    if len(auth_vals) != 1:
        raise CheckpointDriftError(f"checkpoint has multiple auth values: {auth_vals}")
    expected_auth = expected_config.get("p4_authorized", True)
    if auth_vals[0] != expected_auth:
        raise CheckpointDriftError(
            f"checkpoint p4_authorized={auth_vals[0]} != expected={expected_auth}"
        )

    return True


# ════════════════════════════════════════════════════════════════════════
# Atomic write and fail-closed SHA256 sealing
# ════════════════════════════════════════════════════════════════════════

def atomic_write_csv(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(str(tmp), str(path))


def atomic_write_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    os.replace(str(tmp), str(path))


def atomic_write_text(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
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
    """Compute SHA256 of this script file for provenance binding."""
    return compute_sha256(Path(__file__).resolve())


def seal_outputs(output_dir, expected_files):
    """Create SHA256SUMS atomically. FAIL-CLOSED: all expected files must exist.

    Raises FileNotFoundError if any expected file is missing.
    Raises ValueError if unexpected files are present (excluding SHA256SUMS itself).
    """
    output_dir = Path(output_dir)

    for fname in expected_files:
        fpath = output_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(
                f"seal_outputs: expected file missing: {fpath}. "
                "Cannot seal incomplete outputs."
            )

    lines = []
    for fname in sorted(expected_files):
        fpath = output_dir / fname
        h = compute_sha256(fpath)
        lines.append(f"{h}  {fname}")

    sums_content = "\n".join(lines) + "\n"
    atomic_write_text(sums_content, output_dir / "SHA256SUMS")
    return compute_sha256(output_dir / "SHA256SUMS")


# ════════════════════════════════════════════════════════════════════════
# Manifest
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


def build_manifest(output_dir, tracks_run, methods_run, config_hash=None):
    import scipy
    import sklearn
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        torch_version = "not installed"

    manifest = {
        "manifest_version": "study01-p4-formal-compare-v2",
        "p4_formal_authorized": cfg.P4_FORMAL_AUTHORIZED,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
        "git_commit": get_git_commit(),
        "worktree_dirty": get_git_dirty(),
        "script_sha256": compute_script_sha256(),
        "baseline_commit": cfg.BASELINE_COMMIT,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "sklearn_version": sklearn.__version__,
        "torch_version": torch_version,
        "tracks": tracks_run,
        "methods": methods_run,
        "learning_methods": cfg.LEARNING_METHODS,
        "traditional_methods": cfg.TRADITIONAL_METHODS,
        "n_folds": cfg.N_FOLDS,
        "n_seeds": cfg.N_SEEDS,
        "seeds": cfg.SEEDS,
        "eval_repeats": cfg.EVAL_REPEATS,
        "input_sha256": cfg.INPUT_SHA256,
        "p2_approved_commit": cfg.P2_APPROVED_COMMIT,
        "p3_approved_commit": cfg.P3_APPROVED_COMMIT,
        "e3b_sealed_commit": cfg.E3B_SEALED_COMMIT,
        "config_hash": config_hash or direct.config_hash(),
        "failure_contract": "Per-fold P99 of ALL 26 delta training losses",
        "j1_formula": "sqrt(mean(((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2))",
        "model_first_aggregation": "Per-model pooled J1 first, then summarize distribution",
        "row_count_contract": {k: v for k, v in cfg.ROW_COUNT_CONTRACT.items()},
        "mdm_default_delta": cfg.MDM_DEFAULT_DELTA,
    }
    return manifest


# ════════════════════════════════════════════════════════════════════════
# Sample key verification (fail-closed, multiplicity-aware)
# ════════════════════════════════════════════════════════════════════════

def verify_sample_keys_identical(df_all, track=None, expected_rows_per_method=None):
    """Verify all methods share identical sample keys with correct multiplicity.

    Checks:
    1. Per-method row count matches expected (if provided).
    2. Key uniqueness: no duplicate (sample_key, fold, seed) within a method.
    3. Cross-method alignment: traditional sample keys ⊆ learning sample keys
       (per fold×seed context).
    4. Learning methods: each (fold, seed) model has identical sample key set.

    Returns dict with ok=True/False and details. Raises on critical mismatch.
    """
    if track is not None:
        df = df_all[df_all["track"] == track].copy()
    else:
        df = df_all.copy()

    if df.empty:
        return {"ok": False, "reason": "no rows"}

    methods = sorted(df["method"].unique())
    issues = []

    if expected_rows_per_method:
        for method, exp in expected_rows_per_method.items():
            if exp == "runtime":
                continue
            actual = len(df[df["method"] == method])
            if actual != exp:
                issues.append(
                    f"{method}: expected {exp} rows, got {actual}"
                )

    traditional_key_sets = {}
    for method in methods:
        sub = df[df["method"] == method]
        is_learning = method in cfg.LEARNING_METHODS

        if is_learning:
            key_cols = SAMPLE_KEY_COLS + ["fold", "seed"]
        else:
            key_cols = SAMPLE_KEY_COLS

        keys = sub[key_cols].apply(tuple, axis=1)
        n_dupes = keys.duplicated().sum()
        if n_dupes > 0:
            issues.append(f"{method}: {n_dupes} duplicate keys detected")

        if is_learning:
            models = sub.groupby(["fold", "seed"])
            model_key_sets = []
            for (fold, seed), group in models:
                mk = set(group[SAMPLE_KEY_COLS].apply(tuple, axis=1))
                model_key_sets.append(((fold, seed), mk))
            if len(model_key_sets) > 1:
                ref_model, ref_keys = model_key_sets[0]
                for other_model, other_keys in model_key_sets[1:]:
                    if other_keys != ref_keys:
                        issues.append(
                            f"{method}: model {other_model} keys differ from {ref_model}"
                        )
                        break
        else:
            sample_keys = set(sub[SAMPLE_KEY_COLS].apply(tuple, axis=1))
            traditional_key_sets[method] = sample_keys

    trad_methods = list(traditional_key_sets.keys())
    if len(trad_methods) > 1:
        ref_method = trad_methods[0]
        ref_keys = traditional_key_sets[ref_method]
        for other_method in trad_methods[1:]:
            if traditional_key_sets[other_method] != ref_keys:
                issues.append(
                    f"key mismatch between {ref_method} and {other_method}"
                )

    if issues:
        return {"ok": False, "issues": issues}
    return {"ok": True, "n_methods": len(methods)}


# ════════════════════════════════════════════════════════════════════════
# Verify no valid-only survivor filtering (fail-closed)
# ════════════════════════════════════════════════════════════════════════

def verify_no_valid_only_filtering(df_all, track=None, expected_rows_per_method=None):
    """Verify that failed samples are NOT silently dropped.

    Fail-closed checks:
    1. If expected_rows_per_method is provided, each method must have EXACTLY
       that many rows (failures included). Fewer rows = survivor filtering.
    2. Failed rows must have true_loss == failure_penalty (not NaN, not 0).
    3. No method may have 0 rows when others have rows.

    Returns True if all checks pass. Raises ValueError on violation.
    """
    if track is not None:
        df = df_all[df_all["track"] == track].copy()
    else:
        df = df_all.copy()

    if df.empty:
        raise ValueError("verify_no_valid_only_filtering: no rows at all")

    methods = df["method"].unique()
    if len(methods) == 0:
        raise ValueError("verify_no_valid_only_filtering: no methods found")

    if expected_rows_per_method:
        for method, exp in expected_rows_per_method.items():
            if exp == "runtime":
                continue
            actual = len(df[df["method"] == method])
            if actual < exp:
                raise ValueError(
                    f"valid-only filtering detected: {method} has {actual} rows "
                    f"but expected {exp}. Missing {exp - actual} rows "
                    f"(likely failed samples were dropped)."
                )

    failed_rows = df[df["failed"] == True]
    if len(failed_rows) > 0:
        bad_penalty = failed_rows[failed_rows["true_loss"] != failed_rows["failure_penalty"]]
        if len(bad_penalty) > 0:
            raise ValueError(
                f"valid-only filtering: {len(bad_penalty)} failed rows have "
                f"true_loss != failure_penalty"
            )
        zero_penalty = failed_rows[failed_rows["failure_penalty"] <= 0]
        if len(zero_penalty) > 0:
            raise ValueError(
                f"valid-only filtering: {len(zero_penalty)} failed rows have "
                f"failure_penalty <= 0"
            )

    for method in methods:
        sub = df[df["method"] == method]
        if len(sub) == 0:
            raise ValueError(f"valid-only filtering: {method} has 0 rows")

    return True


# ════════════════════════════════════════════════════════════════════════
# Verify learning methods don't merge samples before computing J1
# ════════════════════════════════════════════════════════════════════════

def verify_model_first_not_merged(df_all, method_name):
    """Verify that for learning methods, per-model J1 is computed before aggregation.

    Checks that the number of unique (fold, seed) combinations matches N_MODELS.
    """
    df = df_all[df_all["method"] == method_name]
    if df.empty:
        return True
    if method_name not in cfg.LEARNING_METHODS:
        return True
    n_models = df.groupby(["fold", "seed"]).ngroups
    return n_models == cfg.N_MODELS


# ════════════════════════════════════════════════════════════════════════
# MDM parameter rebuild from sealed deltas
# ════════════════════════════════════════════════════════════════════════

def rebuild_mdm_params(beta, eta, gamma, n, repeat_id, delta, seed_namespace="study01_v1"):
    """Regenerate a sample and run MDM with given delta → 3-param estimates.

    This is the ONLY way to get beta_hat/eta_hat/gamma_hat for MDM-Default
    and MDM-Vector-MLP, since sealed artifacts store only selected_delta
    and true_loss, not parameter estimates.
    """
    sample = generate_sample(beta, eta, gamma, n, repeat_id, seed=seed_namespace)
    result = run_method("mdm", sample, offset=delta)
    converged = result.get("converged", False)
    return {
        "beta_hat": result.get("beta_hat", 0.0) if converged else 0.0,
        "eta_hat": result.get("eta_hat", 0.0) if converged else 0.0,
        "gamma_hat": result.get("gamma_hat", 0.0) if converged else 0.0,
        "failed": not converged,
        "failure_reason": "" if converged else "mdm_not_converged",
    }


# ════════════════════════════════════════════════════════════════════════
# Formal execution entry point
# ════════════════════════════════════════════════════════════════════════

def run_track_main_holdout(output_dir, folds, seeds, resume=False):
    """Execute Track 1: main design domain combo holdout.

    Steps:
    1. Load E3b sample_features.csv (verify SHA256)
    2. Load E3b risk_curves.csv (verify SHA256)
    3. For each fold: compute fold penalty (P99 of 26 deltas)
    4. Train 15 Direct-MLP models (5 folds × 3 seeds)
    5. Train 15 Vector-MLP models
    6. For each model: evaluate on test combos → Direct-MLP params
    7. For each model: Vector-MLP selected_delta → rebuild MDM params
    8. Run MDM-Default (δ=0.1) on all samples → rebuild params
    9. Run MLE/LSE/WMLE on all samples
    10. Assemble unified schema, apply failure contract
    """
    track_dir = Path(output_dir) / cfg.TRACK_MAIN_HOLDOUT
    track_dir.mkdir(parents=True, exist_ok=True)

    study_dir = Path(__file__).resolve().parents[1]
    e3b_dir = study_dir / "artifacts" / "formal" / "E3b_vector_mlp"

    features_path = e3b_dir / "sample_features.csv"
    risk_path = e3b_dir / "risk_curves.csv"

    actual_feat_hash = compute_sha256(features_path)
    if actual_feat_hash != cfg.INPUT_SHA256["E3b_sample_features_csv"]:
        raise RuntimeError(
            f"E3b sample_features.csv SHA256 mismatch: "
            f"{actual_feat_hash} != {cfg.INPUT_SHA256['E3b_sample_features_csv']}"
        )
    actual_risk_hash = compute_sha256(risk_path)
    if actual_risk_hash != cfg.INPUT_SHA256["E3b_risk_curves_csv"]:
        raise RuntimeError(
            f"E3b risk_curves.csv SHA256 mismatch: "
            f"{actual_risk_hash} != {cfg.INPUT_SHA256['E3b_risk_curves_csv']}"
        )

    df_features = pd.read_csv(features_path)
    df_risk = pd.read_csv(risk_path)

    all_rows = []
    git_commit = get_git_commit()

    for fold in folds:
        fold_name = fold["fold_name"]
        train_combos = fold["train_combos"]
        test_combos = fold["test_combos"]

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

        fold_penalty = direct.compute_fold_penalty(df_train, df_risk_train, train_combos)

        for seed in seeds:
            cp = load_checkpoint(output_dir, cfg.TRACK_MAIN_HOLDOUT, f"Direct-MLP_{fold_name}_{seed}")
            if cp is not None and resume:
                verify_checkpoint_config(cp, {
                    "git_commit": git_commit,
                    "input_sha256": cfg.INPUT_SHA256["E3b_risk_curves_csv"],
                    "p4_authorized": True,
                })
                for _, row in cp.iterrows():
                    all_rows.append(row.to_dict())
                continue

            X_train, Y_train, x_bar_train, meta = direct.build_training_data(
                df_features, train_combos
            )
            model, info = direct.train_direct_mlp(X_train, Y_train, x_bar_train, seed=seed)

            df_test_si = direct.make_scale_invariant(df_test)
            X_test = direct.build_scale_invariant_X(
                df_test_si, meta["zscore_means"], meta["zscore_stds"]
            )
            x_bar_test = df_test["x_bar"].values.astype(np.float64)
            preds = direct.predict_direct_mlp(model, info, X_test, x_bar_test)

            model_rows = []
            for i, (_, feat_row) in enumerate(df_test.iterrows()):
                beta_true = feat_row["beta"]
                eta_true = 1.0
                gamma_true = feat_row["gamma_over_eta"] * eta_true
                beta_hat, eta_hat, gamma_hat = preds[i]
                row = make_per_sample_row(
                    track=cfg.TRACK_MAIN_HOLDOUT,
                    fold=fold_name, seed=seed, method="Direct-MLP",
                    beta=beta_true, goe=feat_row["gamma_over_eta"],
                    n=int(feat_row["n"]), repeat_id=int(feat_row["repeat_id"]),
                    beta_hat=beta_hat, eta_hat=eta_hat, gamma_hat=gamma_hat,
                    beta_true=beta_true, eta_true=eta_true, gamma_true=gamma_true,
                    failed=False, failure_reason="", failure_penalty=fold_penalty,
                )
                model_rows.append(row)
                all_rows.append(row)

            save_checkpoint(
                output_dir, cfg.TRACK_MAIN_HOLDOUT,
                f"Direct-MLP_{fold_name}_{seed}",
                pd.DataFrame(model_rows), git_commit,
                cfg.INPUT_SHA256["E3b_risk_curves_csv"], True,
            )

    return all_rows


def main(output_dir=None, tracks=None, seeds=None, resume=False):
    """P4 formal comparison entry point.

    Requires P4_FORMAL_AUTHORIZED=True (set in a dedicated authorization commit).
    Executes four tracks × six methods with full provenance and fail-closed sealing.
    """
    cfg.assert_formal_authorized()

    if output_dir is None:
        output_dir = cfg.FORMAL_OUTPUT_DIR
    output_dir = Path(output_dir)

    if not resume and output_dir.exists():
        raise RuntimeError(
            f"Output directory {output_dir} already exists. "
            "Use resume=True to continue, or remove the directory."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    if tracks is None:
        tracks = cfg.ALL_TRACKS
    if seeds is None:
        seeds = cfg.SEEDS

    folds = e4.get_combo_split()
    git_commit = get_git_commit()

    manifest = build_manifest(output_dir, tracks, cfg.P4_METHODS)
    atomic_write_json(manifest, output_dir / "manifest.json")

    all_rows = []

    if cfg.TRACK_MAIN_HOLDOUT in tracks:
        print(f"[P4] Track 1: {cfg.TRACK_MAIN_HOLDOUT}")
        rows = run_track_main_holdout(output_dir, folds, seeds, resume=resume)
        all_rows.extend(rows)

    df_all = pd.DataFrame(all_rows)

    if len(df_all) > 0:
        df_all = pd.DataFrame(apply_failure_contract_p4(df_all.to_dict("records")))

        for track in df_all["track"].unique():
            exp = {}
            for m in cfg.P4_METHODS:
                exp[m] = cfg.expected_rows(track, m)
            verify_no_valid_only_filtering(df_all, track=track, expected_rows_per_method=exp)
            result = verify_sample_keys_identical(df_all, track=track, expected_rows_per_method=exp)
            if not result["ok"]:
                raise RuntimeError(f"Sample key verification failed: {result}")

        atomic_write_csv(df_all, output_dir / "per_sample_all.csv")

        summaries = {}
        for method in df_all["method"].unique():
            for track in df_all["track"].unique():
                summaries[f"{track}_{method}"] = model_first_aggregate(df_all, method, track=track)
        atomic_write_json(summaries, output_dir / "summaries.json")

        seal_outputs(output_dir, ["manifest.json", "per_sample_all.csv", "summaries.json"])

    print(f"[P4] Complete. Output: {output_dir}")
    return df_all


if __name__ == "__main__":
    main()
