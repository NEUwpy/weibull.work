"""统一报告2样本表为形状、尺度、位置，并保存图3对照样本筛查。"""
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
from 共用 import ROOT, RESULT, write_atomic
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
QA = HERE / (Path(__file__).stem + '-核验.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def module(stem):
    spec = importlib.util.spec_from_file_location('table_order_' + stem, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def write_json(data):
    write_atomic(QA, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def write_text(path, text):
    data = text.encode('utf-8')
    previous = path.read_bytes()
    try:
        write_atomic(path,data)
    except PermissionError:
        # 编辑器可能允许写入但不允许替换文件；仅在内容仍未变化时原位保存。
        assert path.read_bytes()==previous, 'File changed during table revision'
        path.write_bytes(data)
    assert path.read_bytes()==data


def tables(text):
    return list(re.finditer(r'^\| 样本 \|[^\n]*\n(?:\|[^\n]*\n)+', text, re.M))


def cells(line):
    return [s.strip() for s in line.strip().strip('|').split('|')]


def table_records(text):
    records = []
    for match in tables(text):
        lines = match[0].splitlines()
        header = cells(lines[0])
        for line in lines[2:]:
            records.append(json.dumps(dict(zip(header,cells(line))), ensure_ascii=False, sort_keys=True))
    return Counter(records)


def transform(text):
    replacements = {}
    found = tables(text)
    for match in reversed(found):
        lines = match[0].splitlines()
        header = cells(lines[0])
        order = [next(i for i,c in enumerate(header) if c.startswith(name)) for name in ('形状','尺度','位置')]
        slots = sorted(order)
        updated = []
        for line in lines:
            values = cells(line)
            original = list(values)
            for target, source in zip(slots, order):
                values[target] = original[source]
            result = '| ' + ' | '.join(values) + ' |'
            updated.append(result)
            if result != line:
                replacements[line] = result
        text = text[:match.start()] + '\n'.join(updated) + '\n' + text[match.end():]
    return text, replacements, len(found)


def candidates():
    path = RESULT / '报告2/数据/全量流程定位.csv'
    rows = [r for r in csv.DictReader(path.open(encoding='utf-8-sig'))
            if r['combination']=='W(5,100,500)' and int(r['n'])==7 and r['method']=='MDM δ=0.20']
    assert len(rows)==50
    rankings = []
    for row in rows:
        estimates = {p:float(row[p+'_hat']) for p in ('beta','eta','gamma')}
        errors = {p:abs(estimates[p]/float(row[p+'_true'])-1) for p in estimates}
        rankings.append(dict(group=int(row['group']), estimates=estimates, relative_errors=errors,
                             maximum_relative_error=max(errors.values()),
                             mean_squared_relative_error=sum(v*v for v in errors.values())/3,
                             root_solver=row['archived_root_solver'], abnormal=row['abnormal']=='True'))
    rankings.sort(key=lambda r:(r['maximum_relative_error'],r['mean_squared_relative_error'],r['group']))
    eligible = [r for r in rankings if not r['abnormal'] and r['root_solver']=='brent']
    assert rankings[0]['group']==22 and eligible[0]['group']==44
    assert rankings[0]['root_solver']=='right_edge_fit'
    return dict(source_sha256={str(path):digest(path)}, combination='W(5,100,500)', n=7, delta=.2,
                selection_rule='minimize largest relative parameter error; then mean squared relative error and group ID',
                candidates=rankings, best_overall=rankings[0], best_gradient_intersection=eligible[0],
                selected_report_sample=10, report_sample_changed=False)


def apply():
    old = REPORT.read_text(encoding='utf-8')
    text, replacements, count = transform(old)
    assert count==13 and table_records(old)==table_records(text)
    if text==old and QA.exists():
        print('All thirteen sample tables already use shape, scale, location.')
        return
    order = module('20261011-方法顺序统一')
    record = dict(before_report_sha256=digest(REPORT), table_count=count,
                  row_map=replacements, before_table_records=dict(table_records(old)),
                  before_math=re.findall(r'\$\$.*?\$\$',old,re.S),
                  before_images=re.findall(r'!\[[^\]]*\]\((.*?)\)',old),
                  protected_sha256=order.protected(), mdm_control_screen=candidates(),
                  samples_generated=0, estimates_recomputed=0)
    write_text(REPORT,text)
    record['after_report_sha256']=digest(REPORT)
    write_json(record)
    readme=ROOT/'README.md'
    note='样本表的参数列统一为形状β̂、尺度η̂、位置γ̂；[本次脚本](交付/程序/报告2/20261011-样本表参数顺序.py)保存列调整与图3存档对照筛查，核验记录留在程序目录。\n\n'
    content=readme.read_text(encoding='utf-8')
    if '20261011-样本表参数顺序.py' not in content:
        content=content.replace('## 整理与恢复',note+'## 整理与恢复')
        newline='\r\n' if b'\r\n' in readme.read_bytes() else '\n'
        write_text(readme,content.replace('\n',newline))
    print('Reordered thirteen sample tables; all cell values and plots retained.')


def verify():
    record=load(QA)
    text=REPORT.read_text(encoding='utf-8')
    assert len(tables(text))==13
    for match in tables(text):
        header=cells(match[0].splitlines()[0])
        indices=[next(i for i,c in enumerate(header) if c.startswith(name)) for name in ('形状','尺度','位置')]
        assert indices==sorted(indices)
    pair_record = HERE / '20261011-MDM近真值对照-核验.json'
    expected_tables = load(pair_record)['after_table_records'] if pair_record.exists() else record['before_table_records']
    assert dict(table_records(text))==expected_tables
    math_text = module('20261011-MMLE对数似然峰图').restore(text) if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists() else text
    assert re.findall(r'\$\$.*?\$\$',math_text,re.S)==record['before_math']
    assert re.findall(r'!\[[^\]]*\]\((.*?)\)',text)==record['before_images']
    expected_protection = record['protected_sha256']
    if pair_record.exists():
        expected_protection = module('20261011-MDM近真值对照').updated_protection(expected_protection)
    assert module('20261011-方法顺序统一').protected()==expected_protection
    assert candidates()==record['mdm_control_screen']
    record.update(after_report_sha256=digest(REPORT),script_sha256=digest(__file__),
                  validation=dict(status='passed',sample_tables=13,cell_values_match_approved_revisions=True,
                                  formulas_matrices_and_frequency_unchanged=True))
    write_json(record)
    print('PASS: thirteen column orders and approved sample rows; formulas, matrices and frequency preserved.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='verify',choices=['apply','verify','all'])
    action=parser.parse_args().action
    if action=='all':
        apply()
        verify()
    else:
        globals()[action]()
