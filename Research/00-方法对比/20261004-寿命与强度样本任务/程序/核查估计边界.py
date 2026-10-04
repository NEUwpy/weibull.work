"""Audit saved endpoint repetitions and numerical boundaries without refitting."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import gaussian_kde

ROOT=Path(__file__).resolve().parents[1]
METHODS=['mdm','lse','lre','wmle','mle']
KEYS=['beta_hat','eta_hat','gamma_hat']


def audit(case):
    source=case/'中间数据/results.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    samples={(r['n'],r['id']):r['values'] for r in data['samples']}
    records=[]
    boundary_groups=[]
    for n in data['n']:
        for method in METHODS:
            rows=[r for r in data['results'] if r['n']==n and r['method_id']==method and r['converged']]
            for at_zero in (True,False):
                selected=[r for r in rows if (r['gamma_hat']==0)==at_zero]
                if selected:
                    boundary_groups.append(dict(n=n,method=method,gamma_at_zero=at_zero,count=len(selected),
                        ids=[r['id'] for r in selected],
                        parameter_min_median_max={k:np.quantile([r[k] for r in selected],[0,.5,1]).tolist() for k in KEYS}))
            for key in KEYS:
                values=np.array([r[key] for r in rows])
                counts=Counter(values.tolist())
                lower,upper=float(values.min()),float(values.max())
                span=upper-lower
                density_values=values[values>0] if key=='gamma_hat' else values
                end_density=None
                if len(density_values)>1 and np.ptp(density_values)>1e-12:
                    grid=np.linspace(density_values.min(),density_values.max(),256)
                    density=gaussian_kde(density_values,bw_method='scott')(grid)
                    end_density=(density[[0,-1]]/density.max()).tolist()
                records.append(dict(n=n,method=method,parameter=key,successful=len(rows),
                    minimum=lower,maximum=upper,minimum_count=counts[lower],maximum_count=counts[upper],
                    repeated_nonzero_values=[dict(value=v,count=c) for v,c in counts.items() if v!=0 and c>1],
                    zeros=int(np.count_nonzero(values==0)),
                    within_lower_5pct_range=int(np.count_nonzero(values<=lower+.05*span)),
                    within_upper_5pct_range=int(np.count_nonzero(values>=upper-.05*span)),
                    density_endpoint_relative_height=end_density))
    mdm_bounds=[dict(n=r['n'],id=r['id'],beta=r['beta_hat']) for r in data['results']
                if r['converged'] and r['method_id']=='mdm' and (r['beta_hat']<.1001 or r['beta_hat']>14.999)]
    support=[dict(n=r['n'],id=r['id'],method=r['method_id'],gamma=r['gamma_hat'],
                  sample_minimum=samples[r['n'],r['id']][0]) for r in data['results'] if r['converged']]
    assert all(0<=r['gamma']<r['sample_minimum'] for r in support)
    result=dict(distribution=data['distribution'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                records=records,gamma_boundary_groups=boundary_groups,mdm_shape_bounds=[.1,15.],mdm_shape_near_bound=mdm_bounds,
                all_successful_gamma_inside_sample_support=True,
                gamma_zero_by_method={m:sum(r['zeros'] for r in records if r['method']==m and r['parameter']=='gamma_hat') for m in METHODS},
                interpretation='Zero location is a saved constrained boundary result. A flat KDE end alone does not establish repeated extrema.',
                frozen_implementation_rules={
                    'lse':'Search includes gamma=0 and retains the best boundary or refined candidate.',
                    'lre':'Correlation search includes gamma=0 and retains the best boundary or refined candidate.',
                    'mle':'Reject negative gamma; returned gamma below 1e-5 is set to zero.',
                    'mdm':'Conditional beta search in [0.1,15]; gamma=0 if gradient at zero reaches offset.',
                    'wmle':'Nonnegative gamma; shape near implementation upper 10 is marked failure.'})
    (case/'中间数据/边界核查.json').write_text(json.dumps(result,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    return result


if __name__=='__main__':
    cases=[audit(case) for case in sorted((ROOT/'程序').glob('W(*)'))]
    totals={m:sum(c['gamma_zero_by_method'][m] for c in cases) for m in METHODS}
    record=dict(combinations=8,distributions=360,gamma_zero_by_method=totals,
                repeated_nonzero_values=sum(len(r['repeated_nonzero_values']) for c in cases for r in c['records']),
                mdm_shape_near_bound=sum(len(c['mdm_shape_near_bound']) for c in cases),
                cases=[dict(distribution=c['distribution'],gamma_zero_by_method=c['gamma_zero_by_method']) for c in cases])
    (ROOT/'程序/边界核查汇总.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record,ensure_ascii=False),flush=True)
