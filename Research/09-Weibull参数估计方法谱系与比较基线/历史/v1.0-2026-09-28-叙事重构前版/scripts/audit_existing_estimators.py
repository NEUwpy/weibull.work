"""Read-only audit of frozen case outputs and the four production estimators.

Run with python/.venv for estimators; --workbook with bundled Python for XLSX.
Writes only this Research's evidence files. Never reruns workbook generators.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parents[1]
TASK = ROOT / 'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825'
PAYLOAD = ROOT / 'tmp/w2-case-20260921/payload.json'
METHODS = [('lse', 'LS'), ('lre', 'LRE'), ('wmle', 'WMLM'), ('mle', 'MLM')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, result):
    dest = RESEARCH / 'evidence' / name
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(dest, flush=True)


def workbook_audit():
    from openpyxl import load_workbook
    path = TASK / '260921-W2参数估计案例/W(2,1000,1000)/2,1000,1000.xlsx'
    before = sha(path)
    wb = load_workbook(path, read_only=True, data_only=True)
    case = json.loads(PAYLOAD.read_text(encoding='utf-8'))['cases'][0]
    count, mismatches = 0, []
    for n in (7, 15, 30):
        sample_rows = list(wb[f'生成样本_n{n}'].values)
        result_rows = list(wb[f'估计结果_n{n}'].values)
        for i, sample in enumerate(case['samples'][str(n)]):
            for j, expected in enumerate(sample):
                actual = sample_rows[i+1][j+1]
                count += 1
                if not math.isclose(actual, expected, rel_tol=1e-14, abs_tol=1e-12):
                    mismatches.append([n, 'sample', i+1, j+1])
        for offset, start in [('0.10', 5), ('0.15', 63), ('0.20', 121)]:
            for i, row in enumerate(case['results'][str(n)][offset]):
                for j, name in enumerate(['MDM', 'LS', 'LRE', 'WMLM', 'MLM']):
                    result = row[name]
                    expected = [result[k] for k in ('shape_hat', 'scale_hat', 'location_hat')] if result['converged'] else ['—']*3
                    actual = list(result_rows[start+i-1][1+3*j:4+3*j])
                    for a, e in zip(actual, expected):
                        count += 1
                        same = a == e if isinstance(e, str) else isinstance(a, (float, int)) and math.isclose(a, e, rel_tol=1e-14, abs_tol=1e-12)
                        if not same:
                            mismatches.append([n, offset, i+1, name, a, e])
    wb.close()
    result = {'path': str(path), 'sha256_before': before, 'sha256_after': sha(path),
              'checked_cells': count, 'mismatches': mismatches, 'payload_sha256': sha(PAYLOAD)}
    save('workbook_audit.json', result)
    print(json.dumps({'checked_cells': count, 'mismatches': len(mismatches), 'unchanged': before == sha(path)}))


def estimator_audit():
    import numpy as np
    import scipy
    from scipy.optimize import minimize_scalar
    sys.path.insert(0, str(ROOT / 'python'))
    from studies.common.runner import run_method
    from methods.lse import log_weibull_order_stat_means
    payload = json.loads(PAYLOAD.read_text(encoding='utf-8'))
    case = payload['cases'][0]
    report = {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_hashes': {}, 'recorded_revision_comparison': {}, 'stored_status_counts': {}, 'replays': []}
    for mid, _ in METHODS:
        p = ROOT / f'python/methods/{mid}.py'
        copy = TASK / f'四种对照方法-代码与原文/01-Python代码/{mid}.py'
        report['source_hashes'][mid] = {'sha256': sha(p), 'copied_code_same': p.read_bytes() == copy.read_bytes()}
    for rev in ['e25c0fde99222c86661e1fda35d3197c70e9e15d', '931ac7d281f66ebe97b8c5ab274ef6f674d6a3b5', payload['protocol']['code_version']]:
        report['recorded_revision_comparison'][rev] = {}
        for mid, _ in METHODS:
            old = subprocess.check_output(['git', 'show', f'{rev}:python/methods/{mid}.py'], cwd=ROOT)
            now = (ROOT / f'python/methods/{mid}.py').read_bytes()
            report['recorded_revision_comparison'][rev][mid] = old.replace(b'\r\n', b'\n') == now.replace(b'\r\n', b'\n')
    for n in (7, 15, 30):
        rows = case['results'][str(n)]['0.10']
        report['stored_status_counts'][n] = {name: dict(Counter(row[name]['status'] for row in rows)) for _, name in METHODS}
        # First, middle, last, and the first stored WMLE failure where present.
        ids = {1, 25, 50}
        failures = [row['sample_id'] for row in rows if not row['WMLM']['converged']]
        ids.update(failures[:1])
        for sid in sorted(ids):
            for mid, name in METHODS:
                actual = run_method(mid, case['samples'][str(n)][sid-1])
                expected = rows[sid-1][name]
                diff = None
                if actual['converged'] and expected['converged']:
                    diff = max(abs(actual[a]-expected[e]) for a,e in [('beta_hat','shape_hat'),('eta_hat','scale_hat'),('gamma_hat','location_hat')])
                report['replays'].append({'n': n, 'sample_id': sid, 'method': name,
                    'status_matches': actual['converged'] == expected['converged'],
                    'max_abs_parameter_difference': diff, 'new_result': actual, 'stored_result': expected})
        print('replayed n=', n, flush=True)
    # A local 2x2 diagnostic, not a population performance comparison.
    t = np.array(case['samples']['7'][1])
    n = len(t)
    scores = {'expected_order_stat': log_weibull_order_stat_means(n),
              'bernard': np.log(-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4)))}
    variants = []
    for label,z in scores.items():
        def obj(g):
            return -float(np.corrcoef(np.log(t-g),z)[0,1]**2)
        grid = np.linspace(0, t[0]-max(t[0]*1e-9,1e-5),1001)
        vals=np.array([obj(g) for g in grid]);k=int(np.argmin(vals));g=float(grid[k])
        if 0<k<len(grid)-1:
            opt=minimize_scalar(obj,bounds=(grid[k-1],grid[k+1]),method='bounded')
            if opt.fun<vals[k]:g=float(opt.x)
        x=np.log(t-g); xc=x-x.mean();zc=z-z.mean();sx=float(xc@xc);sz=float(zc@zc);cross=float(xc@zc)
        rho2=cross**2/(sx*sz)
        for direction,beta in [('logtime_on_score',sz/cross),('score_on_logtime',cross/sx)]:
            eta=float(np.exp(x.mean()-z.mean()/beta))
            variants.append({'score':label,'direction':direction,'shape':beta,'scale':eta,'location':g,'rho_squared':rho2})
    report['single_sample_variants']={'case':'W(2,1000,1000)','n':7,'sample_id':2,'variants':variants}
    report['replay_summary']={'count':len(report['replays']),
      'status_mismatches':sum(not x['status_matches'] for x in report['replays']),
      'max_abs_parameter_difference':max(x['max_abs_parameter_difference'] or 0 for x in report['replays'])}
    save('estimator_audit.json', report)
    print(json.dumps(report['replay_summary']));print(json.dumps(report['single_sample_variants'],ensure_ascii=False))


def recovery_audit():
    """Diagnose all frozen WMLE failures without changing the delivered workbook."""
    import importlib.util
    import numpy as np
    sys.path.insert(0, str(ROOT / 'python'))
    from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3
    solver = ROOT / 'Study/Study 01 New/数据/E09_六方法共同测试/wmle_solver.py'
    spec = importlib.util.spec_from_file_location('audited_wmle_solver', solver)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = json.loads(PAYLOAD.read_text(encoding='utf-8'))['cases'][0]
    records = []
    for n in (7, 15, 30):
        for row in case['results'][str(n)]['0.10']:
            if row['WMLM']['converged']:
                continue
            sid = row['sample_id']
            x = np.array(case['samples'][str(n)][sid-1])
            fit = module.profile_recover(x)
            check = None
            if fit is not None:
                b, eta, g = (fit[k] for k in ('beta_hat','eta_hat','gamma_hat'))
                a = x-g
                # Direct powers independently check the stable-profile equations.
                r1 = get_weight_j2(n)/b + np.log(a).mean() - np.sum(a**b*np.log(a))/np.sum(a**b)
                r2 = np.mean(1/a)*np.sum(a**b)/np.sum(a**(b-1))-get_weight_j3(n,b)
                expected_eta = (np.sum(a**b)/(n*get_weight_j1(n)))**(1/b)
                check = {'r1':float(r1),'r2':float(r2),'squared_residual':float(r1*r1+r2*r2),
                    'scale_absolute_difference':float(abs(expected_eta-eta)),
                    'inside_production_domain':bool(0<b<9.99 and eta>0 and 0<=g<x.min()-1e-6)}
            records.append({'n':n,'sample_id':sid,'stored_status':row['WMLM']['status'],
                            'recovered':fit,'independent_equation_check':check})
    save('wmle_case_recovery.json',{'solver':str(solver),'solver_sha256':sha(solver),
        'payload_sha256':sha(PAYLOAD),'input_scaling':'none; original sample units',
        'records':records})
    print(json.dumps(records,ensure_ascii=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--workbook',action='store_true')
    mode.add_argument('--recovery',action='store_true')
    args=parser.parse_args()
    if args.workbook:
        workbook_audit()
    elif args.recovery:
        recovery_audit()
    else:
        estimator_audit()
