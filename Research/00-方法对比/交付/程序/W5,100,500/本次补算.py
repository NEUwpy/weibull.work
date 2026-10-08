"""Task032: stored samples only; append MMLE and MDM .10/.15; never refit old five methods."""
import hashlib,json,math,os,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def plain(v):
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [plain(x) for x in v]
    if isinstance(v,(float,np.floating)):return float(v) if math.isfinite(v) else None
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.bool_,)):return bool(v)
    return v
def dump(p,obj):
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(plain(obj),ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8');tmp.replace(p)
def main():
    cfg=json.loads((HERE/'config.json').read_text(encoding='utf-8'));deps=HERE/'依赖快照/python'
    assert sha(HERE/'输入原件/results.json')==cfg['source_files']['results.json']
    for rel,digest in cfg['dependency_hashes'].items():assert sha(deps/rel)==digest
    sys.path.insert(0,str(deps))
    from studies.common.runner import run_method
    from studies.common.metrics import check_status
    original=json.loads((HERE/'输入原件/results.json').read_text(encoding='utf-8'))
    samples={(s['n'],s['id']):s for s in original['samples']}
    old={(r['n'],r['id'],r['method_id'],r['delta']):r for r in original['results']}
    assert len(samples)==150 and len(old)==750
    logfile=HERE/'中间数据/新增估计.jsonl';computed={};calls=0;trace_checks=[]
    if logfile.exists():
        for line in logfile.read_text(encoding='utf-8').splitlines():
            r=json.loads(line);key=(r['n'],r['id'],r['method_id'],r['delta']);assert key not in computed;computed[key]=r
    for (n,sid),sample in sorted(samples.items()):
        x=sample['values']
        for method,delta in [('mdm',.10),('mdm',.15),('mmle',None)]:
            key=(n,sid,method,delta)
            if key in computed:continue
            traced=method=='mdm' and delta==.10 and sid==1
            kwargs={'offset':delta,'gamma_steps':240,'trace':traced} if method=='mdm' else {}
            raw=run_method(method,x,variant=f'mdm-delta-{delta:.2f}' if method=='mdm' else method,**kwargs);calls+=1
            trace=raw.pop('trace_data',None)
            trace_check=None
            if traced:
                assert trace is not None
                fresh=sorted([(p['gamma'],p['gradient']) for p in trace['grad_gamma_curve'] if p.get('source')=='trace_grid'],reverse=True)
                source=next(c for c in original['gradient_curves'] if c['n']==n and c['id']==sid)
                saved=sorted([(p['gamma'],p['gradient']) for p in source['points'] if p.get('source')=='trace_grid'],reverse=True)
                assert fresh==saved,(n,sid,'criterion differs from saved grid')
                trace_check=dict(n=n,id=sid,points=len(saved),exact_match=True)
            values=[raw[k] for k in ['beta_hat','eta_hat','gamma_hat']]
            ref=x[1] if method=='mmle' else x[0]
            status=check_status(*values,*cfg['truth'],converged=raw['converged'],sample_min=ref) if all(v is not None for v in values) else 'failure'
            row=plain(dict(n=n,id=sid,delta=delta,**raw,status=status,sample_min_original=x[0],sample_min_support=ref,trace_grid_check=trace_check))
            with logfile.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');f.flush()
            computed[key]=row
        if sid%10==0:print(cfg['combination'],'n',n,'group',sid,'new records',len(computed),flush=True)
    assert len(computed)==450
    methods=[('mdm',.1),('mdm',.15),('mdm',.2),('lse',None),('lre',None),('wmle',None),('mle',None),('mmle',None)]
    rows=[];reused=0;boundary=[]
    for (n,sid),sample in sorted(samples.items()):
        for method,delta in methods:
            key=(n,sid,method,delta);raw=old.get(key,computed.get(key));assert raw is not None
            action='original_estimate_reused' if key in old else 'new_estimate';reused+=key in old
            values=[raw[k] for k in ['beta_hat','eta_hat','gamma_hat']]
            displayed=bool(raw['converged'] and all(isinstance(v,(int,float)) and math.isfinite(v) for v in values))
            row=dict(n=n,id=sid,method_id=method,delta=delta,**{k:raw[k] for k in ['beta_hat','eta_hat','gamma_hat','converged','status']},
              displayed_success=displayed,action=action,original_record=raw,
              sample_min_original=sample['values'][0],sample_min_support=sample['values'][1] if method=='mmle' else sample['values'][0])
            rows.append(row)
            if displayed and raw['status']!='success':boundary.append(dict(n=n,id=sid,method_id=method,delta=delta,status=raw['status']))
    assert len(rows)==1200 and reused==750
    assert all(r['original_record']==old[r['n'],r['id'],r['method_id'],r['delta']] for r in rows if r['action']=='original_estimate_reused')
    matrix=dict(config=cfg,samples=original['samples'],results=rows)
    dump(HERE/'中间数据/matrix.json',matrix)
    dump(HERE/'中间数据/MDM曲线.json',original['gradient_curves'])
    mmle=[r for r in rows if r['method_id']=='mmle']
    support=dict(reference='x2: second smallest retained observation',records=150,converged=sum(r['converged'] for r in mmle),
      status_success=sum(r['status']=='success' for r in mmle),gamma_equals_x1=sum(r['gamma_hat']==r['sample_min_original'] for r in mmle),
      gamma_below_x2=sum(r['gamma_hat'] is not None and r['gamma_hat']<r['sample_min_support'] for r in mmle))
    trace_checks=[r['trace_grid_check'] for r in computed.values() if r.get('trace_grid_check')]
    manifest=dict(combination=cfg['combination'],sample_groups=150,sample_cells=2600,estimates=1200,new_records=450,reused_records=750,
      newly_added_by_method={'MMLE':150,'MDM δ=0.10':150,'MDM δ=0.15':150},resampling_calls=0,old_method_fit_calls=0,
      actual_new_method_calls_this_run=calls,mmle_support=support,display_status_boundary_records=boundary,
      source_json_sha256=sha(HERE/'输入原件/results.json'),source_csv_sha256=sha(HERE/'输入原件/results.csv'),
      matrix_sha256=sha(HERE/'中间数据/matrix.json'),curve_sha256=sha(HERE/'中间数据/MDM曲线.json'),
      dependency_hashes=cfg['dependency_hashes'],trace_grid_checks=trace_checks,script_sha256=sha(Path(__file__)))
    dump(HERE/'中间数据/补算核验.json',manifest)
    checkpoint=os.environ.get('R00_CHECKPOINT_PATH')
    if checkpoint:
        with Path(checkpoint).open('a',encoding='utf-8') as f:f.write('\n'+cfg['combination']+'：150原样本、750复用记录、450新增记录完成；MMLE支撑='+json.dumps(support,ensure_ascii=False)+'；边界展示记录='+str(len(boundary))+'。\n')
    print('CALC_DONE',cfg['combination'],json.dumps(support,ensure_ascii=False),'boundary',len(boundary),flush=True)
if __name__=='__main__':main()
