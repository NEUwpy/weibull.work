"""Recompute all 6000 fits without overwriting deliveries; paired historical LRE audit."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '结果/复核与LRE对比'
PROGRAM = ROOT / '程序'
METHODS = ['mdm', 'lse', 'lre', 'wmle', 'mle']
KEYS = ['beta_hat', 'eta_hat', 'gamma_hat', 'r_squared']
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[name] = '1'


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def close(a, b, rtol=1e-6, atol=1e-5):
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)


def load_class(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LRE


def formula_checks(x, row):
    """Independent arithmetic from displayed formulas; no calls to method fit helpers."""
    n = len(x)
    b, e, g = (row[k] for k in KEYS[:3])
    rank = (np.arange(1, n + 1) - .3) / (n + .4)
    if row['method_id'] == 'lre':
        i = np.arange(1, n + 1)
        rank = (i - 3/8) / (n + 1/4) if n <= 10 else (i - .5) / n
    y = np.log(-np.log1p(-rank))
    z = np.log(x - g)
    predicted = b * (z - np.log(e))
    r2 = 1 - np.sum((y - predicted)**2) / np.sum((y - y.mean())**2)
    out = {'r2_absolute_error': abs(float(r2) - row['r_squared'])}
    if row['method_id'] == 'lre':
        slope = np.dot(z-z.mean(), y-y.mean()) / np.dot(z-z.mean(), z-z.mean())
        scale = np.exp(z.mean() - y.mean()/slope)
        out['beta_relative_error'] = abs(slope/b-1)
        out['eta_relative_error'] = abs(scale/e-1)
    if row['method_id'] == 'mdm':
        pseudo_scales = (x-g) / (-np.log1p(-rank))**(1/b)
        out['eta_relative_error'] = abs(float(pseudo_scales.mean())/e-1)
    if row['method_id'] == 'lse':
        from methods.lse import log_weibull_order_stat_means
        score = log_weibull_order_stat_means(n)
        slope = np.dot(score-score.mean(), z-z.mean())/np.dot(score-score.mean(), score-score.mean())
        out['beta_relative_error'] = abs(1/slope/b-1)
        out['eta_relative_error'] = abs(float(np.exp(z.mean()-slope*score.mean()))/e-1)
    return out


def one_case(name):
    start = time.perf_counter()
    case = PROGRAM / name
    output = ROOT / '结果' / name
    sys.path.insert(0, str(case / '依赖快照/python'))
    from studies.common.runner import run_method
    from studies.common.metrics import check_status, aggregate_standard_metrics
    from methods import registry
    from 核验任务 import one_case as validate_saved
    validation = validate_saved(case, False)
    source = output / '中间数据/results.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    b, e, g = data['truth']
    samples = {(s['n'], s['id']): np.asarray(s['values']) for s in data['samples']}
    curves = {(c['n'], c['id']): c['points'] for c in data['gradient_curves']}
    saved_summary = json.loads((output/'中间数据/summary.json').read_text(encoding='utf-8'))
    current_class = registry.IMPLEMENTED['lre']
    legacy_class = load_class(PROGRAM/'LRE_旧版Bernard.py', 'legacy_lre_audit')
    ablation_class = load_class(PROGRAM/'LRE_新版搜索与Bernard位置.py', 'ablation_lre_audit')
    recomputed, pairs, mismatches, anomalies, formula_max = [], [], [], [], {}
    aggregate_rows = {}
    for index, original in enumerate(data['results']):
        n, sid, method = original['n'], original['id'], original['method_id']
        x = samples[n, sid]
        fit = run_method(method, x, **({'offset': .2, 'gamma_steps': 240, 'trace': True} if method == 'mdm' else {}))
        status = 'failure' if any(fit[k] is None for k in KEYS[:3]) else check_status(
            *[fit[k] for k in KEYS[:3]], b, e, g, converged=fit['converged'], sample_min=float(x[0]))
        rerun = dict(n=n, id=sid, method_id=method, status=status,
                     **{k: fit[k] for k in [*KEYS, 'converged', 'extra']})
        recomputed.append(rerun)
        for key in KEYS:
            if not close(fit[key], original[key]):
                mismatches.append(dict(n=n, id=sid, method=method, field=key, original=original[key], rerun=fit[key]))
        for key in ('converged', 'status'):
            if rerun[key] != original[key]:
                mismatches.append(dict(n=n, id=sid, method=method, field=key, original=original[key], rerun=rerun[key]))
        if method == 'mdm':
            actual = [dict(gamma=float(p['gamma']), gradient=float(p['gradient']))
                      for p in fit['trace_data']['grad_gamma_curve']
                      if not p.get('virtual', False) and np.isfinite(p['gradient']) and np.isfinite(p['gamma'])]
            expected = curves[n, sid]
            if len(actual) != len(expected) or any(not close(a[k], v[k], 1e-9, 1e-9) for a, v in zip(actual, expected) for k in ('gamma', 'gradient')):
                mismatches.append(dict(n=n, id=sid, method=method, field='gradient_curve'))
        if fit['converged']:
            independent = formula_checks(x, original)
            for key, error in independent.items():
                formula_max[f'{method}/{key}'] = max(formula_max.get(f'{method}/{key}', 0), error)
            if status == 'failure':
                anomalies.append(dict(n=n, id=sid, method=method, type='boundary_pathology',
                                      sample_min=float(x[0]), gap=float(x[0]-fit['gamma_hat']),
                                      qc_tolerance=1e-10*max(abs(float(x[0])), abs(e), 1), **{k: fit[k] for k in KEYS[:3]},
                                      solution_info=(fit['extra'] or {}).get('solution_info')))
        else:
            anomalies.append(dict(n=n, id=sid, method=method, type='nonconvergence', extra=fit['extra']))
        aggregate_rows.setdefault((method, n), []).append(dict(
            **{k: original[k] for k in KEYS[:3]}, beta=b, eta=e, gamma=g,
            converged=original['converged'], sample_min=float(x[0]), time=original['time']))
        if method == 'lre':
            registry.IMPLEMENTED['lre'] = legacy_class
            old = run_method('lre', x)
            registry.IMPLEMENTED['lre'] = ablation_class
            ablation = run_method('lre', x)
            registry.IMPLEMENTED['lre'] = current_class
            pair = dict(distribution=name, beta=b, eta=e, gamma=g, n=n, id=sid,
                        old={k: old[k] for k in [*KEYS, 'converged', 'extra']},
                        new={k: fit[k] for k in [*KEYS, 'converged', 'extra']},
                        bernard_with_new_search={k: ablation[k] for k in [*KEYS, 'converged', 'extra']})
            pair['quantiles'] = []
            for p in (.01, .1, .5, .9):
                row = dict(p=p, truth=g+e*(-math.log1p(-p))**(1/b))
                for version, estimates in (('old', old), ('new', fit)):
                    row[version] = estimates['gamma_hat'] + estimates['eta_hat']*(-math.log1p(-p))**(1/estimates['beta_hat']) if estimates['converged'] else None
                pair['quantiles'].append(row)
            pairs.append(pair)
        if (index+1) % 250 == 0:
            print(f'{name}: {index+1}/750', flush=True)
    summary_mismatches = []
    def compare(a, v, prefix):
        if isinstance(v, dict):
            for key in v:
                saved_key = key if key in a else str(key)
                compare(a[saved_key], v[key], prefix+'/'+str(key))
        elif isinstance(v, list):
            for i, entry in enumerate(v):
                compare(a[i], entry, prefix+f'/{i}')
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if v is None or not np.isfinite(v):
                return
            if not close(a, v, 1e-9, 1e-10):
                summary_mismatches.append(prefix)
        elif a != v:
            summary_mismatches.append(prefix)
    for key, summary in saved_summary.items():
        actual = aggregate_standard_metrics(aggregate_rows[summary['method_variant'], summary['n']])
        # The experiment adds identifiers to the standardized metric dictionary.
        for metric, expected in actual.items():
            compare(summary[metric], expected, key+'/'+metric)
    result = dict(distribution=name, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  saved_artifact_checks=validation, full_fit_recalculations=len(recomputed),
                  parameter_r2_tolerance=dict(relative=1e-6, absolute=1e-5),
                  mismatches=mismatches, summary_mismatches=summary_mismatches,
                  independent_formula_max_errors=formula_max, anomaly_records=anomalies,
                  recomputed=recomputed, lre_pairs=pairs, elapsed_seconds=time.perf_counter()-start)
    dump(OUT/f'{name}.json', result)
    print(f'{name}: DONE {len(mismatches)} fit mismatches, {len(summary_mismatches)} summary mismatches', flush=True)
    return {k: result[k] for k in ('distribution','full_fit_recalculations','mismatches','summary_mismatches','independent_formula_max_errors','elapsed_seconds')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.case:
        one_case(args.case)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    from 核验任务 import check_layout
    layout = check_layout()
    baseline = {str(p.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest()
                for case in (ROOT/'结果').glob('W(*)') for p in case.rglob('*') if p.is_file()}
    dump(OUT/'原始交付SHA256.json', baseline)
    cases = sorted(p.name for p in (PROGRAM).glob('W(*)') if p.is_dir())
    summaries = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(one_case, name): name for name in cases}
        for job in as_completed(jobs):
            summaries.append(job.result())
    changed = [p for p, digest in baseline.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest]
    record = dict(layout=layout, records=sorted(summaries, key=lambda r:r['distribution']),
                  full_fit_recalculations=sum(r['full_fit_recalculations'] for r in summaries),
                  legacy_lre_recalculations=1200, ablation_lre_recalculations=1200,
                  original_delivery_changes=changed,
                  legacy_git_commit=subprocess.check_output(['git','rev-parse','fccff9eb^'], text=True).strip(),
                  legacy_source_sha256=hashlib.sha256((PROGRAM/'LRE_旧版Bernard.py').read_bytes()).hexdigest(),
                  ablation_source_sha256=hashlib.sha256((PROGRAM/'LRE_新版搜索与Bernard位置.py').read_bytes()).hexdigest())
    dump(OUT/'全量复算核验.json', record)


if __name__ == '__main__':
    main()
