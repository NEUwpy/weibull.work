"""
E03 视角错配: 我用 J_param 最优 δ 去估 MDM，用 x95 口径评价，差了多少？
+ E03-4a/4b x95 方向1/2
"""
import pandas as pd, numpy as np
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTAS = np.arange(0, 0.51, 0.02)
C = {b: (-np.log(0.95))**(1.0/b) for b in BETAS}

def x95_from_sub(df, beta):
    """vectorized x95 computation"""
    c = (-np.log(0.95))**(1.0/np.maximum(df['beta_hat'].values, 0.1))
    return df['gamma_hat'].values + df['eta_hat'].values * c

# ── Load dual-perspective optimal deltas ──
j_l4 = {}; j_l5 = {}
ldf = pd.read_csv(DATA_DIR / 'E03_L4_heatmap_gamma0.1_v2.csv', index_col=0)
for n_s in ldf.index:
    for b_s in ldf.columns:
        j_l4[(float(b_s), int(n_s), 0.1)] = ldf.loc[n_s, b_s]
for gr in [0.5, 1.0]:
    m = pd.read_csv(DATA_DIR / f'E03_L4_heatmap_gamma{gr}_v2.csv', index_col=0)
    for n_s in m.index:
        for b_s in m.columns:
            j_l4[(float(b_s), int(n_s), gr)] = m.loc[n_s, b_s]
j_l4_from = pd.read_csv(DATA_DIR / 'E03_L4_heatmap_gamma0.1_x095.csv', index_col=0)
x_l4 = {}
for gr in GERS:
    m = pd.read_csv(DATA_DIR / f'E03_L4_heatmap_gamma{gr}_x095.csv', index_col=0)
    for n_s in m.index:
        for b_s in m.columns:
            x_l4[(float(b_s), int(n_s), gr)] = m.loc[n_s, b_s]
jl5 = pd.read_csv(DATA_DIR / 'E03_L5_per_sample_v2.csv')
xl5 = pd.read_csv(DATA_DIR / 'E03_L5_per_sample_x095.csv')

# ── Mismatch per config (L4 level) ──
print("=== Mismatch analysis ===")
rows = []
for beta in BETAS:
    for n in NS:
        for gr in GERS:
            df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            gamma_t = gr * ETA; x95_true = gamma_t + ETA * C[beta]
            # Optimal x95 δ
            ds_x = x_l4[(beta, n, gr)]
            # J-optimal δ (what you'd use if you optimized J but care about x95)
            ds_j = j_l4[(beta, n, gr)]
            # Evaluate RMSE_x95 at both
            for ds, label in [(ds_x, 'x95_opt'), (ds_j, 'J_opt')]:
                sub = df[df['delta'] == ds]
                if len(sub) == 0: continue
                xh = x95_from_sub(sub, beta)
                loss = np.mean((xh - x95_true)**2)
                rows.append({'beta': beta, 'n': n, 'gamma_eta': gr,
                             'delta_type': label, 'delta': ds,
                             'mean_loss': loss, 'RMSE_x95': np.sqrt(loss)})
mismatch_df = pd.DataFrame(rows)
mismatch_df.to_csv(DATA_DIR / 'E03_mismatch.csv', index=False, encoding='utf-8-sig')

# Summarize
summary = mismatch_df.pivot_table(index=['beta','n','gamma_eta'], columns='delta_type', values='RMSE_x95').reset_index()
summary['penalty'] = summary['J_opt'] - summary['x95_opt']
print(f"Mean mismatch penalty (RMSE_x95): {summary['penalty'].mean():.6f}")
print(f"Max penalty: {summary['penalty'].max():.6f}")
print(f"Penalty as % of Default: {summary['penalty'].mean()/0.1407*100:.1f}%")

# ── Direction 1: self-iteration with RMSE_x95 ──
print("\n=== Direction 1: Self-iteration (x95) ===")
l3_x = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_x095.csv', index_col=0)
l3_lookup = {}
for n_s in l3_x.index:
    for b_s in l3_x.columns:
        l3_lookup[(float(b_s), int(n_s))] = l3_x.loc[n_s, b_s]

from scipy.interpolate import interp1d
def delta_from_beta(bh, n):
    bs = sorted([float(c) for c in l3_x.columns])
    ds = [l3_lookup[(b, n)] for b in bs]
    return float(np.interp(np.clip(bh, bs[0], bs[-1]), bs, ds))

it_rows = []
for beta in BETAS:
    for n in NS:
        for gr in GERS:
            df = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            gamma_t = gr * ETA; x95_t = gamma_t + ETA * C[beta]
            for rep in df['rep'].unique():
                rd = df[df['rep'] == rep]
                # Default
                d0 = rd[rd['delta'] == 0.1]
                if len(d0) == 0: continue
                xh0 = x95_from_sub(d0, beta)
                loss0 = np.mean((xh0 - x95_t)**2)
                # Iterate
                d_cur = 0.1
                for _ in range(10):
                    rk = rd[rd['delta'] == round(d_cur, 2)]
                    if len(rk) == 0: break
                    bh = rk['beta_hat'].values[0]
                    d_new = round(delta_from_beta(bh, n), 2)
                    if abs(d_new - d_cur) < 0.005: break
                    d_cur = d_new
                rf = rd[rd['delta'] == d_cur]
                if len(rf) == 0: continue
                xhf = x95_from_sub(rf, beta)
                lossf = np.mean((xhf - x95_t)**2)
                it_rows.append({'beta': beta, 'n': n, 'gamma_eta': gr, 'rep': int(rep),
                                'loss_default': loss0, 'loss_iter': lossf, 'final_delta': d_cur})
it_df = pd.DataFrame(it_rows)
it_summary = it_df.groupby(['beta','n','gamma_eta']).agg(
    RMSE_default=('loss_default', lambda x: np.sqrt(np.mean(x))),
    RMSE_iter=('loss_iter', lambda x: np.sqrt(np.mean(x))),
).reset_index()
it_summary['improvement'] = (it_summary['RMSE_default']-it_summary['RMSE_iter'])/it_summary['RMSE_default']*100
it_summary.to_csv(DATA_DIR / 'E03-4a_summary_x095.csv', index=False, encoding='utf-8-sig')
ov_def = np.sqrt(it_df['loss_default'].mean())
ov_it = np.sqrt(it_df['loss_iter'].mean())
print(f"Overall: Default={ov_def:.4f}, Iter={ov_it:.4f}, improvement={(ov_def-ov_it)/ov_def*100:+.1f}%")

# ── Direction 2: external β (x95 evaluation) ──
print("\n=== Direction 2: External beta (x95 eval) ===")
d2 = pd.read_csv(DATA_DIR / 'E03-4b_v3_per_sample.csv')
d2j = pd.read_csv(DATA_DIR / 'E03-4b_v3_overall.csv')
d2_summary = d2.groupby(['beta','n','gamma_eta','method']).agg(mean_loss=('loss_i','mean')).reset_index()
# Convert loss_i (J_param loss) to RMSE_x95 by looking up MDM results
# We can't directly convert J-param losses to x95 losses without re-evaluating
# Instead, we compute x95 RMSE for each method's predicted δ
x95_by_method = {}
for method in d2['method'].unique():
    losses = []
    for _, row in d2[d2['method'] == method].iterrows():
        key = (row['beta'], int(row['n']), row['gamma_eta'])
        # The loss_i in the file is J-param loss. For x95 we need MDM results.
        # Since we can't recover the predicted δ from the existing data,
        # we can only compute x95 for the 'oracle' and 'default' methods
        pass
    # Skip detailed x95 conversion for external β - the existing data only has J-param losses
print("Direction 2 x95: requires re-running estimation with x95 lookup. Skipping for now (J-param losses can't be converted to x95).")

# Summary
print(f"\nMismatch penalty: mean={summary['penalty'].mean():.4f}, max={summary['penalty'].max():.4f}")
print(f"Direction 1 x95: Default={ov_def:.4f}, Iter={ov_it:.4f}, { (ov_def-ov_it)/ov_def*100:+.1f}%")

import json; json.dump({'default': float(ov_def), 'iterated': float(ov_it), 'improvement_pct': float((ov_def-ov_it)/ov_def*100)}, open(DATA_DIR/'E03-4a_overall_x095.json','w')); print('Saved E03-4a_overall_x095.json')