"""Study/02 P-Q r4 损失与参数合法化（P、Q 共用同一输出变换）。

r4（Codex 合同决策 000003）授权共享有界 domain-explicit 解码器：
  beta_hat  = softplus(o1) + eps
  eta_hat   = softplus(o2) + eps
  s         = delta + (1 - 2*delta) * sigmoid(o3)
  gamma_hat = gamma_lower + (min(X) - gamma_lower) * s，gamma_lower = 0.0
即 gamma_hat = min(X) * s，s ∈ (delta, 1-delta)。
结构性支撑合法：gamma_hat <= (1-delta)*min(X) < min(X)（严格，非事后 clipping）。
依赖冻结正位置域：真 gamma ∈ [100,1000]，所有样本 min(X) > gamma，故每个真 gamma 都在
(0, min(X)) 内可表示；不声称对负位置问题成立。
P 损失 = approved direct 形式（((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)²）。
Q 损失 = x0.95 相对平方误差（梯度经 Weibull 公式传播）。
不加 log-gap / 辅助 γ 损失 / 直通梯度 / route 特定初始化或解码器。
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from . import config as CFG

GAMMA_LOWER = 0.0
DELTA = 1e-7  # s 的下/上余量，保证 float64 下 gamma_hat 与 0 和 min(X) 严格分离


def decode_params(o: torch.Tensor, min_X: torch.Tensor):
    """o: (..., 3) 原始输出；min_X: (...,) 逐样本 min(X) → 合法三参数。

    gamma_hat = min(X)*s，s = delta + (1-2*delta)*sigmoid(o3) ∈ (delta, 1-delta)，
    故 gamma_hat ∈ (delta*min(X), (1-delta)*min(X))，严格 (0, min(X)) 内。
    """
    eps = CFG.EPS_PARAM
    beta_hat = F.softplus(o[..., 0]) + eps
    eta_hat = F.softplus(o[..., 1]) + eps
    s = DELTA + (1.0 - 2.0 * DELTA) * torch.sigmoid(o[..., 2])
    gamma_hat = GAMMA_LOWER + (min_X - GAMMA_LOWER) * s
    return beta_hat, eta_hat, gamma_hat


def weibull_quantile(beta_hat: torch.Tensor, eta_hat: torch.Tensor,
                     gamma_hat: torch.Tensor, R: float = CFG.X0_95_R) -> torch.Tensor:
    """x_R = gamma + eta * (-ln(R))^(1/beta)。可微。"""
    lnR = torch.tensor(-np.log(R), dtype=torch.float64, device=beta_hat.device)
    return gamma_hat + eta_hat * lnR ** (1.0 / beta_hat)


def loss_p(beta_hat: torch.Tensor, eta_hat: torch.Tensor, gamma_hat: torch.Tensor,
           beta: torch.Tensor, eta: torch.Tensor, gamma: torch.Tensor,
           min_X: torch.Tensor) -> torch.Tensor:
    """direct-P（任务 r4 恢复 approved 形式）：
    rel_b = ((beta_hat-beta)/beta)^2；rel_e = ((eta_hat-eta)/eta)^2；
    rel_g = ((gamma_hat-gamma)/eta)^2（γ 误差以 η 归一，与 Study01 J1 同形）。
    """
    rel_b = (beta_hat - beta) / beta
    rel_e = (eta_hat - eta) / eta
    rel_g = (gamma_hat - gamma) / eta
    return (rel_b ** 2 + rel_e ** 2 + rel_g ** 2).mean()


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
