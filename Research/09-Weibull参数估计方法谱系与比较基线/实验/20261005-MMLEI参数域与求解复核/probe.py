import sys,json,time,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/'python'))
from studies.common.sample import generate_sample
from domain_solver import analyze,CFG
old=pd.read_csv(HERE.parent/'20261005-MLE-MMLE-WMLE三方法/per_sample.csv.gz')
rows=old[(old.method_variant=='MMLE')&(old.status!='success')].groupby('n').head(8)
out=[];start=time.perf_counter()
for row in rows.itertuples():
    b=int(row.block);seed=CFG['base_seed_namespace'] if b==0 else f"{CFG['base_seed_namespace']}:research09-versions:block{b:02d}"
    sample=generate_sample(*CFG['truth'],int(row.n),int(row.repeat_id),seed=seed)
    assert hashlib.sha256(sample.tobytes()).hexdigest()==row.sample_sha256
    record,curve=analyze(sample,True)
    out.append(dict(n=row.n,block=b,rid=row.repeat_id,**{k:v for k,v in record.items() if k not in ['candidates','fits']},
                    fits=record['fits'],roots=record['candidates']))
print(json.dumps(dict(seconds=time.perf_counter()-start,cases=out),ensure_ascii=False,indent=2))
