"""
Study/01 E5b — Real smoke test for the normalized-RAW pipeline.

Generates a tiny NEW-design dataset with the REAL MDM (covers n=7,10,15,20),
then drives the real E5b pipeline functions end-to-end:
  chunks -> integrity -> normalize -> fold/split -> per-n MLP -> predict ->
  select -> J1 + references -> final full-dev models -> scale-invariance check.

The smoke dataset is cached under artifacts/pilot/E5_normalized_raw_smoke/data/
so a re-run skips regeneration.

Run:  python code/run_E5b_smoke.py
Exit: 0 on PASS, 1 on FAIL.
"""

import os
import sys
import csv
import json
import time
import math
import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import nrmc_config as CFG
import run_E5b_normalized_raw_specialist as E5B
from studies.common.sample import generate_sample
from methods.mdm import MDM

SAMPLE_KEYS = E5B.SAMPLE_KEYS

SMOKE_ROOT = os.path.join(STUDY_ROOT, "artifacts", "pilot", "E5_normalized_raw_smoke")
DATA_DIR = os.path.join(SMOKE_ROOT, "data")
OUT_DIR = os.path.join(SMOKE_ROOT, "out")

# Tiny smoke design: every n in {7,10,15,20}, real MDM, small repeats.
SMOKE_BETA = [2.0, 3.0]
SMOKE_GOE = [0.5, 1.0]
SMOKE_N = [7, 10, 15, 20]
SMOKE_REPS = 3
SMOKE_NS = "study01_nrmc_smoke_v1"

FIELDS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id", "delta",
          "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
          "time_ms", "status"]


def smoke_design():
    return {
        "name": "smoke",
        "label": "Normalized-RAW-MLP (smoke)",
        "beta_grid": list(SMOKE_BETA),
        "eta_grid": [CFG.ETA],
        "gamma_over_eta_grid": list(SMOKE_GOE),
        "n_grid": list(SMOKE_N),
        "repeats": SMOKE_REPS,
        "seed_namespace": SMOKE_NS,
        "chunks_dir": os.path.join(DATA_DIR, "chunks"),
        "mc_manifest": os.path.join(DATA_DIR, "manifest.json"),
        "output_dir": OUT_DIR,
    }


def build_smoke_chunks(force=False):
    """Generate (or reuse cached) tiny MDM chunks for the smoke design."""
    chunks_dir = os.path.join(DATA_DIR, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    combos = [(b, g, n) for b in SMOKE_BETA for g in SMOKE_GOE for n in SMOKE_N]
    expected = os.path.join(chunks_dir, f"chunk_{len(combos)-1:04d}_mdm.csv")
    if os.path.isfile(expected) and not force:
        return combos

    t0 = time.time()
    for idx, (beta, goe, n) in enumerate(combos):
        gamma = goe * CFG.ETA
        path = os.path.join(chunks_dir, f"chunk_{idx:04d}_mdm.csv")
        if os.path.isfile(path) and not force:
            continue
        rows = []
        for rid in range(SMOKE_REPS):
            sample = generate_sample(beta, CFG.ETA, gamma, n, rid, seed=SMOKE_NS)
            mdm = MDM(sample)
            for delta in CFG.DELTA_GRID:
                row = {"beta": beta, "eta": CFG.ETA, "gamma": gamma,
                       "gamma_over_eta": goe, "n": n, "repeat_id": rid,
                       "delta": delta, "beta_hat": None, "eta_hat": None,
                       "gamma_hat": None, "r_squared": None,
                       "converged": False, "time_ms": 0.0, "status": "failure"}
                try:
                    bh, eh, gh, r2, conv = mdm.run(offset=delta)
                    row.update({"beta_hat": bh, "eta_hat": eh, "gamma_hat": gh,
                                "r_squared": r2, "converged": bool(conv),
                                "status": "success" if conv and bh > 0 and eh > 0
                                else "failure"})
                except Exception as e:
                    row["status"] = f"error:{type(e).__name__}"
                rows.append(row)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
    # manifest
    manifest = {
        "run_id": "E5b_smoke_v1",
        "design": {"beta": SMOKE_BETA, "goe": SMOKE_GOE, "n": SMOKE_N,
                   "repeats": SMOKE_REPS, "seed_namespace": SMOKE_NS,
                   "eta": CFG.ETA},
        "n_mdm_fits": len(combos) * SMOKE_REPS * len(CFG.DELTA_GRID),
        "elapsed_seconds": time.time() - t0,
    }
    with open(os.path.join(DATA_DIR, "manifest.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return combos


def main():
    print("=" * 70)
    print("E5b REAL SMOKE — normalized-RAW pipeline (tiny new-design data)")
    print("=" * 70)
    t_start = time.time()

    design = smoke_design()
    combos = build_smoke_chunks()
    print(f"[1/6] smoke chunks: {len(combos)} combos, "
          f"{len(combos) * SMOKE_REPS * len(CFG.DELTA_GRID)} MDM fits")

    print("[2/6] load + integrity + normalization...")
    df_mc = E5B.load_mc_scan(design["chunks_dir"])
    with open(design["mc_manifest"], encoding="utf-8") as f:
        mc_manifest = json.load(f)
    integrity = E5B.verify_data_integrity(df_mc, design, mc_manifest)
    print(f"  integrity: {integrity}")
    norm_map, _ = E5B.build_normalized_sample_map(df_mc, design)
    df_full = E5B.compute_per_sample_loss(df_mc)

    print("[3/6] random 80/20 split (guarantees every n in train+test)...")
    # every n has 2x2x3=12 samples; random split keeps every n in both sets
    rng = np.random.default_rng(7)
    keys_all = (df_full[SAMPLE_KEYS].drop_duplicates().sort_values(
        SAMPLE_KEYS).reset_index(drop=True))
    n_test = int(len(keys_all) * 0.2)
    test_idx = rng.choice(len(keys_all), size=n_test, replace=False)
    test_keys = keys_all.iloc[test_idx]
    merge_keys = SAMPLE_KEYS
    df_test = df_full.merge(test_keys[merge_keys], on=merge_keys, how="inner")
    df_train = df_full.merge(test_keys[merge_keys], on=merge_keys, how="left",
                             indicator=True)
    df_train = df_train[df_train["_merge"] == "left_only"].drop(columns=["_merge"])
    for n_val in SMOKE_N:
        assert (df_train["n"] == n_val).any(), f"n={n_val} missing in train"
        assert (df_test["n"] == n_val).any(), f"n={n_val} missing in test"
    # apply the same failure-handling contract as prepare_fold
    train_valid_loss = df_train["loss"].dropna()
    failure_penalty = float(np.nanpercentile(train_valid_loss, 99))
    for d in (df_train, df_test):
        d["loss_filled"] = d["loss"].fillna(failure_penalty)
        d["is_valid"] = d.get("status", "success").eq("success") & d["loss"].notna()
    print(f"  train samples: {len(df_train)}, test samples: {len(df_test)} "
          f"failure_penalty={failure_penalty:.4f}")

    print("[4/6] train per-n specialists + predict + select...")
    sel_frames = []
    for n_val in SMOKE_N:
        keys_tr, X_tr, Y_tr, _ = E5B.pivot_norm_vector(df_train, norm_map, n_val)
        keys_te, X_te, Y_te, valid_te = E5B.pivot_norm_vector(df_test, norm_map, n_val)
        assert X_tr.shape[1] == n_val and X_te.shape[1] == n_val
        assert X_te.shape[0] == len(keys_te)
        Y_pred, n_iter, in_sc, tg_sc, _ = E5B.train_specialist(
            X_tr, Y_tr, X_te, seed=42)
        df_sel, metrics = E5B.evaluate_selection(
            keys_te, Y_pred, Y_te, f"smoke-n{n_val}", valid_te)
        sel_frames.append(df_sel)
        print(f"  n={n_val}: J1={metrics['J1']:.6f} n_iter={n_iter} "
              f"train={len(keys_tr)} test={len(keys_te)}")
    df_sel = pd.concat(sel_frames, ignore_index=True)
    pooled_j1 = math.sqrt(df_sel["true_loss"].mean())
    print(f"  pooled smoke J1={pooled_j1:.6f} (value meaningless; pipeline OK)")

    print("[5/6] references on the same test samples...")
    df_test_loss = E5B.compute_per_sample_loss(df_test)
    refs = E5B.compute_reference_deltas(df_test_loss, design)
    print(f"  refs: default={refs['default_delta']} l1={refs['l1_delta']}")

    print("[6/6] final full-dev models + scale-invariance check...")
    final_models = {}
    for n_val in SMOKE_N:
        meta, model, in_sc, tg_sc, Xf, Yf = E5B.train_final_model(
            n_val, df_full, norm_map, design, lambda m: print("  " + m))
        final_models[n_val] = (meta, model, in_sc, tg_sc, Xf, Yf)
    scale_out = E5B.run_scale_invariance_check(design, norm_map, final_models,
                                               lambda m: print("  " + m))

    ok = (scale_out["all_ok"] and len(design["n_grid"]) == 4
          and 15 in design["n_grid"] and math.isfinite(pooled_j1))
    print(f"\nScale invariance all_ok: {scale_out['all_ok']}")
    print(f"SMOKE {'PASS' if ok else 'FAIL'} in {time.time()-t_start:.1f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
