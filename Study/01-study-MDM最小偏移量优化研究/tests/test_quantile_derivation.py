"""Fail-closed contract tests for the engineering-quantile derivation.

Covers:
1. Quantile formula correctness vs hand-computed values
2. Vectorized build_quantile_long matches a row-wise reference
3. Failure-free contract on scoped methods (failed=True raises)
4. MLE excluded from scope
5. Model-first aggregation: 15 (fold x seed) models, median matches
6. Deterministic reproducibility
7. Known-value spot check on real P4 rows (MDM-Default, main_holdout)
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

import quantile_config as cfg
import run_quantile_derivation as rq
from studies.common.metrics import quantile_est, quantile_true

REAL_CSV = cfg.P4_INPUT_CSV


def _synthetic_rows(n: int, method: str = "MDM-Default") -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = {
        "track": ["main_holdout"] * n,
        "method": [method] * n,
        "fold": [f"combo_fold_{i % 5 + 1}" for i in range(n)],
        "seed": [42 if i % 3 == 0 else (2026 if i % 3 == 1 else 3407) for i in range(n)],
        "beta": [1.5] * n,
        "gamma_over_eta": [0.1] * n,
        "n": [7] * n,
        "repeat_id": list(range(n)),
        "beta_hat": [1.2] * n,
        "eta_hat": [0.9] * n,
        "gamma_hat": [0.3] * n,
        "failed": [False] * n,
    }
    df = pd.DataFrame(rows)
    # give estimates slight per-sample variation
    df["beta_hat"] += rng.normal(0, 0.05, n)
    return df


# --- 1. formula ------------------------------------------------------------- #


def test_quantile_true_hand_computed():
    # x_0.95 with beta=1.5, eta=1.0, gamma=0.1:
    # 0.1 + (-ln 0.95)^(1/1.5) = 0.1 + 0.051293^0.6667 = 0.23805
    assert quantile_true(1.5, 1.0, 0.1, 0.95) == pytest.approx(0.23805, abs=1e-4)


def test_quantile_est_hand_computed():
    # x_hat_0.95 with beta_hat=1.1074, eta_hat=0.9465, gamma_hat=0.3873
    xh = quantile_est(1.1074360721837024, 0.9465472997033988, 0.387303131529939, 0.95)
    assert xh == pytest.approx(0.45207, abs=1e-4)


def test_quantile_relative_error_sign():
    e = rq_model_error(1.1074360721837024, 0.9465472997033988, 0.387303131529939,
                       1.5, 1.0, 0.1, 0.95)
    assert e == pytest.approx((0.45207 - 0.23805) / 0.23805, abs=1e-3)


def rq_model_error(bh, eh, gh, b, e_, g, R):
    return (quantile_est(bh, eh, gh, R) - quantile_true(b, e_, g, R)) / quantile_true(b, e_, g, R)


# --- 2. vectorized == reference -------------------------------------------- #


def test_build_long_matches_reference():
    df = _synthetic_rows(30)
    long_df = rq.build_quantile_long(df)
    for _, r in long_df.iterrows():
        ref = rq_model_error(
            float(r["beta_hat"]), float(r["eta_hat"]), float(r["gamma_hat"]),
            float(r["beta"]), 1.0, float(r["gamma_over_eta"]), float(r["R"]),
        )
        assert r["rel_err"] == pytest.approx(ref, rel=1e-9)
        assert r["x_true"] == pytest.approx(
            quantile_true(float(r["beta"]), 1.0, float(r["gamma_over_eta"]), float(r["R"]))
        )


# --- 3. failure-free contract ---------------------------------------------- #


def test_failure_free_contract_raises():
    df = _synthetic_rows(10)
    df.loc[3, "failed"] = True
    with pytest.raises(RuntimeError, match="failed=True"):
        rq.build_quantile_long(df)


def test_mle_excluded_from_scope():
    df = _synthetic_rows(10, method="MLE")
    df["failed"] = True  # MLE has failures but is out of scope
    # MLE not in METHOD_SCOPE -> filtered before failure check
    long_df = rq.build_quantile_long(df)
    assert len(long_df) == 0
    assert "MLE" not in cfg.METHOD_SCOPE


# --- 4. model-first aggregation -------------------------------------------- #


def test_model_first_15_models():
    df = _synthetic_rows(15 * 8, method="MDM-Vector-MLP")  # 15 foldxseed x 8 samples
    long_df = rq.build_quantile_long(df)
    md = rq.per_model_metrics(long_df, ["track", "method", "R", "fold", "seed"])
    g = md[(md["method"] == "MDM-Vector-MLP") & (md["R"] == 0.95)]
    assert len(g) == 15
    # median of per-model rmse equals direct median
    direct = np.median(g["rmse"].to_numpy())
    agg = rq.aggregate_models(g["rmse"].to_numpy())
    assert agg["median"] == pytest.approx(direct)
    assert agg["n_models"] == 15


# --- 5. reproducibility ----------------------------------------------------- #


def test_deterministic_reproducible():
    df = _synthetic_rows(20)
    a = rq.build_quantile_long(df)
    b = rq.build_quantile_long(df)
    pd.testing.assert_frame_equal(a[["rel_err"]], b[["rel_err"]])


# --- 6. real-data spot check ------------------------------------------------ #


def test_real_p4_row_spot_check():
    """Verify a real MDM-Default main_holdout row reproduces the derivation."""
    if not REAL_CSV.exists():
        pytest.skip("P4 formal evaluation_all.csv not present")
    raw = pd.read_csv(REAL_CSV, nrows=100, low_memory=False)
    row = raw[raw["method"] == "MDM-Default"].iloc[0]
    b, g, eta = float(row["beta"]), float(row["gamma_over_eta"]), 1.0
    bh, eh, gh = float(row["beta_hat"]), float(row["eta_hat"]), float(row["gamma_hat"])
    xt = quantile_true(b, eta, g, 0.95)
    xh = quantile_est(bh, eh, gh, 0.95)
    assert xh > 0.0
    # vectorized path on the same 100 rows
    long_df = rq.build_quantile_long(raw[raw["method"].isin(cfg.METHOD_SCOPE)])
    hit = long_df[(long_df["method"] == "MDM-Default")
                  & (long_df["R"] == 0.95)].iloc[0]
    assert hit["x_true"] == pytest.approx(xt)
    assert hit["x_hat"] == pytest.approx(xh)
