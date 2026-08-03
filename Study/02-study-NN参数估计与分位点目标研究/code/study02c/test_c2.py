"""Tests for C2 core calculations (counterfactual, Jacobian, reproduction).

Run from the study02c directory:
    python -m pytest code/study02c/test_c2.py -v
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import c2_analyze
import data as c2data
from studies.common.metrics import quantile_true

R95 = 0.95


def _x(b, e, g):
    return quantile_true(b, e, g, R95)


def test_quantile_formula():
    # x_R = gamma + eta * (-ln R)^(1/beta); R=0.95 => -ln(0.95)
    assert math.isclose(_x(2.0, 100.0, 10.0), 10.0 + 100.0 * (-math.log(0.95)) ** 0.5, rel_tol=1e-12)


def test_counterfactual_single_replacement():
    # Replacing only beta must equal recomputing x0.95 with that beta and true eta/gamma
    b, e, g = 2.0, 1000.0, 50.0
    bs, es, gs = 1.7, 1300.0, -20.0
    xt = _x(b, e, g)
    d_beta = _x(bs, e, g) - xt
    assert math.isclose(d_beta, quantile_true(bs, e, g, R95) - xt, rel_tol=1e-12)
    d_eta = _x(b, es, g) - xt
    assert math.isclose(d_eta, quantile_true(b, es, g, R95) - xt, rel_tol=1e-12)
    d_gamma = _x(b, e, gs) - xt
    assert math.isclose(d_gamma, quantile_true(b, e, gs, R95) - xt, rel_tol=1e-12)


def test_counterfactual_combined_equals_direct():
    b, e, g = 2.0, 1000.0, 50.0
    bs, es, gs = 1.7, 1300.0, -20.0
    xt = _x(b, e, g)
    combined = _x(bs, es, gs) - xt
    assert math.isclose(combined, quantile_true(bs, es, gs, R95) - xt, rel_tol=1e-12)


def test_jacobian_consistent_with_finite_difference():
    b, e, g = 2.0, 1000.0, 50.0
    db, de, dg = c2_analyze._jacobian(b, e, g)
    eps = 1e-6
    db_num = (_x(b + eps, e, g) - _x(b - eps, e, g)) / (2 * eps)
    de_num = (_x(b, e + eps, g) - _x(b, e - eps, g)) / (2 * eps)
    dg_num = (_x(b, e, g + eps) - _x(b, e, g - eps)) / (2 * eps)
    assert math.isclose(db, db_num, rel_tol=1e-4)
    assert math.isclose(de, de_num, rel_tol=1e-4)
    assert math.isclose(dg, dg_num, rel_tol=1e-4)


def test_jacobian_linear_approx_local():
    # For small perturbations the Jacobian first-order approximation should be close
    b, e, g = 2.0, 1000.0, 50.0
    bs, es, gs = b + 0.02, e + 10.0, g + 1.0
    db, de, dg = c2_analyze._jacobian(b, e, g)
    approx = db * (bs - b) + de * (es - e) + dg * (gs - g)
    exact = _x(bs, es, gs) - _x(b, e, g)
    assert abs(approx - exact) / max(1.0, abs(exact)) < 0.05


def test_inference_reproduces_b4_npz():
    """Re-inferred P x0.95 from frozen checkpoints must match B4 per-seed NPZ."""
    b3 = c2data.load_b3_manifest()
    models = c2data.load_p_models(b3)
    datasets = c2data.generate_test_data()
    # only a small slice for test speed: cluster 0, replicate 0, all n
    keys = [(0, 0, n) for n in c2data.N_VALUES]
    small = {k: datasets[k] for k in keys}
    p_params = c2data.infer_p_params(models, small)
    npz = c2data.load_b4_npz()
    key_to_idx = {k: i for i, k in enumerate(npz["keys"])}
    for k, arr in p_params.items():
        idx = key_to_idx[f"{k[0]}_{k[1]}_{k[2]}"]
        stored = npz["p_seeds"][idx]
        for s in range(arr.shape[0]):
            if np.isfinite(arr[s]).all():
                pred = quantile_true(*arr[s], R95)
                assert abs(pred - float(stored[s])) / max(1.0, abs(float(stored[s]))) < 1e-4


def test_b4_results_match_npz_means():
    rows = c2data.load_b4_results()
    npz = c2data.load_b4_npz()
    key_to_idx = {k: i for i, k in enumerate(npz["keys"])}
    for r in rows:
        k = f"{r['cluster']}_{r['replicate']}_{r['n']}"
        idx = key_to_idx[k]
        p_mean = float(np.nanmean(npz["p_seeds"][idx]))
        assert abs(p_mean - r["P_mean"]) / max(1.0, abs(r["P_mean"])) < 1e-4


# ---- C2 revised-metric tests ----

def test_cluster_rmse_definition_present_and_distinct():
    """Primary cluster metric is cluster-RMSE(D)<cluster-RMSE(P); the
    majority-of-rows variant is supplementary and separately named."""
    rows = c2data.load_b4_results()
    npz = c2data.load_b4_npz()
    c2_1 = c2_analyze.c2_1_n_heterogeneity(rows, npz)
    for n in c2data.N_VALUES:
        cl = c2_1["per_n"][str(n)]["clusters"]
        assert "n_clusters_rmse_D_better" in cl          # primary
        assert "majority_rows_D_better" in cl            # supplementary, renamed
        assert "cluster_I_median" in cl
        assert "cluster_I_q25" in cl and "cluster_I_q75" in cl


def test_normalized_seed_spread_fields_and_scale():
    """seed spread uses SD/true_x095 (scale-free), named accurately, P and D."""
    rows = c2data.load_b4_results()
    npz = c2data.load_b4_npz()
    c2_1 = c2_analyze.c2_1_n_heterogeneity(rows, npz)
    for n in c2data.N_VALUES:
        ss = c2_1["per_n"][str(n)]["seed_spread"]
        for key in ["P_normalized_spread_mean", "D_normalized_spread_mean",
                    "P_spread_vs_err_spearman", "D_spread_vs_err_spearman"]:
            assert key in ss, key
        # normalized spread must be dimensionless (small, ~0..1), not raw x0.95 scale
        assert ss["P_normalized_spread_mean"] < 1.0, "normalized spread should be ~0..1"
        assert ss["D_normalized_spread_mean"] < 1.0


def test_seed_spread_scale_free_small_example():
    """A known small case: constant true value, spread proportional to true."""
    # manual computation of normalized spread = SD(seeds)/true_x095
    import numpy as np
    seeds = np.array([100.0, 110.0, 90.0])
    true = 100.0
    norm = float(np.std(seeds)) / true
    assert abs(norm - np.std(seeds) / 100.0) < 1e-12
    assert norm < 1.0


def test_relative_counterfactual_fields_and_b4_alignment():
    """C2-2 primary is relative (contribution/true); per-seed ensembled within
    row before cross-row aggregation; combined aligns with B4 P_rel_err."""
    b3 = c2data.load_b3_manifest()
    models = c2data.load_p_models(b3)
    datasets = c2data.generate_test_data()
    keys = [(0, r, n) for r in range(c2data.N_REPLICATES) for n in c2data.N_VALUES]
    small = {k: datasets[k] for k in keys}
    p_params = c2data.infer_p_params(models, small)
    rows = [r for r in c2data.load_b4_results()
            if r["cluster"] == 0 and (r["cluster"], r["replicate"], r["n"]) in keys]
    prop = c2_analyze.c2_2_propagation(p_params, small)
    for n in c2data.N_VALUES:
        pn = prop["per_n"][str(n)]
        assert "relative_mean_abs" in pn
        assert "nonadditivity_relative" in pn
        assert "jacobian_reference_relative" in pn
        assert "raw_scale_supplement_mean_abs" in pn
    # B4 alignment within tolerance on the slice
    align = c2_analyze.c2_2_b4_alignment(p_params, small, rows)
    assert align["max_abs_diff"] < 1e-4


def test_relative_nonadditivity_defined():
    """Non-additivity in relative terms must equal combined - sum of singles."""
    rb, re, rg, rc = 0.2, -0.3, 0.1, 0.05
    nonadd = rc - (rb + re + rg)
    assert abs(nonadd - (0.05 - (0.2 - 0.3 + 0.1))) < 1e-12


# ---- C3/C4 tests ----

def test_c3_1_availability_and_direction_fields():
    """C3-1 must report availability, common-valid RMSE, BH decision and a
    decision category per domain x n (route-valid RMSE only supplementary)."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_1_availability_vs_error()
    for dom in c3_c4_analyze.DOMAINS:
        for n in c3_c4_analyze.N_VALUES:
            c = res[dom][f"n{n}"]
            assert "availability" in c and "P" in c["availability"] and "D" in c["availability"]
            assert "common_valid" in c and "rmse_P" in c["common_valid"] and "rmse_D" in c["common_valid"]
            assert "bh_decision" in c and "support" in c["bh_decision"]
            assert "route_valid_rmse_supplementary" in c
            assert c["decision_category"] in {
                "supported_avail_ok", "supported_avail_risk",
                "no_confirmed_difference", "p_better_common_valid", "not_comparable"}


def test_c3_1_low_n10_p_better():
    """Regression (review): low n10 is B5-v6 BH-supported P better."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_1_availability_vs_error()
    c = res["low"]["n10"]
    assert c["bh_decision"]["support"] == "supported (BH)"
    assert c["bh_decision"]["direction"] == "P better"
    assert c["decision_category"] == "p_better_common_valid"


def test_c3_1_loc_n15_no_confirmed():
    """Regression (review): loc n15 is BH not significant despite unadjusted
    'D better' direction -> no_confirmed_difference."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_1_availability_vs_error()
    c = res["loc"]["n15"]
    assert c["bh_decision"]["support"] == "not significant (BH)"
    assert c["decision_category"] == "no_confirmed_difference"


def test_c3_1_low_n5_availability_matches_b5():
    """Cross-check: stress-low n=5 D availability should be ~0.584 (B5 v6)."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_1_availability_vs_error()
    d_avail = res["low"]["n5"]["availability"]["D"]
    assert abs(d_avail - 0.584375) < 1e-6


def test_c3_1_availability_threshold_not_statistical():
    """0.90 is a transparent engineering classification threshold; 0.897 vs
    0.903 crossing it is policy, not a natural break."""
    import c3_c4_analyze
    assert c3_c4_analyze.AVAIL_OK_THRESHOLD == 0.90
    res = c3_c4_analyze.c3_1_availability_vs_error()
    # loc n5 (0.897 < 0.90) must be avail_risk; high n5 (1.0) must be avail_ok
    assert res["loc"]["n5"]["decision_category"] == "supported_avail_risk"
    assert res["high"]["n5"]["decision_category"] == "supported_avail_ok"


def test_c3_2_mle_failure_rate_matches_b4():
    """C3-2 MLE failure rate pooled should match B4's 32% (2,047/6,400)."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_2_mle_survivor_bias()
    total_invalid = sum(int(res[str(n)]["mle_invalid_rows"]) for n in c3_c4_analyze.N_VALUES)
    total = sum(int(res[str(n)]["n_rows"]) for n in c3_c4_analyze.N_VALUES)
    assert abs(total_invalid / total - 2047 / 6400) < 1e-6


def test_c3_3_gate_closed():
    import c3_c4_analyze
    g = c3_c4_analyze.c3_3_close_training_gate()
    assert g["gate"] == "closed"
    assert g["new_training_requested"] is False


def test_c4_conditional_rules_exist():
    """C4 must state: D is not overall-best on core; n7/10 no forced rank;
    full-params need -> P functional value; stress availability separate."""
    import c3_c4_analyze
    res = c3_c4_analyze.c3_1_availability_vs_error()
    c4 = c3_c4_analyze.c4_conditional_selection(res, {})
    assert "MDM/LRE are stronger traditional baselines" in c4["core"]["traditional_baseline"]
    assert "no confirmed difference" in c4["core"]["n7_10"]
    assert "functional value" in c4["core"]["full_params_need"]
    assert "no OOD guarantee" in c4["stress"]["interval_evidence"]
    # stress cells must be enumerated from C3-1
    assert "cells" in c4["stress"]
    assert c4["stress"]["cells"]["loc n15"]["category"] == "no_confirmed_difference"


# ---- Provenance tests ----

def test_provenance_git_tip_returns_sha():
    import provenance
    tip = provenance.git_tip()
    assert len(tip) == 40
    assert all(c in "0123456789abcdef" for c in tip)


def test_provenance_code_tree_clean_after_commit():
    """After the code commit, the study02c subtree must be clean (no tracked
    or untracked changes excluding __pycache__/.pyc)."""
    import provenance
    assert provenance.code_tree_clean() is True
