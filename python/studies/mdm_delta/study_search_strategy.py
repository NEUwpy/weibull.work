"""
搜索策略验证

对比不同搜索策略的效率和精度：
1. 全量细扫 (step=0.001) — 作为 ground truth
2. 两阶段搜索 (coarse=0.02, fine=0.001)
3. 三阶段搜索 (coarse=0.05, medium=0.01, fine=0.001)
4. 自适应搜索 (Brent/scipy minimize_scalar)
"""

import sys
import time
import json
import numpy as np
from pathlib import Path
from scipy.optimize import minimize_scalar, brentq

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta, eta, gamma, n, seed):
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    t = gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)
    return np.sort(t)


def run_mdm(sample, delta, gamma_steps=60):
    """Run MDM, return (beta, eta, gamma) or None"""
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return None
        return (result[0], result[1], result[2])
    except:
        return None


def mse_of_delta(sample, delta, true_params, gamma_steps=60):
    """Compute MSE for a given delta"""
    est = run_mdm(sample, delta, gamma_steps)
    if est is None:
        return None
    return ((est[0] - true_params[0]) / true_params[0]) ** 2 + \
           ((est[1] - true_params[1]) / true_params[1]) ** 2 + \
           ((est[2] - true_params[2]) / true_params[2]) ** 2


def strategy_full_scan(sample, true_params, step=0.001, delta_max=2.0):
    """Full fine scan as ground truth"""
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


def strategy_two_phase(sample, true_params, coarse_step=0.02, fine_step=0.001,
                       delta_max=2.0, fine_range=0.02):
    """Two-phase: coarse scan then fine scan"""
    # Phase 1: coarse
    coarse_deltas = np.arange(coarse_step, delta_max + coarse_step/2, coarse_step)
    n_calls = 0
    best_coarse_delta = coarse_step
    best_coarse_mse = float('inf')

    for d in coarse_deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_coarse_mse:
            best_coarse_mse = mse
            best_coarse_delta = d

    # Phase 2: fine around best coarse
    fine_start = max(fine_step, best_coarse_delta - fine_range)
    fine_end = best_coarse_delta + fine_range
    fine_deltas = np.arange(fine_start, fine_end + fine_step/2, fine_step)

    best_delta = best_coarse_delta
    best_mse = best_coarse_mse

    for d in fine_deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    return best_delta, best_mse, n_calls


def strategy_three_phase(sample, true_params, coarse_step=0.05, medium_step=0.01,
                          fine_step=0.001, delta_max=2.0):
    """Three-phase search"""
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

    # Phase 2: medium around best coarse
    med_start = max(medium_step, best_delta - coarse_step)
    med_end = best_delta + coarse_step
    med_deltas = np.arange(med_start, med_end + medium_step/2, medium_step)

    for d in med_deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    # Phase 3: fine around best medium
    fine_start = max(fine_step, best_delta - medium_step)
    fine_end = best_delta + medium_step
    fine_deltas = np.arange(fine_start, fine_end + fine_step/2, fine_step)

    for d in fine_deltas:
        mse = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    return best_delta, best_mse, n_calls


def strategy_scipy_minimize(sample, true_params, delta_max=2.0):
    """Use scipy minimize_scalar (Brent) for optimization"""
    n_calls = [0]

    def objective(delta):
        n_calls[0] += 1
        mse = mse_of_delta(sample, delta, true_params)
        if mse is None:
            return 1e6  # penalty for failure
        return mse

    result = minimize_scalar(objective, bounds=(0.001, delta_max), method='bounded',
                            options={'xatol': 0.0001})
    return result.x, result.fun, n_calls[0]


def main():
    output_dir = Path(__file__).parent / 'data' / 'curve_study'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Test cases
    cases = [
        (2.0, 1000.0, 1000.0, 7, 'b2_e1000_n7', 3742),
        (1.0, 1000.0, 1000.0, 7, 'b1_e1000_n7', 2742),
        (5.0, 1000.0, 1000.0, 7, 'b5_e1000_n7', 6742),
        (2.0, 1000.0, 1000.0, 20, 'b2_e1000_n20', 5042),
        (2.0, 1000.0, 1000.0, 5, 'b2_e1000_n5', 3542),
    ]

    results = []

    for beta, eta, gamma, n, label, seed in cases:
        sample = generate_weibull_sample(beta, eta, gamma, n, seed)
        true_params = (beta, eta, gamma)
        print(f"\n{'='*60}")
        print(f"{label} (beta={beta}, n={n})")
        print(f"{'='*60}")

        # Ground truth
        t0 = time.time()
        gt_delta, gt_mse, gt_calls = strategy_full_scan(sample, true_params)
        gt_time = time.time() - t0
        print(f"  Full scan:     delta={gt_delta:.4f}  MSE={gt_mse:.6f}  calls={gt_calls:4d}  time={gt_time:.1f}s")

        # Two-phase
        t0 = time.time()
        tp_delta, tp_mse, tp_calls = strategy_two_phase(sample, true_params)
        tp_time = time.time() - t0
        tp_err = abs(tp_mse - gt_mse) / gt_mse * 100 if gt_mse > 0 else 0
        print(f"  Two-phase:     delta={tp_delta:.4f}  MSE={tp_mse:.6f}  calls={tp_calls:4d}  time={tp_time:.1f}s  err={tp_err:.1f}%")

        # Three-phase
        t0 = time.time()
        th_delta, th_mse, th_calls = strategy_three_phase(sample, true_params)
        th_time = time.time() - t0
        th_err = abs(th_mse - gt_mse) / gt_mse * 100 if gt_mse > 0 else 0
        print(f"  Three-phase:   delta={th_delta:.4f}  MSE={th_mse:.6f}  calls={th_calls:4d}  time={th_time:.1f}s  err={th_err:.1f}%")

        # Scipy minimize
        t0 = time.time()
        sp_delta, sp_mse, sp_calls = strategy_scipy_minimize(sample, true_params)
        sp_time = time.time() - t0
        sp_err = abs(sp_mse - gt_mse) / gt_mse * 100 if gt_mse > 0 else 0
        print(f"  Scipy Brent:   delta={sp_delta:.4f}  MSE={sp_mse:.6f}  calls={sp_calls:4d}  time={sp_time:.1f}s  err={sp_err:.1f}%")

        results.append({
            'label': label,
            'full_scan': {'delta': gt_delta, 'mse': gt_mse, 'calls': gt_calls, 'time': gt_time},
            'two_phase': {'delta': tp_delta, 'mse': tp_mse, 'calls': tp_calls, 'time': tp_time, 'err_pct': tp_err},
            'three_phase': {'delta': th_delta, 'mse': th_mse, 'calls': th_calls, 'time': th_time, 'err_pct': th_err},
            'scipy': {'delta': sp_delta, 'mse': sp_mse, 'calls': sp_calls, 'time': sp_time, 'err_pct': sp_err},
        })

    # Summary
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")
    print(f"{'Case':20s} {'Full':>10s} {'2-phase':>10s} {'3-phase':>10s} {'Scipy':>10s}")
    print(f"{'':20s} {'calls':>10s} {'calls/err%':>10s} {'calls/err%':>10s} {'calls/err%':>10s}")
    print("-" * 80)
    for r in results:
        print(f"{r['label']:20s} "
              f"{r['full_scan']['calls']:10d} "
              f"{r['two_phase']['calls']:4d}/{r['two_phase']['err_pct']:5.1f}% "
              f"{r['three_phase']['calls']:4d}/{r['three_phase']['err_pct']:5.1f}% "
              f"{r['scipy']['calls']:4d}/{r['scipy']['err_pct']:5.1f}%")

    with open(output_dir / 'search_strategy_comparison.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == '__main__':
    main()
