"""Regression tests for Study01 E4 subset cost-report updates."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
E4_SCRIPT = (
    PROJECT_ROOT
    / "Study"
    / "01-study-MDM最小偏移量优化研究"
    / "code"
    / "run_E4_formal_validation.py"
)


def load_e4_module():
    spec = importlib.util.spec_from_file_location(
        "study01_e4_formal_validation_cost_test", E4_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_boundary_subset_replaces_only_boundary_costs_and_is_idempotent(tmp_path):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"
    original = pd.DataFrame([
        {"track": "E4a", "elapsed_s": 100.0, "note": "feature ablation"},
        {"track": "E4a", "elapsed_s": 10.0, "fold": "combo_fold_1"},
        {"track": "E4b", "elapsed_s": 20.0, "note": "old boundary"},
        {"track": "E4d", "elapsed_s": 40.0, "note": "selector"},
    ])
    original.to_csv(cost_path, index=False)
    replacement = [{
        "track": "E4b",
        "elapsed_s": 21.0,
        "note": "new boundary",
    }]

    first = module.write_merged_cost_report(cost_path, replacement, {"e4b"})
    second = module.write_merged_cost_report(cost_path, replacement, {"e4b"})

    assert list(second["track"]) == ["E4a", "E4a", "E4d", "E4b"]
    assert second.loc[second["track"] == "E4b", "note"].tolist() == [
        "new boundary"
    ]
    assert second.loc[second["track"] == "E4a", "elapsed_s"].tolist() == [
        100.0,
        10.0,
    ]
    assert second.loc[second["track"] == "E4d", "elapsed_s"].tolist() == [40.0]
    assert_frame_equal(first, second)


def test_offgrid_subset_preserves_prior_boundary_and_other_track_costs(tmp_path):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"
    pd.DataFrame([
        {"track": "E4a", "elapsed_s": 100.0, "note": "feature ablation"},
        {"track": "E4b", "elapsed_s": 21.0, "note": "boundary"},
        {"track": "E4c", "elapsed_s": 30.0, "note": "old offgrid"},
        {"track": "E4d", "elapsed_s": 40.0, "note": "selector"},
    ]).to_csv(cost_path, index=False)

    merged = module.write_merged_cost_report(
        cost_path,
        [{"track": "E4c", "elapsed_s": 31.0, "note": "new offgrid"}],
        {"e4c"},
    )

    assert list(merged["track"]) == ["E4a", "E4b", "E4d", "E4c"]
    assert merged.loc[merged["track"] == "E4b", "elapsed_s"].tolist() == [21.0]
    assert merged.loc[merged["track"] == "E4c", "note"].tolist() == [
        "new offgrid"
    ]


def test_first_empty_write_is_readable_and_can_be_recovered(tmp_path):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"

    empty = module.write_merged_cost_report(cost_path, [], {"e4d"})

    assert list(empty.columns) == ["track"]
    assert pd.read_csv(cost_path).empty
    recovered = module.write_merged_cost_report(
        cost_path,
        [{"track": "E4d", "elapsed_s": 40.0, "note": "selector"}],
        {"e4d"},
    )
    assert recovered.to_dict("records") == [{
        "track": "E4d",
        "elapsed_s": 40.0,
        "note": "selector",
    }]


def test_existing_truly_empty_csv_can_be_recovered(tmp_path):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"
    cost_path.write_text("")

    recovered = module.write_merged_cost_report(
        cost_path,
        [{"track": "E4b", "elapsed_s": 21.0, "note": "boundary"}],
        {"e4b"},
    )

    assert recovered.to_dict("records") == [{
        "track": "E4b",
        "elapsed_s": 21.0,
        "note": "boundary",
    }]
    assert pd.read_csv(cost_path).to_dict("records") == recovered.to_dict("records")


@pytest.mark.parametrize(
    "new_rows",
    [
        [{"track": "E4c", "elapsed_s": 31.0}],
        [{"elapsed_s": 21.0}],
        [{"track": "", "elapsed_s": 21.0}],
        [{"track": "   ", "elapsed_s": 21.0}],
        [{"track": None, "elapsed_s": 21.0}],
    ],
    ids=["unrequested", "missing", "empty", "whitespace", "null"],
)
def test_invalid_new_track_is_rejected_without_touching_report(tmp_path, new_rows):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"
    original = "track,elapsed_s,note\nE4a,100.0,feature ablation\n"
    cost_path.write_text(original)

    with pytest.raises(ValueError, match="track"):
        module.write_merged_cost_report(cost_path, new_rows, {"e4b"})

    assert cost_path.read_text() == original


def test_multiple_requested_tracks_replace_together_and_preserve_others(tmp_path):
    module = load_e4_module()
    cost_path = tmp_path / "cost_report.csv"
    pd.DataFrame([
        {"track": "E4a", "elapsed_s": 100.0, "note": "feature ablation"},
        {"track": "E4b", "elapsed_s": 20.0, "note": "old boundary"},
        {"track": "E4c", "elapsed_s": 30.0, "note": "old offgrid"},
        {"track": "E4d", "elapsed_s": 40.0, "note": "selector"},
    ]).to_csv(cost_path, index=False)

    merged = module.write_merged_cost_report(
        cost_path,
        [
            {"track": "E4b", "elapsed_s": 21.0, "note": "new boundary"},
            {"track": "E4c", "elapsed_s": 31.0, "note": "new offgrid"},
        ],
        {"e4b", "e4c"},
    )

    assert list(merged["track"]) == ["E4a", "E4d", "E4b", "E4c"]
    assert merged.loc[merged["track"] == "E4a", "elapsed_s"].tolist() == [100.0]
    assert merged.loc[merged["track"] == "E4d", "elapsed_s"].tolist() == [40.0]
    assert merged.loc[merged["track"] == "E4b", "note"].tolist() == [
        "new boundary"
    ]
    assert merged.loc[merged["track"] == "E4c", "note"].tolist() == [
        "new offgrid"
    ]
