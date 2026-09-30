"""Check the consolidated report, scientific data and frozen dependencies."""
import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '结果' / '中间数据'
INPUT = ROOT / '程序' / '输入快照'
SCAN = ROOT / '结果' / '独立种子扫描'
sys.path.append('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages')
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = ROOT.parent / '高形状参数下的位置与尺度补偿报告.md'
    links = []
    for document in (report, ROOT / 'README.md'):
        for link in re.findall(r'\]\(([^)\n]+)\)', document.read_text(encoding='utf-8')):
            if link.startswith(('https://', 'http://')):
                continue
            path = document.parent / link.split('#')[0]
            assert path.exists(), f'Missing link: {document}: {link}'
            links.append(path)
    spec = importlib.util.spec_from_file_location('report_generator', ROOT / '程序' / '生成报告.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert report.read_text(encoding='utf-8') == generator.REPORT_TEXT
    assert report.read_text(encoding='utf-8').count('## 第') == 3
    fits = json.loads((DATA / '实际估计.json').read_text(encoding='utf-8'))
    samples = json.loads((DATA / '样本.json').read_text(encoding='utf-8'))
    assert len(fits) == 4200 and len(samples) == 700

    provenance = json.loads((DATA / '图7样本来源与核验.json').read_text(encoding='utf-8'))
    archived = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    actual = next(r for r in archived if r['method'] == 'mdm' and r['beta'] == 5
                  and r['n'] == 7 and r['sample_id'] == provenance['sample_id'])
    assert [actual[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')] == provenance['fit_parameters_beta_eta_gamma']
    for name, expected in provenance['input_hashes'].items():
        assert name in {'原案例估计.json', '原案例核验.json'}
        assert digest(INPUT / name) == expected
    with (DATA / '寿命分位点对照.csv').open(encoding='utf-8-sig', newline='') as stream:
        quantiles = list(csv.DictReader(stream))
    assert len(quantiles) == 4
    for row in quantiles:
        p = float(row['p'])
        for key, parameters in (
                ('true_quantile', provenance['true_parameters_beta_eta_gamma']),
                ('actual_mdm_fit_quantile', provenance['fit_parameters_beta_eta_gamma'])):
            beta, eta, gamma = parameters
            expected = gamma + eta * math.pow(-math.log1p(-p), 1 / beta)
            assert abs(float(row[key]) - expected) < 1e-10
        assert abs(float(row['fit_minus_true']) -
                   (float(row['actual_mdm_fit_quantile']) - float(row['true_quantile']))) < 1e-10
    assert abs(float(quantiles[2]['p']) - (1 - math.exp(-1))) < 1e-15

    record = json.loads((DATA / '整理记录.json').read_text(encoding='utf-8'))
    unchanged_scan_files = 0
    for item in record['copies']:
        if '/结果/独立种子扫描/' in item['target']:
            assert digest(ROOT.parent / item['target']) == item['sha256']
            unchanged_scan_files += 1
    config = json.loads((SCAN / '扫描配置.json').read_text(encoding='utf-8'))
    assert config['seed_namespace'] == 2026100101
    assert config['total_samples'] == 1400 and config['total_fits'] == 7000
    assert config['n_repeats_per_cell'] == 100
    cells = sorted(SCAN.glob('b*_n*'))
    assert len(cells) == 14
    rows = 0
    for cell in cells:
        manifest = json.loads((cell / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['seed_namespace'] == 2026100101
        with (cell / 'results.csv').open(encoding='utf-8-sig', newline='') as stream:
            cell_rows = sum(1 for _ in csv.DictReader(stream))
        assert cell_rows == 500
        rows += cell_rows
    assert rows == 7000
    dependencies = 0
    for item in config['code']:
        if '依赖快照' in item['path']:
            path = ROOT / item['path']
            assert digest(path) == item['sha256']
            dependencies += 1
    assert dependencies == 16
    assert not (ROOT.parent / '20261001-报告机制与启发补充').exists()
    assert not (ROOT.parent / '20261001-高形状参数偏移研究').exists()
    assert not (ROOT.parent / '高形状参数下的位置与尺度补偿报告-v2.md').exists()

    figure = ROOT / '结果' / '图7_不同参数的寿命曲线与分位点'
    with Image.open(figure.with_suffix('.png')) as png:
        dimensions = list(png.size)
        assert dimensions == [3240, 1507]
        assert all(abs(v - 450) < .1 for v in png.info['dpi'])
    svg_text = len(ET.parse(figure.with_suffix('.svg')).findall('.//{http://www.w3.org/2000/svg}text'))
    assert svg_text > 20
    assert b'/FontFile2' in figure.with_suffix('.pdf').read_bytes()
    summary = {
        'local_links_checked': len(links), 'missing_links': 0,
        'report_matches_latest_generator': True, 'three_chapters': True,
        'paired_samples': len(samples), 'paired_fit_records': len(fits),
        'independent_samples': 1400, 'independent_fit_records': rows,
        'independent_source_files_preserved_bytewise': unchanged_scan_files,
        'frozen_scan_dependency_hashes_checked': dependencies,
        'figure7_sample_id': provenance['sample_id'], 'quantile_rows_checked': len(quantiles),
        'removed_directory_and_old_report_checks': True,
        'svg_live_text_count': svg_text, 'png_dimensions': dimensions,
        'new_samples': 0, 'new_fits': 0,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
