"""
E03-4b v2: 四种 β 预估方法对比 + Oracle 参照
1. L-moments (τ₃ → β)
2. WMLE
3. MDM δ=0 β̂
4. Dual-δ average (δ=0.02 + δ=0.10)
0. Oracle (true β, 上界)
"""
import sys, numpy as np, pandas as pd, os, time, hashlib

BASE = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE, "实验数据")
SCRIPT_DIR = os.path.join(BASE, "程序")

sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")
sys.path.insert(0, SCRIPT_DIR)

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from scipy.optimize import brentq

BETAS = [2.0, 2.5, 4.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
N_REPS = 500
ETA_TRUE = 1.0

# ---- L3 lookup table (continuous interpolation) ----
l3_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))
l3 = l3_df[l3_df['level'] == 'L3'].copy()
def parse(g):
    parts = g.split('_')
    return float(parts[0].split('=')[1]), int(parts[1].split('=')[1])

l3_data = {}  # n -> [(beta, delta_star), ...]
for _, row in l3.iterrows():
    beta, n = parse(row['group'])
    l3_data.setdefault(n, []).append((beta, row['optimal_delta']))
for n in l3_data:
    l3_data[n].sort()

def delta_from_beta(beta_hat, n):
    """Continuous interpolation of L3 optimal delta* from estimated beta"""
    bs, ds = zip(*l3_data[n])
    return float(np.interp(np.clip(beta_hat, bs[0], bs[-1]), bs, ds))

DELTA_VALUES = np.arange(0, 0.52, 0.02)
def nearest_delta(d):
    return min(DELTA_VALUES, key=lambda x: abs(x - d))

def compute_jparam(bh, eh, gh, beta_true, gamma_true):
    tb = ((bh - beta_true) / beta_true) ** 2
    te = ((eh - ETA_TRUE) / ETA_TRUE) ** 2
    tg = ((gh - gamma_true) / ETA_TRUE) ** 2
    return np.sqrt(np.mean(tb + te + tg))

# ---- Pre-load sweep data for fast lookup ----
print("Pre-loading E03-3 sweep data...")
sweep_data = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            df = pd.read_csv(os.path.join(DATA_DIR, fname))
            # Index by (delta, rep) for fast lookup
            key = (beta, n, ger)
            lookup = {}
            for d in DELTA_VALUES:
                sub = df[(df['delta'] == d) & (df['status'] == True)]
                for _, row in sub.iterrows():
                    lookup[(d, int(row['rep']))] = (row['beta_hat'], row['eta_hat'], row['gamma_hat'])
            sweep_data[key] = lookup

# Pre-build default delta=0.1 J_param per config
default_j = {}
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            gamma_true = ger * ETA_TRUE
            lookup = sweep_data[(beta, n, ger)]
            vals = [(bh, eh, gh) for (d, r), (bh, eh, gh) in lookup.items() if d == 0.10]
            if vals:
                bh, eh, gh = zip(*vals)
                default_j[(beta, n, ger)] = compute_jparam(
                    np.array(bh), np.array(eh), np.array(gh), beta, gamma_true)

# ---- L-moments β estimation ----
def estimate_beta_lmoments(sample):
    """L-skewness τ₃ → β for 3-parameter Weibull"""
    n = len(sample)
    # Unbiased probability-weighted moments
    b0 = np.mean(sample)
    b1 = np.sum(sample * np.arange(1, n+1) / (n * (n-1))) * (n/(n-1)) if n > 1 else b0
    # Simplified: use order statistics
    # L-skewness via direct formula for Weibull
    # τ₃(β) = (1 - 6*2^(-p) + 6*3^(-p)) / (1 - 2^(-p)), p = 1 + 1/β
    # Estimate via PWM
    pwm = np.zeros(3)
    for j in range(3):
        weights = np.array([np.prod(np.arange(i+1, i+j+1) if j > 0 else [1]) /
                            np.prod(np.arange(n-i, n)) for i in range(n)])
        # Actually use the standard PWM estimator
        pwm[j] = np.sum(sample * np.array([
            np.prod([(i - k) / (n - k) for k in range(j)]) if j > 0 else 1.0
            for i in range(1, n+1)
        ])) / n

    l1 = pwm[0]
    l2 = 2 * pwm[1] - pwm[0]
    l3 = 6 * pwm[2] - 6 * pwm[1] + pwm[0]
    if l2 <= 1e-12:
        return np.nan
    t3 = l3 / l2

    # Invert τ₃(β) numerically
    def tau3_func(b):
        p = 1.0 + 1.0 / max(b, 0.2)
        return (1.0 - 6.0 * 2.0**(-p) + 6.0 * 3.0**(-p)) / (1.0 - 2.0**(-p))

    try:
        t3_lo = tau3_func(0.3)
        t3_hi = tau3_func(20.0)
        if t3 <= t3_hi or t3 >= t3_lo:
            return np.nan
        beta_hat = brentq(lambda b: tau3_func(b) - t3, 0.3, 20.0)
        return beta_hat
    except:
        return np.nan

# ---- Main loop ----
print("\nRunning 4-method β estimation comparison...")
results = []
total = len(BETAS) * len(NS) * len(GERS)
idx = 0

for beta_true in BETAS:
    for n in NS:
        for ger in GERS:
            idx += 1
            gamma_true = ger * ETA_TRUE
            lookup = sweep_data[(beta_true, n, ger)]
            dj = default_j[(beta_true, n, ger)]
            t0 = time.time()

            # Collect per-rep data for each method
            meth_jparams = {m: [] for m in ['oracle', 'lmom', 'wmle', 'mdm0', 'dual']}

            for rep in range(N_REPS):
                sample = generate_sample(beta_true, ETA_TRUE, gamma_true, n, rep)

                # ---- Oracle ----
                d_star = nearest_delta(delta_from_beta(beta_true, n))
                key = (d_star, rep)
                if key in lookup:
                    bh, eh, gh = lookup[key]
                    meth_jparams['oracle'].append(((bh-beta_true)/beta_true)**2 +
                                                   ((eh-ETA_TRUE)/ETA_TRUE)**2 +
                                                   ((gh-gamma_true)/ETA_TRUE)**2)

                # ---- MDM δ=0 ----
                key0 = (0.0, rep)
                if key0 in lookup:
                    bh0, eh0, gh0 = lookup[key0]
                    beta_mdm0 = bh0
                    d_star = nearest_delta(delta_from_beta(beta_mdm0, n))
                    key_star = (d_star, rep)
                    if key_star in lookup:
                        bh, eh, gh = lookup[key_star]
                        meth_jparams['mdm0'].append(((bh-beta_true)/beta_true)**2 +
                                                     ((eh-ETA_TRUE)/ETA_TRUE)**2 +
                                                     ((gh-gamma_true)/ETA_TRUE)**2)

                # ---- Dual-δ avg ----
                key_002 = (0.02, rep)
                key_010 = (0.10, rep)
                if key_002 in lookup and key_010 in lookup:
                    bh_low = lookup[key_002][0]
                    bh_high = lookup[key_010][0]
                    beta_dual = (bh_low + bh_high) / 2.0
                    d_star = nearest_delta(delta_from_beta(beta_dual, n))
                    key_star = (d_star, rep)
                    if key_star in lookup:
                        bh, eh, gh = lookup[key_star]
                        meth_jparams['dual'].append(((bh-beta_true)/beta_true)**2 +
                                                     ((eh-ETA_TRUE)/ETA_TRUE)**2 +
                                                     ((gh-gamma_true)/ETA_TRUE)**2)

                # ---- L-moments ----
                beta_lm = estimate_beta_lmoments(sample)
                if not np.isnan(beta_lm):
                    d_star = nearest_delta(delta_from_beta(beta_lm, n))
                    key_star = (d_star, rep)
                    if key_star in lookup:
                        bh, eh, gh = lookup[key_star]
                        meth_jparams['lmom'].append(((bh-beta_true)/beta_true)**2 +
                                                     ((eh-ETA_TRUE)/ETA_TRUE)**2 +
                                                     ((gh-gamma_true)/ETA_TRUE)**2)

                # ---- WMLE ----
                try:
                    wmle_res = run_method('wmle', sample)
                    if wmle_res.get('converged', False):
                        beta_wmle = wmle_res['beta_hat']
                        d_star = nearest_delta(delta_from_beta(beta_wmle, n))
                        key_star = (d_star, rep)
                        if key_star in lookup:
                            bh, eh, gh = lookup[key_star]
                            meth_jparams['wmle'].append(((bh-beta_true)/beta_true)**2 +
                                                         ((eh-ETA_TRUE)/ETA_TRUE)**2 +
                                                         ((gh-gamma_true)/ETA_TRUE)**2)
                except:
                    pass

                if (rep + 1) % 200 == 0:
                    print(f"  [{idx}/{total}] b={beta_true} n={n} g={ger} rep={rep+1}...", flush=True)

            t1 = time.time()

            # Compute J_param for each method
            for mname in ['oracle', 'lmom', 'wmle', 'mdm0', 'dual']:
                vals = meth_jparams[mname]
                if vals:
                    jp = np.sqrt(np.mean(vals))
                    nv = len(vals)
                else:
                    jp = np.nan
                    nv = 0
                results.append({
                    'beta': beta_true, 'n': n, 'gamma_eta': ger,
                    'method': mname, 'jparam': jp, 'n_valid': nv
                })
                status = f"J={jp:.4f} ({nv}/{N_REPS})" if nv > 0 else "FAIL"
                print(f"  {mname:8s}: {status}")

            print(f"  Default: J={dj:.4f}  [{idx}/{total}] {t1-t0:.1f}s")

# ---- Save & Summarize ----
res_df = pd.DataFrame(results)
res_df.to_csv(os.path.join(DATA_DIR, "E03-4b_v2_methods.csv"), index=False)

# Add default baseline
for beta in BETAS:
    for n in NS:
        for ger in GERS:
            res_df = pd.concat([res_df, pd.DataFrame([{
                'beta': beta, 'n': n, 'gamma_eta': ger,
                'method': 'default', 'jparam': default_j[(beta, n, ger)],
                'n_valid': 500
            }])], ignore_index=True)

# Summary by method
print("\n" + "=" * 60)
print("Summary: average J_param by method")
print("=" * 60)
summary = res_df.groupby('method')['jparam'].mean().sort_values()
for m, v in summary.items():
    n_valid = res_df[res_df['method'] == m]['n_valid'].sum()
    print(f"  {m:10s}: J={v:.4f}  (total valid: {n_valid})")

# Relative to default
default_mean = summary.get('default', 0.582)
print(f"\nRelative to default (J={default_mean:.4f}):")
for m, v in summary.items():
    if m == 'default':
        continue
    print(f"  {m:10s}: {v/default_mean:.3f}  ({(v-default_mean)/default_mean*100:+.1f}%)")

res_df.to_csv(os.path.join(DATA_DIR, "E03-4b_v2_summary.csv"), index=False)
print(f"\nSaved: E03-4b_v2_summary.csv")
