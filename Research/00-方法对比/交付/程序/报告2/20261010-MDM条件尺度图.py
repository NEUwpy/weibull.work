"""Replace report2 MDM panels c/f with conditional eta versus gamma.

Reuse archived samples, gamma nodes and estimates. Evaluate the frozen MDM
shape-selection and scale-mean expressions without running its estimator.
"""
from pathlib import Path
import ast
import csv
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import PROGRAM, RESULT, matrix_path, snapshot_path, setup_runtime

setup_runtime()
import numpy as np
from scipy.optimize import minimize_scalar


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mother = load(HERE / '20261010-MDM公式逐项对应原文.py', 'mdm_eta_renderer')
LABELS = mother.LABELS
CATALOG = PROGRAM / '跨参数对比/13组合取数.json'
DATA = RESULT / '报告2/数据'
SOURCE = Path(__file__).with_suffix('.csv')
QA = Path(__file__).with_suffix('.json')


def frozen_profile(snapshot, values):
    """Evaluate the original nested functions and final eta assignments."""
    base = load(snapshot / 'base.py', 'mdm_eta_base')
    sample = base.WeibullBase(values, rank_method='bernard')
    ranks = sample._median_ranks()
    tree = ast.parse((snapshot / 'methods/mdm.py').read_text(encoding='utf-8-sig'))
    run = next(node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name == 'run')
    names = ('calculate_eta_std', 'find_best_beta_for_gamma')
    functions = [next(node for node in run.body
                      if isinstance(node, ast.FunctionDef) and node.name == name)
                 for name in names]
    eta_assignments = [next(node for node in run.body
                            if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == name
                                    for target in node.targets))
                       for name in ('denom', 'etas', 'found_eta')]
    namespace = dict(np=np, minimize_scalar=minimize_scalar, t=sample.data,
                     neg_ln_1_minus_F=-np.log(1 - ranks), beta_sigma_cache={})
    exec(compile(ast.Module(body=functions, type_ignores=[]),
                 str(snapshot / 'methods/mdm.py'), 'exec'), namespace)
    mean_code = compile(ast.Module(body=eta_assignments, type_ignores=[]),
                        str(snapshot / 'methods/mdm.py'), 'exec')

    def profile(gamma):
        beta, sigma = namespace['find_best_beta_for_gamma'](float(gamma))
        assert beta is not None and np.isfinite(sigma)
        namespace.update(found_beta=beta, found_gamma=float(gamma))
        exec(mean_code, namespace)
        return dict(beta=float(beta), sigma=float(sigma),
                    eta=float(namespace['found_eta']))

    return profile


def main():
    pair_path = DATA / '20261010-配对图参照线精简核验.json'
    nodes_path = DATA / '20261010-参照线精简图数据.csv'
    archive = json.loads(pair_path.read_text(encoding='utf-8'))
    rows = list(csv.DictReader(nodes_path.open(encoding='utf-8-sig')))
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))['sources']
    sources = {source['combination']: source for source in catalog}
    targets = {RESULT / '报告2' / f'配对情形_{label}.png' for label in LABELS}
    protected = [path for path in RESULT.rglob('*') if path.is_file() and path not in targets]
    protected += [CATALOG, pair_path, nodes_path]
    for source in catalog:
        assert mother.digest(matrix_path(source)) == source['matrix_sha256']
        protected += [matrix_path(source), snapshot_path(source) / 'methods/mdm.py',
                      snapshot_path(source) / 'base.py']
    before = {str(path): mother.digest(path) for path in set(protected)}
    output_rows, anchors, figures = [], [], {}
    for label in LABELS:
        pair = archive['pairs'][label]
        curves = {}
        for role in ('normal', 'abnormal'):
            obj = pair[role]
            source = sources[obj['combination']]
            matrix = json.loads(matrix_path(source).read_text(encoding='utf-8'))
            values = next(sample['values'] for sample in matrix['samples']
                          if sample['n'] == obj['n'] and sample['id'] == obj['group'])
            assert sorted(values) == obj['values']
            assert matrix['config']['truth'] == [obj['beta_true'], obj['eta_true'], obj['gamma_true']]
            profile = frozen_profile(snapshot_path(source), obj['values'])
            gammas = {float(row['gamma']) for row in rows
                      if row['example'] == label and row['role'] == obj['role']
                      and row['panel'] == 'gradient'}
            gammas.update((obj['gamma_true'], obj['gamma_hat']))
            curve = []
            for gamma in sorted(gammas):
                assert 0 <= gamma < obj['values'][0]
                point = dict(example=label, role=obj['role'], group=obj['group'],
                             gamma=gamma, **profile(gamma),
                             at_true_gamma=gamma == obj['gamma_true'],
                             at_original_gamma=gamma == obj['gamma_hat'])
                curve.append(point)
            for stage, gamma, reference in (
                    ('true_gamma', obj['gamma_true'], obj['at_true']),
                    ('original_gamma', obj['gamma_hat'],
                     dict(beta=obj['beta_hat'], eta=obj['eta_hat'], sigma=obj['at_original']['sigma']))):
                actual = next(point for point in curve if point['gamma'] == gamma)
                errors = {key: abs(actual[key] - reference[key]) for key in ('beta', 'eta', 'sigma')}
                assert all(error < 1e-8 * (1 + abs(reference[key]))
                           for key, error in errors.items()), (label, role, stage, errors)
                anchors.append(dict(example=label, role=role, stage=stage,
                                    gamma=gamma, beta=actual['beta'], eta=actual['eta'],
                                    sigma=actual['sigma'], absolute_errors=errors))
            curves[role] = curve
            output_rows.extend(curve)
        figures[label] = mother.render(label, pair, rows, archive['figures'][label], curves)
        for index in (0, 1, 3, 4):
            factor = pair['normal']['gamma_true'] if index % 3 == 0 else 1
            eta = 1 if index % 3 == 0 else pair['normal']['eta_true']
            for key in ('xlim', 'xticks', 'ylim', 'yticks'):
                multiplier = factor if key.startswith('x') else eta
                assert np.allclose(figures[label]['axes'][index][key],
                                   np.asarray(archive['figures'][label]['axes'][index][key]) * multiplier)
    assert all(mother.digest(path) == digest for path, digest in before.items())
    with SOURCE.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(output_rows)
    QA.write_text(json.dumps(dict(
        source_data=str(SOURCE), source_sha256=mother.digest(SOURCE),
        protected_sha256=before, protected_files_unchanged=True,
        original_samples_and_estimates_unchanged=True,
        calculation='Frozen MDM conditional shape minimum and pseudo-scale mean; Bernard ranks, beta bounds 0.1 to 15.',
        original_gamma_nodes_reused=True, selected_gamma_included=True,
        anchors=anchors, figures=figures), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'MDM条件尺度：2张PNG，{len(output_rows)}个节点；8个真位置/原估计位置锚点核对通过。')


if __name__ == '__main__':
    main()
