"""Read-only exact replay of the historical W(5,1000,500) delivery."""
from pathlib import Path
import csv
import json
import hashlib
import math
import sys
import numpy as np
from openpyxl import load_workbook

ROOT=Path('D:/weibull')
sys.path.insert(0,str(ROOT/'python'))
from studies.common.sample import generate_sample

source=ROOT/'docs/临时任务/工作输出/20260906-W5-parameters/W5-1000-500'
book=ROOT/'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260906-W5参数估计案例/W(5,1000,500)/5,1000,500.xlsx'
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
p=manifest['parameters']
assert (p['beta'],p['eta'],p['gamma'],p['seed_namespace'])==(5.,1000.,500.,20260906)
before=hashlib.sha256(book.read_bytes()).hexdigest()
with (source/'samples.csv').open(encoding='utf-8-sig',newline='') as f:
    records=list(csv.DictReader(f))
lookup={}
for r in records:
    key=int(r['sample_size']),int(r['sample_id'])
    lookup.setdefault(key,[]).append((int(r['observation_index']),float(r['value'])))
assert len(lookup)==100 and len(records)==1100
wb=load_workbook(book,read_only=True,data_only=True)
result={'parameters':p,'source_workbook':str(book),'checks':[]}
replayed={}
for n in [7,15]:
    rows=list(wb[f'生成样本_n{n}'].values)
    assert len(rows)==51
    assert rows[0][0]=='样本'
    errors_csv=[]; errors_xlsx=[]; formula_errors=[]; recovered_gamma=[]; all_x=[]
    for rep in range(50):
        sid=rep+1
        x=generate_sample(5.0,1000.0,500.0,n,rep,seed=20260906)
        replayed[(n,sid)]=x
        saved=np.array([v for idx,v in sorted(lookup[(n,sid)])])
        assert rows[sid][0]==sid
        sheet=np.array(rows[sid][1:n+1],dtype=float)
        assert len(sheet)==n and len(saved)==n
        errors_csv.extend(abs(x-saved)); errors_xlsx.extend(abs(x-sheet)); all_x.extend(sheet)
        # Independent scalar implementation of the inverse CDF using the recorded seed recipe.
        seed_text=f'20260906|5.0|1000.0|500.0|{n}|{rep}'
        seed_int=int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:4],'big')
        u=np.sort(np.random.default_rng(seed_int).uniform(0,1,size=n))
        baseline=np.array([1000.0*(-math.log(1-float(v)))**.2 for v in u])
        formula_errors.extend(abs(sheet-(500+baseline)))
        recovered_gamma.extend(sheet-baseline)
    assert max(errors_csv)<1e-10 and max(errors_xlsx)<1e-10 and max(formula_errors)<1e-10
    result['checks'].append({'n':n,'groups':50,'value_count':len(all_x),
        'max_abs_difference_replay_vs_csv':float(max(errors_csv)),
        'max_abs_difference_replay_vs_xlsx':float(max(errors_xlsx)),
        'max_abs_difference_independent_formula_vs_xlsx':float(max(formula_errors)),
        'recovered_additive_location_range':[float(min(recovered_gamma)),float(max(recovered_gamma))],
        'sample_range':[float(min(all_x)),float(max(all_x))],
        'sample_1':replayed[(n,1)].tolist()})
for filename in ['mdm_estimates.csv','other_method_estimates.csv']:
    with (source/filename).open(encoding='utf-8-sig',newline='') as f:
        rs=list(csv.DictReader(f))
    assert all(float(r['beta'])==5 and float(r['eta'])==1000 and float(r['gamma'])==500 for r in rs)
    error=max(abs(float(r['sample_min'])-replayed[(int(r['sample_size']),int(r['sample_id']))][0]) for r in rs)
    assert error<1e-10
    result[filename]={'rows':len(rs),'metadata_correct':True,'max_sample_min_difference':float(error)}
wb.close()
result['workbook_unchanged']=before==hashlib.sha256(book.read_bytes()).hexdigest()
assert result['workbook_unchanged']
print(json.dumps(result,ensure_ascii=True,indent=2))
