"""Unit tests for the D7 selection-rule inference (evaluation.py).

Pure-Python, no torch/frozen-config: locks the frozen two-level bootstrap
(seed 520001, 2000 reps) to be deterministic and order-independent, the
global-better three-CI verdict, the smallest-within-2%-CI training-size rule,
and per-sample evaluation self-consistency. These are the rule-engine invariants
the selection engine builds on; the integrative DecisionSpec/trace tests live in
``test_study02a_formal_selection.py``.
"""

from __future__ import annotations

import sys

import pytest


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"))

from study02a.evaluation import (  # noqa: E402
    evaluate_rows_per_sample,
    global_better_intervals,
    paired_two_level_bootstrap_ci,
    smallest_within_2pct_ci_choice,
)


def _record(sample_id, seed, point, l_param, *, legal=True):
    return {
        "sample_id": sample_id, "seed_id": str(seed), "point_id": point,
        "legal": legal, "failure": 0 if legal else 1, "l_param": float(l_param),
        "e_beta": float(l_param), "e_eta": float(l_param), "e_gamma": float(l_param),
    }


def _grid(seeds, points, samples_per_point, delta):
    """3 candidates' worth of synthetic per-(seed,sample) records; delta shifts l_param."""
    records = []
    for seed in seeds:
        for p in points:
            for s in range(samples_per_point):
                records.append(_record(f"{p}:s{s}", seed, p, 0.1 + delta + (seed % 7) * 0.001 + s * 0.0001))
    return records


SEEDS = [420101, 420102, 420103]
POINTS = ["pt0", "pt1", "pt2"]


def test_paired_bootstrap_is_deterministic():
    paired_a = _grid(SEEDS, POINTS, 2, 0.0)
    paired_b = _grid(SEEDS, POINTS, 2, 0.05)
    diff = [
        {"seed_id": str(r["seed_id"]), "sample_id": r["sample_id"], "point_id": r["point_id"],
         "improvement": paired_b[i]["l_param"] - paired_a[i]["l_param"]}
        for i, r in enumerate(paired_a)
    ]
    ci1 = paired_two_level_bootstrap_ci(diff)
    ci2 = paired_two_level_bootstrap_ci(diff)
    assert ci1 == ci2
    # improvement ~0.05 everywhere => CI excludes 0 and straddles 0.05
    assert ci1["ci_lower"] > 0
    assert ci1["ci_lower"] == pytest.approx(0.05, abs=2e-6)
    assert ci1["ci_upper"] == pytest.approx(0.05, abs=2e-6)


def test_paired_bootstrap_is_order_independent():
    paired_a = _grid(SEEDS, POINTS, 2, 0.0)
    paired_b = _grid(SEEDS, POINTS, 2, 0.05)
    diff = [
        {"seed_id": str(r["seed_id"]), "sample_id": r["sample_id"], "point_id": r["point_id"],
         "improvement": paired_b[i]["l_param"] - paired_a[i]["l_param"]}
        for i, r in enumerate(paired_a)
    ]
    import random
    shuffled = random.Random(123).sample(diff, len(diff))
    assert paired_two_level_bootstrap_ci(diff) == paired_two_level_bootstrap_ci(shuffled)


def test_paired_bootstrap_requires_two_point_clusters():
    one_point = [
        {"seed_id": "420101", "sample_id": "s0", "point_id": "only", "improvement": 0.1},
        {"seed_id": "420102", "sample_id": "s1", "point_id": "only", "improvement": 0.2},
    ]
    with pytest.raises(ValueError, match="two parameter-point"):
        paired_two_level_bootstrap_ci(one_point)


def test_paired_bootstrap_rejects_incomplete_grid():
    # missing one (seed, sample) cell => not a complete rectangular grid
    paired = [
        {"seed_id": "420101", "sample_id": "s0", "point_id": "pt0", "improvement": 0.1},
        {"seed_id": "420101", "sample_id": "s1", "point_id": "pt1", "improvement": 0.1},
        {"seed_id": "420102", "sample_id": "s0", "point_id": "pt0", "improvement": 0.1},
        # (420102, s1) missing
    ]
    with pytest.raises(ValueError, match="every \\(seed, sample\\)"):
        paired_two_level_bootstrap_ci(paired)


def test_global_better_verdict_and_intervals():
    candidate = _grid(SEEDS, POINTS, 2, 0.0)   # better (lower l_param)
    comparator = _grid(SEEDS, POINTS, 2, 0.05)
    result = global_better_intervals(candidate=candidate, comparator=comparator)
    assert result["verdict"] == "globally_better"
    assert result["bootstrap_config"] == {"seed": 520001, "replicates": 2000}
    assert result["failure_rate_ci"]["ci_upper"] == 0  # both fully legal
    assert result["l_param_ci"]["ci_lower"] > 0
    # R3#4: relative RMSE ratio CI upper (RMSE_cand/RMSE_comp - 1) <= 5% per component
    assert all(ci["ci_upper"] <= 0.05 for ci in result["component_rmse_ratio_ci"].values())


def test_global_better_uses_relative_rmse_ratio_not_raw_mse_scale_counterexample():
    """R3#4 + attack: raw MSE difference and relative RMSE can disagree. The protocol
    uses the scale-free RELATIVE ratio; a candidate whose errors are a large constant
    offset vs a tiny comparator error worsens on the ratio even when the raw squared
    difference looks small in absolute terms. Build a case where the candidate has a
    small constant relative worsening on a component and confirm the ratio CI reflects it."""
    # comparator e_beta ~ 0.001 (tiny), candidate e_beta ~ 0.002 (double => ratio-1 = 1.0, >> 5%).
    # Raw MSE diff (cand^2 - comp^2) ~ 3e-6 (looks tiny); relative ratio = 1.0 (clearly worsens).
    rng_points = 3
    records_c = []
    records_o = []
    for seed in SEEDS:
        for p in range(rng_points):
            for s in range(2):
                sid = f"pt{p}:s{s}"
                records_c.append({"sample_id": sid, "seed_id": str(seed), "point_id": f"pt{p}",
                                  "legal": True, "failure": 0, "l_param": 0.001,
                                  "e_beta": 0.002, "e_eta": 0.001, "e_gamma": 0.001})
                records_o.append({"sample_id": sid, "seed_id": str(seed), "point_id": f"pt{p}",
                                  "legal": True, "failure": 0, "l_param": 0.001,
                                  "e_beta": 0.001, "e_eta": 0.001, "e_gamma": 0.001})
    result = global_better_intervals(candidate=records_c, comparator=records_o)
    # beta RMSE ratio-1 = 1.0 (100% worsening) => upper >> 0.05 => NOT globally better
    assert result["component_rmse_ratio_ci"]["beta"]["ci_upper"] > 0.05
    assert result["verdict"] != "globally_better"


def test_global_better_zero_comparator_rmse_is_fail_closed():
    """R3#4: when comparator RMSE is exactly 0 and the candidate has any error, the
    component ratio is +inf (fail-closed) => candidate cannot be 'globally better'."""
    records_c = []
    records_o = []
    for seed in SEEDS:
        for p in range(3):
            for s in range(2):
                sid = f"pt{p}:s{s}"
                records_c.append({"sample_id": sid, "seed_id": str(seed), "point_id": f"pt{p}",
                                  "legal": True, "failure": 0, "l_param": 0.001,
                                  "e_beta": 0.01, "e_eta": 0.0, "e_gamma": 0.0})  # candidate has beta error
                records_o.append({"sample_id": sid, "seed_id": str(seed), "point_id": f"pt{p}",
                                  "legal": True, "failure": 0, "l_param": 0.001,
                                  "e_beta": 0.0, "e_eta": 0.0, "e_gamma": 0.0})  # comparator perfect on beta
    result = global_better_intervals(candidate=records_c, comparator=records_o)
    assert result["component_rmse_ratio_ci"]["beta"]["ci_upper"] == float("inf")
    assert result["verdict"] != "globally_better"


def test_validate_point_records_rejects_duplicate_and_inconsistent_point():
    from study02a.evaluation import validate_point_records
    base = [{"sample_id": "s0", "seed_id": "1", "point_id": "pt0", "l_param": 0.1}]
    dup = base + [{"sample_id": "s0", "seed_id": "1", "point_id": "pt0", "l_param": 0.2}]
    with pytest.raises(ValueError, match="duplicate"):
        validate_point_records(dup)
    cross_point = [
        {"sample_id": "s0", "seed_id": "1", "point_id": "pt0", "l_param": 0.1},
        {"sample_id": "s0", "seed_id": "2", "point_id": "pt1", "l_param": 0.1},
    ]
    with pytest.raises(ValueError, match="multiple parameter points"):
        validate_point_records(cross_point)


def test_global_better_rejects_mismatched_sample_sets():
    candidate = _grid(SEEDS, POINTS, 2, 0.0)
    comparator = _grid(SEEDS, POINTS, 2, 0.05)[1:]  # drop one sample
    with pytest.raises(ValueError, match="identical \\(seed_id, sample_id\\)"):
        global_better_intervals(candidate=candidate, comparator=comparator)


def test_evidence_tampering_changes_intervals():
    candidate = _grid(SEEDS, POINTS, 2, 0.0)
    comparator = _grid(SEEDS, POINTS, 2, 0.05)
    baseline = global_better_intervals(candidate=candidate, comparator=comparator)
    tampered = [{**r, "l_param": r["l_param"] + 0.5, "e_beta": r["e_beta"] + 0.5,
                 "e_eta": r["e_eta"] + 0.5, "e_gamma": r["e_gamma"] + 0.5} for r in candidate]
    changed = global_better_intervals(candidate=tampered, comparator=comparator)
    assert changed["l_param_ci"] != baseline["l_param_ci"]


def test_smallest_within_2pct_ci_picks_best_when_smaller_is_statistically_worse():
    # 25000 is within 2% of best (0.100) but strictly worse => CI of (best-cand) < 0
    scores = {"7000": 0.100, "25000": 0.1015, "100000": 0.130, "400000": 0.200}
    paired = {
        "25000": [
            {"seed_id": str(s), "sample_id": f"pt{p}:s{k}", "point_id": f"pt{p}",
             "improvement": 0.100 - 0.1015}
            for s in SEEDS for p in range(3) for k in range(2)
        ],
    }
    assert smallest_within_2pct_ci_choice(candidate_scores=scores, candidate_paired=paired) == "7000"


def test_smallest_within_2pct_ci_picks_smaller_nonbest_when_ci_contains_zero():
    # best is the larger size (0.100); the smaller size (0.101) is within 2% and its paired
    # improvement vs best straddles 0 (not statistically worse) => prefer the smaller size.
    scores = {"7000": 0.101, "25000": 0.100}
    improvements = []
    sign = 1
    for s in SEEDS:
        for p in range(3):
            for k in range(2):
                improvements.append({
                    "seed_id": str(s), "sample_id": f"pt{p}:s{k}", "point_id": f"pt{p}",
                    "improvement": 0.01 * sign,
                })
                sign *= -1
    paired = {"7000": improvements}
    assert smallest_within_2pct_ci_choice(candidate_scores=scores, candidate_paired=paired) == "7000"


def test_smallest_within_2pct_ci_falls_back_to_best_when_all_outside_band():
    scores = {"7000": 0.100, "25000": 0.200, "100000": 0.300, "400000": 0.400}
    # nothing within 2% of 0.100 except best
    assert smallest_within_2pct_ci_choice(candidate_scores=scores, candidate_paired={}) == "7000"


def test_evaluate_rows_per_sample_is_self_consistent_for_illegal():
    illegal = [{
        "sample_id": "s0", "seed_id": "420101", "point_id": "pt0",
        "beta_hat": float("nan"), "eta_hat": 1.0, "gamma_hat": 0.0,
        "beta": 1.0, "eta": 1.0, "gamma": 0.0, "sample_min": 1.0,
    }]
    records = evaluate_rows_per_sample(illegal, failure_penalty=10.0)
    rec = records[0]
    assert rec["legal"] is False
    assert rec["failure"] == 1
    # component errors = penalty each => L_param = sqrt((3*penalty^2)/3) = penalty
    assert rec["l_param"] == pytest.approx(10.0)
    import math
    expected = math.sqrt((rec["e_beta"] ** 2 + rec["e_eta"] ** 2 + rec["e_gamma"] ** 2) / 3.0)
    assert rec["l_param"] == pytest.approx(expected)


def test_evaluate_rows_per_sample_requires_pairing_metadata():
    with pytest.raises(ValueError, match="seed_id"):
        evaluate_rows_per_sample([{
            "sample_id": "s0", "point_id": "pt0",
            "beta_hat": 1.0, "eta_hat": 1.0, "gamma_hat": 0.0,
            "beta": 1.0, "eta": 1.0, "gamma": 0.0, "sample_min": 1.0,
        }])
