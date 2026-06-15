"""
E03-4a self-iteration trajectory viz (5 beta, expanded grid)
"""
import sys, numpy as np, pandas as pd, matplotlib.pyplot as plt, os

BASE = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE, "实验数据")
IMG_DIR = os.path.join(BASE, "图像")
os.makedirs(IMG_DIR, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'figure.dpi': 200, 'savefig.dpi': 200, 'font.size': 9
})

l3_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))
l3 = l3_df[l3_df['level'] == 'L3'].copy()

def parse(g):
    parts = g.split('_')
    return float(parts[0].split('=')[1]), int(parts[1].split('=')[1])

l3_lookup = {}
for _, row in l3.iterrows():
    beta, n = parse(row['group'])
    l3_lookup[(n, beta)] = row['optimal_delta']

BETA_VALUES = [1.5, 2.0, 2.5, 4.0, 5.0]
L2_OPTIMAL = {1.5: 0.40, 2.0: 0.20, 2.5: 0.12, 4.0: 0.04, 5.0: 0.04}
DELTA_VALUES = np.arange(0, 0.52, 0.02)
ETA_TRUE = 1.0

def nearest_delta(d):
    return min(DELTA_VALUES, key=lambda x: abs(x - d))

def delta_from_beta(beta_hat, n):
    bs, ds = zip(*sorted([(b, d) for (nn, b), d in l3_lookup.items() if nn == n]))
    return float(np.interp(np.clip(beta_hat, bs[0], bs[-1]), bs, ds))

def compute_jparam(bh, eh, gh, beta_true, gamma_true):
    tb = ((bh - beta_true) / beta_true) ** 2
    te = ((eh - ETA_TRUE) / ETA_TRUE) ** 2
    tg = ((gh - gamma_true) / ETA_TRUE) ** 2
    return np.sqrt(np.mean(tb + te + tg))

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]

all_data = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            all_data[(beta, n, ger)] = pd.read_csv(os.path.join(DATA_DIR, fname))

trajectories = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            df = all_data[(beta, n, ger)]
            jparam_curve = {}
            for d in DELTA_VALUES:
                rows = df[(df['delta'] == d) & (df['status'] == True)]
                if len(rows) == 0:
                    continue
                jparam_curve[d] = compute_jparam(rows['beta_hat'].values, rows['eta_hat'].values, rows['gamma_hat'].values, beta, gamma_true)
            delta_current = 0.10
            traj = []
            for it in range(15):
                dk = nearest_delta(delta_current)
                if dk not in jparam_curve:
                    break
                rows = df[(df['delta'] == dk) & (df['status'] == True)]
                jp = compute_jparam(rows['beta_hat'].values, rows['eta_hat'].values, rows['gamma_hat'].values, beta, gamma_true)
                bm = np.mean(rows['beta_hat'].values)
                traj.append({'iter': it, 'delta': dk, 'jparam': jp, 'beta_hat': bm})
                d_next = delta_from_beta(bm, n)
                delta_current = delta_current + 0.6 * (d_next - delta_current)
                delta_current = max(0.0, min(0.5, delta_current))
                if abs(d_next - delta_current) < 0.001:
                    break
            trajectories[(beta, n, ger)] = (traj, jparam_curve)

# Figure 1: 5-panel trajectories (n=10)
fig, axes = plt.subplots(1, 5, figsize=(24, 4.5))
n_show = 10
for idx, beta in enumerate(BETAS):
    ax = axes[idx]
    for ger in GERS:
        traj, curve = trajectories[(beta, n_show, ger)]
        ds = sorted(curve.keys())
        js = [curve[d] for d in ds]
        color = {0.1: '#1f77b4', 0.5: '#ff7f0e', 1.0: '#2ca02c'}[ger]
        ax.plot(ds, js, '-', color=color, alpha=0.25, linewidth=1)
        t_deltas = [t['delta'] for t in traj]
        t_js = [t['jparam'] for t in traj]
        ax.plot(t_deltas, t_js, 'o-', color=color, linewidth=2, markersize=5, label=f'g={ger}')
        ax.plot(t_deltas[0], t_js[0], 's', color=color, markersize=7)
        ax.plot(t_deltas[-1], t_js[-1], 'D', color=color, markersize=7)
    ax.axvline(x=L2_OPTIMAL[beta], color='red', linestyle='--', alpha=0.5, label='L2 opt')
    ax.axvline(x=0.10, color='gray', linestyle=':', alpha=0.4, label='default')
    ax.set_title(f'beta = {beta}')
    ax.set_xlabel('delta')
    if idx == 0:
        ax.set_ylabel('J_param')
        ax.legend(fontsize=6)
    ax.grid(True, alpha=0.3)
plt.suptitle('Self-Iteration Trajectories (n=10, expanded grid)', fontsize=12, y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4a_trajectories_v2.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4a_trajectories_v2.png")

# Figure 2: improvement heatmap (5 beta x 3 n)
fig, ax = plt.subplots(figsize=(16, 4))
heat_data = np.zeros((len(NS), len(BETAS) * len(GERS)))
annot = [['' for _ in range(15)] for _ in range(3)]
for ri, n in enumerate(NS):
    for ci, beta in enumerate(BETAS):
        for gi, ger in enumerate(GERS):
            col = ci * 3 + gi
            traj, _ = trajectories[(beta, n, ger)]
            if traj:
                impr = (traj[-1]['jparam'] - traj[0]['jparam']) / traj[0]['jparam'] * 100
                heat_data[ri, col] = impr
                annot[ri][col] = f'{impr:+.1f}%'
            else:
                heat_data[ri, col] = np.nan
                annot[ri][col] = 'N/A'
im = ax.imshow(heat_data, cmap='RdYlGn', aspect='auto', vmin=-30, vmax=30)
ax.set_yticks(range(3))
ax.set_yticklabels([f'n={n}' for n in NS])
xlabels = []
for beta in BETAS:
    for ger in GERS:
        xlabels.append(f'b={beta}\ng={ger}')
ax.set_xticks(range(15))
ax.set_xticklabels(xlabels, fontsize=6)
for ri in range(3):
    for ci in range(15):
        c = 'white' if abs(heat_data[ri, ci]) > 15 else 'black'
        ax.text(ci, ri, annot[ri][ci], ha='center', va='center', fontsize=6, color=c)
plt.colorbar(im, ax=ax, label='Improvement (%)')
ax.set_title('Self-Iteration Improvement Heatmap (expanded grid)')
plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4a_improvement_heatmap.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4a_improvement_heatmap.png")
print("Done.")
