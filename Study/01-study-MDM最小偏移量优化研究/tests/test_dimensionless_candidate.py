"""Contract tests for the dimensionless-input Vector-MLP candidate route.

Covers:
1. Dimensionless feature contract: exactly 11 inputs, no constant, no s/x_bar duplicate,
   no true-parameter/banned field, Q2 = median.
2. Feature formulas match direct computation from a raw sample.
3. Feature scale invariance under {0.001, 1, 1000} within a tight float tolerance.
4. Algebraic scale invariance of the J1 loss under Weibull scale equivariance
   (beta_hat invariant; eta_hat/gamma_hat scale linearly with the sample).
5. Reference J1 values reproduce the sealed E3b numbers (Default/L1/L2/L6-hindsight).
6. Cached main-grid integrity (45,000 unique samples, complete 26-dim risk curves).
7. evaluate_model selection semantics on a small synthetic case.
8. Cross-check: add_dimensionless_columns agrees with the direct per-sample function.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_CODE_DIR = Path(__file__).resolve().parents[1] / "code"
_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
for p in (str(_CODE_DIR), str(_PYTHON_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_dimensionless_candidate as rc  # noqa: E402
import run_E4_formal_validation as e4  # noqa: E402

SCALES = [0.001, 1.0, 1000.0]


# --- 1. feature contract ---------------------------------------------------- #


def test_dimensionless_feature_contract():
    assert len(rc.DIMENSIONLESS_COLS) == 11
    assert rc.DIMENSIONLESS_COLS[0] == "n"
    # No constant-1 feature (x_bar/x_bar) and no duplicate std/mean ratio (s/x_bar
    # is already represented by CV).
    assert "x_bar_r" not in rc.DIMENSIONLESS_COLS
    assert "s_r" not in rc.DIMENSIONLESS_COLS
    assert set(rc.DIMENSIONLESS_COLS) == {
        "n", "x_min_r", "x_max_r", "range_r", "Q1_r", "Q2_r", "Q3_r", "IQR_r",
        "CV", "g1", "g2",
    }
    # No banned/true-parameter field may appear (fail-closed).
    rc.verify_no_banned_fields(rc.DIMENSIONLESS_COLS)


# --- 2. formulas ------------------------------------------------------------ #


def test_dimensionless_formulas():
    sample = np.array([0.3, 0.5, 0.8, 1.2, 2.0])
    f = rc._dimensionless_from_sample(sample)
    x_bar = float(sample.mean())
    assert f["n"] == len(sample)
    assert f["x_min_r"] == pytest.approx(sample.min() / x_bar)
    assert f["x_max_r"] == pytest.approx(sample.max() / x_bar)
    assert f["range_r"] == pytest.approx((sample.max() - sample.min()) / x_bar)
    assert f["Q1_r"] == pytest.approx(np.percentile(sample, 25) / x_bar)
    # Q2 is the median.
    assert f["Q2_r"] == pytest.approx(np.median(sample) / x_bar)
    assert f["Q3_r"] == pytest.approx(np.percentile(sample, 75) / x_bar)
    assert f["IQR_r"] == pytest.approx(f["Q3_r"] - f["Q1_r"])
    assert f["CV"] == pytest.approx(sample.std(ddof=1) / x_bar)


# --- 3. feature scale invariance ------------------------------------------- #


def test_feature_scale_invariance():
    rng = np.random.default_rng(7)
    for _ in range(50):
        n = int(rng.integers(5, 25))
        sample = np.sort(rng.uniform(0.2, 3.0, size=n))
        f0 = rc._dimensionless_from_sample(sample)
        for c in SCALES:
            fc = rc._dimensionless_from_sample(sample * c)
            for k in rc.DIMENSIONLESS_COLS:
                assert fc[k] == pytest.approx(f0[k], rel=1e-9, abs=1e-12)


# --- 4. algebraic loss scale invariance ------------------------------------ #


def test_loss_scale_invariance_algebraic():
    def loss(b, e, g, bh, eh, gh):
        return ((bh - b) / b) ** 2 + ((eh - e) / e) ** 2 + ((gh - g) / e) ** 2

    beta, eta, gamma = 2.0, 1.0, 0.5
    bh, eh, gh = 2.1, 0.9, 0.55
    base = loss(beta, eta, gamma, bh, eh, gh)
    for c in SCALES:
        # Weibull scale equivariance: a sample scaled by c maps
        # (beta, eta, gamma) -> (beta, c*eta, c*gamma) and the estimates likewise,
        # leaving every loss term unchanged.
        assert loss(beta, c * eta, c * gamma, bh, c * eh, c * gh) == pytest.approx(
            base, rel=1e-12
        )


# --- 5. references reproduce sealed E3b ------------------------------------ #


def test_references_match_sealed_e3b():
    df_main, loss_long = rc.load_cached_main_grid()
    refs = rc.compute_reference_results(loss_long)
    # Sealed E3b model_comparison.csv (combo_holdout_pooled).
    expected = {
        "Default": 0.633219,
        "L1": 0.632913,
        "L2": 0.632541,
        "L6-hindsight": 0.494530,
    }
    for name, sealed_j1 in expected.items():
        assert refs[name]["pooled_J1"] == pytest.approx(sealed_j1, abs=1e-5)


# --- 6. cached main-grid integrity ----------------------------------------- #


def test_cached_main_grid_integrity():
    df_main, loss_long = rc.load_cached_main_grid()
    assert len(df_main) == 45000
    assert df_main.duplicated(rc.SAMPLE_KEYS).sum() == 0
    assert not df_main[rc.LOSS_COLS].isna().any().any()
    for col in rc.DIMENSIONLESS_COLS:
        assert col in df_main.columns
    # loss table has exactly one row per (sample, delta).
    assert loss_long.duplicated(["beta", "gamma_over_eta", "n", "repeat_id", "delta"]).sum() == 0


# --- 7. evaluate_model selection semantics --------------------------------- #


class _DummyScaler:
    def __init__(self):
        self.mean_ = np.zeros(rc.N_DELTAS)
        self.scale_ = np.ones(rc.N_DELTAS)

    def inverse_transform(self, Y):
        return Y * self.scale_ + self.mean_


class _DummyModel:
    """Predicts a fixed 26-dim curve shifted per-sample so argmin is testable."""

    def __init__(self, curve):
        self._curve = np.asarray(curve, dtype=float)

    def predict(self, X):
        return np.tile(self._curve, (len(X), 1))


def test_evaluate_model_selection_semantics():
    # Three synthetic samples; loss table holds per (sample, delta) realized loss.
    samples = pd.DataFrame({
        "beta": [1.5, 2.0, 2.5],
        "eta": [1.0, 1.0, 1.0],
        "gamma": [0.1, 0.5, 1.0],
        "gamma_over_eta": [0.1, 0.5, 1.0],
        "n": [7, 10, 20],
        "repeat_id": [0, 1, 2],
    })
    rows = []
    for _, s in samples.iterrows():
        for j, d in enumerate(rc.DELTA_GRID):
            rows.append({
                "beta": s["beta"], "gamma_over_eta": s["gamma_over_eta"],
                "n": s["n"], "repeat_id": s["repeat_id"], "delta": d,
                "loss": float(j) / 100.0,  # realized loss grows with delta
            })
    loss_long = pd.DataFrame(rows)

    # Model predicts a curve with min at delta index 3 (0.06).
    curve = np.arange(rc.N_DELTAS, dtype=float)
    model = _DummyModel(curve)
    scaler = _DummyScaler()
    # Dummy features so build_X returns the right number of rows.  Do NOT clobber
    # the 'n' column: n is both a sample key and a dimensionless feature.
    feat = samples.copy()
    for c in rc.DIMENSIONLESS_COLS:
        if c != "n":
            feat[c] = 1.0
    means = {c: 0.0 for c in rc.DIMENSIONLESS_COLS}
    stds = {c: 1.0 for c in rc.DIMENSIONLESS_COLS}

    out = rc.evaluate_model(
        model, scaler, feat, loss_long,
        rc.DIMENSIONLESS_COLS, [], means, stds, 1e6,
        "combo_fold_1", 42,
    )
    # argmin of the predicted curve is delta index 0 -> 0.00.
    assert out["selected_delta"].tolist() == [0.00, 0.00, 0.00]
    assert out["true_loss"].tolist() == [0.0, 0.0, 0.0]
    assert out["is_valid"].all()
    assert out["regret"].tolist() == [0.0, 0.0, 0.0]


# --- 8. add_dimensionless_columns agrees with direct function --------------- #


def test_add_dimensionless_columns_matches_direct():
    df_main, _ = rc.load_cached_main_grid()
    sub = df_main.head(20).copy()
    df_aug = rc.add_dimensionless_columns(sub)
    for _, row in sub.iterrows():
        sample = e4.generate_sample(
            float(row["beta"]), float(row["eta"]), float(row["gamma"]),
            int(row["n"]), int(row["repeat_id"]), seed=rc.SEED_NAMESPACE,
        )
        direct = rc._dimensionless_from_sample(sample)
        for k in rc.DIMENSIONLESS_COLS:
            assert df_aug.loc[row.name, k] == pytest.approx(direct[k], rel=1e-9, abs=1e-12)


def test_fit_and_build_X_shape():
    df_main, _ = rc.load_cached_main_grid()
    # Rows 0..(repeat<50) span all 45 combos (all n / beta / gamma values), so every
    # feature varies and z-scoring yields per-column mean 0 / std 1 (float32 precision).
    train = df_main[df_main["repeat_id"] < 50].head(300)
    means, stds = rc.fit_zscore_params(train, rc.DIMENSIONLESS_COLS)
    X = rc.build_X(train, rc.DIMENSIONLESS_COLS, [], means, stds)
    assert X.shape == (min(300, len(train)), 11)
    # z-scored features have ~0 mean / ~1 std on the fitted data (float32 precision).
    assert np.allclose(X.mean(axis=0), 0.0, atol=1e-6)
    assert np.allclose(X.std(axis=0), 1.0, atol=1e-6)
