"""Verify an illustrative local quantile match; no sampling or estimation.

The second parameter tuple is constructed to preserve the central quantile
and its slope in z=log(-log(1-p)); it is not a fitted result.
"""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / '结果' / '中间数据'
TRUTH = (5.0, 1000.0, 500.0)
LOCAL_MATCH = (2.5, 500.0, 1000.0)


def quantile_at_z(z, parameters):
    beta, eta, gamma = parameters
    return gamma + eta * math.exp(z / beta)


def main():
    cases = []
    for name, parameters in [('generating_distribution', TRUTH),
                             ('constructed_local_match', LOCAL_MATCH)]:
        beta, eta, gamma = parameters
        center, slope = gamma + eta, eta / beta
        h = 1e-4
        numeric_slope = (quantile_at_z(h, parameters) -
                         quantile_at_z(-h, parameters)) / (2 * h)
        assert quantile_at_z(0, parameters) == center
        assert abs(numeric_slope - slope) < 1e-6
        quantiles = []
        for p in (.01, .1, .5, -math.expm1(-1), .9):
            z = math.log(-math.log1p(-p))
            q = quantile_at_z(z, parameters)
            quantiles.append(dict(p=p, z=z, quantile=q))
        cases.append(dict(name=name, parameters_beta_eta_gamma=parameters,
                          central_quantile=center, central_slope=slope,
                          central_curvature=eta / beta**2,
                          finite_difference_slope_error=abs(numeric_slope-slope),
                          quantiles=quantiles))
    assert cases[0]['central_quantile'] == cases[1]['central_quantile'] == 1500
    assert cases[0]['central_slope'] == cases[1]['central_slope'] == 200
    assert cases[0]['central_curvature'] != cases[1]['central_curvature']
    result = dict(script='程序/核验局部分位补偿.py',
                  purpose='Exact local identities and a constructed illustration, not an estimator comparison.',
                  formula='Q(z)=gamma+eta*exp(z/beta); Q(0)=gamma+eta; Q_prime(0)=eta/beta',
                  approximation_scope='First-order expansion near z=0; tail quantiles use the exact expression.',
                  new_samples=0, new_fits=0, cases=cases)
    (DATA / '局部分位补偿核验.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(central_quantile=1500, central_slope=200,
                         curvature=[r['central_curvature'] for r in cases],
                         new_samples=0, new_fits=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
