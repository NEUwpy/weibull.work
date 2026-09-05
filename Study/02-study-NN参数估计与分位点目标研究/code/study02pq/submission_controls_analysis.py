"""Analyze the complete, prospectively specified submission-control matrix."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from .submission_controls import ROOT,OUT,SEEDS,dump
from .constrained_confirm import crossed_bootstrap_contrast

NS=[7,10,15,20];RS=[.90,.95,.99]
OLD=ROOT/'归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity'
ROUTES=['P','Q','P_QSELECT','QP','QCP','QMULTI']

def main():
    meta={};unavailable=[];hashes={};rows=[];param=[];feasible_minima=[];resources=[]
    risks={(r,m):np.empty((4,5,10)) for r in RS for m in ROUTES}
    for ni,n in enumerate(NS):
      for fi in range(5):
       for si,s in enumerate(SEEDS):
        key=f'n{n}_f{fi+1}_s{s}'
        new={m:json.loads((OUT/'fits'/f'{key}_r{m}.json').read_text())['meta'] for m in ('P_QSELECT','Q','QMULTI')}
        original_q=json.loads((OLD/'fit_metadata'/f'{key}_rQ.json').read_text())
        for m,v in new.items():
            resources.append(dict(n=n,fold=fi+1,seed=s,route=m,best_epoch=v['best_epoch'],stopped_epoch=v['stopped_epoch'],runtime_s=v['runtime_s']))
            for k in ('init_param_sha','batch_order_sha','scaler_sha','train_rows_sha','val_rows_sha','test_rows_sha','network_sha'):
                assert v[k]==original_q[k],(key,m,k)
        np.testing.assert_allclose(new['Q']['rrmse_x95'],original_q['rrmse_x95'],rtol=1e-10,atol=1e-12)
        assert new['Q']['best_epoch']==original_q['best_epoch']
        feasible=json.loads((OUT/'fits'/f'{key}_rQ_FEAS.json').read_text())
        feasible_minima.append(min(h['val_p']/feasible['limit'] for h in feasible['history']))
        if not feasible['available']:unavailable.append(key)
        baseline=None
        for m in ROUTES:
            if m in ('P_QSELECT','Q','QMULTI'):p=OUT/'predictions'/f'{key}_r{m}.npz'
            elif m=='QCP':p=ROOT/'artifacts/qcp_constrained_confirm/evidence'/f'{key}_r{m}.npz'
            else:p=OLD/'evidence'/f'{key}_r{m}.npz'
            hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
            with np.load(p) as z:
                keys=np.column_stack([z[k] for k in ('keys_beta','keys_gamma_over_eta','keys_n','keys_repeat_id')])
                if baseline is None:baseline=keys
                else:np.testing.assert_array_equal(baseline,keys)
                b=keys[:,0];g=1000*keys[:,1];bh,eh,gh=[z[k].astype(float) for k in ('beta_hat','eta_hat','gamma_hat')]
            lp=np.mean(((bh-b)/b)**2+((eh-1000)/1000)**2+((gh-g)/1000)**2)
            param.append(dict(n=n,fold=fi+1,seed=s,route=m,parameter_loss=float(lp)))
            for r in RS:
                a=-np.log(r);truth=g+1000*a**(1/b);err=(gh+eh*a**(1/bh)-truth)/truth
                assert np.isfinite(err).all()
                mse=float(np.mean(err**2));risks[r,m][ni,fi,si]=mse
                rows.append(dict(n=n,fold=fi+1,seed=s,route=m,reliability=r,mse=mse))
    summary={'evidence_level':'post-test supplemental controls on existing simulation samples; no independent fresh-data confirmation',
        'training_trajectories':600,'model_cells':200,'prediction_rows_per_route':480000,'q_reproduction_all_200':True,
        'q_feas':{'available':200-len(unavailable),'total':200,'unavailable_cells':unavailable,'minimum_observed_val_p_over_limit':min(feasible_minima),'scope':'within native Q early-stopping trajectory; no fallback'},
        'pooled':{str(r):{m:float(np.sqrt(risks[r,m].mean())) for m in ROUTES} for r in RS},
        'parameter_loss':pd.DataFrame(param).groupby('route').parameter_loss.mean().to_dict(),'contrasts':{}}
    for r in RS:
      for target,comp in [('Q','P_QSELECT'),('P_QSELECT','P'),('QMULTI','Q'),('QMULTI','QCP'),('QMULTI','QP')]:
        c=crossed_bootstrap_contrast(risks[r,target],risks[r,comp],replicates=200000,seed=2700906+RS.index(r))
        summary['contrasts'][f'{r}:{target}_vs_{comp}']={**c,'relative_improvement':1-np.sqrt(risks[r,target].mean()/risks[r,comp].mean()),
          'favorable_model_units':int(np.sum(risks[r,target]<risks[r,comp])),
          'favorable_seeds':int(np.sum(risks[r,target].mean(axis=(0,1))<risks[r,comp].mean(axis=(0,1))))}
    analysis=OUT/'analysis';analysis.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(analysis/'model_mse.csv',index=False);pd.DataFrame(param).to_csv(analysis/'parameter_loss.csv',index=False)
    pd.DataFrame(resources).to_csv(analysis/'resources.csv',index=False)
    dump(analysis/'summary.json',summary);dump(analysis/'manifest.json',{'source_sha256':hashes,'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('q_feas','contrasts')},ensure_ascii=False))
    print('Q_FEAS available',summary['q_feas']['available'])

if __name__=='__main__':main()
