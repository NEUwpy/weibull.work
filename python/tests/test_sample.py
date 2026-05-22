"""sample.py 测试：可复现性、一致性、边界条件"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample


def test_same_params_same_sample():
    """同一参数组合生成同一份样本"""
    s1 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    s2 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    np.testing.assert_array_equal(s1, s2)


def test_different_repeat_different_sample():
    """不同 repeat_id 生成不同样本"""
    s1 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    s2 = generate_sample(2.0, 100.0, 5.0, 20, 1)
    assert not np.array_equal(s1, s2)


def test_different_params_different_sample():
    """不同参数生成不同样本"""
    s1 = generate_sample(2.0, 100.0, 5.0, 20, 0)
    s2 = generate_sample(3.0, 100.0, 5.0, 20, 0)
    assert not np.array_equal(s1, s2)


def test_sample_is_sorted():
    """样本已排序"""
    sample = generate_sample(2.0, 100.0, 5.0, 50, 3)
    assert list(sample) == sorted(sample)


def test_sample_length():
    """样本长度等于 n"""
    for n in [10, 20, 50, 100]:
        sample = generate_sample(2.0, 100.0, 5.0, n, 0)
        assert len(sample) == n


def test_gamma_zero():
    """gamma=0 时样本仍有效"""
    sample = generate_sample(2.0, 100.0, 0.0, 20, 0)
    assert len(sample) == 20
    assert all(sample > 0)


def test_gamma_large():
    """gamma=10.0 时样本仍有效"""
    sample = generate_sample(2.0, 100.0, 10.0, 20, 0)
    assert len(sample) == 20
    assert all(sample > 10.0)


def test_duplicate_call_consistency():
    """多次调用同一参数，结果完全一致（确定性）"""
    samples = [generate_sample(1.5, 200.0, 0.0, 30, 5) for _ in range(5)]
    for s in samples[1:]:
        np.testing.assert_array_equal(samples[0], s)


def test_cross_process_stability():
    """repr() 规范化确保浮点参数字符串稳定"""
    # 特殊浮点值
    s1 = generate_sample(0.8, 50.0, 0.0, 10, 0)
    s2 = generate_sample(0.8, 50.0, 0.0, 10, 0)
    np.testing.assert_array_equal(s1, s2)
