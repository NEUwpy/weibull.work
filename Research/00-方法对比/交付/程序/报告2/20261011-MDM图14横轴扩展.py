"""Widen only figure 14 panels a/d to the batch gradient plot's gamma range.

Keep groups 4/5, their estimates, existing curve nodes and all other panels.
Evaluate the frozen MDM criterion for additional left-side nodes; no estimator
is run. Source cache and QA stay here; the delivered artifact is one PNG.
"""
from pathlib import Path
from io import BytesIO
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path, setup_runtime, write_atomic
setup_runtime()
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '-曲线.json')
QA = HERE / (STEM + '-核验.json')
DATA = RESULT / '报告2/数据'
TARGET = RESULT / '报告2/配对情形_MDM_edge.png'
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def inputs():
    pairs_path = DATA / '20261010-配对图参照线精简核验.json'
    rows_path = DATA / '20261010-参照线精简图数据.csv'
    eta_path = HERE / '20261010-MDM条件尺度图.csv'
    archive = load(pairs_path)
    rows = [r for r in csv.DictReader(rows_path.open(encoding='utf-8-sig')) if r['example'] == 'MDM_edge']
    etas = list(csv.DictReader(eta_path.open(encoding='utf-8-sig')))
    pair = archive['pairs']['MDM_edge']
    curves = {role: [{**r, 'gamma': float(r['gamma']), 'eta': float(r['eta'])} for r in etas
                     if r['example'] == 'MDM_edge' and r['role'] == pair[role]['role']]
              for role in ('normal', 'abnormal')}
    return archive, pair, rows, curves, [pairs_path, rows_path, eta_path]


def frozen_gradient(path, x):
    """Extract the exact conditional sigma/finite-difference functions from MDM.run."""
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    run = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'run')
    names = ('calculate_eta_std', 'find_best_beta_for_gamma', 'profile_sigma', 'profile_gradient')
    functions = [next(n for n in run.body if isinstance(n, ast.FunctionDef) and n.name == name) for name in names]
    ranks = (np.arange(1, len(x) + 1) - .3) / (len(x) + .4)
    namespace = dict(np=np, minimize_scalar=minimize_scalar, t=x, t_min=x[0],
                     neg_ln_1_minus_F=-np.log(1 - ranks), beta_sigma_cache={}, profile_gradient_cache={})
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['profile_gradient']


def build():
    archive, pair, rows, _, paths = inputs()
    catalog_path = PROGRAM / '跨参数对比/13组合取数.json'
    source = next(s for s in load(catalog_path)['sources'] if s['combination'] == pair['normal']['combination'])
    matrix_file = matrix_path(source)
    assert digest(matrix_file) == source['matrix_sha256']
    matrix = load(matrix_file)
    method = snapshot_path(source) / 'methods/mdm.py'
    config = PROGRAM / source['program'] / '完整矩阵/config.json'
    axis = dict(xlim=load(config)['figure_contract']['x_range'], xticks=[0, 1000, 2000, 3000, 4000])
    assert axis['xlim'] == [0, 4000]
    paths += [catalog_path, matrix_file, method, config]
    extra, checks = [], []
    for role, group in (('normal', 4), ('abnormal', 5)):
        obj = pair[role]
        assert obj['group'] == group and obj['n'] == 7
        x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == group))
        assert x.tolist() == obj['values']
        saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == group
                     and r['method_id'] == 'mdm' and r['delta'] == .2)
        assert all(saved[k] == obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
        gradient = frozen_gradient(method, x)
        original = [r for r in rows if r['role'] == obj['role'] and r['panel'] == 'gradient']
        # Check the new evaluator against every existing node before extending it.
        error = max(abs(gradient(float(r['gamma'])) - float(r['gradient'])) for r in original)
        assert error < 1e-9, (role, error)
        left = min(float(r['gamma']) for r in original)
        gammas = np.linspace(axis['xlim'][0], left, 320, endpoint=False)
        for g in gammas:
            extra.append(dict(example='MDM_edge', role=obj['role'], group=group, panel='gradient',
                              gamma=float(g), gamma_ratio=float(g / obj['gamma_true']), gradient=float(gradient(g))))
        new_values = [r['gradient'] for r in extra if r['role'] == obj['role']]
        assert np.all(np.isfinite(new_values)) and max(new_values) < .2
        roots = obj.get('gradient_roots', [obj['gamma_hat']])
        root_errors = [abs(gradient(g) - .2) for g in roots]
        assert max(root_errors) < 1e-7
        checks.append(dict(role=role, group=group, existing_nodes=len(original), extra_nodes=len(gammas),
                           existing_node_max_error=error, roots=roots, root_errors=root_errors,
                           added_range=[float(gammas[0]), float(gammas[-1])]))
    write_json(CACHE, dict(gradient_axis=axis, additional_rows=extra, checks=checks,
                           source_sha256={str(p): digest(p) for p in paths},
                           backend='Python/matplotlib', export='PNG only', new_samples=0, new_estimates=0,
                           figure_contract=dict(conclusion='Show the complete approach to the existing gradient crossings and right-edge fallback.',
                                                archetype='quantitative grid', size_inches=[9.6, 5.7],
                                                changed_panels=['a', 'd'], criterion=.2,
                                                keep='Existing samples, estimates, roots, probes, y limits, and panels b/c/e/f.')))
    print('Cached 640 added gradient nodes from the frozen MDM criterion; all original nodes and roots matched.')


def right_pixels(data):
    return plt.imread(BytesIO(data), format='png')[:, int(3840 * .35):]


def render():
    cache = load(CACHE)
    for path, sha in cache['source_sha256'].items():
        assert digest(path) == sha, path
    archive, pair, rows, conditional, _ = inputs()
    original_gradient_rows = [r for r in rows if r['panel'] == 'gradient']
    rows.extend(cache['additional_rows'])
    rows.sort(key=lambda r: (r['role'], r['panel'], float(r.get('gamma') or 0)))
    assert [r for r in rows if r['panel'] == 'gradient' and r not in cache['additional_rows']] == sorted(
        original_gradient_rows, key=lambda r: (r['role'], r['panel'], float(r['gamma'])))
    protected = {str(p): digest(p) for p in RESULT.rglob('*') if p.is_file() and p != TARGET}
    protected[str(REPORT)] = digest(REPORT)
    previous = TARGET.read_bytes()
    renderer = module(HERE / '20261010-MDM公式逐项对应原文.py', 'mdm14_wide_renderer')
    temporary = HERE / (STEM + '-render.png')
    assert temporary.resolve().parent == HERE.resolve()
    try:
        meta = renderer.render('MDM_edge', pair, rows, archive['figures']['MDM_edge'], conditional,
                               gradient_axis=cache['gradient_axis'], target_path=temporary)
        current = temporary.read_bytes()
        assert np.array_equal(right_pixels(previous), right_pixels(current)), 'Panels b/c/e/f changed'
        assert all(digest(p) == sha for p, sha in protected.items())
        write_atomic(TARGET, current)
    finally:
        if temporary.exists():
            temporary.unlink()
    assert meta['axes'][0] == meta['axes'][3]
    assert meta['axes'][0]['xlim'] == [0, 4000]
    assert meta['axes'][0]['xticks'] == cache['gradient_axis']['xticks']
    meta.update(path=str(TARGET), sha256=digest(TARGET), gradient_and_shape_nodes_unchanged=False)
    write_json(QA, dict(figure=meta, cache_sha256=digest(CACHE), source_sha256=cache['source_sha256'],
                        protected_sha256=protected, original_pair=pair, script_sha256=digest(__file__),
                        renderer_sha256=digest(Path(renderer.__file__)),
                        panels_bcef_pixels_sha256=hashlib.sha256(right_pixels(current).tobytes()).hexdigest(),
                        existing_gradient_nodes_retained=True, samples_and_estimates_unchanged=True))
    print('Rendered figure 14: panels a/d gamma=0..4000, matching linear ticks; panels b/c/e/f pixel-identical.')


def verify():
    cache, qa = load(CACHE), load(QA)
    assert digest(CACHE) == qa['cache_sha256'] and digest(TARGET) == qa['figure']['sha256']
    for collection in ('source_sha256', 'protected_sha256'):
        for path, sha in qa[collection].items():
            assert digest(path) == sha, path
    assert hashlib.sha256(right_pixels(TARGET.read_bytes()).tobytes()).hexdigest() == qa['panels_bcef_pixels_sha256']
    assert inputs()[1] == qa['original_pair']
    assert len(cache['additional_rows']) == 640
    assert qa['figure']['axes'][0] == qa['figure']['axes'][3]
    print('PASS: original samples, estimates, roots, probes, existing nodes and other panels preserved; a/d range=0..4000.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['build', 'render', 'verify'])
    globals()[parser.parse_args().action]()
