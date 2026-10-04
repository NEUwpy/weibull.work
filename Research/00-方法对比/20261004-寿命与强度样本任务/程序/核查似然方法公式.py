"""Independent scale identities and likelihood scores for all saved successful fits."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'结果/复核与LRE对比'
J1={7:.953,15:.978,30:.989}
records=[]
for case in sorted((ROOT/'结果').glob('W(*)')):
    data=json.loads((case/'中间数据/results.json').read_text(encoding='utf-8'))
    samples={(s['n'],s['id']):np.asarray(s['values']) for s in data['samples']}
    for r in data['results']:
        method=r['method_id']
        if method not in ('mle','wmle') or not r['converged']:continue
        x=samples[r['n'],r['id']]-r['gamma_hat']
        b,e=r['beta_hat'],r['eta_hat']
        expected=float(np.exp(np.log(np.mean(x**b)/(J1[r['n']] if method=='wmle' else 1))/b))
        record=dict(distribution=case.name,n=r['n'],id=r['id'],method=method,
                    eta_relative_identity_error=abs(expected/e-1))
        if method=='wmle':
            record['squared_equation_residual']=r['extra']['solution_info']['objective']
        else:
            v=x/e;u=np.log(v);powers=v**b
            record.update(shape_score=float(1/b+np.mean(u)-np.mean(powers*u)),
                          normalized_scale_score=float(powers.mean()-1),
                          normalized_location_score=float(e*(-(b-1)*np.mean(1/x)+b/e*np.mean(v**(b-1)))),
                          zero_location=r['gamma_hat']==0)
        records.append(record)
(OUT/'似然方法公式核查.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for method in ('mle','wmle'):
    selected=[r for r in records if r['method']==method]
    print(method,len(selected),'max scale identity relative error',max(r['eta_relative_identity_error'] for r in selected))
print('MLE largest score',sorted([r for r in records if r['method']=='mle'],key=lambda r:max(abs(r['shape_score']),abs(r['normalized_scale_score']),abs(r['normalized_location_score']) if not r['zero_location'] else max(r['normalized_location_score'],0)),reverse=True)[:2])
