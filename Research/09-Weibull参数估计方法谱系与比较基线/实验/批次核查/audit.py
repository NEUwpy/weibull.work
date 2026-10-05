"""Read-only audit of three parameter batches; outputs are outside all batches."""
import argparse
import ast
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BATCHES = {'A': ROOT/'W(2,1000,1000)', 'B': ROOT/'W(2,1000,500)', 'C': ROOT/'W(2,100,500)'}
TRUTHS = {'A': [2.,1000.,1000.], 'B': [2.,1000.,500.], 'C': [2.,100.,500.]}
METHODS = ['MLE','MMLE','WMLE']
SIZES = [7,10,15,20,50]
PARAMS = ['beta','eta','gamma']
SYMBOLS = ['β','η','γ']
RNG_SEED = 2026100516
RTOL, ATOL = 1e-7, 1e-7

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_csv(name, rows):
    pd.DataFrame(rows).to_csv(HERE/name, index=False, encoding='utf-8-sig')

def save_json(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def mmle_profile_root(x):
    """Independent score-root check of the same modified likelihood, not Eq11 iteration."""
    z = x[1:]-x[0]
    logs = np.log(z)
    def score(beta):
        w = np.exp(beta*(logs-logs.max()))
        w /= w.sum()
        return 1/beta + logs.mean() - w@logs
    upper = 1.
    while score(upper)>0:
        upper *= 2
    beta = brentq(score, 1e-10, upper, xtol=1e-13, rtol=1e-13)
    eta = float(np.exp((logsumexp(beta*logs)-np.log(len(z)))/beta))
    return dict(beta=float(beta), eta=eta, gamma=float(x[0])), float(score(beta))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot-output', type=Path, required=True)
    args = parser.parse_args()
    plot_root = args.plot_output.resolve()
    assert not any(plot_root.is_relative_to(batch.resolve()) for batch in BATCHES.values())
    guard = {str(p): sha(p) for batch in BATCHES.values() for p in batch.rglob('*') if p.is_file()}
    save_json('三批输入保护.json', guard)
    old_guard = json.loads((ROOT/'两批真值比较/输入保护.json').read_text(encoding='utf-8'))
    assert len(old_guard)==96 and all(sha(p)==digest for p,digest in old_guard.items())
    # All frozen science sources must agree before any direct recalculation.
    frozen = BATCHES['A']/'程序/source_snapshot'
    for p in frozen.rglob('*'):
        if p.is_file():
            assert all(sha(p)==sha(batch/'程序/source_snapshot'/p.relative_to(frozen)) for batch in BATCHES.values())
    sys.path.insert(0,str(frozen/'python'))
    sys.path.insert(0,str(frozen))
    from studies.common.sample import generate_sample
    from paper_solver import solve
    configs, manifests, detail, samples = {}, {}, {}, {}
    configuration, sample_stats, hashes, normalized, refits, axes, pairs, pixel_comparisons = [], [], [], [], [], [], [], []
    arrays = {}
    for key,batch in BATCHES.items():
        cfg = json.loads((batch/'程序/config.json').read_text(encoding='utf-8'))
        manifest = json.loads((batch/'程序/manifest.json').read_text(encoding='utf-8'))
        assert cfg['truth']==manifest['truth']==TRUTHS[key] and cfg['n']==SIZES and cfg['blocks']*cfg['repeats']==1200
        assert cfg['initial_shape']==1 and cfg['shape_absolute_step_tolerance']==1e-8 and cfg['max_iterations']==10000
        assert not cfg['firth'] and not cfg['extra_shape_or_location_caps'] and not cfg['recovery']
        configs[key], manifests[key] = cfg,manifest
        configuration.append(dict(batch=key, folder=batch.name, beta=cfg['truth'][0], eta=cfg['truth'][1], gamma=cfg['truth'][2],
                                  n=','.join(map(str,cfg['n'])),groups_per_n=1200,groups=6000,estimates=18000,
                                  config_task=cfg['task_id'],manifest_task=manifest['latest_task'],solver=cfg['solver'],
                                  frozen_solver_sha256=sha(batch/'程序/source_snapshot/paper_solver.py')))
        detail[key] = pd.read_csv(batch/'结果/估计明细.csv',float_precision='round_trip')
        samples[key] = pd.read_csv(batch/'结果/样本.csv',float_precision='round_trip')
        data,samp = detail[key],samples[key]
        assert len(data)==18000 and len(samp)==6000
        assert set(data['方法'])==set(METHODS)
        assert not data.duplicated(['n','组号','方法']).any()
        for symbol,truth in zip(SYMBOLS,cfg['truth']):
            assert set(data[symbol+'真值'])=={truth}
        arrays[key]={}
        for n in SIZES:
            s = samp[samp.n==n].sort_values('组号')
            assert s['组号'].tolist()==list(range(1,1201))
            x = s[[f'x({i})' for i in range(1,n+1)]].to_numpy()
            assert np.all(np.diff(x,axis=1)>=0) and (x>cfg['truth'][2]).all()
            arrays[key][n] = x
            for row in s.itertuples(index=False,name=None):
                # The first seven columns are n, ID, group, block, repeat, namespace, SHA.
                n0,identity,group,block,repeat,namespace,digest = row[:7]
                observed = x[group-1]
                generated = generate_sample(*cfg['truth'],n,repeat,seed=namespace)
                assert np.array_equal(observed,generated)
                assert hashlib.sha256(observed.tobytes()).hexdigest()==digest
            minimum=x[:,0];med=np.median(x,axis=1);means=x.mean(axis=1)
            sample_stats.append(dict(batch=key,n=n,groups=1200,mean_sample_min=float(minimum.mean()),
                                     mean_sample_median=float(med.mean()),mean_sample_mean=float(means.mean()),
                                     normalized_min=float(((minimum-cfg['truth'][2])/cfg['truth'][1]).mean()),
                                     normalized_mean=float(((means-cfg['truth'][2])/cfg['truth'][1]).mean())))
            for method in METHODS:
                rows=data[(data.n==n)&(data['方法']==method)].sort_values('组号')
                assert len(rows)==1200 and rows['组号'].tolist()==list(range(1,1201))
                assert rows['样本SHA256'].tolist()==s['样本SHA256'].tolist()
                valid=rows[rows['状态'].eq('成功')]
                for j,(parameter,symbol,truth) in enumerate(zip(PARAMS,SYMBOLS,cfg['truth'])):
                    e=valid[symbol+'估计'].to_numpy()-truth
                    normalized.append(dict(batch=key,method=method,n=n,parameter=parameter,success=len(valid),
                                           success_rate=len(valid)/1200,relative_bias=float(e.mean()/truth),
                                           relative_sd=float(e.std(ddof=0)/truth),relative_rmse=float(np.sqrt(np.mean(e*e))/truth),
                                           common_eta_bias=float(e.mean()/cfg['truth'][1]) if j else float(e.mean()/truth),
                                           common_eta_rmse=float(np.sqrt(np.mean(e*e))/cfg['truth'][1]) if j else float(np.sqrt(np.mean(e*e))/truth)))
        for filename in ['样本.csv','估计明细.csv','三方法汇总.csv','01_估计分布小提琴.png','02_有解率.png','03_RMSE_Bias_SD九格.png']:
            p=batch/'结果'/filename
            hashes.append(dict(batch=key,file=filename,bytes=p.stat().st_size,sha256=sha(p),path=str(p)))
        # Source-level axis facts are cross-checked against actual re-render metadata below.
        text=(batch/'程序/draw.py').read_text(encoding='utf-8')
        metrics=next(ast.literal_eval(node.value) for node in ast.walk(ast.parse(text)) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='metric_limits' for t in node.targets))
        source_lines={name:next(i for i,line in enumerate(text.splitlines(),1) if pattern in line) for name,pattern in [('data','raw=SOURCE/'),('summary','stats=pd.read_csv'),('truth','PARAMS='),('metric_limits','metric_limits='),('x','ax.set_xlim(5,52)'),('rate_y','ax.set_ylim(0,1.03)')]}
        axes.append(dict(batch=key,violin={'beta':[0,10],'eta':[0,200] if key=='C' else [0,2000],
                                         'gamma':[400,600] if key=='C' else [0,2000]},
                         metric_limits=metrics,rate_x=[5,52],rate_y=[0,1.03],truth_line=cfg['truth'],
                         lines=source_lines,script=str(batch/'程序/draw.py'),
                         data_source=str(batch/'结果/估计明细.csv'),summary_source=str(batch/'结果/三方法汇总.csv')))
    # A fixed random seed chooses three groups from all 1200 in n=7,15,50 per batch.
    rng=np.random.default_rng(RNG_SEED)
    for key,batch in BATCHES.items():
        for n in [7,15,50]:
            group=int(rng.integers(1,1201));x=arrays[key][n][group-1]
            for method in METHODS:
                row=detail[key][(detail[key].n==n)&(detail[key]['组号']==group)&(detail[key]['方法']==method)].iloc[0]
                score=None
                if method=='MMLE':
                    fit,score=mmle_profile_root(x)
                    status='success';reason=''
                else:
                    answer=solve(x,method)
                    fit=answer['estimate'];status='success' if fit is not None else 'failure';reason=answer['status']
                stored_status='success' if row['状态']=='成功' else 'failure'
                assert status==stored_status
                r=dict(batch=key,n=n,group=group,method=method,stored_status=stored_status,recomputed_status=status,
                       recompute_reason=reason,rtol=RTOL,atol=ATOL,MMLE_profile_score=score)
                for parameter,symbol in zip(PARAMS,SYMBOLS):
                    observed=row[symbol+'估计'];value=None if fit is None else fit[parameter]
                    r['stored_'+parameter]=None if pd.isna(observed) else float(observed)
                    r['recomputed_'+parameter]=value
                    r['difference_'+parameter]=None if value is None or pd.isna(observed) else float(value-observed)
                    if status=='success':
                        assert np.isclose(value,observed,rtol=RTOL,atol=ATOL),(key,n,group,method,parameter,value,observed)
                    else:
                        assert pd.isna(observed)
                refits.append(r)
    # Compare values and scatter sets, not only filename labels or PNG backgrounds.
    for ka,kb in [('A','B'),('A','C'),('B','C')]:
        identical_raw_groups=0;identical_normalized_groups=0;equal_scatter_sets=0;checked_scatter_sets=0
        for n in SIZES:
            xa,xb=arrays[ka][n],arrays[kb][n]
            identical_raw_groups+=int(np.all(xa==xb,axis=1).sum())
            za=(xa-TRUTHS[ka][2])/TRUTHS[ka][1];zb=(xb-TRUTHS[kb][2])/TRUTHS[kb][1]
            identical_normalized_groups+=int(np.all(np.isclose(za,zb,rtol=0,atol=1e-12),axis=1).sum())
            for method in METHODS:
                a=detail[ka][(detail[ka].n==n)&detail[ka]['方法'].eq(method)&detail[ka]['状态'].eq('成功')]
                b=detail[kb][(detail[kb].n==n)&detail[kb]['方法'].eq(method)&detail[kb]['状态'].eq('成功')]
                for symbol in SYMBOLS:
                    va=np.sort(a[symbol+'估计'].to_numpy());vb=np.sort(b[symbol+'估计'].to_numpy())
                    equal_scatter_sets+=int(va.shape==vb.shape and np.allclose(va,vb,rtol=0,atol=1e-12))
                    checked_scatter_sets+=1
        pairs.append(dict(pair=ka+'/'+kb,identical_raw_groups=identical_raw_groups,identical_normalized_groups=identical_normalized_groups,
                          identical_successful_scatter_sets=equal_scatter_sets,checked_scatter_sets=checked_scatter_sets))
    # Re-render each batch from its adjacent CSVs, always to an external audit folder.
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONIOENCODING':'utf-8'}
    from PIL import Image
    for key,batch in BATCHES.items():
        out=plot_root/key
        run=subprocess.run([sys.executable,'-B',str(batch/'程序/draw.py'),'--output',str(out)],env=env,capture_output=True,text=True,encoding='utf-8')
        assert run.returncode==0,(key,run.stdout,run.stderr)
        audit=json.loads((out/'.运行记录/绘图核验.json').read_text(encoding='utf-8'))
        assert audit['source_sha256']==sha(batch/'结果/估计明细.csv')
        for p in PARAMS:
            assert all(r['x_limits']==axes[['A','B','C'].index(key)]['violin'][p] for r in audit['records'] if r['parameter']==p)
        for filename in ['01_估计分布小提琴.png','02_有解率.png','03_RMSE_Bias_SD九格.png']:
            original=batch/'结果'/filename;recreated=out/filename
            im=np.asarray(Image.open(original));im2=np.asarray(Image.open(recreated))
            same_pixels=bool(im.shape==im2.shape and np.array_equal(im,im2))
            pixel_comparisons.append(dict(batch=key,file=filename,original_sha256=sha(original),rerendered_sha256=sha(recreated),
                                          bytes_equal=sha(original)==sha(recreated),pixels_equal=same_pixels,width=im.shape[1],height=im.shape[0]))
            assert same_pixels,(key,filename)
        print(json.dumps(dict(batch=key,inputs_regenerated=6000,estimates_recomputed=9,plots_rerendered=3)),flush=True)
    assert len({r['sha256'] for r in hashes if r['file'].endswith('.png')})==9
    assert all(all(len({r['sha256'] for r in hashes if r['file']==name and r['batch'] in pair})==2 for name in ['样本.csv','估计明细.csv']) for pair in [('A','B'),('A','C'),('B','C')])
    current_files={str(p) for batch in BATCHES.values() for p in batch.rglob('*') if p.is_file()}
    assert current_files==set(guard) and all(sha(p)==digest for p,digest in guard.items())
    write_csv('配置核对.csv',configuration)
    write_csv('样本批次统计.csv',sample_stats)
    write_csv('文件SHA256.csv',hashes)
    write_csv('无量纲指标.csv',normalized)
    write_csv('抽组重算核对.csv',refits)
    write_csv('跨批样本与散点复核.csv',pairs)
    write_csv('九图复绘核对.csv',pixel_comparisons)
    save_json('坐标与数据来源.json',axes)
    summary=dict(truths=TRUTHS,groups_regenerated=18000,raw_sample_observations=367200,configuration_truths_verified=3,
                 estimate_truth_rows_verified=54000,random_seed=RNG_SEED,random_groups=9,method_refits=27,
                 successful_refits=sum(r['recomputed_status']=='success' for r in refits),refit_rtol=RTOL,refit_atol=ATOL,
                 input_file_hashes=len(hashes),unique_PNG_sha256=9,rerendered_plots=9,pixel_identical_to_adjacent_data=sum(r['pixels_equal'] for r in pixel_comparisons),
                 same_bytes_as_rerendered=sum(r['bytes_equal'] for r in pixel_comparisons),protected_files_unchanged=len(guard),
                 preceding_96_file_guard_passed=True,frozen_method_and_shared_sources_identical=True,
                 detected_batch_or_plot_source_errors=[],comparison_pairs=pairs,plot_audit_directory=str(plot_root))
    save_json('核验摘要.json',summary)
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    main()
