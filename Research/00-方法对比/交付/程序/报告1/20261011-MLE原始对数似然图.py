"""Display the saved MLE profiles without subtracting a likelihood baseline.

Reuse all observations, estimates and profile nodes. Only the two MLE PNGs,
their existing drawing metadata and the associated report text are revised.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re

import numpy as np
from scipy.stats import weibull_min

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r1_mle_raw', HERE / '20261011-MLE曲线族与参数传递.py')
plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot)
base = plot.base
QA = HERE / (Path(__file__).stem + '核验.json')


def protected():
    excluded = {plot.FIGURE, plot.TRANSFER, base.FIGURE_QA}
    return {p.relative_to(base.ROOT).as_posix(): base.sha(p)
            for p in base.RESULT.rglob('*') if p.is_file() and p not in excluded}


def snapshot(*, centered=False):
    if QA.exists():
        return
    base.write(QA, dict(cache_sha256=base.sha(plot.DATA),
                        source_hashes=plot.sources(), report2_sha256=base.sha(plot.REPORT2),
                        protected_results=protected(),
                        figure_contract=dict(backend='Python', export='PNG only',
                                             archetype='quantitative grid',
                                             ordinate='profile log likelihood minus value at true gamma' if centered else 'raw profile log likelihood',
                                             additive_shift=centered, fixed_linear_axes=True),
                        new_samples=0, new_estimates=0))


def render(*, centered=False):
    snapshot(centered=centered)
    return plot.render(expected_source_hashes=base.read(QA)['source_hashes'], centered=centered)


def revise(*, centered=False):
    snapshot(centered=centered)
    plot.revise(centered=centered)


def verify(*, centered=False):
    from PIL import Image
    qa, data, figures = base.read(QA), base.read(plot.DATA), base.read(plot.QA)
    assert qa['cache_sha256'] == base.sha(plot.DATA)
    assert qa['source_hashes'] == plot.sources()
    helper_key = str(plot.HELPER.relative_to(base.ROOT))
    changed_sources = {key for key, value in data['source_hashes'].items()
                       if qa['source_hashes'][key] != value}
    assert changed_sources <= {helper_key}
    assert qa['report2_sha256'] == base.sha(plot.REPORT2)
    assert qa['protected_results'] == protected()
    checked, error = 0, 0.
    for row in data['curves']:
        p, x = np.asarray(row['points']), np.asarray(row['observations'])
        direct = weibull_min.logpdf(x[:, None] - p[None, :, 0], p[None, :, 2],
                                   scale=p[None, :, 3]).sum(axis=0)
        error = max(error, float(np.max(np.abs(direct - p[:, 5]))))
        assert np.allclose(direct, p[:, 5], rtol=1e-12, atol=1e-9)
        baseline = row['truth'][5] if centered else 0.
        displayed = np.array([plot.ordinate(node, 5, row, centered=centered) for node in row['points']])
        assert np.allclose(displayed + baseline, p[:, 5], rtol=1e-12, atol=1e-9)
        assert np.argmax(displayed) == np.argmax(p[:, 5])
        assert np.allclose(np.diff(displayed), np.diff(p[:, 5]), rtol=1e-12, atol=1e-9)
        if row['fit']['converged']:
            fit = row['fit']
            actual = float(weibull_min.logpdf(x - fit['gamma_hat'], fit['beta_hat'],
                                             scale=fit['eta_hat']).sum())
            assert np.isclose(actual - baseline, plot.return_ordinate(row, 5, centered=centered), rtol=1e-12, atol=1e-9)
        checked += len(p)
    for example in data['examples']:
        original = next(r for r in data['curves']
                        if (r['beta'], r['n'], r['sample_id']) == (example['beta'], 7, example['sample_id']))
        assert example['points'] == original['points'] and example['fit'] == original['fit']
    family = figures['figures']['criterion']['axis_settings']
    assert all(s == family[0] for s in family)
    transfer = figures['figures']['transfer']['axis_settings']
    assert all(transfer[i] == transfer[i + 1] for i in (0, 2, 4))
    assert all(s['x_scale'] == s['y_scale'] == 'linear' for s in family + transfer)
    for path in (plot.FIGURE, plot.TRANSFER):
        assert figures['figure_hashes'][path.name] == base.sha(path)
        with Image.open(path) as image:
            assert image.size == (3240, 3240)
    text = base.REPORT.read_text(encoding='utf-8')
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', text)] == list(range(1, 45))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', text)] == list(range(1, 16))
    assert r'\Delta\ell' not in text and '似然增量' not in text
    assert ('图12、13均减去同一样本在真γ=500处的值' in text) == centered
    assert plot.common_principles(plot.REPORT2.read_text(encoding='utf-8')) in text
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in target and not target.startswith('#'):
            assert (base.REPORT.parent / target.split('#')[0]).exists(), target
    qa.update(verification=dict(status='passed', curves=300, nodes_checked=checked,
                                maximum_direct_density_difference=error,
                                likelihood_values_and_original_markers_verified=True,
                                additive_shift=centered, peak_locations_and_differences_unchanged=True,
                                source_cache_unchanged=True, other_results_and_report2_unchanged=True,
                                representative_identical_to_family=True, fixed_linear_axes=True,
                                changed_source_files_since_original_cache=sorted(changed_sources),
                                equations=44, main_figures=15, new_samples=0, new_estimates=0),
              script_sha256=base.sha(__file__), renderer_sha256=base.sha(plot.__file__),
              report_sha256=base.sha(base.REPORT), figure_hashes=figures['figure_hashes'])
    base.write(QA, qa)
    print(qa['verification'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['render', 'revise', 'verify', 'all'], default='verify', nargs='?')
    action = parser.parse_args().action
    for name in ['render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
