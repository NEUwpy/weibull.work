"""Workbook parsing preserves source values and refuses ambiguous/unsafe inputs."""
import io
import sys
import zipfile
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studies.common.workbook import parse_workbook, MAX_WORKBOOK_BYTES


def workbook(*, formula=False, duplicate=False, mismatch=False):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    def text(address, value):
        return f'<c r="{address}" t="inlineStr"><is><t>{value}</t></is></c>'
    def num(address, value):
        return f'<c r="{address}" s="1"><v>{value}</v></c>'
    sample = text('A1', '样本') + ''.join(text(f'{c}1', f'第{i}顺序统计量') for i, c in enumerate('BCD', 1))
    sample += num('A2', 1) + num('B2', 1.125) + num('C2', 2.25) + num('D2', 3.5)
    if duplicate:
        sample += num('A3', 1) + num('B3', 4) + num('C3', 5) + num('D3', 6)
    result = text('A1', '样本') + text('B1', 'MDM δ=0.10') + text('E1', 'MLM')
    result += ''.join(text(c + '2', v) for c, v in zip('BCDEFG', ['α', 'β', 'γ'] * 2))
    result += num('A3', 2 if mismatch else 1) + num('B3', 2) + num('C3', 1000) + num('D3', 0) + ''.join(text(c + '3', '—') for c in 'EFG')
    if formula:
        result = result.replace('<v>1000</v>', '<f>SUM(1,2)</f><v>1000</v>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="生成样本_n3" sheetId="1" r:id="r1"/><sheet name="估计结果_n3" sheetId="2" r:id="r2"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr('xl/styles.xml', f'<styleSheet xmlns="{ns}"><numFmts><numFmt numFmtId="164" formatCode="0.000000"/></numFmts><cellXfs><xf numFmtId="0"/><xf numFmtId="164"/></cellXfs></styleSheet>')
        for i, content in enumerate([sample, result], 1):
            merges = '<mergeCells><mergeCell ref="A1:A2"/><mergeCell ref="B1:D1"/><mergeCell ref="E1:G1"/></mergeCells>' if i == 2 else ''
            z.writestr(f'xl/worksheets/sheet{i}.xml', f'<worksheet xmlns="{ns}"><sheetData><row>{content}</row></sheetData>{merges}</worksheet>')
    return out.getvalue()


def test_values_missing_results_aliases_and_headers_are_preserved():
    result = parse_workbook(workbook(), 'W2,1000,500.xlsx')
    group = result['groups']['3']
    assert group['samples'] == [[1, 1.125, 2.25, 3.5]]
    assert group['resultRows'] == [[1, 2, 1000, 0, '—', '—', '—']]
    assert [b['method'] for b in group['blocks']] == ['mdm', 'mle']
    assert result['sheets'][1]['rows'][1][1:4] == ['α', 'β', 'γ']
    assert result['sheets'][1]['merges'] == [[0, 0, 1, 0], [0, 1, 0, 3], [0, 4, 0, 6]]
    assert result['sheets'][1]['formats'][2][1] == '0.000000'
    assert result['source']['kind'] == 'imported'
    assert result['source']['codeVersion'] is None


@pytest.mark.parametrize('flag', ['formula', 'duplicate', 'mismatch'])
def test_formula_and_ambiguous_record_identity_are_rejected(flag):
    with pytest.raises(ValueError):
        parse_workbook(workbook(**{flag: True}), 'W2,1000,500.xlsx')


def test_filename_is_a_label_and_does_not_load_a_file_or_invent_provenance():
    result = parse_workbook(workbook(), '../../custom.xlsx')
    assert result['filename'] == 'custom.xlsx'
    assert result['truth'] is None
    assert result['source']['calculationTime'] is None


def test_invalid_and_oversized_files_are_rejected():
    for raw in [b'not an xlsx', b'x' * (MAX_WORKBOOK_BYTES + 1)]:
        with pytest.raises(ValueError):
            parse_workbook(raw, 'test.xlsx')
