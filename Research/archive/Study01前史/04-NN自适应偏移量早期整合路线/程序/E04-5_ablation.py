"""
E04-5: 消融实验（特征/架构）
标签消融已由 E04-2 的 L4/L5/Risk 三路线覆盖
"""
import numpy as np, pandas as pd, json
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
import warnings; warnings.filterwarnings('ignore')

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
DELTAS = np.arange(0, 0.51, 0.02)
loss_cols = [f'loss_{d:.2f}' for d in DELTAS]

df = pd.read_csv(DATA_DIR / 'E04_features_labels.csv')
risk_df = pd.read_csv(DATA_DIR / 'E04_risk_curves.csv')
all_feats = ['f_mean','f_var','f_sr_mean','f_sr_var','f_skew','f_cv','f_t1m','f_tnm','f_log_ratio','f_n']
Y_risk = risk_df[loss_cols].values.astype(np.float32)

np.random.seed(42)
rng = np.random.default_rng(42)
train_idx = []; test_idx = []
for (b,n,g), gdf in df.groupby(['beta','n','gamma_ratio']):
    ids = rng.permutation(len(gdf))
    n_tr = int(len(ids)*0.7)
    train_idx.extend(gdf.index[ids[:n_tr]]); test_idx.extend(gdf.index[ids[n_tr:]])
t_mask = np.array([i in train_idx for i in df.index])
e_mask = np.array([i in test_idx for i in df.index])

MLP_CFG = dict(hidden_layer_sizes=(256,128,64), activation='relu', solver='adam',
                alpha=1e-4, batch_size=256, learning_rate_init=1e-3, max_iter=300,
                early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
                random_state=42, verbose=False)

sweep = {}
for beta in [1.5,2.0,2.5,4.0,5.0]:
    for n in [7,10,20]:
        for gr in [0.1,0.5,1.0]:
            gt = gr
            sp = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            for _, row in sp.iterrows():
                d = float(row['delta']); r = int(row['rep'])
                loss = ((row['beta_hat']-beta)/beta)**2 + ((row['eta_hat']-1.0)/1.0)**2 + ((row['gamma_hat']-gt)/1.0)**2
                sweep.setdefault((beta,n,gr),{})[(d,r)] = loss

def J_from_preds(sub_df, preds):
    losses = []
    for idx, dp in preds.items():
        row = sub_df.loc[idx]
        key = (row['beta'],int(row['n']),row['gamma_ratio'])
        dn = min(DELTAS, key=lambda x: abs(x-float(dp)))
        lk = sweep.get(key,{}).get((float(dn), int(row['rep'])), np.nan)
        if not np.isnan(lk): losses.append(lk)
    return float(np.sqrt(np.mean(losses))) if losses else np.nan

def run_experiment(feat_list, arch_cfg=None, label='risk'):
    """Train risk curve model with given features, return test J_param"""
    cfg = {**MLP_CFG}
    if arch_cfg: cfg.update(arch_cfg)
    X_tr = StandardScaler().fit_transform(df.loc[t_mask, feat_list].values.astype(np.float32))
    X_te = StandardScaler().fit(df.loc[t_mask, feat_list].values.astype(np.float32)).transform(df.loc[e_mask, feat_list].values.astype(np.float32))
    m = MLPRegressor(**cfg).fit(X_tr, Y_risk[t_mask])
    preds = {}
    for i, idx in enumerate(np.where(e_mask)[0]):
        p = m.predict(X_te[i:i+1])[0]
        preds[idx] = float(DELTAS[np.argmin(p)])
    return J_from_preds(df.iloc[e_mask], preds)

results = {}
base_j = run_experiment(all_feats)
results['baseline'] = base_j
print(f"Baseline (all features, 3-layer): J={base_j:.4f}")

# ── Feature ablation ──
print("\n=== Feature Ablation ===")
for name, feats in [
    ('-skew_cv', [f for f in all_feats if f not in ['f_skew','f_cv']]),
    ('-tail', [f for f in all_feats if f not in ['f_t1m','f_tnm','f_log_ratio']]),
    ('-n', [f for f in all_feats if f != 'f_n']),
]:
    j = run_experiment(feats)
    results[name] = j
    print(f"  {name}: J={j:.4f} (delta={j-base_j:+.4f})")

# ── Architecture ablation ──
print("\n=== Architecture Ablation ===")
for name, acfg in [
    ('shallow_64_32', dict(hidden_layer_sizes=(64,32))),
    ('wide_512_256_128', dict(hidden_layer_sizes=(512,256,128))),
    ('deep_256_128_64_32', dict(hidden_layer_sizes=(256,128,64,32))),
]:
    j = run_experiment(all_feats, acfg)
    results[name] = j
    print(f"  {name}: J={j:.4f} (delta={j-base_j:+.4f})")

with open(DATA_DIR / 'E04_ablation.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*45}")
for k, v in sorted(results.items(), key=lambda x: x[1]):
    print(f"  {k:<20} J={v:.4f}  vs baseline={v-base_j:+.4f}")
print("Done.")
