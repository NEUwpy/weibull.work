"""从保存的样本复算七种方法；--verify 只核对现有结果，不调用估计器。"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.special import logsumexp

PROGRAM = Path(__file__).resolve().parent
STUDY = PROGRAM.parent
RESULTS = STUDY / '结果'
CONFIG = json.loads((PROGRAM / '实验配置.json').read_text(encoding='utf-8'))
CORE = PROGRAM / CONFIG['source_directory']
sys.path.insert(0, str(CORE))
from methods.lse import log_weibull_order_stat_means
from studies.common.experiment import run_experiment
from studies.common.metrics import check_status

PARAMETERS = [('beta_hat', '形状估计'), ('eta_hat', '尺度估计'), ('gamma_hat', '位置估计')]
VARIANTS = [spec['variant'] for _, spec in CONFIG['methods']]


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parameter_name(beta):
    return f"W{beta:g},{CONFIG['eta']:g},{CONFIG['gamma']:g}"


def samples_at(beta, n):
    path = RESULTS / parameter_name(beta) / '原始样本' / f'n{n}.csv'
    fields, rows = read_csv(path)
    assert fields == ['样本编号'] + [f'观测值{i + 1}' for i in range(n)]
    assert [r['样本编号'] for r in rows] == [str(i) for i in range(CONFIG['repeats'])]
    x = np.asarray([[float(r[k]) for k in fields[1:]] for r in rows], dtype=np.float64)
    assert x.shape == (CONFIG['repeats'], n) and np.isfinite(x).all()
    assert (x > 0).all() and (np.diff(x, axis=1) > 0).all()
    assert len({row.tobytes() for row in x}) == len(x)
    return path, fields, rows, x


def verify_sources():
    for name, expected in CONFIG['source_sha256'].items():
        if digest(CORE / name) != expected:
            raise RuntimeError(f'固定计算实现发生变化：{name}')


def verify():
    """逐条核对表格、原样本指纹和求解明细，独立重算参数指标。"""
    verify_sources()
    metadata = json.loads((RESULTS / '数据说明.json').read_text(encoding='utf-8'))
    for name, expected in metadata['file_sha256'].items():
        assert digest(RESULTS / name) == expected, ('结果文件发生变化', name)
    row_count = valid_count = metric_count = kr_count = lse_count = 0
    conditions = set()
    with gzip.open(RESULTS / '求解明细.csv.gz', 'rt', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        key = lambda r: (float(r['beta']), int(r['n']))
        for (beta, n), records in itertools.groupby(reader, key):
            assert (beta, n) not in conditions
            conditions.add((beta, n))
            _, fields, sample_rows, samples = samples_at(beta, n)
            folder = RESULTS / parameter_name(beta)
            table_fields, table = read_csv(folder / '估计结果' / f'n{n}.csv')
            expected_fields = fields + [f'{v}_{label}' for v in VARIANTS
                                       for label in ['形状估计', '尺度估计', '位置估计', '状态']]
            assert table_fields == expected_fields and len(table) == len(samples)
            for sample, row in zip(sample_rows, table):
                assert all(row[k] == sample[k] for k in fields), ('样本与估计表错位', beta, n)
            _, summaries = read_csv(folder / '条件汇总.csv')
            summaries = {r['method']: r for r in summaries if int(r['n']) == n}
            hashes = [hashlib.sha256(row.tobytes()).hexdigest() for row in samples]
            grouped = {v: [] for v in VARIANTS}
            seen = set()
            for row in records:
                rid = int(row['repeat_id'])
                variant = row['method_variant']
                assert 0 <= rid < len(samples) and variant in grouped
                assert (rid, variant) not in seen
                seen.add((rid, variant))
                assert row['method_id'] == dict((v['variant'], m) for m, v in CONFIG['methods'])[variant]
                assert float(row['eta']) == CONFIG['eta'] and float(row['gamma']) == CONFIG['gamma']
                saved = table[rid]
                assert row['status'] == saved[f'{variant}_状态']
                values = [float(row[p]) if row[p] else None for p, _ in PARAMETERS]
                for (p, label), value in zip(PARAMETERS, values):
                    displayed = saved[f'{variant}_{label}']
                    if value is None:
                        assert displayed == ''
                    else:
                        assert np.isclose(value, float(displayed), rtol=0, atol=0, equal_nan=True)
                extra = json.loads(row['extra'])
                context = extra['experiment']
                assert context['sample_sha256'] == hashes[rid]
                assert context['boundary_tol'] == CONFIG['boundary_tol']
                minimum = samples[rid, 1 if row['method_id'] == 'mmle' and values[2] is not None else 0]
                assert context['support_min'] == minimum
                status = 'failure' if any(v is None for v in values) else check_status(
                    *values, beta, CONFIG['eta'], CONFIG['gamma'],
                    converged=row['converged'] == 'True', sample_min=minimum,
                    boundary_tol=CONFIG['boundary_tol'])
                assert status == row['status']
                grouped[variant].append((rid, values, status, context['result_origin']))
                row_count += 1
            assert len(seen) == len(samples) * len(VARIANTS)
            for variant, rows in grouped.items():
                saved = summaries[variant]
                good = [(rid, values) for rid, values, status, _ in rows if status == 'success']
                assert len(rows) == int(saved['total']) == CONFIG['repeats']
                assert len(good) == int(saved['success'])
                assert len(rows) - len(good) == int(saved['failure'])
                assert sum(origin == 'precomputed' for _, _, _, origin in rows) == int(saved['reused'])
                estimates = np.asarray([v for _, v in good], dtype=float).reshape(-1, 3)
                valid_count += len(good)
                for i, (p, truth) in enumerate([('beta', beta), ('eta', CONFIG['eta']), ('gamma', CONFIG['gamma'])]):
                    errors = estimates[:, i] - truth
                    metrics = dict(bias=np.mean(errors), sd=np.std(errors, ddof=1) if len(errors) > 1 else 0.,
                                   rmse=np.sqrt(np.mean(errors**2)), mae=np.mean(np.abs(errors)))
                    for metric, expected in metrics.items():
                        assert np.isclose(float(saved[f'{p}_{metric}']), expected, rtol=1e-10, atol=1e-10, equal_nan=True)
                        metric_count += 1
                rate = np.mean((estimates[:, 0] >= 3 * beta) | (estimates[:, 0] <= beta / 3))
                assert np.isclose(float(saved['shape_anomaly_rate']), rate, rtol=0, atol=1e-12)
                x = samples[[rid for rid, _ in good]]
                if variant == 'MMLE(KR)':
                    b, e, g = estimates.T
                    assert np.array_equal(g, x[:, 0])
                    expected = np.exp((logsumexp(b[:, None] * np.log(x[:, 1:] - g[:, None]), axis=1) - np.log(n - 1)) / b)
                    assert np.allclose(e, expected, rtol=1e-8, atol=1e-8)
                    kr_count += len(good)
                elif variant == 'LSE':
                    b, e, g = estimates.T
                    z = log_weibull_order_stat_means(n)
                    y = np.log(x - g[:, None])
                    slope = ((y - y.mean(axis=1, keepdims=True)) * (z - z.mean())).sum(axis=1) / ((z - z.mean())**2).sum()
                    assert np.allclose(b, 1 / slope, rtol=1e-8, atol=1e-8)
                    assert np.allclose(e, np.exp(y.mean(axis=1) - slope * z.mean()), rtol=1e-8, atol=1e-8)
                    lse_count += len(good)
    assert conditions == set(itertools.product(CONFIG['beta'], CONFIG['n']))
    assert row_count == metadata['totals']['total'] and valid_count == metadata['totals']['success']
    print(json.dumps(dict(result='passed', conditions=len(conditions), samples=len(conditions) * CONFIG['repeats'],
                          records=row_count, valid=valid_count, failed=row_count-valid_count,
                          metrics=metric_count, kr_scale=kr_count, lse_regression=lse_count), ensure_ascii=False), flush=True)


def compute_condition(job):
    beta, n, repeats, destination = job
    source, fields, sample_rows, samples = samples_at(beta, n)
    folder = Path(destination) / parameter_name(beta)
    raw_dir = folder / '求解明细' / f'n{n}'
    summaries = run_experiment(CONFIG['methods'], [(beta, CONFIG['eta'], CONFIG['gamma'])], [n], repeats,
        str(raw_dir), sample_provider=lambda b, e, g, count, rid: samples[rid],
        code_version=CONFIG['solver_version'], run_label='Study04 saved-sample reproduction',
        boundary_tol=CONFIG['boundary_tol'])
    _, raw = read_csv(raw_dir / 'results.csv')
    by_sample = {(int(row['repeat_id']), row['method_variant']): row for row in raw}
    table = []
    for rid, sample in enumerate(sample_rows[:repeats]):
        row = dict(sample)
        for variant in VARIANTS:
            estimate = by_sample[rid, variant]
            row.update({f'{variant}_{label}': estimate[p] for p, label in PARAMETERS})
            row[f'{variant}_状态'] = estimate['status']
        table.append(row)
    write_csv(folder / '原始样本' / f'n{n}.csv', fields, sample_rows[:repeats])
    table_fields = fields + [f'{v}_{label}' for v in VARIANTS
                            for label in ['形状估计', '尺度估计', '位置估计', '状态']]
    write_csv(folder / '估计结果' / f'n{n}.csv', table_fields, table)
    records = []
    for summary in summaries.values():
        variant = summary['method_variant']
        good = [r for r in raw if r['method_variant'] == variant and r['status'] == 'success']
        shape = np.array([float(r['beta_hat']) for r in good])
        row = dict(beta=beta, eta=CONFIG['eta'], gamma=CONFIG['gamma'], n=n, method=variant,
                   total=summary['n_total'], success=summary['n_valid'], failure=summary['n_total']-summary['n_valid'],
                   reused=0, computed=repeats,
                   shape_anomaly_rate=float(np.mean((shape >= 3*beta) | (shape <= beta/3))) if len(shape) else '')
        for p in ['beta', 'eta', 'gamma']:
            stats = summary.get('param_standard', {}).get(p, {}).get('absolute', {})
            row.update({f'{p}_{metric}': stats.get(metric, '') for metric in ['bias', 'sd', 'rmse', 'mae']})
        records.append(row)
    print(f'Completed beta={beta:g}, n={n}, repeats={repeats}', flush=True)
    return beta, records, source.relative_to(RESULTS).as_posix(), digest(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='只核对当前结果及计算实现')
    action.add_argument('--output', type=Path, help='复算另存目录，必须尚不存在')
    parser.add_argument('--beta', nargs='+', type=float, choices=CONFIG['beta'])
    parser.add_argument('--n', nargs='+', type=int, choices=CONFIG['n'])
    parser.add_argument('--repeats', type=int, default=CONFIG['repeats'])
    parser.add_argument('--workers', type=int, default=CONFIG['workers'])
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    verify_sources()
    if not 1 <= args.repeats <= CONFIG['repeats'] or args.workers < 1:
        parser.error('重复数须为1—1200，进程数须为正整数')
    output = args.output.resolve()
    if output.exists():
        parser.error('另存目录已存在；请换一个新目录，不覆盖原结果')
    output.mkdir(parents=True)
    jobs = [(b, n, args.repeats, str(output)) for b in args.beta or CONFIG['beta'] for n in args.n or CONFIG['n']]
    collected = {}
    sources = {}
    with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as pool:
        for beta, records, source, sha in pool.map(compute_condition, jobs):
            collected.setdefault(beta, []).extend(records)
            sources[source] = sha
    verify_sources()
    for beta, rows in collected.items():
        write_csv(output / parameter_name(beta) / '条件汇总.csv', list(rows[0]), rows)
    shutil.copyfile(PROGRAM / '实验配置.json', output / '实验配置.json')
    manifest = dict(status='complete', sample_source=str(RESULTS), sample_sha256=sources,
                    beta=args.beta or CONFIG['beta'], n=args.n or CONFIG['n'], repeats=args.repeats,
                    workers=args.workers, reuse=False, source_directory=str(CORE),
                    source_sha256=CONFIG['source_sha256'], entrypoint_sha256=digest(Path(__file__)))
    (output / '复算说明.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'另存完成：{output}', flush=True)


if __name__ == '__main__':
    main()
