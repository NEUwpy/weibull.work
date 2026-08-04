"""
Study/01 Normalized-RAW (NRMC) 正式实验配置 — 新方法设计唯一真相源

本模块定义样本自适应偏移量选择最终方法的正式参数设计（冻结）：
  排序并归一化的完整样本 Z_n = (x_(1)/mean(x), ..., x_(n)/mean(x))
  -> 按样本量 n 分别训练的 MLP
  -> 预测 26 点候选偏移量损失曲线
  -> 选择预测损失最低的偏移量
  -> 使用 MDM 完成参数估计。

与 config.py 的关系：config.py 仍是旧特征路线的正式配置（历史证据，保留只读）。
本模块是归一化排序样本路线的正式配置，两者互不修改。

冻结设计（2026-08-05）：
  - beta         = {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}
  - eta          = 1000（工程尺度，MDM 的偏移量是绝对梯度阈值，尺度有物理含义）
  - gamma/eta    = {0.10, 0.25, 0.50, 0.75, 1.00}
  - gamma        = eta * (gamma/eta) = {100, 250, 500, 750, 1000}
  - n            = {7, 10, 15, 20}
  - repeats      = 300 / 组合
  - 组合总数     = 8*5*4 = 160；样本总数 = 48,000；候选偏移量估计 = 1,248,000
  - 该设计必须包含 (beta, eta, gamma) = (2, 1000, 1000)  -> 即 beta=2, gamma/eta=1.0
  - delta grid   = {0.00, 0.02, ..., 0.50} 共 26 点（复用既有正式网格）
  - Default     delta = 0.1（MDM-Default 基线）
  - seed 命名空间 = "study01_nrmc_v1"（与旧 "study01_v1" 明确区分）

数据路径：
  - MC 数据    artifacts/formal/E5_normalized_raw/shared_data/
  - 训练评价   artifacts/formal/E5_normalized_raw/specialist/
"""

import os

# ============================================================
# 路径配置
# ============================================================

STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 新方法正式实验根目录
E5_ROOT = os.path.join(STUDY_ROOT, "artifacts", "formal", "E5_normalized_raw")

# MC 数据目录
SHARED_DATA_DIR = os.path.join(E5_ROOT, "shared_data")
CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

# 训练与评价输出目录
SPECIALIST_DIR = os.path.join(E5_ROOT, "specialist")

# ============================================================
# 冻结参数设计
# ============================================================

BETA_GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]   # 8 个形状参数
ETA = 1000.0                                            # 尺度参数（固定，工程尺度）
GAMMA_OVER_ETA_GRID = [0.10, 0.25, 0.50, 0.75, 1.00]    # 5 个位置—尺度比
N_GRID = [7, 10, 15, 20]                                # 4 个样本量
REPEATS = 300                                           # 每组合重复抽样

# gamma = eta * (gamma/eta)
GAMMA_GRID = [round(g * ETA, 6) for g in GAMMA_OVER_ETA_GRID]


def build_combos():
    """全部 (beta, gamma/eta, n) 组合，枚举顺序与五折留出的组合划分一致。

    顺序 = product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID)。
    """
    from itertools import product
    return list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))


def get_gamma(goe):
    return goe * ETA


# ============================================================
# δ 搜索网格与基线
# ============================================================

DELTA_GRID = [round(0.00 + 0.02 * i, 2) for i in range(26)]   # 26 点
DEFAULT_DELTA = 0.1


# ============================================================
# 抽样种子命名空间
# ============================================================

# 与旧特征路线（config.SEED_NAMESPACE = "study01_v1"）明确区分，
# 保证新设计样本序列独立、可复现。
SEED_NAMESPACE = "study01_nrmc_v1"


# ============================================================
# 学习合同（复用既有正式合同；仅输入表示改为归一化排序样本）
# ============================================================

# 每个 n 独立训练一个 MLP（不使用 padding/mask/跨 n 联合网络）
# 结构：输入维 = n，三个隐藏层 256/128/64，输出 26 维损失曲线。
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

# 训练稳定性评价 seed（与既有正式合同一致）
STABILITY_SEEDS = [42, 2026, 3407]

# 最终部署模型的训练 seed：预先固定（不根据测试结果选择），
# 与稳定性 seed 集合刻意区分，避免“按结果挑 seed”的观感。
FINAL_DEV_SEED = 1

# 每个 n 内按完整 (beta, gamma/eta) 组合进行五折留出
N_FOLDS = 5


# ============================================================
# 规模自检
# ============================================================

def design_summary():
    n_combos = len(BETA_GRID) * len(GAMMA_OVER_ETA_GRID) * len(N_GRID)
    n_samples = n_combos * REPEATS
    n_mdm = n_samples * len(DELTA_GRID)
    return {
        "n_beta": len(BETA_GRID),
        "n_gamma_over_eta": len(GAMMA_OVER_ETA_GRID),
        "n_n": len(N_GRID),
        "combos": n_combos,
        "repeats": REPEATS,
        "n_samples": n_samples,
        "n_deltas": len(DELTA_GRID),
        "n_mdm_fits": n_mdm,
        "beta_grid": BETA_GRID,
        "eta": ETA,
        "gamma_grid": GAMMA_GRID,
        "gamma_over_eta_grid": GAMMA_OVER_ETA_GRID,
        "n_grid": N_GRID,
        "delta_grid": DELTA_GRID,
        "default_delta": DEFAULT_DELTA,
        "seed_namespace": SEED_NAMESPACE,
        "must_include_combo": {"beta": 2.0, "eta": 1000.0, "gamma": 1000.0},
    }


# 冻结设计必须包含 (beta, eta, gamma) = (2, 1000, 1000)
def _assert_design():
    assert 2.0 in BETA_GRID
    assert 1.00 in GAMMA_OVER_ETA_GRID
    assert (2.0 * ETA) == 2000.0  # gamma = goe * eta = 1.00 * 1000 = 1000
    assert 15 in N_GRID


_assert_design()


if __name__ == "__main__":
    import json
    s = design_summary()
    print(json.dumps(s, indent=1))
    print(f"MDM 总估计次数: {s['n_mdm_fits']:,}")
    print(f"must include (beta, eta, gamma) = (2, 1000, 1000): "
          f"{(2.0, 1000.0, 1000.0) in [(b, ETA, get_gamma(g)) for b in BETA_GRID for g in GAMMA_OVER_ETA_GRID]}")
