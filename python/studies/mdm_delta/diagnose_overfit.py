"""
诊断实验 6：最优 δ 是否过拟合噪声？

核心问题：n=5 在"最优 δ"下 MSE 更小，是因为：
A. n=5 真的能找到更好的 δ（真实信号）
B. n=5 的最优 δ 过拟合了当前样本的噪声（不泛化）

方法：
1. 对每个样本，用粗搜+细搜找到最优 δ
2. 生成一个新样本（相同参数，不同种子）
3. 用步骤 1 的最优 δ 在新样本上跑 MDM
4. 比较：训练 MSE vs 测试 MSE

如果 n=5 的测试 MSE >> 训练 MSE → 过拟合
如果 n=15 的测试 MSE ≈ 训练 MSE → 泛化良好

使用方法：
    cd python/studies/mdm_delta
    python diagnose_overfit.py
"""

import sys
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta, eta, gamma, n, seed):
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    return np.sort(gamma + eta * (-np.log(1 - u)) ** (1 / beta))


def run_mdm(sample, delta, gamma_steps=60):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps)
        if result[4] == "no_intersection":
            return None
        return (result[0], result[1], result[2])
    except:
        return None


def relative_mse(est, true_beta, true_eta, true_gamma):
    eb, ee, eg = est
    return ((eb - true_beta) / true_beta) ** 2 + \
           ((ee - true_eta) / true_eta) ** 2 + \
           ((eg - true_gamma) / true_gamma) ** 2


def find_best_delta(sample, true_beta, true_eta, true_gamma, delta_grid, gamma_steps=60):
    """在 delta_grid 中找最优 delta"""
    best_delta = None
    best_mse = float('inf')

    for delta in delta_grid:
        est = run_mdm(sample, delta, gamma_steps)
        if est is None:
            continue
        eb, ee, eg = est
        if eb <= 0 or eb > 50 or ee <= 0 or ee > 1e6:
            continue
        mse = relative_mse(est, true_beta, true_eta, true_gamma)
        if mse < best_mse:
            best_mse = mse
            best_delta = delta

    return best_delta, best_mse


def main():
    beta, eta, gamma = 2.0, 1000.0, 1000.0
    sample_sizes = [5, 7, 10, 15, 20]
    mc_runs = 300  # 每组做 300 对训练/测试

    # delta grid: coarse + fine
    coarse_grid = np.arange(0.05, 1.05, 0.1)
    fine_grid = np.arange(0.001, 1.001, 0.01)
    delta_grid = np.unique(np.concatenate([coarse_grid, fine_grid]))
    delta_grid = np.round(delta_grid, 4)

    print("=" * 70)
    print("Experiment 6: Optimal delta overfitting test")
    print(f"beta={beta}, eta={eta}, gamma={gamma}")
    print(f"sample sizes: {sample_sizes}")
    print(f"MC runs: {mc_runs}")
    print(f"delta grid: {len(delta_grid)} points")
    print("=" * 70)

    results = {}

    for n in sample_sizes:
        train_mse_list = []
        test_mse_list = []
        train_delta_list = []
        no_solution = 0

        for sim_id in range(1, mc_runs + 1):
            # Training sample
            seed_train = sim_id + int(beta * 1000) + int(eta) + n * 100
            sample_train = generate_weibull_sample(beta, eta, gamma, n, seed_train)

            # Test sample (different seed, same params)
            seed_test = sim_id + 99999 + int(beta * 1000) + int(eta) + n * 100
            sample_test = generate_weibull_sample(beta, eta, gamma, n, seed_test)

            # Find optimal delta on training sample
            best_delta, train_mse = find_best_delta(
                sample_train, beta, eta, gamma, delta_grid
            )

            if best_delta is None:
                no_solution += 1
                continue

            # Apply optimal delta to test sample
            test_est = run_mdm(sample_test, best_delta)
            if test_est is None:
                no_solution += 1
                continue

            eb, ee, eg = test_est
            if eb <= 0 or eb > 50 or ee <= 0 or ee > 1e6:
                no_solution += 1
                continue

            test_mse = relative_mse(test_est, beta, eta, gamma)

            train_mse_list.append(train_mse)
            test_mse_list.append(test_mse)
            train_delta_list.append(best_delta)

        if len(train_mse_list) > 0:
            results[n] = {
                'count': len(train_mse_list),
                'no_solution': no_solution,
                'train_mse_mean': np.mean(train_mse_list),
                'train_mse_median': np.median(train_mse_list),
                'test_mse_mean': np.mean(test_mse_list),
                'test_mse_median': np.median(test_mse_list),
                'overfit_ratio': np.mean(test_mse_list) / max(np.mean(train_mse_list), 1e-10),
                'delta_mean': np.mean(train_delta_list),
                'delta_std': np.std(train_delta_list),
            }
        else:
            results[n] = {'count': 0, 'no_solution': no_solution}

    # Print results
    print(f"\n{'n':>4} {'pairs':>6} {'train_mse':>10} {'test_mse':>10} {'overfit':>8} {'delta_mean':>10} {'delta_std':>10}")
    print("-" * 70)

    for n in sample_sizes:
        r = results[n]
        if r['count'] > 0:
            print(f"{n:>4} {r['count']:>6} {r['train_mse_mean']:>10.4f} {r['test_mse_mean']:>10.4f} "
                  f"{r['overfit_ratio']:>8.2f}x {r['delta_mean']:>10.4f} {r['delta_std']:>10.4f}")
        else:
            print(f"{n:>4} {0:>6} {'N/A':>10} {'N/A':>10} {'N/A':>8}")

    print(f"\n{'=' * 70}")
    print("Interpretation:")
    print("  overfit_ratio = test_mse / train_mse")
    print("  ratio ~1.0: optimal delta generalizes well")
    print("  ratio >>1.0: optimal delta overfits to training noise")
    print("=" * 70)

    # Also compute: what if we use a FIXED delta (e.g., 0.2) for all samples?
    print(f"\n{'=' * 70}")
    print("Comparison: fixed delta=0.2 vs optimal delta")
    fixed_delta = 0.2

    for n in sample_sizes:
        fixed_mse_list = []
        for sim_id in range(1, mc_runs + 1):
            seed_test = sim_id + 99999 + int(beta * 1000) + int(eta) + n * 100
            sample_test = generate_weibull_sample(beta, eta, gamma, n, seed_test)
            est = run_mdm(sample_test, fixed_delta)
            if est is None:
                continue
            eb, ee, eg = est
            if eb <= 0 or eb > 50 or ee <= 0 or ee > 1e6:
                continue
            fixed_mse_list.append(relative_mse(est, beta, eta, gamma))

        r = results[n]
        fixed_avg = np.mean(fixed_mse_list) if fixed_mse_list else float('nan')
        print(f"  n={n:>2}: fixed_delta MSE={fixed_avg:.4f}, optimal_delta test MSE={r.get('test_mse_mean', float('nan')):.4f}")


if __name__ == '__main__':
    main()
