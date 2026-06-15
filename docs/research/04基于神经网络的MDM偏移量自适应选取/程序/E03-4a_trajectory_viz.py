"""
E03-4a 自迭代轨迹可视化 v2：连续插值版
用 δ*(β) 的连续插值代替 nearest_beta 三档跳，展示完整漂移趋势
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

# ---- Build continuous δ*(β) interpolator per n ----
l3_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))
l3 = l3_df[l3_df['level'] == 'L3'].copy()

def parse(g):
    parts = g.split('_')
    return float(parts[0].split('=')[1]), int(parts[1].split('=')[1])

l3_data = {}  # n -> [(beta, delta_star), ...] sorted by beta
for _, row in l3.iterrows():
    beta, n = parse(row['group'])
    l3_data.setdefault(n, []).append((beta, row['optimal_delta']))
for n in l3_data:
    l3_data[n].sort()

def delta_star_from_beta(beta_hat, n):
    """Linear interpolation of L3 delta* from estimated beta"""
    bs, ds = zip(*l3_data[n])
    if beta_hat <= bs[0]:
        return ds[0]
    if beta_hat >= bs[-1]:
        return ds[-1]
    return float(np.interp(beta_hat, bs, ds))

DELTA_VALUES = np.arange(0, 0.52, 0.02)
ETA_TRUE = 1.0

def nearest_delta(d):
    return min(DELTA_VALUES, key=lambda x: abs(x - d))

def compute_jparam(bh, eh, gh, beta_true, gamma_true):
    tb = ((bh - beta_true) / beta_true) ** 2
    te = ((eh - ETA_TRUE) / ETA_TRUE) ** 2
    tg = ((gh - gamma_true) / ETA_TRUE) ** 2
    return np.sqrt(np.mean(tb + te + tg))

# ---- Load data ----
BETAS = [2.0, 2.5, 4.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
all_data = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            all_data[(beta, n, ger)] = pd.read_csv(os.path.join(DATA_DIR, fname))

# ---- Run interpolated self-iteration (up to 15 steps) ----
print("Interpolated self-iteration (up to 15 steps)...")
trajectories = {}

for beta in BETAS:
    for n in NS:
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            df = all_data[(beta, n, ger)]
            jparam_curve = {}  # delta -> jparam (for the full curve)
            for d in DELTA_VALUES:
                rows = df[(df['delta'] == d) & (df['status'] == True)]
                if len(rows) == 0:
                    continue
                jparam_curve[d] = compute_jparam(
                    rows['beta_hat'].values, rows['eta_hat'].values,
                    rows['gamma_hat'].values, beta, gamma_true)

            delta_current = 0.10
            traj = []

            for it in range(15):
                dk = nearest_delta(delta_current)
                if dk not in jparam_curve:
                    break
                rows = df[(df['delta'] == dk) & (df['status'] == True)]
                bh = rows['beta_hat'].values
                eh = rows['eta_hat'].values
                gh = rows['gamma_hat'].values
                jp = compute_jparam(bh, eh, gh, beta, gamma_true)
                bm = np.mean(bh)
                traj.append({'iter': it, 'delta': dk, 'jparam': jp, 'beta_hat': bm})

                # Use continuous delta*(beta_hat) via interpolation
                d_next = delta_star_from_beta(bm, n)
                # Damping: only move 60% toward the suggested delta each step
                delta_current = delta_current + 0.6 * (d_next - delta_current)
                # Clip to valid range
                delta_current = max(0.0, min(0.5, delta_current))

                if abs(d_next - delta_current) < 0.001:
                    # Converged
                    traj.append({'iter': it+1, 'delta': nearest_delta(delta_current),
                                 'jparam': jparam_curve.get(nearest_delta(delta_current), jp),
                                 'beta_hat': bm, 'converged': True})
                    break

            trajectories[(beta, n, ger)] = (traj, jparam_curve)
            impr = ((traj[-1]['jparam'] - traj[0]['jparam']) / traj[0]['jparam'] * 100) if traj else 0
            print(f"  beta={beta} n={n} g={ger}: {len(traj)} iters, "
                  f"J {traj[0]['jparam']:.3f} -> {traj[-1]['jparam']:.3f} ({impr:+.1f}%)")

# ---- Figure 1: Trajectories with full J_param curves (one per beta) ----
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

for idx, beta in enumerate(BETAS):
    ax = axes[idx]

    # Plot 3 representative configs per beta (pick middle n=10, all 3 gamma)
    n_show = 10
    for ger in GERS:
        traj, curve = trajectories[(beta, n_show, ger)]

        # Full J_param curve
        ds = sorted(curve.keys())
        js = [curve[d] for d in ds]
        color = {0.1: '#1f77b4', 0.5: '#ff7f0e', 1.0: '#2ca02c'}[ger]
        ax.plot(ds, js, '-', color=color, alpha=0.3, linewidth=1)

        # Trajectory points
        t_deltas = [t['delta'] for t in traj]
        t_js = [t['jparam'] for t in traj]
        ax.plot(t_deltas, t_js, 'o-', color=color, linewidth=2, markersize=6,
                label=f'g/eta={ger}')
        # Mark start and end
        ax.plot(t_deltas[0], t_js[0], 's', color=color, markersize=8)
        ax.plot(t_deltas[-1], t_js[-1], 'D', color=color, markersize=8)

    # Mark global optimal delta for this beta
    ax.axvline(x={2.0: 0.20, 2.5: 0.12, 4.0: 0.04}[beta],
               color='red', linestyle='--', alpha=0.5, label='L2 optimal')
    # Mark default
    ax.axvline(x=0.10, color='gray', linestyle=':', alpha=0.5, label='default 0.1')

    ax.set_title(f'beta = {beta} (n=10)')
    ax.set_xlabel('delta')
    if idx == 0:
        ax.set_ylabel('J_param')
        ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

plt.suptitle('Self-Iteration Trajectories (interpolated, damped) vs Full J_param Curve',
             fontsize=12, y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4a_trajectories_v2.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4a_trajectories_v2.png")

# ---- Figure 2: All 27 configs, delta drift direction ----
fig, ax = plt.subplots(figsize=(10, 6))

for beta in BETAS:
    for n in NS:
        for ger in GERS:
            traj, _ = trajectories[(beta, n, ger)]
            if len(traj) < 2:
                continue
            d_start = traj[0]['delta']
            d_end = traj[-1]['delta']
            j_start = traj[0]['jparam']
            j_end = traj[-1]['jparam']
            impr = (j_end - j_start) / j_start * 100

            color = '#2ca02c' if impr < 0 else '#d62728'
            alpha = 0.7
            ax.arrow(d_start, j_start, d_end - d_start, j_end - j_start,
                     head_width=0.008, head_length=0.01, fc=color, ec=color,
                     alpha=alpha, length_includes_head=True)
            ax.plot(d_start, j_start, 'o', color=color, markersize=4)
            # Label with config
            label = f'b={beta},n={n},g={ger}'
            ax.annotate(label, (d_start, j_start), fontsize=5, alpha=0.6,
                        xytext=(3, 3), textcoords='offset points')

ax.axvline(x=0.10, color='gray', linestyle=':', alpha=0.5, label='default 0.1')
ax.set_xlabel('delta')
ax.set_ylabel('J_param')
ax.set_title('Delta Drift Direction: Green = Improve, Red = Worsen')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8)

plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4a_drift_direction.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4a_drift_direction.png")

print("\nDone.")
