from pathlib import Path
import sys

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

import analyze_E1_E2_crossfit as crossfit


def _synthetic_scan():
    rows = []
    for beta in [1.5, 2.0]:
        for n in [7, 10]:
            for repeat_id in range(10):
                for delta in [0.0, 0.1, 0.5]:
                    # fold 0 repeats (0, 5) prefer delta=0.5, while the other
                    # eight training repeats prefer delta=0.0. A valid fold-0
                    # selection must therefore be 0.0 and perform poorly on its
                    # untouched holdout.
                    if delta == 0.1:
                        loss = 2.0
                    elif repeat_id % 5 == 0:
                        loss = 100.0 if delta == 0.0 else 0.0
                    else:
                        loss = 0.0 if delta == 0.0 else 1.0
                    rows.append(
                        {
                            "beta": beta,
                            "eta": 1.0,
                            "gamma": 0.1,
                            "gamma_over_eta": 0.1,
                            "n": n,
                            "repeat_id": repeat_id,
                            "delta": delta,
                            "j1_sq": loss,
                        }
                    )
    return pd.DataFrame(rows)


def test_crossfit_selects_on_training_repeats_and_scores_untouched_holdout():
    result = crossfit.run_crossfit(_synthetic_scan(), n_folds=5)

    fold0_l1 = result["selected_deltas"].query("fold == 0 and layer == 'L1'")
    assert len(fold0_l1) == 1
    assert fold0_l1.iloc[0]["delta_star"] == pytest.approx(0.0)

    fold0_l1_metric = result["fold_metrics"].query("fold == 0 and layer == 'L1'")
    assert len(fold0_l1_metric) == 1
    assert fold0_l1_metric.iloc[0]["J1"] == pytest.approx(10.0)

    assert set(result["pooled_metrics"]["layer"]) == {
        "Default",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
    }
    assert "L6" not in set(result["selected_deltas"]["layer"])
    assert "L6" not in set(result["comparison"]["layer"])


def test_crossfit_rejects_an_incomplete_repeat_delta_grid():
    incomplete = _synthetic_scan().drop(index=0)

    with pytest.raises(ValueError, match="complete repeat-by-delta grid"):
        crossfit.validate_scan_contract(incomplete)


def test_formal_crossfit_artifact_contract():
    output_dir = (
        REPO_ROOT
        / "Study"
        / "01-study-MDM最小偏移量优化研究"
        / "artifacts"
        / "formal"
        / "E1_E2_crossfit"
    )
    required = {
        "manifest.json",
        "summary.json",
        "results.csv",
        "fold_metrics.csv",
        "model_comparison.csv",
        "by_n_metrics.csv",
        "selected_deltas.csv",
        "selection_stability.csv",
        "comparison_vs_same_sample.csv",
        "crossfit_report.md",
    }
    assert required.issubset({path.name for path in output_dir.iterdir()})

    fold_metrics = pd.read_csv(output_dir / "fold_metrics.csv")
    assert len(fold_metrics) == 30
    assert set(fold_metrics["fold"]) == set(range(5))
    assert set(fold_metrics["layer"]) == {
        "Default",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
    }
    assert set(fold_metrics["n_holdout_samples"]) == {9000}

    selections = pd.read_csv(output_dir / "selected_deltas.csv")
    assert "L6" not in set(selections["layer"])
    assert selections.query("layer == 'L1'")["delta_star"].tolist() == [0.08] * 5
