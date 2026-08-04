"""Contract tests for the normalized-RAW (NRMC) final method.

Covers the frozen design and the input-representation contracts:
  - frozen parameter design (160 combos, eta=1000, must include (2,1000,1000))
  - normalization Z_n = sorted(x)/mean(x), dims = n
  - scale invariance of the normalized input (no scale leak)
  - input is the full normalized sample only (no features / n / true params)
  - 5-fold full-combo holdout is a partition, train/test disjoint
  - loss / J1 definitions match the formal metric contract

These tests are self-contained (no reliance on generated artifacts).
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

import nrmc_config as CFG
import run_E5b_normalized_raw_specialist as E5B


def test_frozen_design():
    s = CFG.design_summary()
    assert s["combos"] == 160
    assert s["n_samples"] == 48000
    assert s["n_mdm_fits"] == 1248000
    assert s["beta_grid"] == [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    assert s["eta"] == 1000.0
    assert s["gamma_over_eta_grid"] == [0.10, 0.25, 0.50, 0.75, 1.00]
    assert s["gamma_grid"] == [100.0, 250.0, 500.0, 750.0, 1000.0]
    assert s["n_grid"] == [7, 10, 15, 20]
    assert s["repeats"] == 300
    assert len(s["delta_grid"]) == 26
    assert s["default_delta"] == 0.1


def test_must_include_combo():
    """(beta, eta, gamma) = (2, 1000, 1000) must be in the design."""
    found = [(b, CFG.ETA, CFG.get_gamma(g))
             for b in CFG.BETA_GRID for g in CFG.GAMMA_OVER_ETA_GRID]
    assert (2.0, 1000.0, 1000.0) in found


def test_normalize_sample_dims_and_unit_mean():
    rng = np.random.default_rng(0)
    for n in (7, 10, 15, 20):
        x = rng.gamma(2.0, 1.0, size=n)
        z = E5B.normalize_sample(x)
        assert len(z) == n
        assert np.all(np.diff(z) >= 0), "Z must be ascending-sorted"
        assert abs(z.mean() - 1.0) < 1e-12, "Z has unit mean by construction"


def test_scale_invariance_of_normalized_input():
    rng = np.random.default_rng(1)
    for n in (7, 10, 15, 20):
        x = rng.weibull(3.0, size=n) + 0.5
        z = E5B.normalize_sample(x)
        for c in (0.001, 1.0, 1000.0):
            zc = E5B.normalize_sample(c * x)
            assert np.allclose(zc, z, rtol=1e-12, atol=1e-12), \
                f"scale invariance violated for n={n}, c={c}"


def test_normalized_input_has_no_key_columns():
    """pivot_norm_vector returns X = (n_samples, n) of normalized values only."""
    rng = np.random.default_rng(2)
    n = 7
    beta, eta, gamma, goe = 2.0, 1000.0, 500.0, 0.5
    norm_map = {}
    rows = []
    for rid in range(3):
        x = rng.gamma(2.0, 1.0, size=n) + gamma
        norm_map[(beta, eta, gamma, goe, n, rid)] = E5B.normalize_sample(x)
        for j, d in enumerate(CFG.DELTA_GRID):
            rows.append({
                "beta": beta, "eta": eta, "gamma": gamma,
                "gamma_over_eta": goe, "n": n, "repeat_id": rid, "delta": d,
                "loss_filled": float(rng.random()), "is_valid": True,
            })
    df = pd.DataFrame(rows)
    keys, X, Y, valid = E5B.pivot_norm_vector(df, norm_map, n)
    assert X.shape == (3, n)
    assert keys.shape[0] == 3
    # every input row equals the normalized reconstructed sample
    for i, r in keys.iterrows():
        key = (float(r["beta"]), float(r["eta"]), float(r["gamma"]),
               float(r["gamma_over_eta"]), int(r["n"]), int(r["repeat_id"]))
        assert np.allclose(X[i], norm_map[key])
        assert abs(X[i].mean() - 1.0) < 1e-9
    assert not np.any(np.isnan(X))


def test_fold_partition():
    design = E5B.get_design("formal")
    folds = E5B.get_combo_split(design)
    n_combos = (len(design["beta_grid"]) * len(design["gamma_over_eta_grid"])
                * len(design["n_grid"]))
    all_test = sorted(c for f in folds for c in f["test_combos"])
    assert len(all_test) == n_combos
    assert len(set(all_test)) == n_combos, "fold test combos not a partition"
    for f in folds:
        assert not (set(f["train_combos"]) & set(f["test_combos"]))
    # each fold holds out 1/5 of combos
    for f in folds:
        assert len(f["test_combos"]) == n_combos // 5


def test_loss_and_j1_contract():
    """J1 = sqrt(mean_i(true_loss_i(delta_hat_i))) with the frozen loss."""
    df = pd.DataFrame({
        "beta_hat": [2.2, 1.8], "eta_hat": [1050.0, 980.0],
        "gamma_hat": [510.0, 490.0],
        "beta": [2.0, 2.0], "eta": [1000.0, 1000.0], "gamma": [500.0, 500.0],
    })
    df = E5B.compute_per_sample_loss(df)
    assert not df["loss"].isna().any()
    # J1 over these two "selected" losses
    j1 = math.sqrt(df["loss"].mean())
    assert math.isfinite(j1) and j1 > 0
    # gamma term normalized by eta, not gamma
    r_gamma = (df["gamma_hat"] - df["gamma"]) / df["eta"]
    assert np.allclose(df["loss"] - (df["beta_hat"] - df["beta"])**2 / 4.0
                       - (df["eta_hat"] - df["eta"])**2 / 1e6
                       - r_gamma**2, 0)


def test_default_delta_and_grid():
    assert E5B.DEFAULT_DELTA == 0.1
    assert E5B.DELTA_GRID[0] == 0.0 and E5B.DELTA_GRID[-1] == 0.50
    assert len(E5B.DELTA_GRID) == 26
