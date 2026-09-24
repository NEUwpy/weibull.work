"""Check paired samples, frozen-model decisions and WMLE equation residuals."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
sys.path.insert(0,str(REPO/'python'))
from studies.common.sample import generate_sample
from studies.common.runner import run_method
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3


def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz')
    expected_methods=set(json.loads((HERE/'实验配置.json').read_text(encoding='utf8'))['methods'])
    assert set(data.method)==expected_methods
    assert len(data)==4800*len(expected_methods) and data.cell_id.nunique()==48
    assert not data.duplicated(['cell_id','repeat_id','method']).any()
    assert data.groupby('sample_sha256').method.nunique().eq(len(expected_methods)).all()
    samples={}
    for row in data.drop_duplicates('sample_sha256').itertuples():
        x=generate_sample(row.beta,row.eta,row.gamma,row.n,row.repeat_id,
                          seed='study01_selector_confirmation_20260922_v1')
        assert hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()==row.sample_sha256
        samples[row.sample_sha256]=x
    maxres=0
    for row in data[data.method.eq('WMLE') & data.valid].itertuples():
        x=samples[row.sample_sha256]/1000
        b,e,g=row.beta_hat,row.eta_hat/1000,row.gamma_hat/1000
        assert 0<b<9.99 and e>0 and 0<=g<x.min()
        z=x-g;logs=np.log(z);p=np.exp(b*(logs-logs.max()))
        r1=get_weight_j2(row.n)/b+logs.mean()-np.dot(p,logs)/p.sum()
        r2=np.mean(1/z)*p.sum()/np.sum(p/z)-get_weight_j3(row.n,b)
        objective=r1*r1+r2*r2
        assert objective<=1.001e-8,objective
        expected=np.exp(logs.max()+np.log(p.mean()/get_weight_j1(row.n))/b)
        assert np.isclose(expected,e,rtol=1e-10)
        maxres=max(maxres,objective)
    for n in [7,10,15,20]:
        model=json.loads((HERE/f'models/n{n}_final.json').read_text(encoding='utf8'))
        group=data[data.method.eq('AMDM') & data.n.eq(n)]
        x=np.array([np.sort(samples[h]) for h in group.sample_sha256])
        z=x/x.mean(axis=1,keepdims=True)
        y=(z-model['input_scaler_mean'])/model['input_scaler_std']
        for i,(w,bias) in enumerate(zip(model['mlp_weights']['coefs_'],model['mlp_weights']['intercepts_'])):
            y=y@np.asarray(w)+bias
            if i<len(model['mlp_weights']['coefs_'])-1:y=np.maximum(y,0)
        losses=np.maximum(y*model['target_scaler_std']+model['target_scaler_mean'],0)
        delta=np.array(model['delta_grid'])[losses.argmin(axis=1)]
        assert np.allclose(delta,group.delta,rtol=0,atol=1e-14)
        for row in group.iloc[[0,-1]].itertuples():
            fit=run_method('mdm',samples[row.sample_sha256],offset=row.delta,gamma_steps=60)
            assert fit['converged']
            assert np.allclose([fit[k+'_hat'] for k in ['beta','eta','gamma']],
                               [row.beta_hat,row.eta_hat,row.gamma_hat],rtol=1e-9,atol=1e-8)
    extension_checks=0
    for method in ['LRE','MM','MLE']:
        group=data[data.method.eq(method)]
        if group.empty: continue
        for row in group.groupby('n').head(2).itertuples():
            fit=run_method(method.lower(),samples[row.sample_sha256]/1000.)
            if row.valid:
                assert fit['converged']
                assert np.allclose([fit['beta_hat'],fit['eta_hat']*1000,fit['gamma_hat']*1000],
                                   [row.beta_hat,row.eta_hat,row.gamma_hat],rtol=1e-8,atol=1e-8)
            else:
                assert not fit['converged']
            extension_checks+=1
    report={'rows':len(data),'paired_samples':len(samples),'cells':48,
            'production_extension_spot_checks':extension_checks,
            'sample_hashes_checked':len(samples),'model_decisions_checked':4800,
            'AMDM_solver_spot_checks':8,'WMLE_valid_equations_checked':int((data.method.eq('WMLE')&data.valid).sum()),
            'WMLE_max_squared_residual':float(maxres),'status':'passed'}
    (HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(report)


if __name__=='__main__':main()
