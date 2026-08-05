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


def build_model(n_in: int, seed: int, hidden=None) -> WeibullMLP:
    """在 torch.manual_seed(seed) 后确定性构建模型（初始参数确定）。

    统一 float64（与样本/目标张量一致，避免 dtype 混用）。
    """
    torch.manual_seed(seed)
    model = WeibullMLP(n_in, hidden=hidden)
    return model.double()


def params_sha(model: nn.Module) -> str:
    arr = torch.cat([p.detach().cpu().float().ravel() for p in model.parameters()])
    return hashlib.sha256(arr.numpy().tobytes()).hexdigest()


def structure_signature(n_in: int, hidden=None) -> str:
    hidden = tuple(hidden if hidden is not None else CFG.HIDDEN_LAYERS)
    sig = f"mlp_in{n_in}_hidden{hidden}_relu_out3_softplus_decode"
    return hashlib.sha256(sig.encode()).hexdigest()
