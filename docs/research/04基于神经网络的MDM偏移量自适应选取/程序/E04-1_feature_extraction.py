"""
E04-1: 特征提取 + 标签生成
- 复用 E03-3 delta sweep 的种子，重新生成样本提取统计特征
- 标签从已有数据读取：L4 δ*、L5 δ*_i、risk curve
- 输出：特征矩阵 + 三组标签向量
"""
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import product
import sys

sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")
from studies.common.sample import generate_sample

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
OUT_DIR = DATA_DIR

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA = 1.0
N_REPS = 500
DELTAS = np.arange(0, 0.51, 0.02)

def extract_features(sample):
    """从原始样本提取10维统计特征（仅限部署时可观测）"""
    n = len(sample)
    s = np.sort(sample)
    median = np.median(s)
    if median < 1e-12:
        median = np.mean(s)
    # 次序统计量
    mean_order = np.mean(s)
    var_order = np.var(s)
    # 间距比
    spacings = np.diff(s)
    spacing_ratios = spacings[1:] / (spacings[:-1] + 1e-12)
    spacing_ratios = np.clip(spacing_ratios, 0, 10)
    mean_sr = np.mean(spacing_ratios)
    var_sr = np.var(spacing_ratios)
    # 形状
    skewness = ((s - mean_order) ** 3).mean() / (np.std(s) ** 3 + 1e-12)
    cv = np.std(s) / (mean_order + 1e-12)
    # 尾部
    t1_median = s[0] / median
    tn_median = s[-1] / median
    log_tn_t1 = np.log(s[-1] / (s[0] + 1e-12))
    return np.array([mean_order, var_order, mean_sr, var_sr,
                     skewness, cv, t1_median, tn_median, log_tn_t1, n], dtype=np.float32)


print("=== 1. 加载标签数据 ===")
# L4 δ*_{β,n,γ/η}
l3 = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_v2.csv', index_col=0)  # β,n -> δ*
l4 = {}
for gr in GERS:
    m = pd.read_csv(DATA_DIR / f'E03_L4_heatmap_gamma{gr}_v2.csv', index_col=0)
    for n_str in m.index:
        for b_str in m.columns:
            l4[(float(b_str), int(n_str), gr)] = m.loc[n_str, b_str]

# L5 δ*_i (22,500行)
l5_df = pd.read_csv(DATA_DIR / 'E03_L5_per_sample_v2.csv')
l5_lookup = {}
for _, row in l5_df.iterrows():
    l5_lookup[(row['beta'], int(row['n']), row['gamma_ratio'], int(row['rep']))] = row['delta_star_i']

# Risk curve: 从 delta sweep 读取 loss_i(δ)
print("=== 2. 提取特征 + 构建标签 ===")
rows = []
total = len(BETAS) * len(NS) * len(GERS) * N_REPS
count = 0

for beta, n, gr in product(BETAS, NS, GERS):
    gamma_t = gr * ETA
    # 加载该配置的 delta sweep
    sweep = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
    # 构建 per-rep loss curve lookup
    loss_by_rep_delta = {}
    for _, row_s in sweep.iterrows():
        r = int(row_s['rep'])
        d = float(row_s['delta'])
        loss = ((row_s['beta_hat'] - beta) / beta) ** 2 + \
               ((row_s['eta_hat'] - ETA) / ETA) ** 2 + \
               ((row_s['gamma_hat'] - gamma_t) / ETA) ** 2
        loss_by_rep_delta.setdefault(r, {})[d] = loss

    for rep in range(N_REPS):
        # 同 seed 生成样本
        sample = generate_sample(beta, ETA, gamma_t, n, rep)
        feats = extract_features(sample)

        row = {
            'beta': beta, 'n': n, 'gamma_ratio': gr, 'rep': rep,
            'f_mean': feats[0], 'f_var': feats[1],
            'f_sr_mean': feats[2], 'f_sr_var': feats[3],
            'f_skew': feats[4], 'f_cv': feats[5],
            'f_t1m': feats[6], 'f_tnm': feats[7],
            'f_log_ratio': feats[8], 'f_n': feats[9],
            'label_L4': l4.get((beta, n, gr), np.nan),
            'label_L5': l5_lookup.get((beta, n, gr, rep), np.nan),
        }
        # Risk curve: 26-dim loss vector
        for d in DELTAS:
            row[f'loss_{d:.2f}'] = loss_by_rep_delta.get(rep, {}).get(d, np.nan)
        rows.append(row)
        count += 1
        if count % 5000 == 0:
            print(f"  {count}/{total}")

df = pd.DataFrame(rows)
print(f"\n=== 3. 输出 ===")

# 特征矩阵（10维）+ 元数据
feat_cols = ['beta', 'n', 'gamma_ratio', 'rep',
             'f_mean', 'f_var', 'f_sr_mean', 'f_sr_var',
             'f_skew', 'f_cv', 'f_t1m', 'f_tnm', 'f_log_ratio', 'f_n']
label_cols = ['label_L4', 'label_L5']
loss_cols = [f'loss_{d:.2f}' for d in DELTAS]

df[feat_cols + label_cols].to_csv(OUT_DIR / 'E04_features_labels.csv', index=False, encoding='utf-8-sig')
df[feat_cols + loss_cols].to_csv(OUT_DIR / 'E04_risk_curves.csv', index=False, encoding='utf-8-sig')

print(f"特征+标签: {len(df)} 样本 × {len(feat_cols) - 4} 特征 + {len(label_cols)} 标签")
print(f"风险曲线: {len(df)} 样本 × 26 δ")
print(f"L4 有效标签: {df['label_L4'].notna().sum()} / {len(df)}")
print(f"L5 有效标签: {df['label_L5'].notna().sum()} / {len(df)}")
print(f"Risk 有效: {df[loss_cols].notna().all(axis=1).sum()} / {len(df)}")
print("\n特征统计:")
print(df[feat_cols[4:]].describe().round(3).to_string())
