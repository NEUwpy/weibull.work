"""Study/02 P-Q 损失与参数合法化（P、Q 共用同一输出变换）。

协议 §1：
  beta_hat  = softplus(o1) + eps
  eta_hat   = softplus(o2) + eps
  gamma_hat = o3
  x0.95_hat = gamma_hat + eta_hat * (-ln(0.95))^(1/beta_hat)
P 损失：参数精度相对平方误差（与 Study01 J1 逐样本项同形）。
Q 损失：x0.95 相对平方误差（梯度经 Weibull 公式传播到三个输出）。
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from . import config as CFG


def decode_params(o: torch.Tensor):
    """o: (..., 3) 原始输出 → (beta_hat, eta_hat, gamma_hat)（合法三参数）。"""
    eps = CFG.EPS_PARAM
    beta_hat = F.softplus(o[..., 0]) + eps
    eta_hat = F.softplus(o[..., 1]) + eps
    gamma_hat = o[..., 2]
    return beta_hat, eta_hat, gamma_hat


def weibull_quantile(beta_hat: torch.Tensor, eta_hat: torch.Tensor,
                     gamma_hat: torch.Tensor, R: float = CFG.X0_95_R) -> torch.Tensor:
    """x_R = gamma + eta * (-ln(R))^(1/beta)。可微。"""
    lnR = torch.tensor(-np.log(R), dtype=torch.float64, device=beta_hat.device)
    return gamma_hat + eta_hat * lnR ** (1.0 / beta_hat)


def loss_p(beta_hat: torch.Tensor, eta_hat: torch.Tensor, gamma_hat: torch.Tensor,
           beta: torch.Tensor, eta: torch.Tensor, gamma: torch.Tensor) -> torch.Tensor:
    rel_b = (beta_hat - beta) / beta
    rel_e = (eta_hat - eta) / eta
    rel_g = (gamma_hat - gamma) / eta
    return (rel_b ** 2 + rel_e ** 2 + rel_g ** 2).mean()


def loss_q(x95_hat: torch.Tensor, x95: torch.Tensor) -> torch.Tensor:
    return (((x95_hat - x95) / x95) ** 2).mean()


def compute_x95_hat_from_outputs(o: torch.Tensor) -> torch.Tensor:
    """解码输出并计算 x0.95_hat（供评测与 Q 损失共用）。"""
    b, e, g = decode_params(o)
    return weibull_quantile(b, e, g)


def build_route_loss(route: str):
    """返回 (loss_fn, 需要的目标)。P → 需要 (beta, eta, gamma)；Q → 需要 x0.95。"""
    route = route.upper()
    if route == "P":

        def loss_fn(model_out, targets):
            b, e, g = decode_params(model_out)
            beta, eta, gamma = targets[..., 0], targets[..., 1], targets[..., 2]
            return loss_p(b, e, g, beta, eta, gamma)
        return loss_fn, "params"

    if route == "Q":

        def loss_fn(model_out, targets):
            x95_hat = compute_x95_hat_from_outputs(model_out)
            return loss_q(x95_hat, targets)
        return loss_fn, "x0_95"

    raise ValueError(f"unknown route {route!r}")
