"""Choose closer archived WMLE controls, then redraw report 2 figures 16/17.

Within each original combination and n=7, minimize the largest absolute relative
parameter error; break ties by mean squared relative error and group ID. This is
a reference-case selection, not a new fit or an estimate of typical accuracy.
All source rows, equation grids and verification records stay with this script.
"""
from pathlib import Path
from io import BytesIO, StringIO
import argparse
import csv
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 共用 import PROGRAM, RESULT, matrix_path, snapshot_path, setup_runtime, write_atomic
setup_runtime()
import numpy as np

import importlib.util

HERE = Path(__file__).resolve().parent
STEM = Path(__file__).stem
CACHE = HERE / (STEM + '-缓存.json')
CURVES = HERE / (STEM + '-条件曲线.csv')
GRIDS = HERE / (STEM + '-网格.npz')
QA = HERE / (STEM + '.json')
DISTANCES = HERE / (STEM + '.csv')
CASES = {'WMLE_low': ('W(5,100,500)', 3), 'WMLE_high': ('W(1.5,100,500)', 1)}
PARAMS = ('beta', 'eta', 'gamma')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


renderer = module(HERE / '20261011-WMLE真位置样本距离.py', 'wmle_control_renderer')
renderer.RECORD, renderer.ROWS = QA, DISTANCES
helper = module(HERE / '逐方法机制复核.py', 'wmle_control_profiles')
load, digest = renderer.load, renderer.digest


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def score(row):
    errors = [abs(float(row[p + '_hat']) / float(row[p + '_true']) - 1) for p in PARAMS]
    return max(errors), float(np.mean(np.square(errors))), int(row['group'])


def build():
    flow_path = RESULT / '报告2/数据/全量流程定位.csv'
    flow = list(csv.DictReader(flow_path.open(encoding='utf-8-sig')))
    catalog_path = PROGRAM / '跨参数对比/13组合取数.json'
    catalog = {s['combination']: s for s in load(catalog_path)['sources']}
    sources = {str(p): digest(p) for p in (flow_path, catalog_path, Path(helper.__file__),
                                        Path(helper.conditional_profiles.__file__))}
    controls, rankings, curve_rows, grids = {}, {}, [], {}
    for label, (combo, expected_group) in CASES.items():
        candidates = [r for r in flow if r['combination'] == combo and int(r['n']) == 7
                      and r['method'] == 'WMLE' and r['abnormal'] == 'False'
                      and all(np.isfinite(float(r[p + '_hat'])) for p in PARAMS)]
        candidates.sort(key=score)
        row = candidates[0]
        assert int(row['group']) == expected_group
        source = catalog[combo]
        path = matrix_path(source)
        assert digest(path) == source['matrix_sha256']
        matrix = load(path)
        saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == expected_group
                     and r['method_id'] == 'wmle')
        assert saved['displayed_success'] and saved['converged']
        assert all(float(row[p + '_hat']) == saved[p + '_hat'] for p in PARAMS)
        x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == expected_group))
        truth = matrix['config']['truth']
        assert all(float(row[p + '_true']) == truth[i] for i, p in enumerate(PARAMS))
        snapshot = snapshot_path(source)
        sys.path.insert(0, str(snapshot))
        weights = module(snapshot / 'methods/wmle.py', 'wmle_control_weights_' + label)
        sources.update({str(p): digest(p) for p in (path, snapshot / 'methods/wmle.py',
                                                  snapshot / 'methods/j3_weights.tsv')})
        gamma = float(row['gamma_hat'])
        at_true, at_original = (helper.wmle_profile(x, g, weights) for g in (truth[2], gamma))
        assert at_true is not None and at_original is not None
        assert np.allclose([at_original['beta'], at_original['eta']],
                           [saved['beta_hat'], saved['eta_hat']], rtol=2e-5, atol=0)
        assert at_original['t1'] ** 2 + at_original['t2'] ** 2 <= 1e-8
        for profile, g in ((at_true, truth[2]), (at_original, gamma)):
            logs = np.log(x - g)
            profile.update(gamma=float(g), log_range=float(np.ptp(logs)), log_sd=float(np.std(logs, ddof=1)))
        controls[label] = dict(role='正常', combination=combo, n=7, group=expected_group, method='WMLE',
                              values=x.tolist(), version=row['version'], abnormal=False,
                              root_solver=row['archived_root_solver'], at_true=at_true, at_original=at_original,
                              **{p + suffix: float(row[p + suffix]) for p in PARAMS for suffix in ('_true', '_hat')})
        rankings[label] = [dict(group=int(r['group']), max_relative_error=score(r)[0],
                               mean_squared_relative_error=score(r)[1],
                               estimates=[float(r[p + '_hat']) for p in PARAMS]) for r in candidates]
        lower, gap = .9 * truth[2], max(.02, 1e-8 * x[0])
        upper = min(x[0] - gap, 1.17 * truth[2])
        gs = np.unique(np.r_[np.linspace(lower, upper, 340),
                             x[0] - np.geomspace(gap, x[0] - lower, 150), truth[2], gamma])
        bs = np.linspace(.4, 9, 190)
        t1, t2 = helper.conditional_profiles.wmle_residuals(x, bs[None, :], gs[:, None], weights)
        for key, value in (('gamma', gs), ('beta', bs), ('T1', t1), ('T2', t2)):
            grids[label + '_正常_' + key] = value
        for g in gs:
            profile = helper.wmle_profile(x, float(g), weights)
            curve_rows.append(dict(example=label, role='正常', group=expected_group, panel='shape_zero_branch',
                                   gamma=float(g), gamma_ratio=float(g / truth[2]),
                                   beta=profile['beta'] if profile else float('nan'),
                                   t2=profile['t2'] if profile else float('nan')))
    write_json(CACHE, dict(selection_rule='min(max absolute relative error), then mean squared relative error, then group ID',
                           sample_sizes=[7], controls=controls, candidate_rankings=rankings, source_sha256=sources,
                           new_samples=0, new_estimates=0))
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(curve_rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(curve_rows)
    write_atomic(CURVES, buffer.getvalue().encode('utf-8-sig'))
    buffer = BytesIO()
    np.savez_compressed(buffer, **grids)
    write_atomic(GRIDS, buffer.getvalue())
    for label, obj in controls.items():
        print(label, obj['group'], [obj[p + '_hat'] for p in PARAMS],
              'at_true:', obj['at_true'], 'maximum_relative_error:', rankings[label][0]['max_relative_error'])


def render():
    cache = load(CACHE)
    for path, sha in cache['source_sha256'].items():
        assert digest(path) == sha, path
    rows = list(csv.DictReader(CURVES.open(encoding='utf-8-sig')))
    with np.load(GRIDS) as saved:
        grids = {key: saved[key] for key in saved.files}
    renderer.render(pair_overrides=cache['controls'], curve_overrides=rows, grid_overrides=grids, preserve='abnormal')
    record = load(QA)
    record.update(selection_rule=cache['selection_rule'], control_groups={k: o['group'] for k, o in cache['controls'].items()},
                  archived_sources_sha256=cache['source_sha256'],
                  control_data_sha256={str(p): digest(p) for p in (CACHE, CURVES, GRIDS)},
                  task_script_sha256=digest(__file__))
    write_json(QA, record)


def revise():
    cache = load(CACHE)
    original = renderer.REPORT.read_text(encoding='utf-8')
    before, remaining = original.split('#### 2.1.5', 1)
    section, after = remaining.split('#### 2.1.6', 1)
    if '| 正常·第3组 | 508.70 |' in section and '| 正常·第1组 | 503.91 |' in section:
        print('WMLE control tables and explanations already updated.')
        return
    assert digest(renderer.REPORT) == '9147d892aa6c31d115082f2c919e583791cb4dfb376286bb6a9e18c566c41e31'
    low, high = (cache['controls'][k] for k in ('WMLE_low', 'WMLE_high'))
    for obj in (low, high):
        old = next(line for line in section.splitlines() if line.startswith('| 正常·第10组 |')
                   and (('2.78' in line) if obj is low else ('1.18' in line)))
        new = (f"| 正常·第{obj['group']}组 | {obj['gamma_hat']:.2f} | {obj['beta_hat']:.2f} | {obj['eta_hat']:.2f} | "
               + '，'.join(f'{x:.2f}' for x in obj['values']) + ' |')
        section = section.replace(old, new, 1)
    old = ('以真位置500为起点，第10组的最小观测高于起点43.87，第11组高于起点75.95；后者的前四个观测集中在575.95—586.04，下端空缺更大。两组在真位置处按式（22）计算的T₂都为负，样本乘积低于校准项。联合交点分别位于γ=516.81、573.51，与各自最小观测相差27.06、2.44。第11组需要更靠近最小值的位置才能使两式平衡。')
    # These signs are checked against the same frozen WMLE weights used in the plot.
    assert low['at_true']['t2'] < 0
    new = ('以真位置500为起点，第3组的最小观测高于起点48.67，第11组高于起点75.95；后者的前四个观测集中在575.95—586.04，下端空缺更大。两组在真位置处按式（22）计算的T₂都为负，样本乘积低于校准项。第3组在γ=508.70处达到联合平衡，形状为5.35，接近真值；第11组的交点则位于γ=573.51，与最小观测仅相差2.44，形状降至1.10。')
    assert section.count(old) == 1
    section = section.replace(old, new, 1)
    old = '第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第10组则分布在506.42—734.47，跨度更大。'
    new = '第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第1组则分布在522.01—678.65，跨度更大。'
    assert section.count(old) == 1
    section = section.replace(old, new, 1)
    old = '第10组的距离较分散，联合交点对应β=1.18。'
    new = '第1组的距离较分散，两式在γ=503.91、β=1.60处共同平衡，均接近真值。'
    assert section.count(old) == 1
    section = section.replace(old, new, 1)
    text = before + '#### 2.1.5' + section + '#### 2.1.6' + after
    assert renderer.math_blocks(text) == renderer.math_blocks(original)
    write_atomic(renderer.REPORT, text.encode('utf-8'))
    record = load(QA)
    record['text_revision'] = dict(before_sha256=digest_bytes(original.encode('utf-8')),
                                   after_sha256=digest(renderer.REPORT), section='2.1.5 WMLE',
                                   equations_unchanged=True, abnormal_samples_unchanged=True)
    write_json(QA, record)
    print('Updated only WMLE control rows and the corresponding explanation.')


def digest_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def verify():
    renderer.verify()
    record, cache = load(QA), load(CACHE)
    for collection in ('archived_sources_sha256', 'control_data_sha256'):
        for path, sha in record[collection].items():
            assert digest(path) == sha, path
    archived_pairs = load(RESULT / '报告2/数据/20261010-配对图参照线精简核验.json')['pairs']
    for label, obj in cache['controls'].items():
        assert record['samples'][label]['normal'] == obj
        assert record['samples'][label]['abnormal'] == archived_pairs[label]['abnormal']
        ranked = cache['candidate_rankings'][label]
        assert ranked == sorted(ranked, key=lambda r: (r['max_relative_error'], r['mean_squared_relative_error'], r['group']))
        assert ranked[0]['group'] == obj['group']
    print('PASS: closest joint controls from original n=7 archive; abnormal rows/pixels, all 30 formulas and archived estimates preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['build', 'render', 'revise', 'verify'])
    globals()[parser.parse_args().action]()
