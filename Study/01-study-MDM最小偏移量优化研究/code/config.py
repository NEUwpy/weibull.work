"""
Study/01 正式实验全局配置

唯一真相源：所有实验脚本从此文件读取参数网格、δ grid、repeats 等。
修改任何实验参数只需改这一个文件。

设计原则：
- E1/E2 共用同一批 MC 扫描数据（同一参数网格、同一 δ grid、同一 repeats）
- Default δ=0.1 是所有实验的共用基线
- 每个配置项有注释说明来源（D 编号历史来源见 archive/history/2026-07-03-头脑风暴进度.md；当前协议见 02-实验协议.md）
"""

import os

# ============================================================
# 路径配置
# ============================================================

# 项目根目录（Study/01）
STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 平台代码根目录（python/）
PLATFORM_ROOT = r"D:\weibull\python"

# 正式实验输出根目录
ARTIFACTS_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal")

# E1/E2 共用 MC 扫描数据目录
SHARED_DATA_DIR = os.path.join(ARTIFACTS_DIR, "shared_data")

# E1 输出目录
E1_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E1_baseline")

# E2 输出目录
E2_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E2_oracle_layers")

# MLE 锚点输出目录
MLE_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "mle_anchor")


# ============================================================
# 参数网格（D4/D6 决策）
# ============================================================

# 主网格参数（E1/E2 共用）
BETA_GRID = [1.5, 2.0, 2.5, 4.0, 5.0]        # 形状参数
ETA_GRID = [1.0]                                # 尺度参数（固定，归一化基准）
GAMMA_OVER_ETA_GRID = [0.1, 0.5, 1.0]          # γ/η 比值
N_GRID = [7, 10, 20]                            # 样本量

# γ 由 γ/η × η 计算
def get_gamma_values(eta):
    """根据 η 计算实际 γ 值列表。"""
    return [gne * eta for gne in GAMMA_OVER_ETA_GRID]

# 完整参数组合列表：[(beta, eta, gamma), ...]
def build_param_grid():
    """生成完整参数组合网格。
    
    Returns:
        List[Tuple[beta, eta, gamma]] — 45 组合 (5β × 1η × 3γ/η)
    """
    grid = []
    for eta in ETA_GRID:
        for gamma in get_gamma_values(eta):
            for beta in BETA_GRID:
                grid.append((beta, eta, gamma))
    return grid


# ============================================================
# δ 搜索网格（D3 决策）
# ============================================================

# δ grid: 0.00, 0.02, ..., 0.50 — 26 个点
DELTA_GRID = [round(0.00 + 0.02 * i, 2) for i in range(26)]

# Default 基线 δ
DEFAULT_DELTA = 0.1


# ============================================================
# 蒙特卡洛重复次数（D6 决策）
# ============================================================

# E1/E2 主网格 repeats
R_MAIN = 1000

# E4 稳健性网格 repeats（暂不用，留作参考）
R_ROBUSTNESS = 500


# ============================================================
# 种子命名空间
# ============================================================

# 保证可复现；不同实验如需不同数据可用不同 namespace
SEED_NAMESPACE = "study01_v1"


# ============================================================
# J₁ 指标定义（D1 决策）
# ============================================================

# J₁ = √(mean_i[(Δβ/β)² + (Δη/η)² + (Δγ/η)²])
# - γ 归一化除 η（尺度参数真值），不除 γ 自身
# - 等权 w_β = w_η = w_γ = 1
# 文献先例：182-050 / 182-097 的 Joint RMSE


# ============================================================
# 进程池配置（方案B：温和并行）
# ============================================================

# 并行进程数 — 按参数组合分配
# 每个进程独立处理若干 (beta, eta, gamma, n) 块，互不干扰
# 建议设为 CPU 物理核数的 50%-75%，留余量给系统
N_WORKERS = 4

# 断点续跑进度文件
PROGRESS_FILE = os.path.join(SHARED_DATA_DIR, "progress.json")


# ============================================================
# 计算量
# ============================================================

def estimate_total():
    """计算总估计次数和预估时间。"""
    n_combos = len(BETA_GRID) * len(ETA_GRID) * len(GAMMA_OVER_ETA_GRID) * len(N_GRID)
    n_deltas = len(DELTA_GRID)
    total_mdm = n_combos * n_deltas * R_MAIN
    total_mle = n_combos * R_MAIN  # MLE 无 δ 循环
    return {
        "param_combos": n_combos,
        "delta_points": n_deltas,
        "repeats": R_MAIN,
        "total_mdm_estimates": total_mdm,
        "total_mle_estimates": total_mle,
    }


if __name__ == "__main__":
    info = estimate_total()
    print("=== Study/01 实验配置 ===")
    print(f"参数组合: {info['param_combos']} (β{len(BETA_GRID)} × η{len(ETA_GRID)} × γ/η{len(GAMMA_OVER_ETA_GRID)} × n{len(N_GRID)})")
    print(f"δ grid: {info['delta_points']} 点 ({DELTA_GRID[0]}~{DELTA_GRID[-1]}, 步长0.02)")
    print(f"Repeats: {info['repeats']}")
    print(f"MDM 总估计次数: {info['total_mdm_estimates']:,}")
    print(f"MLE 锚点估计次数: {info['total_mle_estimates']:,}")
    print(f"并行进程数: {N_WORKERS}")
    print(f"预估总时间(97ms/call): {info['total_mdm_estimates'] * 97 / 1000 / 3600:.1f} 小时 (串行)")
    print(f"预估总时间({N_WORKERS}进程): ~{info['total_mdm_estimates'] * 97 / 1000 / 3600 / N_WORKERS:.1f} 小时")
