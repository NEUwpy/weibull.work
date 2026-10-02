"""2026-10-02: verify derived criteria and expand paired curves from panels a/b.

Use saved samples, fits and profiles. Select one paired sample id per method;
do not sample, rerun a three-parameter estimator, or overwrite the profile cache.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.special import logsumexp
from 计算逐法过程曲线 import mother

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '结果' / '中间数据'
METHODS = ('mdm', 'lse', 'lre', 'wmle', 'mle')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_pair(source, method):
    rows = {(r['beta'], r['sample_id']): r for r in source['curves']
            if r['source'] == 'paired' and r['n'] == 7 and r['method'] == method}
    center = float(np.median([r['fit']['gamma_hat'] for (b, _), r in rows.items()
                             if b == 5 and r['fit']['converged']]))
    eligible = [sid for sid in range(1, 51) if all(
        rows[b, sid]['fit']['converged'] and rows[b, sid]['truth'][1] is not None
        and rows[b, sid]['returned'][1] is not None for b in (2, 5))]
    chosen = min(eligible, key=lambda sid: (abs(rows[5, sid]['fit']['gamma_hat']-center), sid))
    return [rows[b, chosen] for b in (2, 5)], center, eligible


def verify_formula(x, row):
    method = row['method']
    checks = []
    # Independent algebraic checks at both meaningful locations; the MLE
    # envelope derivative additionally checks a re-optimized nearby likelihood.
    for saved in (row['truth'], row['returned']):
        gamma, criterion, beta, eta, _, ll = saved
        d = x-gamma
        ld = np.log(d)
        n = len(x)
        if method in ('lse', 'lre'):
            reference = (mother.log_weibull_order_stat_means(n) if method == 'lse'
                         else np.log(-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4))))
            xx, yy = (reference, ld) if method == 'lse' else (ld, reference)
            slope, intercept = np.polyfit(xx, yy, 1)
            sse = float(np.sum((yy-intercept-slope*xx)**2))
            sst = float(np.sum((yy-yy.mean())**2))
            loss = sse/sst
            assert abs(loss-criterion) < 2e-12
            check = dict(gamma=gamma, normalized_residual_loss=loss,
                         correlation_loss=criterion, identity_error=abs(loss-criterion))
            if method == 'lse':
                white_f = (sst/(n-1))/(sse/(n-2))
                derived_f = (n-2)/(n-1)/criterion
                assert abs(white_f-derived_f) <= 1e-9*max(1,abs(white_f))
                check.update(white_f=white_f, derived_f=derived_f)
        elif method == 'mdm':
            a = (-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4)))**(-1/beta)
            pseudo = d*a
            gradient = float(-np.cov(pseudo,a,ddof=1)[0,1]/np.std(pseudo,ddof=1))
            assert abs(gradient-criterion) < 3e-5
            check = dict(gamma=gamma, covariance_gradient=gradient,
                         saved_difference_gradient=criterion, error=abs(gradient-criterion))
        else:
            weights = np.exp(beta*ld-logsumexp(beta*ld))
            shape = (mother.get_weight_j2(n) if method == 'wmle' else 1)/beta + ld.mean()-weights@ld
            assert abs(shape) < 2e-10
            ratio = float(np.exp(logsumexp(beta*ld)-logsumexp((beta-1)*ld)))
            if method == 'wmle':
                position = float(np.mean(1/d)*ratio-mother.get_weight_j3(n,beta))
                assert abs(position-criterion) < 2e-11
                check = dict(gamma=gamma, shape_residual=float(shape),
                             conditional_position_residual=position, saved_position_residual=criterion)
            else:
                direct_ll = float(n*np.log(beta)-n*beta*np.log(eta)+(beta-1)*ld.sum()
                                  -np.exp(beta*(ld-np.log(eta))).sum())
                assert abs(direct_ll-ll) < 1e-9
                score = float(n*(beta/ratio-(beta-1)*np.mean(1/d)))
                assert abs(1000*score/n-criterion) < 2e-10
                h=.001
                plus=mother.profile(x,'mle',gamma+h)
                minus=mother.profile(x,'mle',gamma-h) if gamma>=h else None
                numeric=(plus['ll']-minus['ll'])/(2*h) if minus is not None else (plus['ll']-ll)/h
                assert abs(numeric-score) < 3e-7
                check = dict(gamma=gamma, shape_score_per_observation=float(shape),
                             direct_loglik=direct_ll, saved_loglik=ll,
                             envelope_score=score, likelihood_difference_derivative=numeric,
                             derivative_error=abs(numeric-score))
        checks.append(check)
    return checks


def main():
    inputs = [DATA / name for name in ('样本.json','实际估计.json','逐法过程曲线.json','共同随机分位点.json')]
    before={p.relative_to(ROOT).as_posix():digest(p) for p in inputs}
    source=json.loads(inputs[2].read_text(encoding='utf-8'))
    samples=json.loads(inputs[0].read_text(encoding='utf-8'))
    latent=json.loads(inputs[3].read_text(encoding='utf-8'))
    latent_index={(r['n'],r['sample_id']):r['exponential_order_stats'] for r in latent}
    index={(r['beta'],r['n'],r['sample_id']):r for r in samples}
    results=[]
    for method in METHODS:
        pair,center,eligible=select_pair(source,method)
        cases=[]
        for row in pair:
            sample=index[row['beta'],7,row['sample_id']]
            x=np.array(sample['observations'])
            values=[dict(id=f'G{i+1}',gamma=p[0],value=(p[5]-row['truth'][5]
                    if p[5] is not None else None) if method=='mle' else p[1])
                    for i,p in enumerate(row['points'])]
            cases.append(dict(beta=row['beta'],n=7,sample_id=row['sample_id'],source='paired',
                expanded_from_panel='a' if row['beta']==2 else 'b',
                observations=sample['observations'],latent_E=latent_index[7,row['sample_id']],fit=row['fit'],
                evaluation_points=values,
                true_gamma_point_id=next(p['id'] for p in values if p['gamma']==500),
                returned_gamma_point_id=next(p['id'] for p in values if p['gamma']==row['fit']['gamma_hat']),
                derivation_checks=verify_formula(x,row)))
        assert cases[0]['latent_E']==cases[1]['latent_E']
        results.append(dict(method=method,sample_id=pair[0]['sample_id'],
                            beta5_success_median_gamma=center,eligible_ids=eligible,cases=cases))
    assert all(digest(ROOT/name)==value for name,value in before.items())
    result=dict(task='2026-10-02: derived criteria and literal paired single-case expansions',
        selection_rule='Among n=7 sample ids with successful fits and defined truth/return criteria at both beta=2/5, minimize beta=5 returned gamma distance to the median of all beta=5 successful returns; tie by sample id. Each method uses the same id at both beta values.',
        input_hashes=before,new_samples=0,new_three_parameter_estimates=0,
        single_curves_copied_from_multi_sample_data=True,methods=results)
    (DATA/'配对单例与推导核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({r['method']:dict(sample_id=r['sample_id'],gamma=[c['fit']['gamma_hat'] for c in r['cases']])
                      for r in results},ensure_ascii=False))


if __name__=='__main__':
    main()
