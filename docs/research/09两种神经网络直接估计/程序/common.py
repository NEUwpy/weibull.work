"""
09研究公共模块
- 数据生成：从参数空间采样真值，生成Weibull失效样本
- 特征提取：从样本计算统计特征向量
- 评价指标：参数误差、工程寿命误差
"""

import sys
import os
import math
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional

# 路径设置：从研究脚本位置向上找到项目根目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

from studies.common.metrics import (
    aggregate_standard_metrics,
    param_absolute_errors,
    param_relative_errors,
    quantile_true,
    quantile_est,
)


# ============================================================
# 参数空间定义
# ============================================================

PARAM_RANGES = {
    "beta": (1.0, 5.0),
    "eta": (0.5, 5.0),
    "gamma": (0.0, 2.0),
}

SAMPLE_SIZES = [5, 7, 10, 15, 20, 50]


# ============================================================
# 数据生成
# ============================================================

def sample_params(n_configs: int, seed: int = 42) -> np.ndarray:
    """从参数空间均匀采样 (beta, eta, gamma) 真值。

    Returns:
        shape (n_configs, 3) 数组，列顺序 [beta, eta, gamma]
    """
    rng = np.random.RandomState(seed)
    beta = rng.uniform(*PARAM_RANGES["beta"], n_configs)
    eta = rng.uniform(*PARAM_RANGES["eta"], n_configs)
    gamma = rng.uniform(*PARAM_RANGES["gamma"], n_configs)
    return np.column_stack([beta, eta, gamma])


def generate_weibull_sample(
    beta: float, eta: float, gamma: float, n: int, seed: int = None
) -> np.ndarray:
    """生成三参数Weibull分布的失效样本。

    使用逆变换采样：X = γ + η * (-ln(U))^(1/β)，U~Uniform(0,1)
    """
    rng = np.random.RandomState(seed)
    u = rng.uniform(0.001, 0.999, n)  # 避免 0 和 1
    x = gamma + eta * (-np.log(u)) ** (1.0 / beta)
    return np.sort(x)  # 排序后返回


def generate_dataset(
    n_configs: int,
    n_samples: int,
    n_repeats: int = 1,
    param_seed: int = 42,
    sample_seed_start: int = 0,
) -> pd.DataFrame:
    """生成完整数据集。

    每个参数配置生成 n_repeats 组样本，每组 n_samples 个观测值。

    Returns:
        DataFrame，列：config_id, repeat_id, beta, eta, gamma, x1, x2, ..., xn
    """
    params = sample_params(n_configs, seed=param_seed)
    rows = []

    for i, (beta, eta, gamma) in enumerate(params):
        for rep in range(n_repeats):
            seed = sample_seed_start + i * n_repeats + rep
            x = generate_weibull_sample(beta, eta, gamma, n_samples, seed=seed)
            row = {
                "config_id": i,
                "repeat_id": rep,
                "beta": beta,
                "eta": eta,
                "gamma": gamma,
            }
            for j, val in enumerate(x):
                row[f"x{j+1}"] = val
            rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# 特征提取
# ============================================================

FEATURE_NAMES = [
    "mean",       # 均值
    "std",        # 标准差
    "min",        # 最小值
    "max",        # 最大值
    "range",      # 极差
    "q25",        # 25%分位数
    "q50",        # 中位数
    "q75",        # 75%分位数
    "iqr",        # 四分位距
    "skew",       # 偏度
    "kurt",       # 峰度
    "cv",         # 变异系数
]


def extract_features(samples: np.ndarray) -> np.ndarray:
    """从样本提取固定维度统计特征。

    Args:
        samples: shape (n,) 或 (batch, n) 的样本数组

    Returns:
        shape (n_features,) 或 (batch, n_features) 的特征数组
    """
    if samples.ndim == 1:
        return _extract_single(samples)
    else:
        return np.array([_extract_single(s) for s in samples])


def _extract_single(x: np.ndarray) -> np.ndarray:
    """单个样本的特征提取。"""
    x = np.sort(x)
    n = len(x)

    mean = np.mean(x)
    std = np.std(x, ddof=1) if n > 1 else 0.0
    xmin, xmax = x[0], x[-1]
    rng = xmax - xmin
    q25 = np.percentile(x, 25)
    q50 = np.percentile(x, 50)
    q75 = np.percentile(x, 75)
    iqr = q75 - q25

    # 偏度和峰度（手动计算，避免 scipy 依赖）
    if n > 2 and std > 0:
        z = (x - mean) / std
        skew = np.mean(z ** 3)
        kurt = np.mean(z ** 4) - 3.0  # 超额峰度
    else:
        skew = 0.0
        kurt = 0.0

    cv = std / mean if mean > 0 else 0.0

    return np.array([mean, std, xmin, xmax, rng, q25, q50, q75, iqr, skew, kurt, cv])


def get_feature_dim() -> int:
    """返回特征维度。"""
    return len(FEATURE_NAMES)


# ============================================================
# 数据准备（训练/测试格式）
# ============================================================

def prepare_raw_input(df: pd.DataFrame, n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
    """准备排序样本输入（方案A）。

    Returns:
        X: shape (n_rows, n_samples) 排序样本
        y: shape (n_rows, 3) 真值 [beta, eta, gamma]
    """
    x_cols = [f"x{i+1}" for i in range(n_samples)]
    X = df[x_cols].values
    y = df[["beta", "eta", "gamma"]].values
    return X, y


def prepare_feature_input(df: pd.DataFrame, n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
    """准备统计特征输入（方案B）。

    Returns:
        X: shape (n_rows, n_features) 统计特征
        y: shape (n_rows, 3) 真值 [beta, eta, gamma]
    """
    x_cols = [f"x{i+1}" for i in range(n_samples)]
    samples = df[x_cols].values
    X = extract_features(samples)
    y = df[["beta", "eta", "gamma"]].values
    return X, y


# ============================================================
# 评价指标
# ============================================================

def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    R_levels: Tuple[float, ...] = (0.95, 0.99),
) -> Dict:
    """计算参数误差和工程寿命误差。

    Args:
        y_true: shape (n, 3) 真值 [beta, eta, gamma]
        y_pred: shape (n, 3) 预测 [beta_hat, eta_hat, gamma_hat]
        R_levels: 工程寿命可靠度水平

    Returns:
        包含参数误差和工程寿命误差的字典
    """
    n = len(y_true)
    results = []

    for i in range(n):
        beta, eta, gamma = y_true[i]
        beta_hat, eta_hat, gamma_hat = y_pred[i]

        row = {
            "beta": beta, "eta": eta, "gamma": gamma,
            "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
            "converged": True,
            "sample_min": None,
        }
        results.append(row)

    return aggregate_standard_metrics(results, R_levels=R_levels)


def evaluate_by_sample_size(
    results_by_n: Dict[int, Tuple[np.ndarray, np.ndarray]],
) -> pd.DataFrame:
    """按样本量汇总评价结果。

    Args:
        results_by_n: {n: (y_true, y_pred)} 字典

    Returns:
        DataFrame，每行一个样本量的汇总指标
    """
    rows = []
    for n in sorted(results_by_n.keys()):
        y_true, y_pred = results_by_n[n]
        metrics = evaluate_predictions(y_true, y_pred)

        row = {"n": n}
        # 提取关键指标
        for param in ["beta", "eta", "gamma"]:
            if param in metrics.get("param_standard", {}):
                abs_metrics = metrics["param_standard"][param].get("absolute", {})
                row[f"rmse_{param}"] = abs_metrics.get("rmse")
                row[f"mae_{param}"] = abs_metrics.get("mae")
                row[f"bias_{param}"] = abs_metrics.get("bias")

        # x0.95 误差
        x_key = 0.95
        if x_key in metrics.get("quantile_standard", {}):
            rel_metrics = metrics["quantile_standard"][x_key].get("relative", {})
            row["rmse_x095"] = rel_metrics.get("rmse")
            row["mae_x095"] = rel_metrics.get("mae")

        row["failure_rate"] = metrics.get("failure_rate", 0)
        rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    # 测试：生成一个小数据集
    print("生成测试数据集...")
    df = generate_dataset(n_configs=5, n_samples=10, n_repeats=2)
    print(f"数据集形状: {df.shape}")
    print(f"列: {list(df.columns[:8])}...")

    # 测试特征提取
    X_feat, y = prepare_feature_input(df, n_samples=10)
    print(f"\n特征矩阵形状: {X_feat.shape}")
    print(f"特征名称: {FEATURE_NAMES}")
    print(f"第一行特征: {X_feat[0]}")
    print(f"第一行真值: {y[0]}")

    # 测试评价
    y_pred = y + np.random.randn(*y.shape) * 0.1  # 模拟预测
    metrics = evaluate_predictions(y, y_pred)
    print(f"\n评价指标示例:")
    print(f"  beta RMSE: {metrics['rmse_beta']:.4f}")
    print(f"  x0.95 RMSE: {metrics['rmse_x_r0p95']:.4f}")
