"""
边界案例深入分析

1. b1_e1000_n7: 扩大 δ 范围到 2.0，看曲线是否继续下降
2. b2_e1000_n20: 分析 MDM 失败时的内部状态
3. b5_e1000_n7: 更精细扫描窄谷区域
"""

import sys
import json
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta, eta, gamma, n, seed):
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    t = gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)
    return np.sort(t)


def run_mdm_detailed(sample, delta, gamma_steps=60):
    """运行 MDM 并返回详细结果"""
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        return {
            'beta': result[0], 'eta': result[1], 'gamma': result[2],
            'r2': result[3], 'status': result[4],
        }
    except Exception as e:
        return {'error': str(e)}


def compute_relative_mse(est, true_beta, true_eta, true_gamma):
    return ((est['beta'] - true_beta) / true_beta) ** 2 + \
           ((est['eta'] - true_eta) / true_eta) ** 2 + \
           ((est['gamma'] - true_gamma) / true_gamma) ** 2


def analyze_mdm_internals(sample, delta, gamma_steps=200):
    """分析 MDM 在给定 δ 下的内部搜索过程"""
    t = np.array(sorted(sample))
    n = len(t)

    from scipy.special import betaincinv
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    neg_ln_1_minus_F = -np.log(1 - ranks)

    def calculate_eta_std(beta, gamma, current_t):
        if beta <= 0: return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0/beta)
        etas = (current_t - gamma) / denom
        return np.std(etas, ddof=1)

    from scipy.optimize import minimize_scalar

    def find_best_beta_for_gamma(gamma):
        if gamma >= t[0]:
            return None, float('inf')
        res = minimize_scalar(
            lambda b: calculate_eta_std(b, gamma, t),
            bounds=(0.1, 15.0),
            method='bounded'
        )
        return res.x, res.fun

    t_min = t[0]

    # 第一轮
    gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)
    sigma_mins1 = []
    best_betas1 = []
    for g in gammas1:
        b, sig = find_best_beta_for_gamma(g)
        sigma_mins1.append(sig)
        best_betas1.append(b)

    sigma_mins1 = np.array(sigma_mins1)
    best_betas1 = np.array(best_betas1)
    grads1 = np.gradient(sigma_mins1, gammas1)

    # 第二轮（如果需要）
    diffs1 = grads1 - delta
    sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

    if len(sign_changes) == 0:
        gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
        sigma_mins2 = []
        best_betas2 = []
        for g in gammas2:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins2.append(sig)
            best_betas2.append(b)

        sigma_mins2 = np.array(sigma_mins2)
        best_betas2 = np.array(best_betas2)
        grads2 = np.gradient(sigma_mins2, gammas2)

        gammas = np.concatenate([gammas1, gammas2])
        sigma_mins = np.concatenate([sigma_mins1, sigma_mins2])
        best_betas = np.concatenate([best_betas1, best_betas2])
        grads = np.concatenate([grads1, grads2])
        diffs = grads - delta
        sign_changes = np.where(np.diff(np.sign(diffs)))[0]
    else:
        gammas = gammas1
        sigma_mins = sigma_mins1
        best_betas = best_betas1
        grads = grads1
        diffs = diffs1

    return {
        'gammas': gammas.tolist(),
        'sigma_mins': sigma_mins.tolist(),
        'best_betas': best_betas.tolist(),
        'grads': grads.tolist(),
        'sign_changes': sign_changes.tolist(),
        'delta': delta,
        't_min': float(t_min),
    }


def main():
    output_dir = Path(__file__).parent / 'data' / 'curve_study'
    output_dir.mkdir(parents=True, exist_ok=True)

    # === 1. b1_e1000_n7: extended delta range ===
    print("=" * 60)
    print("1. b1_e1000_n7: extend delta to 2.0")
    print("=" * 60)

    sample_b1 = generate_weibull_sample(1.0, 1000.0, 1000.0, 7, 2742)
    print(f"Sample: {sample_b1.tolist()}")

    delta_extended = np.arange(0.001, 2.001, 0.005)
    results_b1 = []
    for delta in delta_extended:
        est = run_mdm_detailed(sample_b1, delta)
        if 'error' in est or est['status'] == 'no_intersection':
            results_b1.append({'delta': float(delta), 'mse': None, 'status': 'failed'})
        else:
            mse = compute_relative_mse(est, 1.0, 1000.0, 1000.0)
            results_b1.append({
                'delta': float(delta), 'mse': float(mse),
                'beta': float(est['beta']), 'eta': float(est['eta']),
                'gamma': float(est['gamma']), 'status': 'ok',
            })

    valid_b1 = [r for r in results_b1 if r['mse'] is not None]
    if valid_b1:
        best = min(valid_b1, key=lambda x: x['mse'])
        print(f"best delta = {best['delta']:.4f}, MSE = {best['mse']:.6f}")
        print(f"est_beta = {best['beta']:.4f}, est_eta = {best['eta']:.4f}, est_gamma = {best['gamma']:.4f}")
        print(f"valid: {len(valid_b1)}/{len(delta_extended)}")

        # 看曲线尾部
        last_10 = valid_b1[-10:]
        print("\nlast 10 valid points:")
        for r in last_10:
            print(f"  delta={r['delta']:.3f}  MSE={r['mse']:.6f}  est_beta={r['beta']:.4f}")

    # 保存
    with open(output_dir / 'b1_e1000_n7_extended.json', 'w') as f:
        json.dump(results_b1, f, indent=2)

    # === 2. b2_e1000_n20: failure analysis ===
    print("\n" + "=" * 60)
    print("2. b2_e1000_n20: MDM failure analysis")
    print("=" * 60)

    sample_b2_n20 = generate_weibull_sample(2.0, 1000.0, 1000.0, 20, 5042)
    print(f"Sample (first 5): {sample_b2_n20[:5].tolist()}")
    print(f"t_min = {sample_b2_n20[0]:.4f}")

    # Scan near failure boundary
    delta_near_fail = np.arange(0.48, 0.54, 0.001)
    print(f"\nDelta range [{delta_near_fail[0]:.3f}, {delta_near_fail[-1]:.3f}], step 0.001")
    for delta in delta_near_fail:
        est = run_mdm_detailed(sample_b2_n20, delta)
        if 'error' in est or est['status'] == 'no_intersection':
            print(f"  delta={delta:.3f}  FAILED ({est.get('status', est.get('error', '?'))})")
        else:
            mse = compute_relative_mse(est, 2.0, 1000.0, 1000.0)
            print(f"  delta={delta:.3f}  MSE={mse:.6f}  gamma={est['gamma']:.4f}  beta={est['beta']:.4f}")

    # Analyze internal state at failure point
    print("\nInternal state at delta=0.52:")
    internals = analyze_mdm_internals(sample_b2_n20, 0.52, gamma_steps=200)
    print(f"  t_min = {internals['t_min']:.4f}")
    print(f"  sign_changes = {internals['sign_changes']}")
    print(f"  grad range: [{min(internals['grads']):.4f}, {max(internals['grads']):.4f}]")
    cmp = '<' if max(internals['grads']) < 0.52 else '>'
    print(f"  max_grad {max(internals['grads']):.4f} {cmp} 0.52")

    # Compare with delta=0.51 (should succeed)
    print("\nInternal state at delta=0.51:")
    internals_051 = analyze_mdm_internals(sample_b2_n20, 0.51, gamma_steps=200)
    print(f"  sign_changes = {internals_051['sign_changes']}")
    print(f"  grad range: [{min(internals_051['grads']):.4f}, {max(internals_051['grads']):.4f}]")

    # 保存
    with open(output_dir / 'b2_e1000_n20_failure_analysis.json', 'w') as f:
        json.dump({
            'near_failure': [{'delta': float(d), 'result': run_mdm_detailed(sample_b2_n20, d)} for d in delta_near_fail],
            'internals_052': internals,
            'internals_051': internals_051,
        }, f, indent=2, default=str)

    # === 3. b5_e1000_n7: fine scan narrow valley ===
    print("\n" + "=" * 60)
    print("3. b5_e1000_n7: fine scan narrow valley")
    print("=" * 60)

    sample_b5 = generate_weibull_sample(5.0, 1000.0, 1000.0, 7, 6742)
    print(f"Sample: {sample_b5.tolist()}")

    # Fine scan in delta=0.001-0.05
    delta_fine = np.arange(0.001, 0.05, 0.0005)
    print(f"\nDelta range [{delta_fine[0]:.4f}, {delta_fine[-1]:.4f}], step 0.0005")
    results_b5 = []
    for delta in delta_fine:
        est = run_mdm_detailed(sample_b5, delta)
        if 'error' in est or est['status'] == 'no_intersection':
            results_b5.append({'delta': float(delta), 'mse': None})
        else:
            mse = compute_relative_mse(est, 5.0, 1000.0, 1000.0)
            results_b5.append({
                'delta': float(delta), 'mse': float(mse),
                'beta': float(est['beta']), 'eta': float(est['eta']),
                'gamma': float(est['gamma']),
            })

    valid_b5 = [r for r in results_b5 if r['mse'] is not None]
    if valid_b5:
        best_b5 = min(valid_b5, key=lambda x: x['mse'])
        print(f"best delta = {best_b5['delta']:.4f}, MSE = {best_b5['mse']:.6f}")
        print(f"est_beta = {best_b5['beta']:.4f}, est_eta = {best_b5['eta']:.4f}, est_gamma = {best_b5['gamma']:.4f}")

        # Print first 20 points
        print("\nfirst 20 points:")
        for r in valid_b5[:20]:
            print(f"  delta={r['delta']:.4f}  MSE={r['mse']:.6f}  est_beta={r['beta']:.4f}")

    # 保存
    with open(output_dir / 'b5_e1000_n7_fine.json', 'w') as f:
        json.dump(results_b5, f, indent=2)


if __name__ == '__main__':
    main()
