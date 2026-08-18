"""Unseen-beta confirmation for the mean-normalized Study01 selector.

This is the minimum downstream rerun needed after selecting the ordered
``X / mean(X)`` representation.  It reuses the existing 160-combination,
48,000-sample, 26-delta loss scan and the E6 training/evaluation functions;
MDM is not rerun.  For each held-out beta and each n an independent MLP is
trained on the other seven beta levels, using the same architecture, seeds,
failure penalty and train-fold-only scalers as E6.  The only changed input is
the per-sample representation.

Large per-sample blocks are ignored.  Compact summaries are written to
``artifacts/formal/E8_mean_normalized_selector/unseen_beta``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (
        STUDY_CODE_DIR,
        os.path.join(os.path.dirname(os.path.dirname(STUDY_CODE_DIR)), "python")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import dim_raw_config as CFG
import paper_support as PS
import run_E6b_dimensional_raw_specialist as E6
import run_E7_scale_invariant_input_screen as E7
import run_b1_unseen_beta as B1

_THIS = sys.modules[__name__]

CONTRACT_VERSION = "E8_mean_normalized_unseen_beta_v1"
MODEL_NAME = "Mean-Normalized-MLP"
SEEDS = list(CFG.STABILITY_SEEDS)
OUT_DIR = os.path.join(
    E6.STUDY_ROOT, "artifacts", "formal", "E8_mean_normalized_selector",
    "unseen_beta")
RESULTS_DIR = os.path.join(OUT_DIR, "results")


def mean_normalized_map(raw_map: dict) -> dict:
    """Return exactly the selected E7 representation for every sample key."""
    return {
        key: E7.represent_sample(sample, "mean")
        for key, sample in raw_map.items()
    }


def block_path(held_beta: float, n_val: int, seed: int) -> str:
    return os.path.join(
        RESULTS_DIR, f"block_beta{held_beta}_n{n_val}_seed{seed}.csv")


def run_beta_fold(fold: dict, fold_data: dict, n_val: int, seed: int,
                  input_map: dict, baseline: pd.DataFrame, log) -> pd.DataFrame:
    held_beta = float(fold["held_out_beta"])
    path = block_path(held_beta, n_val, seed)
    if os.path.isfile(path):
        log(f"  [skip] beta={held_beta} n={n_val} seed={seed}")
        return pd.read_csv(path)

    keys_tr, x_tr, y_tr, _ = E6.pivot_raw_vector(
        fold_data["df_train"], input_map, n_val)
    keys_te, x_te, y_te, valid_te = E6.pivot_raw_vector(
        fold_data["df_test"], input_map, n_val)
    assert x_tr.shape[1] == n_val and x_te.shape[1] == n_val
    assert np.all(np.isfinite(x_tr)) and np.all(np.isfinite(x_te))
    assert np.allclose(x_tr.mean(axis=1), 1.0, rtol=0.0, atol=1e-12)
    assert np.allclose(x_te.mean(axis=1), 1.0, rtol=0.0, atol=1e-12)

    started = time.time()
    y_pred, n_iter, _input_scaler, _target_scaler, _model = \
        E6.train_specialist(x_tr, y_tr, x_te, seed)
    runtime_s = time.time() - started
    selected, metrics = E6.evaluate_selection(
        keys_te, y_pred, y_te, MODEL_NAME, valid_te)
    selected["held_out_beta"] = held_beta
    selected["seed"] = int(seed)
    selected["n_val"] = int(n_val)
    selected["n_iter"] = int(n_iter)
    selected["runtime_s"] = float(runtime_s)

    test_keys = selected[PS.SAMPLE_KEYS]
    matched = baseline.merge(test_keys, on=PS.SAMPLE_KEYS, how="inner")
    assert len(matched) == len(selected)
    selected = selected.reset_index(drop=True)
    matched = matched.reset_index(drop=True)
    selected["default_loss"] = matched["default_loss"].to_numpy()
    selected["default_valid"] = matched["default_valid"].to_numpy()
    selected["l6_loss"] = matched["l6_loss"].to_numpy()
    selected["l6_delta"] = matched["l6_delta"].to_numpy()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    selected.to_csv(path, index=False)
    log(f"  [done] beta={held_beta} n={n_val} seed={seed}: "
        f"J1={metrics['J1']:.6f}, iter={n_iter}, {runtime_s:.1f}s")
    return selected


def build_long(blocks: list[pd.DataFrame]) -> pd.DataFrame:
    frames = []
    keep = ["held_out_beta", "seed", "beta", "gamma_over_eta", "n",
            "repeat_id", "model", "selected_delta", "true_loss", "is_valid"]
    for block in blocks:
        adaptive = block.copy()
        adaptive["model"] = MODEL_NAME
        frames.append(adaptive[keep])

        default = block.copy()
        default["model"] = "Default"
        default["selected_delta"] = CFG.DEFAULT_DELTA
        default["true_loss"] = default["default_loss"]
        default["is_valid"] = default["default_valid"]
        frames.append(default[keep])

        l6 = block.copy()
        l6["model"] = "L6"
        l6["selected_delta"] = l6["l6_delta"]
        l6["true_loss"] = l6["l6_loss"]
        l6["is_valid"] = True
        frames.append(l6[keep])

    result = pd.concat(frames, ignore_index=True)
    counts = result.groupby(["model", "seed"]).size()
    assert (counts == 48000).all(), counts
    return result


def pooled_seed_stats(long_df: pd.DataFrame, model: str) -> dict:
    values = (long_df[long_df["model"] == model]
              .groupby("seed")["true_loss"]
              .apply(lambda x: math.sqrt(float(x.mean())))
              .sort_index())
    return {
        "pooled_J1_mean": float(values.mean()),
        "pooled_J1_std": float(values.std(ddof=0)),
        "per_seed_pooled_J1": {str(int(k)): float(v)
                                for k, v in values.items()},
    }


def run(force_rerun: bool = False) -> dict:
    runtime_start_git = PS.git_meta()
    if force_rerun and os.path.isdir(RESULTS_DIR):
        shutil.rmtree(RESULTS_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    log = lambda message: print(message, flush=True)  # noqa: E731
    started = time.time()
    log("Study01 E8: mean-normalized leave-one-beta-out confirmation")

    df_mc, df_full, raw_map = PS.load_scan()
    PS.verify_design(df_full)
    input_map = mean_normalized_map(raw_map)
    assert set(input_map) == set(raw_map)
    baseline = PS.default_and_l6(df_full)
    folds = B1.get_beta_folds()
    prepared = {fold["fold_name"]: E6.prepare_fold(df_full, fold)
                for fold in folds}

    blocks = []
    for fold in folds:
        fold_data = prepared[fold["fold_name"]]
        for n_val in CFG.N_GRID:
            for seed in SEEDS:
                blocks.append(run_beta_fold(
                    fold, fold_data, n_val, seed, input_map, baseline, log))
    adaptive = pd.concat(blocks, ignore_index=True)
    assert len(adaptive) == 8 * 4 * 3 * 1500

    long_df = build_long(blocks)
    long_df.to_csv(os.path.join(RESULTS_DIR, "long_comparison.csv"), index=False)
    beta_df, by_n_df = B1.summarize(long_df)
    beta_df.to_csv(os.path.join(OUT_DIR, "beta_holdout.csv"), index=False)
    by_n_df.to_csv(os.path.join(OUT_DIR, "by_n.csv"), index=False)

    comparison_rows = []
    for (held_beta, seed), group in long_df.groupby(
            ["held_out_beta", "seed"]):
        for model, model_rows in group.groupby("model"):
            comparison_rows.append({
                "held_out_beta": float(held_beta), "seed": int(seed),
                "model": model, "J1": PS.j1_from_loss(model_rows["true_loss"]),
                "failure_rate": PS.failure_rate_from_valid(model_rows["is_valid"]),
                "n_samples": int(len(model_rows)),
            })
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(os.path.join(OUT_DIR, "model_comparison.csv"), index=False)

    split_rows = [{
        "fold": fold["fold_name"],
        "held_out_beta": float(fold["held_out_beta"]),
        "n_train_combos": len(fold["train_combos"]),
        "n_test_combos": len(fold["test_combos"]),
        "train_betas": json.dumps(sorted({x[0] for x in fold["train_combos"]})),
        "test_betas": json.dumps(sorted({x[0] for x in fold["test_combos"]})),
    } for fold in folds]
    pd.DataFrame(split_rows).to_csv(
        os.path.join(OUT_DIR, "split_report.csv"), index=False)

    adaptive_stats = pooled_seed_stats(long_df, MODEL_NAME)
    default_j1 = PS.j1_from_loss(
        long_df[long_df["model"] == "Default"]["true_loss"])
    l6_j1 = PS.j1_from_loss(long_df[long_df["model"] == "L6"]["true_loss"])
    relative = (default_j1 - adaptive_stats["pooled_J1_mean"]) / default_j1
    per_n = {}
    for (model, n_val), rows in by_n_df.groupby(["model", "n"]):
        per_n.setdefault(model, {})[str(int(n_val))] = {
            "J1_mean": float(rows["J1"].mean()),
            "J1_std": float(rows["J1"].std(ddof=0)),
            "failure_rate": float(rows["failure_rate"].mean()),
        }

    summary = {
        "experiment": "Mean-normalized leave-one-beta-out confirmation",
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "representation": "ascending-sorted X / mean(X)",
        "split": "leave one complete beta level out; 8 folds",
        "methods": [MODEL_NAME, "Default", "L6"],
        "seeds": SEEDS,
        "pooled": {
            "mean_normalized_3seed": adaptive_stats,
            "Default_J1": default_j1,
            "L6_J1": l6_j1,
            "relative_improvement_vs_Default": relative,
        },
        "per_n": per_n,
        "failure_rate": float(1.0 - adaptive["is_valid"].mean()),
        "boundary": ("discrete 8-point beta grid only; not continuous "
                     "extrapolation; separate model for each trained n"),
        "runtime_start_git": runtime_start_git,
    }
    PS.atomic_write_json(summary, os.path.join(OUT_DIR, "summary.json"))

    manifest = {
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_entry": "code/run_b1_mean_normalized_unseen_beta.py",
        "code_sha256": PS.code_sha256(_THIS, PS, CFG, E6, E7, B1),
        "data_source": ("E5_normalized_raw/shared_data reused; 48,000 samples "
                        "x 26 deltas; no MDM rerun"),
        "training_contract": {
            "representation": "ascending-sorted X / mean(X)",
            "input_scaler": "per-position StandardScaler fit on train fold only",
            "target_scaler": "26-d StandardScaler fit on train fold only",
            "hidden_layers": list(CFG.MLP_HIDDEN_LAYERS),
            "seeds": SEEDS,
            "failure_penalty": "p99 valid loss from full training fold",
        },
        "output_files": ["summary.json", "beta_holdout.csv", "by_n.csv",
                         "model_comparison.csv", "split_report.csv",
                         "manifest.json", "SHA256SUMS",
                         "SHA256SUMS.local_not_in_git",
                         "results/*.csv (gitignored)"],
        "elapsed_s": float(time.time() - started),
        "runtime_start_git": runtime_start_git,
    }
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))
    with open(os.path.join(OUT_DIR, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("results/\nrun_detached*\n")
    for name in ("summary.json", "manifest.json", "beta_holdout.csv", "by_n.csv",
                 "model_comparison.csv", "split_report.csv"):
        PS.lf_normalize(os.path.join(OUT_DIR, name))
    tracked, local = PS.write_sha256sums(OUT_DIR)
    log(f"Done: J1={adaptive_stats['pooled_J1_mean']:.6f}; "
        f"improvement={relative * 100:.2f}%; SHA entries={tracked}+{local}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-rerun", action="store_true")
    args = parser.parse_args()
    run(force_rerun=args.force_rerun)
