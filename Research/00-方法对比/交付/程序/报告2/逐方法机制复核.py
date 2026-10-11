"""Shared conditional diagnostics for archived Research00 estimates.

Curves and candidate probes do not replace estimates, states or frequencies.
The case-37 audit alone replays one frozen estimator to record its five starts.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path, load_conditional_profiles
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
conditional_profiles = load_conditional_profiles()
INPUTS = {
    "high": ("W(2,100,500)", 15, 36),
    "high_control": ("W(2,100,500)", 15, 35),
    "low": ("W(5,100,500)", 7, 11),
    "low_control": ("W(5,100,500)", 7, 10),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cov(a, b):
    return float(np.mean((a - a.mean()) * (b - b.mean())))


def shape_profile(x, gamma):
    """Unrestricted diagnostic for MMLE's retained sample, not the MLE report domain."""
    return conditional_profiles.mle_profile(x, gamma, shape_lower=0)


def mle_profile(x, gamma):
    """R00 MLE conditional optimum over beta>=1, with the boundary retained."""
    return conditional_profiles.mle_profile(x, gamma)


def regression(x, gamma, z, method):
    y = np.log(x-gamma)
    c, vy, vz = cov(y, z), cov(y, y), cov(z, z)
    r2 = c*c/(vy*vz)
    beta = vz/c if method == "LSE" else c/vy
    eta = np.exp(y.mean()-z.mean()/beta)
    return dict(beta=float(beta), eta=float(eta), r2=float(r2),
                relative_residual=float(1-r2),
                fisher_ratio=float((len(x)-2)/(len(x)-1)/(1-r2)))


def mdm_profile(x, gamma):
    p = (np.arange(1, len(x)+1)-.3)/(len(x)+.4)
    u = -np.log1p(-p)

    def sigma(beta):
        return float(np.std((x-gamma)*u**(-1/beta), ddof=1))

    fit = minimize_scalar(sigma, bounds=(.1, 15), method="bounded")
    w = u**(-1/fit.x)
    eta_i = (x-gamma)*w
    grad = float(-np.cov(eta_i, w, ddof=1)[0, 1]/fit.fun)
    bound = float(np.std(w, ddof=1))
    assert abs(grad) <= bound+1e-10
    step = min(x[0]*1e-5, (x[0]-gamma)*.25)
    if gamma > step:
        finite_grad = (mdm_sigma(x, gamma+step, u)-mdm_sigma(x, gamma-step, u))/(2*step)
    else:
        finite_grad = (mdm_sigma(x, gamma+step, u)-fit.fun)/step
    return dict(beta=float(fit.x), eta=float(np.mean(eta_i)), sigma=float(fit.fun),
                gradient=grad, gradient_bound=bound, finite_gradient=float(finite_grad))


def mdm_sigma(x, gamma, u):
    return float(minimize_scalar(lambda b: np.std((x-gamma)*u**(-1/b), ddof=1),
                                bounds=(.1, 15), method="bounded").fun)


def wmle_profile(x, gamma, weights):
    """Same weights and shape cap as the archived WMLE; None means no T1 root."""
    return conditional_profiles.wmle_profile(x, gamma, weights)


def refresh_saved_diagnostics():
    """Re-evaluate only MLE/WMLE diagnostics on the 13 frozen matrices.

    Counts of archived successes and abnormal estimates stay fixed. A better
    feasible candidate is a numerical-solver witness, not a replacement fit.
    """
    import csv

    path = DATA_DIR / '全量流程定位.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        names = list(reader.fieldnames)
        rows = list(reader)
    originals = [dict(r) for r in rows]
    catalog = json.loads((PROGRAM/'跨参数对比/13组合取数.json').read_text(encoding='utf-8'))['sources']
    samples, weights, sources = {}, {}, {}
    for entry in catalog:
        matrix = matrix_path(entry)
        assert digest(matrix) == entry['matrix_sha256']
        data = json.loads(matrix.read_text(encoding='utf-8'))
        combo = entry['combination']
        samples.update({(combo, s['n'], s['id']): np.sort(np.array(s['values'], float)) for s in data['samples']})
        snapshot = snapshot_path(entry)
        sys.path.insert(0, str(snapshot))
        weights[combo] = load_module(snapshot/'methods/wmle.py', 'r00_diag_weights_'+str(len(weights)))
        for source in [matrix, snapshot/'methods/wmle.py', snapshot/'methods/j3_weights.tsv']:
            sources[str(source)] = digest(source)

    missing, numerical = [], []
    for r in rows:
        method = r['method']
        if method not in ('MLE', 'WMLE'):
            continue
        x = samples[r['combination'], int(r['n']), int(r['group'])]
        g, g0 = float(r['gamma_hat']), float(r['gamma_true'])
        at_true = (mle_profile(x, g0) if method == 'MLE' else wmle_profile(x, g0, weights[r['combination']]))
        r['fixed_true_conditional_status'] = 'defined' if at_true is not None else 'no_T1_root_in_shape_range'
        if at_true is None:
            missing.append({k:r[k] for k in ['combination', 'n', 'group', 'abnormal', 'direction']})
            for key in ['beta_fixed_true_location', 'fixed_true_abnormal', 'fixed_true_direction',
                        'removed_by_location_fix', 't2_fixed_true']:
                r[key] = ''
        else:
            b, truth = at_true['beta'], float(r['beta_true'])
            direction = 'over' if b >= 3*truth else 'under' if b <= truth/3 else 'none'
            r.update(beta_fixed_true_location=str(b), fixed_true_abnormal=str(direction != 'none'),
                     fixed_true_direction=direction,
                     removed_by_location_fix=str(r['abnormal']=='True' and direction=='none'))
            if method == 'WMLE':
                r['t2_fixed_true'] = str(at_true['t2'])
        if method == 'MLE':
            selected = mle_profile(x, g)
            r.update(criterion_fixed_true=str(at_true['ll']),
                     selected_minus_true=str(float(r['criterion_selected'])-at_true['ll']),
                     location_score_original=str(selected['location_score']))
            probe_gamma = float(x[0]-max(1e-6, x[0]*1e-7))
            probe = mle_profile(x, probe_gamma)
            gain = probe['ll']-float(r['criterion_selected'])
            better_true = at_true['ll'] > float(r['criterion_selected'])+1e-5
            better_probe = gain > 1e-5
            r.update(boundary_probe_gamma=str(probe_gamma), boundary_probe_beta=str(probe['beta']),
                     boundary_probe_eta=str(probe['eta']), boundary_probe_ll=str(probe['ll']),
                     boundary_probe_ll_gain=str(gain),
                     better_feasible_candidate_found=str(better_true or better_probe))
            if r['abnormal']=='True' and (better_true or better_probe):
                numerical.append({k:r[k] for k in ['combination', 'n', 'group', 'direction',
                                 'selected_minus_true', 'boundary_probe_ll_gain']})

    protected = ['combination', 'n', 'group', 'method', 'version', 'beta_true', 'eta_true',
                 'gamma_true', 'beta_hat', 'eta_hat', 'gamma_hat', 'abnormal', 'direction']
    assert all(all(r[k]==old[k] for k in protected) for r,old in zip(rows, originals))
    names += list(dict.fromkeys(k for r in rows for k in r if k not in names))
    temporary = path.with_suffix('.tmp.csv')
    with temporary.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)

    target = DATA_DIR/'全量流程定位.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    wr = [r for r in rows if r['method']=='WMLE']
    defined = [r for r in wr if r['fixed_true_conditional_status']=='defined']
    abnormal = [r for r in defined if r['abnormal']=='True']
    qa['methods']['WMLE'].update(
        fixed_true_conditional_defined=len(defined), fixed_true_conditional_undefined=len(missing),
        abnormal_fixed_true_conditional_undefined=sum(r['abnormal']=='True' for r in missing),
        removed_at_true_location=sum(r['fixed_true_abnormal']=='False' for r in abnormal),
        persists_at_true_location=sum(r['fixed_true_abnormal']=='True' for r in abnormal),
        normal_becomes_abnormal_at_true=sum(r['abnormal']=='False' and r['fixed_true_abnormal']=='True' for r in defined),
        all_fixed_true_abnormal=sum(r['fixed_true_abnormal']=='True' for r in defined))
    qa['mechanism_checks']['wmle_direction_matches_equation_sign'] = sum(
        (float(r['t2_fixed_true'])<0 if r['direction']=='under' else float(r['t2_fixed_true'])>0) for r in abnormal)
    qa['conditional_diagnostics'] = dict(
        MLE='beta>=1; beta=1 boundary kept with recomputed eta',
        WMLE='0<beta<10; no T1 zero means undefined, never a clamped shape',
        no_estimator_calls=True, archived_estimates_and_abnormal_flags_unchanged=True,
        wmle_undefined_at_true=missing, mle_abnormal_better_feasible_candidates=numerical,
        mle_probe='Compare original likelihood against true-location conditional optimum and min(X)-max(1e-6,1e-7*min(X)). Gain >1e-5 is a witness; no witness is not a global optimality proof.')
    qa['current_diagnostic_source_sha256'] = {**sources, str(Path(__file__)):digest(Path(__file__)),
                                            str(Path(conditional_profiles.__file__)):digest(Path(conditional_profiles.__file__)),
                                            str(path):digest(path)}
    temporary = target.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(qa, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(target)
    print(f'WMLE: {len(missing)} true-location branches undefined; MLE: {len(numerical)} abnormal solver witnesses.')


def audit_mle_case37():
    """Replay one frozen fit and record its five starts without editing the estimator."""
    entry = next(e for e in json.loads((PROGRAM/'跨参数对比/13组合取数.json').read_text(encoding='utf-8'))['sources']
                 if e['combination']=='W(2,1000,3000)')
    data = json.loads(matrix_path(entry).read_text(encoding='utf-8'))
    x = next(s['values'] for s in data['samples'] if s['n']==7 and s['id']==37)
    archived = next(r for r in data['results'] if r['n']==7 and r['id']==37 and r['method_id']=='mle')
    snapshot = snapshot_path(entry)
    sys.path.insert(0, str(snapshot))
    frozen = load_module(snapshot/'methods/mle.py', 'r00_case37_frozen_mle')
    minimize = frozen.minimize
    starts = []

    def observed(*args, **kwargs):
        result = minimize(*args, **kwargs)
        b, eta, gamma = (float(v) for v in result.x)
        starts.append(dict(initial=[float(v) for v in args[1]], beta=b, eta=eta, gamma=gamma,
                           ll=-float(result.fun), optimizer_success=bool(result.success),
                           iterations=int(result.nit), accepted_shape=bool(b>=1)))
        return result

    frozen.minimize = observed
    try:
        returned = frozen.MLE(x).run()
    finally:
        frozen.minimize = minimize
    assert np.allclose(returned[:3], [archived[k] for k in ['beta_hat','eta_hat','gamma_hat']], rtol=1e-10)
    assert len(starts)==5 and starts[0]['accepted_shape'] and all(not s['accepted_shape'] for s in starts[1:])
    at_true = mle_profile(np.array(x), 3000)
    assert at_true['ll']>starts[0]['ll']
    target = DATA_DIR/'20261010-异常各情形过程核验.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    qa['cases']['MLE_stop']['solver_audit'] = dict(
        frozen_estimator_sha256=digest(snapshot/'methods/mle.py'), archived_return_reproduced=True,
        starts=starts, higher_feasible_true_location_candidate=at_true,
        conclusion='Numerical stopping and post-search acceptance problem; not a likelihood formula error.')
    temporary = target.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(qa, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(target)
    print('Reproduced MLE case 37; logged all five starts and the better feasible candidate.')
