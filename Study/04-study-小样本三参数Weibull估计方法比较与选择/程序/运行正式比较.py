"""Study04: fixed-sample, resumable 36-condition comparison via shared pipeline.

Commands: --prepare; --pilot; --run; --verify. All numerical outputs are local
under the Study04 ignored calculation archive. --verify reads saved results;
it does not finalize an existing batch again. No historical sample is modified.
"""
import os
for _key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[_key]='1'

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import subprocess
from 存储路径 import ARCHIVE, saved_path
import csv
import gzip
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
from scipy.special import logsumexp

ROOT=Path(__file__).resolve().parents[3]
STUDY=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'python'))
from methods import wmle
from methods.conditional_profiles import mle_profile, wmle_residuals
from studies.common.experiment import run_experiment
from studies.common.metrics import aggregate_standard_metrics, check_status
from studies.common.sample import generate_sample

CONFIG_PATH=Path(__file__).with_name('正式比较配置.json')
CFG=json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
OUT=ARCHIVE/CFG['run_id']
METHODS=[(v[0],v[1]) for v in CFG['methods']]
IDS=[m[0] for m in METHODS]
VARIANTS={m[0]:m[1]['variant'] for m in METHODS}
R09=ROOT/'Research/09-Weibull参数估计方法谱系与比较基线/实验'
R05=ROOT/'Research/05-传统估计方法横向比较/artifacts/risk_landscape_v1'
SOURCES=['python/base.py','python/methods/registry.py','python/methods/mle.py',
 'python/methods/wmle.py','python/methods/profile_solvers.py','python/methods/conditional_profiles.py',
 'python/methods/mmle.py','python/methods/lse.py','python/methods/lre.py','python/methods/mdm.py',
 'python/methods/mm.py','python/methods/j3_weights.tsv','python/studies/common/sample.py',
 'python/studies/common/runner.py','python/studies/common/metrics.py','python/studies/common/experiment.py',
 str(Path(__file__).relative_to(ROOT)),str(CONFIG_PATH.relative_to(ROOT)),
 str(Path(__file__).with_name('存储路径.py').relative_to(ROOT))]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def fingerprints():return {p:digest(ROOT/p) for p in SOURCES}


def cell_key(beta,n):return f'b{beta:g}_n{n:02d}'


def cells():
    result=[]
    for beta in sorted(CFG['representative_beta']+CFG['intermediate_beta']):
        representative=beta in CFG['representative_beta']
        for n in CFG['main_n']+([CFG['reference_n']] if representative else []):
            result.append(dict(key=cell_key(beta,n),beta=beta,n=n,
                repeats=CFG['representative_repeats'] if representative else CFG['intermediate_repeats'],
                source='Research09' if representative else 'Research05'))
    return result


def original_valid(method,x,values):
    b,e,g=values
    support=x[1] if method=='mmle' else x[0]
    if (not np.isfinite(values).all() or b<=0 or e<=0 or not 0<=g<support):return False,'support'
    if method=='mmle':
        if g!=x[0]:return False,'minimum_location'
        t=np.log(x[1:]-g);w=np.exp(b*(t-t.max()));w/=w.sum()
        return abs(1/b+t.mean()-w@t)<=1e-5,'shape_equation'
    if method=='wmle':
        a,c=wmle_residuals(x,b,g,wmle)
        t=np.log(x-g)
        expected=np.exp((logsumexp(b*t)-np.log(len(x)*wmle.get_weight_j1(len(x))))/b)
        return bool(b<9.99 and a*a+c*c<=1e-8 and np.isclose(e,expected,rtol=1e-8,atol=1e-8)),'weighted_equations'
    if method=='mle':
        if b<1:return False,'shape_domain'
        d=x-g;z=np.log(d/e);v=np.exp(b*z)
        ub=1+b*(z.mean()-np.mean(v*z));ue=b*(v.mean()-1)
        ug=float(np.mean((b*v-(b-1))/d))
        location=(abs(ug) if g>1e-5 else max(0.,ug))*(x[0]-g)
        if max(abs(ub),abs(ue),location)>1e-5:return False,'score_precision'
        if g>1e-5:
            h=min((x[0]-g)*1e-3,g/2)
            p=mle_profile(x,g);left=mle_profile(x,g-h);right=mle_profile(x,g+h)
            if left['ll']>p['ll']+1e-8 or right['ll']>p['ll']+1e-8:return False,'local_peak'
        return True,'finite_local_likelihood'
    return True,'prior_full_audit'


def cached_result(method,x,values,source,legacy_hash,time_value=None):
    b,e,g=map(float,values)
    info={'status':'ok','reused_verified':True}
    if method=='mmle':info.update(deleted_observations=1,gamma_is_original_sample_minimum=True,effective_sample_min=float(x[1]))
    return dict(method_id=method,beta_hat=b,eta_hat=e,gamma_hat=g,r_squared=0. if method=='mmle' else None,
        converged=True,time=time_value,sample_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
        extra=dict(solution_info=info,provenance=dict(source=source,source_method_sha256=legacy_hash,
            new_solver_applied=False,reuse='verified original estimate; not relabeled as a newly computed value')))


def write_inputs(cell,x,old,available,old_success,cache,source_meta):
    folder=OUT/'inputs'/cell['key'];folder.mkdir(parents=True,exist_ok=True)
    assert x.shape==(cell['repeats'],cell['n']) and np.isfinite(x).all() and (np.diff(x,axis=1)>0).all()
    np.savez_compressed(folder/'samples.npz',samples=x,old_estimates=old,old_available=available,old_success=old_success)
    with gzip.open(folder/'verified_cache.json.gz','wt',encoding='utf-8') as f:json.dump(cache,f,ensure_ascii=False,allow_nan=False)
    dump(folder/'manifest.json',dict(**cell,source_details=source_meta,
         sha256={p.name:digest(p) for p in [folder/'samples.npz',folder/'verified_cache.json.gz']},
         cached_results=len(cache)))


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'prepared.json').exists():
        saved=json.loads((OUT/'prepared.json').read_text(encoding='utf-8'))
        if saved['source_hashes']!=fingerprints():raise RuntimeError('Source changed since preparation; preserve this run and use a distinct run ID')
        return saved
    current=fingerprints();historical={};audit=Counter();grid=cells()
    for relative,sha in current.items():
        target=OUT/'source_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target);assert digest(target)==sha
    for beta in CFG['representative_beta']:
        batch=R09/f'W({beta:g},1000,500)'
        c=json.loads((batch/'程序/config.json').read_text(encoding='utf-8'))
        m=json.loads((batch/'程序/manifest.json').read_text(encoding='utf-8'))
        for item in m['files']:
            if item['path'].startswith('数据/'):
                p=batch/item['path'];assert digest(p)==item['sha256'];historical[str(p.relative_to(ROOT))]=item['sha256']
        s=pd.read_csv(batch/'数据/样本.csv',float_precision='round_trip')
        d=pd.read_csv(batch/'数据/估计明细.csv',float_precision='round_trip')
        for cell in [v for v in grid if v['beta']==beta]:
            n=cell['n'];ss=s[s.n==n].sort_values(['block','repeat_id'])
            x=ss[[f'x({i})' for i in range(1,n+1)]].to_numpy(float)
            for k,row in enumerate(ss.itertuples()):
                seed=c['seed_namespace'] if row.block==0 else f"{c['seed_namespace']}:research09-versions:block{row.block:02d}"
                assert np.array_equal(x[k],generate_sample(*c['truth'],n,int(row.repeat_id),seed=seed))
                assert hashlib.sha256(x[k].tobytes()).hexdigest()==getattr(row,'样本SHA256')
            old=np.full((len(x),7,3),np.nan);available=np.zeros((len(x),7),bool);success=available.copy();cache={}
            for row in d[d.n==n].to_dict('records'):
                method={'MLE':'mle','WMLE':'wmle','MMLE':'mmle','K-R MMLE':'mmle'}[row['方法']]
                rid=int(row['block'])*100+int(row['repeat_id']);j=IDS.index(method)
                available[rid,j]=True;success[rid,j]=row['状态']=='成功'
                if not success[rid,j]:audit[f'{method}:old_failure']+=1;continue
                values=np.array([row[p+'估计'] for p in ['β','η','γ']],float);old[rid,j]=values
                valid,reason=original_valid(method,x[rid],values)
                audit[f'{method}:verified' if valid else f'{method}:rejected_{reason}']+=1
                if valid:
                    legacy=digest(batch/'程序/source_snapshot/python/methods'/f'{method}.py') if method!='mmle' else digest(batch/'程序/compute.py')
                    t=float(row['耗时(秒)']) if pd.notna(row['耗时(秒)']) else None
                    cache[f'{rid}|{method}']=cached_result(method,x[rid],values,'Research09',legacy,t)
            write_inputs(cell,x,old,available,success,cache,dict(batch=str(batch.relative_to(ROOT)),config=c))
            print(f"Prepared {cell['key']}: {len(cache)} verified estimates reused",flush=True)
    audit_path=ARCHIVE/'300次补充结果核查-20261016.json'
    prior=json.loads(audit_path.read_text(encoding='utf-8'))
    for relative,sha in prior['original_files_verified'].items():
        p=ROOT/relative;assert digest(p)==sha;historical[relative]=sha
    r=pd.read_csv(R05/'per_sample_losses.csv.gz',float_precision='round_trip')
    for cell in [v for v in grid if v['source']=='Research05']:
        b,n=cell['beta'],cell['n'];x=np.array([generate_sample(float(b),1000.,500.,n,rid,seed='study01_nrmc_v1') for rid in range(300)])
        old=np.full((len(x),7,3),np.nan);available=np.zeros((len(x),7),bool);success=available.copy();cache={}
        dd=r[r.beta.eq(b)&r.gamma_over_eta.eq(.5)&r.n.eq(n)]
        for row in dd.to_dict('records'):
            method={'MDM-0.1':'mdm','MLE':'mle','WMLE':'wmle','LSE':'lse','LRE':'lre'}[row['method']]
            rid=int(row['repeat_id']);j=IDS.index(method);available[rid,j]=True;success[rid,j]=not row['failed']
            if not success[rid,j]:continue
            values=np.array([row['beta_hat'],row['eta_hat_norm']*1000,row['gamma_hat_norm']*1000]);old[rid,j]=values
            if method not in ['mdm','lse']:continue
            assert original_valid(method,x[rid],values)[0]
            assert digest(ROOT/f'python/methods/{method}.py')==prior['source_identity'][method]['archived_sha256']
            cache[f'{rid}|{method}']=cached_result(method,x[rid],values,'Research05',prior['source_identity'][method]['archived_sha256'])
            audit[f'{method}:verified']+=1
        write_inputs(cell,x,old,available,success,cache,dict(batch=str(R05.relative_to(ROOT)),seed_namespace='study01_nrmc_v1',numeric_types='float beta/eta/gamma; int n/repeat'))
        print(f"Prepared {cell['key']}: {len(cache)} verified estimates reused",flush=True)
    result=dict(run_id=CFG['run_id'],cells=grid,source_hashes=current,historical_files=historical,
        original_result_validation=dict(audit),sample_count=sum(c['repeats'] for c in grid),expected_rows=CFG['expected_rows'],
        prepared_at=datetime.now(timezone.utc).isoformat())
    assert len(grid)==36 and result['sample_count']==28800
    dump(OUT/'prepared.json',result)
    return result


def task_path(key,start):return OUT/'shards'/key/f'{start:04d}'


def task_complete(key,start):
    folder=task_path(key,start);p=folder/'done.json'
    if not p.exists():return False
    saved=json.loads(p.read_text(encoding='utf-8'))
    return all((folder/name).exists() and digest(folder/name)==h for name,h in saved['sha256'].items())


def run_task(job):
    cell,start=job;n=cell['n'];beta=cell['beta'];size=min(CFG['chunk_size'],cell['repeats']-start)
    folder=task_path(cell['key'],start)
    with np.load(OUT/'inputs'/cell['key']/'samples.npz') as pack:x=pack['samples']
    with gzip.open(OUT/'inputs'/cell['key']/'verified_cache.json.gz','rt',encoding='utf-8') as f:cache=json.load(f)
    reused={}
    for rid in range(size):
        for method in IDS:
            prior=cache.get(f'{start+rid}|{method}')
            if prior is not None:reused[(beta,1000.,500.,n,rid,VARIANTS[method])]=prior
    run_experiment(METHODS,[(beta,1000.,500.)],[n],size,str(folder),
        sample_provider=lambda b,e,g,nn,rid:x[start+rid],precomputed_results=reused,
        code_version=CFG['run_id'],run_label=f"{cell['key']}:{start}",boundary_tol=CFG['boundary_tol'])
    temporary=folder/'results.csv.gz.tmp';count=0
    with (folder/'results.csv').open(encoding='utf-8',newline='') as source,gzip.open(temporary,'wt',encoding='utf-8',newline='') as target:
        reader=csv.DictReader(source);writer=csv.DictWriter(target,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            row['repeat_id']=int(row['repeat_id'])+start;writer.writerow(row);count+=1
    assert count==size*7
    temporary.replace(folder/'results.csv.gz')
    raw_path=folder/'results.csv'
    assert raw_path.resolve().is_relative_to(OUT.resolve())
    raw_path.unlink()  # Only the just-written uncompressed working copy.
    m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    m.update(repeat_id_offset=start,sample_pack_sha256=digest(OUT/'inputs'/cell['key']/'samples.npz'))
    dump(folder/'manifest.json',m)
    completed=dict(rows=count,reused=len(reused),computed=count-len(reused),
        sha256={name:digest(folder/name) for name in ['results.csv.gz','summary.json','manifest.json']})
    dump(folder/'done.json',completed)
    return dict(cell=cell['key'],start=start,**completed)


def run(pilot=False):
    prepared=prepare()
    jobs=[(c,start) for c in prepared['cells'] for start in range(0,c['repeats'],CFG['chunk_size'])]
    if pilot:
        keys={cell_key(1.5,7),cell_key(2.5,7)}
        jobs=[(c,s) for c,s in jobs if c['key'] in keys and s==0]
    jobs=[j for j in jobs if not task_complete(j[0]['key'],j[1])]
    print(f'Running {len(jobs)} remaining shards with {CFG["workers"]} workers',flush=True)
    with ProcessPoolExecutor(max_workers=min(CFG['workers'],max(1,len(jobs)))) as pool:
        for i,future in enumerate(as_completed([pool.submit(run_task,j) for j in jobs]),1):
            r=future.result()
            print(f"Completed {i}/{len(jobs)}: {r['cell']} repeats {r['start']}..; reused {r['reused']}, computed {r['computed']}",flush=True)
    if not pilot:finalize()


def finalize():
    prepared=json.loads((OUT/'prepared.json').read_text(encoding='utf-8'))
    if prepared['source_hashes']!=fingerprints():raise RuntimeError('Computation sources changed during the run')
    totals=Counter();summaries={};by_method={};issues=[];rows_written=0
    merged_tmp=OUT/'results.csv.gz.tmp'
    with gzip.open(merged_tmp,'wt',encoding='utf-8',newline='') as merged:
        writer=None
        for cell in prepared['cells']:
            key=cell['key'];size=cell['repeats']
            with np.load(OUT/'inputs'/key/'samples.npz') as pack:
                x=pack['samples'];old_available=pack['old_available'];old_success=pack['old_success']
            rows=[]
            for start in range(0,size,CFG['chunk_size']):
                assert task_complete(key,start),f'Incomplete shard: {key}/{start}'
                with gzip.open(task_path(key,start)/'results.csv.gz','rt',encoding='utf-8',newline='') as f:
                    reader=csv.DictReader(f)
                    if writer is None:writer=csv.DictWriter(merged,fieldnames=reader.fieldnames);writer.writeheader()
                    for raw in reader:
                        writer.writerow(raw);rows_written+=1
                        parsed={p:(float(raw[p]) if raw[p] else None) for p in ['beta_hat','eta_hat','gamma_hat']}
                        row=dict(**parsed,beta=cell['beta'],eta=1000.,gamma=500.,n=cell['n'],
                            repeat_id=int(raw['repeat_id']),method_id=raw['method_id'],method_variant=raw['method_variant'],
                            converged=raw['converged']=='True',status=raw['status'],extra=json.loads(raw['extra']),
                            time=float(raw['time']) if raw['time'] else None,boundary_tol=CFG['boundary_tol'])
                        rows.append(row)
            assert len(rows)==size*7 and len({(r['repeat_id'],r['method_id']) for r in rows})==len(rows)
            for method in IDS:
                rr=[r for r in rows if r['method_id']==method];assert len(rr)==size
                assert {r['repeat_id'] for r in rr}==set(range(size))
                counts=Counter(total=size)
                for row in rr:
                    rid=row['repeat_id'];sample=x[rid];j=IDS.index(method);extra=row['extra'];e=extra['experiment']
                    assert e['sample_sha256']==hashlib.sha256(sample.tobytes()).hexdigest()
                    assert e['boundary_tol']==CFG['boundary_tol']
                    minimum=float(sample[1] if method=='mmle' and row['gamma_hat'] is not None else sample[0])
                    assert e['support_min']==minimum
                    row['sample_min']=minimum
                    b,eta,g=[row[p] for p in ['beta_hat','eta_hat','gamma_hat']]
                    status='failure' if b is None or eta is None or g is None else check_status(b,eta,g,
                        row['beta'],1000.,500.,converged=row['converged'],sample_min=minimum,boundary_tol=0.)
                    assert status==row['status']
                    counts['reused' if e['result_origin']=='precomputed' else 'computed']+=1
                    counts[status]+=1
                    if status=='success':
                        assert g>=0
                        if method in ['mle','wmle','mmle']:
                            ok,reason=original_valid(method,sample,np.array([b,eta,g]))
                            if not ok:issues.append(dict(cell=key,method=method,repeat_id=rid,reason=reason))
                        counts['shape_anomaly']+=int(b>=3*cell['beta'] or b<=cell['beta']/3)
                        if old_available[rid,j] and not old_success[rid,j]:counts['old_failure_recovered']+=1
                    if old_available[rid,j]:
                        counts['old_success' if old_success[rid,j] else 'old_failure']+=1
                    info=extra.get('solution_info') or {}
                    counts['boundary_approximation']+=int(bool(info.get('approximate_boundary_root')))
                metrics=aggregate_standard_metrics(rr)
                assert metrics['n_total']==counts['total'] and metrics['n_valid']==counts['success']
                summaries[f'{key}|{VARIANTS[method]}']=dict(beta=cell['beta'],eta=1000.,gamma=500.,n=cell['n'],
                    source=cell['source'],method_id=method,method_variant=VARIANTS[method],**metrics,
                    provenance_counts=dict(counts),shape_anomaly=dict(count=counts['shape_anomaly'],valid=counts['success'],
                        rate=counts['shape_anomaly']/counts['success'] if counts['success'] else None))
                for name,value in counts.items():totals[name]+=value
                bucket=by_method.setdefault(method,Counter());bucket.update(counts)
            print(f'Verified {key}: {len(rows)} result rows',flush=True)
    assert rows_written==CFG['expected_rows'] and len(summaries)==36*7
    dump(OUT/'verification.json',dict(rows=rows_written,checked_groups=len(summaries),
        numeric_issues=issues,totals=dict(totals),by_method={k:dict(v) for k,v in by_method.items()}))
    if issues:raise RuntimeError(f'{len(issues)} numerical checks need review; see verification.json')
    merged_tmp.replace(OUT/'results.csv.gz')
    dump(OUT/'summary.json',summaries)
    fieldnames=['beta','eta','gamma','n','method','total','success','failure','reused','computed','shape_anomaly_rate']
    fieldnames += [f'{p}_{metric}' for p in ['beta','eta','gamma'] for metric in ['bias','sd','rmse','mae']]
    with (OUT/'条件汇总.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader()
        for group in summaries.values():
            record={k:group[k] for k in ['beta','eta','gamma','n']}
            record.update(method=group['method_variant'],shape_anomaly_rate=group['shape_anomaly']['rate'])
            record.update({k:group['provenance_counts'].get(k,0) for k in ['total','success','failure','reused','computed']})
            for p in ['beta','eta','gamma']:
                stats=group.get('param_standard',{}).get(p,{}).get('absolute',{})
                record.update({f'{p}_{m}':stats.get(m) for m in ['bias','sd','rmse','mae']})
            writer.writerow(record)
    for relative,sha in prepared['historical_files'].items():assert digest(saved_path(relative))==sha,relative
    assert prepared['source_hashes']==fingerprints()
    manifest=dict(run_id=CFG['run_id'],status='complete',completed_at=datetime.now(timezone.utc).isoformat(),
        config=CFG,cells=prepared['cells'],source_hashes=prepared['source_hashes'],
        historical_files=prepared['historical_files'],original_result_validation=prepared['original_result_validation'],
        totals=dict(totals),by_method={k:dict(v) for k,v in by_method.items()},
        sd='shared sample SD, ddof=1',support='strict gamma<retained_min; K-R MMLE deletes original minimum',
        runtime='archived runtimes and missing old runtimes are not used to compare computational speed',
        file_sha256={name:digest(OUT/name) for name in ['results.csv.gz','summary.json','条件汇总.csv','verification.json']})
    dump(OUT/'manifest.json',manifest)
    print(json.dumps(dict(status='complete',totals=dict(totals),by_method=manifest['by_method']),ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    for name in ['prepare','pilot','run','verify']:action.add_argument('--'+name,action='store_true')
    args=parser.parse_args()
    if args.prepare:prepare()
    elif args.pilot:run(pilot=True)
    elif args.run:run()
    else:subprocess.run([sys.executable, str(Path(__file__).with_name('核对正式汇总.py')), '--batch', CFG['run_id']], check=True)
