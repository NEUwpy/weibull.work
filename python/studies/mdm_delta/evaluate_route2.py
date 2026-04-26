"""
Route 2 Evaluation Script - Iterative Convergence Testing

Tests the Route 2 iteration approach:
  delta_0 = 0.5 -> MDM -> N1 -> delta_1 -> MDM -> N1 -> delta_2 -> ... -> convergence

Evaluates:
1. Convergence rate and average steps
2. Final MSE vs fixed delta baselines
3. Route 2 vs Route 1 comparison

Usage:
    cd python/studies/mdm_delta

    # Full evaluation
    python evaluate_route2.py

    # Quick test with fewer samples
    python evaluate_route2.py --test-samples 50 --mc-runs 50

Output:
    data/route2_convergence.csv    - Per-sample convergence details
    data/route2_comparison.csv     - Route 2 vs fixed delta comparison
    data/route2_summary.json       - Summary statistics
"""

import sys
import os
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from itertools import product
from datetime import datetime

import torch
import torch.nn as nn

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


# ============================================================
# Model definition (same as train_model.py)
# ============================================================

class DeltaMLP_N1(nn.Module):
    """Route 2 public model: (beta, eta, gamma) -> optimal delta"""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# ============================================================
# Data generation
# ============================================================

def generate_weibull_sample(beta, eta, gamma, n, seed):
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def run_mdm(sample, delta, gamma_steps=60):
    """Run MDM with given delta. Returns (beta, eta, gamma) or None."""
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return None
        beta, eta, gamma = result[0], result[1], result[2]
        if beta <= 0 or beta > 50 or eta <= 0 or eta > 1e6:
            return None
        return (beta, eta, gamma)
    except Exception:
        return None


def compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma):
    return ((est_beta - true_beta) / true_beta) ** 2 + \
           ((est_eta - true_eta) / true_eta) ** 2 + \
           ((est_gamma - true_gamma) / true_gamma) ** 2


# ============================================================
# Route 2 iteration
# ============================================================

def route2_iterate(sample, n1_model, scaler_params, delta_min, delta_max,
                   delta_0=0.5, max_steps=10, tol=0.001):
    """
    Route 2 iterative convergence.

    Returns: (final_beta, final_eta, final_gamma, final_delta, steps, history, convergence_reason)
    """
    delta = delta_0
    history = []
    converged = False
    convergence_reason = "max_iterations"
    final_beta = final_eta = final_gamma = None

    for step in range(max_steps):
        # Run MDM
        result = run_mdm(sample, delta)
        if result is None:
            convergence_reason = "mdm_failed"
            break

        est_beta, est_eta, est_gamma = result
        final_beta, final_eta, final_gamma = est_beta, est_eta, est_gamma

        history.append({
            'step': step,
            'delta': round(delta, 6),
            'beta': round(est_beta, 4),
            'eta': round(est_eta, 4),
            'gamma': round(est_gamma, 4),
        })

        # N1 predicts next delta
        params_arr = np.array([[est_beta, est_eta, est_gamma]])
        if scaler_params:
            x_mean = np.array(scaler_params['x_mean'])
            x_std = np.array(scaler_params['x_std'])
            params_arr = (params_arr - x_mean) / x_std

        params_tensor = torch.FloatTensor(params_arr)
        with torch.no_grad():
            pred = n1_model(params_tensor).squeeze().item()

        delta_new = pred * (delta_max - delta_min) + delta_min

        # Convergence check
        if abs(delta_new - delta) < tol:
            delta = delta_new
            converged = True
            convergence_reason = "delta_stable"
            history.append({
                'step': step + 1,
                'delta': round(delta_new, 6),
                'beta': None,
                'eta': None,
                'gamma': None,
            })
            break

        delta = delta_new

    return final_beta, final_eta, final_gamma, delta, len(history), history, convergence_reason


# ============================================================
# Main evaluation
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Route 2 evaluation')
    parser.add_argument('--betas', type=str, default='2')
    parser.add_argument('--etas', type=str, default='100,1000,5000')
    parser.add_argument('--gamma', type=float, default=1000)
    parser.add_argument('--sample-sizes', type=str, default='5,7,10,15,20')
    parser.add_argument('--test-samples', type=int, default=100,
                        help='Test samples per parameter combo (default: 100)')
    parser.add_argument('--seed-start', type=int, default=10000,
                        help='Seed start for test data (different from training)')
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--tol', type=float, default=0.001)
    parser.add_argument('--model-dir', type=str, default=None)
    parser.add_argument('--output-dir', type=str, default=None)

    args = parser.parse_args()

    betas = [float(b) for b in args.betas.split(',')]
    etas = [float(e) for e in args.etas.split(',')]
    sample_sizes = [int(n) for n in args.sample_sizes.split(',')]

    model_dir = Path(args.model_dir) if args.model_dir else PROJECT_ROOT / 'python' / 'models' / 'mdm_delta'
    output_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent / 'data'
    output_dir.mkdir(exist_ok=True)

    # Load N1 model
    n1_path = model_dir / 'delta_from_params.pth'
    if not n1_path.exists():
        print(f"ERROR: N1 model not found at {n1_path}")
        print("Please train N1 first: python train_model.py --model-type n1")
        sys.exit(1)

    checkpoint = torch.load(n1_path, map_location='cpu', weights_only=False)
    n1_model = DeltaMLP_N1()
    n1_model.load_state_dict(checkpoint['model_state_dict'])
    n1_model.eval()

    delta_min = checkpoint.get('delta_min', 0.001)
    delta_max = checkpoint.get('delta_max', 1.0)
    scaler_params = checkpoint.get('scaler_params', None)

    print("=" * 60)
    print("Route 2 Evaluation")
    print("=" * 60)
    print(f"N1 model: {n1_path}")
    print(f"delta range: [{delta_min}, {delta_max}]")
    print(f"Test samples per combo: {args.test_samples}")
    print(f"Seed start: {args.seed_start}")
    print(f"Max steps: {args.max_steps}, tolerance: {args.tol}")
    print("=" * 60)

    # Fixed delta baselines
    fixed_deltas = [0.1, 0.2, 0.5]

    # Results storage
    convergence_records = []  # Per-sample details
    comparison_records = []   # Aggregated comparison

    for n in sample_sizes:
        print(f"\n--- Evaluating n={n} ---")

        param_combos = list(product(betas, etas))
        n_converged = 0
        n_total = 0
        n_mdm_fail = 0
        total_steps = 0
        route2_mse_list = []
        fixed_mse_lists = {d: [] for d in fixed_deltas}

        for beta_val, eta_val in param_combos:
            gamma_val = args.gamma
            print(f"  beta={beta_val}, eta={eta_val}, gamma={gamma_val}: ", end='', flush=True)

            combo_converged = 0
            combo_total = 0
            combo_mdm_fail = 0

            for sim_id in range(args.seed_start, args.seed_start + args.test_samples):
                seed = sim_id + int(beta_val * 1000) + int(eta_val) + n * 100
                sample = generate_weibull_sample(beta_val, eta_val, gamma_val, n, seed)
                combo_total += 1
                n_total += 1

                # Route 2 iteration
                final_beta, final_eta, final_gamma, final_delta, steps, history, reason = \
                    route2_iterate(sample, n1_model, scaler_params, delta_min, delta_max,
                                   delta_0=0.5, max_steps=args.max_steps, tol=args.tol)

                if reason == "mdm_failed":
                    combo_mdm_fail += 1
                    n_mdm_fail += 1
                    convergence_records.append({
                        'n': n, 'beta': beta_val, 'eta': eta_val, 'gamma': gamma_val,
                        'seed': seed, 'route2_delta': None, 'route2_mse': None,
                        'steps': steps, 'converged': False, 'reason': reason,
                    })
                else:
                    mse = compute_relative_mse(final_beta, final_eta, final_gamma,
                                               beta_val, eta_val, gamma_val)
                    route2_mse_list.append(mse)
                    converged = (reason == "delta_stable")
                    if converged:
                        combo_converged += 1
                        n_converged += 1
                    total_steps += steps

                    convergence_records.append({
                        'n': n, 'beta': beta_val, 'eta': eta_val, 'gamma': gamma_val,
                        'seed': seed, 'route2_delta': round(final_delta, 6),
                        'route2_mse': round(mse, 6),
                        'steps': steps, 'converged': converged, 'reason': reason,
                    })

                # Fixed delta baselines
                for d in fixed_deltas:
                    result = run_mdm(sample, d)
                    if result is not None:
                        fb, fg, fg2 = result
                        fixed_mse = compute_relative_mse(fb, fg, fg2, beta_val, eta_val, gamma_val)
                        fixed_mse_lists[d].append(fixed_mse)

            conv_rate = combo_converged / combo_total * 100
            print(f"converged {combo_converged}/{combo_total} ({conv_rate:.0f}%), "
                  f"mdm_fail {combo_mdm_fail}")

        # Aggregate for this n
        avg_route2_mse = np.mean(route2_mse_list) if route2_mse_list else float('inf')
        conv_rate = n_converged / max(n_total - n_mdm_fail, 1) * 100
        avg_steps = total_steps / max(n_converged, 1)

        print(f"  Summary: convergence={conv_rate:.1f}%, avg_steps={avg_steps:.1f}, "
              f"route2_mse={avg_route2_mse:.4f}")

        row = {
            'n': n,
            'route2_mse': round(avg_route2_mse, 6),
            'route2_convergence_rate': round(conv_rate, 1),
            'route2_avg_steps': round(avg_steps, 1),
            'route2_samples': len(route2_mse_list),
            'mdm_fail_count': n_mdm_fail,
        }
        for d in fixed_deltas:
            d_str = str(d).replace('.', '_')
            avg_fixed = np.mean(fixed_mse_lists[d]) if fixed_mse_lists[d] else float('inf')
            row[f'fixed_delta_{d_str}_mse'] = round(avg_fixed, 6)
            # Improvement percentage
            if avg_fixed > 0:
                row[f'improvement_vs_{d_str}'] = round((avg_fixed - avg_route2_mse) / avg_fixed * 100, 1)
            else:
                row[f'improvement_vs_{d_str}'] = 0.0
        comparison_records.append(row)

    # Save convergence details
    conv_path = output_dir / 'route2_convergence.csv'
    with open(conv_path, 'w', newline='', encoding='utf-8') as f:
        if convergence_records:
            writer = csv.DictWriter(f, fieldnames=convergence_records[0].keys())
            writer.writeheader()
            writer.writerows(convergence_records)
    print(f"\nConvergence details: {conv_path} ({len(convergence_records)} records)")

    # Save comparison
    comp_path = output_dir / 'route2_comparison.csv'
    with open(comp_path, 'w', newline='', encoding='utf-8') as f:
        if comparison_records:
            writer = csv.DictWriter(f, fieldnames=comparison_records[0].keys())
            writer.writeheader()
            writer.writerows(comparison_records)
    print(f"Comparison: {comp_path} ({len(comparison_records)} records)")

    # Save summary
    summary = {
        'config': {
            'betas': betas,
            'etas': etas,
            'gamma': args.gamma,
            'sampleSizes': sample_sizes,
            'testSamples': args.test_samples,
            'seedStart': args.seed_start,
            'maxSteps': args.max_steps,
            'tolerance': args.tol,
        },
        'results': comparison_records,
        'generatedAt': datetime.now().isoformat(timespec='seconds'),
    }
    summary_path = output_dir / 'route2_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary: {summary_path}")

    # Print final table
    print("\n" + "=" * 70)
    print("Route 2 vs Fixed Delta Comparison")
    print("=" * 70)
    print(f"{'n':>4} | {'Route2 MSE':>11} | {'Conv%':>6} | {'Steps':>5} | ", end='')
    for d in fixed_deltas:
        print(f"{'d=' + str(d) + ' MSE':>11} | ", end='')
    print("Improv vs d=0.2")
    print("-" * 70)
    for row in comparison_records:
        print(f"{row['n']:>4} | {row['route2_mse']:>11.4f} | {row['route2_convergence_rate']:>5.1f}% | "
              f"{row['route2_avg_steps']:>5.1f} | ", end='')
        for d in fixed_deltas:
            d_str = str(d).replace('.', '_')
            print(f"{row[f'fixed_delta_{d_str}_mse']:>11.4f} | ", end='')
        print(f"{row.get('improvement_vs_0_2', 0):>+.1f}%")
    print("=" * 70)


if __name__ == '__main__':
    main()
