from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

import analyze_beta_profile_audit as audit


def test_build_design_has_exact_300_unique_samples():
    design = audit.build_design()

    assert len(design) == 300
    assert set(design["beta"]) == {1.5, 2.0, 2.5, 4.0, 5.0}
    assert set(design["n"]) == {7, 10, 20}
    assert design["repeat_id"].min() == 0
    assert design["repeat_id"].max() == 19
    assert not design.duplicated(["beta", "n", "repeat_id"]).any()


def test_interpolate_gradient_brackets_true_gamma():
    points = [
        {"gamma": 0.8, "gradient": 0.4},
        {"gamma": 0.2, "gradient": 0.1},
    ]

    assert audit.interpolate_gradient(points, 0.5) == pytest.approx(0.25)


def test_interpolate_gradient_rejects_out_of_range_target():
    points = [
        {"gamma": 0.8, "gradient": 0.4},
        {"gamma": 0.2, "gradient": 0.1},
    ]

    with pytest.raises(ValueError, match="outside"):
        audit.interpolate_gradient(points, 0.9)


def test_local_gradient_slope_uses_nearest_seven_nonvirtual_points():
    points = [
        {
            "gamma": float(gamma),
            "gradient": 2.0 * gamma + 1.0,
            "virtual": gamma == 9,
        }
        for gamma in range(10)
    ]

    assert audit.local_gradient_slope(
        points, target_gamma=4.0, k=7
    ) == pytest.approx(2.0)


def test_direction_consistency_requires_three_same_nonzero_signs():
    assert audit.direction_consistent([0.4, 0.2, 0.1])
    assert audit.direction_consistent([-0.4, -0.2, -0.1])
    assert not audit.direction_consistent([0.4, -0.2, 0.1])
    assert not audit.direction_consistent([0.4, 0.0, 0.1])
    assert not audit.direction_consistent([0.4, 0.2])


def test_extract_one_real_trace_has_finite_contract_fields():
    row = audit.build_design().iloc[0].to_dict()

    result = audit.extract_sample_metrics(row)

    for name in audit.METRIC_COLS:
        assert np.isfinite(result[name])
    assert result["solution_strategy"] in {"truncated_at_zero", "brent_root"}


def test_compute_trends_reports_each_n_and_pooled():
    frame = pd.DataFrame(
        {
            "beta": [1.5, 2.0, 2.5, 4.0, 5.0] * 3,
            "n": np.repeat([7, 10, 20], 5),
            "gradient_at_zero": [1, 2, 3, 4, 5] * 3,
        }
    )

    trends = audit.compute_trends(frame, ["gradient_at_zero"])

    assert set(trends["scope"]) == {"n=7", "n=10", "n=20", "pooled"}
    assert trends.query("scope != 'pooled'")["spearman_rho"].tolist() == pytest.approx(
        [1.0, 1.0, 1.0]
    )


def test_formal_artifact_contract():
    output_dir = STUDY_ROOT / "artifacts" / "formal" / "E2_beta_profile_audit"
    required = {
        "profile_metrics.csv",
        "by_beta_n.csv",
        "trend_summary.csv",
        "summary.json",
        "manifest.json",
    }
    assert output_dir.is_dir()
    assert required.issubset({path.name for path in output_dir.iterdir()})

    metrics = pd.read_csv(output_dir / "profile_metrics.csv")
    by_beta_n = pd.read_csv(output_dir / "by_beta_n.csv")
    trends = pd.read_csv(output_dir / "trend_summary.csv")
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert len(metrics) == 300
    assert not metrics.duplicated(["beta", "n", "repeat_id"]).any()
    assert len(by_beta_n) == 15
    assert set(trends["scope"]) == {"n=7", "n=10", "n=20", "pooled"}
    assert trends.groupby("metric")["scope"].nunique().eq(4).all()
    assert summary["evidence_boundary"]["causal_claim_allowed"] is False
