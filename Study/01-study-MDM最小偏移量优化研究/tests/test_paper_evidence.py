"""Contract tests for the B1/B2/B3 paper-evidence outputs (Study01 E6 route).

These tests read the COMMITTED compact outputs (summary.json / summary.csv /
param_metrics.csv / beta_holdout.csv / model_comparison.csv / manifests), not
the gitignored per-sample tables, so they run wherever the repo is checked out
with the sealed artifacts present.  Local-only raw files (estimation.csv,
per_sample.csv, results/) are read only when present, guarded by existence.

Covers:
  - B1 unseen-beta: per-(beta, seed, model) schema, same-test sample counts,
    leave-one-beta-out partition, and a non-vacuous regression that pooled J1
    is sqrt(mean(row-level loss)) per (model, seed), not mean-of-group-J1.
  - B2 WMLE/LSE: method schema, the single WMLE failure included in the
    primary all-sample J1 via its frozen zero-estimate loss, labeled
    complete-case sensitivity, parameter Bias/RMSE/MAE, sample-key alignment.
  - B3 quantiles: per-method/per-seed schema, per-n disk completeness, exact
    three-seed model-first mean, finite metrics, zero failure for the
    MDM-derived main methods.
  - Provenance: each manifest binds its declared entry script and material
    deps via code_sha256; SHA256SUMS covers only tracked files while
    SHA256SUMS.local_not_in_git lists local-only raw files.
  - Figures: render QA (dimensions, non-blank, content within margins).
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
    # primary all-sample J1 includes the failed row (zero-estimate loss);
    # complete-case is a labeled sensitivity and must differ for WMLE
    assert "J1_complete_case" in s["WMLE"]
    assert s["WMLE"]["J1"] > s["WMLE"]["J1_complete_case"]
    for method in ("WMLE", "LSE"):
        for n in N_GRID:
            assert f"J1_n{n}" in s[method] and f"J1_n{n}_cc" in s[method]


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


# ============================================================
# R1 regression tests (row-level pooling, failure treatment,
# per-n + three-seed, provenance, render QA)
# ============================================================

def test_b1_three_seed_stats_pools_row_level():
    """Frozen J1 = sqrt(mean(sample loss)): three_seed_stats must pool
    row-level losses per seed, NOT average the per-beta J1s (non-vacuous)."""
    sys.path.insert(0, os.path.join(STUDY_ROOT, "code"))
    import run_b1_unseen_beta as B1
    rng = np.random.default_rng(0)
    frames = []
    for seed in SEEDS:
        for beta in (1.5, 5.0):
            for _ in range(100):
                frames.append({"held_out_beta": beta, "seed": seed,
                               "model": "Dimensional-RAW",
                               "true_loss": float(rng.gamma(2.0, 1.0)),
                               "is_valid": True, "n": 7})
    long_df = pd.DataFrame(frames)
    stats = B1.three_seed_stats(long_df, "Dimensional-RAW")
    for seed in SEEDS:
        sub = long_df[long_df["seed"] == seed]
        expected = math.sqrt(float(sub["true_loss"].mean()))
        assert abs(stats["per_seed_pooled_J1"][seed] - expected) < 1e-12
    # non-vacuous: mean-of-per-beta-J1 differs from the pooled row-level value
    beta_level = (long_df.groupby(["held_out_beta", "seed"])["true_loss"]
                  .apply(lambda x: math.sqrt(float(x.mean()))))
    mean_of_groups = float(beta_level.groupby(level="seed").mean().mean())
    assert abs(mean_of_groups - stats["pooled_J1_mean"]) > 1e-6


def test_b1_pooled_j1_anchors():
    """B1 pooled numbers match the independent row-level recomputation."""
    d = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "unseen_beta", "summary.json"))
    pooled = d["pooled"]
    dim = pooled["Dimensional_RAW_3seed"]
    assert abs(dim["pooled_J1_mean"] - 0.5417905836) < 1e-6
    assert abs(dim["pooled_J1_std"] - 0.0021218216) < 1e-6
    assert abs(pooled["Default_J1"] - 0.6304091999) < 1e-6
    assert abs(pooled["L6_J1"] - 0.4922971153) < 1e-6
    assert abs(pooled["relative_improvement_vs_Default"]
               - 0.1405731648) < 1e-6


def test_b2_failed_row_included_in_primary_j1():
    """The single WMLE failure enters the primary all-sample J1 via its frozen
    zero-estimate loss (2.5625 for the goe=0.75 row)."""
    est_path = os.path.join(TRAD_REF, "estimation.csv")
    if os.path.exists(est_path):
        est = pd.read_csv(est_path)
        failed = est[est["failed"]]
        assert len(failed) == 1
        row = failed.iloc[0]
        assert row["method"] == "WMLE"
        expected = (((0 - row["beta"]) / row["beta"]) ** 2
                    + ((0 - row["eta"]) / row["eta"]) ** 2
                    + ((0 - row["gamma"]) / row["eta"]) ** 2)
        assert abs(row["loss"] - expected) < 1e-9
        assert abs(row["loss"] - 2.5625) < 1e-6
    d = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "traditional_ref", "summary.json"))
    wmle = {r["method"]: r for r in d["summary"]}["WMLE"]
    assert wmle["n_failed"] == 1
    assert wmle["J1"] > wmle["J1_complete_case"]


def test_b3_per_n_disk_output():
    by_n = pd.read_csv(os.path.join(QUANTILES, "summary_by_n.csv"))
    assert set(by_n["n"]) == {7, 10, 15, 20}
    assert set(by_n["method"]) == {"Dimensional-RAW", "Default", "L6", "WMLE",
                                   "LSE"}
    counts = by_n.groupby(["method", "seed", "quantile"])["n"].count()
    assert (counts == 4).all(), "every (method, seed, quantile) must have all 4 n"
    for col in ("bias", "rmse", "mae", "p95_abs_rel"):
        assert by_n[col].notna().all()


def test_b3_three_seed_mean_consistency():
    s = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "quantiles", "summary.json"))
    entry = s["per_method"]["Dimensional-RAW"]
    assert entry.get("n_seeds") == 3
    for q in ("x0.90", "x0.95", "x0.99"):
        ts = entry["three_seed_mean"][q]
        per_seed = [entry["per_seed"][str(seed)][q] for seed in SEEDS]
        for metric in ("bias", "rmse", "mae", "p95_abs_rel", "failure_rate"):
            assert abs(ts[metric] - float(np.mean([p[metric] for p in per_seed]))
                       ) < 1e-12


def test_b3_three_seed_std_exact():
    """three_seed_std must equal the exact ddof=0 SD of the three per-seed
    metric values, reported for every metric and quantile."""
    s = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                "quantiles", "summary.json"))
    entry = s["per_method"]["Dimensional-RAW"]
    assert entry.get("three_seed_std_ddof") == 0
    for q in ("x0.90", "x0.95", "x0.99"):
        ts = entry["three_seed_std"][q]
        per_seed = [entry["per_seed"][str(seed)][q] for seed in SEEDS]
        for metric in ("bias", "rmse", "mae", "p95_abs_rel", "failure_rate"):
            vals = [p[metric] for p in per_seed]
            expected = float(np.std(vals, ddof=0))
            assert abs(ts[metric] - expected) < 1e-12, \
                f"{q}/{metric}: stored {ts[metric]} != expected {expected}"


def _lf_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        prev = b""
        while True:
            blk = f.read(1 << 20)
            if not blk:
                break
            data = prev + blk
            data = data.replace(b"\r\n", b"\n")
            prev = data[-1:] if data.endswith(b"\r") else b""
            h.update(data[:-1] if prev else data)
        if prev:
            h.update(prev)
    return h.hexdigest()


def test_manifests_bind_entry_scripts():
    for rel in ("unseen_beta", "traditional_ref", "quantiles", "paper"):
        m = _load_json(os.path.join("artifacts/formal/E6_dimensional_raw",
                                    rel, "manifest.json"))
        entry = m.get("code_entry")
        assert entry, f"{rel}: manifest must declare code_entry"
        entry_basename = os.path.basename(entry)
        assert entry_basename in m["code_sha256"], \
            f"{rel}: entry script not bound in code_sha256"
        code_path = os.path.join(STUDY_ROOT, entry)
        assert os.path.exists(code_path), f"{rel}: {code_path} missing"
        assert m["code_sha256"][entry_basename] == _lf_sha256(code_path), \
            f"{rel}: committed entry-script hash mismatch"


def test_sha256_tracked_vs_local_split():
    for rel in ("unseen_beta", "traditional_ref", "quantiles"):
        d = os.path.join(E6_DIR, rel)
        assert os.path.exists(os.path.join(d, "SHA256SUMS"))
        assert os.path.exists(os.path.join(d, "SHA256SUMS.local_not_in_git"))
        tracked = open(os.path.join(d, "SHA256SUMS"), encoding="utf-8").read()
        # local-only raw files must NOT appear in the tracked package list
        for marker in ("results/", "estimation.csv", "per_sample.csv"):
            assert marker not in tracked, \
                f"{rel}: local-only file leaked into tracked SHA256SUMS"
        local = open(os.path.join(d, "SHA256SUMS.local_not_in_git"),
                     encoding="utf-8").read()
        assert local.strip(), f"{rel}: local ledger should not be empty"


def test_figures_render_qa():
    from PIL import Image
    paper = os.path.join(E6_DIR, "paper")
    pngs = [f for f in os.listdir(paper) if f.endswith(".png")]
    assert len(pngs) == 7
    for f in pngs:
        im = Image.open(os.path.join(paper, f)).convert("RGB")
        a = np.asarray(im)
        h, w, _ = a.shape
        assert w >= 900 and h >= 650, f"{f}: dimensions too small"
        assert a.std() > 5.0, f"{f}: appears blank"
        content = ~(a > 245).all(axis=2)
        ys, xs = np.where(content)
        margin = max(2, int(min(h, w) * 0.01))
        assert xs.min() > margin, f"{f}: content clipped at left edge"
        assert xs.max() < w - 1 - margin, f"{f}: content clipped at right edge"
        assert ys.min() > margin, f"{f}: content clipped at top edge"
        assert ys.max() < h - 1 - margin, f"{f}: content clipped at bottom edge"
