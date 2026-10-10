"""Rebuild the reviewed report and check its sample-to-criterion argument.

Reuse the report mother and archived diagnostics. No sampling, estimation or
redrawing. Keep this task's verification record in the program directory.
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
from scipy.special import logsumexp

from 计算逐法过程曲线 import mother


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '结果' / '中间数据'
REPORT = ROOT.parent / '报告1：高形状参数下的估计偏移.md'
RECORD = Path(__file__).with_suffix('.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seal = json.loads((DATA / '封存清单.json').read_text(encoding='utf-8'))
    unchanged = {**seal['input_hashes'], **seal['output_hashes']}
    unchanged.update({k: v for k, v in seal['code_hashes'].items()
                      if k.startswith('程序/依赖快照/')})
    for name, expected in unchanged.items():
        assert digest(ROOT / name) == expected, name
    chapter1 = REPORT.read_text(encoding='utf-8').split('## 第二章')[0]
    spec = importlib.util.spec_from_file_location('reviewed_report', ROOT / '程序' / '生成报告.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.main()
    text = REPORT.read_text(encoding='utf-8')
    assert text == generator.REPORT_TEXT
    assert text.split('## 第二章')[0] == chapter1
    figures = re.findall(r'^!\[图(\d+)[^\]]*\]\(([^\n]+)\)', text, re.M)
    expected_files = ['图1_原案例参数分布.png', '图2_样本与真实起点.png',
                      '图2_样本与分布相容.png', '图3_MDM六格机制.png',
                      '图4_LSE六格机制.png', '图5_LRE六格机制.png',
                      '图6_WMLE六格机制.png', '图7_MLE六格机制.png',
                      '图8_寿命分布与分位点.png']
    assert [int(n) for n, _ in figures] == list(range(1, 10))
    assert [Path(p).name for _, p in figures] == expected_files
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(n) for n in range(1, 10)]
    assert text.index('Q(p)=') < text.index('![图3') < text.index('### 2.1 MDM')
    assert text.count('Q(p)=\\gamma+') == 2
    assert '### 2.6 寿命分位的偏差' in text

    samples = json.loads((DATA / '样本.json').read_text(encoding='utf-8'))
    corr_error, checked_samples, remainder_checks = 0., 0, 0
    for row in samples:
        if row['beta'] not in (2, 5):
            continue
        x = np.array(row['observations'])
        reference = np.log(-np.log1p(-(np.arange(1, len(x)+1)-.3)/(len(x)+.4)))
        original = np.corrcoef(x, reference)[0, 1]
        for gamma in (0., 500.):
            center = x.mean()-gamma
            u = (x-x.mean())/center
            affine = np.log(center)+u
            corr_error = max(corr_error, abs(np.corrcoef(affine, reference)[0, 1]-original))
            # The log series gives this remainder bound for |u| < 1.
            radius = float(np.max(np.abs(u)))
            if radius < 1:
                error = np.abs(np.log(x-gamma)-affine)
                bound = u*u/(2*(1-radius))
                assert np.all(error <= bound+1e-14)
                remainder_checks += 1
        checked_samples += 1
    assert checked_samples == 200 and corr_error < 2e-13

    process = json.loads((DATA / '逐法过程曲线.json').read_text(encoding='utf-8'))
    wmle = {(r['beta'], r['n'], r['sample_id']): r for r in process['curves']
            if r['source'] == 'paired' and r['method'] == 'wmle'}
    proportional_error, paired_checks = 0., 0
    for n in (7, 15):
        for sid in range(1, 51):
            beta2, beta5 = [wmle[b, n, sid]['truth'][2] for b in (2, 5)]
            if beta2 is not None and beta5 is not None:
                proportional_error = max(proportional_error, abs(beta5/(2.5*beta2)-1))
                paired_checks += 1
    assert paired_checks > 0 and proportional_error < 1e-8

    pairs = json.loads((DATA / '配对单例与推导核验.json').read_text(encoding='utf-8'))
    example = next(r for r in pairs['methods'] if r['method'] == 'wmle')
    traces = []
    for case in example['cases']:
        beta = case['fit']['conditional_beta']
        d = np.array(case['observations'])-500.
        product = float(np.mean(1/d)*np.exp(logsumexp(beta*np.log(d))-
                                            logsumexp((beta-1)*np.log(d))))
        target = float(mother.get_weight_j3(case['n'], beta))
        assert abs(product-target-case['fit']['criterion_at_truth']) < 2e-11
        traces.append(dict(generating_beta=case['beta'], conditional_beta=beta,
                           product_at_true_gamma=product, calibration_target=target,
                           residual_at_true_gamma=product-target,
                           returned_gamma=case['fit']['gamma_hat']))
    assert round(traces[0]['conditional_beta'], 2) == 3.52
    assert round(traces[1]['conditional_beta'], 2) == 8.79
    assert round(traces[0]['residual_at_true_gamma'], 3) == -.018
    assert round(traces[1]['residual_at_true_gamma'], 3) == -.108

    for name, expected in unchanged.items():
        assert digest(ROOT / name) == expected, name
    result = dict(task='2026-10-10: sample constraints, compensation, criterion selection',
                  report_sha256=digest(REPORT), generator_sha256=digest(ROOT/'程序'/'生成报告.py'),
                  chapter1_unchanged=True, scientific_and_figure_files_unchanged=len(unchanged),
                  main_figure_order=[dict(number=int(n), file=Path(p).name) for n, p in figures],
                  regression_expansion=dict(samples=checked_samples,
                                            affine_correlation_max_error=float(corr_error),
                                            log_series_remainder_checks=remainder_checks),
                  wmle_conditional_shape=dict(paired_checks=paired_checks,
                                              proportional_relative_error=float(proportional_error),
                                              example_id=example['sample_id'], traces=traces),
                  new_random_draws=0, new_estimates=0, redrawn_figures=0,
                  bounds=['Quantile and log-distance expansions are local approximations.',
                          'Compensation does not prescribe a common bias direction.',
                          'WMLE table-endpoint and calibration contributions are not separated.'])
    RECORD.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ('scientific_and_figure_files_unchanged',
                                           'regression_expansion', 'wmle_conditional_shape',
                                           'new_estimates', 'redrawn_figures')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
