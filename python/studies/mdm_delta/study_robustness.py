"""
三阶段搜索稳健性验证

对多个随机种子验证三阶段搜索的一致性。
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


def run_mdm(sample, delta, gamma_steps=60):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return None
        return (result[0], result[1], result[2])
    except:
        return None


def mse_of_delta(sample, delta, true_params):
    est = run_mdm(sample, delta)
    if est is None:
        return None
    return ((est[0] - true_params[0]) / true_params[0]) ** 2 + \
           ((est[1] - true_params[1]) / true_params[1]) ** 2 + \
           ((est[2] - true_params[2]) / true_params[2]) ** 2


def strategy_three_phase(sample, true_params, delta_max=2.0):
    coarse_step, medium_step, fine_step = 0.05, 0.01, 0.001

    # Phase 1: coarse
    coarse_deltas = np.arange(coarse_step, delta_max + coarse_step/2, coarse_step)
    n_calls = 0
    best_delta = coarse_step
    best_mse = float('inf')

    for d in coarse_deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    # Phase 2: medium
    med_start = max(medium_step, best_delta - coarse_step)
    med_end = best_delta + coarse_step
    for d in np.arange(med_start, med_end + medium_step/2, medium_step):
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    # Phase 3: fine
    fine_start = max(fine_step, best_delta - medium_step)
    fine_end = best_delta + medium_step
    for d in np.arange(fine_start, fine_end + fine_step/2, fine_step):
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    return best_delta, best_mse, n_calls


def strategy_full_scan(sample, true_params, step=0.001, delta_max=2.0):
    deltas = np.arange(step, delta_max + step/2, step)
    n_calls = 0
    best_delta = step
    best_mse = float('inf')
    for d in deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d
    return best_delta, best_mse, n_calls


def main():
    # Test multiple seeds for each case
    cases = [
        (2.0, 1000.0, 1000.0, 7, 'b2_n7', 20),
        (1.0, 1000.0, 1000.0, 7, 'b1_n7', 20),
        (5.0, 1000.0, 1000.0, 7, 'b5_n7', 20),
        (2.0, 1000.0, 1000.0, 20, 'b2_n20', 10),
    ]

    for beta, eta, gamma, n, label, n_seeds in cases:
        print(f"\n{'='*60}")
        print(f"{label} (beta={beta}, n={n}, {n_seeds} seeds)")
        print(f"{'='*60}")

        tp_deltas = []
        tp_mses = []
        gt_deltas = []
        gt_mses = []
        disagreements = 0

        for i in range(n_seeds):
            seed = 42 + int(beta * 1000) + int(eta) + n * 100 + i * 10000
            sample = generate_weibull_sample(beta, eta, gamma, n, seed)
            true_params = (beta, eta, gamma)

            # Three-phase (fast)
            tp_d, tp_m, tp_c = strategy_three_phase(sample, true_params)

            # Full scan (ground truth) - only for first 5 seeds to save time
            if i < 5:
                gt_d, gt_m, gt_c = strategy_full_scan(sample, true_params)
                gt_deltas.append(gt_d)
                gt_mses.append(gt_m)

                if abs(tp_d - gt_d) > 0.002:
                    disagreements += 1
                    print(f"  seed={seed} DISAGREE: tp_delta={tp_d:.4f} gt_delta={gt_d:.4f} "
                          f"tp_mse={tp_m:.6f} gt_mse={gt_m:.6f}")

            tp_deltas.append(tp_d)
            tp_mses.append(tp_m)

        # Summary
        tp_deltas = np.array(tp_deltas)
        tp_mses = np.array(tp_mses)
        print(f"\n  Three-phase results ({n_seeds} seeds):")
        print(f"    delta: mean={np.mean(tp_deltas):.4f} std={np.std(tp_deltas):.4f} "
              f"min={np.min(tp_deltas):.4f} max={np.max(tp_deltas):.4f}")
        print(f"    MSE:   mean={np.mean(tp_mses):.4f} std={np.std(tp_mses):.4f} "
              f"min={np.min(tp_mses):.4f} max={np.max(tp_mses):.4f}")

        if gt_deltas:
            gt_deltas = np.array(gt_deltas)
            gt_mses = np.array(gt_mses)
            print(f"  Full scan (first 5):")
            print(f"    delta: mean={np.mean(gt_deltas):.4f} std={np.std(gt_deltas):.4f}")
            print(f"    MSE:   mean={np.mean(gt_mses):.4f} std={np.std(gt_mses):.4f}")
            print(f"  Disagreements (>0.002 delta diff): {disagreements}/5")


if __name__ == '__main__':
    main()
