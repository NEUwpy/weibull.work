import importlib.util
import math
import sys
import tempfile
from pathlib import Path

import pandas as pd


def load_e3a_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = next((repo_root / "Study").glob("01-study-MDM*/code/run_E3a.py"))
    sys.path.insert(0, str(script_path.parent))
    sys.path.insert(0, str(repo_root / "python"))
    spec = importlib.util.spec_from_file_location("study01_run_E3a", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiny_curve_frame():
    rows = []
    for repeat_id, losses in [
        (0, {0.0: 4.0, 0.1: 1.0}),
        (1, {0.0: 0.25, 0.1: 9.0}),
    ]:
        for delta, loss in losses.items():
            rows.append(
                {
                    "beta": 1.5,
                    "eta": 1.0,
                    "gamma": 0.1,
                    "gamma_over_eta": 0.1,
                    "n": 7,
                    "repeat_id": repeat_id,
                    "delta": delta,
                    "loss_filled": loss,
                    "is_valid": True,
                }
            )
    return pd.DataFrame(rows)


def test_reference_selection_keeps_sample_rows_for_pooled_baselines():
    e3a = load_e3a_module()
    result = e3a.evaluate_reference_selection(
        tiny_curve_frame(), "Default", lambda _sample: 0.1
    )

    assert "df_sel" in result
    assert len(result["df_sel"]) == 2
    assert result["n_samples"] == 2


def test_l6_hindsight_selects_best_true_loss_per_sample():
    e3a = load_e3a_module()
    result = e3a.evaluate_l6_hindsight_selection(tiny_curve_frame())

    selected = {
        int(row.repeat_id): float(row.selected_delta)
        for row in result["df_sel"].itertuples(index=False)
    }
    assert result["model"] == "L6-hindsight"
    assert selected == {0: 0.1, 1: 0.0}
    assert result["J1"] == math.sqrt((1.0 + 0.25) / 2.0)


def test_acceptance_report_writer_creates_markdown(tmp_path):
    e3a = load_e3a_module()
    report_path = e3a.write_acceptance_report(
        output_dir=tmp_path,
        data_integrity={
            "expected_rows": 4,
            "actual_rows": 4,
            "duplicate_rows": 0,
            "unique_combos": 1,
            "delta_points": 2,
            "non_success_rate": 0.0,
        },
        combo_agg=[
            {
                "model": "L2",
                "J1": 2.0,
                "failure_rate": 0.0,
                "n_samples": 2,
                "per_n": {7: {"J1": 2.0, "failure_rate": 0.0, "count": 2}},
            },
            {
                "model": "NN-RC-L6",
                "J1": 1.5,
                "failure_rate": 0.0,
                "n_samples": 2,
                "per_n": {7: {"J1": 1.5, "failure_rate": 0.0, "count": 2}},
            },
        ],
        random_results=[],
        split_rows=[{"fold": "fold_1", "test_beta": 1.5}],
        decision="APPROVE",
        decision_reasons=["NN-RC-L6 improves pooled J1 over L2."],
    )

    text = Path(report_path).read_text(encoding="utf-8")
    assert "APPROVE" in text
    assert "NN-RC-L6" in text


def test_fit_row_cap_keeps_complete_delta_curves():
    e3a = load_e3a_module()
    df = tiny_curve_frame()
    capped = e3a.select_fit_rows(df, sample_cap=1, random_state=0)

    assert capped["repeat_id"].nunique() == 1
    assert sorted(capped["delta"].tolist()) == [0.0, 0.1]


def test_combo_split_holds_out_full_combos_once_without_beta_blocks():
    e3a = load_e3a_module()
    folds = e3a.get_combo_split()
    all_test_combos = [combo for fold in folds for combo in fold["test_combos"]]

    assert len(folds) == 5
    assert len(all_test_combos) == len(set(all_test_combos)) == 45
    for fold in folds:
        assert len(fold["test_combos"]) == 9
        assert not set(fold["train_combos"]) & set(fold["test_combos"])
        assert len({combo[0] for combo in fold["test_combos"]}) > 1


if __name__ == "__main__":
    test_reference_selection_keeps_sample_rows_for_pooled_baselines()
    test_l6_hindsight_selects_best_true_loss_per_sample()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_acceptance_report_writer_creates_markdown(Path(tmpdir))
    test_fit_row_cap_keeps_complete_delta_curves()
    test_combo_split_holds_out_full_combos_once_without_beta_blocks()
