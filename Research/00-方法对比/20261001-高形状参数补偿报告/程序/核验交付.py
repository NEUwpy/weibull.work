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
    process = json.loads((DATA / '逐法过程曲线.json').read_text(encoding='utf-8'))
    figure_checks = json.loads((DATA / '逐法图核验.json').read_text(encoding='utf-8'))
    assert len(process['curves']) == 755
    curve_points = sum(len(r['points']) for r in process['curves'])
    assert curve_points == 110213
    for name, expected in process['provenance']['input_hashes'].items():
        assert digest(ROOT / name) == expected
    fit_index = {(r['beta'], r['n'], r['sample_id'], r['method']): r for r in fits}
    original_fits = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    for method in ('mdm', 'lse', 'lre', 'wmle', 'mle'):
        for beta, n in ((2, 7), (5, 7), (5, 15)):
            rr = [r for r in process['curves'] if r['source'] == 'paired' and r['method'] == method and r['beta'] == beta and r['n'] == n]
            assert len(rr) == 50 and {r['sample_id'] for r in rr} == set(range(1, 51))
            for r in rr:
                assert r['fit'] == fit_index[beta, n, r['sample_id'], method]
                assert all(0 <= p[0] < r['sample_min'] for p in r['points'])
                if r['fit']['converged']:
                    assert r['returned'][0] == r['fit']['gamma_hat']
        case = next(r for r in process['curves'] if r['source'] == 'original' and r['method'] == method)
        actual = next(r for r in original_fits if r['beta'] == 5 and r['n'] == 7 and r['method'] == method and r['sample_id'] == case['sample_id'])
        assert actual == case['fit']
    for r in figure_checks['ecdf']:
        values = [f[r['parameter']] for f in original_fits if f['beta'] == 5 and f['n'] == r['n'] and f['method'] == r['method'] and f['converged']]
        assert len(values) == r['success'] and r['failure'] == 50 - len(values)
        assert r['x_limits'][0] <= min(values) == r['minimum']
        assert r['maximum'] == max(values) <= r['x_limits'][1]
    for r in process['regression_truth_invariance'].values():
        assert r['paired_groups'] == 50 and r['maximum_absolute_loss_difference'] < 1e-12
    for r in process['mdm_envelope']:
        assert r['groups'] == 50 and r['maximum_gradient_difference'] < 5e-5
        assert all(abs(c['envelope_gradient']) <= c['weight_sd'] + 1e-12 for c in r['checks'])
    new_figure_names = ['图1_原案例参数分布'] + [r['file'] for r in figure_checks['process_figures']]
    for name in new_figure_names:
        figure = ROOT / '结果' / name
        with Image.open(figure.with_suffix('.png')) as png:
            assert png.size == (3240, 2250 if name == new_figure_names[0] else 2407)
            assert all(abs(v-450) < .1 for v in png.info['dpi'])
        assert len(ET.parse(figure.with_suffix('.svg')).findall('.//{http://www.w3.org/2000/svg}text')) > 25
        assert b'/FontFile2' in figure.with_suffix('.pdf').read_bytes()

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
        'complete_original_ecdf_panels_checked': 6,
        'method_process_figures_checked': 5, 'all_condition_curves': 750,
        'original_process_cases': 5, 'process_candidate_points': curve_points,
        'process_inputs_hash_checked': True, 'saved_fits_and_failures_unchanged': True,
        'regression_affine_invariance_checked': True, 'mdm_envelope_bound_checked': True,
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
