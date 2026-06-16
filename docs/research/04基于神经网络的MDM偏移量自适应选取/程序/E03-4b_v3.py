"""
E03-4b v3: 外部β预估方法对比（新口径 + 新 L3 表）
方法: Oracle(真β), L-moment, WMLE, MDM δ=0, Dual-δ avg
输出: 逐样本 loss + 按配置汇总 + 整体阶梯，J_param = sqrt(mean(mean_loss))
"""
import sys, numpy as np, pandas as pd, os, time
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
SCRIPT_DIR = BASE / "程序"

sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")
sys.path.insert(0, str(SCRIPT_DIR))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from scipy.optimize import brentq

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
N_REPS = 500
ETA = 1.0

# ---- New L3 lookup table (β,n → δ*) ----
l3_mat = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_v2.csv', index_col=0)
l3_data = {}
for n_str in l3_mat.index:
    n = int(n_str)
    l3_data[n] = []
    for b_str in l3_mat.columns:
        l3_data[n].append((float(b_str), l3_mat.loc[n_str, b_str]))
    l3_data[n].sort()

def delta_from_beta(beta_hat, n):
    bs, ds = zip(*l3_data[n])
    return float(np.interp(np.clip(beta_hat, bs[0], bs[-1]), bs, ds))

DELTA_GRID = [round(d, 2) for d in np.arange(0, 0.51, 0.02)]
def nearest_delta(d):
    return min(DELTA_GRID, key=lambda x: abs(x - d))

# ---- Pre-load sweep data (fast lookup by delta+rep) ----
print("Pre-loading sweep data...")
sweep = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            df = pd.read_csv(DATA_DIR / fname)
            lookup = {}
            for d in DELTA_GRID:
                sub = df[(df['delta'] == d) & (df['status'] == True)]
                for _, row in sub.iterrows():
                    lookup[(d, int(row['rep']))] = (row['beta_hat'], row['eta_hat'], row['gamma_hat'])
            sweep[(beta, n, ger)] = lookup
print(f"Loaded {len(sweep)} configs")

# ---- L-moments β estimation ----
def estimate_beta_lmoments(sample):
    n = len(sample)
    pwm = np.zeros(3)
    for j in range(3):
        numer = np.array([np.prod([(i - k)/(n - k) for k in range(j)]) for i in range(1, n+1)])
        pwm[j] = np.sum(sample * numer) / n
    l1, l2, l3 = pwm[0], 2*pwm[1]-pwm[0], 6*pwm[2]-6*pwm[1]+pwm[0]
    if l2 <= 1e-12: return np.nan
    t3 = l3 / l2
    def tau3_func(b):
        p = 1.0 + 1.0/max(b, 0.2)
        return (1.0 - 6.0*2.0**(-p) + 6.0*3.0**(-p)) / (1.0 - 2.0**(-p))
    try:
        if t3 <= tau3_func(20.0) or t3 >= tau3_func(0.3): return np.nan
        return brentq(lambda b: tau3_func(b) - t3, 0.3, 20.0)
    except:
        return np.nan

# ---- Main ----
print("\nRunning external beta estimation (L-moment, WMLE, MDM0, Dual, Oracle)...")
all_rows = []
total = len(BETAS) * len(NS) * len(GERS)

for ci, (beta_t, n, ger) in enumerate([(b, n, g) for b in BETAS for n in NS for g in GERS]):
    gamma_t = ger * ETA
    lookup = sweep[(beta_t, n, ger)]
    t0 = time.time()
    
    for rep in range(N_REPS):
        sample = generate_sample(beta_t, ETA, gamma_t, n, rep)
        
        # ---- Oracle (true β) ----
        d_star = nearest_delta(delta_from_beta(beta_t, n))
        if (d_star, rep) in lookup:
            bh, eh, gh = lookup[(d_star, rep)]
            loss_o = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
            all_rows.append({'beta': beta_t, 'n': n, 'gamma_eta': ger, 'rep': rep,
                             'method': 'oracle', 'loss_i': loss_o})
        
        # ---- MDM δ=0 ----
        if (0.0, rep) in lookup:
            bh0, _, _ = lookup[(0.0, rep)]
            d_star = nearest_delta(delta_from_beta(bh0, n))
            if (d_star, rep) in lookup:
                bh, eh, gh = lookup[(d_star, rep)]
                loss = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
                all_rows.append({'beta': beta_t, 'n': n, 'gamma_eta': ger, 'rep': rep,
                                 'method': 'mdm0', 'loss_i': loss})
        
        # ---- Dual-δ avg ----
        if (0.02, rep) in lookup and (0.10, rep) in lookup:
            bh_low = lookup[(0.02, rep)][0]
            bh_high = lookup[(0.10, rep)][0]
            beta_dual = (bh_low + bh_high)/2
            d_star = nearest_delta(delta_from_beta(beta_dual, n))
            if (d_star, rep) in lookup:
                bh, eh, gh = lookup[(d_star, rep)]
                loss = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
                all_rows.append({'beta': beta_t, 'n': n, 'gamma_eta': ger, 'rep': rep,
                                 'method': 'dual', 'loss_i': loss})
        
        # ---- L-moments ----
        beta_lm = estimate_beta_lmoments(sample)
        if not np.isnan(beta_lm):
            d_star = nearest_delta(delta_from_beta(beta_lm, n))
            if (d_star, rep) in lookup:
                bh, eh, gh = lookup[(d_star, rep)]
                loss = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
                all_rows.append({'beta': beta_t, 'n': n, 'gamma_eta': ger, 'rep': rep,
                                 'method': 'lmom', 'loss_i': loss})
        
        # ---- WMLE ----
        try:
            wmle_res = run_method('wmle', sample)
            if wmle_res.get('converged', False):
                d_star = nearest_delta(delta_from_beta(wmle_res['beta_hat'], n))
                if (d_star, rep) in lookup:
                    bh, eh, gh = lookup[(d_star, rep)]
                    loss = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
                    all_rows.append({'beta': beta_t, 'n': n, 'gamma_eta': ger, 'rep': rep,
                                     'method': 'wmle', 'loss_i': loss})
        except:
            pass
    
    t1 = time.time()
    print(f"  [{ci+1}/{total}] beta={beta_t} n={n} g={ger}  {t1-t0:.1f}s")

# ---- Aggregate ----
print("\nAggregating...")
df = pd.DataFrame(all_rows)
df.to_csv(DATA_DIR / 'E03-4b_v3_per_sample.csv', index=False, encoding='utf-8-sig')

# Per-config per-method: mean_loss → J_param = sqrt(mean_loss)
config_summary = df.groupby(['beta', 'n', 'gamma_eta', 'method']).agg(
    mean_loss=('loss_i', 'mean'),
    n_valid=('rep', 'count'),
).reset_index()
config_summary['J_param'] = np.sqrt(config_summary['mean_loss'])
config_summary.to_csv(DATA_DIR / 'E03-4b_v3_config.csv', index=False, encoding='utf-8-sig')

# Overall per method: J_param = sqrt(mean(mean_loss across configs))
overall = config_summary.groupby('method').agg(
    avg_mean_loss=('mean_loss', 'mean'),
    total_valid=('n_valid', 'sum'),
    n_configs=('mean_loss', 'count'),
).reset_index()
overall['J_param'] = np.sqrt(overall['avg_mean_loss'])
overall['valid_rate'] = overall['total_valid'] / (total * N_REPS) * 100

# Default δ=0.1 baseline: pull losses directly
default_losses = []
for beta_t in BETAS:
    for n in NS:
        for ger in GERS:
            lookup = sweep[(beta_t, n, ger)]
            gamma_t = ger * ETA
            for rep in range(N_REPS):
                if (0.10, rep) in lookup:
                    bh, eh, gh = lookup[(0.10, rep)]
                    loss = ((bh-beta_t)/beta_t)**2 + ((eh-ETA)/ETA)**2 + ((gh-gamma_t)/ETA)**2
                    default_losses.append(loss)
default_J = np.sqrt(np.mean(default_losses))
default_row = pd.DataFrame([{'method': 'default', 'J_param': default_J, 'total_valid': len(default_losses), 'n_configs': total, 'valid_rate': 100.0}])
overall = pd.concat([overall, default_row], ignore_index=True)

# Sort by J_param
overall = overall.sort_values('J_param')
overall.to_csv(DATA_DIR / 'E03-4b_v3_overall.csv', index=False, encoding='utf-8-sig')

# Print summary
print(f"\n{'='*65}")
print(f"Overall J_param by method (config-equal weight)")
print(f"{'='*65}")
print(f"{'Method':<12} {'J_param':>8} {'vs Default':>12} {'Valid%':>8}")
print(f"{'-'*45}")
for _, row in overall.iterrows():
    vs_def = (row['J_param'] - default_J) / default_J * 100
    print(f"{row['method']:<12} {row['J_param']:>8.4f} {vs_def:>+11.1f}% {row['valid_rate']:>7.1f}%")

print(f"\nDefault J_param = {default_J:.4f}")
print(f"Saved: E03-4b_v3_per_sample.csv, E03-4b_v3_config.csv, E03-4b_v3_overall.csv")
