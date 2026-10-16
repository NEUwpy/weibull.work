"""Read-only validation of the fixed-location/scale slice of Research05.

Rebuild observations from the frozen generator/seed; check all stored results
and replay a small, predetermined subset. No historical file is rewritten.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import types

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
from methods import wmle
from methods.lse import log_weibull_order_stat_means
from studies.common.sample import generate_sample
from studies.common.runner import run_method
from 验证求解修订 import likelihood

R05 = ROOT/'Research/05-传统估计方法横向比较/artifacts/risk_landscape_v1'
SHARED = ROOT/'Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E5_normalized_raw/shared_data'
BETAS = [1.5, 2., 2.5, 3., 3.5, 4., 4.5, 5.]
NS = [7, 10, 15, 20]
KEYS = ['beta', 'n', 'repeat_id']


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def sample(beta, n, repeat):
    # Numeric types are part of the frozen seed key.
    return generate_sample(float(beta), 1000., 500., int(n), int(repeat), seed='study01_nrmc_v1')


def replay(job):
    beta, n, repeat, method, old, old_success = job
    x = sample(beta, n, repeat)
    result = (run_method('mdm', x, offset=.1) if method == 'MDM-0.1'
              else run_method(method.lower(), x))
    record = dict(beta=beta, n=n, repeat_id=repeat, method=method,
                  old_success=old_success, new_success=result['converged'])
    if result['converged']:
        values = [result[p+'_hat'] for p in ['beta', 'eta', 'gamma']]
        record.update(new_estimate=values, old_estimate=old,
                      parameters_match=bool(old_success and np.allclose(values, old, rtol=1e-6, atol=1e-5)))
        if method == 'MLE' and old_success:
            record['log_likelihood_gain'] = likelihood(x,*values)-likelihood(x,*old)
    else:
        record['failure'] = result['extra']
    return record


def main():
    manifest = json.loads((R05/'manifest.json').read_text(encoding='utf-8'))
    verified = {}
    for name, expected in manifest['output_hashes'].items():
        assert digest(R05/name) == expected, name
        verified[str((R05/name).relative_to(ROOT))] = expected
    for key, relative in [('mc_scan_raw', SHARED/'mc_scan_raw.csv'),
                          ('mc_manifest', SHARED/'manifest.json'),
                          ('mc_data_sha256sums', SHARED/'data_sha256sums.txt')]:
        assert digest(relative) == manifest['input_hashes'][key], key
        verified[str(relative.relative_to(ROOT))] = digest(relative)
    source_identity = {}
    for name in ['mdm', 'mle', 'wmle', 'lse', 'lre', 'sample']:
        relative = f'python/methods/{name}.py' if name != 'sample' else 'python/studies/common/sample.py'
        source = subprocess.run(['git', 'show', f"{manifest['git_head']}:{relative}"],
                                cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout
        crlf = source.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        assert manifest['input_hashes'][name] in [hashlib.sha256(v).hexdigest() for v in [source, crlf]], name
        source_identity[name] = dict(archived_sha256=manifest['input_hashes'][name],
                                     current_sha256=digest(ROOT/relative),
                                     same_bytes=digest(ROOT/relative) == manifest['input_hashes'][name])
        if name == 'wmle':
            frozen_weights = types.ModuleType('r05_frozen_weights')
            frozen_weights.__file__ = str(ROOT/relative)
            exec(compile(source.decode('utf-8'), str(ROOT/relative), 'exec'), frozen_weights.__dict__)
    weight_blob = subprocess.run(['git', 'show', f"{manifest['git_head']}:python/methods/j3_weights.tsv"],
                                 cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout
    assert (ROOT/'python/methods/j3_weights.tsv').read_bytes().replace(b'\r\n', b'\n') == weight_blob.replace(b'\r\n', b'\n')
    raw = pd.read_csv(R05/'per_sample_losses.csv.gz', float_precision='round_trip')
    raw = raw[raw.gamma_over_eta == .5].copy()
    assert len(raw) == 48000 and not raw.duplicated(KEYS+['method']).any()
    assert raw.groupby(KEYS).size().eq(5).all()
    assert raw.groupby(['beta','n','method']).size().eq(300).all()
    assert set(raw.beta) == set(BETAS) and set(raw.n) == set(NS)
    natural = ((raw.beta_hat-raw.beta)/raw.beta)**2 + (raw.eta_hat_norm-1)**2 + (raw.gamma_hat_norm-.5)**2
    assert np.allclose(raw.loc[~raw.failed, 'loss_natural_zero'], natural[~raw.failed], rtol=1e-11, atol=1e-12)
    assert raw.loc[raw.failed, ['beta_hat','eta_hat_norm','gamma_hat_norm']].eq(0).all().all()
    assert raw.loc[raw.failed,'loss_primary'].eq(3).all()
    assert np.allclose(raw.loc[~raw.failed,'loss_primary'], natural[~raw.failed], rtol=1e-11, atol=1e-12)
    summary = pd.read_csv(R05/'cell_summary.csv', float_precision='round_trip')
    summary = summary[summary.gamma_over_eta == .5].set_index(['beta','n','method'])
    for key, group in raw.groupby(['beta','n','method']):
        saved = summary.loc[key]
        assert np.isclose(group.loss_primary.mean(), saved.mean_loss_primary, atol=1e-11)
        assert np.isclose(np.sqrt(group.loss_primary.mean()), saved.J1_primary, atol=1e-11)
        assert np.isclose(group.failed.mean(), saved.failure_rate, atol=1e-12)
        assert saved.n_samples == 300
    parts = []
    for chunk in pd.read_csv(SHARED/'mc_scan_raw.csv', chunksize=150000, float_precision='round_trip'):
        selected = chunk[np.isclose(chunk.delta,.1) & chunk.gamma_over_eta.eq(.5)]
        if len(selected):
            parts.append(selected)
    mdm = pd.concat(parts).set_index(KEYS).sort_index()
    saved_mdm = raw[raw.method == 'MDM-0.1'].set_index(KEYS).sort_index()
    assert len(mdm) == 9600 and mdm.index.equals(saved_mdm.index)
    assert mdm.eta.eq(1000).all() and mdm.gamma.eq(500).all()
    assert np.allclose(mdm[['beta_hat','eta_hat','gamma_hat']].to_numpy() / [1,1000,1000],
                       saved_mdm[['beta_hat','eta_hat_norm','gamma_hat_norm']].to_numpy(), rtol=1e-11, atol=1e-12)

    counts = {m:dict(total=9600, stored_success=int((~g.failed).sum()), support_invalid=0)
              for m,g in raw.groupby('method')}
    counts['MLE'].update(stationary_check_pass=0, stationary_check_fail=0, stationary_loose_1e3_pass=0, maximum_score_error=0.)
    counts['WMLE'].update(equation_check_pass=0, equation_check_fail=0, scale_check_fail=0, weight_mismatches=0,
                         maximum_squared_residual=0.)
    counts['LSE'].update(regression_check_fail=0)
    selected_mdm_checks = []
    hashes = hashlib.sha256()
    for (beta,n), cell in raw.groupby(['beta','n']):
        samples = np.array([sample(beta,n,r) for r in range(300)])
        hashes.update(samples.tobytes())
        x = samples/1000.
        for method, group in cell.groupby('method'):
            group = group.sort_values('repeat_id')
            good = ~group.failed.to_numpy()
            b,e,g = group[['beta_hat','eta_hat_norm','gamma_hat_norm']].to_numpy().T
            support = (b>0)&(e>0)&(g>=0)&(g<x[:,0])&np.isfinite(b+e+g)
            counts[method]['support_invalid'] += int((good&~support).sum())
            valid = good&support
            for index in np.flatnonzero(valid):
                d = x[index]-g[index]
                t = np.log(d)
                power = np.exp(b[index]*(t-t.max()))
                if method == 'WMLE':
                    a = frozen_weights.get_weight_j2(int(n))/b[index] + t.mean() - np.sum(power*t)/power.sum()
                    ratio = np.exp(t.max())*power.sum()/np.exp((b[index]-1)*(t-t.max())).sum()
                    old_j3 = frozen_weights.get_weight_j3(int(n),float(b[index]))
                    c = np.mean(1/d)*ratio-old_j3
                    residual = a*a+c*c
                    passed = residual <= 1e-8 and b[index]<9.99
                    counts[method]['equation_check_pass' if passed else 'equation_check_fail'] += 1
                    counts[method]['maximum_squared_residual'] = max(counts[method]['maximum_squared_residual'],float(residual))
                    if old_j3 != wmle.get_weight_j3(int(n),float(b[index])):
                        counts[method]['weight_mismatches'] += 1
                    scale = np.exp(t.max())*(power.mean()/frozen_weights.get_weight_j1(int(n)))**(1/b[index])
                    counts[method]['scale_check_fail'] += int(not np.isclose(scale,e[index],rtol=1e-8,atol=1e-10))
                elif method == 'MLE':
                    logz = t-np.log(e[index]); v=np.exp(b[index]*logz)
                    ub = 1+b[index]*(logz.mean()-np.mean(v*logz))
                    ue = b[index]*(v.mean()-1)
                    ug = np.mean((b[index]*v-(b[index]-1))/d)
                    location_error = (abs(ug) if g[index]>1e-6 else max(0.,ug))*(x[index,0]-g[index])
                    score_error = max(abs(ub),abs(ue),location_error)
                    passed = b[index]>=1 and score_error<=1e-5
                    counts[method]['stationary_check_pass' if passed else 'stationary_check_fail'] += 1
                    counts[method]['stationary_loose_1e3_pass'] += int(b[index]>=1 and score_error<=1e-3)
                    counts[method]['maximum_score_error'] = max(counts[method]['maximum_score_error'],float(score_error))
                elif method == 'LSE':
                    reference = log_weibull_order_stat_means(int(n))
                    slope = np.sum((reference-reference.mean())*(t-t.mean()))/np.sum((reference-reference.mean())**2)
                    values = [1/slope,np.exp(t.mean()-slope*reference.mean())]
                    counts[method]['regression_check_fail'] += int(not np.allclose(values,[b[index],e[index]],rtol=1e-8,atol=1e-10))
        # Same methods and a predetermined three repeats across the full grid.
        for repeat in [0,149,299]:
            for method in ['MDM-0.1','LSE','MLE','WMLE']:
                row=cell[(cell.repeat_id==repeat)&(cell.method==method)].iloc[0]
                selected_mdm_checks.append((float(beta),int(n),repeat,method,
                        [float(row.beta_hat),float(row.eta_hat_norm*1000),float(row.gamma_hat_norm*1000)],not bool(row.failed)))
    print('All 9600 deterministic sample groups and 48000 stored estimates checked',flush=True)
    replays=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(replay,j) for j in selected_mdm_checks]):
            replays.append(future.result())
            if len(replays)%96==0:print(f'Replayed {len(replays)}/{len(selected_mdm_checks)} checks',flush=True)
    replay_summary={}
    for method in ['MDM-0.1','LSE','MLE','WMLE']:
        rr=[r for r in replays if r['method']==method]
        replay_summary[method]=dict(checked=len(rr),old_success=sum(r['old_success'] for r in rr),
             new_success=sum(r['new_success'] for r in rr),matching_parameters=sum(r.get('parameters_match',False) for r in rr))
        if method == 'MLE':
            gains=[r['log_likelihood_gain'] for r in rr if 'log_likelihood_gain' in r]
            replay_summary[method].update(maximum_log_likelihood_gain=max(gains),
                 minimum_log_likelihood_gain=min(gains), likelihood_gains_over_1e6=sum(v>1e-6 for v in gains))
    report=dict(scope='Fixed eta=1000 and gamma=500 only; 32 conditions, 300 repeats each',
                deterministic_sample_groups=9600, rebuilt_sample_sha256=hashes.hexdigest(),
                stored_estimates_checked=48000, cell_summary_values_checked=640,
                original_files_verified=verified, source_identity=source_identity,
                mdm_original_rows_matched=9600, checks=counts, replay_summary=replay_summary,
                current_source_hashes={p:digest(ROOT/p) for p in ['python/methods/mdm.py','python/methods/lse.py',
                      'python/methods/mle.py','python/methods/wmle.py','python/methods/profile_solvers.py',
                      'python/methods/conditional_profiles.py','python/methods/j3_weights.tsv',
                      'python/studies/common/sample.py','python/studies/common/runner.py']},
                replays=sorted(replays,key=lambda r:(r['method'],r['beta'],r['n'],r['repeat_id'])),
                sample_boundary='Observations rebuilt from byte-matched generator, original namespace and exact parameter types; historical sample values were not stored in R05 raw result table',
                reuse_boundary='Use per-method masks and version checks, not the old failure-penalized selection score as parameter accuracy')
    out=STUDY/'结果/300次补充结果核查-20261016.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(checks=counts,replays=replay_summary),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
