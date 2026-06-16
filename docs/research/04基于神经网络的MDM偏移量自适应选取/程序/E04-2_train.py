"""
E04-2/3: 神经网络训练 + 评估（同分布 7:3 split）
三路线：L4 hard label、L5 hard label、Risk curve
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
import json, warnings
warnings.filterwarnings('ignore')

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
OUT_DIR = DATA_DIR

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTAS = np.arange(0, 0.51, 0.02)

# ── Load ──
print("Loading data...")
df = pd.read_csv(DATA_DIR / 'E04_features_labels.csv')
risk = pd.read_csv(DATA_DIR / 'E04_risk_curves.csv')

feat_names = ['f_mean', 'f_var', 'f_sr_mean', 'f_sr_var',
              'f_skew', 'f_cv', 'f_t1m', 'f_tnm', 'f_log_ratio', 'f_n']
loss_cols = [f'loss_{d:.2f}' for d in DELTAS]
X_all = df[feat_names].values.astype(np.float32)
y_l4 = df['label_L4'].values.astype(np.float32)
y_l5 = df['label_L5'].values.astype(np.float32)
Y_risk = risk[loss_cols].values.astype(np.float32)

# ── Pre-build sweep lookup for evaluation ──
print("Building sweep lookup...")
sweep_lookup = {}
for beta in BETAS:
    for n in NS:
        for gr in GERS:
            gamma_t = gr * ETA
            sp = pd.read_csv(DATA_DIR / f'E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv')
            for _, row in sp.iterrows():
                d = float(row['delta'])
                r = int(row['rep'])
                loss = ((row['beta_hat']-beta)/beta)**2 + ((row['eta_hat']-ETA)/ETA)**2 + ((row['gamma_hat']-gamma_t)/ETA)**2
                sweep_lookup.setdefault((beta, n, gr), {})[(d, r)] = loss

def J_param_for_predictions(df_rows, delta_preds):
    """给定样本行和预测δ，计算 J_param = sqrt(mean(loss_i(δ_pred)))"""
    losses = []
    for idx, d_pred in delta_preds.items():
        row = df_rows.loc[idx]
        key = (row['beta'], int(row['n']), row['gamma_ratio'])
        d_nearest = min(DELTAS, key=lambda x: abs(x - float(d_pred)))
        r = int(row['rep'])
        lk = sweep_lookup.get(key, {})
        loss = lk.get((float(d_nearest), r), np.nan)
        if not np.isnan(loss):
            losses.append(loss)
    return float(np.sqrt(np.mean(losses))), len(losses)

# ── 7:3 split per config ──
np.random.seed(42)
train_idx, test_idx = [], []
for (beta, n, gr), gdf in df.groupby(['beta', 'n', 'gamma_ratio']):
    idxs = gdf.index.values.copy()
    np.random.shuffle(idxs)
    n_train = int(len(idxs) * 0.7)
    train_idx.extend(idxs[:n_train])
    test_idx.extend(idxs[n_train:])
train_idx = np.array(train_idx)
test_idx = np.array(test_idx)
print(f"Train: {len(train_idx)}, Test: {len(test_idx)}")

# ── Standardize ──
scaler = StandardScaler()
X_train = scaler.fit_transform(X_all[train_idx])
X_test = scaler.transform(X_all[test_idx])
df_test = df.iloc[test_idx].reset_index(drop=True)

# ══════════════════════════════════════════
# Train 3 models
# ══════════════════════════════════════════
results = {}
MLP_CONFIG = dict(hidden_layer_sizes=(256, 128, 64), activation='relu',
                   solver='adam', alpha=1e-4, batch_size=256,
                   learning_rate_init=1e-3, max_iter=200,
                   early_stopping=True, validation_fraction=0.15,
                   n_iter_no_change=20, random_state=42, verbose=False)

# --- L4 ---
print("\n=== L4 Hard Label ===")
m_l4 = MLPRegressor(**MLP_CONFIG).fit(X_train, y_l4[train_idx])
d_l4 = {}
for i, idx in enumerate(test_idx):
    d_l4[test_idx[i]] = float(np.clip(m_l4.predict(X_test[i:i+1])[0], 0, 0.5))
jl4, nl4 = J_param_for_predictions(df.iloc[test_idx], d_l4)
results['L4_hard'] = dict(J_param=jl4, n_valid=nl4, model=m_l4)

# --- L5 ---
print("=== L5 Hard Label ===")
m_l5 = MLPRegressor(**MLP_CONFIG).fit(X_train, y_l5[train_idx])
d_l5 = {}
for i, idx in enumerate(test_idx):
    d_l5[test_idx[i]] = float(np.clip(m_l5.predict(X_test[i:i+1])[0], 0, 0.5))
jl5, nl5 = J_param_for_predictions(df.iloc[test_idx], d_l5)
results['L5_hard'] = dict(J_param=jl5, n_valid=nl5, model=m_l5)

# --- Risk Curve ---
print("=== Risk Curve (26-dim MSE) ===")
m_risk = MLPRegressor(**{**MLP_CONFIG, 'max_iter': 300}).fit(X_train, Y_risk[train_idx])
d_risk = {}
for i, idx in enumerate(test_idx):
    pred = m_risk.predict(X_test[i:i+1])[0]
    best_j = np.argmin(pred)
    d_risk[test_idx[i]] = float(DELTAS[best_j])
jr, nr = J_param_for_predictions(df.iloc[test_idx], d_risk)
results['Risk_curve'] = dict(J_param=jr, n_valid=nr, model=m_risk)

# --- Default ---
print("=== Default δ=0.1 ===")
d_def = {idx: 0.1 for idx in test_idx}
jdef, ndef = J_param_for_predictions(df.iloc[test_idx], d_def)
results['Default'] = dict(J_param=jdef, n_valid=ndef)

# ── Print ──
print(f"\n{'='*55}")
print(f"  Results (test set, n={len(test_idx)})")
print(f"{'='*55}")
print(f"{'Method':<15} {'J_param':>8} {'vs Default':>12}")
print(f"{'-'*40}")
for name, r in results.items():
    vs = (r['J_param'] - jdef) / jdef * 100
    print(f"{name:<15} {r['J_param']:>8.4f} {vs:>+11.1f}%")

# ── Save ──
out = {k: {'J_param': v['J_param'], 'n_valid': v['n_valid']} for k, v in results.items()}
with open(OUT_DIR / 'E04_main_results.json', 'w') as f:
    json.dump(out, f, indent=2)
# Save per-config breakdown
config_j = {}
for (beta, n, gr), gdf in df_test.groupby(['beta', 'n', 'gamma_ratio']):
    for method, deltas_dict in [('L4_hard', d_l4), ('L5_hard', d_l5), ('Risk_curve', d_risk), ('Default', d_def)]:
        idxs_in_config = [i for i in gdf.index if i in deltas_dict]
        sub_deltas = {i: deltas_dict[i] for i in idxs_in_config}
        j, nv = J_param_for_predictions(gdf.loc[idxs_in_config], sub_deltas)
        config_j.setdefault(method, {})[f'{beta}_{n}_{gr}'] = j
pd.DataFrame(config_j).to_csv(OUT_DIR / 'E04_main_by_config.csv', encoding='utf-8-sig')

print("\nPer-config: E04_main_by_config.csv")
print("Summary: E04_main_results.json")
print("Done.")
