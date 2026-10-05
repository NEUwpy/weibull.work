"""Read-only diagnosis of saved estimates; no sampling or solver calls."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
BATCH=HERE.parents[1]
PREVIOUS=BATCH.parent/'20261005-MLE-MMLE全版本固定真值比较'
KEY=['n','block','repeat_id']

def main():
    sources=[BATCH/'per_sample.csv.gz',BATCH/'failure_reasons.csv',BATCH/'manifest.json',
             PREVIOUS/'per_sample.csv.gz',PREVIOUS/'manifest.json']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    source=pd.read_csv(BATCH/'per_sample.csv.gz');old=pd.read_csv(PREVIOUS/'per_sample.csv.gz')
    cw=source[source.method_variant.eq('MMLE')].copy();mle=source[source.method_variant.eq('MLE')].copy()
    paper=old[old.method_variant.eq('mmle_i_paper')][KEY+['status','beta_hat','eta_hat','gamma_hat','extra']]
    paper=paper.rename(columns={c:'paper_'+c for c in paper if c not in KEY})
    cw=cw.merge(paper,on=KEY,validate='one_to_one')
    cw['reason']=cw.extra.map(json.loads).map(lambda x:x.get('solution_info',{}).get('status','unknown'))
    cw['root_diagnosis']='main_success'
    failed=cw.status.ne('success');paper_good=cw.paper_status.eq('success')
    cw.loc[failed,'root_diagnosis']='unresolved_beyond_saved_domains'
    cw.loc[failed&paper_good&cw.paper_gamma_hat.lt(0),'root_diagnosis']='saved_root_at_negative_location'
    cw.loc[failed&paper_good&cw.paper_gamma_hat.ge(0)&cw.paper_beta_hat.ge(9.99),'root_diagnosis']='saved_root_shape_above_main_limit'
    cw.loc[failed&paper_good&cw.paper_gamma_hat.ge(0)&cw.paper_beta_hat.lt(9.99),'root_diagnosis']='saved_root_inside_main_domain'
    counts=[]
    for n,part in cw.groupby('n'):
        f=part[part.status.ne('success')]
        endpoints=f[f.reason.eq('no_root_in_declared_location_domain')].extra.map(json.loads).map(
            lambda x:x['solution_info']['endpoint_constraint_residuals'])
        counts.append(dict(n=n,main_success=int(part.status.eq('success').sum()),main_failure=len(f),
            no_root=int(f.reason.eq('no_root_in_declared_location_domain').sum()),
            shape_outside=int(f.reason.eq('shape_outside_declared_domain').sum()),
            residual_failure=int(f.reason.eq('equation_residual').sum()),
            endpoint_both_positive=sum(a>0 and b>0 for a,b in endpoints),
            endpoint_both_negative=sum(a<0 and b<0 for a,b in endpoints),
            endpoint_opposite=sum(a*b<0 for a,b in endpoints),
            paper_success=int(part.paper_status.eq('success').sum()),
            extra_negative_root=int(f.root_diagnosis.eq('saved_root_at_negative_location').sum()),
            negative_also_shape_high=int((f.root_diagnosis.eq('saved_root_at_negative_location')&f.paper_beta_hat.ge(9.99)).sum()),
            extra_high_shape_root=int(f.root_diagnosis.eq('saved_root_shape_above_main_limit').sum()),
            inside_root=int(f.root_diagnosis.eq('saved_root_inside_main_domain').sum()),
            unresolved=int(f.root_diagnosis.eq('unresolved_beyond_saved_domains').sum())))
    pd.DataFrame(counts).to_csv(HERE/'失败分类与已存原文域根.csv',index=False,encoding='utf-8-sig')
    cw[KEY+['status','reason','root_diagnosis','paper_status','paper_beta_hat','paper_eta_hat','paper_gamma_hat']].to_csv(
        HERE/'逐样本MMLE诊断.csv',index=False,encoding='utf-8-sig')
    data=mle.merge(cw[KEY+['status','root_diagnosis']],on=KEY,suffixes=('','_cw'),validate='one_to_one')
    data['gap']=data.sample_min-data.gamma_hat
    data['severe_shape']=data.beta_hat.ge(5)
    data['severe_eta']=data.eta_error.abs().ge(500)
    data['severe_gamma']=data.gamma_error.abs().ge(500)
    data['severe_any']=data[['severe_shape','severe_eta','severe_gamma']].any(axis=1)
    boundary=[];cross=[]
    for n,part in data.groupby('n'):
        good=part[part.status.eq('success')];zero=good[good.gamma_hat.eq(0)];other=good[good.gamma_hat.ne(0)]
        boundary.append(dict(n=n,success=len(good),zero_location=len(zero),zero_fraction=len(zero)/len(good),
            interior_success_without_zero=len(other),
            shape_ge5=int(good.beta_hat.ge(5).sum()),shape_ge10=int(good.beta_hat.ge(10).sum()),
            shape_ge999=int(good.beta_hat.ge(9.99).sum()),gap_lt1e4=int(good.gap.lt(.0001).sum()),
            gap_le1=int(good.gap.le(1).sum()),gap_le10=int(good.gap.le(10).sum()),min_gap=good.gap.min(),
            beta_bias=good.beta_error.mean(),zero_mean_beta=zero.beta_hat.mean(),nonzero_mean_beta=other.beta_hat.mean(),
            zero_beta_bias_contribution=zero.beta_error.sum()/len(good),
            zero_eta_bias=zero.eta_error.mean(),zero_gamma_bias=zero.gamma_error.mean()))
        for cohort,mask in [('MMLE_failure',part.status_cw.ne('success')),('MMLE_success',part.status_cw.eq('success'))]:
            cohort_rows=part[mask];v=cohort_rows[cohort_rows.status.eq('success')]
            item=dict(n=n,cohort=cohort,total=len(cohort_rows),mle_success=len(v),mle_failure=len(cohort_rows)-len(v),
                mle_zero_location=int(v.gamma_hat.eq(0).sum()),severe_shape=int(v.severe_shape.sum()),
                severe_eta=int(v.severe_eta.sum()),severe_gamma=int(v.severe_gamma.sum()),severe_any=int(v.severe_any.sum()))
            for p in ['beta','eta','gamma']:
                item[p+'_bias']=v[p+'_error'].mean();item[p+'_rmse']=np.sqrt(np.mean(v[p+'_error']**2)) if len(v) else None
            cross.append(item)
    pd.DataFrame(boundary).to_csv(HERE/'MLE边界与形状.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(cross).to_csv(HERE/'按MMLE成败分组的MLE误差.csv',index=False,encoding='utf-8-sig')
    # Explicit four-cell same-sample status table.
    data.groupby(['n','status_cw','status']).size().rename('count').reset_index().to_csv(
        HERE/'成败交叉表.csv',index=False,encoding='utf-8-sig')
    data[KEY+['status','status_cw','beta_hat','eta_hat','gamma_hat','gap','severe_shape','severe_eta','severe_gamma','severe_any']].to_csv(
        HERE/'逐样本MLE交叉诊断.csv',index=False,encoding='utf-8-sig')
    assert source.shape[0]==18000 and len(cw)==len(mle)==6000
    original_fail=pd.read_csv(BATCH/'failure_reasons.csv')
    assert len(cw[cw.status.ne('success')])==int(original_fail[original_fail.method_variant.eq('MMLE-I')]['count'].sum())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    record=dict(source_sha256=hashes,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        no_new_estimates=True,no_new_samples=True,thresholds=dict(zero_location='gamma_hat==0',
        proximity_gaps_raw=[.0001,1,10],large_shape=[5,9.99,10],
        severe_any='beta_hat>=5 OR abs(eta_error)>=500 OR abs(gamma_error)>=500; descriptive thresholds, not pathology theorem'),
        roots='Only already saved paper-domain estimates; unresolved cases are not proved rootless',all_passed=True)
    (HERE/'诊断核验.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    print(pd.DataFrame(counts).to_string(index=False));print(pd.DataFrame(boundary).to_string(index=False));print(pd.DataFrame(cross).to_string(index=False))

if __name__=='__main__':main()
