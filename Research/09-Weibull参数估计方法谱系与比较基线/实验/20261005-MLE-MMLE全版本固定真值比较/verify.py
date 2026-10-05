"""Original-paper fixture, independent residuals and denser root scans."""
import json
from pathlib import Path
import re
import numpy as np
from scipy.special import gamma, logsumexp
from experiment import HERE, fit_mmle, fit_mme, ROMAN, namespace
from studies.common.sample import generate_sample

LIB=Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法')

def residuals(x,p,variant,moment=False):
    b,e,g=p
    gm1=gamma(1+1/b); variance=gamma(1+2/b)-gm1**2
    if moment:
        basic=[(g+e*gm1-x.mean())/x.std(ddof=1),e**2*variance/x.var(ddof=1)-1]
    else:
        logs=np.log(x-g);weights=np.exp(b*(logs-logs.max()))
        basic=[b*(np.dot(weights,logs)/weights.sum()-logs.mean())-1,
               (logsumexp(b*logs)-np.log(len(x)))/b-np.log(e)]
    if variant=='I':extra=b*np.log(x.min()-g)-b*np.log(e)-np.log(np.log1p(1/len(x)))
    elif variant=='II':extra=(g+e*len(x)**(-1/b)*gm1-x.min())/x.std(ddof=1)
    elif variant=='III' and not moment:extra=(g+e*gm1-x.mean())/x.std(ddof=1)
    elif variant=='IV':extra=e**2*variance/x.var(ddof=1)-1
    else:extra=(g+e*np.log(2)**(1/b)-np.median(x))/x.std(ddof=1)
    return np.array(basic+[extra])

def main():
    text=(LIB/'182-091-pdf原文.md').read_text(encoding='utf-8')
    table=text.split('**TABLE V**')[1].split('$n = 100')[0]
    x=np.sort([float(v) for line in table.splitlines() if re.match(r'\| \d+ \|',line)
               for v in line.split('|')[2].split(',')])
    assert len(x)==100
    expected_mmle=[[1.615,1.028,.042],[1.595,1.017,.050],[1.514,.976,.081],
                   [1.486,.963,.089],[1.523,.980,.078]]
    expected_mme=[[1.565,1.016,.047],[1.565,1.016,.047],[1.534,.995,.064]]
    fixtures=[]
    for moment,expected,fitted in [(False,expected_mmle,fit_mmle(tuple(x),True)),
                                  (True,expected_mme,fit_mme(tuple(x)))]:
        for variant,ref in zip(ROMAN,expected):
            p,info=fitted[variant]
            assert p is not None,info
            diff=float(np.max(np.abs(np.array(p)-ref)))
            # Table VI does not exactly satisfy the stated equations for III
            # and (most visibly) MME-II. Preserve this discrepancy explicitly.
            limit=.014 if moment and variant=='II' else .003 if not moment and variant=='III' else .001
            assert diff<limit,(variant,moment,p,ref,diff)
            err=float(np.max(np.abs(residuals(x,p,variant,moment))))
            assert err<1e-8,(variant,moment,err)
            fixtures.append(dict(method=('MME' if moment else 'MMLE')+'-'+variant,
                                 estimated=p,published=ref,max_difference=diff,max_residual=err,
                                 published_max_equation_residual=float(np.max(np.abs(residuals(x,ref,variant,moment)))),
                                 table_match='discrepancy_recorded' if diff>=.001 else 'approximately_matched'))
    checks=[]
    for n in [7,10,15,20,50]:
        for rid in [0,1,2]:
            x=generate_sample(2.0,1000.0,1000.0,n,rid,seed=namespace(0))/1000
            for paper in [False,True]:
                sparse=fit_mmle(tuple(x),paper);dense=fit_mmle(tuple(x),paper,385)
                for variant in ROMAN:
                    p,info=sparse[variant];q,_=dense[variant]
                    assert (p is None)==(q is None),(n,rid,variant,paper,p,q)
                    if p is not None:
                        assert np.max(np.abs(np.array(p)-q))<1e-7
                        assert np.max(np.abs(residuals(x,p,variant)))<1e-8
                    checks.append(dict(n=n,repeat_id=rid,method='MMLE-'+variant,paper_domain=paper,
                                       status=info['status']))
            sparse=fit_mme(tuple(x));dense=fit_mme(tuple(x),1201)
            for variant in ROMAN[:3]:
                p,info=sparse[variant];q,_=dense[variant]
                assert (p is None)==(q is None),(n,rid,variant,p,q)
                if p is not None:
                    assert np.max(np.abs(np.array(p)-q))<1e-7
                    # Invalid-support candidates are preserved, but not accepted.
                    if info['status']=='ok':assert np.max(np.abs(residuals(x,p,variant,True)))<1e-8
                checks.append(dict(n=n,repeat_id=rid,method='MME-'+variant,status=info['status']))
    result=dict(paper_fixtures=fixtures,dense_grid_checks=checks,all_passed=True)
    (HERE/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(paper_fixtures=fixtures,dense_grid_checks=len(checks),all_passed=True)))

if __name__=='__main__':main()
