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
        assert [p['beta'] for p in fig['single_panels']] == [2,5]
        assert [p['expanded_from_panel'] for p in fig['single_panels']] == ['a','b']
        assert all(p['source'] == 'paired' and p['n'] == 7 for p in fig['single_panels'])
        assert fig['single_panels'][0]['sample_id'] == fig['single_panels'][1]['sample_id']
        assert fig['single_panels'][0]['criterion_y_limits'] == fig['single_panels'][1]['criterion_y_limits']
        assert fig['six_panel_axes_identical'] and not fig['single_panel_zoom']
        panels = [*fig['panels'],*fig['single_panels']]
        assert len(panels) == 6
        assert all(p['axis_settings'] == panels[0]['axis_settings'] for p in panels)
        assert all(p['x_limits'] == panels[0]['x_limits'] and
                   p['criterion_y_limits'] == panels[0]['criterion_y_limits'] for p in panels)
        assert panels[0]['axis_settings']['x_scale'] == 'linear'
        assert panels[0]['axis_settings']['y_scale'] == ('log' if fig['method'] in ('lse','lre') else 'linear')
        assert not fig['formula_printed_on_figure'] and fig['formula_documented_in_report']
    curve_points = sum(len(r['points']) for r in process['curves'])
    assert curve_points == 147550
    for name, expected in process['provenance']['input_hashes'].items():
        assert digest(ROOT / name) == expected
    fit_index = {(r['beta'], r['n'], r['sample_id'], r['method']): r for r in fits}
    original_fits = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    pairs = json.loads((DATA / '配对单例与推导核验.json').read_text(encoding='utf-8'))
    assert pairs['new_samples'] == pairs['new_three_parameter_estimates'] == 0
    assert pairs['single_curves_copied_from_multi_sample_data']
    for name, expected in pairs['input_hashes'].items():
        assert digest(ROOT / name) == expected
    sample_index = {(r['beta'],r['n'],r['sample_id']):r for r in samples}
    latent_index = {(r['n'],r['sample_id']):r['exponential_order_stats'] for r in
                    json.loads((DATA / '共同随机分位点.json').read_text(encoding='utf-8'))}
    from 推导判据与统一单例 import select_pair, verify_formula
    paired_evaluation_points = derivation_checks = 0
    for selection in pairs['methods']:
        method = selection['method']
        rows, center, eligible = select_pair(process, method)
        assert selection['beta5_success_median_gamma'] == center
        assert selection['eligible_ids'] == eligible
        assert selection['sample_id'] == rows[0]['sample_id'] == rows[1]['sample_id']
        panels = next(fig['single_panels'] for fig in figure_checks['process_figures']
                      if fig['method'] == method)
        for case, row, panel in zip(selection['cases'], rows, panels):
            assert case['source'] == row['source'] == panel['source'] == 'paired'
            assert case['sample_id'] == row['sample_id'] == panel['sample_id']
            assert case['expanded_from_panel'] == panel['expanded_from_panel']
            assert case['fit'] == row['fit'] == fit_index[case['beta'],7,case['sample_id'],method]
            assert case['observations'] == sample_index[case['beta'],7,case['sample_id']]['observations']
            assert case['latent_E'] == latent_index[7,case['sample_id']]
            assert np.allclose(case['observations'], 500+1000*np.array(case['latent_E'])**(1/case['beta']), rtol=0, atol=1e-10)
            assert len(case['evaluation_points']) == len(row['points'])
            for i, (point, saved) in enumerate(zip(case['evaluation_points'],row['points'])):
                expected = (saved[5]-row['truth'][5] if saved[5] is not None else None) if method == 'mle' else saved[1]
                assert point == dict(id=f'G{i+1}',gamma=saved[0],value=expected)
            detail = panel['detail']
            assert detail['type'] == 'numbered_formula_evaluations'
            assert detail['total_points'] == len(case['evaluation_points'])
            assert detail['plotted_defined_points'] == sum(p['value'] is not None for p in case['evaluation_points'])
            assert detail['labelled_point_ids'] == [case['true_gamma_point_id'],case['returned_gamma_point_id']]
            for key, gamma in (('true_gamma_point_id',500.),('returned_gamma_point_id',case['fit']['gamma_hat'])):
                assert next(p['gamma'] for p in case['evaluation_points'] if p['id'] == case[key]) == gamma
            checks = verify_formula(np.array(case['observations']), row)
            assert checks == case['derivation_checks']
            derivation_checks += len(checks)
            paired_evaluation_points += len(case['evaluation_points'])
        assert selection['cases'][0]['latent_E'] == selection['cases'][1]['latent_E']
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
        assert min(values) == r['minimum'] and r['maximum'] == max(values)
        limits={'beta_hat':[0.,10.], 'eta_hat':[0.,2000.], 'gamma_hat':[0.,1500.]}[r['parameter']]
        ticks={'beta_hat':[0.,2.,4.,6.,8.,10.], 'eta_hat':[0.,500.,1000.,1500.,2000.],
               'gamma_hat':[0.,500.,1000.,1500.]}[r['parameter']]
        assert r['x_limits']==limits and r['x_ticks']==ticks and r['axis_scale']=='linear'
        shown=[f for f in successful if limits[0]<=f[r['parameter']]<=limits[1]]
        hidden=[f for f in successful if not limits[0]<=f[r['parameter']]<=limits[1]]
        shown_values=[f[r['parameter']] for f in shown]
        assert r['display_values']==shown_values
        assert r['display_sample_ids']==[f['sample_id'] for f in shown]
        assert r['omitted_values']==[f[r['parameter']] for f in hidden]
        assert r['omitted_sample_ids']==[f['sample_id'] for f in hidden]
        assert r['omitted_count']==len(hidden) and len(shown)+len(hidden)==len(values)
        assert np.allclose(r['quartiles'], np.quantile(values, [.25, .5, .75]), rtol=0, atol=1e-12)
        zeros = values.count(0) if r['parameter'] == 'gamma_hat' else 0
        density_values=[v for v in shown_values if v>0 or r['parameter']!='gamma_hat']
        assert r['zero_count'] == zeros and r['kde_count'] == len(density_values)
        assert len(r['displayed_y']) == len(shown_values)
        method_position = ('mdm', 'lse', 'lre', 'wmle', 'mle').index(r['method'])
        assert set(r['displayed_y']) == {float(method_position)}
        assert min(r['kde_density']) >= 0 and len(r['kde_density']) == 256
        assert r['kde_coordinate']=='linear'
        expected_grid_limits = [min(density_values),max(density_values)]
        assert np.allclose([r['kde_coordinate_grid'][0], r['kde_coordinate_grid'][-1]], expected_grid_limits, atol=1e-12)
        assert r['density_limits']==expected_grid_limits
        from scipy.stats import gaussian_kde
        assert np.allclose(r['kde_density'],gaussian_kde(density_values,bw_method='scott')(r['kde_coordinate_grid']),rtol=1e-12,atol=1e-12)
    assert violin_data['summary_source']=='all successful estimates'
    assert violin_data['density_source']=='displayed successful estimates' and not violin_data['tail_extension']
    assert violin_data['figure_contract']['formats']==['PNG 450dpi']
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
    auxiliary = figure_checks['auxiliary_figure']
    assert [(p['method'],p['beta'],p['source']) for p in auxiliary['panels']] == [
        (m,b,'original') for m in ('lse','lre','wmle') for b in (2,5)]
    for panel in auxiliary['panels']:
        detail = panel['detail']
        beta_case = point_data['cases_by_beta'][str(panel['beta'])]
        if panel['method'] in ('lse','lre'):
            case = beta_case['regressions'][panel['method']]
            assert detail['sample_id'] == case['sample_id']
            assert detail['observations'] == 7 and detail['transformed_points'] == 14
            assert detail['all_observation_ids_labelled']
        else:
            assert detail['sample_id'] == beta_case['wmle']['sample_id']
            assert detail['formula_grid_points'] == beta_case['wmle']['grid_points']
    new_figure_names = ['图1_原案例参数分布'] + [r['file'] for r in figure_checks['process_figures']] + [auxiliary['file']]
    for name in new_figure_names:
        figure = ROOT / '结果' / name
        with Image.open(figure.with_suffix('.png')) as png:
            dimensions = figure_checks['distribution_figure']['png_dimensions'] if name == new_figure_names[0] else next(r['png_dimensions'] for r in [*figure_checks['process_figures'],auxiliary] if r['file'] == name)
            assert list(png.size) == dimensions
            assert all(abs(v-450) < .1 for v in png.info['dpi'])
        if name != new_figure_names[0]:
            assert len(ET.parse(figure.with_suffix('.svg')).findall('.//{http://www.w3.org/2000/svg}text')) > 25
            assert b'/FontFile2' in figure.with_suffix('.pdf').read_bytes()
        else:
            assert not figure.with_suffix('.svg').exists() and not figure.with_suffix('.pdf').exists()

    provenance = json.loads((DATA / '图8样本来源与核验.json').read_text(encoding='utf-8'))
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
    local = json.loads((DATA / '局部分位补偿核验.json').read_text(encoding='utf-8'))
    assert local['new_samples'] == local['new_fits'] == 0
    assert [c['name'] for c in local['cases']] == ['generating_distribution','constructed_local_match']
    for case in local['cases']:
        beta, eta, gamma = case['parameters_beta_eta_gamma']
        assert case['central_quantile'] == gamma+eta == 1500
        assert case['central_slope'] == eta/beta == 200
        assert case['central_curvature'] == eta/beta**2
        for row in case['quantiles']:
            expected = gamma+eta*(-math.log1p(-row['p']))**(1/beta)
            assert abs(row['quantile']-expected) < 1e-10
    assert local['cases'][0]['central_curvature'] != local['cases'][1]['central_curvature']

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

    figure = ROOT / '结果' / '图8_寿命分布与分位点'
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
    assert len(clean_style['figures']) == 12
    from 绘制样本相容分布 import source_data
    compatibility = json.loads((ROOT / '程序' / '样本相容绘图数据.json').read_text(encoding='utf-8'))
    for key, expected in source_data().items():
        assert compatibility[key] == expected, key
    for name, expected in compatibility['source_hashes'].items():
        assert digest(ROOT / name) == expected
    assert compatibility['sample_id'] == provenance['sample_id'] == 31
    assert compatibility['n'] == 7
    assert compatibility['observations'] == provenance['observations']
    assert compatibility['plotting_positions'] == provenance['plotting_positions']
    assert compatibility['actual_fit_parameters_beta_eta_gamma'] == provenance['fit_parameters_beta_eta_gamma']
    assert [curve['parameters_beta_eta_gamma'] for curve in compatibility['curves']] == [
        [5., 1000., 500.], [2., 500., 1000.]]
    assert compatibility['new_samples'] == compatibility['new_fits'] == 0
    assert compatibility['formats'] == ['png']
    assert compatibility['axis_settings']['x_scale'] == compatibility['axis_settings']['y_scale'] == 'linear'
    assert compatibility['plotted_curve_count'] == 2
    assert compatibility['plotted_sample_point_count'] == 7
    assert compatibility['extra_annotation_count'] == 0
    for item in compatibility['existing_exports_renumbered_without_redrawing']:
        assert digest(ROOT / item['to']) == item['sha256']
        assert not (ROOT / item['from']).exists()
    with Image.open(ROOT / compatibility['figure']) as png:
        assert list(png.size) == compatibility['png_dimensions']
        assert all(abs(value - 450) < .1 for value in png.info['dpi'])
    numbers = [int(value) for value in re.findall(r'^!\[图(\d+)', report.read_text(encoding='utf-8'), re.M)]
    assert numbers == list(range(1, 9)), numbers
    export_names = {item['file'] for item in clean_style['figures']} | {'图1_原案例参数分布', '图2_样本与分布相容'}
    assert len(export_names) == 14
    for extension in ('png','pdf','svg'):
        expected_exports=export_names if extension=='png' else export_names-{'图1_原案例参数分布', '图2_样本与分布相容'}
        assert {p.stem for p in (ROOT / '结果').glob(f'*.{extension}')} == expected_exports
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
        'violin_axes_all_linear_with_shared_limits_and_ticks': True,
        'violin_display_omissions_checked': sum(r['omitted_count'] for r in violin_data['panels']),
        'violin_full_estimates_and_summaries_preserved': True,
        'method_process_figures_checked': 5, 'six_panel_layout_checked': True, 'all_condition_curves': 1000,
        'all_six_panel_axis_limits_scales_ticks_and_labels_identical': True,
        'single_panel_zoom_removed': True,
        'paired_single_panels_copied_from_a_b': 10,
        'paired_single_evaluation_points_checked': paired_evaluation_points,
        'single_panel_criterion_matches_multi_sample_panel': True,
        'single_beta_pairs_share_latent_sample': True,
        'single_pair_selection_rule_checked': True,
        'principle_derivation_checks_at_true_and_returned_gamma': derivation_checks,
        'original_case_auxiliary_panels_checked': 6,
        'current_figures': 14, 'current_export_files': 38,
        'sample_compatibility_curves_checked': 2,
        'sample_compatibility_observations_checked': 7,
        'sample_compatibility_reuses_figure8_sample': True,
        'sample_compatibility_scipy_cdf_check': True,
        'sample_compatibility_axes_linear': True,
        'main_figure_numbers_in_reading_order': numbers,
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
        'figure8_sample_id': provenance['sample_id'], 'quantile_rows_checked': len(quantiles),
        'removed_directory_and_old_report_checks': True,
        'svg_live_text_count': svg_text, 'png_dimensions': dimensions,
        'new_samples': 0, 'new_fits': 0,
        'remaining_figures_simplified_and_checked': 12,
        'simplified_svg_text_matches_saved_inventory': True,
        'superseded_figure_exports_removed': 33,
        'local_compensation_example_is_constructed': True,
        'local_compensation_centers_checked': 2,
        'local_compensation_slopes_checked': 2,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
