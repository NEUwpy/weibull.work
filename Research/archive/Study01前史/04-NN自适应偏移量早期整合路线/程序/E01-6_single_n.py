"""
E01-6 蒙特卡洛 — 单n运行版

用法: python E01-6_single_n.py <n> [reps]
"""
import sys, os, time, csv
import numpy as np

PROJ_ROOT = "D:/weibull/python"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ_ROOT)
sys.path.insert(0, os.path.join(PROJ_ROOT, "studies", "common"))
sys.path.insert(0, SCRIPT_DIR)

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import aggregate_standard_metrics, quantile_true
from lse_weibull import fit_weibull3_lse

BETA_TRUE = 2.5
ETA_TRUE = 1000.0
GAMMA_TRUE = 100.0
SEED = 2024
R_LEVELS = [0.95, 0.99]
GAMMA_ZERO_TOL = 1e-10
GAMMA_NEAR_ZERO_TOL = 0.01

OUT_DATA = os.path.join(SCRIPT_DIR, '..', '实验数据')

HEADER_RAW = ['n', 'rep', 'method', 'beta_hat', 'eta_hat', 'gamma_hat',
              'converged', 'sample_min', 'gamma_zero', 'gamma_near_zero']


def run_one(t, method):
    if method == 'lse':
        r = fit_weibull3_lse(t)
        return {'beta_hat': r['beta_hat'], 'eta_hat': r['eta_hat'],
                'gamma_hat': r['gamma_hat'], 'converged': True}
    else:
        kw = {'offset': 0.1} if method == 'mdm' else {}
        r = run_method(method, t, **kw)
        return {'beta_hat': r['beta_hat'], 'eta_hat': r['eta_hat'],
                'gamma_hat': r['gamma_hat'], 'converged': r['converged']}


def main():
    n = int(sys.argv[1])
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    methods = ['mdm', 'mle', 'lse']

    csv_path = os.path.join(OUT_DATA, f'E01-6_n{n}.csv')
    rows = []
    metrics_input = {m: [] for m in methods}
    t0 = time.time()

    print(f"n={n}, {reps} reps", flush=True)
    for rep in range(reps):
        t = generate_sample(BETA_TRUE, ETA_TRUE, GAMMA_TRUE, n,
                            repeat_id=rep, seed=SEED)
        smin = float(t[0])

        for method in methods:
            try:
                res = run_one(t, method)
            except Exception:
                res = {'beta_hat': None, 'eta_hat': None, 'gamma_hat': None,
                       'converged': False}

            gh = res['gamma_hat']
            gz = 1 if gh is not None and abs(gh) < GAMMA_ZERO_TOL else 0
            gnz = 1 if gh is not None and abs(gh) < GAMMA_NEAR_ZERO_TOL * GAMMA_TRUE else 0

            rows.append({
                'n': n, 'rep': rep, 'method': method,
                'beta_hat': res['beta_hat'], 'eta_hat': res['eta_hat'],
                'gamma_hat': gh, 'converged': res['converged'],
                'sample_min': smin, 'gamma_zero': gz, 'gamma_near_zero': gnz,
            })
            metrics_input[method].append({
                'beta_hat': res['beta_hat'], 'eta_hat': res['eta_hat'],
                'gamma_hat': gh, 'beta': BETA_TRUE, 'eta': ETA_TRUE,
                'gamma': GAMMA_TRUE, 'converged': res['converged'],
                'sample_min': smin,
            })

        if (rep + 1) % 200 == 0:
            print(f"  {rep+1}/{reps} ({time.time()-t0:.0f}s)", flush=True)

    # Save raw
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEADER_RAW)
        w.writeheader()
        w.writerows(rows)

    # Compute summary for this n
    summary = {}
    for method in methods:
        agg = aggregate_standard_metrics(metrics_input[method], R_levels=R_LEVELS)
        gz_c = sum(1 for r in rows if r['method'] == method and r['gamma_zero'] == 1)
        gnz_c = sum(1 for r in rows if r['method'] == method and r['gamma_near_zero'] == 1)
        entry = {
            'n': n, 'method': method,
            'n_total': agg['n_total'], 'n_valid': agg['n_valid'],
            'n_failure': agg['n_failure'],
            'valid_rate': agg['valid_rate'], 'failure_rate': agg['failure_rate'],
            'gamma_zero_count': gz_c, 'gamma_zero_rate': gz_c / agg['n_total'],
            'gamma_near_zero_count': gnz_c, 'gamma_near_zero_rate': gnz_c / agg['n_total'],
        }
        for p in ('beta', 'eta', 'gamma'):
            ps = agg.get('param_standard', {}).get(p, {})
            for k in ('bias', 'sd', 'rmse', 'mae'):
                entry[f'{k}_{p}'] = ps.get('absolute', {}).get(k)
            for k in ('bias', 'sd', 'rmse', 'mae'):
                entry[f'rel_{k}_{p}'] = ps.get('relative', {}).get(k)
        for R in R_LEVELS:
            tag = f'x{int(R*100)}'
            qs = agg.get('quantile_standard', {}).get(R, {})
            for k in ('bias', 'sd', 'rmse', 'mae'):
                entry[f'{k}_{tag}'] = qs.get('absolute', {}).get(k)
            for k in ('bias', 'sd', 'rmse', 'mae'):
                entry[f'rel_{k}_{tag}'] = qs.get('relative', {}).get(k)
        summary[method] = entry

    # Save summary for this n
    sum_path = os.path.join(OUT_DATA, f'E01-6_summary_n{n}.json')
    import json
    with open(sum_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    # Print quick results
    elapsed = time.time() - t0
    print(f"\nn={n} done in {elapsed:.0f}s ({len(rows)} rows)")
    print(f"{'method':>4} {'n_valid':>7} {'fail%':>6} {'RMSE_β':>7} {'RMSE_x95':>9} {'gz%':>5} {'gnz%':>5}")
    for m in methods:
        e = summary[m]
        print(f"{m:>4} {e['n_valid']:7d} {e['failure_rate']:6.1%} "
              f"{e.get('rmse_beta',0) or 0:7.3f} {e.get('rmse_x95',0) or 0:9.1f} "
              f"{e['gamma_zero_rate']:5.1%} {e['gamma_near_zero_rate']:5.1%}")


if __name__ == '__main__':
    main()
