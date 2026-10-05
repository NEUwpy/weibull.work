"""Read-only comparison of two parameter batches with Monte Carlo uncertainty."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_function
from scipy.stats import fisher_exact

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
METHODS=['MLE','MMLE','WMLE']
PARAMS=['beta','eta','gamma']
SIZES=[7,10,15,20,50]
BOOTSTRAPS=9999
BOOTSTRAP_SEED=2026100514
BATCHES={'A':ROOT/'W(2,1000,1000)','B':ROOT/'W(2,1000,500)'}
RAW={'A':ROOT/'20261005-KunduRaqab原版MMLE三方法/程序/per_sample.csv.gz',
     'B':Path(r'D:\Hermes Email\执行完毕\research09-kundu-mmle-gamma500-013\运行记录\程序\per_sample.csv.gz')}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inputs():
    guard={str(p):sha(p) for batch in BATCHES.values() for p in batch.rglob('*') if p.is_file()}
    (HERE/'输入保护.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
    detail={key:pd.read_csv(path/'结果/估计明细.csv',float_precision='round_trip') for key,path in BATCHES.items()}
    summary={key:pd.read_csv(path/'结果/三方法汇总.csv',float_precision='round_trip') for key,path in BATCHES.items()}
    samples={key:pd.read_csv(path/'结果/样本.csv',float_precision='round_trip') for key,path in BATCHES.items()}
    return guard,detail,summary,samples

def errors(rows,n,truth):
    array=np.full((1200,3,3),np.nan)
    valid=np.zeros((1200,3),bool)
    for m,method in enumerate(METHODS):
        g=rows[(rows.n==n)&(rows['方法']==method)].sort_values('组号')
        assert g['组号'].tolist()==list(range(1,1201))
        ok=g['状态'].eq('成功').to_numpy()
        values=g[['β估计','η估计','γ估计']].to_numpy()-np.array([2.,1000.,truth])
        array[:,m,:]=np.where(ok[:,None],values,np.nan)
        valid[:,m]=ok
    return array,valid

def bootstrap_metrics(array,valid,rng):
    flat=np.nan_to_num(array.reshape(1200,9))
    valid_float=valid.astype(float)
    result=[]
    for start in range(0,BOOTSTRAPS,250):
        size=min(250,BOOTSTRAPS-start)
        weights=rng.multinomial(1200,np.full(1200,1/1200),size=size).astype(float)
        number=weights@valid_float
        denom=np.repeat(number,3,axis=1)
        assert (denom>0).all()
        means=(weights@flat)/denom
        squares=(weights@(flat*flat))/denom
        sd=np.sqrt(np.maximum(squares-means*means,0))
        result.append(np.concatenate([number/1200,means,sd,np.sqrt(squares)],axis=1))
    return np.concatenate(result)

def analytic_se(values,metric):
    m=len(values)
    if metric=='bias':influence=values-values.mean()
    elif metric=='sd':
        sd=values.std(ddof=0)
        influence=((values-values.mean())**2-sd**2)/(2*sd)
    else:
        rmse=np.sqrt(np.mean(values*values))
        influence=(values*values-rmse**2)/(2*rmse)
    return float(np.sqrt(np.var(influence,ddof=1)/m))

def wilson(success,total):
    z=1.959963984540054
    p=success/total
    denominator=1+z*z/total
    center=(p+z*z/(2*total))/denominator
    half=z*np.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return max(0.,center-half),min(1.,center+half)

def primary_comparison(detail,summary):
    rows=[]
    for n in SIZES:
        a,va=errors(detail['A'],n,1000.)
        b,vb=errors(detail['B'],n,500.)
        rng_a=np.random.default_rng(np.random.SeedSequence([BOOTSTRAP_SEED,n,0]))
        rng_b=np.random.default_rng(np.random.SeedSequence([BOOTSTRAP_SEED,n,1]))
        distribution=bootstrap_metrics(b,vb,rng_b)-bootstrap_metrics(a,va,rng_a)
        for m,method in enumerate(METHODS):
            sa=summary['A'][(summary['A'].method==method)&(summary['A'].n==n)].iloc[0]
            sb=summary['B'][(summary['B'].method==method)&(summary['B'].n==n)].iloc[0]
            pa,pb=sa.success_rate,sb.success_rate
            la,ua=wilson(int(sa.success),1200)
            lb,ub=wilson(int(sb.success),1200)
            delta=pb-pa
            low=delta-np.sqrt((pb-lb)**2+(ua-pa)**2)
            high=delta+np.sqrt((ub-pb)**2+(pa-la)**2)
            p=fisher_exact([[int(sb.success),1200-int(sb.success)],[int(sa.success),1200-int(sa.success)]],alternative='two-sided').pvalue
            rows.append(dict(method=method,n=n,parameter='all',metric='success_rate',A=pa,B=pb,delta=delta,
                             valid_A=int(sa.success),valid_B=int(sb.success),
                             se_analytic=float(np.sqrt(pa*(1-pa)/1200+pb*(1-pb)/1200)),
                             se_boot=float(distribution[:,m].std(ddof=1)),ci_low=low,ci_high=high,p=float(p),
                             ci_method='Newcombe difference of Wilson intervals',test='Fisher exact',
                             degenerate_plugin_se=bool(pa==1 and pb==1)))
            for j,param in enumerate(PARAMS):
                for k,metric in enumerate(['bias','sd','rmse']):
                    ea=a[va[:,m],m,j]
                    eb=b[vb[:,m],m,j]
                    expected_a=sa[param+'_'+metric]
                    expected_b=sb[param+'_'+metric]
                    delta=float(expected_b-expected_a)
                    index=3+k*9+m*3+j
                    diff=distribution[:,index]
                    noise=diff-delta
                    qlo,qhi=np.quantile(noise,[.025,.975])
                    p=min(1.,2*min((np.sum(noise<=delta)+1)/(BOOTSTRAPS+1),(np.sum(noise>=delta)+1)/(BOOTSTRAPS+1)))
                    rows.append(dict(method=method,n=n,parameter=param,metric=metric,
                                     A=float(expected_a),B=float(expected_b),delta=delta,
                                     valid_A=len(ea),valid_B=len(eb),
                                     se_analytic=float(np.hypot(analytic_se(ea,metric),analytic_se(eb,metric))),
                                     se_boot=float(diff.std(ddof=1)),ci_low=float(delta-qhi),ci_high=float(delta-qlo),
                                     p=float(p),ci_method='basic bootstrap, resample 1200 groups including failures',
                                     test='centered bootstrap equal-tail',degenerate_plugin_se=False))
        print(json.dumps(dict(n=n,bootstrap_replications=BOOTSTRAPS,metrics_completed=len(rows))),flush=True)
    result=pd.DataFrame(rows)
    assert len(result)==150
    order=np.argsort(result.p.to_numpy(),kind='stable')
    adjusted=np.maximum.accumulate((150-np.arange(150))*result.p.to_numpy()[order])
    p_holm=np.empty(150)
    p_holm[order]=np.minimum(adjusted,1.)
    result['p_holm']=p_holm
    result['outside_pointwise_noise']=(result.ci_low>0)|(result.ci_high<0)
    result['holm_reject']=result.p_holm<.05
    result['signal_in_se']=np.divide(result.delta,result.se_boot,out=np.zeros(150),where=result.se_boot.to_numpy()>0)
    result.to_csv(HERE/'全部差异与噪声.csv',index=False,encoding='utf-8-sig')
    return result

def boundary_diagnostics(detail,samples):
    records=[]
    bins=[]
    for key,truth in [('A',1000.),('B',500.)]:
        sample=samples[key].set_index(['n','组号'])
        for n in SIZES:
            thresholds=1000*np.sqrt(-np.log(1-np.array([.25,.5,.75]))/n)
            observed=sample.loc[n]
            truth_gap=observed['x(1)'].to_numpy()-truth
            quartiles=np.searchsorted(thresholds,truth_gap,side='right')+1
            for method in METHODS:
                rows=detail[key][(detail[key].n==n)&(detail[key]['方法']==method)].sort_values('组号')
                ok=rows['状态'].eq('成功').to_numpy()
                estimates=rows.loc[ok,'γ估计'].to_numpy()
                retained_min=rows.loc[ok,'支持检查最小值'].to_numpy()
                gamma_error=estimates-truth
                records.append(dict(batch=key,truth_gamma=truth,n=n,method=method,success=int(ok.sum()),
                                    negative_gamma_estimates=int(np.sum(estimates<0)),negative_share=float(np.mean(estimates<0)),
                                    gamma_bias_relative_truth=float(gamma_error.mean()/truth),
                                    gamma_rmse_relative_truth=float(np.sqrt(np.mean(gamma_error**2))/truth),
                                    gamma_bias_relative_eta=float(gamma_error.mean()/1000),
                                    true_min_gap_mean=float(truth_gap.mean()),
                                    fitted_retained_gap_mean=float((retained_min-estimates).mean()),
                                    fitted_retained_gap_median=float(np.median(retained_min-estimates)),
                                    full_sample_gap_zero_by_construction=method=='MMLE'))
                if method=='MLE':
                    for quartile in range(1,5):
                        mask=quartiles==quartile
                        bins.append(dict(batch=key,n=n,quartile=quartile,total=int(mask.sum()),success=int(ok[mask].sum()),
                                         success_rate=float(ok[mask].mean()),
                                         lower_true_gap=0. if quartile==1 else float(thresholds[quartile-2]),
                                         upper_true_gap=None if quartile==4 else float(thresholds[quartile-1])))
    pd.DataFrame(records).to_csv(HERE/'支持距离与相对位置.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(bins).to_csv(HERE/'MLE真值边界距离分层.csv',index=False,encoding='utf-8-sig')
    return records,bins

def root_selection_audit(detail):
    audit=[]
    for key,shift in [('A',-500.),('B',500.)]:
        raw=pd.read_csv(RAW[key])
        source=detail[key].set_index(['n','block','repeat_id','方法'])
        for row in raw[raw.method_variant=='WMLE'].itertuples():
            info=json.loads(row.extra)['solution_info']
            valid=[c for c in info['candidates'] if c['in_shape_domain'] and c['local_maximum'] and c['objective']<=1e-8]
            d=source.loc[(row.n,row.block,row.repeat_id,'WMLE')]
            xmin=d['原始最小值']/1000
            def score(c,change):
                location=c['gamma']/1000+change/1000
                sample_min=xmin+change/1000
                return math.log(c['beta']/2)**2+((location-.9*sample_min)/max(sample_min,1))**2
            before=min(range(len(valid)),key=lambda i:score(valid[i],0))
            after=min(range(len(valid)),key=lambda i:score(valid[i],shift))
            chosen=valid[before]
            assert math.isclose(chosen['beta'],d['β估计'],rel_tol=2e-12)
            assert math.isclose(chosen['gamma'],d['γ估计'],rel_tol=2e-12,abs_tol=2e-10)
            audit.append(dict(batch=key,n=row.n,block=row.block,repeat_id=row.repeat_id,
                              valid_roots=len(valid),shift=shift,selection_changed=before!=after))
    pd.DataFrame(audit).to_csv(HERE/'WMLE平移选根复核.csv',index=False,encoding='utf-8-sig')
    return audit

def main():
    guard,detail,summary,samples=inputs()
    differences=primary_comparison(detail,summary)
    diagnostics,bins=boundary_diagnostics(detail,samples)
    audit=root_selection_audit(detail)
    theory=[]
    for n in SIZES:
        scale=1000/n**.5
        bias=scale*gamma_function(1.5)
        sd=scale*np.sqrt(1-gamma_function(1.5)**2)
        values={key:summary[key][(summary[key].method=='MMLE')&(summary[key].n==n)].iloc[0] for key in ['A','B']}
        theory.append(dict(n=n,gamma_bias_theory=float(bias),gamma_sd_theory=float(sd),gamma_rmse_theory=float(scale),
                           A_bias=float(values['A'].gamma_bias),B_bias=float(values['B'].gamma_bias),
                           A_z_from_theory=float((values['A'].gamma_bias-bias)/(sd/np.sqrt(1200))),
                           B_z_from_theory=float((values['B'].gamma_bias-bias)/(sd/np.sqrt(1200)))))
    pd.DataFrame(theory).to_csv(HERE/'MMLE位置偏差理论.csv',index=False,encoding='utf-8-sig')
    assert all(sha(Path(p))==digest for p,digest in guard.items())
    current={str(p) for batch in BATCHES.values() for p in batch.rglob('*') if p.is_file()}
    assert current==set(guard)
    meta=dict(bootstrap_replications=BOOTSTRAPS,bootstrap_seed=BOOTSTRAP_SEED,main_tests=150,
              scalar_precision_tests=135,success_rate_tests=15,
              pointwise_exclusions=int(differences.outside_pointwise_noise.sum()),
              holm_rejections=int(differences.holm_reject.sum()),minimum_p=float(differences.p.min()),
              minimum_holm_p=float(differences.p_holm.min()),protected_files_unchanged=len(guard),
              wmle_valid_root_counts={key:pd.Series([r['valid_roots'] for r in audit if r['batch']==key]).value_counts().to_dict() for key in ['A','B']},
              wmle_translation_selection_changes=sum(r['selection_changed'] for r in audit),
              parameter_estimation_reruns=0,theoretical_mmle_position_bias=theory)
    (HERE/'分析核验.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False))
    print(differences[differences.outside_pointwise_noise][['method','n','parameter','metric','delta','se_boot','ci_low','ci_high','p','p_holm']].to_string(index=False))

if __name__=='__main__':main()
