"""Study/02 P-Q v2 损失与参数合法化（P、Q 共用同一输出变换）。

协议 v2 §1.1（location-scale decode，参考 study02a/representations.decode_targets）：
  beta_hat  = softplus(o1) + eps
  eta_hat   = softplus(o2) + eps
  gamma_hat = min(X) - eta * (exp(o3) + GAP_FLOOR)
其中 eta = 设计固定 scale（1000），location = min(X)，GAP_FLOOR = 1e-7（gap 下限，
保证 float64 下严格 gamma_hat < min(X)，即使 o3 -> -inf）。
P 损失：β/η 相对平方误差 + γ 的平方 log-gap 误差（对带支撑约束的位置参数，log-gap 是
自然相对误差尺度，且其梯度在 collapse 区非零，避免 exp 死区陷阱）。
Q 损失：x0.95 相对平方误差（梯度经 Weibull 公式传播到三个输出）。
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from . import config as CFG

GAP_FLOOR = 1e-7  # gap = min(X) - gamma_hat 的相对下限（乘 eta 后 >> ulp）


def decode_params(o: torch.Tensor, min_X: torch.Tensor):
    """o: (..., 3) 原始输出；min_X: (...,) 逐样本 min(X) → 合法三参数。

    返回 (beta_hat, eta_hat, gamma_hat)。gamma_hat < min(X) 由构造严格保证：
    gap = eta*(exp(o3)+GAP_FLOOR) >= eta*GAP_FLOOR = 1e-4 > min(X) 的 ulp。
    """
    eps = CFG.EPS_PARAM
    beta_hat = F.softplus(o[..., 0]) + eps
    eta_hat = F.softplus(o[..., 1]) + eps
    gap = CFG.ETA * (torch.exp(o[..., 2]) + GAP_FLOOR)
    gamma_hat = min_X - gap
    return beta_hat, eta_hat, gamma_hat


def weibull_quantile(beta_hat: torch.Tensor, eta_hat: torch.Tensor,
                     gamma_hat: torch.Tensor, R: float = CFG.X0_95_R) -> torch.Tensor:
    """x_R = gamma + eta * (-ln(R))^(1/beta)。可微。"""
    lnR = torch.tensor(-np.log(R), dtype=torch.float64, device=beta_hat.device)
    return gamma_hat + eta_hat * lnR ** (1.0 / beta_hat)


def loss_p(beta_hat: torch.Tensor, eta_hat: torch.Tensor, gamma_hat: torch.Tensor,
           beta: torch.Tensor, eta: torch.Tensor, gamma: torch.Tensor,
           min_X: torch.Tensor) -> torch.Tensor:
    rel_b = (beta_hat - beta) / beta
    rel_e = (eta_hat - eta) / eta
    # γ：平方 log-gap 误差（gap = min(X) - gamma，带支撑约束位置参数的自然相对误差）
    gap_hat = min_X - gamma_hat
    gap_true = min_X - gamma
    log_gap_err = torch.log(gap_hat) - torch.log(gap_true)
    return (rel_b ** 2 + rel_e ** 2 + log_gap_err ** 2).mean()


def loss_q(x95_hat: torch.Tensor, x95: torch.Tensor) -> torch.Tensor:
    return (((x95_hat - x95) / x95) ** 2).mean()


def compute_x95_hat_from_outputs(o: torch.Tensor, min_X: torch.Tensor) -> torch.Tensor:
    """解码输出并计算 x0.95_hat（供评测与 Q 损失共用）。"""
    b, e, g = decode_params(o, min_X)
    return weibull_quantile(b, e, g)


def build_route_loss(route: str):
    """返回 (loss_fn, target_kind)。loss_fn(model_out, targets, min_X)。"""
    route = route.upper()
    if route == "P":

        def loss_fn(model_out, targets, min_X):
            b, e, g = decode_params(model_out, min_X)
            beta, eta, gamma = targets[..., 0], targets[..., 1], targets[..., 2]
            return loss_p(b, e, g, beta, eta, gamma, min_X)
        return loss_fn, "params"

    if route == "Q":

        def loss_fn(model_out, targets, min_X):
            x95_hat = compute_x95_hat_from_outputs(model_out, min_X)
            return loss_q(x95_hat, targets)
        return loss_fn, "x0_95"

    raise ValueError(f"unknown route {route!r}")
