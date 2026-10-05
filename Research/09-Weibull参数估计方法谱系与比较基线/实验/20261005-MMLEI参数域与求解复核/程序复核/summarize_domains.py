"""Read saved fits, certify categories, independently check equations and old-directory protection."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import logsumexp
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
sys.path.insert(0,str(REPO/'python'))
from studies.common.sample import generate_sample
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
BASE=HERE.parent/'20261005-MLE-MMLE-WMLE三方法'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def namespace(block):return CFG['base_seed_namespace'] if block==0 else f"{CFG['base_seed_namespace']}:research09-versions:block{block:02d}"

def endpoint_profile(raw,gamma):
    delta=raw-raw[0];d=raw[0]-gamma;t=np.log1p(delta/d);u=t/t[-1]
    def score(k):
        w=np.exp(k*(u-1));return k*(w@u/w.sum()-u.mean())-1
    right=2*len(raw)
    while score(right)<0:right*=2
    k=brentq(score,1e-9,right,xtol=1e-12)
    return float(logsumexp(k*u)-np.log(len(raw))+np.log(np.log1p(1/len(raw))))

def main():
    d=pd.read_csv(HERE/'per_sample.csv.gz');old=pd.read_csv(BASE/'per_sample.csv.gz')
    oldcw=old[old.method_variant=='MMLE'].set_index('sample_sha256');assert len(oldcw)==6000
    older=pd.read_csv(HERE.parent/'20261005-MLE-MMLE全版本固定真值比较/per_sample.csv.gz')
    oldpaper=older[older.method_variant=='mmle_i_paper'].set_index('sample_sha256')
    assert len(oldpaper)==6000
    certificates=pd.read_csv(HERE/'无根证书索引.csv');assert len(certificates)==860 and certificates.certified.all()
    certset=set(certificates.sha);rows=[];valid_checks=0;maxeq=np.zeros(3);old_diffs=[]
    for row in d[d.method_variant=='cw_engineering'].itertuples():
        raw=generate_sample(*CFG['truth'],int(row.n),int(row.repeat_id),seed=namespace(int(row.block)))
        assert digest_bytes(raw)==row.sample_sha256
        record=json.loads(row.extra)['solution_info']['diagnostic'];prev=oldcw.loc[row.sample_sha256]
        for name,oldtable in [('engineering',oldcw),('paper',oldpaper)]:
            fit=record['fits'][name];estimate=fit['estimate'];prior=oldtable.loc[row.sample_sha256]
            assert (estimate is not None)==(prior.status=='success'),(name,row.sample_sha256)
            if estimate:
                hats=np.array([estimate['beta'],estimate['eta'],estimate['gamma']]);original=prior[['beta_hat','eta_hat','gamma_hat']].to_numpy(float)
                old_diffs.append(np.abs(hats-original));assert np.allclose(hats,original,rtol=1e-8,atol=1e-5)
                beta,eta,gamma=hats;z=raw-gamma;logs=np.log(z);w=np.exp(beta*(logs-logs.max()));w/=w.sum()
                eq=np.array([1/beta-w@logs+logs.mean(),np.mean(np.exp(beta*np.log(z/eta)))-1,
                             -np.expm1(-np.exp(beta*np.log((raw[0]-gamma)/eta)))-1/(len(raw)+1)])
                maxeq=np.maximum(maxeq,np.abs(eq));assert max(np.abs(eq))<1e-8;valid_checks+=1
        if prev.status=='success':continue
        candidates=record['candidates'];eng=record['fits']['engineering'];paper=record['fits']['paper']
        if eng['estimate'] is not None:category='old_grid_missed_accepted_root'
        elif paper['estimate'] is not None:
            category='negative_root_in_paper_domain' if paper['estimate']['gamma']<0 else 'positive_root_shape_cap_only'
        elif candidates:category='root_outside_paper_domain'
        elif row.sample_sha256 in certset:category='certified_no_root_all_location_domain'
        else:category='unresolved_numerical_search'
        first=candidates[0] if candidates else {}
        low=paper['location_lower_raw'];cv=np.load(HERE/'逐样本曲线'/f'{row.sample_sha256}.npz')
        assert np.array_equal(cv['sample'],raw)
        rows.append(dict(n=int(row.n),block=int(row.block),repeat_id=int(row.repeat_id),sample_sha256=row.sample_sha256,
            old_status=str(prev.status),category=category,beta_root=first.get('beta'),eta_root=first.get('eta'),gamma_root=first.get('gamma'),
            paper_gamma_lower=low,engineering_gamma_lower=0.,engineering_boundary_residual=endpoint_profile(raw,0.),
            paper_boundary_residual=endpoint_profile(raw,low),finite_curve_minimum=record['finite_minimum_residual'],
            finite_curve_minimum_gamma=record['finite_minimum_gamma'],finite_minimum_sign=int(np.sign(record['finite_minimum_residual'])),
            limit_residual=record['limit_residual'],observed_monotone_decreasing=record['observed_monotone_decreasing'],
            interior_extrema=record['local_extrema'],log_gap_step=record['log_gap_step'],grid_points=record['grid_points'],
            search_gamma_low=record['searched_gamma_low'],search_gamma_high=record['searched_gamma_high'],
            negative_root=bool(first.get('gamma',1)<0),below_paper_location=bool(first.get('gamma',np.inf)<low),
            above_paper_shape=bool(first.get('beta',0)>=15),above_engineering_shape=bool(first.get('beta',0)>=9.99),
            curve_file=str(HERE/'逐样本曲线'/f'{row.sample_sha256}.npz'),
            certificate_file=str(HERE/'无根区间证书'/f'{row.sample_sha256}.json') if not candidates else ''))
    diagnosis=pd.DataFrame(rows);assert len(diagnosis)==1769
    diagnosis.to_csv(HERE/'旧失败逐样本归因.csv',index=False,encoding='utf-8-sig')
    diagnosis.groupby(['n','category']).size().unstack(fill_value=0).to_csv(HERE/'旧失败归因汇总.csv',encoding='utf-8-sig')
    summary=[];wide=[]
    for method,label in [('cw_engineering','工程域 MMLE-I'),('cw_paper','原文域 MMLE-I')]:
        columns={'policy':method,'label':label}
        for n in CFG['n_values']:
            part=d[(d.method_variant==method)&(d.n==n)];good=part[part.status=='success'];records=[json.loads(s)['solution_info']['diagnostic'] for s in part.extra]
            outside=sum(r['fits']['engineering' if method=='cw_engineering' else 'paper']['status']=='outside_declared_domain_root' for r in records)
            no_root=sum(sha in certset for sha in part.sample_sha256);unresolved=len(part)-len(good)-outside-no_root
            result=dict(policy=method,label=label,n=n,total=len(part),accepted=len(good),acceptance_rate=len(good)/len(part),
                        outside_declared_domain_root=outside,certified_no_root=no_root,numerical_unresolved=unresolved)
            for p in ['beta','eta','gamma']:
                error=good[p+'_error'].to_numpy();bias=error.mean();sd=error.std(ddof=0);rmse=np.sqrt(np.mean(error**2))
                assert np.isclose(rmse**2,bias**2+sd**2,rtol=1e-12)
                result.update({p+'_bias':bias,p+'_sd':sd,p+'_rmse':rmse})
            summary.append(result);columns.update({f'n{n}_{key}':v for key,v in result.items() if key not in ['policy','label','n']})
        wide.append(columns)
    summary=pd.DataFrame(summary);summary.to_csv(HERE/'两口径分n统计.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(wide).to_csv(HERE/'两行汇总表.csv',index=False,encoding='utf-8-sig')
    # Failures count only the stated domain. Roots excluded by it stay visible separately.
    joined=diagnosis.groupby('n').agg(old_failed=('category','size'),negative_paper_root=('category',lambda s:(s=='negative_root_in_paper_domain').sum()),
        positive_shape_only=('category',lambda s:(s=='positive_root_shape_cap_only').sum()),wider_root=('category',lambda s:(s=='root_outside_paper_domain').sum()),
        no_root=('category',lambda s:(s=='certified_no_root_all_location_domain').sum()))
    joined['domain_relaxation_gain']=joined.negative_paper_root+joined.positive_shape_only
    joined=joined.reindex(CFG['n_values'],fill_value=0)
    joined['old_mle_success']=old[old.method_variant=='MLE'].groupby('n').apply(lambda s:(s.status=='success').sum())
    joined.to_csv(HERE/'域设定影响.csv',encoding='utf-8-sig')
    protection=json.loads((HERE/'原主目录保护.json').read_text(encoding='utf-8'))
    actual={str(p):digest(p) for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert actual==protection,'Protected original batch changed'
    record=dict(shared_sample_sha256_verified=6000,equation_checks=valid_checks,max_absolute_equation_residual=maxeq.tolist(),
       unchanged_accepted_status=12000,maximum_parameter_change_from_old=np.max(old_diffs,axis=0).tolist(),
       old_failure_curves=1769,no_root_interval_certificates=860,certificate_intervals=int(certificates.intervals.sum()),
       min_certificate_residual_lower_bound=float(certificates.minimum_C_lower.min()),old_main_files_unchanged=len(protection),
       old_grid_missed_accepted_roots=int((diagnosis.category=='old_grid_missed_accepted_root').sum()),
       tangent_roots_found=0,observed_monotone_curves=int(diagnosis.observed_monotone_decreasing.sum()),
       new_samples=0,new_cw_domain_outputs=12000,all_passed=True,python=sys.executable,
       output_sha256={str(p):digest(p) for p in HERE.glob('*.csv')})
    (HERE/'复核记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary.to_string(index=False));print(joined.to_string());print(json.dumps(record,ensure_ascii=False,indent=2))

def digest_bytes(values):return hashlib.sha256(values.tobytes()).hexdigest()
if __name__=='__main__':main()
