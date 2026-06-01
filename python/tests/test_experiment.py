"""experiment.py 测试：小规模端到端验证"""

import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.experiment import run_experiment
from studies.common.sample import generate_sample


def test_end_to_end_creates_files():
    """运行实验后 CSV 和 JSON 文件存在"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle", ("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=5,
            output_dir=tmpdir,
        )
        assert os.path.exists(os.path.join(tmpdir, "results.csv"))
        assert os.path.exists(os.path.join(tmpdir, "summary.json"))


def test_csv_row_count():
    """CSV 行数 = 参数组合 × n_values × n_repeats × 方法数"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle", ("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0), (3.0, 100.0, 0.0)],
            n_values=[20],
            n_repeats=10,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # 2 param combos × 1 n × 10 repeats × 2 methods = 40
        assert len(rows) == 40


def test_csv_columns():
    """CSV 包含所有必要列"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle"],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=3,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        expected_cols = {
            "beta", "eta", "gamma", "n", "repeat_id",
            "method_id", "method_variant",
            "beta_hat", "eta_hat", "gamma_hat",
            "r_squared", "converged", "time",
            "status", "beta_rel_error", "eta_rel_error", "gamma_rel_error", "extra",
        }
        assert set(rows[0].keys()) == expected_cols


def test_status_values():
    """status 列只包含 success/failure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle", ("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=20,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            statuses = [row["status"] for row in reader]
        assert all(s in ("success", "failure") for s in statuses)


def test_json_summary_counts():
    """JSON 汇总中 failure + valid = total"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle"],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=10,
            output_dir=tmpdir,
        )
        json_path = os.path.join(tmpdir, "summary.json")
        with open(json_path, encoding="utf-8") as f:
            summary = json.load(f)
        for key, group in summary.items():
            assert group["n_failure"] + group["n_valid"] == group["n_total"]
            assert "param_distribution" in group
            assert "quantile_distribution" in group


def test_variant_in_summary():
    """不同 method_variant 在 JSON 汇总中分别统计"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=[
                ("mdm", {"offset": 0.3, "variant": "mdm_o0.3"}),
                ("mdm", {"offset": 0.5, "variant": "mdm_o0.5"}),
            ],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=10,
            output_dir=tmpdir,
        )
        json_path = os.path.join(tmpdir, "summary.json")
        with open(json_path, encoding="utf-8") as f:
            summary = json.load(f)
        variants = {g["method_variant"] for g in summary.values()}
        assert "mdm_o0.3" in variants
        assert "mdm_o0.5" in variants


def test_shared_sample_evidence():
    """同一 repeat_id 下不同方法共享同一样本（间接验证）"""
    # 生成两个样本，确认同一 repeat_id 的样本一致
    s1 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    s2 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    import numpy as np
    np.testing.assert_array_equal(s1, s2)


def test_success_rows_record_relative_errors():
    """success 行记录 S2R 参数相对误差"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle"],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=50,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["status"] == "success":
                    assert row["beta_rel_error"] != "" and row["beta_rel_error"] != "nan"
                    assert row["eta_rel_error"] != "" and row["eta_rel_error"] != "nan"
                    assert row["gamma_rel_error"] != "" and row["gamma_rel_error"] != "nan"
