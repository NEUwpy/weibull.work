"""Paired-quantile shape sweep, using this batch's frozen generator and estimators."""
import importlib.util
import json
import math
import platform
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
DATA = BATCH / '结果' / '中间数据'
spec = importlib.util.spec_from_file_location('mother', HERE / '剖面母体.py')
mother = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mother)
BETAS = [2., 2.5, 3., 3.5, 4., 4.5, 5.]
NS = [7, 15]
METHODS = ['mdm', 'lse', 'lre', 'wmle', 'mle', 'lre_park']
SEED = 20261001
GROUPS = 50


def dump(name, value):
    mother.dump(DATA / name, value)


def quantiles(values):
    values = [v for v in values if v is not None and math.isfinite(v)]
    if not values:
        return [None] * 5
    return [float(v) for v in np.quantile(values, [.1, .25, .5, .75, .9])]


def summarize(fits, samples):
    summary = []
    for n in NS:
        for beta in BETAS:
            for method in METHODS:
                rows = [r for r in fits if r['n'] == n and r['beta'] == beta and r['method'] == method]
                good = [r for r in rows if r['converged']]
                paired = [r for r in good if r['conditional_eta'] is not None]
                s = dict(beta=beta, n=n, method=method, total=len(rows), success=len(good),
                         failed=len(rows)-len(good), boundary_zero=sum(r['gamma_hat'] == 0 for r in good),
                         gamma_high=sum(r['gamma_hat'] > 500 for r in good),
                         eta_low=sum(r['eta_hat'] < 1000 for r in good),
                         joint=sum(r['gamma_hat'] > 500 and r['eta_hat'] < 1000 for r in good),
                         conditional_pairs=len(paired), criterion_defined=sum(r['criterion_at_truth'] is not None for r in rows),
                         mdm_below_threshold=sum(r['criterion_at_truth'] < .1 for r in rows if r['criterion_at_truth'] is not None))
                for name in ('beta_hat', 'eta_hat', 'gamma_hat'):
                    s[name + '_q'] = quantiles([r[name] for r in good])
                for name in ('criterion_at_truth', 'truth_drive'):
                    s[name + '_q'] = quantiles([r[name] for r in rows])
                for name in ('free', 'fixed'):
                    s['eta_error_' + name + '_q'] = quantiles([abs(r['eta_hat' if name == 'free' else 'conditional_eta']-1000) for r in paired])
                s['sum_q'] = quantiles([r['gamma_hat']+r['eta_hat'] for r in good])
                # Shared standard Bias/SD/RMSE/MAE remain separate from descriptive quantiles.
                s['standard_metrics'] = mother.aggregate_standard_metrics(rows, include_diagnostics=False)
                summary.append(s)
    endpoint_pairs = []
    for n in NS:
        for method in METHODS:
            low = {r['sample_id']: r for r in fits if r['beta'] == 2 and r['n'] == n and r['method'] == method and r['converged']}
            high = {r['sample_id']: r for r in fits if r['beta'] == 5 and r['n'] == n and r['method'] == method and r['converged']}
            ids = sorted(low.keys() & high.keys())
            endpoint_pairs.append(dict(n=n, method=method, paired_success=len(ids),
                delta_gamma_q=quantiles([high[i]['gamma_hat']-low[i]['gamma_hat'] for i in ids]),
                delta_eta_q=quantiles([high[i]['eta_hat']-low[i]['eta_hat'] for i in ids]),
                gamma_increased=sum(high[i]['gamma_hat'] > low[i]['gamma_hat'] for i in ids),
                eta_decreased=sum(high[i]['eta_hat'] < low[i]['eta_hat'] for i in ids)))
    tail = []
    for n in NS:
        for beta in BETAS:
            rows = [r for r in samples if r['beta'] == beta and r['n'] == n]
            tail.append(dict(beta=beta, n=n, minimum_q=quantiles([r['observations'][0] for r in rows]),
                theoretical_mean_minimum=500+1000*float(mother.gamma_function(1+1/beta))*n**(-1/beta),
                theoretical_probability_minimum_above_1000=math.exp(-n*.5**beta),
                above_1000=sum(r['observations'][0] > 1000 for r in rows)))
    dump('汇总.json', dict(summary=summary, endpoint_pairs=endpoint_pairs, tail=tail))
    flat = [{k: v for k, v in s.items() if not isinstance(v, (dict, list))} |
            {f'{key}_{suffix}': value for key, values in s.items() if key.endswith('_q')
             for suffix, value in zip(('p10','q1','median','q3','p90'), values)} for s in summary]
    mother.write_csv(DATA / '汇总.csv', flat)


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    if (DATA / '实际估计.json').exists():
        raise SystemExit('Results already exist. Create another batch for a new calculation.')
    samples, latent, fits, checks = [], [], [], []
    representatives = {}
    for n in NS:
        base = []
        for sid in range(1, GROUPS+1):
            e = mother.generate_sample(1., 1., 0., n, sid-1, seed=SEED)
            u = -np.expm1(-e)
            distance = float(np.mean((u-np.arange(1, n+1)/(n+1))**2))
            base.append((sid, e, distance))
            latent.append(dict(n=n, sample_id=sid, seed=SEED, exponential_order_stats=e.tolist(),
                               uniform_order_stats=u.tolist(), representative_distance=distance))
        representatives[n] = min(base, key=lambda t: (t[2], t[0]))[0]
        for beta in BETAS:
            for sid, e, distance in base:
                x = 500.+1000.*e**(1/beta)
                recovery = ((x-500.)/1000.)**beta
                error = float(np.max(abs(recovery-e)))
                assert error < 1e-11
                samples.append(dict(beta=beta, n=n, sample_id=sid, seed=SEED,
                    observations=x.tolist(), exponential_recovery_error=error))
                for method in METHODS:
                    r = mother.run_method(method, x, **({'offset': .1, 'gamma_steps': 240} if method == 'mdm' else {}))
                    r.update(beta=beta, eta=1000., gamma=500., n=n, sample_id=sid, method=method,
                             sample_min=float(x[0]))
                    p = mother.profile(x, method, 500.)
                    r['conditional_beta'] = p['b'] if p else None
                    r['conditional_eta'] = p['eta'] if p else None
                    r['criterion_at_truth'] = p['value'] if p else None
                    if method in ('lse', 'lre', 'lre_park'):
                        left, right = mother.profile(x, method, 499.99), mother.profile(x, method, 500.01)
                        r['truth_drive'] = 1000*(right['value']-left['value'])/.02
                    else:
                        r['truth_drive'] = (p['value']-.1 if method == 'mdm' else p['value']) if p else None
                    if r['converged']:
                        at = mother.profile(x, method, r['gamma_hat'])
                        checks.append(dict(beta=beta, n=n, sample_id=sid, method=method,
                            profile_defined=at is not None,
                            beta_formula_error=abs(at['b']-r['beta_hat']) if at else None,
                            eta_formula_error=abs(at['eta']-r['eta_hat']) if at else None,
                            criterion_at_fit=at['value'] if at else None))
                    r.pop('trace_data', None)
                    fits.append(r)
                if sid % 10 == 0:
                    print(f'beta={beta:g} n={n}: {sid}/50 groups', flush=True)
    dump('共同随机分位点.json', latent)
    dump('样本.json', samples)
    dump('实际估计.json', fits)
    dump('公式核验.json', checks)
    curves = []
    for n in NS:
        sid = representatives[n]
        for beta in BETAS:
            x = np.array(next(s['observations'] for s in samples if s['beta'] == beta and s['n'] == n and s['sample_id'] == sid))
            for method in METHODS:
                fit = next(r for r in fits if r['beta'] == beta and r['n'] == n and r['sample_id'] == sid and r['method'] == method)
                grid = np.unique(np.r_[np.linspace(0, min(x[0]*(1-1e-6), 1450), 181), 500.,
                                     fit['gamma_hat'] if fit['converged'] else 500.])
                for g in grid:
                    p = mother.profile(x, method, float(g))
                    curves.append(dict(beta=beta, n=n, sample_id=sid, method=method, gamma=float(g),
                        criterion=p['value'] if p else None, conditional_beta=p['b'] if p else None,
                        conditional_eta=p['eta'] if p else None, loglikelihood=p['ll'] if p else None,
                        J3_clamped=p['clipped'] if p else False))
    dump('代表样本曲线.json', curves)
    mother.write_csv(DATA / '代表样本曲线.csv', curves)
    summarize(fits, samples)
    finalize()
    print('COMPLETE', len(samples), 'groups,', len(fits), 'fits, representatives', representatives, flush=True)


def finalize():
    """Write provenance from saved computations; does not rerun or alter estimates."""
    fits = json.loads((DATA / '实际估计.json').read_text(encoding='utf-8'))
    samples = json.loads((DATA / '样本.json').read_text(encoding='utf-8'))
    checks = json.loads((DATA / '公式核验.json').read_text(encoding='utf-8'))
    latent = json.loads((DATA / '共同随机分位点.json').read_text(encoding='utf-8'))
    representatives = {n: min([r for r in latent if r['n'] == n],
                             key=lambda r:(r['representative_distance'],r['sample_id']))['sample_id'] for n in NS}
    max_b = max(r['beta_formula_error'] for r in checks if r['beta_formula_error'] is not None)
    max_eta = max(r['eta_formula_error'] for r in checks if r['eta_formula_error'] is not None)
    by_key = {(r['beta'], r['n'], r['sample_id'], r['method']): r for r in fits}
    max_relative_b = max(r['beta_formula_error']/by_key[(r['beta'],r['n'],r['sample_id'],r['method'])]['beta_hat'] for r in checks)
    max_relative_eta = max(r['eta_formula_error']/by_key[(r['beta'],r['n'],r['sample_id'],r['method'])]['eta_hat'] for r in checks)
    assert all(r['profile_defined'] for r in checks)
    # Frozen optimizers return approximate solutions, including a J3 interpolation
    # knot. Preserve these candidates; report the measured differences explicitly.
    assert max_relative_b < 1e-3 and max_relative_eta < 1e-4
    dump('manifest.json', dict(task='paired quantile shape sweep and compensation report', date='2026-10-01',
        betas=BETAS, n=NS, groups_per_cell=GROUPS, seed=SEED, methods=METHODS,
        true_eta=1000, true_gamma=500, sample_groups=len(samples), fit_records=len(fits),
        sampling='shared generate_sample(1.,1.,0.,n,repeat_id,seed) -> E; x=500+1000 E^(1/beta)',
        representative_rule='argmin mean((1-exp(-E_i)-i/(n+1))^2); tie by id; one id per n for all beta and methods',
        representatives=representatives, historical_inputs='Copied prior verified estimates/audit; original deliveries untouched.',
        statistics='Descriptive quantiles on all converged returns; failed rows retained. Cross-beta centers may use different successful subsets; endpoint paired stats use shared successful ids.',
        implementation_limits='Historical snapshot; WMLE beta<10, J3 clamps above5; MLE only finite local branch beta>1; MDM delta=.1 and gamma>=0.',
        checks=dict(sample_recovery_max_error=max(s['exponential_recovery_error'] for s in samples),
                    successful_formula_checks=len(checks), max_beta_formula_error=max_b, max_eta_formula_error=max_eta,
                    max_relative_beta_formula_error=max_relative_b, max_relative_eta_formula_error=max_relative_eta,
                    formula_check_tolerances='relative beta<1e-3, eta<1e-4; actual errors retained, no estimates replaced'),
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=mother.scipy.__version__,
                     matplotlib=mother.matplotlib.__version__, executable=sys.executable)))
    print('PROVENANCE', len(samples), 'groups,', len(fits), 'fits, representatives', representatives, flush=True)


if __name__ == '__main__':
    finalize() if '--finalize' in sys.argv else main()
