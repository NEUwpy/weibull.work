"""S4.9 默认 MDM：离散搜索、边界截断与 trace 一致性测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.mdm import MDM
from studies.common.sample import generate_sample


def test_default_mdm_truncates_negative_offset_root_to_zero():
    """已知旧版 no_intersection 样本应返回 gamma=0 边界截断解。"""
    sample = generate_sample(1.5, 100.0, 0.0, 10, 1)

    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(trace=True, offset=0.1, gamma_steps=20)

    assert status is True
    assert beta is not None and beta > 0
    assert eta is not None and eta > 0
    assert gamma == 0.0
    assert r2 is not None

    trace = mdm.trace_data
    assert trace["solution_strategy"] == "truncated_at_zero"
    assert trace["constraint"] == "gamma >= 0"
    assert trace["gamma_steps"] == 20
    assert trace["optimal_gamma"] == 0.0
    assert len(trace["grad_gamma_curve"]) == 20
    assert trace["probe_gradient_at_zero"] > trace["target_offset"]


def test_default_mdm_trace_records_discrete_offset_root_bracket():
    """有交点样本应由离散梯度曲线插值得到最优 gamma。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)

    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(trace=True, offset=0.1, gamma_steps=30)

    assert status is True
    assert beta is not None and beta > 0
    assert eta is not None and eta > 0
    assert gamma is not None and gamma > 0
    assert r2 is not None

    trace = mdm.trace_data
    assert trace["search_strategy"] == "geometric_from_tmin"
    assert trace["solution_strategy"] == "offset_root"
    assert trace["gamma_steps"] == 30
    assert len(trace["grad_gamma_curve"]) == 30

    bracket = trace["root_bracket"]
    assert bracket is not None
    left = bracket["left"]
    right = bracket["right"]
    assert min(left["gamma"], right["gamma"]) <= gamma <= max(left["gamma"], right["gamma"])
    assert (left["gradient"] - trace["target_offset"]) * (
        right["gradient"] - trace["target_offset"]
    ) <= 0
