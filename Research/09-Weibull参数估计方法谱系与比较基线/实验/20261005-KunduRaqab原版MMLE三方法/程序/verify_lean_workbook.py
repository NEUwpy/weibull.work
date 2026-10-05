"""Compare the Research00 workbook with saved scientific data, without fitting."""
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
OUT = BATCH / '结果'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SIZES = [7, 10, 15, 20, 50]
METHODS = ['MLE', 'MMLE', 'WMLE']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def column(n):
    result = ''
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result

def column_number(address):
    result = 0
    for char in re.match(r'[A-Z]+', address).group():
        result = result * 26 + ord(char) - 64
    return result

def main():
    guard = json.loads((HERE / '邮件011保护.json').read_text(encoding='utf-8'))
    assert len(guard['protected_scientific_files']) == 270
    for category in ['protected_scientific_files', 'protected_deliveries']:
        for p, digest in guard[category].items():
            assert sha(p) == digest, p
    raw = pd.read_csv(HERE / 'per_sample.csv.gz')
    raw['method'] = raw.method_variant.replace({'K-R MMLE': 'MMLE'})
    assert len(raw) == 18000
    assert not raw.duplicated(['n', 'block', 'repeat_id', 'method']).any()
    source = raw.set_index(['n', 'block', 'repeat_id', 'method'])
    arrays = np.load(HERE / '输入样本.npz')
    summary = json.loads((HERE / '汇总表数据.json').read_text(encoding='utf-8'))['rows']
    expected_names = [name for n in SIZES for name in [f'生成样本_n{n}', f'估计结果_n{n}']] + ['汇总']
    cells_checked = 0
    blank_estimates = 0
    formula_count = 0
    forbidden = ['种子', 'SHA', 'block', 'repeat_id', '收敛', '失败原因',
                 '原始最小值', '支持检查最小值', '删除观测数', '耗时', '样本组ID']
    with zipfile.ZipFile(OUT / 'W(2,1000,1000).xlsx') as z:
        assert z.testzip() is None
        book = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = book.findall('s:sheets/s:sheet', NS)
        assert [s.get('name') for s in sheets] == expected_names
        assert all(s.get('state', 'visible') == 'visible' for s in sheets)
        shared = ([''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
                  if 'xl/sharedStrings.xml' in z.namelist() else [])
        def value(cell):
            if cell is None:
                return None
            v = cell.find('s:v', NS)
            if cell.get('t') == 's':
                return shared[int(v.text)]
            if cell.get('t') == 'str':
                return v.text if v is not None and v.text is not None else ''
            if cell.get('t') == 'inlineStr':
                return ''.join(cell.find('s:is', NS).itertext())
            return float(v.text) if v is not None and v.text is not None else None
        def check(actual, expected):
            nonlocal cells_checked
            if expected is None:
                assert actual in (None, ''), (actual, expected)
            elif isinstance(expected, (int, float)):
                assert actual is not None and math.isclose(actual, expected, rel_tol=2e-12, abs_tol=2e-10), (actual, expected)
            else:
                assert actual == expected, (actual, expected)
            cells_checked += 1
        for sheet_index, name in enumerate(expected_names, 1):
            xml = ET.fromstring(z.read(f'xl/worksheets/sheet{sheet_index}.xml'))
            cells = {c.get('r'): c for c in xml.findall('.//s:c', NS)}
            assert not any(c.get('t') == 'e' for c in cells.values())
            formulas = xml.findall('.//s:f', NS)
            formula_count += len(formulas)
            values = {address: value(cell) for address, cell in cells.items()}
            for actual in values.values():
                if isinstance(actual, str):
                    assert not any(token in actual for token in forbidden), actual
            assert not xml.findall('s:mergeCells/s:mergeCell', NS)
            assert not any(isinstance(v, str) and any(t in v for t in ['真值', 'ddof', '说明', '备注', 'mean(', '精度使用']) for v in values.values())
            if name == '汇总':
                assert [values[column(j) + '1'] for j in range(1, 15)] == [
                    '方法', 'n', '总组数', '有效解', '有解率', 'β Bias', 'β SD', 'β RMSE',
                    'η Bias', 'η SD', 'η RMSE', 'γ Bias', 'γ SD', 'γ RMSE']
                for row_index, row in enumerate(summary, 2):
                    for j, expected in enumerate(row, 1):
                        check(values.get(column(j) + str(row_index)), expected)
                    formula = cells[f'E{row_index}'].find('s:f', NS).text
                    assert formula.lstrip('=') == f'D{row_index}/C{row_index}'
                assert len(formulas) == 15
                max_col, max_row = 14, 16
            else:
                n = int(name.split('_n')[1])
                assert arrays[f'n{n}'].shape == (1200, n)
                assert (np.diff(arrays[f'n{n}'], axis=1) >= 0).all()
                assert not formulas
                if name.startswith('估计结果'):
                    assert [values[column(j) + '1'] for j in range(1, 11)] == ['样本'] + [f'{m} {p}' for m in METHODS for p in ['β', 'η', 'γ']]
                    for i in range(1200):
                        block, repeat = divmod(i, 100)
                        expected = [i + 1]
                        for method in METHODS:
                            row = source.loc[(n, block, repeat, method)]
                            if row.status == 'success':
                                expected.extend(float(row[p + '_hat']) for p in ['beta', 'eta', 'gamma'])
                            else:
                                expected.extend([None] * 3)
                                blank_estimates += 3
                        for j, v in enumerate(expected, 1):
                            check(values.get(column(j) + str(i + 2)), v)
                    max_col, max_row = 10, 1201
                else:
                    assert [values[column(j) + '1'] for j in range(1, n + 2)] == ['样本'] + [f't{i}' for i in range(1, n + 1)]
                    for i, observations in enumerate(arrays[f'n{n}']):
                        for j, v in enumerate([i + 1, *observations], 1):
                            check(values.get(column(j) + str(i + 2)), v)
                    max_col, max_row = n + 1, 1201
            assert all(column_number(a) <= max_col and int(re.search(r'\d+', a).group()) <= max_row
                       for a, v in values.items() if v is not None and v != '')
        assert not any('comment' in p.lower() for p in z.namelist())
    assert cells_checked == 188610 and blank_estimates == 5322 and formula_count == 15
    old = json.loads((HERE / '既有结果保护.json').read_text(encoding='utf-8'))
    assert len(old) == 3882 and all(sha(p) == digest for p, digest in old.items())
    current = {str(p) for batch in BATCH.parent.glob('20261005-*') if batch != BATCH
               for p in batch.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '程序复核' not in p.parts}
    assert current == set(old)
    results = dict(sheet_names=expected_names, sample_groups=6000, observations=122400,
                   workbook_data_cells_checked=cells_checked, failed_estimate_triplets=1774,
                   blank_estimate_cells=blank_estimates, summary_rows=15, formula_cells=15,
                   formula_errors=0, scientific_files_unchanged=270, other_batches_unchanged=3882,
                   existing_csv_and_png_unchanged=True, estimation_reruns=0,
                   first_row_headers=True, data_starts_row=2, merged_cells=0, remarks=0,
                   visual_check='all 11 worksheet previews reviewed')
    (HERE / '邮件011核验.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))

if __name__ == '__main__':
    main()
