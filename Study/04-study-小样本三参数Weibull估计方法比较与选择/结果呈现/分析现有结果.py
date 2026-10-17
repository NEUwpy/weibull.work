"""Study04已保存估计的描述性再分析；不调用估计器，不改变成功状态。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from studies.common.metrics import summarize_standard_errors
from methods.mm import sample_weibull_moment, solve_from_weibull_moments


def interval(count, total):
    bounds = binomtest(int(count), int(total)).proportion_ci(method='wilson')
    return float(bounds.low), float(bounds.high)


def analyze_cell(beta, n, frame, arrays, valid_masks, config, analysis):
    common = np.logical_and.reduce(list(valid_masks.values()))
    analysis['common_counts'].append(dict(beta=beta, n=n, total=len(frame), common_valid=int(common.sum())))
    for method in config['methods']:
        name = method['id']
        valid = valid_masks[name]
        values = arrays[name]
        assert np.isfinite(values[valid]).all()
        for subset, mask in [('own', valid), ('common', common)]:
            row = dict(beta=beta, eta=1000., gamma=500., n=n, method=name,
                       subset=subset, total=len(frame), effective_count=int(mask.sum()))
            for col, (param, truth) in enumerate([('beta', beta), ('eta', 1000.), ('gamma', 500.)]):
                estimates = values[mask, col]
                errors = estimates-truth
                stats = summarize_standard_errors(errors)
                for metric in ['bias', 'sd', 'rmse', 'mae']:
                    row[f'{param}_{metric}'] = stats[metric]
                row[f'{param}_median'] = float(np.median(estimates))
                row[f'{param}_q95_abs'] = float(np.quantile(np.abs(errors), .95))
                row[f'{param}_q99_abs'] = float(np.quantile(np.abs(errors), .99))
                row[f'{param}_bias_mcse'] = stats['sd']/np.sqrt(len(errors))
                row[f'{param}_rmse_mcse_delta'] = float(np.std(errors**2, ddof=1) /
                    np.sqrt(len(errors))/(2*stats['rmse'])) if stats['rmse'] else 0.
            analysis['metrics'].append(row)
        for col, (param, truth) in enumerate([('beta', beta), ('eta', 1000.), ('gamma', 500.)]):
            differences = (values[common, col]-truth)**2 - (arrays['MDM-0.1'][common, col]-truth)**2
            delta = summarize_standard_errors(differences)
            analysis['paired'].append(dict(beta=beta, n=n, method=name, reference='MDM-0.1',
                parameter=param, common_valid=int(common.sum()), mse_difference=delta['bias'],
                difference_mcse=delta['sd']/np.sqrt(common.sum())))
        estimates = values[valid, 0]
        for factor in config['anomaly_factors']:
            low = int(np.sum(estimates <= beta/factor))
            high = int(np.sum(estimates >= beta*factor))
            count = low+high
            lo, hi = interval(count, valid.sum())
            success_lo, success_hi = interval(valid.sum(), len(frame))
            analysis['risk'].append(dict(beta=beta, n=n, method=name, factor=factor,
                total=len(frame), success=int(valid.sum()), failure=int((~valid).sum()),
                success_rate=float(valid.mean()), success_ci_low=success_lo, success_ci_high=success_hi,
                anomaly_low=low, anomaly_high=high, anomaly_count=count,
                anomaly_valid_rate=count/int(valid.sum()), anomaly_attempt_rate=count/len(frame),
                anomaly_ci_low=lo, anomaly_ci_high=hi,
                gamma_zero_count=int(np.sum(values[valid, 2] == 0)),
                gamma_zero_valid_rate=float(np.mean(values[valid, 2] == 0))))
        # 仅用于解释平方误差是否被极少数记录支配，不删除这些记录。
        ids = np.flatnonzero(valid)
        square_errors = (values[valid, 0]-beta)**2
        ordered = np.argsort(square_errors)[::-1]
        position = ids[ordered[0]]
        sse = float(square_errors.sum())
        case = dict(beta=beta, n=n, method=name, sample_id=int(frame.iloc[position]['样本编号']),
            beta_hat=float(values[position, 0]), eta_hat=float(values[position, 1]),
            gamma_hat=float(values[position, 2]), beta_median=float(np.median(estimates)),
            beta_maximum=float(estimates.max()), top1_sse_share=float(square_errors[ordered[0]]/sse),
            top5_sse_share=float(square_errors[ordered[:5]].sum()/sse))
        case['paired_estimates'] = {m['id']: dict(status='success' if valid_masks[m['id']][position] else 'failure',
            estimates=[float(v) if np.isfinite(v) else None for v in arrays[m['id']][position]]) for m in config['methods']}
        case['sample'] = frame.loc[position, [f'观测值{i}' for i in range(1, n+1)]].tolist()
        if name == 'MM':
            moments = [sample_weibull_moment(np.asarray(case['sample']), k) for k in [1, 2, 4]]
            solved = solve_from_weibull_moments(*moments)
            assert np.isclose(solved[0], case['beta_hat'], rtol=1e-10)
            d12, d24 = moments[0]-moments[1], moments[1]-moments[2]
            case['construction'] = dict(m1=moments[0], m2=moments[1], m4=moments[2],
                d12=d12, d24=d24, ratio=d12/d24, log_ratio=float(np.log(d12/d24)),
                raw_beta=solved[0], raw_gamma=solved[1], raw_eta=solved[2])
        analysis['tail_cases'].append(case)


def export_analysis(analysis, folder, config):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(analysis['metrics'])
    risk = pd.DataFrame(analysis['risk'])
    counts = pd.DataFrame(analysis['common_counts'])
    assert len(metrics) == 560 and len(counts) == 40
    assert metrics.effective_count.gt(1).all()
    assert not metrics.duplicated(['beta', 'n', 'method', 'subset']).any()
    ranges = []
    for label, lower, upper in [('1.5—2.5', 1.5, 2.5), ('3—5', 3., 5.), ('1.5—5', 1.5, 5.)]:
        selected = metrics[metrics.beta.between(lower, upper)]
        for (subset, n, method), group in selected.groupby(['subset', 'n', 'method']):
            risk_rows = risk[(risk.factor == 3) & risk.beta.between(lower, upper) & (risk.n == n) & (risk.method == method)]
            ranges.append(dict(range=label, subset=subset, n=int(n), method=method, cells=len(group),
                beta_nrmse=float(np.sqrt(np.mean((group.beta_rmse/group.beta)**2))),
                eta_rmse=float(np.sqrt(np.mean(group.eta_rmse**2))),
                gamma_rmse=float(np.sqrt(np.mean(group.gamma_rmse**2))),
                success_mean=float(risk_rows.success_rate.mean()), success_worst=float(risk_rows.success_rate.min()),
                anomaly_mean=float(risk_rows.anomaly_valid_rate.mean()), anomaly_worst=float(risk_rows.anomaly_valid_rate.max())))
    tables = {'参数指标.csv': metrics, '风险统计.csv': risk, '共同有效数.csv': counts,
              '范围比较.csv': pd.DataFrame(ranges), '共同样本配对误差差.csv': pd.DataFrame(analysis['paired'])}
    for name, table in tables.items():
        table.to_csv(folder/name, index=False, encoding='utf-8-sig', float_format='%.17g')
    (folder/'尾部案例.json').write_text(json.dumps(analysis['tail_cases'], ensure_ascii=False,
        indent=2, allow_nan=False)+'\n', encoding='utf-8')
    checks = {
        'Simpson': '按beta与n逐条件比较；范围汇总等权；n50单列',
        'ecological': '条件平均不解释为每份样本的保证',
        'Berkson': '共同有效子集仅作敏感性核对，不代表全部样本',
        'collider': '成功条件化可能改变比较结果，不解释为方法因果效应',
        'base_rate': '同时保存成功、失败、异常次数与两种分母',
        'regression_to_mean': '无极端筛选后重测或改进效果主张',
        'survivorship': '有效样本比较与成功率并列；共同有效集合另存',
        'look_elsewhere': '全40条件保留，不作显著性筛选',
        'forking_paths': '阈值2、3、5倍均保存；保留极端输出',
        'causation': '仅分析表现及联动，机制需另有证据',
        'reverse_causality': '不作因果方向主张',
    }
    (folder/'分析核验.json').write_text(json.dumps(dict(result='ANALYZED', checks=checks,
        fallacy_checks='11/11', main_n=[7, 10, 15, 20], reference_n=50,
        anomaly_rule='success and (beta_hat>=factor*beta or beta_hat<=beta/factor)',
        range_rule='条件等权平均标准化形状MSE后开方；尺度、位置RMSE不归一化；描述性分组，未经独立选择验证',
        table_rows={name:len(table) for name,table in tables.items()}), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return metrics, risk, counts
