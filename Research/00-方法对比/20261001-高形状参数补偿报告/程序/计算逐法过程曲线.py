"""Diagnose all saved fits in three conditions; no sampling or estimator reruns.

Every curve uses the frozen criterion in 剖面母体.py. The returned fit is
unchanged. Conditional WMLE equations and finite MLE scores are diagnostics,
not records of the joint optimizer's iterations.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / '结果' / '中间数据'
INPUT = HERE / '输入快照'
METHODS = ('mdm', 'lse', 'lre', 'wmle', 'mle')
CONDITIONS = ((2, 7), (5, 7), (5, 15))
spec = importlib.util.spec_from_file_location('frozen_profile', HERE / '剖面母体.py')
mother = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mother)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def curve(task):
    source, beta, n, sid, method, observations, fit = task
    x = np.array(observations, dtype=float)
    top = float(x[0] - max(1e-5, x[0] * 1e-7))
    actual = float(fit['gamma_hat']) if fit['converged'] else None
    extra = [500.]
    if actual is not None:
        extra += [actual, actual - 2, actual + 2, actual - 10, actual + 10]
    # An exact point at the returned gamma avoids interpolating its criterion.
    grid = np.unique(np.r_[np.linspace(0, top, 141), extra])
    grid = grid[(grid >= 0) & (grid <= top)]
    points = []
    for g in grid:
        p = mother.profile(x, method, float(g))
        if p is None:
            points.append([float(g), None, None, None, False, None])
        else:
            values = [p['value'], p['b'], p['eta']]
            assert all(math.isfinite(float(v)) for v in values), (source, beta, n, sid, method, g)
            points.append([float(g), float(p['value']), float(p['b']), float(p['eta']), p['clipped'], p['ll']])
    truth = next(p for p in points if p[0] == 500.) if top >= 500 else None
    returned = next((p for p in points if actual is not None and p[0] == actual), None)
    return dict(source=source, beta=beta, n=n, sample_id=sid, method=method,
                sample_min=float(x[0]), fit=fit, points=points,
                truth=truth, returned=returned)


def main():
    paths = [DATA / '样本.json', DATA / '实际估计.json', INPUT / '原案例核验.json',
             INPUT / '原案例估计.json', HERE / '剖面母体.py']
    hashes = {str(p.relative_to(HERE.parent)): sha(p) for p in paths}
    samples, estimates, audit, old = (load(p) for p in paths[:4])
    fit_index = {(r['beta'], r['n'], r['sample_id'], r['method']): r for r in estimates}
    tasks = []
    for beta, n in CONDITIONS:
        ss = sorted((s for s in samples if s['beta'] == beta and s['n'] == n), key=lambda s: s['sample_id'])
        assert len(ss) == 50
        for method in METHODS:
            for s in ss:
                fit = fit_index[beta, n, s['sample_id'], method]
                tasks.append(('paired', beta, n, s['sample_id'], method, s['observations'], fit))
    for method in METHODS:
        successful = [r for r in old if r['beta'] == 5 and r['n'] == 7 and r['method'] == method and r['converged']]
        median = float(np.median([r['gamma_hat'] for r in successful]))
        fit = min(successful, key=lambda r: (abs(r['gamma_hat'] - median), r['sample_id']))
        s = next(s for s in audit['samples'] if s['beta_true'] == 5 and s['n'] == 7 and s['sample_id'] == fit['sample_id'])
        tasks.append(('original', 5, 7, fit['sample_id'], method, s['observations'], fit))
    target = DATA / '逐法过程曲线.json'
    if target.exists():
        cached = load(target)
        assert cached['provenance']['input_hashes'] == hashes, 'Inputs changed; use a separate reproduction directory.'
        curves = cached['curves']
        assert len(curves) == len(tasks)
    else:
        curves = []
        with ProcessPoolExecutor(max_workers=3) as pool:
            for result in pool.map(curve, tasks, chunksize=10):
                curves.append(result)
                if len(curves) % 150 == 0:
                    print(f'{len(curves)}/{len(tasks)} profiles', flush=True)
    summaries = []
    for method in METHODS:
        for beta, n in CONDITIONS:
            rr = [r for r in curves if r['source'] == 'paired' and r['method'] == method and r['beta'] == beta and r['n'] == n]
            good = [r for r in rr if r['fit']['converged']]
            gamma = [r['fit']['gamma_hat'] for r in good]
            truth = [r['truth'][1] for r in rr if r['truth'] is not None and r['truth'][1] is not None]
            summaries.append(dict(method=method, beta=beta, n=n, total=len(rr), success=len(good),
                gamma_median=float(np.median(gamma)), gamma_above_truth=sum(g > 500 for g in gamma),
                gamma_at_zero=sum(g <= 1e-8 for g in gamma),
                truth_criterion_count=len(truth), truth_criterion_quartiles=np.quantile(truth, [.25, .5, .75]).tolist(),
                truth_below_mdm_threshold=sum(v < .1 for v in truth) if method == 'mdm' else None,
                undefined_curve_points=sum(p[1] is None for r in rr for p in r['points']),
                returned_without_conditional_curve=sum(r['returned'] is None or r['returned'][1] is None for r in good)))
    invariance = {}
    for method in ('lse', 'lre'):
        rr = {(r['beta'], r['sample_id']): r for r in curves if r['source'] == 'paired' and r['method'] == method and r['n'] == 7}
        differences = [abs(rr[2, sid]['truth'][1] - rr[5, sid]['truth'][1]) for sid in range(1, 51)]
        invariance[method] = dict(paired_groups=50, maximum_absolute_loss_difference=max(differences))
        assert max(differences) < 1e-12
    assert all(sha(p) == hashes[str(p.relative_to(HERE.parent))] for p in paths)
    sample_index = {(s['beta'], s['n'], s['sample_id']): np.array(s['observations']) for s in samples}
    mdm_envelope = []
    for beta, n in CONDITIONS:
        checks = []
        for r in curves:
            if r['source'] != 'paired' or r['method'] != 'mdm' or r['beta'] != beta or r['n'] != n:
                continue
            b = r['truth'][2]
            x = sample_index[beta, n, r['sample_id']]
            p = (np.arange(1, n+1) - .3) / (n + .4)
            weights = (-np.log1p(-p)) ** (-1/b)
            pseudo_scale = (x - 500) * weights
            derivative = float(-np.cov(pseudo_scale, weights, ddof=1)[0, 1] / np.std(pseudo_scale, ddof=1))
            sd_weights = float(np.std(weights, ddof=1))
            assert abs(derivative) <= sd_weights + 1e-12
            checks.append(dict(sample_id=r['sample_id'], conditional_beta=b, weight_sd=sd_weights,
                envelope_gradient=derivative, finite_difference_gradient=r['truth'][1],
                gradient_difference=abs(derivative-r['truth'][1])))
        mdm_envelope.append(dict(beta=beta, n=n, groups=len(checks),
            conditional_beta_median=float(np.median([r['conditional_beta'] for r in checks])),
            weight_sd_median=float(np.median([r['weight_sd'] for r in checks])),
            maximum_gradient_difference=max(r['gradient_difference'] for r in checks), checks=checks))
    output = dict(columns=['gamma', 'criterion', 'conditional_beta', 'conditional_eta', 'J3_clamped', 'profile_loglik'],
        conditions=[dict(beta=b, n=n, groups=50) for b, n in CONDITIONS],
        provenance=dict(input_hashes=hashes, new_samples=0, new_fits=0,
            across_beta='Same n and sample id share E; n7 and n15 use separate latent families.',
            original_selection='Original beta5 n7 successful gamma closest to method median; tie by id',
            diagnostic_scope='Actual frozen conditional criteria; not optimizer iteration trajectories.'),
        summaries=summaries, regression_truth_invariance=invariance, mdm_envelope=mdm_envelope, curves=curves)
    target.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(curves=len(curves), points=sum(len(r['points']) for r in curves),
                         summaries=summaries, invariance=invariance), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
