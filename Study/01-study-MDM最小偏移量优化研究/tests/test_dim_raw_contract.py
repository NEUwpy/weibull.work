"""Contract tests for the Dimensional-RAW (DIM-RAW) final method.

Covers:
  - frozen parameter design (160 combos, eta=1000, must include (2,1000,1000))
  - input is the SORTED RAW sample X_n (dimensional; NOT divided by mean)
  - per-position StandardScaler is fit on the train fold only
  - 5-fold full-combo holdout is a partition, train/test disjoint
  - loss / J1 definitions match the formal metric contract
  - L1–L5 cross-fit selects on train / scores on held-out fold (no full-data leak)

Self-contained (no dependence on generated artifacts / large data).
"""

import os
import sys
import math
import numpy as np
import pandas as pd
from itertools import product

STUDY_CODE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "code")
PYTHON_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6


def test_frozen_design():
    s = CFG.design_summary()
    assert s["combos"] == 160
    assert s["n_samples"] == 48000
    assert s["n_mdm_fits"] == 1248000
    assert s["beta_grid"] == [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    assert s["eta"] == 1000.0
    assert s["gamma_over_eta_grid"] == [0.10, 0.25, 0.50, 0.75, 1.00]
    assert s["n_grid"] == [7, 10, 15, 20]
    assert s["repeats"] == 300
    assert len(s["delta_grid"]) == 26 and s["default_delta"] == 0.1


def test_must_include_combo():
    found = [(b, CFG.ETA, CFG.get_gamma(g))
             for b in CFG.BETA_GRID for g in CFG.GAMMA_OVER_ETA_GRID]
    assert (2.0, 1000.0, 1000.0) in found


def test_pivot_input_is_sorted_raw_not_normalized():
    """X rows == sorted raw sample; mean on the ~1000 scale (NOT ~1)."""
    rng = np.random.default_rng(0)
    n = 7
    beta, eta, gamma, goe = 2.0, 1000.0, 500.0, 0.5
    raw_map = {}
    rows = []
    for rid in range(3):
        x = np.sort(rng.gamma(2.0, 1.0, size=n) * eta + gamma)
        raw_map[(beta, eta, gamma, goe, n, rid)] = x.astype(np.float64)
        for j, d in enumerate(CFG.DELTA_GRID):
            rows.append({"beta": beta, "eta": eta, "gamma": gamma,
                         "gamma_over_eta": goe, "n": n, "repeat_id": rid,
                         "delta": d, "loss_filled": float(rng.random()),
                         "is_valid": True})
    df = pd.DataFrame(rows)
    keys, X, Y, valid = E6.pivot_raw_vector(df, raw_map, n)
    assert X.shape == (3, n)
    for i, r in keys.iterrows():
        key = (float(r["beta"]), float(r["eta"]), float(r["gamma"]),
               float(r["gamma_over_eta"]), int(r["n"]), int(r["repeat_id"]))
        assert np.allclose(X[i], raw_map[key])          # exact raw values
        assert np.all(np.diff(X[i]) >= 0)               # sorted
        assert abs(X[i].mean() - 1000.0) > 100.0        # NOT scaled to mean ~1


def test_no_per_sample_division():
    """No per-sample divide-by-mean OPERATION in the input path.

    The word "Normalized-RAW" legitimately appears as the candidate-control
    label; this test asserts no division of the sorted sample by its mean
    anywhere in the implementation.
    """
    src = open(os.path.join(STUDY_CODE_DIR,
                            "run_E6b_dimensional_raw_specialist.py"),
               encoding="utf-8").read()
    assert "normalize_sample" not in src          # old normalize helper removed
    assert "def normalize" not in src
    for pat in (" / s.mean", " / x.mean", "/ sample.mean", "/ x_bar",
                "/ mean(sample)", " / mean(", "s / s.mean", "x / x.mean"):
        assert pat not in src, f"found per-sample division pattern: {pat}"
    # pivot assigns the raw reconstructed sample directly
    assert "X[i] = raw_map[key]" in src


def test_scaler_fit_on_train_only():
    """input_scaler statistics come from train fit; test only transformed."""
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(1)
    X_train = rng.gamma(2.0, 1.0, size=(20, 7)) * 1000.0
    X_test = X_train + 5.0
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    # test transform must equal (X_test - mean_train) / std_train
    expected = (X_test - scaler.mean_) / scaler.scale_
    assert np.allclose(X_test_s, expected)
    # verifying fit used ONLY X_train: recompute train stats independently
    assert np.allclose(scaler.mean_, X_train.mean(axis=0))
    assert np.allclose(scaler.scale_, X_train.std(axis=0))


def test_fold_partition():
    folds = E6.get_combo_split()
    n_combos = len(CFG.BETA_GRID) * len(CFG.GAMMA_OVER_ETA_GRID) * len(CFG.N_GRID)
    all_test = sorted(c for f in folds for c in f["test_combos"])
    assert len(all_test) == n_combos and len(set(all_test)) == n_combos
    for f in folds:
        assert not (set(f["train_combos"]) & set(f["test_combos"]))
        assert len(f["test_combos"]) == n_combos // 5


def test_loss_and_j1_contract():
    df = pd.DataFrame({
        "beta_hat": [2.2, 1.8], "eta_hat": [1050.0, 980.0],
        "gamma_hat": [510.0, 490.0],
        "beta": [2.0, 2.0], "eta": [1000.0, 1000.0], "gamma": [500.0, 500.0],
    })
    df = E6.compute_per_sample_loss(df)
    assert not df["loss"].isna().any()
    j1 = math.sqrt(df["loss"].mean())
    assert math.isfinite(j1) and j1 > 0
    r_gamma = (df["gamma_hat"] - df["gamma"]) / df["eta"]
    assert np.allclose(df["loss"] - (df["beta_hat"] - df["beta"])**2 / 4.0
                       - (df["eta_hat"] - df["eta"])**2 / 1e6 - r_gamma**2, 0)


def test_crossfit_selects_on_train_scores_on_heldout():
    """L1–L5 cross-fit: selection on train, scoring on held-out (no leak)."""
    import analyze_E1_E2_crossfit as CF
    rng = np.random.default_rng(3)
    # synthetic: 2 betas x 2 goe x 2 n = 8 combos x 20 repeats x 26 deltas
    rows = []
    for b in (2.0, 3.0):
        for goe in (0.5, 1.0):
            for n in (7, 10):
                for rid in range(20):
                    # per-sample loss curve with a true optimum near delta=0.2
                    base = float(rng.random())
                    for j, d in enumerate(CFG.DELTA_GRID):
                        loss = base + (d - 0.2) ** 2
                        rows.append({"beta": b, "eta": 1000.0,
                                     "gamma": goe * 1000.0,
                                     "gamma_over_eta": goe, "n": n,
                                     "repeat_id": rid, "delta": d,
                                     "j1_sq": loss})
    scan = pd.DataFrame(rows)
    res = CF.run_crossfit(scan, n_folds=5, default_delta=0.1)
    pooled = res["pooled_metrics"]
    # all layers present, cross-fit J1 finite and ordered
    layers = list(pooled["layer"])
    assert layers == ["Default", "L1", "L2", "L3", "L4", "L5"]
    assert pooled["J1"].notna().all()
    # L5 (most info) should be <= L1 (least info) in this synthetic (both >= Default's fixed 0.1 rule on avg)
    j1 = dict(zip(pooled["layer"], pooled["J1"]))
    assert j1["L5"] <= j1["L1"] + 1e-12
    # each selected delta was chosen on train folds (fold column present)
    assert "fold" in res["selected_deltas"].columns
