"""Frozen W2 case integration audit. No performance-based version selection.

Use raw lifespan units, no jitter, no clipping, no resampling. Archived four
methods are read, not rerun; new methods follow their separately audited versions.
"""
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path
import sys
import numpy as np
import scipy
from audit_mps_lm import fit_mps,fit_lm
from audit_sam import fit_sam
from audit_new_original_methods import dmmle

ROOT=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parents[1]/'evidence/common_sample_audit.json'


def parameters(result):
    return np.array([result[k] for k in ['beta','eta','gamma']],dtype=float)


def accepted(r,x,allow_endpoint=False):
    if r.get('status') not in ['estimated','converged']:return False
    if not all(k in r for k in ['beta','eta','gamma']):return False
    b,e,g=parameters(r)
    support=(g<=min(x)) if allow_endpoint else (g<min(x))
    return bool(np.isfinite([b,e,g]).all() and b>0 and e>0 and g>=0 and support)


def metrics(rows,method):
    a=np.array([parameters(r['results'][method]) for r in rows])
    truth=np.array([2.,1000.,1000.]);errors=(a-truth)/[2,1000,1000]
    q= a[:,2]+a[:,1]*(-np.log(.99))**(1/a[:,0])
    qt=1000+1000*np.sqrt(-np.log(.99))
    return {'normalized_bias':errors.mean(axis=0).tolist(),
            'normalized_rmse':np.sqrt((errors**2).mean(axis=0)).tolist(),
            'q01_relative_rmse':float(np.sqrt(np.mean(((q-qt)/qt)**2)))}


def main():
    source=ROOT/'tmp/w2-case-20260921/payload.json'
    raw=source.read_bytes();case=json.loads(raw)['cases'][0]
    recovery_path=DEST.parent/'wmle_case_recovery.json'
    recovery=json.loads(recovery_path.read_text(encoding='utf-8'))
    assert recovery['payload_sha256']==hashlib.sha256(raw).hexdigest()
    recovered={(r['n'],r['sample_id']):r for r in recovery['records']}
    out={'scope':'integration audit on existing W(2,1000,1000) data; not independent validation or method ranking',
         'protocol':{'sample_sizes':[7,15,30],'repetitions_each':50,
                     'units':'original raw time units; no parameter-informed preprocessing',
                     'methods':['LS','LRE','WMLE_archived','WMLE_recovered','MLE_archived','MPS_R09','LM_unconstrained','SAM_initial_only','DMMLE_author_start','DMMLE_budget200'],
                     'acceptance':'original method success plus finite beta,eta>0 and gamma>=0; gamma<=min allowed only because DMMLE defines equality; no clipping',
                     'pairwise_reference':'LRE, chosen before run because it has all archived samples valid',
                     'metrics':'e_beta=(beta_hat-2)/2,e_eta=(eta_hat-1000)/1000,e_gamma=(gamma_hat-1000)/1000; paired common-valid sets only; q01 relative RMSE',
                     'SAM':'absolute increment 1e-5, initial adjustment only; subsequent domain failure recorded',
                     'WMLE_recovered':'archived successes plus three previously independently verified roots; recovery file SHA and original payload identity checked',
                     'DMMLE':'raw alpha,sigma, start(1,1),20 iterations; original observed-information score',
                     'DMMLE_budget200':'diagnostic follow-up after all 20-step runs failed residual gate; same score, start, units, stopping tolerance; increase maximum to 200; no accuracy-based selection'},
         'source':{'path':str(source),'sha256':hashlib.sha256(raw).hexdigest()},
         'wmle_recovery_sha256':hashlib.sha256(recovery_path.read_bytes()).hexdigest(),
         'runtime':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__},
         'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('audit_*.py')},
         'samples':[],'summary':{}}
    for n in [7,15,30]:
        archived=case['results'][str(n)]['0.10']
        for i,x in enumerate(case['samples'][str(n)]):
            row={'n':n,'sample_id':i+1,'data':x,'results':{}}
            for name,old in [('LS','LS'),('LRE','LRE'),('WMLE_archived','WMLM'),('MLE_archived','MLM')]:
                z=archived[i][old];r={'status':'estimated' if z['converged'] else z['status']}
                if z['converged']:r.update(beta=z['shape_hat'],eta=z['scale_hat'],gamma=z['location_hat'])
                row['results'][name]=r
            r=dict(row['results']['WMLE_archived'])
            if (n,i+1) in recovered:
                entry=recovered[n,i+1];assert entry['independent_equation_check']['inside_production_domain']
                assert entry['independent_equation_check']['squared_residual']<=1e-8
                z=entry['recovered'];r={'status':'estimated','beta':z['beta_hat'],'eta':z['eta_hat'],'gamma':z['gamma_hat'],'source':'previously_verified_profile_root'}
            row['results']['WMLE_recovered']=r
            for name,fn in [('MPS_R09',fit_mps),('LM_unconstrained',fit_lm),('SAM_initial_only',fit_sam),('DMMLE_author_start',dmmle),('DMMLE_budget200',lambda x:dmmle(x,maxiter=200))]:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error',RuntimeWarning)
                        r=fn(np.asarray(x,float))
                    if name.startswith('DMMLE') and 'alpha' in r:r['beta']=r['alpha']
                except (ValueError,ArithmeticError,RuntimeWarning,np.linalg.LinAlgError) as exc:
                    r={'status':'numerical_exception','detail':type(exc).__name__+': '+str(exc)}
                row['results'][name]=r
            for name,r in row['results'].items():
                r['accepted']=accepted(r,x,allow_endpoint=name.startswith('DMMLE'))
                if not r['accepted'] and r['status'] in ['estimated','converged']:
                    r['acceptance_reason']='estimate_outside_declared_parameter_or_sample_support_domain'
            out['samples'].append(row)
        rows=[r for r in out['samples'] if r['n']==n];s={}
        for method in out['protocol']['methods']:
            valid=[r for r in rows if r['results'][method]['accepted']]
            pair=[r for r in valid if r['results']['LRE']['accepted']]
            s[method]={'accepted':len(valid),'total':len(rows),
                       'statuses':dict(Counter(r['results'][method]['status'] for r in rows)),
                       'domain_rejections_after_estimation':sum('acceptance_reason' in r['results'][method] for r in rows),
                       'common_with_LRE':len(pair),'common_sample_ids':[r['sample_id'] for r in pair]}
            if pair:s[method].update(method_metrics=metrics(pair,method),LRE_metrics_on_same_samples=metrics(pair,'LRE'))
        out['summary'][str(n)]=s
        print('completed n',n,{m:s[m]['accepted'] for m in s},flush=True)
    DEST.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':main()
