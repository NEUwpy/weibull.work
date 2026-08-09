"""Study/02 P-Q 三输出 MLP（P、Q 共用同一结构）。

结构签名：隐藏层 (256,128,64) + ReLU + 3 输出（协议 §1.1）。
初始化：torch.manual_seed(seed) 后默认 Kaiming 初始化。
"""

from __future__ import annotations

import hashlib

import torch
import torch.nn as nn

from . import config as CFG


class WeibullMLP(nn.Module):
    def __init__(self, n_in: int, hidden=None):
        super().__init__()
        hidden = hidden if hidden is not None else CFG.HIDDEN_LAYERS
        layers = []
        prev = n_in
        for h in hidden:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            prev = h
        layers.append(nn.Linear(prev, 3))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class WeibullScalarMLP(nn.Module):
    """与 :class:`WeibullMLP` 相同隐藏骨干、单标量输出头。

    仅供 S5B 的 Q-direct 结构基线使用；不替代 P/Q 的三输出主对照。
    """

    def __init__(self, n_in: int, hidden=None):
        super().__init__()
        hidden = hidden if hidden is not None else CFG.HIDDEN_LAYERS
        layers = []
        prev = n_in
        for h in hidden:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def build_model(n_in: int, seed: int, hidden=None) -> WeibullMLP:
    """在 torch.manual_seed(seed) 后确定性构建模型（初始参数确定）。

    统一 float64（与样本/目标张量一致，避免 dtype 混用）。
    """
    torch.manual_seed(seed)
    model = WeibullMLP(n_in, hidden=hidden)
    return model.double()


def build_scalar_model(n_in: int, seed: int, hidden=None) -> WeibullScalarMLP:
    """确定性构建 S5B Q-direct 单输出模型。"""
    torch.manual_seed(seed)
    return WeibullScalarMLP(n_in, hidden=hidden).double()


def trunk_params_sha(model: nn.Module) -> str:
    """隐藏骨干参数 SHA；排除最后一个线性输出头。"""
    linear_layers = [m for m in model.modules() if isinstance(m, nn.Linear)]
    if len(linear_layers) < 2:
        raise ValueError("model has no separable hidden trunk")
    head = linear_layers[-1]
    parts = [p.detach().cpu().float().ravel()
             for p in model.parameters()
             if all(p is not hp for hp in head.parameters())]
    return hashlib.sha256(torch.cat(parts).numpy().tobytes()).hexdigest()


def params_sha(model: nn.Module) -> str:
    arr = torch.cat([p.detach().cpu().float().ravel() for p in model.parameters()])
    return hashlib.sha256(arr.numpy().tobytes()).hexdigest()


def structure_signature(n_in: int, hidden=None) -> str:
    hidden = tuple(hidden if hidden is not None else CFG.HIDDEN_LAYERS)
    sig = f"mlp_in{n_in}_hidden{hidden}_relu_out3_softplus_decode"
    return hashlib.sha256(sig.encode()).hexdigest()


def scalar_structure_signature(n_in: int, hidden=None) -> str:
    hidden = tuple(hidden if hidden is not None else CFG.HIDDEN_LAYERS)
    sig = f"mlp_in{n_in}_hidden{hidden}_relu_out1_direct_xR"
    return hashlib.sha256(sig.encode()).hexdigest()
