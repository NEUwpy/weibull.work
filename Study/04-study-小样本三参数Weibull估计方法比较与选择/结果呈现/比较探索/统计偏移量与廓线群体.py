"""Analyze paired estimates and independently evaluate local profile geometry."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from scipy.stats import binom,binomtest,percentileofscore
from 验证MDM偏移量与廓线群体 import STUDY,OUT,HERE,NS,sha,dump,table,validate
from 绘制嵌套样本拟合 import nested_samples
from 第三章机制候选图 import mdm_conditional,gradient
from studies.common.metrics import summarize_standard_errors
from methods.conditional_profiles import mle_profile

IDS=list(range(0,1200,10));VARIANTS=['MLE','MMLE','MDM-0','MDM-0.1']
TRUTH={'beta':5.,'eta':1000.,'gamma':500.}


def summarize(frame,variants):
    records=[]
    for n in NS:
        d=frame[frame.n.eq(n)]
        states=d.pivot(index='repeat_id',columns='method_variant',values='status')
        common=states.index[states[variants].eq('success').all(axis=1)]
        for variant in variants:
            v=d[d.method_variant.eq(variant)]
            for subset,chosen in [('own',v[v.status.eq('success')]),('common',v[v.repeat_id.isin(common)])]:
                record=dict(n=n,method=variant,subset=subset,total=len(v),valid=len(chosen),
                            valid_rate=float(v.status.eq('success').mean()))
                for p,truth in TRUTH.items():
                    stats=summarize_standard_errors(chosen[p+'_hat'].to_numpy(float)-truth)
                    record.update({p+'_'+k:stats[k] for k in ['bias','sd','rmse','mse']})
                records.append(record)
    return pd.DataFrame(records)


def existing_seven():
    variants=['MLE','MMLE(KR)','WMLE','LSE','LRE(Park)','MDM-0.1','MM'];rows=[]
    saved_summary=pd.read_csv(STUDY/'结果/W5,1000,500/条件汇总.csv')
    for n in NS:
        d=table(n);common=d[[v+'_状态' for v in variants]].eq('success').all(axis=1)
        for variant in variants:
            own=d[variant+'_状态'].eq('success')
            source=saved_summary[saved_summary.n.eq(n)&saved_summary.method.eq(variant)].iloc[0]
            for subset,mask in [('own',own),('common',common)]:
                r=dict(n=n,method=variant,subset=subset,total=1200,valid=int(mask.sum()))
                for p,label in [('beta','形状'),('eta','尺度'),('gamma','位置')]:
                    metrics=summarize_standard_errors(d.loc[mask,variant+'_'+label+'估计'].to_numpy(float)-TRUTH[p])
                    for k in ['bias','sd','rmse','mse']:r[p+'_'+k]=metrics[k]
                    if subset=='own':
                        for k in ['bias','sd','rmse']:assert np.isclose(metrics[k],source[p+'_'+k],rtol=1e-9)
                rows.append(r)
    return pd.DataFrame(rows)


def curvature(job):
    row,x=job;n=int(row['n']);variant=row['method_variant']
    r=dict(source_id=IDS[int(row['repeat_id'])],n=n,method=variant,
           gamma=row['gamma_hat'],beta=row['beta_hat'],status=row['status'],category='failure')
    if row['status']!='success':return r
    g=float(row['gamma_hat']);b=float(row['beta_hat']);gap=float(x[0]-g)
    info=json.loads(row['extra']).get('solution_info',{})
    if info.get('root_solver')=='right_edge_fit':r['category']='right_edge_fit';return r
    if g==0:r['category']='zero_boundary';return r
    bound=(b<=1.001) if variant=='MLE' else (b<=.101 or b>=14.999)
    if bound:r['category']='shape_boundary';return r
    h=min(2.,g/3,gap/3);r['h']=h
    if h<.001:r['category']='near_support_or_zero';return r
    if variant=='MLE':
        center=mle_profile(x,g);s=lambda u:-mle_profile(x,u)['ll'];factor=1000.**2
        residual=1000.*abs(center['location_score'])/n
    else:
        s=lambda u:float(mdm_conditional(x,u)[1]);factor=1000.
        residual=abs(gradient(x,g)-(0. if variant=='MDM-0' else .1))
    r['root_residual']=residual
    if not np.isfinite(residual) or residual>1e-4:r['category']='root_residual';return r
    f0=s(g);k1=factor*(s(g+h)-2*f0+s(g-h))/h**2
    k2=factor*(s(g+h/2)-2*f0+s(g-h/2))/(h/2)**2
    r.update(curvature_h=k1,curvature_half_h=k2,
             relative_step_difference=abs(k1-k2)/max(abs(k1),abs(k2),1e-12))
    if not np.isfinite([k1,k2]).all() or min(k1,k2)<=0:r['category']='nonpositive_curvature';return r
    if r['relative_step_difference']>.2:r['category']='step_unstable';return r
    r.update(category='reliable',kappa=k2,kappa_per_observation=k2/n if variant=='MLE' else None)
    return r


def ratio_summary(frame,method,column='kappa'):
    d=frame[frame.method.eq(method)&frame.category.eq('reliable')]
    wide=d.pivot(index='source_id',columns='n',values=column).reindex(columns=[50,7]).dropna()
    ratios=wide[7]/wide[50];values=np.sort(ratios.to_numpy(float));count=len(values)
    result=dict(method=method,quantity=column,paired=count,total_paths=120,
                ratio_median=float(np.median(values)) if count else None,
                lower_count=int((values<1).sum()),ratio_median_ci95=None,lower_fraction_ci95=None)
    if count:
        ci=binomtest(result['lower_count'],count).proportion_ci(.95,method='wilson')
        result.update(lower_fraction=result['lower_count']/count,lower_fraction_ci95=[float(ci.low),float(ci.high)])
    if count>=6:
        k=int(binom.ppf(.025,count,.5))
        result['ratio_median_ci95']=[float(values[k-1]),float(values[count-k])]
    return result,ratios


def medoid(values):
    center=values.median();mad=(values-center).abs().median()
    iqr=values.quantile(.75)-values.quantile(.25)
    scale=mad.where(mad>0,iqr).where(lambda a:a>0,values.std(ddof=0)).where(lambda a:a>0,1.)
    distances=((values-center)/scale).abs().mean(axis=1)
    return int(distances.sort_index().idxmin()),distances,center,scale


def choose_examples(nested,geometry):
    endpoints=nested[nested.n.isin([50,7])]
    states=endpoints.pivot(index='repeat_id',columns=['method_variant','n'],values='status')
    good=states.index[states.eq('success').all(axis=1)]
    assert len(good)>0
    rows=[]
    for rid in good:
        r={'source_id':IDS[int(rid)]}
        d=endpoints[endpoints.repeat_id.eq(rid)]
        for variant in VARIANTS:
            for n in [50,7]:
                v=d[d.method_variant.eq(variant)&d.n.eq(n)].iloc[0]
                for p,truth in TRUTH.items():r[f'{variant}_{n}_{p}']=(v[p+'_hat']-truth)/(5. if p=='beta' else 1000.)
        rows.append(r)
    features=pd.DataFrame(rows).set_index('source_id')
    main,distances,center,scale=medoid(features)
    result=dict(main_source_id=main,endpoint_common_valid=len(good),total_paths=120,
        selection='24-dimensional endpoint-error median/MAD distance; no curvature direction filter',
        selected_distance=float(distances.loc[main]),feature_medians=center.to_dict(),feature_scales=scale.to_dict(),
        selected_features=features.loc[main].to_dict(),parameter_change_percentiles={},curvature_percentiles={})
    for variant in VARIANTS:
        d=endpoints[endpoints.method_variant.eq(variant)&endpoints.repeat_id.isin(good)]
        for p in TRUTH:
            w=d.pivot(index='repeat_id',columns='n',values=p+'_hat');change=w[7]-w[50]
            result['parameter_change_percentiles'][variant+'_'+p]=float(percentileofscore(change,change.loc[IDS.index(main)],kind='mean'))
    for method in ['MLE','MDM-0','MDM-0.1']:
        _,ratios=ratio_summary(geometry,method)
        if main in ratios.index:result['curvature_percentiles'][method]=float(percentileofscore(ratios,ratios.loc[main],kind='mean'))
    reliable=geometry[geometry.method.eq('MDM-0')&geometry.category.eq('reliable')]
    w=reliable.pivot(index='source_id',columns='n',values='kappa').reindex(columns=[50,7]).dropna()
    if len(w):
        params=nested[nested.method_variant.eq('MDM-0')].copy();params['source_id']=params.repeat_id.map(lambda x:IDS[int(x)])
        g=params.pivot(index='source_id',columns='n',values='gamma_hat')
        z=pd.DataFrame({'log_ratio':np.log(w[7]/w[50]),'log_k50':np.log(w[50]),
                        'g50':g.loc[w.index,50]/1000,'g7':g.loc[w.index,7]/1000})
        typical,*_=medoid(z);median=float(z.log_ratio.median())
        opposite=z[z.log_ratio*median<0]
        counter=medoid(opposite)[0] if len(opposite) else None
        result.update(curvature_typical_source_id=typical,curvature_opposite_source_id=counter,
                      curvature_pair_count=len(w),opposite_direction_count=len(opposite))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=8);args=parser.parse_args()
    before=validate();primary=pd.read_csv(OUT/'正式样本/results.csv',float_precision='round_trip')
    nested=pd.read_csv(OUT/'嵌套四法/results.csv',float_precision='round_trip')
    assert len(primary)==12000 and len(nested)==2400
    metrics=summarize(primary,['MDM-0','MDM-0.1']);metrics.to_csv(OUT/'偏移量指标.csv',index=False,encoding='utf-8-sig')
    original=existing_seven();original.to_csv(OUT/'七法指标.csv',index=False,encoding='utf-8-sig')
    formal=pd.read_csv(STUDY/'结果/W5,1000,500/条件汇总.csv')
    for _,r in metrics[metrics.method.eq('MDM-0.1')&metrics.subset.eq('own')].iterrows():
        source=formal[formal.n.eq(r.n)&formal.method.eq('MDM-0.1')].iloc[0]
        for p in TRUTH:
            for k in ['bias','sd','rmse']:assert np.isclose(r[p+'_'+k],source[p+'_'+k],rtol=1e-10)
    paths=nested_samples(table(50).reset_index(),IDS)
    jobs=[(r.to_dict(),paths[IDS[int(r.repeat_id)],int(r.n)]) for _,r in nested[nested.method_variant.ne('MMLE')].iterrows()]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        geometry=pd.DataFrame(pool.map(curvature,jobs,chunksize=15))
    geometry.to_csv(OUT/'廓线几何.csv',index=False,encoding='utf-8-sig')
    ratios=[ratio_summary(geometry,m)[0] for m in ['MLE','MDM-0','MDM-0.1']]
    ratios.append(ratio_summary(geometry,'MLE','kappa_per_observation')[0])
    examples=choose_examples(nested,geometry)
    categories=geometry.groupby(['method','n','category']).size().rename('count').reset_index()
    categories.to_csv(OUT/'几何可用性.csv',index=False,encoding='utf-8-sig')
    summary=dict(scope='W(5,1000,500), five n; 1200 formal samples/cell and 120 separate nested paths',
                 primary_metrics=metrics.to_dict('records'),ratios=ratios,examples=examples,
                 geometry_categories=categories.to_dict('records'),
                 sources={q.relative_to(STUDY).as_posix():sha(q) for q in [OUT/'正式样本/results.csv',OUT/'嵌套四法/results.csv',OUT/'廓线几何.csv']})
    dump(OUT/'群体结论.json',summary);assert before==validate()
    print(json.dumps(dict(ratios=ratios,examples={k:v for k,v in examples.items() if k not in ['feature_medians','feature_scales','selected_features']}),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
