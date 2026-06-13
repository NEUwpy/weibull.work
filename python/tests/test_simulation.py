"""simulation.py 测试：API 与研究脚本共享同一蒙特卡洛核心。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.simulation import aggregate_simulation_rows, iter_batch_rows, simulate_method


def test_generate_sample_accepts_optional_seed_namespace():
    """同一 seed 命名空间内样本可复现，不同 seed 生成不同样本。"""
    s1 = generate_sample(2.0, 100.0, 5.0, 20, 1, seed=42)
    s2 = generate_sample(2.0, 100.0, 5.0, 20, 1, seed=42)
    s3 = generate_sample(2.0, 100.0, 5.0, 20, 1, seed=43)

    assert (s1 == s2).all()
    assert not (s1 == s3).all()


def test_simulate_method_uses_common_sample_and_runner():
    """单方法蒙特卡洛复用 generate_sample + run_method 的结果。"""
    rows = simulate_method(
        method_id="mle",
        beta=2.0,
        eta=100.0,
        gamma=5.0,
        n=20,
        rep=2,
        seed=42,
    )

    sample = generate_sample(2.0, 100.0, 5.0, 20, 1, seed=42)
    expected = run_method("mle", sample)

    assert len(rows) == 2
    assert rows[0]["sim_id"] == 1
    assert rows[0]["beta_true"] == 2.0
    assert rows[0]["eta_true"] == 100.0
    assert rows[0]["gamma"] == 5.0
    assert rows[0]["sample_size"] == 20
    assert rows[0]["est_beta"] == pytest.approx(expected["beta_hat"])
    assert rows[0]["r_squared"] == pytest.approx(expected["r_squared"])
    assert rows[0]["method_id"] == "mle"
    assert rows[0]["converged"] is True
    assert rows[0]["time"] >= 0
    assert rows[0]["sample_min"] == pytest.approx(float(min(sample)))


def test_simulate_method_applies_default_mdm_offset():
    """MDM 蒙特卡洛默认使用 API 约定的 offset=0.1。"""
    rows = simulate_method(
        method_id="mdm",
        beta=2.0,
        eta=100.0,
        gamma=5.0,
        n=20,
        rep=1,
        seed=42,
    )

    assert rows[0]["offset_value"] == 0.1
    assert rows[0]["est_beta"] is not None


def test_aggregate_simulation_rows_returns_standard_metrics():
    rows = simulate_method(
        method_id="mle",
        beta=2.0,
        eta=100.0,
        gamma=5.0,
        n=20,
        rep=3,
        seed=42,
    )

    metrics = aggregate_simulation_rows(rows)

    assert metrics["n_total"] == 3
    assert "param_standard" in metrics
    assert "quantile_standard" in metrics
    assert "diagnostics" in metrics


def test_iter_batch_rows_keeps_batch_csv_shape():
    """批量模拟输出保持 main.py 下载 CSV 需要的字段。"""
    rows = list(iter_batch_rows(
        method_id="mle",
        true_beta=2.0,
        true_eta=100.0,
        true_gamma=5.0,
        sample_sizes=[10, 20],
        beta_values=None,
        offset_values=None,
        num_simulations=2,
    ))

    assert len(rows) == 4
    assert set(rows[0]) == {
        "beta_true",
        "eta_true",
        "gamma_true",
        "sample_size",
        "sim_id",
        "est_beta",
        "est_eta",
        "est_gamma",
        "bias_beta",
        "bias_eta",
        "bias_gamma",
        "r_squared",
    }
