"""
Study/01 Dimensional-RAW (DIM-RAW) 正式实验配置 — 冻结参数设计唯一真相源

本模块定义样本自适应偏移量选择最终方法的参数设计（冻结，与 160 组合新设计一致）：
  排序的原始样本 X_n = sort(x_1, ..., x_n)（有量纲，保留绝对尺度）
  -> 按样本量 n 分别训练的 MLP
  -> 预测 26 点候选偏移量损失曲线
  -> 选择预测损失最低的偏移量
  -> 使用 MDM 完成参数估计。

输入表示与 Normalized-RAW 候选对照（x/mean(x)，已标记为未采用）的区别：
  本路线不除以样本均值，保留原始样本的绝对尺度；允许仅由训练折拟合的
  per-position StandardScaler 改善数值训练，但禁止逐样本除均值或其他删除
  绝对尺度信息的处理。因此本路线的网络不具备单位不变性，结论仅适用于与
  训练一致的物理单位及尺度范围（见 03-论文骨架 2.4 边界）。

冻结设计（2026-08-05）：
  - beta         = {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}
  - eta          = 1000（本研究的代表性工程尺度；MDM 本身在同比例缩放下尺度等变）
  - gamma/eta    = {0.10, 0.25, 0.50, 0.75, 1.00}
  - gamma        = eta * (gamma/eta) = {100, 250, 500, 750, 1000}
  - n            = {7, 10, 15, 20}
  - repeats      = 300 / 组合
  - 组合总数     = 160；样本总数 = 48,000；候选偏移量估计 = 1,248,000
  - 必须包含 (beta, eta, gamma) = (2, 1000, 1000)
  - delta grid   = {0.00, 0.02, ..., 0.50} 共 26 点
  - Default     delta = 0.1
  - seed 命名空间 = "study01_nrmc_v1"（与数据分片一致；数据复用上一轮已生成缓存）

数据与产物路径：
  - MC 数据（复用，不重跑/不复制）：
      artifacts/formal/E5_normalized_raw/shared_data/
        chunks/（160 分片，gitignore）  mc_scan_raw.csv（合并，gitignore）
        manifest.json + data_sha256sums.txt（数据清单，纳入 git）
  - 训练评价：artifacts/formal/E6_dimensional_raw/specialist/
"""

import os

# ============================================================
# 路径配置
# ============================================================

STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 复用的新设计数据目录（上一轮生成并校验；命名沿用首次创建时的目录名）
DATA_ROOT = os.path.join(STUDY_ROOT, "artifacts", "formal", "E5_normalized_raw")
SHARED_DATA_DIR = os.path.join(DATA_ROOT, "shared_data")
CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

# Dimensional-RAW 训练与评价输出目录
SPECIALIST_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal",
                              "E6_dimensional_raw", "specialist")

# ============================================================
# 冻结参数设计（与 160 组合新设计一致）
# ============================================================

BETA_GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]   # 8 个形状参数
ETA = 1000.0                                            # 代表性工程尺度（固定）
GAMMA_OVER_ETA_GRID = [0.10, 0.25, 0.50, 0.75, 1.00]    # 5 个位置—尺度比
N_GRID = [7, 10, 15, 20]                                # 4 个样本量
REPEATS = 300                                           # 每组合重复抽样

GAMMA_GRID = [round(g * ETA, 6) for g in GAMMA_OVER_ETA_GRID]


def build_combos():
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
# 抽样种子命名空间（与数据分片一致）
# ============================================================

SEED_NAMESPACE = "study01_nrmc_v1"


# ============================================================
# 学习合同（复用既有正式合同；仅输入表示改为排序原始样本）
# ============================================================

MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

STABILITY_SEEDS = [42, 2026, 3407]
FINAL_DEV_SEED = 1
N_FOLDS = 5


# ============================================================
# 规模自检
# ============================================================

def design_summary():
    n_combos = len(BETA_GRID) * len(GAMMA_OVER_ETA_GRID) * len(N_GRID)
    n_samples = n_combos * REPEATS
    n_mdm = n_samples * len(DELTA_GRID)
    return {
        "n_beta": len(BETA_GRID), "n_gamma_over_eta": len(GAMMA_OVER_ETA_GRID),
        "n_n": len(N_GRID), "combos": n_combos, "repeats": REPEATS,
        "n_samples": n_samples, "n_deltas": len(DELTA_GRID),
        "n_mdm_fits": n_mdm,
        "beta_grid": BETA_GRID, "eta": ETA, "gamma_grid": GAMMA_GRID,
        "gamma_over_eta_grid": GAMMA_OVER_ETA_GRID, "n_grid": N_GRID,
        "delta_grid": DELTA_GRID, "default_delta": DEFAULT_DELTA,
        "seed_namespace": SEED_NAMESPACE,
        "must_include_combo": {"beta": 2.0, "eta": 1000.0, "gamma": 1000.0},
    }


def _assert_design():
    assert 2.0 in BETA_GRID
    assert 1.00 in GAMMA_OVER_ETA_GRID
    assert 15 in N_GRID


_assert_design()


if __name__ == "__main__":
    import json
    print(json.dumps(design_summary(), indent=1))
