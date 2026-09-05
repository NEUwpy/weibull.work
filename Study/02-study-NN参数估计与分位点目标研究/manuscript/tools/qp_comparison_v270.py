"""Recover the archived, paired QP comparator without new training."""
from pathlib import Path
import sys,os,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
os.environ['PQ_PROTOCOL']='iid-v1'
sys.path.insert(0,str(ROOT/'code'))
from study02pq.constrained_confirm import crossed_bootstrap_contrast

OUT=ROOT/'artifacts/qp_comparison_v270'
OLD=ROOT/'归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity'
NS=[7,10,15,20];SEEDS=[42,2026,3407,17,73,314,2718,4099,8128,12011]
ROUTES=['P','Q','QP','QCP'];RS=[.90,.95,.99]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={}; rows=[];arrays={(r,m):np.empty((4,5,10)) for r in RS for m in ROUTES}
    for ni,n in enumerate(NS):
      for f in range(1,6):
       for si,s in enumerate(SEEDS):
        base=None
        for m in ROUTES:
         source=ROOT/'artifacts/qcp_constrained_confirm' if m=='QCP' else OLD
         p=source/'evidence'/f'n{n}_f{f}_s{s}_r{m}.npz'
         hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
         with np.load(p) as z:
          keys=np.column_stack([z[k] for k in ('keys_beta','keys_gamma_over_eta','keys_n','keys_repeat_id')])
          if base is None:base=keys
          else:np.testing.assert_array_equal(base,keys)
          b,g=z['keys_beta'].astype(float),1000*z['keys_gamma_over_eta'].astype(float)
          bh,eh,gh=[z[k].astype(float) for k in ('beta_hat','eta_hat','gamma_hat')]
         for r in RS:
          a=-np.log(r);truth=g+1000*a**(1/b);err=(gh+eh*a**(1/bh)-truth)/truth
          assert np.isfinite(err).all()
          arrays[r,m][ni,f-1,si]=np.mean(err**2)
          rows.append(dict(n=n,fold=f,seed=s,route=m,reliability=r,mse=float(np.mean(err**2))))
    old=json.loads((OLD/'analysis/summary.json').read_text(encoding='utf-8'))
    summary={'evidence_level':'post-test fixed-weight comparator and derived cross-life-point analysis','new_training_fits':0,'rows_per_route':480000,'pooled':{},'contrasts':{}}
    for r in RS:
      summary['pooled'][str(r)]={m:float(np.sqrt(arrays[r,m].mean())) for m in ROUTES}
      for target,comp in [('QP','Q'),('QP','P'),('QCP','QP')]:
       key=f'{r}:{target}_vs_{comp}'
       boot=crossed_bootstrap_contrast(arrays[r,target],arrays[r,comp],replicates=200000,seed=2700905+RS.index(r))
       summary['contrasts'][key]={'improvement':1-summary['pooled'][str(r)][target]/summary['pooled'][str(r)][comp],**boot}
    for m in ROUTES:np.testing.assert_allclose(summary['pooled']['0.95'][m],old['pooled_rrmse'][m],rtol=1e-8)
    # Keep the published target comparison CI from its original frozen resampling.
    summary['original_target_qcp_vs_qp']=old['contrasts']['QCP_minus_QP']
    summary['resources']=old['resource_diagnostics']
    pd.DataFrame(rows).to_csv(OUT/'model_mse.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps({'source_sha256':hashes,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
