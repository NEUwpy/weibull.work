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
            "status", "beta_error", "eta_error", "gamma_error",
            "beta_rel_error", "eta_rel_error", "gamma_rel_error", "extra",
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
            assert "param_standard" in group
            assert "quantile_standard" in group
            assert "diagnostics" in group
            assert "param_distribution" in group["diagnostics"]
            assert "quantile_distribution" in group["diagnostics"]


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


def test_experiment_produces_manifest():
    """run_experiment 输出 manifest.json 且包含必要字段"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=10,
            output_dir=tmpdir,
            code_version="test-v1",
        )
        manifest_path = os.path.join(tmpdir, "manifest.json")
        assert os.path.exists(manifest_path)
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
        assert "methods" in m
        assert "param_grid" in m
        assert "generated_at" in m
        assert m["code_version"] == "test-v1"
        assert m["n_repeats"] == 10
        assert m["total_rows"] == 10
        assert len(m["methods"]) == 1
        assert m["methods"][0]["method_id"] == "mdm"
        assert m["methods"][0]["kwargs"]["offset"] == 0.1
        assert "primary" in m["metrics"]


def test_manifest_seed_namespace():
    """manifest 记录 seed_namespace"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle"],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=3,
            output_dir=tmpdir,
            seed_namespace=42,
        )
        with open(os.path.join(tmpdir, "manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        assert m["seed_namespace"] == 42


def test_mdm_solution_info_in_extra():
    """MDM 行的 extra 列包含 solution_info"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=5,
            output_dir=tmpdir,
        )
        csv_path = os.path.join(tmpdir, "results.csv")
        found_solution_info = False
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["status"] == "success" and row["extra"]:
                    extra = json.loads(row["extra"])
                    if "solution_info" in extra:
                        found_solution_info = True
                        si = extra["solution_info"]
                        assert "solution_strategy" in si
                        assert "target_offset" in si
                        assert si["constraint"] == "gamma >= 0"
                        break
        assert found_solution_info, "未找到包含 solution_info 的 MDM 行"


def test_mdm_small_grid_valid_rate():
    """MDM 在标准小网格上 valid_rate = 100%"""
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = run_experiment(
            methods=[("mdm", {"offset": 0.1})],
            param_grid=[(2.0, 100.0, 5.0), (3.0, 100.0, 0.0)],
            n_values=[20, 30],
            n_repeats=50,
            output_dir=tmpdir,
        )
        for key, group in summary.items():
            assert group["valid_rate"] == 1.0, f"{key}: valid_rate={group['valid_rate']}"


def test_manifest_records_custom_r_levels():
    """manifest.json 记录实际传入的 R_levels 和 diagnostic_R_levels"""
    custom_R = (0.90, 0.95, 0.99)
    custom_diag = (0.50, 0.90, 0.95, 0.99, 0.999)
    with tempfile.TemporaryDirectory() as tmpdir:
        run_experiment(
            methods=["mle"],
            param_grid=[(2.0, 100.0, 5.0)],
            n_values=[20],
            n_repeats=5,
            output_dir=tmpdir,
            R_levels=custom_R,
            diagnostic_R_levels=custom_diag,
        )
        with open(os.path.join(tmpdir, "manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        assert m["metrics"]["R_levels"] == [0.90, 0.95, 0.99]
        assert m["metrics"]["diagnostic_R_levels"] == [0.50, 0.90, 0.95, 0.99, 0.999]
