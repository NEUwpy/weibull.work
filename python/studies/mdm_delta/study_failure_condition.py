"""
MDM 失败条件分析

验证：增大 gamma_steps 能否消除 MDM 失败？
分析梯度上限的数学性质。
"""

import sys
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


def run_mdm_with_gamma_steps(sample, delta, gamma_steps):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        return result[4] != "no_intersection", result
    except Exception as e:
        return False, str(e)


def main():
    # b2_e1000_n20 sample that fails at delta=0.52
    sample = generate_weibull_sample(2.0, 1000.0, 1000.0, 20, 5042)
    print(f"t_min = {sample[0]:.4f}")

    # Test 1: Does increasing gamma_steps help?
    print("\n=== Test 1: gamma_steps vs failure at delta=0.52 ===")
    for gs in [60, 100, 200, 500, 1000]:
        ok, result = run_mdm_with_gamma_steps(sample, 0.52, gs)
        if ok:
            print(f"  gamma_steps={gs:4d}  OK  beta={result[0]:.4f}  gamma={result[2]:.4f}")
        else:
            print(f"  gamma_steps={gs:4d}  FAILED")

    # Test 2: What's the max gradient for different gamma_steps?
    print("\n=== Test 2: max gradient vs gamma_steps ===")
    from scipy.special import betaincinv
    from scipy.optimize import minimize_scalar

    t = sample
    n = len(t)
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    neg_ln_1_minus_F = -np.log(1 - ranks)

    def calculate_eta_std(beta, gamma, current_t):
        if beta <= 0: return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0/beta)
        etas = (current_t - gamma) / denom
        return np.std(etas, ddof=1)

    def find_best_beta_for_gamma(gamma):
        if gamma >= t[0]:
            return None, float('inf')
        res = minimize_scalar(
            lambda b: calculate_eta_std(b, gamma, t),
            bounds=(0.1, 15.0),
            method='bounded'
        )
        return res.x, res.fun

    for gs in [60, 100, 200, 500, 1000]:
        # Round 1
        gammas1 = np.linspace(0, t[0] * 0.99, gs)
        sigma_mins1 = np.array([find_best_beta_for_gamma(g)[1] for g in gammas1])
        grads1 = np.gradient(sigma_mins1, gammas1)

        # Round 2
        gammas2 = np.linspace(t[0] * 0.99, t[0] * 0.999999, gs)
        sigma_mins2 = np.array([find_best_beta_for_gamma(g)[1] for g in gammas2])
        grads2 = np.gradient(sigma_mins2, gammas2)

        all_grads = np.concatenate([grads1, grads2])
        max_grad = np.max(all_grads)
        print(f"  gamma_steps={gs:4d}  max_grad={max_grad:.6f}  max_grad > 0.52: {max_grad > 0.52}")

    # Test 3: Analyze the gradient curve shape
    print("\n=== Test 3: gradient curve shape (gamma_steps=500) ===")
    gs = 500
    gammas1 = np.linspace(0, t[0] * 0.99, gs)
    sigma_mins1 = []
    best_betas1 = []
    for g in gammas1:
        b, sig = find_best_beta_for_gamma(g)
        sigma_mins1.append(sig)
        best_betas1.append(b)

    sigma_mins1 = np.array(sigma_mins1)
    best_betas1 = np.array(best_betas1)
    grads1 = np.gradient(sigma_mins1, gammas1)

    # Print gradient at key points
    print(f"  gamma=0:      sigma={sigma_mins1[0]:.4f}  grad={grads1[0]:.4f}  beta={best_betas1[0]:.4f}")
    print(f"  gamma=tmin/4: sigma={sigma_mins1[gs//4]:.4f}  grad={grads1[gs//4]:.4f}  beta={best_betas1[gs//4]:.4f}")
    print(f"  gamma=tmin/2: sigma={sigma_mins1[gs//2]:.4f}  grad={grads1[gs//2]:.4f}  beta={best_betas1[gs//2]:.4f}")
    print(f"  gamma=3tmin/4: sigma={sigma_mins1[3*gs//4]:.4f}  grad={grads1[3*gs//4]:.4f}  beta={best_betas1[3*gs//4]:.4f}")
    print(f"  gamma~tmin:   sigma={sigma_mins1[-1]:.4f}  grad={grads1[-1]:.4f}  beta={best_betas1[-1]:.4f}")

    # Where is the max gradient?
    max_grad_idx = np.argmax(grads1)
    print(f"\n  max gradient at gamma={gammas1[max_grad_idx]:.4f}, "
          f"grad={grads1[max_grad_idx]:.6f}, "
          f"sigma={sigma_mins1[max_grad_idx]:.4f}, "
          f"beta={best_betas1[max_grad_idx]:.4f}")

    # Test 4: Different beta, same eta/gamma/n
    print("\n=== Test 4: max gradient for different beta ===")
    for beta in [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0]:
        s = generate_weibull_sample(beta, 1000.0, 1000.0, 7, 42 + int(beta*1000))
        t_s = s
        n_s = len(t_s)
        ranks_s = (np.arange(1, n_s + 1) - 0.3) / (n_s + 0.4)
        neg_ln_s = -np.log(1 - ranks_s)

        def calc_std(b, g, t_arr, neg_ln):
            if b <= 0: return float('inf')
            denom = np.power(neg_ln, 1.0/b)
            etas = (t_arr - g) / denom
            return np.std(etas, ddof=1)

        def find_beta(g, t_arr, neg_ln):
            if g >= t_arr[0]: return None, float('inf')
            res = minimize_scalar(
                lambda b: calc_std(b, g, t_arr, neg_ln),
                bounds=(0.1, 15.0), method='bounded'
            )
            return res.x, res.fun

        gammas = np.linspace(0, t_s[0] * 0.999999, 200)
        sigmas = []
        for g in gammas:
            _, sig = find_beta(g, t_s, neg_ln_s)
            sigmas.append(sig)
        sigmas = np.array(sigmas)
        grads = np.gradient(sigmas, gammas)
        max_g = np.max(grads)
        print(f"  beta={beta:5.1f}  t_min={t_s[0]:.2f}  max_grad={max_g:.6f}  "
              f"delta_limit~{max_g:.3f}")


if __name__ == '__main__':
    main()
