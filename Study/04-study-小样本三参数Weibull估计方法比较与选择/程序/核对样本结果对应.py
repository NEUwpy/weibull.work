"""独立从原始计算片段核对样本与结果对应关系；不导入整理程序，不改数据。"""
import csv
import gzip
import hashlib
import json
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from 存储路径 import STUDY, RESULTS, ARCHIVE, current_batch, saved_path

BATCH = current_batch()
REPORT = ARCHIVE / '样本结果独立对应核查.json'
FIELDS = [('beta_hat', '形状估计'), ('eta_hat', '尺度估计'), ('gamma_hat', '位置估计'), ('status', '状态')]


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f))


def require(condition, message, context):
    if not condition:
        raise AssertionError(f'{message}: {context}')


def main():
    prepared = load(BATCH / 'prepared.json')
    config = load(BATCH / 'manifest.json')['config']
    manifest_totals = load(BATCH / 'manifest.json')['totals']
    methods = {method: spec['variant'] for method, spec in config['methods']}
    touched = {}
    total = Counter()
    details = []
    expected_groups = {f"W{cell['beta']:g},{config['eta']:g},{config['gamma']:g}" for cell in prepared['cells']}
    require({p.name for p in RESULTS.glob('W*') if p.is_dir()} == expected_groups, '参数目录不符', '全部目录')
    with (BATCH / '条件汇总.csv').open(encoding='utf-8-sig', newline='') as f:
        summary = {(float(r['beta']), int(r['n']), r['method']): r for r in csv.DictReader(f)}
    for cell in prepared['cells']:
        name = f"W{cell['beta']:g},{config['eta']:g},{config['gamma']:g}"
        folder = RESULTS / name
        sample_path = folder / '原始样本' / f"n{cell['n']}.csv"
        table_path = folder / '估计结果' / sample_path.name
        pack_path = BATCH / 'inputs' / cell['key'] / 'samples.npz'
        input_manifest = load(pack_path.with_name('manifest.json'))
        pack_hash = sha(pack_path)
        require(pack_hash == input_manifest['sha256']['samples.npz'], '存档样本包指纹不符', cell['key'])
        for path in (sample_path, table_path, pack_path):
            touched[path] = sha(path)
        samples = read_csv(sample_path)
        table = read_csv(table_path)
        n, repeats = cell['n'], cell['repeats']
        sample_header = ['样本编号'] + [f'观测值{i + 1}' for i in range(n)]
        table_header = sample_header + [f'{variant}_{label}' for variant in methods.values() for _, label in FIELDS]
        require(samples[0] == sample_header and table[0] == table_header, '列名或方法次序不符', cell['key'])
        require(len(samples) == len(table) == repeats + 1, '样本或结果行数不符', cell['key'])
        with np.load(pack_path, allow_pickle=False) as package:
            original = package['samples']
        baseline = prepared.get('baseline_inputs', {}).get(cell['key'])
        if baseline:
            baseline_path = saved_path(baseline['path'])
            require(sha(baseline_path) == baseline['sha256'], '补齐前样本包指纹变化', cell['key'])
            with np.load(baseline_path, allow_pickle=False) as package:
                require(original[:baseline['repeats']].tobytes() == package['samples'].tobytes(), '原有样本被替换', cell['key'])
        ancestor = prepared.get('ancestor_inputs', {}).get(cell['key'])
        if ancestor:
            ancestor_path = saved_path(ancestor['path'])
            require(sha(ancestor_path) == ancestor['sha256'], '早期样本包指纹变化', cell['key'])
            with np.load(ancestor_path, allow_pickle=False) as package:
                require(original[:ancestor['repeats']].tobytes() == package['samples'].tobytes(), '早期样本被替换', cell['key'])
        require(original.shape == (repeats, n) and original.dtype == np.float64, '存档样本形状或类型不符', cell['key'])
        sample_hashes = []
        rows = []
        for repeat in range(repeats):
            sample, result = samples[repeat + 1], table[repeat + 1]
            context = (cell['key'], repeat)
            require(len(sample) == n + 1 and len(result) == len(table_header), '列数不符', context)
            require(sample[0] == result[0] == str(repeat), '编号错位或重复', context)
            require(result[:n + 1] == sample, '结果表观测值与样本表不一致', context)
            encoded = struct.pack(f'={n}d', *(float(v) for v in sample[1:]))
            require(encoded == original[repeat].tobytes(), 'CSV观测与存档不一致', context)
            sample_hashes.append(hashlib.sha256(encoded).hexdigest())
            rows.append(dict(zip(table_header, result)))
        require(len(set(sample_hashes)) == repeats, '同一条件内存在重复样本', cell['key'])
        seen = set()
        statuses = Counter()
        shard_count = 0
        expected_shards = {f'{start:04d}' for start in range(0, repeats, config['chunk_size'])}
        cell_shards = BATCH / 'shards' / cell['key']
        require({p.name for p in cell_shards.iterdir() if p.is_dir()} == expected_shards, '计算片段目录不符', cell['key'])
        for start in range(0, repeats, config['chunk_size']):
            chunk = cell_shards / f'{start:04d}'
            done = load(chunk / 'done.json')
            chunk_manifest = load(chunk / 'manifest.json')
            for filename, expected in done['sha256'].items():
                require(sha(chunk / filename) == expected, '计算片段指纹不符', str(chunk / filename))
            historical_shard = baseline and start < baseline['repeats']
            expected_pack_hash = baseline['sha256'] if historical_shard else pack_hash
            if historical_shard:
                original_chunk = baseline_path.parents[2] / 'shards' / cell['key'] / f'{start:04d}'
                require(sha(chunk / 'done.json') == sha(original_chunk / 'done.json'), '原有计算片段被修改', str(chunk))
                expected_pack_hash = load(original_chunk / 'manifest.json')['sample_pack_sha256']
                if expected_pack_hash != baseline['sha256']:
                    require(ancestor and expected_pack_hash == ancestor['sha256'] and
                            start + min(config['chunk_size'], repeats - start) <= ancestor['repeats'],
                            '历史片段所用的早期样本包无法追溯', str(chunk))
            require(chunk_manifest['sample_pack_sha256'] == expected_pack_hash, '计算时使用的样本包不对应', str(chunk))
            require(chunk_manifest['repeat_id_offset'] == start, '片段编号偏移不符', str(chunk))
            count = 0
            with gzip.open(chunk / 'results.csv.gz', 'rt', encoding='utf-8', newline='') as f:
                for raw in csv.DictReader(f):
                    repeat = int(raw['repeat_id'])
                    method = raw['method_id']
                    context = (cell['key'], repeat, method)
                    require((float(raw['beta']), float(raw['eta']), float(raw['gamma']), int(raw['n'])) ==
                            (cell['beta'], config['eta'], config['gamma'], n), '真实参数或样本量不符', context)
                    require(start <= repeat < min(start + config['chunk_size'], repeats), '记录属于其他片段', context)
                    require(method in methods and raw['method_variant'] == methods[method], '方法身份不符', context)
                    require((repeat, method) not in seen, '重复估计记录', context)
                    seen.add((repeat, method))
                    fingerprint = json.loads(raw['extra'])['experiment']['sample_sha256']
                    require(fingerprint == sample_hashes[repeat], '方法实际输入与该行样本不对应', context)
                    variant = methods[method]
                    for source_field, label in FIELDS:
                        require(rows[repeat][f'{variant}_{label}'] == raw[source_field], '估计参数或状态列不对应', (context, source_field))
                    statuses[(method, raw['status'])] += 1
                    total[raw['status']] += 1
                    if prepared.get('baseline_inputs'):
                        total['retained_attempts' if historical_shard else 'additional_attempts'] += 1
                    count += 1
            require(count == done['rows'] == min(config['chunk_size'], repeats - start) * len(methods), '片段记录遗漏', str(chunk))
            shard_count += 1
        require(seen == {(repeat, method) for repeat in range(repeats) for method in methods}, '存在缺失或多余的方法记录', cell['key'])
        for method, variant in methods.items():
            expected = summary[(cell['beta'], n, variant)]
            require(statuses[(method, 'success')] == int(expected['success']) and
                    statuses[(method, 'failure')] == int(expected['failure']), '成功或失败数量与汇总不一致', (cell['key'], variant))
        total.update(samples=repeats, observations=repeats * n, conditions=1, shards=shard_count)
        details.append(dict(cell=cell['key'], parameter_group=name, sample_rows=repeats,
                            observations=repeats * n, attempts=len(seen), passed=True))
    require(all(sha(path) == before for path, before in touched.items()), '核查期间文件发生变化', '样本和结果表')
    expected_observations = sum(c['repeats'] * c['n'] for c in prepared['cells'])
    expected_shards = sum((c['repeats'] + config['chunk_size'] - 1) // config['chunk_size'] for c in prepared['cells'])
    require(total['samples'] == prepared['sample_count'] and total['observations'] == expected_observations and
            total['success'] == manifest_totals['success'] and total['failure'] == manifest_totals['failure'] and
            total['conditions'] == len(prepared['cells']) and total['shards'] == expected_shards, '合计数量不符', dict(total))
    if prepared.get('baseline_inputs'):
        expected_retained = sum(v['repeats'] for v in prepared['baseline_inputs'].values()) * len(methods)
        require(total['retained_attempts'] == expected_retained and total['additional_attempts'] == config['additional_rows'],
                '保留或追加的记录数量不符', dict(total))
    report = dict(passed=True, checked_at=datetime.now(timezone.utc).isoformat(),
                  run_id=BATCH.name, checker_sha256=sha(Path(__file__)),
                  scope='CSV样本表→CSV结果表→原始计算片段；不重新估计参数',
                  independent_of='按参数整理结果.py及其导出/核验函数',
                  parameter_groups=len(expected_groups), totals=dict(total),
                  mismatches=0, missing_records=0, duplicate_records=0,
                  unchanged_sample_and_table_files=len(touched), conditions=details)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'conditions'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
