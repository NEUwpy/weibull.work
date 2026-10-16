"""Independent checks of the saved Study04 table, without rerunning estimators.

Direct formulas here are validation checks, not a second production metric API.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from scipy.special import logsumexp

ROOT=Path(__file__).resolve().parents[3]
STUDY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from methods.lse import log_weibull_order_stat_means


from 存储路径 import batch_path, current_batch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',help='计算存档中的批次名；默认读取当前批次')
    args=parser.parse_args()
    out=batch_path(args.batch) if args.batch else current_batch()
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    config=manifest['config']
    assert manifest['status']=='complete'
    for name,sha in manifest['file_sha256'].items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==sha,name
    columns=['beta','eta','gamma','n','repeat_id','method_id','method_variant',
             'beta_hat','eta_hat','gamma_hat','status']
    raw=pd.read_csv(out/'results.csv.gz',usecols=columns,float_precision='round_trip')
    table=pd.read_csv(out/'条件汇总.csv',float_precision='round_trip').set_index(['beta','n','method'])
    assert len(raw)==config['expected_rows'] and len(table)==config['expected_cells']*len(config['methods'])
    assert raw.eta.eq(1000).all() and raw.gamma.eq(500).all()
    assert not raw.duplicated(['beta','n','repeat_id','method_id']).any()
    assert raw.groupby(['beta','n','repeat_id']).method_id.nunique().eq(7).all()
    checked_values=0;closed_scale=0;regression=0;valid_support=0
    for (beta,n),cell in raw.groupby(['beta','n']):
        key=f'b{beta:g}_n{n:02d}'
        with np.load(out/'inputs'/key/'samples.npz') as pack:samples=pack['samples']
        for (method,variant),group in cell.groupby(['method_id','method_variant']):
            saved=table.loc[(beta,n,variant)];good=group[group.status=='success']
            assert int(saved.total)==len(group) and int(saved.success)==len(good)
            assert int(saved.failure)==len(group)-len(good)
            for p,truth in [('beta',beta),('eta',1000.),('gamma',500.)]:
                errors=good[p+'_hat'].to_numpy()-truth
                expected=dict(bias=float(errors.mean()) if len(errors) else np.nan,
                    sd=float(errors.std(ddof=1)) if len(errors)>1 else (0. if len(errors) else np.nan),
                    rmse=float(np.sqrt(np.mean(errors**2))) if len(errors) else np.nan,
                    mae=float(np.mean(np.abs(errors))) if len(errors) else np.nan)
                for metric,value in expected.items():
                    assert np.isclose(saved[p+'_'+metric],value,rtol=1e-10,atol=1e-10,equal_nan=True),(key,method,p,metric)
                    checked_values+=1
            shape=good.beta_hat.to_numpy()
            anomaly=np.mean((shape>=3*beta)|(shape<=beta/3)) if len(shape) else np.nan
            assert np.isclose(saved.shape_anomaly_rate,anomaly,rtol=0,atol=1e-12,equal_nan=True)
            for row in good.itertuples():
                x=samples[int(row.repeat_id)];b,e,g=row.beta_hat,row.eta_hat,row.gamma_hat
                minimum=x[1] if method=='mmle' else x[0]
                assert b>0 and e>0 and 0<=g<minimum
                valid_support+=1
                if method=='mmle':
                    assert g==x[0]
                    expected=np.exp((logsumexp(b*np.log(x[1:]-g))-np.log(len(x)-1))/b)
                    assert np.isclose(e,expected,rtol=1e-8,atol=1e-8)
                    closed_scale+=1
                elif method=='lse':
                    z=log_weibull_order_stat_means(int(n));y=np.log(x-g)
                    slope=np.sum((z-z.mean())*(y-y.mean()))/np.sum((z-z.mean())**2)
                    expected=[1/slope,np.exp(y.mean()-slope*z.mean())]
                    assert np.allclose([b,e],expected,rtol=1e-8,atol=1e-8)
                    regression+=1
    report=dict(rows=len(raw),groups=len(table),metric_values_checked=checked_values,
        valid_support_checked=valid_support,mmle_scale_checked=closed_scale,lse_regression_checked=regression,
        result='passed',checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'独立汇总核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
