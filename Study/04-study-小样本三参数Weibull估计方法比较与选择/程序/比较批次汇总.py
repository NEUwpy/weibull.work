"""首轮成熟汇总流程的通用入口：仅将36条件断言改为配置值，不改指标公式。"""
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
import numpy as np


def finalize(engine):
    OUT, CFG = engine.OUT, engine.CFG
    ROOT, IDS, VARIANTS = engine.ROOT, engine.IDS, engine.VARIANTS
    fingerprints, task_complete, task_path = engine.fingerprints, engine.task_complete, engine.task_path
    digest, dump = engine.digest, engine.dump
    check_status, original_valid = engine.check_status, engine.original_valid
    aggregate_standard_metrics = engine.aggregate_standard_metrics
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
    assert rows_written==CFG['expected_rows'] and len(summaries)==CFG['expected_cells']*len(IDS)
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
    for relative,sha in prepared['historical_files'].items():assert digest(ROOT/relative)==sha,relative
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
