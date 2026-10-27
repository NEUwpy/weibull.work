"""
统一样本生成模块

供蒙特卡洛框架调用，保证同一参数组合 + 样本量 + 重复编号生成同一份样本。
种子使用 hashlib.sha256 + repr() 规范化，不依赖 Python 内置 hash()。

规范来源：AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划 第 3.2 节
"""

import hashlib
from typing import Optional

import numpy as np


def generate_sample(beta: float, eta: float, gamma: float,
                    n: int, repeat_id: int,
                    seed: Optional[int] = None) -> np.ndarray:
    """生成确定性可复现的三参数威布尔样本。

    种子由 (beta, eta, gamma, n, repeat_id) 唯一确定，
    可选 seed 作为命名空间；不依赖方法 ID，不同方法共享同一份样本，
    支持配对比较。

    Args:
        beta: 形状参数 (>0)
        eta: 尺度参数 (>0)
        gamma: 位置参数
        n: 样本量
        repeat_id: 重复编号 (>=0)
        seed: 可选随机种子命名空间；为 None 时保持历史样本序列

    Returns:
        np.ndarray，已排序，长度为 n
    """
    if seed is None:
        seed_str = f"{repr(beta)}|{repr(eta)}|{repr(gamma)}|{n}|{repeat_id}"
    else:
        seed_str = f"{repr(seed)}|{repr(beta)}|{repr(eta)}|{repr(gamma)}|{n}|{repeat_id}"
    seed_bytes = hashlib.sha256(seed_str.encode()).digest()[:4]
    seed_int = int.from_bytes(seed_bytes, byteorder="big")

    rng = np.random.default_rng(seed_int)
    u = rng.uniform(0, 1, size=n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)
    return np.sort(sample)
