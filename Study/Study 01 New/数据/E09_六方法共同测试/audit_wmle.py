"""Diagnose E09 rejected WMLE fits without changing the estimator or its results."""
from pathlib import Path
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'python'))
from methods import wmle
from studies.common.runner import run_method
from studies.common.sample import generate_sample


def inspect_row(row):
    x = generate_sample(row['beta'], row['eta'], row['gamma'], int(row['n']),
                        int(row['repeat_id']), seed='study01_selector_confirmation_20260922_v1')
    assert hashlib.sha256(x.astype('<f8').tobytes()).hexdigest() == row['sample_sha256']
    x = x / 1000
    captured = []
    original = wmle.minimize
    def capture(*args, **kwargs):
        fit = original(*args, **kwargs)
        captured.append(fit)
        return fit
    wmle.minimize = capture
    try:
        res = run_method('wmle', x)
    finally:
        wmle.minimize = original
    info = res['extra']['solution_info']
    fit = captured[info['selected_start']]
    b, g = fit.x
    def residual(v):
        shape, loc = v
        z = x-loc
        logz = np.log(z)
        powers = np.exp(shape * (logz-logz.max()))
        return np.array([wmle.get_weight_j2(len(x))/shape + logz.mean()
                         - np.dot(logz, powers)/powers.sum(),
                         np.mean(1/z)*powers.sum()/np.sum(powers/z)
                         - wmle.get_weight_j3(len(x), shape)])
    # A different solver checks positive-domain roots and then removes only
    # the lower location bound; neither probe replaces the reported estimate.
    def best_fit(starts, lower):
        fits = []
        for start in starts:
            fitted = least_squares(residual, start,
                bounds=([0.01, lower], [9.999999, x.min()-1e-6]),
                ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=2000)
            fits.append(fitted)
            if np.sum(fitted.fun**2)<=1e-8:
                break
        return min(fits, key=lambda f: np.sum(f.fun**2))
    positive = best_fit([[b,max(g,1e-10)],[1.2,.8*x.min()],
                         [2,.3*x.min()],[4,.9*x.min()],[6,1e-10]],0)
    unrestricted = best_fit([positive.x,[2,x.min()-np.std(x)],
                              [5,-np.std(x)],[8,-3*np.std(x)]],-np.inf)
    return {k: row[k] for k in ['cell_id','repeat_id','n','beta','gamma_over_eta','sample_sha256']} | {
        'original_status': info['status'], 'bounded_shape': b,
        'bounded_location': g*1000, 'bounded_objective': float(fit.fun),
        'positive_retry_objective': float(np.sum(positive.fun**2)),
        'positive_retry_shape': float(positive.x[0]),
        'positive_retry_location': float(positive.x[1]*1000),
        'relaxed_objective': float(np.sum(unrestricted.fun**2)),
        'relaxed_shape': float(unrestricted.x[0]),
        'relaxed_location': float(unrestricted.x[1]*1000),
    }


def main():
    data = pd.read_csv(HERE/'per_sample.csv.gz')
    cohort = HERE/'wmle_failure_audit.csv'
    if cohort.exists():
        # Recheck the original rejected cohort after numerical recovery.
        keys=pd.read_csv(cohort)[['cell_id','repeat_id']]
        rejected=data[data.method=='WMLE'].merge(keys,on=['cell_id','repeat_id'],validate='one_to_one')
    else:
        rejected = data[(data.method=='WMLE') & ~data.valid]
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows = []
        for i, result in enumerate(pool.map(inspect_row, rejected.to_dict('records')), 1):
            rows.append(result)
            if i % 50 == 0: print(f'{i}/{len(rejected)}', flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(HERE/'wmle_failure_audit.csv', index=False)
    summary = {
        'rejected': len(out),
        'location_near_zero': int((out.bounded_location.abs()<1e-3).sum()),
        'positive_retry_roots': int((out.positive_retry_objective<=1e-8).sum()),
        'relaxed_negative_roots': int(((out.relaxed_objective<=1e-8)&(out.relaxed_location<0)).sum()),
        'unresolved_relaxed': int((out.relaxed_objective>1e-8).sum()),
        'diagnostic_only': True,
        'method_source': 'https://github.com/dcousin3/wMLE/blob/main/R/wbl3.R',
        'source_sha256': hashlib.sha256((REPO/'python/methods/wmle.py').read_bytes()).hexdigest(),
    }
    (HERE/'wmle_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
