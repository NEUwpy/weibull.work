"""
E03 工程视角重算：RMSE_x95 (绝对寿命误差，绝对RMSE)
x̂_0.95 = γ̂ + η̂ × (-ln 0.95)^(1/β̂)
loss_eng_i(δ) = (x̂_0.95(δ) - x_0.95_true)²
RMSE_x95 = sqrt(mean(loss_eng_i))
口径：先 avg mean_loss，再 sqrt（与 J_param 一致）
"""
import pandas as pd, numpy as np, json
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTAS = np.arange(0, 0.51, 0.02)
R = 0.95
C = (-np.log(R)) ** (1.0 / np.array(BETAS))  # (-ln 0.95)^(1/β) per β

def x95_hat(bh, eh, gh, beta):
    """计算预测的 x_0.95"""
    c = (-np.log(0.95)) ** (1.0 / np.maximum(bh, 0.1))  # clip β̂ ≥ 0.1
    return gh + eh * c

def config_rmse(df, beta, gr):
    """per-config: 计算每个 δ 的 mean_loss_eng → RMSE_x95"""
    gamma_t = gr * ETA
    x95_true = gamma_t + ETA * C[BETAS.index(beta)]
    df = df.copy()
    df['x95_hat'] = x95_hat(df['beta_hat'].values, df['eta_hat'].values, df['gamma_hat'].values, beta)
    df['loss_eng'] = (df['x95_hat'] - x95_true) ** 2
    agg = df.groupby('delta').agg(mean_loss=('loss_eng','mean'), n_valid=('status','sum')).reset_index()
    agg['RMSE_x95'] = np.sqrt(agg['mean_loss'])
    return agg

def aggregate_mean_loss(configs_subset):
    """等权平均各配置 mean_loss，返回 {delta: avg_mean_loss}"""
    d = {delta: [] for delta in DELTAS}
    for key in configs_subset:
        df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{key[0]}_n{key[1]}_gamma{key[2]}.csv')
        cj = config_rmse(df, key[0], key[2])
        for _, row in cj.iterrows():
            dt = float(row['delta'])
            if dt in d:
                d[dt].append(row['mean_loss'])
    return {k: float(np.mean(v)) for k, v in d.items() if v}

def level_optimal(configs_subset, name):
    al = aggregate_mean_loss(configs_subset)
    if not al: return None
    best = min(al, key=al.get)
    return {'level': name, 'delta_star': float(best), 'RMSE_x95': float(np.sqrt(al[best])), 'n_configs': len(configs_subset)}

def level_j(configs_subset, get_delta_fn):
    """层级综合 RMSE_x95 = sqrt(mean over configs of mean_loss at their level-optimal δ)"""
    losses = []
    for key in configs_subset:
        df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{key[0]}_n{key[1]}_gamma{key[2]}.csv')
        cj = config_rmse(df, key[0], key[2])
        d_star = get_delta_fn(key[0], key[1]) if len(configs_subset) > 1 else get_delta_fn(key)
        row = cj[cj['delta'] == d_star]
        if len(row) > 0:
            losses.append(float(row['mean_loss'].iloc[0]))
    return float(np.sqrt(np.mean(losses))) if losses else None

# ── Config scan (key output for mismatch + plots) ──
print("Building config scan...")
scan_rows = []
for beta in BETAS:
    for n in NS:
        for gr in GERS:
            df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            cj = config_rmse(df, beta, gr)
            for _, row in cj.iterrows():
                scan_rows.append({'beta': beta, 'n': n, 'gamma_eta': gr,
                                  'delta': float(row['delta']),
                                  'mean_loss': float(row['mean_loss']),
                                  'RMSE_x95': float(np.sqrt(row['mean_loss'])),
                                  'n_valid': int(row['n_valid'])})
scan_df = pd.DataFrame(scan_rows)
scan_df.to_csv(DATA_DIR / 'E03_by_config_x095.csv', index=False, encoding='utf-8-sig')
print(f"Config scan: {len(scan_df)} rows")

# ── L0~L4 ──
all_keys = [(b, n, g) for b in BETAS for n in NS for g in GERS]
l0 = level_optimal(all_keys, 'L0')

l1_res = {}
for n in NS:
    keys = [k for k in all_keys if k[1] == n]
    r = level_optimal(keys, f'L1_n{n}')
    if r: l1_res[n] = r
l1_j = level_j(all_keys, lambda b, n: l1_res[n]['delta_star'])
l1 = {'level': 'L1', 'delta_star_by_n': {n: r['delta_star'] for n, r in l1_res.items()}, 'RMSE_x95': l1_j}

l2_res = {}
for beta in BETAS:
    keys = [k for k in all_keys if k[0] == beta]
    r = level_optimal(keys, f'L2_b{beta}')
    if r: l2_res[beta] = r
l2_j = level_j(all_keys, lambda b, n: l2_res[b]['delta_star'])
l2 = {'level': 'L2', 'delta_star_by_beta': {b: r['delta_star'] for b, r in l2_res.items()}, 'RMSE_x95': l2_j}

l3_res = {}
for beta in BETAS:
    for n in NS:
        keys = [k for k in all_keys if k[0] == beta and k[1] == n]
        r = level_optimal(keys, f'L3_b{beta}_n{n}')
        if r: l3_res[(beta, n)] = r
l3_j = level_j(all_keys, lambda b, n: l3_res[(b, n)]['delta_star'])
l3 = {'level': 'L3', 'delta_star_by_bn': {str(k): r['delta_star'] for k, r in l3_res.items()}, 'RMSE_x95': l3_j}

# L4: 每个配置有自己独立的 δ*，直接遍历计算
l4_res = {}
for key in all_keys:
    r = level_optimal([key], 'L4')
    if r: l4_res[key] = r
l4_losses = []
for key in all_keys:
    df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{key[0]}_n{key[1]}_gamma{key[2]}.csv')
    cj = config_rmse(df, key[0], key[2])
    ds = l4_res[key]['delta_star']
    row = cj[cj['delta'] == ds]
    if len(row) > 0: l4_losses.append(float(row['mean_loss'].iloc[0]))
l4_j = float(np.sqrt(np.mean(l4_losses))) if l4_losses else None
l4 = {'level': 'L4', 'delta_star_by_config': {str(k): r['delta_star'] for k, r in l4_res.items()}, 'RMSE_x95': l4_j}
l4 = {'level': 'L4', 'delta_star_by_config': {str(k): r['delta_star'] for k, r in l4_res.items()}, 'RMSE_x95': l4_j}

# ── L5 ──
print("Computing L5...")
l5_data = []
for beta in BETAS:
    for n in NS:
        for gr in GERS:
            df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            gamma_t = gr * ETA
            x95_true = gamma_t + ETA * C[BETAS.index(beta)]
            for rep in df['rep'].unique():
                rd = df[df['rep'] == rep].copy()
                rd['x95_hat'] = x95_hat(rd['beta_hat'].values, rd['eta_hat'].values, rd['gamma_hat'].values, beta)
                rd['loss_eng'] = (rd['x95_hat'] - x95_true) ** 2
                best = rd.loc[rd['loss_eng'].idxmin()]
                l5_data.append({'beta': beta, 'n': n, 'gamma_ratio': gr, 'rep': int(rep),
                                'delta_star_i_x95': float(best['delta']),
                                'min_loss_eng': float(best['loss_eng'])})
l5_df = pd.DataFrame(l5_data)
l5_j = float(np.sqrt(l5_df['min_loss_eng'].mean()))
l5 = {'level': 'L5', 'RMSE_x95': l5_j, 'n_samples': len(l5_df)}
l5_df.to_csv(DATA_DIR / 'E03_L5_per_sample_x095.csv', index=False, encoding='utf-8-sig')

# ── Default ──
def_losses = []
for key in all_keys:
    df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{key[0]}_n{key[1]}_gamma{key[2]}.csv')
    gamma_t = key[2] * ETA; x95_t = gamma_t + ETA * C[BETAS.index(key[0])]
    sub = df[df['delta'] == 0.1]
    xh = x95_hat(sub['beta_hat'].values, sub['eta_hat'].values, sub['gamma_hat'].values, key[0])
    def_losses.extend(((xh - x95_t)**2).tolist())
def_j = float(np.sqrt(np.mean(def_losses)))

# ── Output ──
print(f"\n{'='*55}")
print(f"  RMSE_x95 ladder (absolute, eta=1)")
print(f"{'='*55}")
print(f"{'Level':<10} {'RMSE_x95':>10} {'vs Default':>12}")
for name, j in [('Default', def_j), ('L0', l0['RMSE_x95']), ('L1', l1_j), ('L2', l2_j), ('L3', l3_j), ('L4', l4_j), ('L5', l5_j)]:
    print(f"{name:<10} {j:>10.4f} {(j-def_j)/def_j*100:>+11.1f}%")
print(f"\nL0 delta* = {l0['delta_star']:.2f}")

# Save curves (same format as J_param versions)
def save_curves(name, configs_fn):
    al = aggregate_mean_loss(configs_fn(all_keys))
    df = pd.DataFrame({'delta': list(al.keys()), 'RMSE_x95': [np.sqrt(v) for v in al.values()]})
    df.to_csv(DATA_DIR / f'E03_L0_curve_x095.csv', index=False)

# By-n curves
for n in NS:
    ks = [k for k in all_keys if k[1] == n]
    al = aggregate_mean_loss(ks)
    pd.DataFrame({'delta': list(al.keys()), 'RMSE_x95': [np.sqrt(v) for v in al.values()]}).to_csv(DATA_DIR / f'E03_L1_curve_n{n}_x095.csv', index=False)

# By-beta curves  
for beta in BETAS:
    ks = [k for k in all_keys if k[0] == beta]
    al = aggregate_mean_loss(ks)
    pd.DataFrame({'delta': list(al.keys()), 'RMSE_x95': [np.sqrt(v) for v in al.values()]}).to_csv(DATA_DIR / f'E03_L2_curve_b{beta}_x095.csv', index=False)

# Heatmaps
l3_mat = pd.DataFrame(index=NS, columns=BETAS)
for (b, n), r in l3_res.items(): l3_mat.loc[n, b] = r['delta_star']
l3_mat.to_csv(DATA_DIR / 'E03_L3_heatmap_x095.csv')

for gr in GERS:
    mat = pd.DataFrame(index=NS, columns=BETAS)
    for (b, n, g), r in l4_res.items():
        if g == gr: mat.loc[n, b] = r['delta_star']
    mat.to_csv(DATA_DIR / f'E03_L4_heatmap_gamma{gr}_x095.csv')

# Ladder
pd.DataFrame([{'Level': n, 'RMSE_x95': j, 'vs_Default': (j-def_j)/def_j*100}
              for n, j in [('Default', def_j), ('L0', l0['RMSE_x95']), ('L1', l1_j),
                           ('L2', l2_j), ('L3', l3_j), ('L4', l4_j), ('L5', l5_j)]]
).to_csv(DATA_DIR / 'E03_ladder_x095.csv', index=False, encoding='utf-8-sig')

results = {'default': def_j, 'l0': l0, 'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4, 'l5': l5}
with open(DATA_DIR / 'E03_level_results_x095.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\nDone. All _x095 files written.")
