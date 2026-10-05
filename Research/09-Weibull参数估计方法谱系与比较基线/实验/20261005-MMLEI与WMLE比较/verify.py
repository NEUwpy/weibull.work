"""Independent equation checks, paper example, unit and grid sensitivity."""
import argparse
import json
from pathlib import Path
import re

import numpy as np
from scipy.optimize import root
from scipy.special import logsumexp

from run import HERE, REPO, CONFIG, fit_cw_i, register
from studies.common.sample import generate_sample
from studies.common.runner import run_method

LIB = Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法')


def equations(x, estimate):
    b, e, g = estimate
    logs = np.log(x - g)
    powers = np.exp(b * (logs - logs.max()))
    return np.array([b * (np.dot(powers, logs) / powers.sum() - logs.mean()) - 1,
                     (logsumexp(b * logs) - np.log(len(x))) / b - np.log(e),
                     b * np.log(x.min() - g) - b * np.log(e)
                     - np.log(np.log1p(1 / len(x)))])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', action='store_true')
    args = parser.parse_args()
    if args.results:
        verify_results()
        return
    register()
    text = (LIB / '182-091-pdf原文.md').read_text(encoding='utf-8')
    table = text.split('**TABLE V**')[1].split('$n = 100')[0]
    observations = []
    for line in table.splitlines():
        if re.match(r'\| \d+ \|', line):
            observations.extend(float(v) for v in line.split('|')[2].split(','))
    assert len(observations) == 100
    x = np.sort(observations)
    fitted, info = fit_cw_i(tuple(x), True)
    assert fitted is not None, info
    expected = np.array([1.615, 1.028, .042])  # Table VI, PDF p23 / printed2652
    assert np.max(np.abs(np.array(fitted) - expected)) < .0006, (fitted, expected)
    assert np.max(np.abs(equations(x, fitted))) < 1e-8
    checks = []
    for b in [1.5, 2.0, 3.0, 5.0]:
        for n in [7, 10, 15, 20, 50]:
            for rid in [0, 1, 2]:
                raw = generate_sample(b, 1000.0, 1000.0, n, rid, seed=CONFIG['seed_namespace'])
                sample = raw / CONFIG['unit_divisor']
                estimate, diag = fit_cw_i(tuple(sample), True)
                dense, _ = fit_cw_i(tuple(sample), True, grid_size=385)
                assert (estimate is None) == (dense is None)
                if estimate is not None:
                    assert np.max(np.abs(np.array(estimate) - dense)) < 1e-7
                    residual = equations(sample, estimate)
                    assert np.max(np.abs(residual)) < 1e-8
                    # Independent simultaneous solve; does not repeat profile code.
                    solved = root(lambda q: equations(sample, (np.exp(q[0]), np.exp(q[1]),
                        sample.min() - np.exp(q[2]))),
                        [np.log(estimate[0]), np.log(estimate[1]), np.log(sample.min()-estimate[2])])
                    assert np.max(np.abs(solved.fun)) < 1e-8
                checks.append({'beta': b, 'n': n, 'repeat_id': rid,
                               'success': estimate is not None, 'status': diag['status']})
    # Shared pipeline rejects invalid observations and cannot invent parameters.
    assert not run_method('cw_i_nonnegative', [0, 1, 2])['converged']
    assert not run_method('cw_i_nonnegative', [1, 1, 1])['converged']
    result = {'paper_example': {'estimated': fitted, 'published': expected.tolist(),
                  'max_equation_residual': float(np.max(np.abs(equations(x, fitted))))},
              'grid_and_independent_solver_checks': checks,
              'checks_passed': len(checks) + 3}
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print({'checks_passed': result['checks_passed'], 'paper_example': fitted})


def verify_results():
    import pandas as pd
    from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3
    data = pd.read_csv(HERE/'per_sample.csv.gz')
    greatest_cw, greatest_wmle = 0.0, 0.0
    checked = 0
    for key, part in data.groupby(['beta','eta','gamma','n','repeat_id']):
        b, e, g, n, rid = key
        raw = generate_sample(float(b),float(e),float(g),int(n),int(rid),seed=CONFIG['seed_namespace'])
        x = raw / CONFIG['unit_divisor']
        for row in part[part.status.eq('success')].itertuples():
            estimate = (row.beta_hat,row.eta_hat/1000,row.gamma_hat/1000)
            if row.method_variant.startswith('cw'):
                residual = float(np.max(np.abs(equations(x, estimate))))
                assert residual < 1e-8, (key,row.method_variant,residual)
                greatest_cw = max(greatest_cw,residual)
            else:
                bb, ee, gg = estimate
                z = x-gg
                logs = np.log(z)
                p = np.exp(bb*(logs-logs.max()))
                r = np.array([get_weight_j2(int(n))/bb+logs.mean()-np.dot(p,logs)/p.sum(),
                    np.mean(1/z)*p.sum()/np.sum(p/z)-get_weight_j3(int(n),bb)])
                assert float(np.sum(r*r)) <= 1.0001e-8
                eta_equation = (logsumexp(bb*logs)-np.log(n*get_weight_j1(int(n))))/bb-np.log(ee)
                assert abs(eta_equation)<1e-8
                greatest_wmle=max(greatest_wmle,float(np.sum(r*r)))
            checked+=1
    unresolved = data[data.method_variant.eq('cw_i_paper_domain') & data.status.ne('success')]
    # Fixed, recorded selection of failures; substantially denser location scan.
    selected = unresolved.groupby(['beta','n'],group_keys=False).head(1)
    for row in selected.itertuples():
        x=generate_sample(float(row.beta),float(row.eta),float(row.gamma),int(row.n),int(row.repeat_id),
                          seed=CONFIG['seed_namespace'])/1000
        fitted, diag=fit_cw_i(tuple(x),True,grid_size=769)
        assert fitted is None,(row.cell_id,row.repeat_id,diag)
    outcome={'successful_estimates_checked':checked,'max_cw_equation_residual':greatest_cw,
             'max_wmle_equation_squared_residual':greatest_wmle,
             'dense_failure_rechecks':len(selected),'all_passed':True}
    (HERE/'final_verification.json').write_text(json.dumps(outcome,indent=2),encoding='utf-8')
    print(outcome)


if __name__ == '__main__':
    main()
