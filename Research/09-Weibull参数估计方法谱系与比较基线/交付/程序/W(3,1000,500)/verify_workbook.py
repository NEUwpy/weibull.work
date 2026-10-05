"""Check an exported workbook against the adjacent CSV tables."""
import argparse
import json
import math
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def column(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tables', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.tables.read_text(encoding='utf-8'))
    expected = data['sheets'] + [dict(name='汇总', rows=data['summary']['rows'])]
    checked = 0
    with zipfile.ZipFile(args.workbook) as z:
        assert z.testzip() is None
        names = [s.get('name') for s in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS)]
        assert names == [s['name'] for s in expected]
        shared = [''.join(c.itertext()) for c in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        for index, table in enumerate(expected, 1):
            xml = ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
            assert not xml.findall('s:mergeCells/s:mergeCell', NS)
            cells = {c.get('r'): c for c in xml.findall('.//s:c', NS)}
            assert not any(c.get('t') == 'e' for c in cells.values())
            def value(cell):
                if cell is None:
                    return None
                v = cell.find('s:v', NS)
                if cell.get('t') == 's':
                    return shared[int(v.text)]
                if cell.get('t') in ['str', 'inlineStr']:
                    return v.text if v is not None else None
                return float(v.text) if v is not None and v.text is not None else None
            for i, row in enumerate(table['rows'], 2):
                for j, expected_value in enumerate(row, 1):
                    actual = value(cells.get(column(j) + str(i)))
                    if expected_value is None:
                        assert actual in [None, '']
                    elif isinstance(expected_value, (int, float)):
                        assert actual is not None and math.isclose(actual, expected_value, rel_tol=2e-12, abs_tol=2e-10)
                    else:
                        assert actual == expected_value
                    checked += 1
    assert checked == 188610
    print(f'{checked} workbook data cells verified against saved CSVs; 11 paired sheets and no merged cells.')

if __name__ == '__main__':
    main()
