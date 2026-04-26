"""
诊断实验 1：固定 δ 对比

目的：排除 δ 选择的影响，直接比较 MDM 在不同 n 下的表现。
如果 n=15 在固定 δ 下优于 n=5，说明问题出在 δ 搜索/边界排除。
如果 n=5 在固定 δ 下仍优于 n=15，说明 MDM 方法本身的性质。

使用方法：
    cd python/studies/mdm_delta
    python diagnose_fixed_delta.py
"""

import sys
import csv
import json
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


def main():
    beta, eta, gamma = 2.0, 1000.0, 1000.0
    sample_sizes = [5, 7, 10, 15, 20]
    deltas = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0]
    mc_runs = 500

    print("=" * 70)
    print("Experiment 1: Fixed delta comparison")
    print(f"beta={beta}, eta={eta}, gamma={gamma}")
    print(f"sample sizes: {sample_sizes}")
    print(f"deltas: {deltas}")
    print(f"MC runs: {mc_runs}")
    print("=" * 70)

    results = {}  # {n: {delta: [mse_list]}}

    for n in sample_sizes:
        results[n] = {}
        for delta in deltas:
            mse_list = []
            no_solution = 0

            for sim_id in range(1, mc_runs + 1):
                seed = sim_id + int(beta * 1000) + int(eta) + n * 100
                sample = generate_weibull_sample(beta, eta, gamma, n, seed)
                est = run_mdm(sample, delta)

                if est is None:
                    no_solution += 1
                    continue

                eb, ee, eg = est
                if eb <= 0 or eb > 50 or ee <= 0 or ee > 1e6:
                    no_solution += 1
                    continue

                mse_list.append(relative_mse(est, beta, eta, gamma))

            results[n][delta] = {
                'mean_mse': np.mean(mse_list) if mse_list else float('nan'),
                'median_mse': np.median(mse_list) if mse_list else float('nan'),
                'std_mse': np.std(mse_list) if mse_list else float('nan'),
                'success': len(mse_list),
                'no_solution': no_solution,
            }

    # Print results table
    print(f"\n{'n':>4}", end='')
    for d in deltas:
        print(f"  d={d:.2f}", end='')
    print(f"  {'avg':>8}")
    print("-" * (4 + 10 * len(deltas) + 10))

    for n in sample_sizes:
        print(f"{n:>4}", end='')
        avg_mse = []
        for d in deltas:
            r = results[n][d]
            if r['success'] > 0:
                print(f"  {r['mean_mse']:8.4f}", end='')
                avg_mse.append(r['mean_mse'])
            else:
                print(f"  {'N/A':>8}", end='')
        if avg_mse:
            print(f"  {np.mean(avg_mse):8.4f}", end='')
        print()

    # Print success rates
    print(f"\nSuccess rates:")
    print(f"{'n':>4}", end='')
    for d in deltas:
        print(f"  d={d:.2f}", end='')
    print()
    print("-" * (4 + 10 * len(deltas)))

    for n in sample_sizes:
        print(f"{n:>4}", end='')
        for d in deltas:
            r = results[n][d]
            rate = r['success'] / mc_runs * 100
            print(f"  {rate:7.0f}%", end='')
        print()

    # Summary
    print(f"\n{'=' * 70}")
    print("Average MSE across all deltas (lower = better):")
    for n in sample_sizes:
        avg = np.mean([results[n][d]['mean_mse'] for d in deltas if results[n][d]['success'] > 0])
        print(f"  n={n:>2}: {avg:.4f}")
    print("=" * 70)

    # Save to CSV
    output_dir = Path(__file__).parent / 'data'
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / 'fixed_delta_comparison.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['n', 'delta', 'mean_mse', 'median_mse', 'std_mse', 'success', 'no_solution'])
        for n in sample_sizes:
            for d in deltas:
                r = results[n][d]
                writer.writerow([n, d, round(r['mean_mse'], 6), round(r['median_mse'], 6),
                                 round(r['std_mse'], 6), r['success'], r['no_solution']])
    print(f"\nCSV saved: {csv_path}")

    # Copy to public/ai/data/
    import shutil
    public_dir = PROJECT_ROOT / 'public' / 'ai' / 'data'
    public_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, public_dir / 'fixed_delta_comparison.csv')
    print(f"Copied to: {public_dir / 'fixed_delta_comparison.csv'}")


if __name__ == '__main__':
    main()
