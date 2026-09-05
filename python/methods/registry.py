"""
方法注册表

集中管理所有参数估计方法的注册、别名和未实现标记。
"""

from fastapi import HTTPException

from methods.mle import MLE
from methods.mmle import MMLE
from methods.lre import LRE
from methods.lse import LSE
from methods.mps import MPS
from methods.mm import MM
from methods.wmle import WMLE
from methods.mdm import MDM

# ============================================================
# 有独立实现的方法
# ============================================================
IMPLEMENTED = {
    "mle": MLE, "mmle": MMLE, "mps": MPS, "wmle": WMLE,
    "lse": LSE, "mdm": MDM, "lre": LRE,
    "mm": MM,
}

# ============================================================
# 合理的别名映射（同族方法的不同变体）
# ============================================================
ALIASES = {
    "wlse": "lse", "mde": "mdm", "eiv": "lse",
    "rrx": "lre", "rry": "lre", "blre": "lre",
    "lm": "pwm", "tlm": "pwm",
    "gm11": "grey",
    "gibbs": "bayesian", "map": "bayesian",
}

# ============================================================
# 前端有定义但后端尚未实现的方法
# ============================================================
NOT_IMPLEMENTED = {
    "pwm", "grey", "bayesian",
    "construct_stat", "mve", "lsf",
    "ai", "pso", "svr", "ann",
}


def resolve_method(method_id: str):
    """
    解析方法ID，返回对应的算法类。
    - 已实现：直接返回
    - 别名：解析到已实现的方法
    - 未实现：抛出 501 HTTPException
    - 未知方法：抛出 400 HTTPException
    """
    mid = method_id.lower()

    # Resolve aliases before checking availability, including aliases to stubs.
    mid = ALIASES.get(mid, mid)

    if mid in NOT_IMPLEMENTED:
        raise HTTPException(
            status_code=501,
            detail=f"方法 '{method_id}' 尚未实现，暂不可用。"
        )

    if mid in IMPLEMENTED:
        return mid, IMPLEMENTED[mid]

    raise HTTPException(
        status_code=400,
        detail=f"不支持的方法: '{method_id}'。"
    )
