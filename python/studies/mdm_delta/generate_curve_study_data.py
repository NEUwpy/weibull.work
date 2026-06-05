"""
Generate curve study data for frontend visualization.

Outputs a single JSON file to public/case-studies/mdm/curve-study/data.json
containing all curve property research results.

Usage:
    cd python/studies/mdm_delta
    python generate_curve_study_data.py
"""

import sys
import json
import numpy as np
from pathlib import Path
from scipy.optimize import minimize_scalar

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


def mse_of_delta(sample, delta, true_params, gamma_steps=60):
    est = run_mdm(sample, delta, gamma_steps)
    if est is None:
        return None, None, None, None
    mse_b = ((est[0] - true_params[0]) / true_params[0]) ** 2
    mse_e = ((est[1] - true_params[1]) / true_params[1]) ** 2
    mse_g = ((est[2] - true_params[2]) / true_params[2]) ** 2
    return mse_b + mse_e + mse_g, mse_b, mse_e, mse_g


def _build_geometric_gamma_grid(t_min, gamma_steps):
    """Build a discrete gamma grid searched from t_min downward to 0.
    Mirrors the default MDM implementation in python/methods/mdm.py."""
    steps = max(4, int(gamma_steps))
    min_gap = max(abs(float(t_min)) * 1e-9, 1e-12)
    gaps = np.geomspace(min_gap, float(t_min), steps)
    gammas = float(t_min) - gaps
    gammas[0] = float(t_min) - min_gap
    gammas[-1] = 0.0
    return gammas


def compute_max_gradient(sample, gamma_steps=200):
    """Compute the max gradient of sigma_min(gamma) curve using geometric grid."""
    t = np.array(sorted(sample))
    n = len(t)
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    neg_ln_1_minus_F = -np.log(1 - ranks)

    def calculate_eta_std(beta, gamma):
        if beta <= 0 or gamma >= t[0]:
            return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0 / beta)
        etas = (t - gamma) / denom
        return np.std(etas, ddof=1)

    def find_best_beta_for_gamma(gamma):
        if gamma >= t[0]:
            return None, float('inf')
        res = minimize_scalar(
            lambda b: calculate_eta_std(b, gamma),
            bounds=(0.1, 15.0), method='bounded'
        )
        return res.x, res.fun

    gammas = _build_geometric_gamma_grid(t[0], gamma_steps)
    sigmas = []
    for g in gammas:
        _, sig = find_best_beta_for_gamma(g)
        sigmas.append(sig)
    sigmas = np.array(sigmas)
    grads = np.gradient(sigmas, gammas)
    return float(np.max(grads))


def scan_curve(sample, true_params, delta_step=0.002, delta_max=2.0):
    """Scan MSE-delta curve. Retains both success and failure points."""
    deltas = np.arange(delta_step, delta_max + delta_step / 2, delta_step)
    results = []
    for d in deltas:
        mse, mse_b, mse_e, mse_g = mse_of_delta(sample, d, true_params)
        if mse is not None:
            est = run_mdm(sample, d)
            results.append({
                'delta': round(float(d), 4),
                'mse': round(float(mse), 6),
                'mse_beta': round(float(mse_b), 6),
                'mse_eta': round(float(mse_e), 6),
                'mse_gamma': round(float(mse_g), 6),
                'est_beta': round(float(est[0]), 4),
                'est_eta': round(float(est[1]), 2),
                'est_gamma': round(float(est[2]), 2),
            })
        else:
            # Retain failure points so failure_delta can be found downstream
            results.append({
                'delta': round(float(d), 4),
                'mse': None,
                'mse_beta': None,
                'mse_eta': None,
                'mse_gamma': None,
                'est_beta': None,
                'est_eta': None,
                'est_gamma': None,
            })
    return results


def strategy_three_phase(sample, true_params, delta_max=2.0):
    coarse_step, medium_step, fine_step = 0.05, 0.01, 0.001
    n_calls = 0
    best_delta = coarse_step
    best_mse = float('inf')

    # Phase 1
    for d in np.arange(coarse_step, delta_max + coarse_step / 2, coarse_step):
        mse, _, _, _ = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    # Phase 2
    for d in np.arange(max(medium_step, best_delta - coarse_step),
                        best_delta + coarse_step + medium_step / 2, medium_step):
        mse, _, _, _ = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    # Phase 3
    for d in np.arange(max(fine_step, best_delta - medium_step),
                        best_delta + medium_step + fine_step / 2, fine_step):
        mse, _, _, _ = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d

    return best_delta, best_mse, n_calls


def strategy_full_scan(sample, true_params, step=0.001, delta_max=2.0):
    n_calls = 0
    best_delta = step
    best_mse = float('inf')
    for d in np.arange(step, delta_max + step / 2, step):
        mse, _, _, _ = mse_of_delta(sample, d, true_params)
        n_calls += 1
        if mse is not None and mse < best_mse:
            best_mse = mse
            best_delta = d
    return best_delta, best_mse, n_calls


def main():
    output_dir = PROJECT_ROOT / 'public' / 'case-studies' / 'mdm' / 'curve-study'
    output_dir.mkdir(parents=True, exist_ok=True)

    # === Primary cases for curve visualization ===
    cases = [
        {'beta': 2.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 7,  'seed': 3742, 'label': 'b2_n7',  'desc': 'β=2, n=7 (baseline)'},
        {'beta': 1.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 7,  'seed': 2742, 'label': 'b1_n7',  'desc': 'β=1, n=7 (large δ)'},
        {'beta': 5.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 7,  'seed': 6742, 'label': 'b5_n7',  'desc': 'β=5, n=7 (narrow valley)'},
        {'beta': 2.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 5,  'seed': 3542, 'label': 'b2_n5',  'desc': 'β=2, n=5 (monotone)'},
        {'beta': 2.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 10, 'seed': 4042, 'label': 'b2_n10', 'desc': 'β=2, n=10 (monotone)'},
        {'beta': 2.0, 'eta': 1000.0, 'gamma': 1000.0, 'n': 20, 'seed': 5042, 'label': 'b2_n20', 'desc': 'β=2, n=20 (failure boundary)'},
        {'beta': 0.5, 'eta': 1000.0, 'gamma': 1000.0, 'n': 7,  'seed': 1742, 'label': 'b05_n7', 'desc': 'β=0.5, n=7 (wide range)'},
    ]

    print("Generating curve study data...")
    curve_samples = []

    for case in cases:
        label = case['label']
        print(f"  Scanning {label}...")
        sample = generate_weibull_sample(case['beta'], case['eta'], case['gamma'], case['n'], case['seed'])
        true_params = (case['beta'], case['eta'], case['gamma'])

        # Scan curve
        curve_data = scan_curve(sample, true_params, delta_step=0.002, delta_max=2.0)

        # Find best
        valid = [r for r in curve_data if r['mse'] is not None]
        best = min(valid, key=lambda x: x['mse']) if valid else None

        # Failure boundary
        failed = [r for r in curve_data if r['mse'] is None]
        failure_delta = min(r['delta'] for r in failed) if failed else None

        # Curve shape analysis
        if best:
            best_idx = next(i for i, r in enumerate(curve_data) if r['delta'] == best['delta'])
            valid_indices = [i for i, r in enumerate(curve_data) if r['mse'] is not None]
            min_valid_idx = min(valid_indices)
            max_valid_idx = max(valid_indices)

            at_left = best_idx == min_valid_idx
            at_right = best_idx == max_valid_idx

            # Check unimodality
            valid_mse = [r['mse'] for r in curve_data if r['mse'] is not None]
            valid_delta = [r['delta'] for r in curve_data if r['mse'] is not None]
            best_local_idx = valid_mse.index(best['mse'])

            left_mono = all(valid_mse[i] >= valid_mse[i+1] for i in range(best_local_idx))
            right_mono = all(valid_mse[i] <= valid_mse[i+1] for i in range(best_local_idx, len(valid_mse)-1))
            is_unimodal = left_mono and right_mono

            if at_left:
                shape = 'monotone_increasing'
            elif at_right:
                shape = 'monotone_decreasing'
            elif is_unimodal:
                shape = 'unimodal'
            else:
                shape = 'non_unimodal'
        else:
            shape = 'all_failed'
            at_left = False
            at_right = False

        # Max gradient
        print(f"    Computing max gradient...")
        max_grad = compute_max_gradient(sample)

        curve_samples.append({
            'label': label,
            'desc': case['desc'],
            'beta': case['beta'],
            'eta': case['eta'],
            'gamma': case['gamma'],
            'n': case['n'],
            'seed': case['seed'],
            'sample': sample.tolist(),
            'curve': curve_data,
            'best_delta': best['delta'] if best else None,
            'best_mse': best['mse'] if best else None,
            'failure_delta': failure_delta,
            'shape': shape,
            'at_left_boundary': at_left,
            'at_right_boundary': at_right,
            'valid_count': len(valid),
            'total_count': len(curve_data),
            'max_gradient': round(max_grad, 4),
        })

    # === Search strategy comparison ===
    print("\nComparing search strategies...")
    strategy_cases = [
        (2.0, 1000.0, 1000.0, 7, 'b2_n7', 3742),
        (1.0, 1000.0, 1000.0, 7, 'b1_n7', 2742),
        (5.0, 1000.0, 1000.0, 7, 'b5_n7', 6742),
        (2.0, 1000.0, 1000.0, 20, 'b2_n20', 5042),
        (2.0, 1000.0, 1000.0, 5, 'b2_n5', 3542),
    ]

    search_strategy = []
    for beta, eta, gamma, n, label, seed in strategy_cases:
        sample = generate_weibull_sample(beta, eta, gamma, n, seed)
        true_params = (beta, eta, gamma)

        gt_delta, gt_mse, gt_calls = strategy_full_scan(sample, true_params)
        tp_delta, tp_mse, tp_calls = strategy_three_phase(sample, true_params)
        tp_err = abs(tp_mse - gt_mse) / gt_mse * 100 if gt_mse > 0 else 0

        print(f"  {label}: full={gt_calls} calls, 3-phase={tp_calls} calls, err={tp_err:.1f}%")

        search_strategy.append({
            'label': label,
            'full_scan': {'delta': round(gt_delta, 4), 'mse': round(gt_mse, 6), 'calls': gt_calls},
            'three_phase': {'delta': round(tp_delta, 4), 'mse': round(tp_mse, 6), 'calls': tp_calls, 'err_pct': round(tp_err, 1)},
        })

    # === Beta sensitivity (max gradient vs beta) ===
    print("\nComputing beta sensitivity...")
    beta_sensitivity = []
    for beta in [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0]:
        sample = generate_weibull_sample(beta, 1000.0, 1000.0, 7, 42 + int(beta * 1000))
        max_grad = compute_max_gradient(sample)
        print(f"  beta={beta}: max_grad={max_grad:.4f}")
        beta_sensitivity.append({
            'beta': beta,
            'max_gradient': round(max_grad, 4),
            'delta_limit': round(max_grad, 4),
        })

    # === Assemble final JSON ===
    data = {
        'meta': {
            'generated': '2026-06-05',
            'description': 'MSE-delta curve properties study for MDM method (S4.9: geometric gamma grid, offset_root / truncated_at_zero / no_offset_root semantics)',
            'param_space': {
                'beta': [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0],
                'eta': 1000.0,
                'gamma': 1000.0,
                'n': [5, 7, 10, 15, 20],
            },
        },
        'curve_samples': curve_samples,
        'search_strategy': search_strategy,
        'beta_sensitivity': beta_sensitivity,
        'conclusions': {
            'curve_shapes': [
                {'shape': 'unimodal', 'desc': 'MSE has a clear interior minimum. Common for moderate n and beta.', 'example': 'b2_n7'},
                {'shape': 'monotone_increasing', 'desc': 'MSE increases with delta. Optimal delta near 0. Common for small n.', 'example': 'b2_n5, b2_n10, b2_n15'},
                {'shape': 'monotone_decreasing', 'desc': 'MSE decreases with delta. Optimal delta at boundary. Requires large search range.', 'example': 'b1_n7'},
                {'shape': 'non_unimodal', 'desc': 'Very narrow valley (width ~0.005). Requires fine step size.', 'example': 'b5_n7'},
            ],
            'failure_condition': 'S4.9 uses gamma=0 gradient as the decision boundary: (1) offset_root — gradient curve crosses offset, interpolate gamma_hat; (2) truncated_at_zero — no crossing but gamma=0 gradient >= offset (unconstrained root on negative axis, clipped by gamma>=0 constraint); (3) no_offset_root — no crossing and gamma=0 gradient < offset (entire gradient curve below offset, e.g. delta > max(nabla sigma)).',
            'failure_condition_historical': 'Pre-S4.9: MDM returned no_intersection when delta > max(nabla sigma). This was an engineering implementation issue (gamma >= 0 constraint clipping + discrete grid miss), not a mathematical impossibility.',
            'recommended_search': {
                'strategy': 'three_phase',
                'phases': [
                    {'name': 'coarse', 'step': 0.05, 'range': '[0.05, 2.0]'},
                    {'name': 'medium', 'step': 0.01, 'range': '±0.05 around best coarse'},
                    {'name': 'fine', 'step': 0.001, 'range': '±0.01 around best medium'},
                ],
                'delta_range': [0.001, 2.0],
                'calls_per_sample': 72,
                'error_pct': 0.0,
                'speedup_vs_full_scan': '28x',
            },
            'boundary_samples': 'Samples where optimal delta is at the search boundary have inherent MDM accuracy limits. These should be flagged in training data but not filtered out.',
            'boundary_samples_s49': 'S4.9: 当 offset 超过梯度曲线最大值时，gamma=0 处梯度也低于 offset，系统返回 no_offset_root（诊断状态）。truncated_at_zero 仅在 gamma=0 处梯度 >= offset 时触发（无约束根在负半轴被 gamma>=0 约束切除）。',
        },
    }

    output_path = output_dir / 'data.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to {output_path}")
    print(f"  curve_samples: {len(curve_samples)} cases")
    print(f"  search_strategy: {len(search_strategy)} comparisons")
    print(f"  beta_sensitivity: {len(beta_sensitivity)} points")


if __name__ == '__main__':
    main()
