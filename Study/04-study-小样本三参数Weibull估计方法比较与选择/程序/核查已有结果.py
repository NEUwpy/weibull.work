"""Read-only audit of the four Research09 batches proposed for Study04.

Rechecks inputs, summaries and method identity; replays a small fixed subset.
Conditional curves only diagnose candidate existence and do not replace fits.
"""
from pathlib import Path
import hashlib
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from methods import wmle
from methods.conditional_profiles import mle_profile, wmle_profile, wmle_residuals
from studies.common.metrics import check_status, summarize_standard_errors
from studies.common.runner import run_method
from studies.common.sample import generate_sample


def read_csv(path):
    return pd.read_csv(path, float_precision='round_trip')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ll_at(x, beta, eta, gamma):
    t = np.log(x - gamma)
    return float(len(x) * (np.log(beta) - beta * np.log(eta))
                 + (beta - 1) * t.sum() - np.exp(beta * (t - np.log(eta))).sum())


def wmle_candidate(x):
    previous = None
    for gamma in np.linspace(0., x[0] * (1 - 1e-7), 81):
        point = wmle_profile(x, float(gamma), wmle)
        if point is None:
            previous = None
            continue
        if previous and previous[1]['t2'] * point['t2'] < 0:
            try:
                root = brentq(lambda g: wmle_profile(x, g, wmle)['t2'], previous[0], gamma)
                candidate = wmle_profile(x, root, wmle)
                if (candidate['t1'] ** 2 + candidate['t2'] ** 2 <= 1e-8
                        and candidate['beta'] < wmle.SHAPE_UPPER - .01
                        and root < x[0] - 1e-6):
                    return dict(beta=candidate['beta'], eta=candidate['eta'], gamma=float(root),
                                squared_residual=candidate['t1'] ** 2 + candidate['t2'] ** 2)
            except (ValueError, TypeError):
                pass
        previous = (gamma, point)
    return None


def audit(beta):
    batch = ROOT / 'Research/09-Weibull参数估计方法谱系与比较基线/实验' / f'W({beta:g},1000,500)'
    program = batch / '程序'
    config = json.loads((program / 'config.json').read_text(encoding='utf-8'))
    truth = tuple(float(v) for v in config['truth'])
    samples = read_csv(batch / '数据/样本.csv')
    exported = read_csv(batch / '数据/估计明细.csv')
    raw = exported.rename(columns={'方法': 'method_variant', 'β真值': 'beta', 'η真值': 'eta',
                                   'γ真值': 'gamma', 'β估计': 'beta_hat', 'η估计': 'eta_hat',
                                   'γ估计': 'gamma_hat', '收敛': 'converged', '状态': 'status',
                                   '样本SHA256': 'sample_sha256', '支持检查最小值': 'retained_min',
                                   '删除观测数': 'deleted_count'}).copy()
    raw['method_variant'] = raw['method_variant'].replace({'MMLE': 'K-R MMLE'})
    raw['status'] = raw['status'].map({'成功': 'success', '失败': 'failure'})
    assert raw['status'].notna().all()
    summary = read_csv(batch / '数据/三方法汇总.csv')
    assert truth == (beta, 1000., 500.)
    assert len(raw) == 18000 and len(samples) == 6000 and len(exported) == 18000
    assert not raw.duplicated(['n', 'block', 'repeat_id', 'method_variant']).any()
    hashes, values = {}, {}
    regenerated = 0
    for n in config['n']:
        saved = samples[samples.n == n].sort_values(['block', 'repeat_id'])
        a = saved[[f'x({i})' for i in range(1, n + 1)]].to_numpy()
        assert a.shape == (1200, n) and np.isfinite(a).all()
        assert np.all(np.diff(a, axis=1) > 0) and (a > truth[2]).all()
        for block in range(config['blocks']):
            seed = config['seed_namespace'] if block == 0 else f"{config['seed_namespace']}:research09-versions:block{block:02d}"
            for repeat in range(config['repeats']):
                key = (n, block, repeat)
                x = a[block * 100 + repeat]
                # The historical seed key includes repr() of parameter values:
                # preserve JSON int/float identities instead of normalizing them.
                generated = generate_sample(*config['truth'], n, repeat, seed=seed)
                assert np.array_equal(x, generated), key
                regenerated += 1
                hashes[key] = hashlib.sha256(x.tobytes()).hexdigest()
                values[key] = x
    for row in samples.itertuples(index=False, name=None):
        record = dict(zip(samples.columns, row))
        key = tuple(int(record[p]) for p in ['n', 'block', 'repeat_id'])
        assert record['样本SHA256'] == hashes[key]
    mmle_max_score = 0.
    for row in raw.itertuples():
        key = (int(row.n), int(row.block), int(row.repeat_id))
        x = values[key]
        assert row.sample_sha256 == hashes[key]
        assert (row.beta, row.eta, row.gamma) == truth
        minimum = x[1] if row.method_variant == 'K-R MMLE' else x[0]
        assert np.isclose(row.retained_min, minimum, rtol=0., atol=1e-9)
        assert row.deleted_count == (1 if row.method_variant == 'K-R MMLE' else 0)
        status = check_status(row.beta_hat, row.eta_hat, row.gamma_hat, *truth,
                              converged=bool(row.converged), sample_min=minimum, boundary_tol=0.)
        assert status == row.status
        if row.method_variant == 'K-R MMLE' and status == 'success':
            assert np.isclose(row.gamma_hat, x[0], rtol=0., atol=1e-9)
            t = np.log(x[1:] - x[0])
            w = np.exp(row.beta_hat * (t - t.max()))
            score = 1 / row.beta_hat + t.mean() - (w @ t) / w.sum()
            mmle_max_score = max(mmle_max_score, abs(float(score)))
            assert abs(score) < 1e-5
    checks, counts = 0, {}
    for (method, n), group in raw.groupby(['method_variant', 'n']):
        label = 'MMLE' if method == 'K-R MMLE' else method
        valid = group[group.status == 'success']
        table = summary[(summary.method == label) & (summary.n == n)].iloc[0]
        assert len(group) == 1200 and int(table.success) == len(valid)
        for p, true_value in zip(['beta', 'eta', 'gamma'], truth):
            stats = summarize_standard_errors(valid[p + '_hat'].to_numpy() - true_value)
            observed = dict(bias=stats['bias'], sd=float(np.std(valid[p + '_hat'] - true_value, ddof=0)), rmse=stats['rmse'])
            for name, value in observed.items():
                assert np.isclose(table[p + '_' + name], value, rtol=1e-11, atol=1e-10)
                checks += 1
        counts[f'{label}/n{n}'] = dict(success=len(valid), total=len(group))
    manifest = json.loads((program / 'manifest.json').read_text(encoding='utf-8'))
    verified_files = []
    for item in manifest['files']:
        if item['path'] in ['数据/样本.csv', '数据/估计明细.csv', '数据/三方法汇总.csv']:
            assert digest(batch / item['path']) == item['sha256']
            verified_files.append(item['path'])
    assert len(verified_files) == 3
    identity = {}
    for relative in ['methods/mle.py', 'methods/wmle.py', 'methods/j3_weights.tsv',
                     'base.py', 'studies/common/sample.py', 'studies/common/runner.py']:
        old = program / 'source_snapshot/python' / relative
        current = ROOT / 'python' / relative
        identity[relative] = dict(same_bytes=digest(old) == digest(current),
                                  archived_sha256=digest(old), current_sha256=digest(current))
    selected = []
    for method in ['MLE', 'K-R MMLE', 'WMLE']:
        for status in ['success', 'failure']:
            candidates = raw[(raw.n == 7) & (raw.method_variant == method) & (raw.status == status)]
            if not candidates.empty:
                selected.append(candidates.iloc[0])
    selected.append(raw[(raw.n == 50) & (raw.method_variant == 'MLE') & (raw.status == 'success')].iloc[0])
    replays = []
    for row in selected:
        key = (int(row.n), int(row.block), int(row.repeat_id))
        x = values[key]
        method_id = 'mmle' if row.method_variant == 'K-R MMLE' else row.method_variant.lower()
        current = run_method(method_id, x)
        same = bool(current['converged']) == bool(row.converged)
        if bool(row.converged) and current['converged']:
            same = same and np.allclose([current[p + '_hat'] for p in ['beta', 'eta', 'gamma']],
                                       [row.beta_hat, row.eta_hat, row.gamma_hat], rtol=1e-8, atol=1e-7)
        record = dict(method=method_id, n=key[0], block=key[1], repeat_id=key[2],
                      archived_status=row.status, replay_matches=bool(same), replay_extra=current['extra'])
        if method_id == 'mle':
            candidates = [(float(g), mle_profile(x, float(g))) for g in np.linspace(0., x[0] * (1 - 1e-7), 81)]
            gamma, best = max((v for v in candidates if v[1] is not None), key=lambda v: v[1]['ll'])
            record['admissible_profile_candidate'] = dict(beta=best['beta'], eta=best['eta'], gamma=gamma, ll=best['ll'])
            if row.status == 'success':
                previous_ll = ll_at(x, row.beta_hat, row.eta_hat, row.gamma_hat)
                record['saved_ll'] = previous_ll
                record['candidate_ll_improvement'] = best['ll'] - previous_ll
        if method_id == 'wmle' and row.status == 'failure':
            record['admissible_equation_root_found'] = wmle_candidate(x)
        replays.append(record)
    print(f'Completed beta={beta}: 6000 samples, 18000 estimates, {len(replays)} replays', flush=True)
    return dict(truth=truth, regenerated_samples=regenerated, checked_estimates=len(raw),
                checked_summary_values=checks, mmle_max_shape_score=mmle_max_score,
                manifest_files_verified=verified_files,
                source_identity=identity, status_counts=counts, replays=replays)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='A new report path; existing reports cannot be overwritten')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f'Preserve the existing audit: {output}')
    report = dict(scope='Four main Research09 batches only; original files unchanged',
                  interpretation='Conditional diagnostics find candidates, not certified global optima',
                  batches=[audit(beta) for beta in [1.5, 2., 3., 5.]])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print('Audit saved:', output, flush=True)
