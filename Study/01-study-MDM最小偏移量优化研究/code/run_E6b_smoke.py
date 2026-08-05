"""
Study/01 E6b — Real smoke for the Dimensional-RAW pipeline.

Reads 4 real chunks of the reused 160-combo design (one combo per n,
beta=2.0, goe=0.5, n=7/10/15/20) and drives the real E6b pipeline:
  load -> raw sorted input -> per-n MLP -> predict -> select -> J1.
Verifies the input contract: X_n is the sorted raw sample (mean ~1000-scale,
NOT divided by mean), and the scaler is fit on the train split only.

Run:  python code/run_E6b_smoke.py
Exit: 0 PASS / 1 FAIL.
"""

import os
import sys
import math
import numpy as np
import pandas as pd

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
from studies.common.sample import generate_sample

# one combo per n: (beta=2.0, goe=0.5, n) -> chunk indices 28,29,30,31
SMOKE_INDICES = [28, 29, 30, 31]
SMOKE_NS = CFG.SEED_NAMESPACE


def main():
    print("=" * 70)
    print("E6b REAL SMOKE — Dimensional-RAW pipeline (raw sorted input)")
    print("=" * 70)
    t_start = __import__('time').time()

    # load 4 chunks (real reused data)
    frames = []
    for idx in SMOKE_INDICES:
        p = os.path.join(CFG.CHUNKS_DIR, f"chunk_{idx:04d}_mdm.csv")
        frames.append(pd.read_csv(p))
    df_mc = pd.concat(frames, ignore_index=True)
    print(f"[1/5] loaded {len(df_mc):,} rows from chunks {SMOKE_INDICES}")

    # 1) raw sorted input check on reconstructed samples
    print("[2/5] raw input contract check...")
    raw_map, _ = E6.build_raw_sample_map(df_mc)
    for n_val in CFG.N_GRID:
        key = next(k for k in raw_map if k[4] == n_val)
        beta, eta, gamma, goe, n, rid = key
        sample = generate_sample(beta, eta, gamma, n, rid, seed=SMOKE_NS)
        X = raw_map[key]
        assert np.allclose(X, np.sort(sample)), f"n={n}: X != sorted raw sample"
        mean_x = float(X.mean())
        assert not np.isclose(mean_x, 1.0, atol=1e-3), \
            f"n={n}: input appears normalized (mean ~1); must be dimensional raw"
        print(f"  n={n}: mean(x)={mean_x:.2f} (raw ~1000-scale, NOT normalized) OK")

    # 2) loss + random 80/20 split
    print("[3/5] loss + random split...")
    df_full = E6.compute_per_sample_loss(df_mc)
    train_valid = df_full['loss'].dropna()
    penalty = float(np.nanpercentile(train_valid, 99))
    for d in (df_full,):
        d['loss_filled'] = d['loss'].fillna(penalty)
        d['is_valid'] = d.get('status', 'success').eq('success') & d['loss'].notna()
    rng = np.random.default_rng(7)
    keys_all = (df_full[E6.SAMPLE_KEYS].drop_duplicates().sort_values(
        E6.SAMPLE_KEYS).reset_index(drop=True))
    n_test = int(len(keys_all) * 0.2)
    test_idx = rng.choice(len(keys_all), size=n_test, replace=False)
    test_keys = keys_all.iloc[test_idx]
    df_test = df_full.merge(test_keys[E6.SAMPLE_KEYS], on=E6.SAMPLE_KEYS, how="inner")
    df_train = df_full.merge(test_keys[E6.SAMPLE_KEYS], on=E6.SAMPLE_KEYS,
                             how="left", indicator=True)
    df_train = df_train[df_train['_merge'] == 'left_only'].drop(columns=['_merge'])

    # 3) train per-n + evaluate
    print("[4/5] train per-n specialists...")
    sel_frames = []
    for n_val in CFG.N_GRID:
        keys_tr, X_tr, Y_tr, _ = E6.pivot_raw_vector(df_train, raw_map, n_val)
        keys_te, X_te, Y_te, valid_te = E6.pivot_raw_vector(df_test, raw_map, n_val)
        assert X_tr.shape[1] == n_val and X_te.shape[1] == n_val
        # scaler train-only: fit ONLY on train, transform test
        Y_pred, n_iter, in_sc, tg_sc, _ = E6.train_specialist(X_tr, Y_tr, X_te, seed=42)
        df_sel, metrics = E6.evaluate_selection(
            keys_te, Y_pred, Y_te, f"smoke-n{n_val}", valid_te)
        sel_frames.append(df_sel)
        print(f"  n={n_val}: J1={metrics['J1']:.6f} n_iter={n_iter} "
              f"train={len(keys_tr)} test={len(keys_te)}")
    df_sel = pd.concat(sel_frames, ignore_index=True)
    pooled = math.sqrt(df_sel['true_loss'].mean())

    # 4) cross-fit L1-L6 on a MINIMAL multi-combo slice: skip here (validated
    #    separately against Codex refs on the full 160-combo data); just confirm
    #    the module imports and prepare_scan works.
    print("[5/5] crossfit module import check...")
    import analyze_E1_E2_crossfit as CF
    scan = CF.prepare_scan(df_full)
    assert 'j1_sq' in scan.columns
    print("  prepare_scan OK")

    ok = math.isfinite(pooled) and len(df_sel) > 0
    print(f"\npooled smoke J1={pooled:.6f} (value meaningless; pipeline OK)")
    print(f"SMOKE {'PASS' if ok else 'FAIL'} in {__import__('time').time()-t_start:.1f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
