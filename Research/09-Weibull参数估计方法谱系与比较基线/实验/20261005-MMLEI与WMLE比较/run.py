"""Research-only CW MMLE-I vs existing WMLE, using the shared MC pipeline.

Use D:/weibull/python/.venv/Scripts/python.exe run.py [--workers 2].
Cells are checkpoints; --cell ID --repeats N --output DIR supports verification.
This registers research classes only inside this process, never changes production.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / 'python/methods/wmle.py').exists())
E09 = REPO / 'Study/Study 01 New/数据/E09_六方法共同测试'
sys.path.insert(0, str(REPO / 'python'))
sys.path.insert(0, str(E09))
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.experiment import run_experiment
from studies.common.runner import run_method
from wmle_solver import profile_recover

CONFIG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
SOURCE_PATHS = [HERE / 'run.py', HERE / 'config.json', REPO / 'python/methods/wmle.py',
                REPO / 'python/methods/j3_weights.tsv', E09 / 'wmle_solver.py',
                REPO / 'python/studies/common/sample.py', REPO / 'python/studies/common/runner.py',
                REPO / 'python/studies/common/experiment.py', REPO / 'python/studies/common/metrics.py']


def source_hashes():
    return {str(p.relative_to(REPO)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SOURCE_PATHS}


@lru_cache(maxsize=8)
def fit_cw_i(values: tuple, paper_domain: bool = False, grid_size: int = 97):
    """Solve CW (1982) (2.4),(2.5),(3.4); modern stable bracketing.

    Inner equation beta*(weighted mean log z - mean log z)=1 is strictly
    increasing at positive beta. Log-gap profiling avoids a coarse location
    candidate being accepted as an equation root. No true parameter is used.
    """
    x = np.sort(np.asarray(values, dtype=float))
    n, xmin = len(x), float(x[0])
    if n < 3 or np.ptp(x) <= 0:
        return None, {'status': 'invalid_sample'}
    spec = CONFIG['cw_i_paper_domain' if paper_domain else 'cw_i_nonnegative']
    lower = float(x.mean() - 10 * x.std(ddof=1)) if paper_domain else 0.0
    dmax = xmin - lower
    # Inputs were divided by a fixed 1000, so retain the stated raw-unit gap.
    dmin = spec['raw_min_gap'] / CONFIG['unit_divisor']
    if dmax <= dmin:
        return None, {'status': 'empty_location_domain'}
    c = np.log1p(1 / n)
    delta = x - xmin

    def profile(logd):
        d = np.exp(logd)
        logs = np.log1p(delta / d)
        mean_log = logs.mean()
        def first(b):
            powers = np.exp(b * (logs - logs.max()))
            return b * (np.dot(powers, logs) / powers.sum() - mean_log) - 1
        high = 2.0
        while first(high) < 0 and high < 1e7:
            high *= 2
        if first(high) < 0:
            raise ArithmeticError('shape profile outside numerical range')
        b = brentq(first, 1e-7, high, xtol=1e-12, rtol=1e-12)
        second = logsumexp(b * logs) - np.log(n) + np.log(c)
        return b, float(second), float(first(b)), d

    grid = np.linspace(np.log(dmin), np.log(dmax), grid_size)
    roots = []
    previous = None
    for logd in grid:
        point = profile(logd)
        if abs(point[1]) < 1e-11:
            roots.append((logd, point))
        if previous is not None and previous[1] * point[1] < 0:
            logroot = brentq(lambda t: profile(t)[1], previous[0], logd,
                            xtol=1e-12, rtol=1e-12)
            roots.append((logroot, profile(logroot)))
        previous = (logd, point[1])
    if not roots:
        endpoints = [profile(grid[0]), profile(grid[-1])]
        return None, {'status': 'no_root_in_declared_location_domain',
                      'location_lower': lower * CONFIG['unit_divisor'],
                      'endpoint_constraint_residuals': [p[1] for p in endpoints],
                      'grid_size': grid_size}
    # First admissible root from xmin downwards, like the paper's search order.
    rejected = []
    for _, (b, r_c, r_shape, d) in roots:
        if not spec['shape_bounds'][0] < b < spec['shape_bounds'][1]:
            rejected.append(float(b))
            continue
        g = xmin - d
        logs = np.log(x - g)
        eta = float(np.exp((logsumexp(b * logs) - np.log(n)) / b))
        residual = r_shape ** 2 + r_c ** 2
        if residual > 1e-12 or not np.isfinite(eta) or eta <= 0:
            return None, {'status': 'equation_residual', 'objective': residual}
        return (float(b), eta, float(g)), {'status': 'ok', 'objective': residual,
                    'roots_found': len(roots), 'grid_size': grid_size,
                    'strategy': 'cw_i_profile_brent', 'paper_domain': paper_domain,
                    'raw_min_gap': float(d * CONFIG['unit_divisor'])}
    return None, {'status': 'shape_outside_declared_domain',
                  'candidate_shapes': rejected, 'roots_found': len(roots)}


class CWNonnegative(WeibullBase):
    paper_domain = False
    def run(self):
        unit = CONFIG['unit_divisor']
        fitted, self.last_solution_info = fit_cw_i(tuple(self.data / unit), self.paper_domain)
        if fitted is None:
            return [None, None, None, 0.0, self.last_solution_info['status']]
        b, e, g = fitted
        return [b, e * unit, g * unit, 0.0, True]


class CWPaperDomain(CWNonnegative):
    paper_domain = True


class WMLEChecked(WeibullBase):
    def run(self):
        unit = CONFIG['unit_divisor']
        result = run_method('wmle', self.data / unit)
        initial = (result.get('extra') or {}).get('solution_info', {}).copy()
        recovered = False
        if not result['converged']:
            fallback = profile_recover(self.data / unit)
            if fallback is not None:
                result = fallback
                recovered = True
        self.last_solution_info = (result.get('extra') or {}).get('solution_info', {}).copy()
        self.last_solution_info.update(production_status=initial.get('status'), recovered=recovered)
        if not result['converged']:
            return [None, None, None, 0.0, self.last_solution_info.get('status', 'wmle_failure')]
        return [result['beta_hat'], result['eta_hat'] * unit,
                result['gamma_hat'] * unit, result.get('r_squared') or 0.0, True]


def register():
    IMPLEMENTED.update(cw_i_nonnegative=CWNonnegative, cw_i_paper_domain=CWPaperDomain,
                       wmle_checked=WMLEChecked)


def cells():
    return [(i, b, CONFIG['eta'], ratio * CONFIG['eta'], n)
            for i, (b, ratio, n) in enumerate(
                (b, r, n) for b in CONFIG['beta'] for r in CONFIG['gamma_over_eta']
                for n in CONFIG['n_values'])]


def run_cell(args):
    cell, out, repeats, hashes, commit = args
    cid, b, e, g, n = cell
    dest = Path(out) / f'cell_{cid:02d}'
    manifest = dest / 'manifest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text(encoding='utf-8'))
        if old.get('source_sha256') != hashes or old['n_repeats'] != repeats:
            raise RuntimeError(f'checkpoint source/repeat mismatch: {dest}')
        return cid, 'existing'
    register()
    run_experiment(CONFIG['methods'], [(b, e, g)], [n], repeats, str(dest),
                   seed_namespace=CONFIG['seed_namespace'], code_version=commit,
                   run_label=f"{CONFIG['experiment_id']}:cell_{cid:02d}")
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data.update(source_sha256=hashes, contract=CONFIG)
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    return cid, 'complete'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--cell', type=int)
    parser.add_argument('--repeats', type=int, default=CONFIG['repeats'])
    parser.add_argument('--output', type=Path, default=HERE / 'cells')
    args = parser.parse_args()
    selected = [c for c in cells() if args.cell is None or c[0] == args.cell]
    hashes = source_hashes()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    tasks = [(c, str(args.output), args.repeats, hashes, commit) for c in selected]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_cell, t) for t in tasks]
        for count, future in enumerate(as_completed(futures), 1):
            print({'finished': count, 'total': len(tasks), 'cell': future.result()}, flush=True)
    if source_hashes() != hashes:
        raise RuntimeError('source changed while experiment was running')


if __name__ == '__main__':
    main()
