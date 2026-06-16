"""
E04-4: 泛化测试（blocked split）
跨β / 跨n / 跨γ/η
"""
import numpy as np, pandas as pd, json
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
import warnings; warnings.filterwarnings('ignore')

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
DELTAS = np.arange(0, 0.51, 0.02)
feat_names = ['f_mean','f_var','f_sr_mean','f_sr_var','f_skew','f_cv','f_t1m','f_tnm','f_log_ratio','f_n']
loss_cols = [f'loss_{d:.2f}' for d in DELTAS]

df = pd.read_csv(DATA_DIR / 'E04_features_labels.csv')
risk_df = pd.read_csv(DATA_DIR / 'E04_risk_curves.csv')
X_all = df[feat_names].values.astype(np.float32)
y_l4 = df['label_L4'].values.astype(np.float32)
y_l5 = df['label_L5'].values.astype(np.float32)
Y_risk = risk_df[loss_cols].values.astype(np.float32)

MLP_CFG = dict(hidden_layer_sizes=(256,128,64), activation='relu', solver='adam',
                alpha=1e-4, batch_size=256, learning_rate_init=1e-3, max_iter=200,
                early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
                random_state=42, verbose=False)

# Sweep lookup (same as before)
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

def J_eval(sub_df, delta_preds):
    losses = []
    for idx, dp in delta_preds.items():
        row = sub_df.loc[idx]
        key = (row['beta'],int(row['n']),row['gamma_ratio'])
        dn = min(DELTAS, key=lambda x: abs(x-float(dp)))
        lk = sweep.get(key,{}).get((float(dn), int(row['rep'])), np.nan)
        if not np.isnan(lk): losses.append(lk)
    return float(np.sqrt(np.mean(losses))) if losses else np.nan, len(losses)

def train_and_eval(train_mask, test_mask, label='L4'):
    X_tr = StandardScaler().fit_transform(X_all[train_mask])
    X_te = StandardScaler().fit(X_all[train_mask]).transform(X_all[test_mask])
    # L4
    m_l4 = MLPRegressor(**MLP_CFG).fit(X_tr, y_l4[train_mask])
    d_l4 = {idx: float(np.clip(m_l4.predict(X_te[i:i+1])[0],0,0.5)) for i, idx in enumerate(np.where(test_mask)[0])}
    jl4, _ = J_eval(df.iloc[test_mask], d_l4)
    # Risk
    m_risk = MLPRegressor(**{**MLP_CFG, 'max_iter': 300}).fit(X_tr, Y_risk[train_mask])
    d_risk = {}
    for i, idx in enumerate(np.where(test_mask)[0]):
        pred = m_risk.predict(X_te[i:i+1])[0]
        d_risk[idx] = float(DELTAS[np.argmin(pred)])
    jr, _ = J_eval(df.iloc[test_mask], d_risk)
    # Default on test
    d_def = {idx: 0.1 for idx in np.where(test_mask)[0]}
    jd, _ = J_eval(df.iloc[test_mask], d_def)
    return jl4, jr, jd

results = {}

# ── Cross-β ──
print("=== Cross-β: train {1.5,2.5,5.0}, test {2.0,4.0} ===")
t_mask = df['beta'].isin([1.5,2.5,5.0]).values
e_mask = df['beta'].isin([2.0,4.0]).values
jl4, jr, jd = train_and_eval(t_mask, e_mask)
results['cross_beta'] = {'L4_hard': jl4, 'Risk_curve': jr, 'Default': jd}
print(f"  L4={jl4:.4f}  Risk={jr:.4f}  Default={jd:.4f}")

# ── Cross-n ──
print("=== Cross-n: train {7,20}, test {10} ===")
t_mask = df['n'].isin([7,20]).values
e_mask = (df['n'] == 10).values
jl4, jr, jd = train_and_eval(t_mask, e_mask)
results['cross_n'] = {'L4_hard': jl4, 'Risk_curve': jr, 'Default': jd}
print(f"  L4={jl4:.4f}  Risk={jr:.4f}  Default={jd:.4f}")

# ── Cross-γ/η ──
print("=== Cross-γ/η: train {0.1,1.0}, test {0.5} ===")
t_mask = df['gamma_ratio'].isin([0.1,1.0]).values
e_mask = (df['gamma_ratio'] == 0.5).values
jl4, jr, jd = train_and_eval(t_mask, e_mask)
results['cross_ger'] = {'L4_hard': jl4, 'Risk_curve': jr, 'Default': jd}
print(f"  L4={jl4:.4f}  Risk={jr:.4f}  Default={jd:.4f}")

with open(DATA_DIR / 'E04_generalization.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n{'='*50}")
for k, v in results.items():
    print(f"{k}: L4={v['L4_hard']:.4f}, Risk={v['Risk_curve']:.4f}, Def={v['Default']:.4f}")
print("Done.")
