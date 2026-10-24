"""从正式存档核对选参、固定位置诊断和失败状态；不抽样或重新估计。"""
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
FROZEN = STUDY / '程序/计算实现-20261016'
sys.path.insert(0, str(FROZEN))
from methods.lse import log_weibull_order_stat_means


def conditional_lse(sample, location):
    """沿冻结LSE的White回归，比较指定位置下的同一判据。"""
    n = len(sample)
    reference = log_weibull_order_stat_means(n)
    z = np.log(np.asarray(sample) - location)
    slope = float(np.sum((reference-reference.mean())*(z-z.mean())) /
                  np.sum((reference-reference.mean())**2))
    intercept = float(z.mean()-slope*reference.mean())
    residual = float(np.sum((z-intercept-slope*reference)**2) /
                     np.sum((z-z.mean())**2))
    return dict(gamma=float(location), beta=1/slope, eta=float(np.exp(intercept)),
                relative_residual=residual, fisher_ratio=(n-2)/(n-1)/residual)


def main():
    attempts, failures = Counter(), Counter()
    reasons = defaultdict(Counter)
    cells = defaultdict(lambda: [0, 0])
    example = {}
    with gzip.open(STUDY/'结果/求解明细.csv.gz', 'rt', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            method = row['method_id']
            attempts[method] += 1
            key = (method, float(row['beta']), int(row['n']))
            cells[key][0] += 1
            if row['status'] != 'success':
                failures[method] += 1
                cells[key][1] += 1
                extra = json.loads(row['extra'])
                info = extra.get('solution_info', {})
                reason = str(extra.get('raw_status', info.get('status', row['status'])))
                reasons[method][reason] += 1
                if method not in example:
                    example[method] = {k:row[k] for k in ['beta','n','repeat_id','status']}
                    example[method]['extra'] = extra
    assert sum(attempts.values()) == 336000
    assert sum(failures.values()) == 11433

    with (STUDY/'结果/W5,1000,500/估计结果/n7.csv').open(encoding='utf-8-sig', newline='') as f:
        pairs = []
        for row in csv.DictReader(f):
            if row['样本编号'] not in ['0', '34']:
                continue
            sample = [float(row[f'观测值{i}']) for i in range(1,8)]
            selected = conditional_lse(sample, float(row['LSE_位置估计']))
            assert np.isclose(selected['beta'],float(row['LSE_形状估计']),rtol=1e-9)
            assert np.isclose(selected['eta'],float(row['LSE_尺度估计']),rtol=1e-9)
            pairs.append(dict(repeat_id=int(row['样本编号']), sample_min=sample[0],
                              at_true_location=conditional_lse(sample,500), at_selected_location=selected))

    fixed = defaultdict(lambda: [[],[]])
    with (STUDY/'结果呈现/分析数据/第三章固定真位置对照.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if int(row['n']) in [50,7]:
                lists = fixed[(row['method'],int(row['n']))]
                lists[0].append(float(row['full_shape']))
                lists[1].append(float(row['fixed_gamma_shape']))
    fixed_summary = []
    for (method,n), arrays in sorted(fixed.items()):
        assert len(arrays[0]) == len(arrays[1]) == 1200
        measures = [dict(bias=float(np.mean(a)-5),sd=float(np.std(a,ddof=1))) for a in arrays]
        fixed_summary.append(dict(method=method,n=n,repeats=1200,full=measures[0],fixed_true_gamma=measures[1]))

    report = dict(scope='Formal 40 conditions; existing estimates and saved fixed-true-location diagnostic only. No new estimator calls or Weibull samples.',
                  attempts=dict(attempts),failures=dict(failures),
                  recorded_failure_status={m:dict(c) for m,c in reasons.items()},
                  first_failure_examples=example,
                  endpoint_failure_rates=[dict(method=m,n=n,attempts=sum(v[0] for (mm,b,nn),v in cells.items() if mm==m and nn==n),
                                               failures=sum(v[1] for (mm,b,nn),v in cells.items() if mm==m and nn==n))
                                          for m in attempts for n in [50,7]],
                  lse_paired_cases=dict(truth=[5,1000,500],n=7,cases=pairs),
                  fixed_gamma_diagnostic=dict(truth=[5,1000,500],gamma_fixed=500,
                                              interpretation='Diagnostic intervention using true gamma; not an available estimator or an additive causal contribution.',
                                              rows=fixed_summary))
    (HERE/'第三章选参与返回状态核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='first_failure_examples'},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
