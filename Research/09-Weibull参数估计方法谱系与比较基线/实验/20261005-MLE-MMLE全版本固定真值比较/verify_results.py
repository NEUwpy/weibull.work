"""Substitute every accepted result into independently written equations."""
import json
import importlib.util
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from experiment import HERE, CONFIG, namespace, fit_mmle, fit_mme, prior
from refine import fit_mmle,fit_mme
spec=importlib.util.spec_from_file_location('local_equation_verification',HERE/'verify.py')
local_verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(local_verify)
residuals=local_verify.residuals
from studies.common.sample import generate_sample
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3

def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz')
    maxima={};counts={}
    for (n,block,rid),part in data.groupby(['n','block','repeat_id']):
        x=generate_sample(2.0,1000.0,1000.0,int(n),int(rid),seed=namespace(int(block)))/1000
        for row in part[part.status.eq('success')].itertuples():
            b,e,g=(row.beta_hat,row.eta_hat/1000,row.gamma_hat/1000)
            method=row.method_variant
            if method.startswith('mmle_'):
                variant=method.split('_')[1].upper();err=float(np.max(np.abs(residuals(x,(b,e,g),variant))))
                assert err<2e-8,(n,block,rid,method,err)
            elif method.startswith('mme_'):
                variant=method.split('_')[1].upper();err=float(np.max(np.abs(residuals(x,(b,e,g),variant,True))))
                assert err<2e-8,(n,block,rid,method,err)
            elif method=='wmle_checked':
                z=x-g;logs=np.log(z);weights=np.exp(b*(logs-logs.max()))
                rr=[get_weight_j2(int(n))/b+logs.mean()-np.dot(weights,logs)/weights.sum(),
                    np.mean(1/z)*weights.sum()/np.sum(weights/z)-get_weight_j3(int(n),b)]
                err=float(np.sum(np.array(rr)**2));assert err<1.0001e-8
                scale=(logsumexp(b*logs)-np.log(n*get_weight_j1(int(n))))/b-np.log(e)
                assert abs(scale)<1e-8
            else:
                logs=np.log(x-g)
                ll=n*np.log(b)-n*b*np.log(e)+(b-1)*logs.sum()-np.exp(b*(logs-np.log(e))).sum()
                info=json.loads(row.extra)['solution_info']
                err=abs(ll-info['log_likelihood'])
                assert err<1e-8 and b>=1 and g>=0,(n,block,rid,method,err,info)
            maxima[method]=max(maxima.get(method,0),err);counts[method]=counts.get(method,0)+1
    failures=data[data.failure_reason.str.startswith('no_root',na=False)]
    ordinary=failures[~failures.method_variant.str.contains('mmle_iii|mmle_iv')]
    # Narrow paired roots were found in the initial implementation. Exhaustively
    # recheck remaining III/IV failures, rather than just two examples per group.
    selected=pd.concat([ordinary.groupby(['method_variant','n'],group_keys=False).head(2),
        failures[failures.method_variant.str.contains('mmle_iii|mmle_iv')]],ignore_index=True)
    probes=[]
    for row in selected.itertuples():
        x=generate_sample(2.0,1000.0,1000.0,int(row.n),int(row.repeat_id),seed=namespace(int(row.block)))/1000
        variant=row.method_variant.split('_')[1].upper()
        if row.method_variant.startswith('mme_'):
            p,diag=fit_mme(tuple(x),1201)[variant]
        elif variant=='I':
            p,diag=prior.fit_cw_i(tuple(x),row.method_variant.endswith('_paper'),769)
        else:
            p,diag=fit_mmle(tuple(x),row.method_variant.endswith('_paper'),769)[variant]
        assert p is None,(row.n,row.block,row.repeat_id,row.method_variant,diag)
        probes.append(dict(n=row.n,block=row.block,repeat_id=row.repeat_id,method=row.method_variant,
                           dense_status=diag['status']))
    result=dict(successful_results_checked=sum(counts.values()),counts=counts,
                maxima=maxima,dense_failure_rechecks=probes,all_passed=True)
    (HERE/'final_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(successful_results_checked=sum(counts.values()),maxima=maxima,
                         dense_failure_rechecks=len(probes),all_passed=True)))

if __name__=='__main__':main()
