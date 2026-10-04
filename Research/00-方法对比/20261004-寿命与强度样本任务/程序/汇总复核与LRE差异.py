"""Summarize paired changes and numerical anomalies; preserves all original artifacts."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'结果/复核与LRE对比'
PARAMETERS = [('beta_hat','β'),('eta_hat','η'),('gamma_hat','γ')]


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(median=float(np.median(a)), p90=float(np.quantile(a,.9)), maximum=float(np.max(a)))


def main():
    audits = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('W(*).json'))]
    assert len(audits)==8
    pairs = [r for a in audits for r in a['lre_pairs']]
    assert len(pairs)==1200
    totals, failure_rows, boundary_rows, conditions, parameters, quantiles, detailed = [], [], [], [], [], [], []
    method_counts=Counter()
    for audit in audits:
        name=audit['distribution']
        raw=json.loads((ROOT/'结果'/name/'中间数据/results.json').read_text(encoding='utf-8'))
        beta,eta,gamma=raw['truth']
        samples={(s['n'],s['id']):s for s in raw['samples']}
        for r in raw['results']:
            method_counts[r['method_id'],'total']+=1
            method_counts[r['method_id'],'returned']+=int(r['converged'])
            method_counts[r['method_id'],'valid']+=int(r['status']=='success')
            kind=None
            extra=r['extra'] or {}
            solution=extra.get('solution_info') or {}
            if not r['converged']:
                kind=solution.get('status') or extra.get('raw_status') or 'unknown_failure'
            elif r['status']=='failure':
                kind='boundary_pathology'
            elif r['gamma_hat']==0:
                kind='gamma_zero'
            if kind:
                sample_min=samples[r['n'],r['id']]['values'][0]
                row=[name,r['n'],r['id'],r['method_id'],kind,*[r[k] for k,_ in PARAMETERS],sample_min,
                     sample_min-r['gamma_hat'] if r['gamma_hat'] is not None else None,r['r_squared']]
                boundary_rows.append(row)
                if kind!='gamma_zero':failure_rows.append(row)
        for n in raw['n']:
            counts=[]
            for method in ['mdm','lse','lre','wmle','mle']:
                group=[r for r in raw['results'] if r['n']==n and r['method_id']==method]
                counts.append(sum(r['status']=='failure' for r in group))
            totals.append([name,n,*counts])
        for n in (7,15,30):
            group=[r for r in pairs if r['distribution']==name and r['n']==n]
            assert len(group)==50 and all(r['old']['converged'] and r['new']['converged'] for r in group)
            zeros=[sum(r[v]['gamma_hat']==0 for r in group) for v in ('old','new')]
            transitions=sum((r['old']['gamma_hat']==0)!=(r['new']['gamma_hat']==0) for r in group)
            conditions.append(dict(distribution=name,n=n,old_gamma_zero=zeros[0],new_gamma_zero=zeros[1],zero_transitions=transitions))
            for key,symbol in PARAMETERS:
                old=[r['old'][key] for r in group]
                new=[r['new'][key] for r in group]
                signed=[v-u for u,v in zip(old,new)]
                absolute=stats(np.abs(signed))
                # beta and eta: percentage of the historical estimate. gamma: physical units.
                scaled=[100*abs(v-u)/u for u,v in zip(old,new)] if key!='gamma_hat' else [100*abs(v-u)/eta for u,v in zip(old,new)]
                size=stats(scaled)
                row=[name,n,symbol,float(np.median(old)),float(np.median(new)),float(np.median(signed)),
                     absolute['median'],absolute['p90'],absolute['maximum'],size['median'],size['p90'],size['maximum']]
                parameters.append(row)
            for qi,p in enumerate((.01,.1,.5,.9)):
                old=[r['quantiles'][qi]['old'] for r in group]
                new=[r['quantiles'][qi]['new'] for r in group]
                truth=group[0]['quantiles'][qi]['truth']
                changes=stats(np.abs(np.subtract(new,old)))
                percent=stats(100*np.abs(np.subtract(new,old))/truth)
                quantiles.append([name,n,p,truth,float(np.median(old)),float(np.median(new)),
                                  changes['median'],percent['median'],percent['p90'],percent['maximum']])
    for r in pairs:
        old,new=r['old'],r['new']
        detailed.append([r['distribution'],r['n'],r['id'],old['beta_hat'],new['beta_hat'],new['beta_hat']-old['beta_hat'],
                         old['eta_hat'],new['eta_hat'],new['eta_hat']-old['eta_hat'],
                         old['gamma_hat'],new['gamma_hat'],new['gamma_hat']-old['gamma_hat']])
    global_parameters={}
    for key,symbol in PARAMETERS:
        signed=[r['new'][key]-r['old'][key] for r in pairs]
        scaled=[100*abs(r['new'][key]-r['old'][key])/r['old'][key] for r in pairs] if key!='gamma_hat' else list(np.abs(signed))
        global_parameters[symbol]=dict(absolute=stats(np.abs(signed)),scaled=stats(scaled),signed_median=float(np.median(signed)))
    ablation={}
    for key,symbol in PARAMETERS:
        changes=[abs(r['bernard_with_new_search'][key]-r['old'][key]) for r in pairs]
        ablation[symbol]=stats(changes)
    qglobal={str(p):stats([100*abs(r['quantiles'][qi]['new']-r['quantiles'][qi]['old'])/r['quantiles'][qi]['truth'] for r in pairs])
             for qi,p in enumerate((.01,.1,.5,.9))}
    mdm_gradients=[]
    for audit in audits:
        raw=json.loads((ROOT/'结果'/audit['distribution']/'中间数据/results.json').read_text(encoding='utf-8'))
        samples={(s['n'],s['id']):np.asarray(s['values']) for s in raw['samples']}
        for r in raw['results']:
            if r['method_id']!='mdm':continue
            t=samples[r['n'],r['id']]
            p=(np.arange(1,r['n']+1)-.3)/(r['n']+.4)
            w=(-np.log1p(-p))**(-1/r['beta_hat'])
            scales=(t-r['gamma_hat'])*w
            gradient=-np.dot(scales-scales.mean(),w-w.mean())/((r['n']-1)*scales.std(ddof=1))
            mdm_gradients.append(dict(distribution=audit['distribution'],n=r['n'],id=r['id'],status=r['status'],
                                      analytic_partial_gradient=float(gradient),threshold=.2,
                                      root_solver=r['extra']['solution_info']['root_solver'],r_squared=r['r_squared']))
    failures=Counter(row[4] for row in failure_rows)
    totals_by_method=[dict(method=m,total=method_counts[m,'total'],returned=method_counts[m,'returned'],
                           valid=method_counts[m,'valid'],failure=method_counts[m,'total']-method_counts[m,'valid'])
                      for m in ['mdm','lse','lre','wmle','mle']]
    worst=sorted(pairs,key=lambda r:abs(r['new']['gamma_hat']-r['old']['gamma_hat']),reverse=True)[:5]
    summary=dict(method_counts=totals_by_method,failure_reasons=dict(failures),conditions=conditions,
                 global_parameter_changes=global_parameters,quantile_changes_percent_of_true_lifetime=qglobal,
                 search_only_ablation_absolute_changes=ablation,worst_gamma_pairs=worst,
                 mdm_analytic_gradients=mdm_gradients)
    # Keep independent diagnosis separate from the original success/failure contract.
    for file,kind in [('MLE局部收敛核查.json','likelihood_suboptimal'),('MDM梯度独立核查.json','finite_difference_sensitivity')]:
        source=OUT/file
        if not source.exists():continue
        diagnostic=json.loads(source.read_text(encoding='utf-8'))
        for record in (diagnostic if isinstance(diagnostic,list) else [diagnostic]):
            if kind=='finite_difference_sensitivity' and record['status']!='success':continue
            raw=json.loads((ROOT/'结果'/record['distribution']/'中间数据/results.json').read_text(encoding='utf-8'))
            method='mle' if kind=='likelihood_suboptimal' else 'mdm'
            fit=next(r for r in raw['results'] if (r['n'],r['id'],r['method_id'])==(record['n'],record['id'],method))
            minimum=next(s['values'][0] for s in raw['samples'] if (s['n'],s['id'])==(record['n'],record['id']))
            boundary_rows.append([record['distribution'],record['n'],record['id'],method,kind,
                                  *[fit[k] for k,_ in PARAMETERS],minimum,minimum-fit['gamma_hat'],fit['r_squared']])
    (OUT/'差异与异常汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tables=[dict(name='条件汇总',headers=['参数组合','n','参数','旧版中位数','新版中位数','差值中位数','绝对差中位数','绝对差P90','最大绝对差','幅度中位数(%)','幅度P90(%)','最大幅度(%)'],rows=parameters),
            dict(name='逐组对比',headers=['参数组合','n','组号','旧β','新β','Δβ','旧η','新η','Δη','旧γ','新γ','Δγ'],rows=detailed),
            dict(name='工程分位点',headers=['参数组合','n','累计概率p','真实分位点','旧版中位数','新版中位数','绝对差中位数','差异中位数(%)','差异P90(%)','最大差异(%)'],rows=quantiles),
            dict(name='异常记录',headers=['参数组合','n','组号','方法','情形','β估计','η估计','γ估计','样本最小值','位置间距','R²'],rows=boundary_rows)]
    wmle_file=OUT/'WMLE失败根核查.json'
    if wmle_file.exists():
        roots=json.loads(wmle_file.read_text(encoding='utf-8'))['records']
        rows=[]
        for record in roots:
            root=record['admissible_roots'][0] if record['admissible_roots'] else None
            rows.append([record['distribution'],record['n'],record['id'],record['original_solution_info']['objective'],
                         root['beta'] if root else None,root['eta'] if root else None,root['gamma'] if root else None,
                         root['squared_residual'] if root else None,'原求解器漏解' if root else '本扫描未找到根'])
        tables.append(dict(name='WMLE失败核查',headers=['参数组合','n','组号','原平方残差','根β','根η','根γ','根平方残差','核查结果'],rows=rows))
    (OUT/'比较表数据.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(method_counts=totals_by_method,global_parameters=global_parameters,quantile_changes=qglobal,
                          search_only=ablation,failures=dict(failures),zero_transitions=sum(r['zero_transitions'] for r in conditions)),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
