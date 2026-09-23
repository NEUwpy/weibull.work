"""Re-evaluate only failed WMLE rows; retain all other E09 estimates exactly."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import numpy as np
import pandas as pd
from run_e09 import HERE, REPO, NAMESPACE, implementation_tag, collect
from wmle_solver import profile_recover
from studies.common.sample import generate_sample


def repair(row):
    x=generate_sample(row['beta'],row['eta'],row['gamma'],int(row['n']),int(row['repeat_id']),seed=NAMESPACE)
    assert hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()==row['sample_sha256']
    result=profile_recover(x/1000)
    record={k:row[k] for k in ['cell_id','repeat_id','sample_sha256']}
    record['recovered']=result is not None
    if result:
        record.update({k:result[k] for k in ['beta_hat','eta_hat','gamma_hat']})
        record['eta_hat']*=1000;record['gamma_hat']*=1000
        record.update(result['extra']['solution_info'])
    return record


def main():
    before=pd.read_csv(HERE/'per_sample.csv.gz')
    fail=before[(before.method=='WMLE')&~before.valid]
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows=[]
        for i,row in enumerate(pool.map(repair,fail.to_dict('records')),1):
            rows.append(row)
            if i%50==0:print(f'{i}/{len(fail)}',flush=True)
    changes=pd.DataFrame(rows)
    changes.to_csv(HERE/'wmle_recovery.csv',index=False)
    for path in sorted((HERE/'cells').glob('cell_*.csv')):
        data=pd.read_csv(path)
        for row in changes[changes.recovered & changes.cell_id.eq(int(data.cell_id.iloc[0]))].itertuples():
            idx=data.method.eq('WMLE') & data.repeat_id.eq(row.repeat_id)
            assert idx.sum()==1
            data.loc[idx,['beta_hat','eta_hat','gamma_hat']]=[row.beta_hat,row.eta_hat,row.gamma_hat]
            data.loc[idx,'valid']=True;data.loc[idx,'failure_reason']=''
        data.to_csv(path,index=False)
        path.with_suffix('.version').write_text(implementation_tag(),encoding='utf8')
    collect()
    after=pd.read_csv(HERE/'per_sample.csv.gz')
    cols=['cell_id','repeat_id','method','beta_hat','eta_hat','gamma_hat','valid']
    unchanged=before.method.ne('WMLE')|before.valid
    pd.testing.assert_frame_equal(before.loc[unchanged,cols].reset_index(drop=True),
        after.loc[unchanged,cols].reset_index(drop=True),check_exact=False,rtol=1e-14,atol=1e-12)
    print({'prior_failures':len(fail),'recovered':int(changes.recovered.sum()),
           'remaining':int((after.method.eq('WMLE')&~after.valid).sum())})


if __name__=='__main__':main()
