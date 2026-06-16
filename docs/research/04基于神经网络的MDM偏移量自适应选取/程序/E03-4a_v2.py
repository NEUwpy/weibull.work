"""
E03-4a v2: MDM自迭代方案 — 从现有delta sweep数据模拟迭代过程
按新口径计算 J_param
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
OUT_DIR = DATA_DIR

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GAMMA_RATIOS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTA_GRID = np.arange(0, 0.51, 0.02)
MAX_ITERS = 20
CONVERGENCE_TOL = 0.005

# Load L3 lookup table (β,n -> δ*)
l3_mat = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_v2.csv', index_col=0)
l3_lookup = {}
for n_str in l3_mat.index:
    for beta_str in l3_mat.columns:
        l3_lookup[(float(beta_str), int(n_str))] = l3_mat.loc[n_str, beta_str]

def delta_star_lookup(beta_hat, n):
    """Find δ* for given (β̂, n) by nearest neighbor or interpolation"""
    betas_known = sorted(set(k[0] for k in l3_lookup if k[1] == n))
    deltas_known = [l3_lookup[(b, n)] for b in betas_known]
    if len(betas_known) >= 2:
        f = interp1d(betas_known, deltas_known, kind='linear', bounds_error=False,
                      fill_value=(deltas_known[0], deltas_known[-1]))
        return float(np.clip(f(beta_hat), 0, 0.5))
    return float(deltas_known[0])

def load_sweep(beta, n, gr):
    fpath = DATA_DIR / f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv"
    return pd.read_csv(fpath)

def compute_loss(row, beta, gr):
    gamma_true = gr * ETA
    return ((row['beta_hat'] - beta) / beta)**2 + \
           ((row['eta_hat'] - ETA) / ETA)**2 + \
           ((row['gamma_hat'] - gamma_true) / ETA)**2

def run_iteration(df, beta, n, gr):
    """Simulate self-iteration: δ=0.1 → β̂ → δ* → β̂ → ... for each rep"""
    reps = df['rep'].unique()
    rows_out = []
    gamma_true = gr * ETA
    
    for rep in reps:
        rep_data = df[df['rep'] == rep]
        rep_dict = rep_data.set_index('delta').to_dict('index')
        
        # Default δ=0.1
        d_default = 0.1
        row_default = rep_dict.get(d_default)
        if row_default is None:
            continue
        loss_default = ((row_default['beta_hat']-beta)/beta)**2 + \
                       ((row_default['eta_hat']-ETA)/ETA)**2 + \
                       ((row_default['gamma_hat']-gamma_true)/ETA)**2
        
        # Iteration
        current_delta = d_default
        converged = False
        n_iters = 0
        delta_history = [current_delta]
        
        while not converged and n_iters < MAX_ITERS:
            row = rep_dict.get(round(current_delta, 2))
            if row is None:
                # Nearest delta
                available = sorted(rep_dict.keys())
                nearest = min(available, key=lambda x: abs(x - current_delta))
                row = rep_dict[nearest]
            
            beta_hat = row['beta_hat']
            new_delta = round(delta_star_lookup(beta_hat, n), 2)
            new_delta = float(np.clip(new_delta, 0, 0.5))
            
            if abs(new_delta - current_delta) < CONVERGENCE_TOL:
                converged = True
            else:
                current_delta = new_delta
                delta_history.append(current_delta)
                n_iters += 1
        
        # Final evaluation at converged delta
        final_delta = current_delta
        row_final = rep_dict.get(round(final_delta, 2))
        if row_final is None:
            available = sorted(rep_dict.keys())
            nearest = min(available, key=lambda x: abs(x - final_delta))
            row_final = rep_dict[nearest]
            final_delta = nearest
        
        loss_final = ((row_final['beta_hat']-beta)/beta)**2 + \
                     ((row_final['eta_hat']-ETA)/ETA)**2 + \
                     ((row_final['gamma_hat']-gamma_true)/ETA)**2
        
        rows_out.append({
            'beta': beta, 'n': n, 'gamma_ratio': gr, 'rep': int(rep),
            'loss_default': loss_default,
            'loss_iterated': loss_final,
            'final_delta': final_delta,
            'n_iterations': n_iters,
            'converged': converged,
        })
    
    return pd.DataFrame(rows_out)


print("=== E03-4a v2: Self-iteration ===")
all_results = []

for beta in BETAS:
    for n in NS:
        for gr in GAMMA_RATIOS:
            df = load_sweep(beta, n, gr)
            res = run_iteration(df, beta, n, gr)
            all_results.append(res)
            print(f"  β={beta}, n={n}, γ/η={gr}: {len(res)} samples")

results_df = pd.concat(all_results, ignore_index=True)
results_df.to_csv(OUT_DIR / 'E03-4a_self_iteration_v2.csv', index=False, encoding='utf-8-sig')

# Aggregate by config
summary = results_df.groupby(['beta', 'n', 'gamma_ratio']).agg(
    J_param_default=('loss_default', lambda x: np.sqrt(np.mean(x))),
    J_param_iterated=('loss_iterated', lambda x: np.sqrt(np.mean(x))),
    mean_final_delta=('final_delta', 'mean'),
    n_samples=('rep', 'count'),
    converged_rate=('converged', 'mean'),
).reset_index()
summary['improvement'] = (summary['J_param_default'] - summary['J_param_iterated']) / summary['J_param_default'] * 100
summary.to_csv(OUT_DIR / 'E03-4a_summary_v2.csv', index=False, encoding='utf-8-sig')

# Overall
overall_default = np.sqrt(results_df['loss_default'].mean())
overall_iter = np.sqrt(results_df['loss_iterated'].mean())
print(f"\nOverall Default J_param = {overall_default:.4f}")
print(f"Overall Iterated J_param = {overall_iter:.4f}")
print(f"Overall improvement = {(overall_default - overall_iter)/overall_default*100:.1f}%")
print(f"Improvement rate = {(summary['improvement'] > 0).mean()*100:.1f}%")

# By beta
print("\nBy β:")
for beta in BETAS:
    sub = summary[summary['beta'] == beta]
    avg_imp = sub['improvement'].mean()
    print(f"  β={beta}: avg improvement = {avg_imp:+.1f}%")
