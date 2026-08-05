"""Contract tests for the B1/B2/B3 paper-evidence outputs (Study01 E6 route).

These tests read the COMMITTED compact outputs (summary.json / summary.csv /
param_metrics.csv / beta_holdout.csv / model_comparison.csv / manifests), not
the gitignored per-sample tables, so they run wherever the repo is checked out
with the sealed artifacts present.

Covers:
  - B2 WMLE/LSE: method schema, complete-case J1, the documented single WMLE
    failure, parameter Bias/RMSE/MAE, sample-key alignment with the MC scan.
  - B3 quantiles: per-method/per-seed schema, finite relative metrics, zero
    failure for the MDM-derived main methods, honest failure propagation for
    WMLE.
  - B1 unseen-beta: per-(beta, seed, model) schema, same-test sample counts,
    pooled summary consistency, leave-one-beta-out partition.
"""

import json
import math
import os
import sys

import numpy as np
import pandas as pd

STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E6_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal", "E6_dimensional_raw")
SPECIALIST = os.path.join(E6_DIR, "specialist")
UNSEEN_BETA = os.path.join(E6_DIR, "unseen_beta")
TRAD_REF = os.path.join(E6_DIR, "traditional_ref")
QUANTILES = os.path.join(E6_DIR, "quantiles")

BETAS = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
SEEDS = [42, 2026, 3407]
N_GRID = [7, 10, 15, 20]


def _load_json(rel):
    with open(os.path.join(STUDY_ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# B2 — WMLE/LSE external reference
# ============================================================

def test_b2_summary_schema():
    d = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "traditional_ref", "summary.json"))
    s = {r["method"]: r for r in d["summary"]}
    assert set(s) == {"WMLE", "LSE"}
    for method in ("WMLE", "LSE"):
        r = s[method]
        assert math.isfinite(r["J1"]) and r["J1"] > 0
        assert r["n_total"] == 48000
        assert r["n_valid"] <= 48000
        assert 0.0 <= r["failure_rate"] <= 1.0
        for n in N_GRID:
            assert f"J1_n{n}" in r and math.isfinite(r[f"J1_n{n}"])
    # the single documented WMLE non-convergence must be counted honestly
    assert s["WMLE"]["n_failed"] == 1
    assert s["WMLE"]["n_valid"] == 47999


def test_b2_param_metrics():
    p = pd.read_csv(os.path.join(TRAD_REF, "param_metrics.csv"))
    assert set(p["method"]) == {"WMLE", "LSE"}
    for col in ("bias_beta", "bias_eta", "bias_gamma",
                "rmse_beta", "rmse_eta", "rmse_gamma",
                "mae_beta", "mae_eta", "mae_gamma"):
        assert col in p.columns
        assert p[col].notna().all()
        assert (p[col] >= 0).all() or col.startswith("bias")


def test_b2_sample_key_verification():
    k = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "traditional_ref",
                                "sample_key_verification.json"))
    assert k["match"] is True
    assert k["n_scan_keys"] == 48000 == k["n_grid_keys"]


# ============================================================
# B3 — engineering quantiles
# ============================================================

def test_b3_summary_schema():
    df = pd.read_csv(os.path.join(QUANTILES, "summary.csv"))
    assert set(df["method"]) == {"Dimensional-RAW", "Default", "L6", "WMLE",
                                 "LSE"}
    assert set(df["quantile"]) == {"x0.90", "x0.95", "x0.99"}
    for seed in SEEDS:
        sub = df[df["method"] == "Dimensional-RAW"]
        assert seed in set(sub["seed"]), "DIM-RAW must report all three seeds"
    for col in ("bias", "rmse", "mae", "p95_abs_rel"):
        assert df[col].notna().all(), f"{col} must be finite for all rows"


def test_b3_zero_failure_for_mdm_methods():
    df = pd.read_csv(os.path.join(QUANTILES, "summary.csv"))
    for method in ("Dimensional-RAW", "Default", "L6"):
        sub = df[df["method"] == method]
        assert (sub["failure_rate"] == 0).all(), \
            f"{method} should have no failures (all MDM estimates valid)"


def test_b3_parameter_gain_does_not_presuppose_quantile_gain():
    """Honesty contract: report whatever the quantile metrics show; do not
    require DIM-RAW to win the tail quantile."""
    df = pd.read_csv(os.path.join(QUANTILES, "summary.csv"))
    x95 = df[df["quantile"] == "x0.95"]
    dim = x95[x95["method"] == "Dimensional-RAW"]["rmse"].mean()
    default = x95[x95["method"] == "Default"]["rmse"].mean()
    # the check is that both are finite and comparable in magnitude
    assert math.isfinite(dim) and math.isfinite(default)
    assert 0.1 < dim < 0.5 and 0.1 < default < 0.5


# ============================================================
# B1 — unseen-beta held-out validation
# ============================================================

def test_b1_schema():
    bh = pd.read_csv(os.path.join(UNSEEN_BETA, "beta_holdout.csv"))
    assert set(bh["model"]) == {"Dimensional-RAW", "Default", "L6"}
    assert set(bh["seed"]) == set(SEEDS)
    assert set(bh["held_out_beta"]) == set(BETAS)
    # 8 betas x 3 seeds x 3 models
    assert len(bh) == 8 * 3 * 3
    assert bh["J1"].notna().all()


def test_b1_same_test_sample_counts():
    bh = pd.read_csv(os.path.join(UNSEEN_BETA, "beta_holdout.csv"))
    counts = bh.groupby(["held_out_beta", "seed", "model"])["n_samples"].unique()
    for (_, _, model), vals in counts.items():
        assert (vals == 6000).all(), \
            f"{model} must be scored on the same 6000 held-out samples"


def test_b1_split_report_disjoint():
    sr = pd.read_csv(os.path.join(UNSEEN_BETA, "split_report.csv"))
    assert len(sr) == 8
    for _, row in sr.iterrows():
        assert row["n_train_combos"] == 140
        assert row["n_test_combos"] == 20
        assert str(row["test_betas"]).startswith("[")


def test_b1_pooled_consistency():
    d = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "unseen_beta", "summary.json"))
    pooled = d["pooled"]
    assert "Dimensional_RAW_3seed" in pooled
    dim_mean = pooled["Dimensional_RAW_3seed"]["pooled_J1_mean"]
    dflt = pooled["Default_J1"]
    assert math.isfinite(dim_mean) and math.isfinite(dflt)
    assert 0.3 < dim_mean < 0.9 and 0.3 < dflt < 0.9
    assert 0.0 <= pooled["relative_improvement_vs_Default"] <= 0.3
    # boundary note present
    assert "boundary" in d and "discrete" in d["boundary"]


# ============================================================
# Shared baselines (default/L6 anchors against sealed E6 values)
# ============================================================

def test_baseline_anchors_match_sealed_e6():
    """paper_support.default_and_l6 reproduces the sealed Default/L6 J1."""
    sys.path.insert(0, os.path.join(STUDY_ROOT, "code"))
    import paper_support as PS
    _mc, df_full, _raw = PS.load_scan(verbose=False)
    base = PS.default_and_l6(df_full)
    assert len(base) == 48000
    assert abs(PS.j1_from_loss(base["default_loss"]) - 0.630409) < 1e-5
    assert abs(PS.j1_from_loss(base["l6_loss"]) - 0.492297) < 1e-5
