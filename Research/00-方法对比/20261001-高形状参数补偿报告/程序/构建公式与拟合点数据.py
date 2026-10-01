"""Build numbered observed regression points and formula-evaluation points.

Uses saved fits and the frozen profile/weight functions. No sampling and no new
three-parameter estimates. The WMLE grid diagnoses both original equations.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.special import logsumexp
from 计算逐法过程曲线 import mother

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / '结果' / '中间数据'
INPUT = HERE / '输入快照'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wmle_residuals(x, beta, gamma):
    """Exact frozen T1,T2; accepts scalar parameters for independent QA."""
    d = np.asarray(x) - gamma
    ld = np.log(d)
    weights = np.exp(beta*ld - logsumexp(beta*ld))
    t1 = mother.get_weight_j2(len(x))/beta + ld.mean() - weights @ ld
    ratio = np.exp(logsumexp(beta*ld) - logsumexp((beta-1)*ld))
    t2 = np.mean(1/d)*ratio - mother.get_weight_j3(len(x), beta)
    return float(t1), float(t2)


def main():
    process_path = DATA / '逐法过程曲线.json'
    audit_path = INPUT / '原案例核验.json'
    source = json.loads(process_path.read_text(encoding='utf-8'))
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    original = {r['method']: r for r in source['curves'] if r['source'] == 'original'}
    samples = {(r['beta_true'], r['n'], r['sample_id']): r['observations'] for r in audit['samples']}
    result = dict(regressions={}, evaluation_points={}, wmle={},
        input_hashes={'结果/中间数据/逐法过程曲线.json': digest(process_path),
                      '程序/输入快照/原案例核验.json': digest(audit_path)},
        new_samples=0, new_three_parameter_estimates=0)
    for method in ('lse', 'lre'):
        r = original[method]
        x = np.array(samples[5, 7, r['sample_id']])
        n = len(x)
        reference = (mother.log_weibull_order_stat_means(n) if method == 'lse' else
                     np.log(-np.log1p(-(np.arange(1, n+1)-.3)/(n+.4))))
        datasets = []
        for role, p in [('fixed_true_gamma', r['truth']), ('fixed_returned_gamma', r['returned'])]:
            g, _, b, eta, _, _ = p
            ld = np.log(x-g)
            xx, yy = (reference, ld) if method == 'lse' else (ld, reference)
            slope, intercept = np.polyfit(xx, yy, 1)
            predicted = slope*xx + intercept
            expected_b = 1/slope if method == 'lse' else slope
            expected_eta = np.exp(intercept) if method == 'lse' else np.exp(-intercept/slope)
            assert abs(expected_b - b) < 1e-10 and abs(expected_eta - eta) < 1e-8
            datasets.append(dict(role=role, gamma=g, conditional_beta=b, conditional_eta=eta,
                slope=float(slope), intercept=float(intercept), loss=float(1-np.corrcoef(xx, yy)[0,1]**2),
                points=[dict(id=i+1, observation=float(x[i]), x=float(xx[i]), y=float(yy[i]),
                             fitted_y=float(predicted[i])) for i in range(n)]))
        result['regressions'][method] = dict(sample_id=r['sample_id'], n=n, observations=x.tolist(), datasets=datasets)
    for method in ('mdm', 'mle'):
        r = original[method]
        points = [dict(id=f'G{i+1}', gamma=p[0], value=p[1] if method == 'mdm' else
                       (p[5]-r['truth'][5] if p[5] is not None else None)) for i, p in enumerate(r['points'])]
        truth = next(p for p in points if p['gamma'] == 500)
        returned = next(p for p in points if p['gamma'] == r['fit']['gamma_hat'])
        result['evaluation_points'][method] = dict(sample_id=r['sample_id'], points=points,
            true_gamma_point_id=truth['id'], returned_gamma_point_id=returned['id'],
            meaning='G indexes candidate-gamma formula evaluations, not observed lifetimes')
    r = original['wmle']
    x = np.array(samples[5, 7, r['sample_id']])
    gg = np.unique(np.r_[np.linspace(0, x[0] - 1e-4, 220), 500., r['fit']['gamma_hat']])
    bb = np.unique(np.r_[np.linspace(.3, 9.98, 180), 5., r['fit']['beta_hat']])
    ld = np.log(x[None, :] - gg[:, None])
    powers = bb[:, None, None] * ld[None, :, :]
    log_s = logsumexp(powers, axis=2)
    weights = np.exp(powers-log_s[:,:,None])
    t1 = mother.get_weight_j2(len(x))/bb[:,None] + ld.mean(axis=1)[None,:] - (weights*ld[None,:,:]).sum(axis=2)
    ratio = np.exp(log_s-logsumexp((bb[:,None,None]-1)*ld[None,:,:], axis=2))
    j3 = np.array([mother.get_weight_j3(len(x), float(b)) for b in bb])
    t2 = np.mean(1/(x[None,:]-gg[:,None]), axis=1)[None,:]*ratio-j3[:,None]
    actual_b, actual_g = r['fit']['beta_hat'], r['fit']['gamma_hat']
    rb, rg = int(np.where(bb == actual_b)[0][0]), int(np.where(gg == actual_g)[0][0])
    actual_t1, actual_t2 = wmle_residuals(x, actual_b, actual_g)
    assert abs(t1[rb,rg]-actual_t1) < 1e-12 and abs(t2[rb,rg]-actual_t2) < 1e-12
    result['wmle'] = dict(sample_id=r['sample_id'], observations=x.tolist(),
        gamma_grid=gg.tolist(), beta_grid=bb.tolist(), t1=t1.tolist(), t2=t2.tolist(),
        returned_beta=actual_b, returned_gamma=actual_g, returned_t1=actual_t1, returned_t2=actual_t2,
        returned_objective=actual_t1**2+actual_t2**2,
        truth_beta=5., truth_gamma=500., truth_residuals=list(wmle_residuals(x, 5., 500.)),
        grid_points=int(t1.size))
    (DATA / '单组绘图点与方程.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(regression_observations_per_method=7, wmle_formula_grid_points=int(t1.size),
        wmle_actual_return_residuals=[actual_t1, actual_t2], new_three_parameter_estimates=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
