"""
E03 c-space 分析：用 c = δ/s_v(β,n) 归一化坐标重做层级最优和部署阶梯
"""
import numpy as np
import pandas as pd
import os

BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")
IMG_DIR = os.path.join(BASE_DIR, "图像")
OUT_DIR = os.path.join(BASE_DIR, "实验数据")

# s_v table (Bernard median ranks)
SV_TABLE = {
    (1.5, 7): 1.4210, (1.5, 10): 1.6317, (1.5, 20): 2.0890,
    (2.0, 7): 0.8679, (2.0, 10): 0.9616, (2.0, 20): 1.1478,
    (2.5, 7): 0.6203, (2.5, 10): 0.6746, (2.5, 20): 0.7770,
    (4.0, 7): 0.3326, (4.0, 10): 0.3533, (4.0, 20): 0.3895,
    (5.0, 7): 0.2539, (5.0, 10): 0.2680, (5.0, 20): 0.2919,
}

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA_TRUE = 1.0
RAW_DELTAS = np.arange(0, 0.52, 0.02)

def compute_jparam_config(bh, eh, gh, beta, gamma_true):
    """J_param = sqrt(mean(squared errors))"""
    term_beta = ((bh - beta) / beta) ** 2
    term_eta = ((eh - ETA_TRUE) / ETA_TRUE) ** 2
    term_gamma = ((gh - gamma_true) / ETA_TRUE) ** 2
    return np.sqrt(np.mean(term_beta + term_eta + term_gamma))

print("=" * 60)
print("Step 1: Build c-space grid for each config")
print("=" * 60)

# For each config, compute c = δ/s_v and then a regular c-grid by interpolation
C_GRID = np.linspace(0, 0.60, 31)  # 0 to 0.60, step 0.02

all_c_jparam = {}  # (beta, n, ger, c) -> jparam

for beta in BETAS:
    sv = SV_TABLE[(beta, 7)]  # for display
    print(f"\nbeta={beta}: s_v range: n=7: {SV_TABLE[(beta,7)]:.4f}, "
          f"n=10: {SV_TABLE[(beta,10)]:.4f}, n=20: {SV_TABLE[(beta,20)]:.4f}")

for beta in BETAS:
    for n in NS:
        sv = SV_TABLE[(beta, n)]
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            df = pd.read_csv(os.path.join(DATA_DIR, fname))

            # For each raw delta, compute c = δ/s_v and jparam
            raw_c_jp = {}  # raw c -> jparam
            for d in RAW_DELTAS:
                c_val = d / sv if sv > 0 else d
                rows = df[(df['delta'] == d) & (df['status'] == True)]
                if len(rows) == 0:
                    continue
                bh = rows['beta_hat'].values
                eh = rows['eta_hat'].values
                gh = rows['gamma_hat'].values
                jp = compute_jparam_config(bh, eh, gh, beta, gamma_true)
                raw_c_jp[c_val] = jp

            # Interpolate to regular c-grid
            cs_sorted = sorted(raw_c_jp.keys())
            jps_sorted = [raw_c_jp[c] for c in cs_sorted]
            for c_target in C_GRID:
                if c_target < cs_sorted[0] or c_target > cs_sorted[-1]:
                    continue
                jp_interp = np.interp(c_target, cs_sorted, jps_sorted)
                all_c_jparam[(beta, n, ger, round(c_target, 4))] = jp_interp

print(f"\nTotal c-grid entries: {len(all_c_jparam)}")

# ============================================================
# Step 2: Level optimal in c-space
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Level optimal c* in c-space")
print("=" * 60)

def best_c_for_configs(config_list):
    """For a set of configs, find c that minimizes mean J_param"""
    best_c = None
    best_j = float('inf')
    for c in C_GRID:
        jvals = [all_c_jparam.get((beta, n, ger, round(c, 4)), np.nan)
                 for beta, n, ger in config_list]
        jvals = [v for v in jvals if not np.isnan(v)]
        if jvals and np.mean(jvals) < best_j:
            best_j = np.mean(jvals)
            best_c = c
    return best_c, best_j

# L0: global
all_configs = [(b, n, g) for b in BETAS for n in NS for g in GERS]
c_l0, j_l0 = best_c_for_configs(all_configs)
print(f"L0 global: c*={c_l0:.4f}, J={j_l0:.4f}")

# L1: by n
l1_results = {}
for n in NS:
    configs = [(b, n, g) for b in BETAS for g in GERS]
    c_l1, j_l1 = best_c_for_configs(configs)
    l1_results[n] = (c_l1, j_l1)
    print(f"L1 n={n}: c*={c_l1:.4f}, J={j_l1:.4f}")

# L2: by beta
l2_results = {}
for beta in BETAS:
    configs = [(beta, n, g) for n in NS for g in GERS]
    c_l2, j_l2 = best_c_for_configs(configs)
    l2_results[beta] = (c_l2, j_l2)
    print(f"L2 beta={beta}: c*={c_l2:.4f}, J={j_l2:.4f}")

# L3: by (beta, n)
l3_results = {}
for beta in BETAS:
    for n in NS:
        configs = [(beta, n, g) for g in GERS]
        c_l3, j_l3 = best_c_for_configs(configs)
        l3_results[(beta, n)] = (c_l3, j_l3)
        print(f"L3 beta={beta} n={n}: c*={c_l3:.4f}, J={j_l3:.4f}")

# L4: by (beta, n, ger)
l4_results = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            configs = [(beta, n, ger)]
            c_l4, j_l4 = best_c_for_configs(configs)
            l4_results[(beta, n, ger)] = (c_l4, j_l4)

# Compute average J_param for each level
j_l1_avg = np.mean([v[1] for v in l1_results.values()])
j_l2_avg = np.mean([v[1] for v in l2_results.values()])
j_l3_avg = np.mean([v[1] for v in l3_results.values()])
j_l4_avg = np.mean([v[1] for v in l4_results.values()])

print(f"\n--- c-space Level Summary ---")
print(f"L0 global:     J={j_l0:.4f}  (c*={c_l0:.4f})")
print(f"L1 by n:       J={j_l1_avg:.4f}  (c*={[round(l1_results[n][0],3) for n in NS]})")
print(f"L2 by beta:    J={j_l2_avg:.4f}  (c*={[round(l2_results[b][0],3) for b in BETAS]})")
print(f"L3 by (b,n):   J={j_l3_avg:.4f}")
print(f"L4 by (b,n,g): J={j_l4_avg:.4f}")

# Compare with raw-delta space
print(f"\n--- Comparison: raw-delta vs c-space ---")
print(f"L0->L4 delta: raw J improvement = 0.582->0.547 = {((0.582-0.547)/0.582*100):.1f}%")
print(f"L0->L4 delta: c-space J improvement = {j_l0:.4f}->{j_l4_avg:.4f} = {((j_l0-j_l4_avg)/j_l0*100):.1f}%")
print(f"L0->L1 delta: raw J improvement = 0.582->0.581 = 0.1%")
print(f"L0->L1 delta: c-space J improvement = {j_l0:.4f}->{j_l1_avg:.4f} = {((j_l0-j_l1_avg)/j_l0*100):.1f}%")

# ============================================================
# Step 3: Deployment ladder in c-space
# ============================================================
print("\n" + "=" * 60)
print("Step 3: Deployment ladder in c-space")
print("=" * 60)

# Default δ=0.1 corresponds to c = 0.1/s_v for each config
default_c_jparams = []
for beta in BETAS:
    for n in NS:
        sv = SV_TABLE[(beta, n)]
        c_default = 0.1 / sv
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            jp = all_c_jparam.get((beta, n, ger, round(c_default, 4)), np.nan)
            if not np.isnan(jp):
                default_c_jparams.append(jp)
j_default_c = np.mean(default_c_jparams)
print(f"Default delta=0.1 in c-space: J={j_default_c:.4f}")

# Test various global c constants
print("\nGlobal c scan:")
c_candidates = np.arange(0.10, 0.36, 0.02)
best_global_c = None
best_global_j = float('inf')
for c_test in c_candidates:
    jvals = []
    for beta in BETAS:
        for n in NS:
            for ger in GERS:
                jp = all_c_jparam.get((beta, n, ger, round(c_test, 4)), np.nan)
                if not np.isnan(jp):
                    jvals.append(jp)
    j_mean = np.mean(jvals) if jvals else np.nan
    marker = ""
    if not np.isnan(j_mean) and j_mean < best_global_j:
        best_global_j = j_mean
        best_global_c = c_test
    if not np.isnan(j_mean):
        marker = " <<< BEST" if j_mean < best_global_j + 0.001 else ""
    print(f"  c={c_test:.2f}: J={j_mean:.4f}{marker}")

print(f"\nBest global c* = {best_global_c:.2f}, J={best_global_j:.4f}")

# Ladder table: compare raw-delta schemes vs c-space schemes
# Load raw-delta ladder for comparison
raw_ladder = pd.read_csv(os.path.join(DATA_DIR, "E03-4c_ladder_table.csv"))
print(f"\n--- Raw-delta ladder baseline ---")
print(f"Default(δ=0.1): J={raw_ladder[raw_ladder['method']=='Default(delta=0.1)']['jparam'].values[0]:.4f}")
print(f"L4:              J={raw_ladder[raw_ladder['method'].str.startswith('L4')]['jparam'].values[0]:.4f}")
print(f"L3:              J={raw_ladder[raw_ladder['method'].str.startswith('L3')]['jparam'].values[0]:.4f}")

# Build c-space ladder
print("\n--- c-space ladder ---")
print(f"c* global (L0):          J={j_l0:.4f} (c*={best_global_c:.2f})")
print(f"c* by n (L1):            J={j_l1_avg:.4f}")
print(f"c* by beta (L2):         J={j_l2_avg:.4f}")
print(f"c* by (beta,n) (L3):     J={j_l3_avg:.4f}")
print(f"c* by (beta,n,g) (L4):   J={j_l4_avg:.4f}")
print(f"Default equivalent (δ=0.1 as c): J={j_default_c:.4f}")

# Compare improvement from raw to c
print(f"\n--- Key comparison ---")
print(f"Raw δ=0.1:            {raw_ladder[raw_ladder['method']=='Default(delta=0.1)']['jparam'].values[0]:.4f}")
print(f"Raw L4 (per-config):  {raw_ladder[raw_ladder['method'].str.startswith('L4')]['jparam'].values[0]:.4f}")
print(f"c-space global c*:    {best_global_j:.4f}")
print(f"c-space L4:           {j_l4_avg:.4f}")
print(f"c-space improvement over raw default: {(1-best_global_j/raw_ladder[raw_ladder['method']=='Default(delta=0.1)']['jparam'].values[0])*100:.1f}%")

# Stretch: test various global c values beyond our grid
print(f"\n--- c-space c* robustness ---")
print(f"Best c* = {best_global_c:.2f}")
print(f"c* range across (beta,n) L3: [{min(v[0] for v in l3_results.values()):.3f}, {max(v[0] for v in l3_results.values()):.3f}]")
print(f"c* range across (beta,n,ger) L4: [{min(v[0] for v in l4_results.values()):.3f}, {max(v[0] for v in l4_results.values()):.3f}]")

# Save c-space level data
c_level_rows = []
c_level_rows.append({'level': 'L0', 'group': 'global', 'optimal_c': best_global_c, 'jparam': j_l0})
for n in NS:
    c_level_rows.append({'level': 'L1', 'group': f'n={n}', 'optimal_c': l1_results[n][0], 'jparam': l1_results[n][1]})
for beta in BETAS:
    c_level_rows.append({'level': 'L2', 'group': f'beta={beta}', 'optimal_c': l2_results[beta][0], 'jparam': l2_results[beta][1]})
for (beta, n), (c_val, j_val) in l3_results.items():
    c_level_rows.append({'level': 'L3', 'group': f'beta={beta}_n={n}', 'optimal_c': c_val, 'jparam': j_val})
for (beta, n, ger), (c_val, j_val) in l4_results.items():
    c_level_rows.append({'level': 'L4', 'group': f'beta={beta}_n={n}_g={ger}', 'optimal_c': c_val, 'jparam': j_val})

c_level_df = pd.DataFrame(c_level_rows)
c_level_df.to_csv(os.path.join(OUT_DIR, "E03_cspace_level_optimal.csv"), index=False)
print(f"\nc-space level data saved to E03_cspace_level_optimal.csv")

# Save per-config c* data
c_config_rows = []
for beta in BETAS:
    for n in NS:
        sv = SV_TABLE[(beta, n)]
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            for c in C_GRID:
                jp = all_c_jparam.get((beta, n, ger, round(c, 4)))
                if jp is not None and not np.isnan(jp):
                    c_config_rows.append({
                        'beta': beta, 'n': n, 'gamma_eta': ger,
                        'c': c, 'jparam': jp,
                        'raw_delta_equiv': c * sv
                    })
c_config_df = pd.DataFrame(c_config_rows)
c_config_df.to_csv(os.path.join(OUT_DIR, "E03_cspace_jparam_by_config.csv"), index=False)
print(f"c-space per-config J_param saved ({len(c_config_df)} rows)")

print("\nDone.")
