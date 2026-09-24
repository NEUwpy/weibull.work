"""Reuse production LRE/MM/MLE on the frozen E09 samples, with resumable cells."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'python'))
from studies.common.runner import run_method
from studies.common.sample import generate_sample

METHODS = ['LRE', 'MM', 'MLE']
SOURCE_PATHS = ['python/methods/lre.py', 'python/methods/mm.py', 'python/methods/mle.py',
                'python/studies/common/runner.py', 'python/studies/common/sample.py',
                'python/base.py', 'python/methods/registry.py']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def evaluate(records, tag):
    cell = records[0]['cell_id']
    out = HERE / 'extension_cells' / f'cell_{cell:03d}.csv'
    marker = out.with_suffix('.version')
    if out.exists() and marker.exists() and marker.read_text() == tag:
        return cell, 0
    rows = []
    for r in records:
        x = generate_sample(r['beta'], r['eta'], r['gamma'], int(r['n']), int(r['repeat_id']),
                            seed='study01_selector_confirmation_20260922_v1')
        assert hashlib.sha256(x.astype('<f8').tobytes()).hexdigest() == r['sample_sha256']
        for method in METHODS:
            fit = run_method(method.lower(), x / 1000.0)
            values = [fit.get(k + '_hat') for k in ['beta', 'eta', 'gamma']]
            valid = bool(fit['converged']) and all(v is not None and np.isfinite(v) for v in values)
            reason = ''
            if valid:
                bh, eh, gh = values[0], values[1]*1000, values[2]*1000
                valid = bh > 0 and eh > 0 and 0 <= gh < min(x)
                if not valid:
                    reason = 'parameter_admissibility'
            else:
                extra = fit.get('extra') or {}
                reason = extra.get('raw_status') or extra.get('error') or 'not_converged'
            info = (fit.get('extra') or {}).get('solution_info') or {}
            row = {k:r[k] for k in ['cell_id','beta','eta','gamma','gamma_over_eta','n','repeat_id','sample_sha256']}
            row.update(method=method, delta=np.nan, valid=bool(valid), failure_reason=reason,
                       beta_hat=bh if valid else np.nan, eta_hat=eh if valid else np.nan,
                       gamma_hat=gh if valid else np.nan,
                       solver_status=info.get('status',''),
                       location_adjustment=info.get('location_adjustment',''),
                       selected_start=info.get('selected_start',np.nan))
            rows.append(row)
    out.parent.mkdir(exist_ok=True)
    temp = out.with_suffix('.tmp')
    pd.DataFrame(rows).to_csv(temp,index=False)
    os.replace(temp,out)
    marker.write_text(tag)
    return cell, len(rows)


def main():
    old = pd.read_csv(HERE/'per_sample.csv.gz')
    base = old[old.method=='AMDM']
    assert len(base)==4800
    hashes={p:sha(REPO/p) for p in SOURCE_PATHS}
    hashes['extension_driver']=sha(__file__)
    tag=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(evaluate,g.to_dict('records'),tag) for _,g in base.groupby('cell_id')]
        for i,f in enumerate(as_completed(jobs),1):
            print(f'{i}/48 cell {f.result()}',flush=True)
    ext=pd.concat([pd.read_csv(HERE/'extension_cells'/f'cell_{int(c):03d}.csv') for c in base.cell_id.unique()],ignore_index=True)
    assert len(ext)==14400
    ext.to_csv(HERE/'additional_methods.csv.gz',index=False,compression='gzip')
    # Keep existing six-method values; add only the three requested estimators.
    merged=pd.concat([old[~old.method.isin(METHODS)],ext[old.columns.intersection(ext.columns)]],ignore_index=True)
    for p,den in [('beta',merged.beta),('eta',merged.eta),('gamma',merged.eta)]:
        merged['err_'+p]=(merged[p+'_hat']-merged[p])/den
    merged['squared_loss']=merged[['err_beta','err_eta','err_gamma']].pow(2).sum(axis=1,min_count=3)
    merged['score']=np.where(merged.valid,merged.squared_loss,3.)
    assert len(merged)==43200 and not merged.duplicated(['cell_id','repeat_id','method']).any()
    pd.testing.assert_frame_equal(old[~old.method.isin(METHODS)].reset_index(drop=True),
                                  merged[~merged.method.isin(METHODS)].reset_index(drop=True),check_exact=False,rtol=1e-12,atol=1e-14)
    merged.to_csv(HERE/'per_sample.csv.gz',index=False,compression='gzip')
    report={'status':'completed','sample_hashes_checked':4800,'added_rows':14400,'methods':METHODS,
            'source_hashes':hashes,'additional_rows_sha256':sha(HERE/'additional_methods.csv.gz'),
            'existing_six_methods_unchanged':True,'unit_conversion':1000,
            'protocol':'production defaults, gamma>=0; MLE selects a converged beta>=1 finite candidate; no true parameters passed to estimators'}
    (HERE/'extension_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(merged.groupby('method').valid.agg(['size','sum']),flush=True)


if __name__=='__main__':
    main()
