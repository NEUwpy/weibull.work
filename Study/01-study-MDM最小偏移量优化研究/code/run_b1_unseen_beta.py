"""
Study/01 B1 — unseen-beta minimal held-out validation (Dimensional-RAW).

Contract (02-实验协议 §5.1):
  - Reuse the existing 160-combo risk data (no MDM rerun, no data regeneration).
  - Leave out one complete beta level at a time (8 folds).  Train fold and test
    fold are strictly disjoint on beta; within each beta fold every n still uses
    an independent per-n MLP (same representation/contract as E6: sorted raw
    sample, per-position StandardScaler fit on the train fold only, MLP
    256-128-64, 26-dim loss-curve target, 3 seeds).
  - Compare Dimensional-RAW-MLP / Default (delta=0.1) / L6 hindsight on the
    SAME held-out test samples.
  - Report per held-out beta, pooled, per-n, three seeds and failure rates.

Stop/boundary note: the result is only a discrete-grid unseen-beta check for
the current 8-point beta grid; it is not continuous-parameter extrapolation.

Output: artifacts/formal/E6_dimensional_raw/unseen_beta/
  summary.json, beta_holdout.csv, by_n.csv, model_comparison.csv,
  split_report.csv, manifest.json, SHA256SUMS
  results/ (gitignored per-block + per-sample long table)

Run:  python code/run_b1_unseen_beta.py [--force-rerun]
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
for p in (STUDY_CODE_DIR, os.path.join(os.path.dirname(os.path.dirname(
        STUDY_CODE_DIR)), "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import paper_support as PS
import run_E6b_dimensional_raw_specialist as E6

_THIS = sys.modules[__name__]

CONTRACT_VERSION = "B1_unseen_beta_v1"
SEEDS = CFG.STABILITY_SEEDS
OUT_DIR = PS.UNSEEN_BETA_DIR
RESULTS_DIR = os.path.join(OUT_DIR, "results")


# ============================================================
# Beta-level split
# ============================================================

def get_beta_folds():
    """Leave-one-beta-out: each fold holds out one complete beta level.

    test_combos = all (beta=b, gamma/eta, n) combos for the held-out beta.
    train_combos = all other combos.
    """
    folds = []
    for b in CFG.BETA_GRID:
        train = [(bb, g, n)
                 for bb in CFG.BETA_GRID for g in CFG.GAMMA_OVER_ETA_GRID
                 for n in CFG.N_GRID if bb != b]
        test = [(b, g, n)
                for g in CFG.GAMMA_OVER_ETA_GRID for n in CFG.N_GRID]
        folds.append({"fold_name": f"beta_holdout_{b}",
                      "held_out_beta": float(b),
                      "train_combos": train, "test_combos": test})
    return folds


def block_path(held_beta, n_val, seed):
    return os.path.join(RESULTS_DIR,
                        f"block_beta{held_beta}_n{n_val}_seed{seed}.csv")


# ============================================================
# Per-block run (train per-n MLP on other betas, evaluate on held-out beta)
# ============================================================

def run_beta_fold(fold, fp, n_val, seed, raw_map, baseline, log):
    held_beta = fold["held_out_beta"]
    bpath = block_path(held_beta, n_val, seed)
    if os.path.exists(bpath):
        log(f"  [skip] beta={held_beta} n={n_val} seed={seed}")
        return pd.read_csv(bpath)
    keys_tr, X_tr, Y_tr, _ = E6.pivot_raw_vector(fp["df_train"], raw_map, n_val)
    keys_te, X_te, Y_te, valid_te = E6.pivot_raw_vector(fp["df_test"], raw_map, n_val)
    assert X_te.shape[0] == len(keys_te)
    assert not np.any(np.isnan(X_tr)), "NaN in raw input (train)"

    t0 = time.time()
    Y_pred, n_iter, _in, _tg, _ = E6.train_specialist(X_tr, Y_tr, X_te, seed)
    runtime = time.time() - t0

    df_sel, metrics = E6.evaluate_selection(
        keys_te, Y_pred, Y_te, f"Dimensional-RAW", valid_te)
    df_sel["held_out_beta"] = held_beta
    df_sel["seed"] = seed
    df_sel["n_val"] = n_val
    df_sel["n_iter"] = n_iter
    df_sel["runtime_s"] = runtime

    # same-test Default / L6 baselines for these samples
    test_keys = df_sel[PS.SAMPLE_KEYS]
    base = baseline.merge(test_keys, on=PS.SAMPLE_KEYS, how="inner")
    assert len(base) == len(df_sel), \
        f"baseline join {len(base)} != {len(df_sel)} for beta={held_beta} n={n_val}"
    df_sel = df_sel.reset_index(drop=True)
    base = base.reset_index(drop=True)
    df_sel["default_loss"] = base["default_loss"].values
    df_sel["default_valid"] = base["default_valid"].values
    df_sel["l6_loss"] = base["l6_loss"].values
    df_sel["l6_delta"] = base["l6_delta"].values

    os.makedirs(RESULTS_DIR, exist_ok=True)
    df_sel.to_csv(bpath, index=False)
    log(f"  [done] beta={held_beta} n={n_val} seed={seed}: "
        f"J1={metrics['J1']:.6f} n_iter={n_iter} t={runtime:.1f}s "
        f"(train={len(keys_tr)}, test={len(keys_te)})")
    return df_sel


def build_long_comparison(df_sel_blocks):
    """Stack per-block selection into a long same-test comparison table.

    Columns: held_out_beta, seed, beta, gamma_over_eta, n, repeat_id,
             model (Dimensional-RAW / Default / L6), selected_delta,
             true_loss, is_valid.
    """
    frames = []
    for b in df_sel_blocks:
        d = b.copy()
        d["model"] = "Dimensional-RAW"
        d["true_loss"] = d["true_loss"]
        d["is_valid"] = d["is_valid"]
        d["selected_delta"] = d["selected_delta"]
        keep = ["held_out_beta", "seed", "beta", "gamma_over_eta", "n",
                "repeat_id", "model", "selected_delta", "true_loss", "is_valid"]
        frames.append(d[keep])

        # Default
        dd = d.copy()
        dd["model"] = "Default"
        dd["selected_delta"] = CFG.DEFAULT_DELTA
        dd["true_loss"] = dd["default_loss"]
        dd["is_valid"] = dd["default_valid"]
        frames.append(dd[keep])

        # L6
        dl = d.copy()
        dl["model"] = "L6"
        dl["selected_delta"] = dl["l6_delta"]
        dl["true_loss"] = dl["l6_loss"]
        dl["is_valid"] = True
        frames.append(dl[keep])

    out = pd.concat(frames, ignore_index=True)
    # key contract: exactly 48,000 samples per (model, seed)
    counts = out.groupby(["model", "seed"])["n"].count()
    assert (counts == 48000).all(), f"model/seed sample counts wrong: {counts}"
    return out


# ============================================================
# Summaries
# ============================================================

def summarize(long_df):
    """Per-(model,seed) summary: pooled J1, per-n, failure rate.

    Returns a per-(held_out_beta, model, seed) row and a per-(n, model, seed) row.
    """
    beta_rows = []
    n_rows = []
    for (beta, model, seed), g in long_df.groupby(
            ["held_out_beta", "model", "seed"]):
        r = {"held_out_beta": float(beta), "model": model, "seed": int(seed),
             "J1": PS.j1_from_loss(g["true_loss"]),
             "failure_rate": PS.failure_rate_from_valid(g["is_valid"]),
             "n_samples": int(len(g))}
        for nv, ng in g.groupby("n"):
            r[f"J1_n{int(nv)}"] = PS.j1_from_loss(ng["true_loss"])
            r[f"failure_n{int(nv)}"] = PS.failure_rate_from_valid(ng["is_valid"])
        beta_rows.append(r)
    for (model, seed, nv), g in long_df.groupby(["model", "seed", "n"]):
        n_rows.append({"model": model, "seed": int(seed), "n": int(nv),
                       "J1": PS.j1_from_loss(g["true_loss"]),
                       "failure_rate": PS.failure_rate_from_valid(g["is_valid"]),
                       "n_samples": int(len(g))})
    return pd.DataFrame(beta_rows), pd.DataFrame(n_rows)


def three_seed_stats(long_df, model):
    """Across the 8 held-out betas, the three-seed pooled-J1 distribution.

    Frozen J1 = sqrt(mean(sample loss)): pool the ROW-LEVEL losses once per
    seed (across all held-out betas), then summarize the three-seed
    distribution.  Averaging per-beta J1 would violate the frozen definition.
    """
    sub = long_df[long_df["model"] == model]
    pooled = sub.groupby("seed")["true_loss"].apply(
        lambda losses: math.sqrt(float(losses.mean()))).sort_index()
    return {
        "pooled_J1_mean": float(pooled.mean()),
        "pooled_J1_std": float(pooled.std(ddof=0)),
        "per_seed_pooled_J1": {int(s): float(v) for s, v in pooled.items()},
    }


def main(force_rerun=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    if force_rerun:
        import shutil
        if os.path.isdir(RESULTS_DIR):
            shutil.rmtree(RESULTS_DIR)

    log = lambda msg: print(msg, flush=True)   # noqa: E731
    t_start = time.time()
    log("=" * 72)
    log("Study/01 B1 — unseen-beta held-out validation (Dimensional-RAW)")
    log(f"Output: {OUT_DIR}")
    log("=" * 72)

    df_mc, df_full, raw_map = PS.load_scan()
    PS.verify_design(df_full)
    baseline = PS.default_and_l6(df_full)
    folds = get_beta_folds()

    log("\n[1/4] Beta-level folds...")
    for f in folds:
        log(f"  {f['fold_name']}: train={len(f['train_combos'])} "
            f"test={len(f['test_combos'])} combos")

    log("\n[2/4] Training per-n specialists (8 beta x 4n x 3 seed)...")
    fold_prep = {f["fold_name"]: E6.prepare_fold(df_full, f) for f in folds}
    blocks = []
    for fold in folds:
        fp = fold_prep[fold["fold_name"]]
        for n_val in CFG.N_GRID:
            for seed in SEEDS:
                blocks.append(run_beta_fold(fold, fp, n_val, seed,
                                            raw_map, baseline, log))
    df_sel = pd.concat(blocks, ignore_index=True)
    assert len(df_sel) == 8 * 4 * 3 * 1500
    log(f"  per-sample DIM-RAW rows: {len(df_sel)}")

    log("\n[3/4] Same-test long comparison + summaries...")
    long_df = build_long_comparison(blocks)
    long_df.to_csv(os.path.join(RESULTS_DIR, "long_comparison.csv"), index=False)
    beta_df, n_df = summarize(long_df)
    beta_df.to_csv(os.path.join(OUT_DIR, "beta_holdout.csv"), index=False)
    n_df.to_csv(os.path.join(OUT_DIR, "by_n.csv"), index=False)

    # pooled / per-beta comparison rows per seed (model_comparison.csv)
    comp_rows = []
    for (beta, seed), g in long_df.groupby(["held_out_beta", "seed"]):
        for model, mg in g.groupby("model"):
            comp_rows.append({"held_out_beta": float(beta), "seed": int(seed),
                              "model": model, "J1": PS.j1_from_loss(mg["true_loss"]),
                              "failure_rate": PS.failure_rate_from_valid(
                                  mg["is_valid"]),
                              "n_samples": int(len(mg))})
    comp = pd.DataFrame(comp_rows)
    comp.to_csv(os.path.join(OUT_DIR, "model_comparison.csv"), index=False)

    dim_3seed = three_seed_stats(long_df, "Dimensional-RAW")
    # Pooled over all row-level losses (frozen definition), not mean of
    # per-beta J1.  Default/L6 rows are seed-invariant; the pooled value is
    # unaffected by the per-seed replication.
    default_j1 = PS.j1_from_loss(
        long_df[long_df["model"] == "Default"]["true_loss"])
    l6_j1 = PS.j1_from_loss(
        long_df[long_df["model"] == "L6"]["true_loss"])
    rel_improve = (default_j1 - dim_3seed["pooled_J1_mean"]) / default_j1

    log(f"\n  Dimensional-RAW 3-seed pooled J1 = {dim_3seed['pooled_J1_mean']:.6f} "
        f"(std={dim_3seed['pooled_J1_std']:.6f})")
    log(f"  Default J1 = {default_j1:.6f}  L6 J1 = {l6_j1:.6f}  "
        f"rel-improve vs Default = {rel_improve*100:.2f}%")

    log("\n[4/4] Split report + provenance...")
    split_rows = []
    for f in folds:
        split_rows.append({"fold": f["fold_name"],
                           "held_out_beta": f["held_out_beta"],
                           "n_train_combos": len(f["train_combos"]),
                           "n_test_combos": len(f["test_combos"]),
                           "test_betas": sorted({c[0] for c in f["test_combos"]}),
                           "train_betas": sorted({c[0] for c in f["train_combos"]})})
    pd.DataFrame(split_rows).to_csv(
        os.path.join(OUT_DIR, "split_report.csv"), index=False)

    per_beta_summary = {}
    for (beta, model), g in comp.groupby(["held_out_beta", "model"]):
        per_beta_summary.setdefault(float(beta), {})[model] = {
            "J1": float(g["J1"].mean()),
            "seed_J1": {int(s): float(v) for s, v in
                        g.groupby("seed")["J1"].mean().items()},
            "failure_rate": float(g["failure_rate"].mean()),
        }

    per_n_summary = {}
    for (model, nv), g in n_df.groupby(["model", "n"]):
        per_n_summary.setdefault(model, {})[int(nv)] = {
            "J1_mean": float(g["J1"].mean()),
            "J1_std": float(g["J1"].std(ddof=0)),
            "failure_rate": float(g["failure_rate"].mean()),
        }

    summary = {
        "experiment": "B1 unseen-beta held-out validation (Dimensional-RAW)",
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split": ("leave-one-beta-out (8 folds); train/test strictly disjoint "
                  "on beta; per-n independent MLP; same test samples for "
                  "Dimensional-RAW / Default / L6"),
        "methods": ["Dimensional-RAW-MLP", "Default", "L6"],
        "seeds": SEEDS,
        "n_folds": len(folds),
        "per_beta": per_beta_summary,
        "pooled": {
            "Dimensional_RAW_3seed": dim_3seed,
            "Default_J1": default_j1,
            "L6_J1": l6_j1,
            "relative_improvement_vs_Default": rel_improve,
        },
        "per_n": per_n_summary,
        "boundary": ("discrete 8-point beta grid only; not continuous-parameter "
                     "extrapolation; per-n models defined only for "
                     "n in {7,10,15,20}"),
        **PS.git_meta(),
    }
    PS.atomic_write_json(summary, os.path.join(OUT_DIR, "summary.json"))

    n_tracked, n_local = PS.write_sha256sums(OUT_DIR)
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_entry": "code/run_b1_unseen_beta.py",
        "code_sha256": PS.code_sha256(_THIS, PS, CFG, E6),
        "data_source": "artifacts/formal/E5_normalized_raw/shared_data "
                       "(reused; no MDM rerun, no data regeneration)",
        "training_contract": {
            "representation": "sorted raw sample X_n (dimensional)",
            "scaler": "per-position StandardScaler fit on train fold only",
            "mlp": {"hidden_layer_sizes": list(CFG.MLP_HIDDEN_LAYERS),
                    "max_iter": CFG.MLP_MAX_ITER, "seeds": SEEDS},
            "failure_penalty": "p99 of valid train-fold loss",
        },
        "design": CFG.design_summary(),
        "provenance_note": ("code_sha256 binds the committed content of the "
                            "entry script and material dependencies; "
                            "git_commit records the runtime HEAD at generation "
                            "(see branch commit chain for the implementation "
                            "commits). SHA256SUMS covers git-tracked files "
                            "only; SHA256SUMS.local_not_in_git lists "
                            "gitignored/local raw files."),
        "sha256_tracked_entries": n_tracked,
        "sha256_local_not_in_git_entries": n_local,
        "output_files": ["summary.json", "beta_holdout.csv", "by_n.csv",
                         "model_comparison.csv", "split_report.csv",
                         "manifest.json", "SHA256SUMS",
                         "SHA256SUMS.local_not_in_git",
                         "results/*.csv (gitignored)"],
        "elapsed_s": float(time.time() - t_start),
        **PS.git_meta(),
    }
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))

    gitignore = "results/\nrun_b1_detached*\n"
    with open(os.path.join(OUT_DIR, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(gitignore)

    for p in (os.path.join(OUT_DIR, "summary.json"),
              os.path.join(OUT_DIR, "manifest.json"),
              os.path.join(OUT_DIR, "beta_holdout.csv"),
              os.path.join(OUT_DIR, "by_n.csv"),
              os.path.join(OUT_DIR, "model_comparison.csv"),
              os.path.join(OUT_DIR, "split_report.csv")):
        PS.lf_normalize(p)
    log(f"\nDone in {time.time()-t_start:.1f}s. Outputs in {OUT_DIR} "
        f"(SHA256SUMS tracked: {n_tracked}, local_not_in_git: {n_local})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-rerun", action="store_true")
    args = ap.parse_args()
    main(force_rerun=args.force_rerun)
