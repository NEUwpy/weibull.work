"""Repeat the requested +2000 paired check without changing source files."""
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path('D:/weibull')
sys.path.insert(0, str(ROOT / 'python'))
from methods.mdm import MDM
from methods.wmle import WMLE, get_weight_j1, get_weight_j2, get_weight_j3

src = ROOT / 'docs/临时任务/工作输出/20260906-W5-parameters/W5-1000-500'
paths = [src / name for name in ['samples.csv', 'mdm_estimates.csv', 'other_method_estimates.csv']]
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
samples, mdm, other = [list(csv.DictReader(p.open(encoding='utf-8-sig'))) for p in paths]
observations = {}
for r in samples:
    observations.setdefault((int(r['sample_size']), int(r['sample_id'])), []).append(float(r['value']))

def residuals(x, beta, gamma):
    y = x - gamma
    logy = np.log(y)
    z = y / y.max()
    weights = z ** beta
    r1 = get_weight_j2(len(x))/beta + logy.mean() - weights @ logy / weights.sum()
    r2 = np.mean(1/z)*sum(z**beta)/sum(z**(beta-1))-get_weight_j3(len(x), beta)
    return r1*r1+r2*r2

def recover(x, original):
    # Supplementary diagnostic only: bracket around the translated old root.
    n = len(x)
    def shape(g):
        z = np.log(x-g)
        z -= z.max()
        def equation(b):
            w = np.exp(b*z)
            return b*(w@z/w.sum()-z.mean())-get_weight_j2(n)
        return brentq(equation, .01, 10., xtol=1e-13)
    def equation(g):
        b = shape(g)
        z = (x-g)/(x-g).max()
        return np.mean(1/z)*sum(z**b)/sum(z**(b-1))-get_weight_j3(n,b)
    expected = original[2]+2000
    g = brentq(equation, max(0,expected-10), min(x.min()-1e-6,expected+10), xtol=1e-10)
    b = shape(g)
    eta = (np.mean((x-g)**b)/get_weight_j1(n))**(1/b)
    assert residuals(x,b,g) < 1e-8
    return [b,eta,g]

result = []
for n in [7,15]:
    for delta in [.1,.15,.2,None]:
        for sid in range(1,51):
            x = np.sort(np.array(observations[(n,sid)]))
            candidates = mdm if delta is not None else other
            old = next(r for r in candidates if int(r['sample_size'])==n and int(r['sample_id'])==sid and
                       (float(r['offset'])==delta if delta is not None else r['method_id']=='wmle'))
            try:
                before = [float(old[k]) for k in ['beta_hat','eta_hat','gamma_hat']]
            except ValueError:
                before = None
            if delta is not None:
                after = list(MDM(x+2000).run(offset=delta,gamma_steps=240)[:3])
                note = ''
            else:
                model = WMLE(x+2000)
                run = model.run()
                if model.last_solution_info['status']=='ok':
                    after = list(map(float,run[:3]))
                    note = ''
                elif before is not None:
                    after = recover(x+2000,before)
                    note = '平移后常规求解漏解；独立廓线求根补充验证'
                else:
                    after = None
                    note = '原样本和平移后样本均未通过方程残差检查'
            result.append(dict(n=n,id=sid,method='MDM' if delta is not None else 'WMLE',delta=delta,
                               before=before,after=after,note=note))
        print('COMPLETED',n,delta,flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
payload = {'shift':2000,'rows':result,'samples':samples,'source_hashes':hashes}
out = Path(__file__).with_name('translation_data.json')
out.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
print('SAVED',out,flush=True)
