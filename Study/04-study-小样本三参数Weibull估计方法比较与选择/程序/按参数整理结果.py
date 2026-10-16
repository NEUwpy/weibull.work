"""按Research00的参数目录组织已完成结果；不抽样、不拟合、不重算指标。"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import numpy as np

from 存储路径 import STUDY, RESULTS, ARCHIVE, METADATA, current_batch, parameter_file

BATCH = current_batch()
SAMPLE_DESCRIPTION = '- [原始样本](原始样本/)：各n一份CSV，每行一组升序观测；样本编号从0开始，与估计结果表逐行对应，数值保存17位有效数字。\n\n'
RESULT_FIELDS = [('beta_hat', '形状估计'), ('eta_hat', '尺度估计'), ('gamma_hat', '位置估计'), ('status', '状态')]
RESULT_DESCRIPTION = '- [估计结果](估计结果/)：各n一份CSV，每行一组样本；原始观测与7种方法的估计参数、状态在同一行，样本编号与原始样本表对应。\n'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def parameter_hashes(name):
    files = {}
    for folder in (RESULTS / name, METADATA / name):
        for path in folder.rglob('*'):
            if path.is_file() and path.name != 'manifest.json':
                key = path.relative_to(folder).as_posix()
                assert key not in files, ('重复参数文件', name, key)
                files[key] = sha(path)
    return files


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def group_name(beta, eta=1000, gamma=500):
    return f'W{float(beta):g},{float(eta):g},{float(gamma):g}'


def groups():
    result = {}
    for cell in load(BATCH / 'prepared.json')['cells']:
        result.setdefault(group_name(cell['beta']), []).append(cell)
    return result


def raw_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def check_sample_csv(path, cell):
    with np.load(BATCH / 'inputs' / cell['key'] / 'samples.npz', allow_pickle=False) as package:
        original = package['samples']
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        assert next(reader) == ['样本编号'] + [f'观测值{i + 1}' for i in range(cell['n'])]
        rows = list(reader)
    assert len(rows) == cell['repeats']
    assert [r[0] for r in rows] == [str(i) for i in range(cell['repeats'])]
    assert all(len(r) == cell['n'] + 1 for r in rows)
    restored = np.array([[float(v) for v in row[1:]] for row in rows], dtype=original.dtype)
    assert original.shape == restored.shape and original.tobytes() == restored.tobytes(), ('CSV数值不一致', path)
    return original.size


def write_sample_csv(path, cell):
    with np.load(BATCH / 'inputs' / cell['key'] / 'samples.npz', allow_pickle=False) as package:
        samples = package['samples']
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['样本编号'] + [f'观测值{i + 1}' for i in range(cell['n'])])
        for repeat, values in enumerate(samples):
            writer.writerow([repeat] + [format(float(value), '.17g') for value in values])
    check_sample_csv(temporary, cell)
    temporary.replace(path)


def read_result_table(path, cell, variants):
    with (path.parents[1] / '原始样本' / path.name).open(encoding='utf-8-sig', newline='') as f:
        samples = list(csv.reader(f))
    fields = samples[0] + [f'{variant}_{label}' for variant in variants for _, label in RESULT_FIELDS]
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == fields, ('结果表列名', path)
        rows = list(reader)
    assert len(rows) == cell['repeats'] == len(samples) - 1
    for repeat, (row, sample) in enumerate(zip(rows, samples[1:])):
        assert row['样本编号'] == str(repeat)
        assert [row[key] for key in samples[0]] == sample, ('结果表与样本不对应', path, repeat)
    return rows


def result_tables():
    """把逐次记录展开为样本对应表，原始返回和详细诊断继续保存在计算存档。"""
    grid = groups()
    variants = [spec['variant'] for _, spec in load(BATCH / 'manifest.json')['config']['methods']]
    returned = {}
    for name in grid:
        folder = RESULTS / name
        manifest = load(parameter_file(name, 'manifest.json'))
        assert all(sha(parameter_file(name, p)) == value for p, value in manifest['file_sha256'].items())
    with ExitStack() as stack:
        legacy = {}
        for name in grid:
            old = RESULTS / name / '估计明细.csv.gz'
            if old.exists():
                f = stack.enter_context(gzip.open(old, 'rt', encoding='utf-8', newline=''))
                legacy[name] = iter(csv.DictReader(f))
        for row in raw_rows(BATCH / 'results.csv.gz'):
            name = group_name(row['beta'], row['eta'], row['gamma'])
            if name in legacy:
                assert next(legacy[name]) == row, '原压缩明细与计算存档不一致'
            key = (name, int(row['n']), int(row['repeat_id']))
            methods = returned.setdefault(key, {})
            assert row['method_variant'] not in methods
            methods[row['method_variant']] = tuple(row[field] for field, _ in RESULT_FIELDS)
        assert all(next(reader, None) is None for reader in legacy.values())
    for name, cells in grid.items():
        folder = RESULTS / name
        (folder / '估计结果').mkdir(exist_ok=True)
        for cell in cells:
            filename = f"n{cell['n']}.csv"
            check_sample_csv(folder / '原始样本' / filename, cell)
            with (folder / '原始样本' / filename).open(encoding='utf-8-sig', newline='') as f:
                samples = list(csv.reader(f))
            path = folder / '估计结果' / filename
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(samples[0] + [f'{variant}_{label}' for variant in variants for _, label in RESULT_FIELDS])
                for repeat, sample in enumerate(samples[1:]):
                    values = returned[(name, cell['n'], repeat)]
                    assert set(values) == set(variants)
                    writer.writerow(sample + [value for variant in variants for value in values[variant]])
            rows = read_result_table(path, cell, variants)
            for repeat, row in enumerate(rows):
                for variant in variants:
                    assert tuple(row[f'{variant}_{label}'] for _, label in RESULT_FIELDS) == returned[(name, cell['n'], repeat)][variant]
        old = folder / '估计明细.csv.gz'
        if old.exists():
            assert old.resolve().is_relative_to(folder.resolve())
            old.unlink()
        readme = METADATA / name / 'README.md'
        text = readme.read_text(encoding='utf-8')
        old_line = '- [估计明细.csv.gz](估计明细.csv.gz)：逐次估计，完整保留失败、极端值及来源字段。\n'
        text = text.replace(old_line, RESULT_DESCRIPTION)
        text = text.replace('与估计明细的repeat_id对应', '与估计结果表逐行对应')
        if RESULT_DESCRIPTION not in text:
            text = text.replace('- [summary.json]', RESULT_DESCRIPTION + '- [summary.json]')
        readme.write_text(text, encoding='utf-8')
        manifest = load(parameter_file(name, 'manifest.json'))
        manifest['file_sha256'] = parameter_hashes(name)
        manifest['result_table_format'] = '每个n一份CSV；每行一组样本，观测与7种方法的参数、原状态横向排列；编号从0开始'
        manifest['transformation'] = '原记录按参数及n展开为样本对应表；保留原估计值、失败与极端值；不抽样、不拟合、不重算汇总'
        dump(METADATA / name / 'manifest.json', manifest)
    index = RESULTS / 'README.md'
    text = index.read_text(encoding='utf-8')
    if '估计结果也按n保存为CSV' not in text:
        text = text.replace('每行一组观测。', '每行一组观测。估计结果也按n保存为CSV，每行对应同一组样本，横向列出7种方法的估计参数与状态。')
        index.write_text(text, encoding='utf-8')
    return verify()


def samples_to_csv():
    """替换参数目录中的样本副本；计算存档里的NPZ及其附带旧结果保持原字节。"""
    old_description = '- [原始样本](原始样本/)：各n的原样本包，NPZ中的samples数组每行是一组观测。\n\n'
    for name, cells in groups().items():
        folder = RESULTS / name
        manifest = load(parameter_file(name, 'manifest.json'))
        assert all(sha(parameter_file(name, p)) == value for p, value in manifest['file_sha256'].items())
        for cell in cells:
            write_sample_csv(folder / '原始样本' / f"n{cell['n']}.csv", cell)
            old_copy = folder / '原始样本' / f"n{cell['n']}.npz"
            if old_copy.exists():
                assert old_copy.resolve().is_relative_to((RESULTS / name).resolve())
                assert sha(old_copy) == sha(BATCH / 'inputs' / cell['key'] / 'samples.npz')
                old_copy.unlink()
        readme = METADATA / name / 'README.md'
        readme.write_text(readme.read_text(encoding='utf-8').replace(old_description, SAMPLE_DESCRIPTION), encoding='utf-8')
        manifest['file_sha256'] = parameter_hashes(name)
        manifest['transformation'] = '原记录按参数筛分；样本按17位有效数字转为CSV并逐值核对；不抽样、不拟合、不重算汇总'
        manifest['sample_format'] = 'CSV, UTF-8 BOM, .17g, 样本编号与repeat_id一致（从0开始）'
        dump(METADATA / name / 'manifest.json', manifest)
    index = RESULTS / 'README.md'
    text = index.read_text(encoding='utf-8')
    if '原始样本均为CSV' not in text:
        text = text.replace('每个W目录对应一组形状、尺度、位置参数，同组各样本量集中保存。',
                            '每个W目录对应一组形状、尺度、位置参数，同组各样本量集中保存。原始样本均为CSV，每个n一份，每行一组观测。')
        index.write_text(text, encoding='utf-8')
    return verify()


def export():
    grid = groups()
    existing = [str(RESULTS / name) for name in grid if (RESULTS / name).exists()]
    if existing:
        raise FileExistsError('参数目录已存在；仅核对请使用 --verify：' + ', '.join(existing))
    source_names = ['results.csv.gz', 'summary.json', '条件汇总.csv', 'manifest.json', 'prepared.json']
    before = {name: sha(BATCH / name) for name in source_names}
    source_summary = load(BATCH / 'summary.json')
    with (BATCH / '条件汇总.csv').open(encoding='utf-8-sig', newline='') as f:
        table_reader = csv.DictReader(f)
        summary_fields = table_reader.fieldnames
        summary_rows = list(table_reader)
    for name in grid:
        (RESULTS / name / '原始样本').mkdir(parents=True)
    index = ['# 按参数查看结果', '',
             '每个W目录对应一组形状、尺度、位置参数，同组各样本量集中保存。原始样本均为CSV，每个n一份，每行一组观测。方法版本及评价口径见[实验设置](../实验设置.md)。', '',
             '| 参数目录 | 样本量n | 每条件重复数 | 方法尝试数 |',
             '|---|---|---:|---:|']
    for name, cells in grid.items():
        folder = RESULTS / name
        selected = {k: v for k, v in source_summary.items() if group_name(v['beta'], v['eta'], v['gamma']) == name}
        (METADATA / name).mkdir(parents=True, exist_ok=True)
        dump(METADATA / name / 'summary.json', selected)
        with (folder / '条件汇总.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=summary_fields)
            writer.writeheader()
            writer.writerows(r for r in summary_rows if group_name(r['beta'], r['eta'], r['gamma']) == name)
        for cell in cells:
            write_sample_csv(folder / '原始样本' / f"n{cell['n']}.csv", cell)
        attempts = sum(c['repeats'] * 7 for c in cells)
        ns = '、'.join(str(c['n']) for c in cells)
        repeats = cells[0]['repeats']
        readme_text = (
            f'# {name}\n\n形状β={cells[0]["beta"]:g}，尺度η=1000，位置γ=500；n={ns}，每条件{repeats}组样本，共{attempts}条方法尝试。\n\n'
            '- [条件汇总.csv](条件汇总.csv)：按样本量、方法列出成功/失败、误差与波动。\n'
            + RESULT_DESCRIPTION +
            '- [summary.json](summary.json)：原批次的详细指标，仅按参数分出，未重新计算。\n'
            + SAMPLE_DESCRIPTION +
            f'n=50仅作参照（若本组包含）；本组每条件{repeats}次，跨条件汇总按条件等权。\n\n'
            f'数据来自[计算存档](../../{BATCH.name}/计算结果概览.md)，程序版本、求解限制及指纹保存在原批次。\n')
        for target in ['条件汇总.csv', '估计结果/', '原始样本/']:
            readme_text = readme_text.replace(f']({target})', f'](../../../结果/{name}/{target})')
        (METADATA / name / 'README.md').write_text(readme_text, encoding='utf-8')
        file_hashes = parameter_hashes(name)
        dump(METADATA / name / 'manifest.json', dict(parameters=[cells[0]['beta'], 1000, 500], cells=cells,
             attempts=attempts, source_batch=f'../{BATCH.name}', source_sha256=before, file_sha256=file_hashes,
             transformation='原记录按参数筛分；样本按17位有效数字转为CSV并逐值核对；不抽样、不拟合、不重算汇总',
             sample_format='CSV, UTF-8 BOM, .17g, 样本编号与repeat_id一致（从0开始）'))
        index.append(f'| [{name}]({name}/) | {ns} | {repeats} | {attempts} |')
    index += ['', f'常用入口为上面的参数目录。[计算存档](../计算存档/{BATCH.name}/计算结果概览.md)保留续算片段、源码快照及原核验记录；核查过程JSON不属于新的实验数据。', '',
              '所有数据仍位于Study04的Git忽略目录。目录整理入口为[按参数整理结果](../程序/按参数整理结果.py)，加`--verify`仅核对。', '']
    (RESULTS / 'README.md').write_text('\n'.join(index), encoding='utf-8')
    assert before == {name: sha(BATCH / name) for name in source_names}, '原批次被修改'
    return result_tables()


def verify():
    grid = groups()
    methods = [spec['variant'] for _, spec in load(BATCH / 'manifest.json')['config']['methods']]
    counts = Counter()
    seen = set()
    source_summary = load(BATCH / 'summary.json')
    tables = {}
    sample_hashes = {}
    for name, cells in grid.items():
        for cell in cells:
            key = (name, cell['n'])
            tables[key] = read_result_table(RESULTS / name / '估计结果' / f"n{cell['n']}.csv", cell, methods)
            sample_hashes[key] = [hashlib.sha256(np.array([float(row[f'观测值{i + 1}']) for i in range(cell['n'])], dtype=np.float64).tobytes()).hexdigest() for row in tables[key]]
    for original in raw_rows(BATCH / 'results.csv.gz'):
        name = group_name(original['beta'], original['eta'], original['gamma'])
        key = (name, int(original['n']))
        repeat = int(original['repeat_id'])
        variant = original['method_variant']
        row = tables[key][repeat]
        assert variant in methods
        assert tuple(row[f'{variant}_{label}'] for _, label in RESULT_FIELDS) == tuple(original[field] for field, _ in RESULT_FIELDS), ('估计值或状态不一致', key, repeat, variant)
        assert json.loads(original['extra'])['experiment']['sample_sha256'] == sample_hashes[key][repeat], ('样本指纹不对应', key, repeat)
        identity = (name, original['n'], original['repeat_id'], variant)
        assert identity not in seen, ('重复记录', identity)
        seen.add(identity)
        counts[name] += 1
    summary_groups = sample_files = sample_rows = sample_values = 0
    for name, cells in grid.items():
        folder = RESULTS / name
        manifest = load(parameter_file(name, 'manifest.json'))
        assert all(sha(BATCH / p) == value for p, value in manifest['source_sha256'].items()), '原批次指纹变化'
        assert all(sha(parameter_file(name, p)) == value for p, value in manifest['file_sha256'].items()), '参数目录文件变化'
        expected_summary = {k: v for k, v in source_summary.items() if group_name(v['beta'], v['eta'], v['gamma']) == name}
        assert load(parameter_file(name, 'summary.json')) == expected_summary
        with (BATCH / '条件汇总.csv').open(encoding='utf-8-sig', newline='') as f:
            expected_csv = [r for r in csv.DictReader(f) if group_name(r['beta'], r['eta'], r['gamma']) == name]
        with (folder / '条件汇总.csv').open(encoding='utf-8-sig', newline='') as f:
            assert list(csv.DictReader(f)) == expected_csv
        summary_groups += len(expected_summary)
        for c in cells:
            sample_values += check_sample_csv(folder / '原始样本' / f"n{c['n']}.csv", c)
            assert not (folder / '原始样本' / f"n{c['n']}.npz").exists()
            sample_rows += c['repeats']
            for repeat in range(c['repeats']):
                for variant in methods:
                    assert (name, str(c['n']), str(repeat), variant) in seen
            sample_files += 1
        assert counts[name] == sum(c['repeats'] * 7 for c in cells)
        assert not (folder / '估计明细.csv.gz').exists()
    expected = load(BATCH / 'prepared.json')
    assert sum(counts.values()) == expected['expected_rows']
    assert sample_rows == expected['sample_count'] and sample_files == len(expected['cells'])
    assert summary_groups == len(expected['cells']) * len(methods)
    result = dict(passed=True, parameter_groups=len(grid), attempt_rows=sum(counts.values()),
                  summary_groups=summary_groups, sample_files=sample_files, sample_rows=sample_rows,
                  sample_values=sample_values, result_table_files=len(tables), rows_by_parameter=dict(counts),
                  checks=[f'{sum(counts.values())}条估计参数和状态原字符串一致且无遗漏重复', f'{sum(counts.values())}条估计对应的样本SHA256一致', '详细汇总和CSV一致', 'CSV样本转回浮点数组逐字节一致', '原批次指纹未变'])
    dump(ARCHIVE / '按参数整理核验.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--verify', action='store_true', help='仅核对已有参数目录')
    mode.add_argument('--samples-csv', action='store_true', help='将已有参数目录的样本转换为CSV')
    mode.add_argument('--result-tables', action='store_true', help='将已有记录转为与样本对应的CSV结果表')
    args = parser.parse_args()
    if args.samples_csv:
        samples_to_csv()
    elif args.result_tables:
        result_tables()
    elif args.verify:
        verify()
    else:
        export()
