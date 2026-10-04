"""Compare old/new LRE accuracy against known truth, separately from version differences."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'结果/复核与LRE对比'
files=sorted(OUT.glob('W(*).json'))
pairs=[r for file in files for r in json.loads(file.read_text(encoding='utf-8'))['lre_pairs']]
assert len(pairs)==1200


def describe(rows):
    result=dict(sample_groups=len(rows),parameters={},quantiles={})
    for name,key in [('beta','beta_hat'),('eta','eta_hat'),('gamma','gamma_hat')]:
        result['parameters'][name]={}
        for version in ('old','new'):
            errors=np.array([(r[version][key]-r[name])/r[name] for r in rows])
            result['parameters'][name][version]=dict(
                median_absolute_relative_error_percent=float(100*np.median(np.abs(errors))),
                relative_rmse_percent=float(100*np.sqrt(np.mean(errors**2))))
    for i,p in enumerate((.01,.1,.5,.9)):
        result['quantiles'][str(p)]={}
        for version in ('old','new'):
            errors=np.array([(r['quantiles'][i][version]-r['quantiles'][i]['truth'])/r['quantiles'][i]['truth'] for r in rows])
            result['quantiles'][str(p)][version]=dict(
                median_absolute_relative_error_percent=float(100*np.median(np.abs(errors))),
                relative_rmse_percent=float(100*np.sqrt(np.mean(errors**2))))
    return result


result=dict(metric_definition='For each estimate divide absolute error by its true parameter or quantile, then take the median; RMSE is computed on signed relative errors.',
            source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            all_conditions=describe(pairs),beta5=describe([r for r in pairs if r['beta']==5]),conditions=[])
for name in sorted({r['distribution'] for r in pairs}):
    for n in (7,15,30):
        result['conditions'].append(dict(distribution=name,n=n,**describe([r for r in pairs if r['distribution']==name and r['n']==n])))
(OUT/'LRE真值误差对比.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result['beta5'],ensure_ascii=False,indent=2))
