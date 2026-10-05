"""E10: independent n=30/50 development, frozen models and common test.

Run with BLAS thread counts set to one. Each development/test cell is an atomic
checkpoint. The cached MDM evaluator retains the production offset root,
finite difference, beta optimizer and boundary rules; it skips only the
offset-independent 60-point diagnostic trace and shares profile values among
the 26 offsets for one sample. `verify` compares it with production MDM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

for env in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[env] = '1'

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar, root_scalar
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'python'))
sys.path.insert(0, str(HERE.parent / 'E09_六方法共同测试'))
from studies.common.sample import generate_sample
from studies.common.runner import run_method
from wmle_solver import run_wmle_checked

DELTAS = np.round(np.arange(26) * .02, 2)
BETAS = (1.5, 2., 2.5, 3., 3.5, 4., 4.5, 5.)
RATIOS = (.1, .25, .5, .75, 1.)
TEST_BETAS = (1.5, 2., 3., 5.)
TEST_RATIOS = (.1, .5, 1.)
NS = (30, 50)
DEV_SEED = 'study01_e10_dev_20260924_v1'
TEST_SEED = 'study01_e10_test_20260924_v1'
METHODS = ('AMDM', 'MDM-0.1', 'WMLE', 'MLE')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def sample_sha(x):
    return sha(np.asarray(x, dtype='<f8').tobytes())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    os.replace(tmp, path)


class CachedMDM:
    """Production MDM final estimate with shared per-sample profile cache.

    No interpolation or surrogate roots. The production trace grid is omitted
    because it only populates diagnostics and does not enter the final solve.
    """
    def __init__(self, sample):
        self.t = np.sort(np.asarray(sample, dtype=float))
        self.tmin = float(self.t[0])
        n = len(self.t)
        ranks = (np.arange(1, n + 1) - .3) / (n + .4)
        self.q = -np.log(1 - ranks)
        self.profiles = {}
        self.gradients = {}

    def profile(self, gamma):
        gamma = float(gamma)
        if gamma in self.profiles:
            return self.profiles[gamma]
        if gamma >= self.tmin:
            return None, float('inf')
        def sigma(beta):
            return np.std((self.t - gamma) / np.power(self.q, 1 / beta), ddof=1)
        result = minimize_scalar(sigma, bounds=(.1, 15.), method='bounded')
        value = float(result.x), float(result.fun)
        self.profiles[gamma] = value
        return value

    def gradient(self, gamma):
        gamma = float(gamma)
        if gamma in self.gradients:
            return self.gradients[gamma]
        scale = max(abs(self.tmin), 1.)
        nominal_h = scale * 1e-5
        left_room = max(gamma, 0.)
        right_room = max(self.tmin - gamma, 0.)
        if right_room <= 0:
            return float('inf')
        if gamma <= 0 or left_room <= nominal_h:
            h = max(min(nominal_h, right_room * .25), np.finfo(float).eps * scale)
            value = (self.profile(gamma + h)[1] - self.profile(gamma)[1]) / h
        elif right_room <= nominal_h:
            h = max(min(nominal_h, left_room * .25, right_room * .5), np.finfo(float).eps * scale)
            value = (self.profile(gamma)[1] - self.profile(gamma - h)[1]) / h
        else:
            h = max(min(nominal_h, left_room * .25, right_room * .25), np.finfo(float).eps * scale)
            value = (self.profile(gamma + h)[1] - self.profile(gamma - h)[1]) / (2 * h)
        self.gradients[gamma] = float(value)
        return float(value)

    def fit(self, offset):
        offset = float(offset)
        g0 = self.gradient(0.)
        if g0 >= offset:
            gamma = 0.
            strategy = 'truncated_at_zero'
        else:
            min_gap = max(abs(self.tmin) * 1e-12, 1e-12)
            gaps = np.geomspace(max(abs(self.tmin) * 1e-3, min_gap), min_gap, 24)
            anchor = None
            for gap in gaps:
                probe = max(0., self.tmin - float(gap))
                if probe >= self.tmin:
                    probe = self.tmin - min_gap
                grad = self.gradient(probe)
                if not np.isfinite(grad):
                    continue
                anchor = (probe, grad)
                if grad >= offset:
                    break
            if anchor is None:
                probe = max(0., self.tmin - min_gap)
                anchor = (probe, self.gradient(probe))
            if anchor[1] >= offset:
                root = root_scalar(lambda g: self.gradient(g) - offset,
                                   bracket=(0., float(anchor[0])), method='brentq',
                                   xtol=1e-8, rtol=1e-10, maxiter=80)
                gamma = min(max(float(root.root), 0.), self.tmin - 1e-12)
                strategy = 'brent_root'
            else:
                gamma = float(np.nextafter(self.tmin, 0.))
                if gamma <= anchor[0]:
                    gap = max(self.tmin - anchor[0], 0.)
                    fallback = max(gap * .5, np.finfo(float).eps * max(abs(self.tmin), 1.))
                    gamma = min(self.tmin - fallback, float(np.nextafter(self.tmin, 0.)))
                gamma = min(max(gamma, 0.), float(np.nextafter(self.tmin, 0.)))
                strategy = 'right_edge_fit'
        beta = self.profile(gamma)[0]
        eta = float(np.mean((self.t - gamma) / np.power(self.q, 1 / beta)))
        return np.array([beta, eta, gamma], dtype=float), strategy


def grid(kind):
    bs, rs, repeats = (BETAS, RATIOS, 300) if kind == 'dev' else (TEST_BETAS, TEST_RATIOS, 100)
    return [(n, b, r, repeats, i) for n in NS for i, (b, r) in enumerate((b, r) for b in bs for r in rs)]


def dev_cell(task):
    n, b, ratio, repeats, cell = task
    dest = HERE / 'dev_cells' / f'n{n}_cell{cell:02d}.npz'
    if dest.exists():
        with np.load(dest) as z:
            assert z['x'].shape == (300, n) and z['hats'].shape == (300, 26, 3)
        return str(dest), 'cached'
    x = np.empty((repeats, n))
    hats = np.empty((repeats, 26, 3))
    hashes = np.empty(repeats, dtype='U64')
    for repeat in range(repeats):
        obs = generate_sample(float(b), 1000., float(ratio * 1000.), n, repeat, seed=DEV_SEED)
        x[repeat] = obs
        hashes[repeat] = sample_sha(obs)
        solver = CachedMDM(obs)
        for j, delta in enumerate(DELTAS):
            hats[repeat, j], _ = solver.fit(delta)
    err = (hats - np.array([b, 1000., ratio * 1000.])) / np.array([b, 1000., 1000.])
    loss = np.sum(err ** 2, axis=2)
    valid = np.isfinite(hats).all(axis=2) & (hats[:, :, 0] > 0) & (hats[:, :, 1] > 0) & (hats[:, :, 2] >= 0) & (hats[:, :, 2] < x[:, 0, None])
    loss[~valid] = np.nan
    dest.parent.mkdir(exist_ok=True)
    tmp = dest.with_suffix('.tmp.npz')
    np.savez_compressed(tmp, x=x, hats=hats, loss=loss, valid=valid, sample_sha256=hashes,
                        beta=b, eta=1000., gamma=ratio * 1000., ratio=ratio, n=n)
    os.replace(tmp, dest)
    return str(dest), 'new'


def scan():
    tasks = grid('dev')
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(dev_cell, task) for task in tasks]
        for i, job in enumerate(as_completed(jobs), 1):
            path, status = job.result()
            print(f'dev {i}/{len(tasks)} {Path(path).name} {status}', flush=True)


def train():
    files = sorted((HERE / 'dev_cells').glob('*.npz'))
    files = [p for p in files if any(p.name.startswith(f'n{n}_') for n in NS)]
    assert len(files) == 40 * len(NS), len(files)
    valid_losses = []
    for path in files:
        with np.load(path) as z:
            valid_losses.append(z['loss'][np.isfinite(z['loss'])])
    penalty = float(np.percentile(np.concatenate(valid_losses), 99))
    for n in NS:
        model_path = HERE / 'models' / f'n{n}_final.json'
        if model_path.exists():
            print(f'model n={n} cached', flush=True)
            continue
        parts = [p for p in files if p.name.startswith(f'n{n}_')]
        xs, ys = [], []
        for path in parts:
            with np.load(path) as z:
                xs.append(z['x'] / z['x'].mean(axis=1, keepdims=True))
                ys.append(np.where(np.isfinite(z['loss']), z['loss'], penalty))
        x, y = np.concatenate(xs), np.concatenate(ys)
        assert x.shape == (12000, n) and y.shape == (12000, 26)
        sx, sy = StandardScaler(), StandardScaler()
        xz, yz = sx.fit_transform(x), sy.fit_transform(y)
        model = MLPRegressor(hidden_layer_sizes=(256, 128, 64), activation='relu', solver='adam',
                             alpha=.0001, learning_rate_init=.001, max_iter=300,
                             early_stopping=True, validation_fraction=.15, n_iter_no_change=20,
                             random_state=1, batch_size=256)
        started = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', ConvergenceWarning)
            model.fit(xz, yz)
        result = dict(n=n, seed=1, train_n_samples=len(x), n_iter=model.n_iter_, runtime_s=time.time()-started,
                      converged_before_max_iter=model.n_iter_ < 300, loss=float(model.loss_),
                      best_validation_score=float(model.best_validation_score_),
                      dev_failure_penalty=penalty, delta_grid=DELTAS.tolist(),
                      normalization='sorted(sample)/mean(sample), then per-position StandardScaler',
                      input_scaler_mean=sx.mean_.tolist(), input_scaler_std=sx.scale_.tolist(),
                      target_scaler_mean=sy.mean_.tolist(), target_scaler_std=sy.scale_.tolist(),
                      mlp_weights={'coefs_':[a.tolist() for a in model.coefs_],
                                   'intercepts_':[a.tolist() for a in model.intercepts_]},
                      source_cell_hashes={p.name:file_sha(p) for p in parts})
        direct = np.maximum(sy.inverse_transform(model.predict(xz[:8])), 0.)
        restored = np.stack([predict_curve(x[i], result) for i in range(8)])
        result['serialized_forward_max_abs'] = float(np.max(np.abs(direct - restored)))
        assert result['serialized_forward_max_abs'] < 1e-9
        write_json(model_path, result)
        print(f'model n={n} iterations={model.n_iter_} val={model.best_validation_score_:.5f}', flush=True)


def predict_curve(obs, model):
    z = np.sort(obs) / np.mean(obs)
    a = (z - np.asarray(model['input_scaler_mean'])) / np.asarray(model['input_scaler_std'])
    weights = model['mlp_weights']
    for i, (coef, intercept) in enumerate(zip(weights['coefs_'], weights['intercepts_'])):
        a = a @ np.asarray(coef) + np.asarray(intercept)
        if i < len(weights['coefs_']) - 1:
            a = np.maximum(a, 0.)
    return np.maximum(a * np.asarray(model['target_scaler_std']) + np.asarray(model['target_scaler_mean']), 0.)


def test_cell(task):
    n, b, ratio, repeats, cell = task
    dest = HERE / 'test_cells' / f'n{n}_cell{cell:02d}.csv'
    if dest.exists():
        old = pd.read_csv(dest)
        assert len(old) == 400 and old.sample_sha256.nunique() == 100
        return str(dest), 'cached'
    model_path = HERE / 'models' / f'n{n}_final.json'
    model = json.loads(model_path.read_text(encoding='utf8'))
    rows = []
    for repeat in range(repeats):
        obs = generate_sample(float(b), 1000., float(ratio * 1000.), n, repeat, seed=TEST_SEED)
        h = sample_sha(obs)
        chosen = float(DELTAS[int(np.argmin(predict_curve(obs, model)))])
        for method in METHODS:
            if method in ('AMDM', 'MDM-0.1'):
                delta = chosen if method == 'AMDM' else .1
                fit = run_method('mdm', obs, offset=delta, gamma_steps=60)
                scale = 1.
            elif method == 'WMLE':
                delta = np.nan
                fit = run_wmle_checked(obs / 1000.)
                scale = 1000.
            else:
                delta = np.nan
                fit = run_method('mle', obs / 1000.)
                scale = 1000.
            bh, eh, gh = (fit.get(k) for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
            valid = bool(fit.get('converged')) and all(v is not None and np.isfinite(v) for v in (bh, eh, gh))
            if valid:
                eh, gh = eh * scale, gh * scale
                valid = bool(bh > 0 and eh > 0 and 0 <= gh < obs[0])
            extra = fit.get('extra') or {}
            info = extra.get('solution_info') or {}
            rows.append(dict(n=n, cell_id=f'n{n}_cell{cell:02d}', beta=b, eta=1000., gamma=ratio*1000.,
                             gamma_over_eta=ratio, repeat_id=repeat, sample_sha256=h, method=method,
                             delta=delta, beta_hat=bh if valid else np.nan,
                             eta_hat=eh if valid else np.nan, gamma_hat=gh if valid else np.nan,
                             valid=valid, failure_reason='' if valid else str(extra.get('raw_status') or extra.get('error') or 'not_converged'),
                             solver_status=info.get('status', '')))
    dest.parent.mkdir(exist_ok=True)
    tmp = dest.with_suffix('.tmp')
    pd.DataFrame(rows).to_csv(tmp, index=False)
    os.replace(tmp, dest)
    return str(dest), 'new'


def test():
    assert all((HERE / 'models' / f'n{n}_final.json').exists() for n in NS)
    tasks = grid('test')
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(test_cell, task) for task in tasks]
        for i, job in enumerate(as_completed(jobs), 1):
            path, status = job.result()
            print(f'test {i}/{len(tasks)} {Path(path).name} {status}', flush=True)


def summarize():
    files = sorted((HERE / 'test_cells').glob('*.csv'))
    assert len(files) == 24, len(files)
    df = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
    assert len(df) == 9600
    df.valid = df.valid.astype(str).str.lower().eq('true')
    assert not df.duplicated(['cell_id', 'repeat_id', 'method']).any()
    assert df.groupby(['cell_id', 'repeat_id']).sample_sha256.nunique().eq(1).all()
    for p, denom in (('beta', df.beta), ('eta', df.eta), ('gamma', df.eta)):
        df[f'err_{p}'] = (df[f'{p}_hat'] - df[p]) / denom
    df['squared_loss'] = df[[f'err_{p}' for p in ('beta', 'eta', 'gamma')]].pow(2).sum(axis=1, min_count=3)
    df.to_csv(HERE / 'per_sample.csv.gz', index=False, compression='gzip')
    def metrics(group):
        valid = group[group.valid]
        out = dict(samples=len(group), valid_samples=len(valid), failures=len(group)-len(valid),
                   failure_rate=1-len(valid)/len(group), J1_valid=float(np.sqrt(valid.squared_loss.mean())))
        for p in ('beta', 'eta', 'gamma'):
            e = valid[f'err_{p}']
            out.update({f'bias_{p}':float(e.mean()), f'sd_{p}':float(e.std(ddof=1)),
                        f'rmse_{p}':float(np.sqrt(e.pow(2).mean()))})
        return pd.Series(out)
    by_n = df.groupby(['n','method']).apply(metrics, include_groups=False).reset_index()
    by_cell = df.groupby(['n','cell_id','beta','gamma_over_eta','method']).apply(metrics, include_groups=False).reset_index()
    by_n.to_csv(HERE/'by_n.csv', index=False)
    by_cell.to_csv(HERE/'by_cell.csv', index=False)
    wide = df.pivot(index=['n','cell_id','repeat_id'], columns='method', values='squared_loss')
    valid = df.pivot(index=['n','cell_id','repeat_id'], columns='method', values='valid')
    rng = np.random.default_rng(20260924)
    intervals = []
    curves = []
    gain_draws = {}
    for n in NS:
        v = valid.loc[n]
        w = wide.loc[n]
        assert len(v) == 1200
        pair = v['AMDM'] & v['MDM-0.1']
        blocks = [w.loc[cell].loc[pair.loc[cell], ['AMDM','MDM-0.1']].to_numpy()
                  for cell in sorted(w.index.get_level_values(0).unique())]
        assert len(blocks) == 12 and all(len(a) > 0 for a in blocks)
        all_pair = np.concatenate(blocks)
        j = np.sqrt(all_pair.mean(axis=0))
        draws = np.zeros((2000,2))
        for block in blocks:
            ix = rng.integers(0,len(block),size=(2000,len(block)))
            draws += block[ix].sum(axis=1)
        draws = np.sqrt(draws/len(all_pair))
        gain = 1-draws[:,0]/draws[:,1]
        gain_draws[n] = gain
        intervals.append(dict(n=n, pair_valid_samples=len(all_pair), AMDM_J1=j[0], MDM_J1=j[1],
                              relative_gain=1-j[0]/j[1], ci95_low=np.quantile(gain,.025),
                              ci95_high=np.quantile(gain,.975), bootstrap_draws=2000))
        common = v[list(METHODS)].all(axis=1)
        common_idx = common[common].index
        selected = df[(df.n == n)].set_index(['cell_id','repeat_id','method']).loc[
            [(c,r,m) for c,r in common_idx for m in METHODS]].reset_index()
        for p in ('beta','eta','gamma'):
            base = np.sqrt(np.mean(selected[selected.method == 'MLE'][f'err_{p}']**2))
            for method in METHODS:
                this = selected[selected.method == method]
                rmse = np.sqrt(np.mean(this[f'err_{p}']**2))
                curves.append(dict(n=n, parameter=p, method=method, common_valid_samples=len(common_idx),
                                   rmse=rmse, MLE_rmse=base, relative_reduction=1-rmse/base,
                                   retained_per_cell=json.dumps({c:int(common.loc[c].sum())
                                       for c in sorted(common.index.get_level_values(0).unique())})))
    pd.DataFrame(intervals).to_csv(HERE/'paired_interval.csv', index=False)
    difference = gain_draws[50] - gain_draws[30]
    write_json(HERE/'gain_difference.json', dict(comparison='n50 minus n30 AMDM relative J1 gain',
               point_estimate=float(intervals[1]['relative_gain']-intervals[0]['relative_gain']),
               ci95=[float(v) for v in np.quantile(difference,[.025,.975])], draws=2000,
               resampling='Independent within-cell paired repeat resampling for each n'))
    pd.DataFrame(curves).to_csv(HERE/'parameter_vs_mle.csv', index=False)
    manifest = dict(status='completed', development_samples=24000, development_candidate_fits=624000,
                    test_samples=2400, test_method_rows=9600, development_seed=DEV_SEED, test_seed=TEST_SEED,
                    training_model_seed=1, test_condition_count=24, methods=METHODS,
                    source_hashes={str(p.relative_to(REPO)):file_sha(p) for p in [REPO/'python/methods/mdm.py',
                        REPO/'python/methods/mle.py', REPO/'python/methods/wmle.py',
                        REPO/'python/studies/common/sample.py', REPO/'python/studies/common/runner.py',
                        HERE.parent/'E09_六方法共同测试/wmle_solver.py', HERE/'run_e10.py']},
                    models={f'n{n}':file_sha(HERE/'models'/f'n{n}_final.json') for n in NS},
                    outputs={p.name:file_sha(p) for p in [HERE/'per_sample.csv.gz', HERE/'by_n.csv',
                         HERE/'by_cell.csv', HERE/'paired_interval.csv', HERE/'gain_difference.json',
                         HERE/'parameter_vs_mle.csv']})
    write_json(HERE/'manifest.json',manifest)
    print(pd.DataFrame(intervals).to_string(index=False), flush=True)
    print(by_n[['n','method','failures']].to_string(index=False), flush=True)


def verify():
    records = []
    for n, b, ratio, repeat in [(30,1.5,.1,0),(30,2.,.5,23),(30,5.,1.,99),
                                (50,1.5,1.,0),(50,3.,.5,23),(50,5.,.1,99)]:
        obs = generate_sample(b,1000.,ratio*1000.,n,repeat,seed=DEV_SEED)
        cached = CachedMDM(obs)
        for delta in (.0,.1,.24,.5):
            got, strategy = cached.fit(delta)
            prod = run_method('mdm',obs,offset=delta,gamma_steps=60)
            ref = np.array([prod[k] for k in ('beta_hat','eta_hat','gamma_hat')])
            err = np.abs(got-ref)
            records.append(dict(n=n,beta=b,ratio=ratio,repeat_id=repeat,delta=delta,
                                max_abs=float(err.max()),max_relative=float(np.max(err/np.maximum(abs(ref),1.))),
                                cached_strategy=strategy,production_converged=bool(prod['converged'])))
    report = dict(comparisons=len(records), max_relative=max(r['max_relative'] for r in records),
                  max_absolute=max(r['max_abs'] for r in records), records=records)
    write_json(HERE/'cached_mdm_verification.json',report)
    assert report['max_relative'] < 1e-8, report['max_relative']
    print(f"cached MDM verified: {len(records)} comparisons max relative {report['max_relative']:.3g}",flush=True)


def audit():
    dev_files = sorted((HERE/'dev_cells').glob('*.npz'))
    test_files = sorted((HERE/'test_cells').glob('*.csv'))
    assert len(dev_files) == 80 and len(test_files) == 24
    dev_hashes = set()
    dev_checked = 0
    candidate_rows = 0
    for path in dev_files:
        with np.load(path) as z:
            x, hats, loss, hashes = (z[k] for k in ('x','hats','loss','sample_sha256'))
            b, e, g, n = float(z['beta']), float(z['eta']), float(z['gamma']), int(z['n'])
            assert x.shape == (300,n) and hats.shape == (300,26,3) and loss.shape == (300,26)
            rebuilt = np.sum(((hats-[b,e,g])/[b,e,e])**2,axis=2)
            valid = z['valid']
            assert np.array_equal(np.isfinite(loss), valid)
            assert np.allclose(loss[valid], rebuilt[valid], rtol=1e-12, atol=1e-13)
            for repeat in range(300):
                h = sample_sha(x[repeat])
                assert h == hashes[repeat]
                dev_hashes.add(h)
            for repeat in (0,149,299):
                expected = generate_sample(b,e,g,n,repeat,seed=DEV_SEED)
                assert np.array_equal(expected,x[repeat])
                dev_checked += 1
            candidate_rows += loss.size
    assert len(dev_hashes) == 24000 and candidate_rows == 624000
    df = pd.read_csv(HERE/'per_sample.csv.gz')
    assert len(df) == 9600 and df.groupby(['cell_id','repeat_id']).sample_sha256.nunique().eq(1).all()
    test_hashes = set()
    model_by_n = {n:json.loads((HERE/'models'/f'n{n}_final.json').read_text(encoding='utf8')) for n in NS}
    solver_checks = 0
    for (n, cell, repeat), block in df.groupby(['n','cell_id','repeat_id']):
        row = block.iloc[0]
        obs = generate_sample(float(row.beta),float(row.eta),float(row.gamma),int(n),int(repeat),seed=TEST_SEED)
        h = sample_sha(obs)
        assert h == row.sample_sha256 and h not in dev_hashes and len(block) == 4
        test_hashes.add(h)
        chosen = float(DELTAS[np.argmin(predict_curve(obs,model_by_n[n]))])
        assert np.isclose(block.loc[block.method=='AMDM','delta'].iloc[0],chosen,atol=1e-14)
        if cell.endswith(('00','05','11')) and repeat == 0:
            for saved in block.itertuples():
                if saved.method in ('AMDM','MDM-0.1'):
                    direct = run_method('mdm',obs,offset=float(saved.delta),gamma_steps=60)
                    scale = 1.
                elif saved.method == 'WMLE':
                    direct = run_wmle_checked(obs/1000.)
                    scale = 1000.
                else:
                    direct = run_method('mle',obs/1000.)
                    scale = 1000.
                vals = [direct.get(k) for k in ('beta_hat','eta_hat','gamma_hat')]
                is_valid = bool(direct.get('converged')) and all(v is not None and np.isfinite(v) for v in vals)
                if is_valid:
                    vals[1] *= scale
                    vals[2] *= scale
                    is_valid = vals[0] > 0 and vals[1] > 0 and 0 <= vals[2] < obs[0]
                assert bool(saved.valid) == bool(is_valid)
                if is_valid:
                    assert np.allclose(vals,[saved.beta_hat,saved.eta_hat,saved.gamma_hat],rtol=1e-9,atol=1e-8)
                solver_checks += 1
    assert len(test_hashes) == 2400
    for n in NS:
        model = json.loads((HERE/'models'/f'n{n}_final.json').read_text(encoding='utf8'))
        assert model['seed'] == 1 and model['train_n_samples'] == 12000
        assert model['serialized_forward_max_abs'] < 1e-9
    summary = pd.read_csv(HERE/'by_n.csv')
    for row in summary.itertuples():
        part = df[(df.n == row.n) & (df.method == row.method)]
        valid = part[part.valid.astype(str).str.lower().eq('true')]
        assert len(part) == 1200 and len(valid) == row.valid_samples
        joint = np.sqrt(np.mean(valid.squared_loss))
        assert np.isclose(joint, row.J1_valid, rtol=1e-12)
        for p in ('beta','eta','gamma'):
            err = valid[f'err_{p}']
            assert np.isclose(np.sqrt(np.mean(err**2)), getattr(row,f'rmse_{p}'), rtol=1e-12)
    report = dict(status='passed', development_samples=len(dev_hashes), development_reconstructions=dev_checked,
                  candidate_losses=candidate_rows, test_sample_hashes_checked=len(test_hashes),
                  overlap_samples=len(dev_hashes & test_hashes), models_checked=2,
                  model_selected_deltas_checked=len(test_hashes), test_solver_rows_recomputed=solver_checks,
                  by_n_rows_recomputed=len(summary),
                  cached_mdm_comparisons=json.loads((HERE/'cached_mdm_verification.json').read_text())['comparisons'])
    write_json(HERE/'verification.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('verify','scan','train','test','summarize','audit','all'))
    args = parser.parse_args()
    if args.stage in ('verify','all'): verify()
    if args.stage in ('scan','all'): scan()
    if args.stage in ('train','all'): train()
    if args.stage in ('test','all'): test()
    if args.stage in ('summarize','all'): summarize()
    if args.stage in ('audit','all'): audit()


if __name__ == '__main__':
    main()
