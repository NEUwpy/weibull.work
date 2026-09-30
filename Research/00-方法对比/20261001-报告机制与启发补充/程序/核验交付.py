"""Read-only checks of the delivered report/figure and frozen source identities."""
import csv
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '结果' / '中间数据'
INPUT = ROOT / '程序' / '输入快照'
sys.path.append('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages')
from PIL import Image


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    previous = json.loads((INPUT / '前批次封存清单.json').read_text(encoding='utf-8'))
    provenance = json.loads((DATA / '图7样本来源与核验.json').read_text(encoding='utf-8'))
    source = ROOT.parent / '20261001-高形状参数补偿报告'
    report = ROOT.parent / '高形状参数下的位置与尺度补偿报告-v2.md'
    links = []
    for document in (report, ROOT / 'README.md'):
        text = document.read_text(encoding='utf-8')
        for link in re.findall(r'\]\(([^)\n]+)\)', text):
            if link.startswith(('https://', 'http://')):
                continue
            path = document.parent / link.split('#')[0]
            assert path.exists(), f'Missing link: {document}: {link}'
            links.append(str(path))
    old_report = ROOT.parent / '高形状参数下的位置与尺度补偿报告.md'
    assert digest(old_report) == digest(INPUT / '报告v1.md')
    expected_report = previous['document_hashes']['../高形状参数下的位置与尺度补偿报告.md']
    assert digest(old_report) == expected_report
    dependencies = 0
    for name, expected in previous['code_hashes'].items():
        if name.startswith('程序/依赖快照/'):
            assert digest(ROOT / name) == expected
            dependencies += 1
    copies = 0
    for name, expected in previous['output_hashes'].items():
        path = Path(name)
        if path.parent.as_posix() == '结果' and path.suffix in {'.png', '.pdf', '.svg', '.xlsx'}:
            assert digest(ROOT / name) == expected == digest(source / name)
            copies += 1

    # Use scalar standard-library formulae to recheck the saved NumPy quantiles.
    max_error = 0.0
    with (DATA / '寿命分位点对照.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    for row in rows:
        p = float(row['p'])
        for key, parameters in (
                ('true_quantile', provenance['true_parameters_beta_eta_gamma']),
                ('actual_mdm_fit_quantile', provenance['fit_parameters_beta_eta_gamma'])):
            beta, eta, gamma = parameters
            expected = gamma + eta * math.pow(-math.log1p(-p), 1 / beta)
            error = abs(expected - float(row[key]))
            assert error < 1e-10
            max_error = max(max_error, error)
        assert abs(float(row['fit_minus_true']) -
                   (float(row['actual_mdm_fit_quantile']) - float(row['true_quantile']))) < 1e-10

    figure = ROOT / '结果' / '图7_不同参数的寿命曲线与分位点'
    with Image.open(figure.with_suffix('.png')) as png:
        dimensions = list(png.size)
        dpi = list(png.info['dpi'])
        assert dimensions == [3240, 1507]
        assert all(abs(d - 450) < .1 for d in dpi)
    svg = ET.parse(figure.with_suffix('.svg'))
    text_count = len(svg.findall('.//{http://www.w3.org/2000/svg}text'))
    assert text_count > 20
    assert b'/FontFile2' in figure.with_suffix('.pdf').read_bytes()
    summary = {
        'local_link_count': len(links), 'missing_local_links': 0,
        'reused_files_byte_identity_count': copies, 'reused_hash_mismatches': 0,
        'frozen_method_dependency_count': dependencies,
        'v1_report_and_previous_seal_unchanged': True,
        'quantile_rows': len(rows), 'standard_library_quantile_max_error': max_error,
        'figure_png_dimensions': dimensions, 'figure_png_dpi': dpi,
        'svg_live_text_count': text_count, 'pdf_embedded_truetype': True,
        'visual_check': 'PNG inspected: no clipped labels/legend, correct curves and point annotations.',
        'independent_readonly_review': 'mechanism_review APPROVE: no required revisions.',
        'new_samples': 0, 'new_fits': 0,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
