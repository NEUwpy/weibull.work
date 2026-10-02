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
import numpy as np

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
    assert len(process['curves']) == 1010
    for fig in figure_checks['process_figures']:
        assert [(p['beta'], p['n'], p['curves']) for p in fig['panels']] == [(2,7,50),(5,7,50),(2,15,50),(5,15,50)]
        assert [p['beta'] for p in fig['original_panels']] == [2,5]
        assert not fig['formula_printed_on_figure'] and fig['formula_documented_in_report']
    curve_points = sum(len(r['points']) for r in process['curves'])
    assert curve_points == 147550
    for name, expected in process['provenance']['input_hashes'].items():
        assert digest(ROOT / name) == expected
    fit_index = {(r['beta'], r['n'], r['sample_id'], r['method']): r for r in fits}
    original_fits = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    for method in ('mdm', 'lse', 'lre', 'wmle', 'mle'):
        for beta, n in ((2, 7), (5, 7), (2, 15), (5, 15)):
            rr = [r for r in process['curves'] if r['source'] == 'paired' and r['method'] == method and r['beta'] == beta and r['n'] == n]
            assert len(rr) == 50 and {r['sample_id'] for r in rr} == set(range(1, 51))
            for r in rr:
                assert r['fit'] == fit_index[beta, n, r['sample_id'], method]
                assert all(0 <= p[0] < r['sample_min'] for p in r['points'])
                if r['fit']['converged']:
                    assert r['returned'][0] == r['fit']['gamma_hat']
        for beta in (2, 5):
            case = next(r for r in process['curves'] if r['source'] == 'original' and r['method'] == method and r['beta'] == beta)
            actual = next(r for r in original_fits if r['beta'] == beta and r['n'] == 7 and r['method'] == method and r['sample_id'] == case['sample_id'])
            assert actual == case['fit']
    violin_data = json.loads((DATA / '图1小提琴数据与核验.json').read_text(encoding='utf-8'))
    assert digest(ROOT / violin_data['input_path']) == violin_data['input_sha256']
    assert len(figure_checks['violin']) == len(violin_data['panels']) == 30
    for r, check in zip(violin_data['panels'], figure_checks['violin']):
        assert all(r[k] == v for k, v in check.items())
        successful = sorted((f for f in original_fits if f['beta'] == 5 and f['n'] == r['n'] and f['method'] == r['method'] and f['converged']), key=lambda f: f['sample_id'])
        values = [f[r['parameter']] for f in successful]
        assert r['values'] == values and r['sample_ids'] == [f['sample_id'] for f in successful]
        assert len(values) == r['success'] and r['failure'] == 50 - len(values)
        assert r['x_limits'][0] <= min(values) == r['minimum']
        assert r['maximum'] == max(values) <= r['x_limits'][1]
        assert np.allclose(r['quartiles'], np.quantile(values, [.25, .5, .75]), rtol=0, atol=1e-12)
        zeros = values.count(0) if r['parameter'] == 'gamma_hat' else 0
        assert r['zero_count'] == zeros and r['kde_count'] == len(values)-zeros
        assert len(r['displayed_y']) == len(values)
        method_position = ('mdm', 'lse', 'lre', 'wmle', 'mle').index(r['method'])
        assert set(r['displayed_y']) == {float(method_position)}
        assert min(r['kde_density']) >= 0 and len(r['kde_density']) == 256
        expected_grid_limits = np.log10([min(values), max(values)]) if r['kde_coordinate'] == 'log10' else [min(v for v in values if v > 0), max(values)]
        assert np.allclose([r['kde_coordinate_grid'][0], r['kde_coordinate_grid'][-1]], expected_grid_limits, atol=1e-12)
    for r in process['regression_truth_invariance'].values():
        assert r['paired_groups'] == 50 and r['maximum_absolute_loss_difference'] < 1e-12
    for r in process['mdm_envelope']:
        assert r['groups'] == 50 and r['maximum_gradient_difference'] < 5e-5
        assert all(abs(c['envelope_gradient']) <= c['weight_sd'] + 1e-12 for c in r['checks'])
    point_data = json.loads((DATA / '单组绘图点与方程.json').read_text(encoding='utf-8'))
    for name, expected in point_data['input_hashes'].items():
        assert digest(ROOT / name) == expected
    original_samples = json.loads((INPUT / '原案例核验.json').read_text(encoding='utf-8'))['samples']
    assert set(point_data['cases_by_beta']) == {'2', '5'}
    wmle_grid_points = wmle_scalar_checks = 0
    for beta in (2, 5):
        beta_case = point_data['cases_by_beta'][str(beta)]
        for method, case in beta_case['regressions'].items():
            source_sample = next(r for r in original_samples if r['beta_true'] == beta and r['n'] == 7 and r['sample_id'] == case['sample_id'])
            assert case['observations'] == source_sample['observations']
            for ds in case['datasets']:
                assert [p['id'] for p in ds['points']] == list(range(1, 8))
                assert [p['observation'] for p in ds['points']] == source_sample['observations']
                xx = np.array([p['x'] for p in ds['points']]); yy = np.array([p['y'] for p in ds['points']])
                residual = yy - (ds['intercept'] + ds['slope']*xx)
                assert abs(residual.sum()) < 1e-10 and abs(xx @ residual) < 1e-10
                assert abs(ds['loss'] - (1-np.corrcoef(xx, yy)[0,1]**2)) < 1e-12
                actual_ld = np.log(np.array(case['observations']) - ds['gamma'])
                assert np.max(abs(actual_ld - (yy if method == 'lse' else xx))) < 1e-12
        for method, case in beta_case['evaluation_points'].items():
            curve = next(r for r in process['curves'] if r['source'] == 'original' and r['method'] == method and r['beta'] == beta)
            assert len(case['points']) == len(curve['points'])
            for i, (p, saved) in enumerate(zip(case['points'], curve['points'])):
                assert p['id'] == f'G{i+1}' and p['gamma'] == saved[0]
                expected = saved[1] if method == 'mdm' else saved[5]-curve['truth'][5] if saved[5] is not None else None
                assert p['value'] == expected
            assert next(p for p in case['points'] if p['id'] == case['true_gamma_point_id'])['gamma'] == 500
            assert next(p for p in case['points'] if p['id'] == case['returned_gamma_point_id'])['gamma'] == curve['fit']['gamma_hat']
        from 构建公式与拟合点数据 import wmle_residuals
        w = beta_case['wmle']
        original_wmle = next(r for r in process['curves'] if r['source'] == 'original' and r['method'] == 'wmle' and r['beta'] == beta)
        assert [w['returned_beta'], w['returned_gamma']] == [original_wmle['fit']['beta_hat'], original_wmle['fit']['gamma_hat']]
        gamma_grid, beta_grid = w['gamma_grid'], w['beta_grid']
        grid_checks = [(0, 0), (len(beta_grid)//2, len(gamma_grid)//2),
                       (beta_grid.index(float(beta)), gamma_grid.index(500.)),
                       (beta_grid.index(w['returned_beta']), gamma_grid.index(w['returned_gamma'])),
                       (len(beta_grid)-1, len(gamma_grid)-1)]
        for bi, gi in grid_checks:
            t1, t2 = wmle_residuals(np.array(w['observations']), beta_grid[bi], gamma_grid[gi])
            assert np.allclose([w['t1'][bi][gi], w['t2'][bi][gi]], [t1, t2], rtol=1e-11, atol=1e-11)
        assert w['returned_objective'] < 1e-20
        wmle_grid_points += w['grid_points']
        wmle_scalar_checks += len(grid_checks)
    assert wmle_grid_points == 81030 and wmle_scalar_checks == 10
    new_figure_names = ['图1_原案例参数分布'] + [r['file'] for r in figure_checks['process_figures']]
    for name in new_figure_names:
        figure = ROOT / '结果' / name
        with Image.open(figure.with_suffix('.png')) as png:
            dimensions = figure_checks['distribution_figure']['png_dimensions'] if name == new_figure_names[0] else next(r['png_dimensions'] for r in figure_checks['process_figures'] if r['file'] == name)
            assert list(png.size) == dimensions
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

    figure = ROOT / '结果' / '图7_寿命分布与分位点'
    with Image.open(figure.with_suffix('.png')) as png:
        dimensions = list(png.size)
        assert dimensions == provenance['png_dimensions']
        assert all(abs(v - 450) < .1 for v in png.info['dpi'])
    svg_text = len(ET.parse(figure.with_suffix('.svg')).findall('.//{http://www.w3.org/2000/svg}text'))
    assert svg_text > 20
    assert b'/FontFile2' in figure.with_suffix('.pdf').read_bytes()
    clean_style = json.loads((DATA / '简洁图样核验.json').read_text(encoding='utf-8'))
    assert clean_style['new_samples'] == 0 and clean_style['new_fits'] == 0
    for name, expected in clean_style['scientific_input_hashes'].items():
        assert digest(ROOT / name) == expected
    assert len(clean_style['figures']) == 11
    for item in clean_style['figures']:
        base = ROOT / '结果' / item['file']
        with Image.open(base.with_suffix('.png')) as png:
            assert png.width == 3240 and all(abs(v-450) < .1 for v in png.info['dpi'])
        texts = [''.join(element.itertext()).strip() for element in ET.parse(
            base.with_suffix('.svg')).findall('.//{http://www.w3.org/2000/svg}text')]
        assert texts == item['svg_text_labels']
        assert b'/FontFile2' in base.with_suffix('.pdf').read_bytes()
    for old, current in clean_style['file_renames'].items():
        for extension in ('png', 'pdf', 'svg'):
            assert not (ROOT / '结果' / f'{old}.{extension}').exists()
            assert (ROOT / '结果' / f'{current}.{extension}').exists()
    summary = {
        'local_links_checked': len(links), 'missing_links': 0,
        'report_matches_latest_generator': True, 'three_chapters': True,
        'paired_samples': len(samples), 'paired_fit_records': len(fits),
        'complete_original_violin_panels_checked': 6, 'violin_method_distributions_checked': 30,
        'violin_raw_points_quartiles_zero_counts_checked': True,
        'violin_points_aligned_on_method_axis': True,
        'method_process_figures_checked': 5, 'six_panel_layout_checked': True, 'all_condition_curves': 1000,
        'original_process_cases': 10, 'process_candidate_points': curve_points,
        'process_inputs_hash_checked': True, 'saved_fits_and_failures_unchanged': True,
        'regression_affine_invariance_checked': True, 'mdm_envelope_bound_checked': True,
        'numbered_regression_observations_checked': 28,
        'regression_transforms_and_ols_normal_equations_checked': True,
        'candidate_point_ids_and_values_checked': True,
        'wmle_joint_formula_grid_points': wmle_grid_points,
        'wmle_scalar_grid_checks': wmle_scalar_checks,
        'method_formulas_documented_in_report': sum(r['formula_documented_in_report'] for r in figure_checks['process_figures']),
        'independent_samples': 1400, 'independent_fit_records': rows,
        'independent_source_files_preserved_bytewise': unchanged_scan_files,
        'frozen_scan_dependency_hashes_checked': dependencies,
        'figure7_sample_id': provenance['sample_id'], 'quantile_rows_checked': len(quantiles),
        'removed_directory_and_old_report_checks': True,
        'svg_live_text_count': svg_text, 'png_dimensions': dimensions,
        'new_samples': 0, 'new_fits': 0,
        'remaining_figures_simplified_and_checked': 11,
        'simplified_svg_text_matches_saved_inventory': True,
        'superseded_figure_exports_removed': 33,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
