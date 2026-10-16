"""Validate revised solvers on fixed archived samples; never rewrite old data."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from 存储路径 import ARCHIVE
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from methods import wmle
from methods.profile_solvers import SOLVER_VERSION
from studies.common.runner import run_method


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def likelihood(x, beta, eta, gamma):
    d = x - gamma
    return float(len(x) * (np.log(beta) - beta * np.log(eta))
                 + (beta - 1) * np.log(d).sum() - ((d / eta) ** beta).sum())


def verify_equations(x, beta, eta, gamma):
    """Direct paper equations, independent of the conditional-profile helpers."""
    d = x - gamma
    t = np.log(d)
    t1 = wmle.get_weight_j2(len(x)) / beta + t.mean() - np.sum(t * d**beta) / np.sum(d**beta)
    t2 = np.mean(1 / d) * np.sum(d**beta) / np.sum(d**(beta - 1)) - wmle.get_weight_j3(len(x), beta)
    scale = (np.mean(d**beta) / wmle.get_weight_j1(len(x))) ** (1 / beta)
    assert np.isclose(eta, scale, rtol=1e-11)
    residual = float(t1*t1 + t2*t2)
    assert residual <= 1e-8
    return residual


def check_old_success(job):
    """Compare saved successful parameters with a fresh fit, without truth-based selection."""
    x = np.asarray(job.pop('sample'), float)
    old = np.asarray(job['old_estimate'], float)
    result = run_method(job['method'], x)
    record = dict(**job, new_success=result['converged'])
    if not result['converged']:
        record['failure'] = result['extra']
        return record
    new = np.array([result[p + '_hat'] for p in ['beta', 'eta', 'gamma']])
    assert new[0] > 0 and new[1] > 0 and 0 <= new[2] < x[0]
    record.update(new_estimate=new.tolist(), absolute_difference=np.abs(new-old).tolist(),
                  parameters_match=bool(np.allclose(new, old, rtol=1e-6, atol=1e-5)),
                  candidate_count=result['extra']['solution_info']['candidate_count'],
                  approximate_boundary_root=result['extra']['solution_info'].get('approximate_boundary_root', False))
    if job['method'] == 'wmle':
        record['new_squared_residual'] = verify_equations(x, *new)
        record['old_squared_residual'] = verify_equations(x, *old)
    else:
        ll = likelihood(x, *new)
        record['ll_change_from_old'] = ll - likelihood(x, *old)
        for name, estimate in [('old', old), ('new', new)]:
            b, e, g = estimate
            d = x - g
            logz = np.log(d / e)
            power = np.exp(b * logz)
            shape_score = 1 + b * (logz.mean() - np.mean(power * logz))
            scale_score = b * (power.mean() - 1)
            location_score = float((-(b-1)/d + b*power/d).mean())
            # Interior stationary point or a one-sided maximum at gamma=0.
            location_error = (abs(location_score) if g > 1e-5 else max(0., location_score)) * (x[0]-g)
            record[name + '_score_error'] = float(max(abs(shape_score), abs(scale_score), location_error))
        record['new_valid_stationary_point'] = record['new_score_error'] < 1e-5
        record['old_valid_stationary_point'] = record['old_score_error'] < 1e-5
        # The selected solution should not admit an obvious coordinate ascent.
        for index in range(3):
            step = 1e-5 * max(abs(new[index]), 1.)
            for direction in [-1, 1]:
                trial = new.copy()
                trial[index] += direction * step
                if trial[0] < 1 or trial[1] <= 0 or not 0 <= trial[2] < x[0]:
                    continue
                assert likelihood(x, *trial) <= ll + 1e-8
    return record


def verify_old_successes():
    """Twenty old successes per method and design cell, including extreme estimates."""
    backup = STUDY / '程序/历史版本/2026-10-16-求解更新前'
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        assert digest(backup / item['path']) == item['sha256']
    input_hashes, jobs = {}, []
    for shape in [1.5, 2, 3, 5]:
        batch = ROOT / 'Research/09-Weibull参数估计方法谱系与比较基线/实验' / f'W({shape},1000,500)'
        source = json.loads((batch / '程序/manifest.json').read_text(encoding='utf-8'))
        for item in source['files']:
            if item['path'].startswith('数据/'):
                assert digest(batch / item['path']) == item['sha256']
                input_hashes[str((batch/item['path']).relative_to(ROOT))] = item['sha256']
        for method in ['mle', 'wmle']:
            relative = f'python/methods/{method}.py'
            assert digest(batch/'程序/source_snapshot'/relative) == digest(backup/relative)
        samples = pd.read_csv(batch/'数据/样本.csv', float_precision='round_trip').set_index(['n', 'block', 'repeat_id'])
        estimates = pd.read_csv(batch/'数据/估计明细.csv', float_precision='round_trip')
        estimates = estimates[(estimates['状态'] == '成功') & estimates['方法'].isin(['MLE', 'WMLE'])]
        for (method, n), cell in estimates.groupby(['方法', 'n']):
            cell = cell.sort_values(['block', 'repeat_id']).reset_index(drop=True)
            # Five extremes plus fifteen records spread over all twelve blocks.
            chosen = list(dict.fromkeys([int(cell[p].idxmin()) for p in ['β估计', 'η估计']]
                     + [int(cell[p].idxmax()) for p in ['β估计', 'η估计', 'γ估计']]
                     + np.linspace(0, len(cell)-1, 15, dtype=int).tolist()))
            for index in range(len(cell)):
                if len(chosen) >= 20:
                    break
                if index not in chosen:
                    chosen.append(index)
            assert len(chosen) == 20
            for index in chosen:
                row = cell.iloc[index]
                key = (int(n), int(row.block), int(row.repeat_id))
                sample = samples.loc[key, [f'x({i})' for i in range(1, int(n)+1)]].to_numpy(dtype=float)
                jobs.append(dict(method=method.lower(), truth_shape=shape, n=key[0], block=key[1], repeat_id=key[2],
                                 sample=sample.tolist(), sample_sha256=digest_bytes(sample.tobytes()),
                                 old_estimate=[float(row[p+'估计']) for p in ['β', 'η', 'γ']]))
    records = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(check_old_success, job) for job in jobs]
        for future in as_completed(futures):
            records.append(future.result())
            if len(records) % 100 == 0:
                print(f'Checked {len(records)}/{len(jobs)} old successful estimates', flush=True)
    records.sort(key=lambda r: (r['method'], r['truth_shape'], r['n'], r['block'], r['repeat_id']))
    summary = {}
    for method in ['mle', 'wmle']:
        rows = [r for r in records if r['method'] == method]
        success = [r for r in rows if r['new_success']]
        summary[method] = dict(checked=len(rows), new_success=len(success),
                               matching_parameters=sum(r['parameters_match'] for r in success),
                               max_absolute_difference=np.max([r['absolute_difference'] for r in success], axis=0).tolist(),
                               approximate_boundary_roots=sum(r['approximate_boundary_root'] for r in success))
        if method == 'mle':
            summary[method].update(minimum_ll_change=min(r['ll_change_from_old'] for r in success),
                                   maximum_ll_change=max(r['ll_change_from_old'] for r in success),
                                   old_valid_stationary_points=sum(r['old_valid_stationary_point'] for r in success),
                                   new_valid_stationary_points=sum(r['new_valid_stationary_point'] for r in success))
        else:
            summary[method].update(maximum_old_squared_residual=max(r['old_squared_residual'] for r in success),
                                   maximum_new_squared_residual=max(r['new_squared_residual'] for r in success))
    report = dict(solver_version=SOLVER_VERSION,
                  scope='20 old successes per method per cell: 15 across the ordered blocks plus five extreme estimates, filling duplicates to 20; 20 cells, two methods',
                  tolerance=dict(rtol=1e-6, atol=1e-5), parameters=['beta', 'eta', 'gamma'],
                  original_file_hashes=input_hashes, backup_manifest_sha256=digest(backup/'manifest.json'),
                  source_hashes={p: digest(ROOT/p) for p in ['python/methods/mle.py', 'python/methods/wmle.py',
                       'python/methods/profile_solvers.py', 'python/methods/conditional_profiles.py', 'python/methods/j3_weights.tsv']},
                  summary=summary, records=records)
    output = ARCHIVE/'旧成功结果对照-20261016.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def main():
    backup = STUDY / '程序/历史版本/2026-10-16-求解更新前'
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        assert digest(backup / item['path']) == item['sha256']
    records, input_hashes = [], {}
    for shape in [1.5, 2, 3, 5]:
        batch = ROOT / 'Research/09-Weibull参数估计方法谱系与比较基线/实验' / f'W({shape},1000,500)'
        original = json.loads((batch / '程序/manifest.json').read_text(encoding='utf-8'))
        for item in original['files']:
            if item['path'].startswith('数据/'):
                assert digest(batch / item['path']) == item['sha256']
                input_hashes[str((batch / item['path']).relative_to(ROOT))] = item['sha256']
        samples = pd.read_csv(batch / '数据/样本.csv', float_precision='round_trip')
        estimates = pd.read_csv(batch / '数据/估计明细.csv', float_precision='round_trip')
        keys = set()
        for n, group in samples.groupby('n'):
            for row in group.sort_values(['block', 'repeat_id']).head(5).itertuples():
                keys.add((int(n), int(row.block), int(row.repeat_id)))
        # Include the four previously diagnosed failures regardless of their ID.
        failure = estimates[(estimates.n == 7) & (estimates['方法'] == 'WMLE') & (estimates['状态'] == '失败')].iloc[0]
        keys.add((7, int(failure.block), int(failure.repeat_id)))
        for n, block, repeat in sorted(keys):
            row = samples[(samples.n == n) & (samples.block == block) & (samples.repeat_id == repeat)].iloc[0]
            x = row[[f'x({i})' for i in range(1, n+1)]].to_numpy(dtype=float)
            for method in ['mle', 'wmle']:
                old = estimates[(estimates.n == n) & (estimates.block == block)
                                & (estimates.repeat_id == repeat) & (estimates['方法'] == method.upper())].iloc[0]
                result = run_method(method, x)
                info = result['extra'].get('solution_info', {})
                record = dict(truth_shape=shape, n=n, block=block, repeat_id=repeat, method=method,
                              old_success=old['状态'] == '成功', new_success=result['converged'],
                              status=info.get('status'), candidates=info.get('candidate_count'),
                              targeted_old_failure=(n, block, repeat) == (7, int(failure.block), int(failure.repeat_id)))
                if result['converged']:
                    b, e, g = [result[p + '_hat'] for p in ['beta', 'eta', 'gamma']]
                    assert b > 0 and e > 0 and 0 <= g < x[0]
                    record['estimate'] = [b, e, g]
                    if method == 'wmle':
                        record['independent_squared_residual'] = verify_equations(x, b, e, g)
                    else:
                        ll = likelihood(x, b, e, g)
                        assert np.isclose(ll, info['log_likelihood'], atol=1e-8, rtol=0)
                        # All one-coordinate perturbations must not improve it.
                        for parameter in range(3):
                            h = 1e-5 * max(abs([b, e, g][parameter]), 1.)
                            for sign in [-1, 1]:
                                trial = [b, e, g]
                                trial[parameter] += sign * h
                                if trial[0] < 1 or trial[1] <= 0 or not 0 <= trial[2] < x[0]:
                                    continue
                                assert likelihood(x, *trial) <= ll + 1e-8
                        record['support_limit_higher'] = info['boundary_limit_exceeds_selected']
                        if record['old_success']:
                            previous = [float(old[p + '估计']) for p in ['β', 'η', 'γ']]
                            record['ll_change_from_old'] = ll - likelihood(x, *previous)
                else:
                    assert all(result[p + '_hat'] is None for p in ['beta', 'eta', 'gamma'])
                records.append(record)
        print(f'Validated shape={shape}: {len(keys)} archived samples', flush=True)
    counts = Counter(f"{r['method']}:{int(r['old_success'])}->{int(r['new_success'])}" for r in records)
    recovered = [r for r in records if r['method'] == 'wmle' and r['targeted_old_failure'] and not r['old_success'] and r['new_success']]
    assert len(recovered) == 4
    report = dict(solver_version=SOLVER_VERSION,
                  scope='First five archived samples in each of 20 cells, plus four diagnosed WMLE failures; not a performance-rate estimate',
                  backup_files_verified=len(manifest['files']), original_file_hashes=input_hashes,
                  source_hashes={p: digest(ROOT / p) for p in ['python/methods/mle.py', 'python/methods/wmle.py',
                      'python/methods/profile_solvers.py', 'python/methods/conditional_profiles.py', 'python/methods/lre.py', 'python/methods/j3_weights.tsv']},
                  compared_estimates=len(records), transitions=dict(counts), targeted_wmle_recoveries=len(recovered), records=records)
    output = ARCHIVE / '求解修订验证-20261016.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['compared_estimates', 'transitions', 'targeted_wmle_recoveries']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--old-success']:
        verify_old_successes()
    elif sys.argv[1:]:
        raise SystemExit('Usage: 验证求解修订.py [--old-success]')
    else:
        main()
