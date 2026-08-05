"""
E03 统一口径重算脚本
- 读取现有45配置 delta sweep 原始数据
- 按新口径计算 loss_i, j_i, J_param
- 输出 L0~L5 阶梯表和中间汇总数据
"""
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
import json

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
OUT_DIR = DATA_DIR  # 输出到同目录
PROG_DIR = BASE / "程序"

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GAMMA_RATIOS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTAS = np.arange(0, 0.51, 0.02)

CONFIGS = list(product(BETAS, NS, GAMMA_RATIOS))
print(f"参数空间: {len(BETAS)} β × {len(NS)} n × {len(GAMMA_RATIOS)} γ/η = {len(CONFIGS)} 配置")


def load_config(beta, n, gamma_ratio):
    """加载单个配置的 delta sweep 数据，计算 loss_i"""
    fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{gamma_ratio}.csv"
    fpath = DATA_DIR / fname
    if not fpath.exists():
        print(f"  WARNING: {fname} not found, skipping")
        return None
    df = pd.read_csv(fpath)
    gamma_true = gamma_ratio * ETA
    df['loss_i'] = (
        ((df['beta_hat'] - beta) / beta) ** 2 +
        ((df['eta_hat'] - ETA) / ETA) ** 2 +
        ((df['gamma_hat'] - gamma_true) / ETA) ** 2
    )
    df['j_i'] = np.sqrt(df['loss_i'])
    df['beta'] = beta
    df['n'] = n
    df['gamma_ratio'] = gamma_ratio
    df['gamma_true'] = gamma_true
    return df


def config_jparam(df):
    """对单个配置按 delta 聚合计算 J_param(δ) = sqrt(mean(loss_i(δ)))"""
    agg = df.groupby('delta').agg(
        mean_loss=('loss_i', 'mean'),
        n_valid=('status', 'sum'),
        n_total=('status', 'count'),
    ).reset_index()
    agg['J_param'] = np.sqrt(agg['mean_loss'])
    agg['valid_rate'] = agg['n_valid'] / agg['n_total']
    return agg


print("\n=== 1. 加载所有配置 ===")
all_data = {}
config_jparams = {}

for beta, n, gr in CONFIGS:
    df = load_config(beta, n, gr)
    if df is not None:
        key = (beta, n, gr)
        all_data[key] = df
        config_jparams[key] = config_jparam(df)

print(f"成功加载 {len(all_data)}/{len(CONFIGS)} 配置")


# ============================================================
# L0~L4 层级计算
# ============================================================
# 正确口径：先平均 mean_loss，再 sqrt。不是平均 J_param。
# J_param_level(δ) = sqrt(mean_{config in level} mean_loss_config(δ))
print("\n=== 2. 计算 L0~L4 层级最优 ===")

def aggregate_mean_loss(configs_subset):
    """对一组配置，按 δ 等权平均 mean_loss，返回 {delta: avg_mean_loss}"""
    loss_by_delta = {d: [] for d in DELTAS}
    for key in configs_subset:
        cj = config_jparams[key]
        for _, row in cj.iterrows():
            d = float(row['delta'])
            if d in loss_by_delta:
                loss_by_delta[d].append(row['mean_loss'])
    avg = {}
    for d in DELTAS:
        if loss_by_delta[d]:
            avg[d] = float(np.mean(loss_by_delta[d]))
    return avg

def level_optimal(configs_subset, level_name):
    """返回最优 δ* 和对应 J_param = sqrt(min_δ avg_mean_loss(δ))"""
    avg_loss = aggregate_mean_loss(configs_subset)
    if not avg_loss:
        return None
    best_delta = min(avg_loss, key=avg_loss.get)
    return {
        'level': level_name,
        'delta_star': float(best_delta),
        'J_param': float(np.sqrt(avg_loss[best_delta])),
        'n_configs': len(configs_subset),
    }

def level_J_param(configs_subset):
    """计算层级综合 J_param = sqrt(mean_{config} mean_loss_{config}(δ*_config))"""
    # 每个 config 在自己的 δ* 下有一个 mean_loss
    # 层级 J = sqrt(mean of these mean_loss across configs)
    losses = []
    for key in configs_subset:
        cj = config_jparams[key]
        best_idx = cj['mean_loss'].idxmin()
        best_loss = cj.loc[best_idx, 'mean_loss']
        losses.append(best_loss)
    return float(np.sqrt(np.mean(losses))) if losses else None


# L0: 全局
l0 = level_optimal(list(all_data.keys()), 'L0')

# L1: 按 n
l1_results = {}
for n in NS:
    configs = [k for k in all_data if k[1] == n]
    r = level_optimal(configs, f'L1_n{n}')
    if r:
        l1_results[n] = r
# L1 综合 J: 先用各 n 自己的 δ*_n，再 sqrt(mean(mean_loss across n))
l1_combined = level_J_param(list(all_data.keys()))  # all configs at their own L1 δ*
# 但 L1 按 n 意味着: 对每个 n，所有该 n 的 config 共用 δ*_n
# 所以 L1 J_param = sqrt(mean over all configs of mean_loss_config(δ*_n(config)))
l1_losses = []
for key, cj in config_jparams.items():
    n = key[1]
    l1_delta = l1_results[n]['delta_star']
    row = cj[cj['delta'] == l1_delta]
    if len(row) > 0:
        l1_losses.append(float(row['mean_loss'].iloc[0]))
l1_J = float(np.sqrt(np.mean(l1_losses))) if l1_losses else None

l1 = {
    'level': 'L1',
    'delta_star_by_n': {n: r['delta_star'] for n, r in l1_results.items()},
    'J_param_by_n': {n: r['J_param'] for n, r in l1_results.items()},
    'J_param': l1_J,
    'n_configs': sum(r['n_configs'] for r in l1_results.values()),
}

# L2: 按 β
l2_results = {}
for beta in BETAS:
    configs = [k for k in all_data if k[0] == beta]
    r = level_optimal(configs, f'L2_beta{beta}')
    if r:
        l2_results[beta] = r
l2_losses = []
for key, cj in config_jparams.items():
    beta = key[0]
    l2_delta = l2_results[beta]['delta_star']
    row = cj[cj['delta'] == l2_delta]
    if len(row) > 0:
        l2_losses.append(float(row['mean_loss'].iloc[0]))
l2_J = float(np.sqrt(np.mean(l2_losses))) if l2_losses else None

l2 = {
    'level': 'L2',
    'delta_star_by_beta': {b: r['delta_star'] for b, r in l2_results.items()},
    'J_param_by_beta': {b: r['J_param'] for b, r in l2_results.items()},
    'J_param': l2_J,
    'n_configs': sum(r['n_configs'] for r in l2_results.values()),
}

# L3: 按 (β, n)
l3_results = {}
for beta in BETAS:
    for n in NS:
        configs = [k for k in all_data if k[0] == beta and k[1] == n]
        r = level_optimal(configs, f'L3_b{beta}_n{n}')
        if r:
            l3_results[(beta, n)] = r
l3_losses = []
for key, cj in config_jparams.items():
    bn = (key[0], key[1])
    l3_delta = l3_results[bn]['delta_star']
    row = cj[cj['delta'] == l3_delta]
    if len(row) > 0:
        l3_losses.append(float(row['mean_loss'].iloc[0]))
l3_J = float(np.sqrt(np.mean(l3_losses))) if l3_losses else None

l3 = {
    'level': 'L3',
    'delta_star_by_bn': {str(k): r['delta_star'] for k, r in l3_results.items()},
    'J_param': l3_J,
    'n_configs': len(l3_results),
}

# L4: 按 (β, n, γ/η)
l4_results = {}
for beta in BETAS:
    for n in NS:
        for gr in GAMMA_RATIOS:
            key = (beta, n, gr)
            if key in all_data:
                r = level_optimal([key], f'L4_b{beta}_n{n}_g{gr}')
                if r:
                    l4_results[key] = r
l4_losses = []
for key, cj in config_jparams.items():
    l4_delta = l4_results[key]['delta_star']
    row = cj[cj['delta'] == l4_delta]
    if len(row) > 0:
        l4_losses.append(float(row['mean_loss'].iloc[0]))
l4_J = float(np.sqrt(np.mean(l4_losses))) if l4_losses else None

l4 = {
    'level': 'L4',
    'delta_star_by_config': {str(k): r['delta_star'] for k, r in l4_results.items()},
    'J_param': l4_J,
    'n_configs': len(l4_results),
}


# ============================================================
# L5: 逐样本 Oracle
# ============================================================
print("=== 3. 计算 L5 逐样本 Oracle ===")

l5_per_sample = []
for key, df in all_data.items():
    beta, n, gr = key
    for rep_id in df['rep'].unique():
        rep_data = df[df['rep'] == rep_id]
        # 找使 loss_i 最小的 δ
        best_idx = rep_data['loss_i'].idxmin()
        best_row = rep_data.loc[best_idx]
        l5_per_sample.append({
            'beta': beta,
            'n': n,
            'gamma_ratio': gr,
            'rep': rep_id,
            'delta_star_i': float(best_row['delta']),
            'min_loss_i': float(best_row['loss_i']),
        })

l5_df = pd.DataFrame(l5_per_sample)
l5_J_param = float(np.sqrt(l5_df['min_loss_i'].mean()))
l5_mean_ji = float(np.sqrt(l5_df['min_loss_i']).mean())  # 旧口径 mean(j_i)

l5 = {
    'level': 'L5',
    'J_param': l5_J_param,
    'mean_ji_old': l5_mean_ji,  # 旧口径参考
    'n_samples': len(l5_df),
}

# Default δ=0.1
print("=== 4. 计算 Default δ=0.1 ===")
default_losses = []
for key, df in all_data.items():
    d01 = df[df['delta'] == 0.1]
    default_losses.extend(d01['loss_i'].tolist())
default_J = float(np.sqrt(np.mean(default_losses)))
default_info = {
    'level': 'Default',
    'delta': 0.1,
    'J_param': default_J,
}


# ============================================================
# 输出阶梯表
# ============================================================
print("\n=== 5. 阶梯表 ===")

ladder_rows = [
    ('Default δ=0.1', default_J, 0.0, '—'),
    ('L0 全局最优', l0['J_param'], l0['J_param'] - default_J, 'vs Default'),
    ('L1 按 n', l1['J_param'], l1['J_param'] - default_J, 'vs L0'),
    ('L2 按 β', l2['J_param'], l2['J_param'] - default_J, 'vs L1'),
    ('L3 按 β,n', l3['J_param'], l3['J_param'] - default_J, 'vs L2'),
    ('L4 按 β,n,γ/η', l4['J_param'], l4['J_param'] - default_J, 'vs L3'),
    ('L5 逐样本', l5_J_param, l5_J_param - default_J, 'vs L4'),
]

print(f"{'层级':<20} {'J_param':>8} {'vs Default':>10} {'边际'}")
print("-" * 55)
for name, j, vs_def, marginal in ladder_rows:
    print(f"{name:<20} {j:>8.4f} {vs_def:>+10.4f} {marginal}")

# 保存阶梯表 CSV
ladder_df = pd.DataFrame(ladder_rows, columns=['层级', 'J_param', 'vs_Default', '边际增益'])
ladder_df.to_csv(OUT_DIR / 'E03_ladder_table_v2.csv', index=False, encoding='utf-8-sig')

# 保存 L0~L4 详细结果
detailed = {
    'default': default_info,
    'l0': l0,
    'l1': l1,
    'l2': l2,
    'l3': l3,
    'l4': l4,
    'l5': l5,
}

# 清理不可序列化的 key
def make_serializable(obj):
    if isinstance(obj, dict):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

with open(OUT_DIR / 'E03_level_results_v2.json', 'w', encoding='utf-8') as f:
    json.dump(make_serializable(detailed), f, indent=2, ensure_ascii=False)

# 保存 L3/L4 delta_star 矩阵 (用于热力图)
l3_matrix = pd.DataFrame(index=NS, columns=BETAS)
for (beta, n), r in l3_results.items():
    l3_matrix.loc[n, beta] = r['delta_star']
l3_matrix.to_csv(OUT_DIR / 'E03_L3_heatmap_v2.csv', encoding='utf-8-sig')

l4_matrices = {}
for gr in GAMMA_RATIOS:
    mat = pd.DataFrame(index=NS, columns=BETAS)
    for (beta, n, g), r in l4_results.items():
        if g == gr:
            mat.loc[n, beta] = r['delta_star']
    mat.to_csv(OUT_DIR / f'E03_L4_heatmap_gamma{gr}_v2.csv', encoding='utf-8-sig')
    l4_matrices[gr] = mat

# 保存 L5 逐样本数据
l5_df.to_csv(OUT_DIR / 'E03_L5_per_sample_v2.csv', index=False, encoding='utf-8-sig')

# 保存 L2 按 β 的曲线数据 — 正确口径: 先 avg mean_loss 再 sqrt
l2_curves = {}
for beta in BETAS:
    configs = [k for k in all_data if k[0] == beta]
    avg_loss = aggregate_mean_loss(configs)
    l2_curves[beta] = {d: float(np.sqrt(v)) for d, v in avg_loss.items()}

l2_curve_df = pd.DataFrame(l2_curves, index=DELTAS)
l2_curve_df.index.name = 'delta'
l2_curve_df.to_csv(OUT_DIR / 'E03_L2_curves_v2.csv', encoding='utf-8-sig')

# L1 曲线
l1_curves = {}
for n in NS:
    configs = [k for k in all_data if k[1] == n]
    avg_loss = aggregate_mean_loss(configs)
    l1_curves[n] = {d: float(np.sqrt(v)) for d, v in avg_loss.items()}

l1_curve_df = pd.DataFrame(l1_curves, index=DELTAS)
l1_curve_df.index.name = 'delta'
l1_curve_df.to_csv(OUT_DIR / 'E03_L1_curves_v2.csv', encoding='utf-8-sig')

# L0 全局曲线
avg_loss_global = aggregate_mean_loss(list(all_data.keys()))
l0_curve = {d: float(np.sqrt(v)) for d, v in avg_loss_global.items()}
l0_curve_df = pd.DataFrame({'J_param': l0_curve}, index=DELTAS)
l0_curve_df.index.name = 'delta'
l0_curve_df.to_csv(OUT_DIR / 'E03_L0_curve_v2.csv', encoding='utf-8-sig')

print("\n=== 完成 ===")
print(f"Default J_param = {default_J:.4f}")
print(f"L0 δ* = {l0['delta_star']:.2f}, J_param = {l0['J_param']:.4f}")
print(f"L5 J_param = {l5_J_param:.4f} (旧口径 mean(j_i) = {l5_mean_ji:.4f})")
print(f"\n输出文件:")
for f in OUT_DIR.glob('E03_*_v2.*'):
    print(f"  {f.name}")
