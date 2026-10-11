"""按报告1的方法顺序整理报告2；apply、render、verify可分别执行。"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, setup_runtime, write_atomic
setup_runtime()

ORDER = ['MDM', 'LSE', 'LRE', 'WMLE', 'MLE', 'MMLE']
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
REFERENCE = ROOT / '报告1：高形状参数下的估计偏移.md'
QA = HERE / (Path(__file__).stem + '-核验.json')
FREQUENCY = HERE / '第一章频率.csv'
FREQUENCY_QA = HERE / '第一章频率核对.json'
FIGURE = RESULT / '报告2/图1_明显异常估计频率.png'
SECTION = re.compile(r'^#### 2\.1\.\d+[^\n]*\[([A-Z]+)\][^\n]*\n.*?(?=^#### |^### |\Z)', re.M | re.S)
TAG = re.compile(r'\\tag\{(\d+)\}')
DISPLAY = re.compile(r'\$\$.*?\$\$', re.S)
FORMULA_REF = re.compile(r'式（\d+）(?:[、—]（\d+）)*')
FIGURE_REF = re.compile(r'图\d+(?:[、—]\d+)*')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data, newline=None):
    path = Path(path)
    if newline is None:
        newline = '\r\n' if path.exists() and b'\r\n' in path.read_bytes() else '\n'
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    write_atomic(path, text.replace('\n', newline).encode('utf-8'))


def module(stem):
    spec = importlib.util.spec_from_file_location('order_' + stem, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def protected():
    # 本次仅重排报告2图1及它的排列元数据，其他结果和过程输入逐字节核对。
    paths = [p for p in (RESULT / '报告2').rglob('*')
             if p.is_file() and p not in (FIGURE, FREQUENCY_QA)]
    for source in load(PROGRAM / '跨参数对比/13组合取数.json')['sources']:
        path = matrix_path(source)
        assert digest(path) == source['matrix_sha256'], path
        paths.append(path)
        paths.extend(p for p in (RESULT / source['program']).rglob('*') if p.is_file())
    for pattern in ('*数据.json', '*曲线.json', '*缓存.json', '*.csv', '*.npz'):
        paths.extend(HERE.glob(pattern))
    return {str(p): digest(p) for p in sorted(set(paths))}


def method_order(text):
    return [m[1] for m in SECTION.finditer(text)]


def remap(text, equations, figures):
    text = TAG.sub(lambda m: '\\tag{' + str(equations[int(m[1])]) + '}', text)
    text = FORMULA_REF.sub(lambda m: re.sub(r'\d+', lambda n: str(equations[int(n[0])]), m[0]), text)
    return FIGURE_REF.sub(lambda m: re.sub(r'\d+', lambda n: str(figures[int(n[0])]), m[0]), text)


def transform(text):
    sections = list(SECTION.finditer(text))
    assert len(sections) == 6 and set(m[1] for m in sections) == set(ORDER)
    blocks = {m[1]: m[0] for m in sections}
    moved = text[:sections[0].start()] + ''.join(
        re.sub(r'^(#### 2\.1\.)\d+', lambda m: m[1] + str(i), blocks[method], count=1)
        for i, method in enumerate(ORDER, 1)) + text[sections[-1].end():]
    equations = {int(old): new for new, old in enumerate(TAG.findall(moved), 1)}
    figures = {int(old): new for new, old in enumerate(re.findall(r'^\*\*图(\d+)｜', moved, re.M), 1)}
    moved = remap(moved, equations, figures)
    moved = moved.replace('LSE、LRE、MLE、WMLE、MMLE，共8种设置',
                          'LSE、LRE、WMLE、MLE、MMLE，共8种设置')
    intro, comparison = moved.split('### 2.3', 1)
    rows = list(re.finditer(r'^\| (MDM|LSE|LRE|WMLE|MLE|MMLE) \|[^\n]*\n', comparison, re.M))
    assert len(rows) == 6
    lookup = {m[1]: m[0] for m in rows}
    comparison = comparison[:rows[0].start()] + ''.join(lookup[m] for m in ORDER) + comparison[rows[-1].end():]
    final = intro + '### 2.3' + comparison
    # 每个方法原文完整保留，只允许小节、图号、式号变化。
    inverses = ({v:k for k,v in equations.items()}, {v:k for k,v in figures.items()})
    for section in SECTION.finditer(final):
        restored = remap(section[0], *inverses)
        normalize = lambda s: re.sub(r'^(#### 2\.1\.)\d+', r'\1N', s, count=1)
        assert normalize(restored) == normalize(blocks[section[1]]), section[1]
    assert Counter(TAG.sub('', m) for m in DISPLAY.findall(text)) == Counter(TAG.sub('', m) for m in DISPLAY.findall(final))
    assert Counter(re.findall(r'^\|.*组.*$', text, re.M)) == Counter(re.findall(r'^\|.*组.*$', final, re.M))
    return final, equations, figures


def sync_readme():
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8')
    text = text.replace('报告2的WMLE图16、17', '报告2的WMLE图12、13')
    text = text.replace('式（21）、（22）直接定义T₁、T₂。', '式（17）、（18）直接定义T₁、T₂。')
    text = text.replace('报告2图14的a、d', '报告2图4的a、d')
    text = text.replace('报告2的公式编号与正文引用由[20261011-报告2公式编号与引用.py](交付/程序/报告2/20261011-报告2公式编号与引用.py)保存；`apply`应用本次修改，`verify`核对编号、引用及公式和图表数据的一致性。',
                        '报告2首次增加公式编号与正文引用的记录由[20261011-报告2公式编号与引用.py](交付/程序/报告2/20261011-报告2公式编号与引用.py)保存；当前编号与引用核对使用下述方法顺序统一脚本。')
    if '20261011-方法顺序统一.py' not in text:
        note = ('两份报告的方法顺序统一为MDM、LSE、LRE、WMLE、MLE、MMLE。报告2的小节、图号、式号、正文引用、方法比较表及图1面板同步排列；样本、估计、公式内容、案例曲线和异常频率保持不变。'
                '[本次脚本](交付/程序/报告2/20261011-方法顺序统一.py)提供`apply`、`render`、`verify`及`all`入口，已接入`report2`；'
                '[核验记录](交付/程序/报告2/20261011-方法顺序统一-核验.json)、频率表及频率核对留在程序目录。\n\n')
        text = text.replace('## 整理与恢复', note + '## 整理与恢复')
    original = path.read_text(encoding='utf-8')
    if text != original:
        newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
        write_atomic(path, text.replace('\n',newline).encode('utf-8'))


def apply():
    sync_readme()
    text = REPORT.read_text(encoding='utf-8')
    if method_order(text) == ORDER:
        print('Method order already matches report 1.')
        return
    reference = REFERENCE.read_text(encoding='utf-8')
    assert re.findall(r'^### 2\.\d+ \[([A-Z]+)\]', reference, re.M) == ORDER
    original_hash = digest(REPORT)
    figure_before = digest(FIGURE)
    frequency_created = not FREQUENCY.exists() or not FREQUENCY_QA.exists()
    if frequency_created:
        # 只汇总存档估计；源频率缓存已退出当前目录。
        import matplotlib
        with matplotlib.rc_context(rc=matplotlib.rcParamsDefault):
            module('第一章频率').main()
    final, equations, figures = transform(text)
    record = dict(before_report_sha256=original_hash, before_method_order=method_order(text),
                  method_order=ORDER, equation_map=equations, figure_map=figures,
                  before_math=DISPLAY.findall(text), before_images=re.findall(r'!\[[^\]]*\]\((.*?)\)', text),
                  before_sample_rows=re.findall(r'^\|.*组.*$', text, re.M),
                  protected_sha256=protected(), before_frequency_metadata=load(FREQUENCY_QA),
                  figure_before_sha256=figure_before, frequency_cache_reconstructed=frequency_created,
                  figure_contract=dict(conclusion='异常频率随参数条件、样本量和方法而异。',
                                       archetype='quantitative grid', backend='Python', export='PNG only',
                                       evidence='原13个组合、n=7/15/30的六方法频率；按报告方法顺序排列。'),
                  samples_generated=0, estimates_recomputed=0)
    write_atomic(REPORT, final.encode('utf-8'))
    record['after_report_sha256'] = digest(REPORT)
    write_json(QA, record)
    print('Reordered six complete sections, figure numbers 1–21 and equation numbers 1–30.')


def render():
    import matplotlib
    frequency = module('第一章频率')
    table = list(csv.DictReader(FREQUENCY.open(encoding='utf-8-sig')))
    before = protected()
    with matplotlib.rc_context(rc=matplotlib.rcParamsDefault):
        contract = frequency.render(table)
    assert protected() == before
    metadata = load(FREQUENCY_QA)
    metadata['plot_methods'] = frequency.PLOT_METHODS
    # 仅更改排列，不重新统计或修改任何频率。
    write_json(FREQUENCY_QA, metadata)
    record = load(QA)
    record.update(figure=contract, figure_sha256=digest(FIGURE), frequency_csv_sha256=digest(FREQUENCY))
    write_json(QA, record)
    print('Reordered figure 1 from its unchanged saved frequency table.')


def refresh_checks():
    """当前制图脚本的保护记录接纳本次图1重排，其余哈希必须保持原值。"""
    record = load(QA)
    changed = {str(FIGURE), str(FREQUENCY_QA)}
    adjustments = record.get('active_check_updates', {})
    for stem, suffix in [('20261011-WMLE迭代残差与尺度方程', '-核验'),
                         ('20261011-展开观测位置差', '-核验'),
                         ('20261011-合并高估与MMLE实际流程', '')]:
        path = HERE / (stem + suffix + '.json')
        obj = load(path)
        previous_sha = adjustments.get(path.name, {}).get('before_sha256', digest(path))
        updates = obj.get('method_order_revision', {}).get('changed_protected_files', {})
        for key in ('protected_sha256', 'source_sha256'):
            for p, expected in obj.get(key, {}).items():
                actual = digest(p)
                if actual != expected:
                    assert p in changed, p
                    updates[p] = dict(before=expected, after=actual)
                    obj[key][p] = actual
        script = HERE / (stem + '.py')
        if 'script_sha256' in obj:
            obj['script_sha256'] = digest(script)
        obj['method_order_revision'] = dict(record=QA.name, changed_protected_files=updates)
        write_json(path, obj, newline='\r\n' if suffix=='' else None)
        adjustments[path.name] = dict(before_sha256=previous_sha, after_sha256=digest(path), changes=updates)
    record['active_check_updates'] = adjustments
    write_json(QA, record)


def verify():
    record = load(QA)
    text = REPORT.read_text(encoding='utf-8')
    assert method_order(text) == ORDER
    assert re.findall(r'^### 2\.\d+\s+\[([A-Z]+)\]', REFERENCE.read_text(encoding='utf-8'), re.M) == ORDER
    assert TAG.findall(text) == [str(i) for i in range(1,31)]
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(i) for i in range(1,22)]
    refs = [int(n) for m in FORMULA_REF.finditer(text) for n in re.findall(r'\d+',m[0])]
    assert set(refs) == set(range(1,31))
    assert set(int(n) for m in FIGURE_REF.finditer(text) for n in re.findall(r'\d+',m[0])) == set(range(1,22))
    eq_map = {int(k):v for k,v in record['equation_map'].items()}
    math_text = module('20261011-MMLE对数似然峰图').restore(text) if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists() else text
    formulas = {int(TAG.search(m)[1]): TAG.sub('',m) for m in DISPLAY.findall(math_text)}
    for m in record['before_math']:
        assert formulas[eq_map[int(TAG.search(m)[1])]] == TAG.sub('',m)
    paths = re.findall(r'!\[[^\]]*\]\((.*?)\)', text)
    assert Counter(paths) == Counter(record['before_images'])
    assert all((ROOT / p).is_file() for p in paths)
    table_record = HERE / '20261011-样本表参数顺序-核验.json'
    row_map = load(table_record)['row_map'] if table_record.exists() else {}
    expected_rows = [row_map.get(row,row) for row in record['before_sample_rows']]
    pair_record = HERE / '20261011-MDM近真值对照-核验.json'
    if pair_record.exists():
        approved_rows = load(pair_record)['row_map']
        expected_rows = [approved_rows.get(row,row) for row in expected_rows]
    row_text = text
    if (HERE / '20261011-MDM回退程序归因.json').exists():
        row_text = module('20261011-MDM回退程序归因').restore(text)
    assert Counter(re.findall(r'^\|.*组.*$', row_text,re.M)) == Counter(expected_rows)
    expected_protection = record['protected_sha256']
    if pair_record.exists():
        expected_protection = module('20261011-MDM近真值对照').updated_protection(expected_protection)
    assert protected() == expected_protection
    original = record['before_frequency_metadata']
    current = load(FREQUENCY_QA)
    assert {k:v for k,v in original.items() if k!='plot_methods'} == {k:v for k,v in current.items() if k!='plot_methods'}
    assert current['plot_methods'] == ['MDM δ=0.20'] + ORDER[1:]
    assert record['figure']['panel_titles'] == current['plot_methods']
    assert record['figure']['plot_row_order'] == original['plot_row_order']
    assert record['figure']['color_limits'] == original['color_limits']
    counts = Counter()
    for row in csv.DictReader((RESULT / '报告2/数据/20261010-各类异常参数空间.csv').open(encoding='utf-8-sig')):
        counts[row['method'], row['combination'], int(row['n'])] += int(row['count'])
    assert sum(counts.values()) == 963
    for row in csv.DictReader(FREQUENCY.open(encoding='utf-8-sig')):
        if row['method'] in current['plot_methods']:
            assert int(row['abnormal']) == counts[row['method'], row['combination'], int(row['n'])], row
    assert digest(FREQUENCY) == record['frequency_csv_sha256'] and digest(FIGURE) == record['figure_sha256']
    # MMLE的形状得分引用仍指向MLE得分，而非同号的其他方法。
    mmle = next(m[0] for m in SECTION.finditer(math_text) if m[1]=='MMLE')
    assert f'将式（25）的位置代入式（{eq_map[13]}）' in mmle
    record.update(after_report_sha256=digest(REPORT), script_sha256=digest(__file__),
                  validation=dict(status='passed', methods=6, equations=30, figures=21,
                                  formula_bodies_and_frequency_unchanged=True,
                                  sample_tables_and_figures_match_approved_revisions=True,
                                  thirteen_combination_results_unchanged=True))
    write_json(QA, record)
    print('PASS: method order, figure/formula references and approved sample rows; archived estimates and frequency preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply','render','verify','all'])
    action = parser.parse_args().action
    if action == 'all':
        apply()
        render()
        refresh_checks()
        verify()
    else:
        globals()[action]()
