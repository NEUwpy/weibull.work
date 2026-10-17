"""从原结果CSV独立重建样本集合，核对Study04派生统计与PNG指纹。"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT/'python'))
from studies.common.metrics import summarize_standard_errors


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected):
    assert np.isclose(actual, expected, rtol=1e-10, atol=1e-10), (actual, expected)


def main():
    folder = HERE/'分析数据'
    config = json.loads((HERE/'绘图配置.json').read_text(encoding='utf-8'))
    read = lambda name: pd.read_csv(folder/name, float_precision='round_trip')
    metrics = read('参数指标.csv').set_index(['beta', 'n', 'method', 'subset'])
    risk = read('风险统计.csv').set_index(['beta', 'n', 'method', 'factor'])
    common_counts = read('共同有效数.csv').set_index(['beta', 'n'])
    paired = read('共同样本配对误差差.csv').set_index(['beta', 'n', 'method', 'parameter'])
    cases = json.loads((folder/'尾部案例.json').read_text(encoding='utf-8'))
    assert len(metrics) == 560 and len(risk) == 840 and len(paired) == 840
    checked, checked_risks, checked_pairs, checked_cases, kr = 0, 0, 0, 0, 0
    common_total, valid_total, attempts = 0, 0, 0
    methods = [method['id'] for method in config['methods']]
    for beta in config['distribution_beta']:
        for n in config['sample_sizes']:
            frame = pd.read_csv(STUDY/'结果'/f'W{beta:g},1000,500'/'估计结果'/f'n{n}.csv', float_precision='round_trip')
            assert frame['样本编号'].tolist() == list(range(1200))
            masks = {method:frame[f'{method}_状态'].eq('success').to_numpy() for method in methods}
            common = np.all(np.stack(list(masks.values())), axis=0)
            assert int(common_counts.loc[(beta, n), 'common_valid']) == int(common.sum())
            common_total += int(common.sum())
            arrays = {method:frame[[f'{method}_{field}' for field in ['形状估计', '尺度估计', '位置估计']]].to_numpy(dtype=float) for method in methods}
            assert np.array_equal(arrays['MMLE(KR)'][:, 2], frame['观测值1'].to_numpy())
            kr += len(frame)
            for method in methods:
                values, valid = arrays[method], masks[method]
                valid_total += int(valid.sum())
                attempts += len(frame)
                for subset, mask in [('own', valid), ('common', common)]:
                    saved = metrics.loc[(beta, n, method, subset)]
                    assert saved.effective_count == int(mask.sum())
                    for col, (param, truth) in enumerate([('beta', beta), ('eta', 1000.), ('gamma', 500.)]):
                        errors = values[mask, col]-truth
                        expected = summarize_standard_errors(errors)
                        for metric in ['bias', 'sd', 'rmse', 'mae']:
                            close(saved[f'{param}_{metric}'], expected[metric])
                            checked += 1
                        close(saved[f'{param}_median'], np.median(values[mask, col]))
                        close(saved[f'{param}_q95_abs'], np.quantile(np.abs(errors), .95))
                        close(saved[f'{param}_q99_abs'], np.quantile(np.abs(errors), .99))
                        close(saved[f'{param}_bias_mcse'], expected['sd']/np.sqrt(len(errors)))
                        close(saved[f'{param}_rmse']**2, saved[f'{param}_bias']**2 +
                            (len(errors)-1)/len(errors)*saved[f'{param}_sd']**2)
                for factor in config['anomaly_factors']:
                    shape = values[valid, 0]
                    low, high = int((shape <= beta/factor).sum()), int((shape >= beta*factor).sum())
                    saved = risk.loc[(beta, n, method, factor)]
                    assert saved.success == int(valid.sum()) and saved.failure == int((~valid).sum())
                    assert saved.anomaly_low == low and saved.anomaly_high == high
                    assert saved.anomaly_count == low+high
                    close(saved.success_rate, valid.mean())
                    close(saved.anomaly_valid_rate, (low+high)/valid.sum())
                    close(saved.anomaly_attempt_rate, (low+high)/len(frame))
                    close(saved.gamma_zero_valid_rate, np.mean(values[valid, 2] == 0))
                    ci = binomtest(low+high, int(valid.sum())).proportion_ci(method='wilson')
                    close(saved.anomaly_ci_low, ci.low)
                    close(saved.anomaly_ci_high, ci.high)
                    checked_risks += 1
                for col, (param, truth) in enumerate([('beta', beta), ('eta', 1000.), ('gamma', 500.)]):
                    delta = (values[common, col]-truth)**2 - (arrays['MDM-0.1'][common, col]-truth)**2
                    expected = summarize_standard_errors(delta)
                    saved = paired.loc[(beta, n, method, param)]
                    close(saved.mse_difference, expected['bias'])
                    close(saved.difference_mcse, expected['sd']/np.sqrt(common.sum()))
                    checked_pairs += 1
                case = next(row for row in cases if row['beta'] == beta and row['n'] == n and row['method'] == method)
                position = int(case['sample_id'])
                assert valid[position]
                assert np.array_equal(np.array(case['sample']), frame.loc[position, [f'观测值{i}' for i in range(1, n+1)]].to_numpy(dtype=float))
                np.testing.assert_allclose([case['beta_hat'], case['eta_hat'], case['gamma_hat']], values[position], rtol=0, atol=0)
                squares = np.sort((values[valid, 0]-beta)**2)[::-1]
                close((values[position, 0]-beta)**2, squares[0])
                close(case['top1_sse_share'], squares[0]/squares.sum())
                checked_cases += 1
    audit = json.loads((HERE/'图片/绘图核验.json').read_text(encoding='utf-8'))
    assert len(audit['outputs']) == 18 and len(audit['sources']) == 88
    for name, expected in audit['sources'].items():
        assert digest(STUDY/name) == expected
    for name, record in audit['outputs'].items():
        path = HERE/'图片'/name
        assert path.suffix == '.png' and digest(path) == record['sha256']
        with Image.open(path) as image:
            image.verify()
    for path, key in [(HERE/'绘制偏差与稳定性.py', 'program_sha256'), (HERE/'分析现有结果.py', 'analysis_program_sha256'),
                      (HERE/'绘图配置.json', 'config_sha256'), (ROOT/'python/studies/common/metrics.py', 'metric_program_sha256'),
                      (ROOT/'python/methods/mm.py', 'mm_diagnostic_program_sha256')]:
        assert digest(path) == audit[key]
    assert attempts == 336000 and valid_total == 324567
    report = dict(result='passed', method_attempts=attempts, valid_estimates=valid_total,
        parameter_metrics_checked=checked, risk_groups_checked=checked_risks,
        paired_groups_checked=checked_pairs, tail_cases_checked=checked_cases,
        kr_minimum_construction_checked=kr, common_valid_samples=common_total,
        source_files_unchanged=len(audit['sources']), png_verified=len(audit['outputs']),
        checker_sha256=digest(Path(__file__)))
    (folder/'独立分析核对.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
