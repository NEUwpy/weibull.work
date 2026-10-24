"""Feature-only B10 risk prediction. Raw study data and frozen estimators stay unchanged."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
import numpy as np
from scipy.stats import rankdata, spearmanr
import torch
from torch import nn

PROGRAM = Path(__file__).resolve().parent
STUDY = PROGRAM.parent
CONFIG = json.loads((PROGRAM / '实验配置.json').read_text(encoding='utf-8'))
CORE = PROGRAM / CONFIG['source_directory']
sys.path.insert(0, str(CORE))
from studies.common.metrics import quantile_true, quantile_est, summarize_standard_errors

METHODS = [spec['variant'] for _, spec in CONFIG['methods']]
OUT = Path(os.environ.get('B10_SELECTOR_OUTPUT', str(STUDY / '结果/B10方法选择-v1'))).resolve()
VERSION = 'b10-feature-selector-v1-20261024'
SPLIT_NAMESPACE = b'b10-feature-selector-20261024-v1|'
GROUPS = {
    'n': ['log_n'],
    'level': ['log_mean', 'log_std', 'log_min', 'log_max', 'log_median', 'log_range'],
    'quantiles': [f'z_q{q:02d}' for q in [5, 10, 20, 25, 50, 75, 80, 90, 95]],
    'moments': ['z_mean', 'z_std', 'cv', 'skewness', 'excess_kurtosis', 'bowley'],
    'spacing': ['gap_first', 'gap_second', 'gap_last', 'gap_max', 'gap_top2',
                'gap_entropy', 'gap_lower2', 'gap_upper2'],
}
FEATURES = sum(GROUPS.values(), [])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_write(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def csv_write(path, rows):
    if not rows:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def features(sample):
    """Only this sample is accepted: no truth, estimator output, IDs, or cohort."""
    x = np.sort(np.asarray(sample, dtype=np.float64))
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all() or (x <= 0).any():
        raise ValueError('At least three finite positive observations required')
    span = np.ptp(x)
    if span <= 0:
        raise ValueError('Nonzero sample range required')
    z = (x - x[0]) / span
    gaps = np.diff(z)
    zmean = z.mean()
    zstd = np.std(z, ddof=0)
    q = np.quantile(z, np.array([5, 10, 20, 25, 50, 75, 80, 90, 95]) / 100)
    q25, q50, q75 = q[[3, 4, 5]]
    bowley = (q75 + q25 - 2 * q50) / max(q75 - q25, 1e-12)
    p = gaps[gaps > 0]
    values = np.r_[np.log(len(x)),
        np.log([x.mean(), x.std(ddof=1), x[0], x[-1], np.median(x), span]), q,
        zmean, zstd, x.std(ddof=1) / x.mean(),
        np.mean(((z-zmean) / zstd)**3), np.mean(((z-zmean) / zstd)**4)-3, bowley,
        gaps[0], gaps[1], gaps[-1], gaps.max(), np.sort(gaps)[-2:].sum(),
        -np.sum(p * np.log(p)) / np.log(len(gaps)), gaps[:2].sum(), gaps[-2:].sum()]
    assert len(values) == len(FEATURES) and np.isfinite(values).all()
    return values


def verify_source_files():
    for name, expected in CONFIG['source_sha256'].items():
        if sha(CORE / name) != expected:
            raise RuntimeError(f'Frozen implementation changed: {name}')


def prepare():
    verify_source_files()
    if (OUT/'dataset.npz').exists():
        raise FileExistsError('Dataset already exists; use a new version for a new preparation')
    OUT.mkdir(parents=True, exist_ok=True)
    arrays = {k: [] for k in ['x', 'e', 'valid', 'beta', 'eta', 'gamma', 'n', 'rid', 'cell', 'hash', 'split']}
    source_hashes = {}
    for beta in CONFIG['beta']:
        for n in CONFIG['n']:
            path = STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            source_hashes[path.relative_to(STUDY).as_posix()] = sha(path)
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1200
            for row in rows:
                sample = np.array([float(row[f'观测值{i+1}']) for i in range(n)], dtype='<f8')
                fingerprint = hashlib.sha256(sample.tobytes()).hexdigest()
                u = int.from_bytes(hashlib.sha256(SPLIT_NAMESPACE+fingerprint.encode()).digest()[:8], 'big') / 2**64
                split = 0 if u < .6 else 1 if u < .8 else 2
                valid = np.array([row[f'{m}_状态'] == 'success' for m in METHODS])
                errors = np.full(7, np.nan)
                truth = quantile_true(beta, 1000., 500., .9)
                for j, m in enumerate(METHODS):
                    if valid[j]:
                        values = [float(row[f'{m}_{p}估计']) for p in ['形状', '尺度', '位置']]
                        errors[j] = quantile_est(*values, .9) - truth
                values = dict(x=features(sample), e=errors, valid=valid, beta=beta,
                    eta=1000., gamma=500., n=n, rid=int(row['样本编号']),
                    cell=f'b{beta:g}_n{n}', hash=fingerprint, split=split)
                for key in arrays:
                    arrays[key].append(values[key])
    data = {k: np.asarray(v) for k, v in arrays.items()}
    assert np.isfinite(data['e'][data['valid']]).all()
    assignments = {}
    for h, s in zip(data['hash'], data['split']):
        if h in assignments:
            assert assignments[h] == s
        assignments[h] = s
    np.savez_compressed(OUT/'dataset.npz', **data)
    cells = []
    for c in np.unique(data['cell']):
        idx = data['cell'] == c
        cells.append(dict(cell=c, train=int(np.sum(idx & (data['split']==0))),
            validation=int(np.sum(idx & (data['split']==1))), test=int(np.sum(idx & (data['split']==2)))))
    csv_write(OUT/'split_counts.csv', cells)
    manifest = dict(version=VERSION, source_hashes=source_hashes,
        config_sha256=sha(PROGRAM/'实验配置.json'), metadata_sha256=sha(STUDY/'结果/数据说明.json'),
        dataset_sha256=sha(OUT/'dataset.npz'), script_at_preparation=sha(__file__),
        feature_groups=GROUPS, methods=METHODS, rows=len(data['x']),
        unique_samples=len(assignments), split_counts=np.bincount(data['split']).tolist(),
        split_namespace=SPLIT_NAMESPACE.decode(), torch=torch.__version__, numpy=np.__version__,
        scipy=__import__('scipy').__version__, feature_count=len(FEATURES),
        all_method_success=int(data['valid'].all(axis=1).sum()))
    json_write(OUT/'manifest.json', manifest)
    print(json.dumps({k:manifest[k] for k in ['rows','feature_count','split_counts','all_method_success']},ensure_ascii=False), flush=True)


def load_data():
    with np.load(OUT/'dataset.npz', allow_pickle=False) as z:
        return {k:z[k] for k in z.files}


def weights(data, mask):
    cells = data['cell'][mask]
    unique, inverse, counts = np.unique(cells, return_inverse=True, return_counts=True)
    return 1 / counts[inverse] / len(unique) * len(cells)


class RiskNet(nn.Module):
    def __init__(self, dim, width):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim,width), nn.SiLU(), nn.Linear(width,width),
                                 nn.SiLU(), nn.Linear(width,7), nn.Softplus())

    def forward(self, x):
        return self.net(x) + 1e-6


def columns(variant):
    if variant == 'n_only':
        allowed = GROUPS['n']
    elif variant.startswith('no_'):
        group = variant[3:]
        excluded = GROUPS['quantiles']+GROUPS['moments'] if group == 'shape' else GROUPS[group]
        allowed = [f for f in FEATURES if f not in excluded]
    else:
        allowed = FEATURES
    return [FEATURES.index(f) for f in allowed]


def fit(data, label, variant, width, seed, eligible=None, epochs=160):
    target = OUT/'models'/f'{label}.pt'
    if target.exists():
        print(f'Using saved {label}', flush=True)
        return torch.load(target, weights_only=True)
    if eligible is None:
        eligible = np.ones(len(data['x']), dtype=bool)
    train = (data['split']==0) & eligible
    validation = (data['split']==1) & eligible
    idx = columns(variant)
    xt = data['x'][train][:,idx]
    center, scale = xt.mean(axis=0), xt.std(axis=0)
    scale = np.where(scale < 1e-10, 1., scale)
    trw, vaw = weights(data,train), weights(data,validation)
    yt = np.nan_to_num(data['e'][train]**2, nan=0.)
    yv = np.nan_to_num(data['e'][validation]**2, nan=0.)
    mt, mv = data['valid'][train], data['valid'][validation]
    yscale = np.sum(yt*trw[:,None],axis=0) / np.sum(mt*trw[:,None],axis=0)
    tensors = [torch.tensor(v,dtype=torch.float32) for v in [
        (xt-center)/scale, yt/yscale, mt*trw[:,None],
        (data['x'][validation][:,idx]-center)/scale, yv/yscale, mv*vaw[:,None]]]
    tx,ty,tm,vx,vy,vm = tensors
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model = RiskNet(len(idx),width)
    optimizer = torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    generator = torch.Generator().manual_seed(seed+10000)
    best, best_epoch, history = math.inf, 0, []
    started = time.monotonic()
    for epoch in range(1,epochs+1):
        model.train()
        perm = torch.randperm(len(tx), generator=generator)
        for batch in perm.split(1024):
            mu = model(tx[batch])
            terms = mu-ty[batch]*torch.log(mu)
            loss = ((terms*tm[batch]).sum(axis=0)/tm[batch].sum(axis=0).clamp_min(1)).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(),10.)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            mu = model(vx)
            score = float((((mu-vy*torch.log(mu))*vm).sum(axis=0)/vm.sum(axis=0)).mean())
        if not math.isfinite(score):
            raise RuntimeError(f'Nonfinite validation score for {label}')
        history.append([epoch,score])
        if score < best-1e-6:
            best, best_epoch = score, epoch
            best_state = copy.deepcopy(model.state_dict())
        if epoch-best_epoch >= 22:
            break
    bundle = dict(state=best_state, columns=idx, center=center.tolist(), scale=scale.tolist(),
        yscale=yscale.tolist(), width=width, seed=seed, variant=variant,
        val_score=best, best_epoch=best_epoch, epochs_run=epoch, train_rows=int(train.sum()),
        validation_rows=int(validation.sum()), seconds=time.monotonic()-started,
        train_hash=hashlib.sha256(''.join(sorted(data['hash'][train])).encode()).hexdigest(),
        features=[FEATURES[i] for i in idx], methods=METHODS, version=VERSION)
    target.parent.mkdir(parents=True,exist_ok=True)
    torch.save(bundle,target)
    json_write(target.with_suffix('.json'), {k:v for k,v in bundle.items() if k!='state'} | {'history':history})
    print(f'{label}: epoch={best_epoch}/{epoch} val={best:.5f} seconds={bundle["seconds"]:.1f}',flush=True)
    return bundle


def predict(bundle, x):
    model = RiskNet(len(bundle['columns']),bundle['width'])
    model.load_state_dict(bundle['state'])
    model.eval()
    z = (x[:,bundle['columns']]-np.asarray(bundle['center']))/np.asarray(bundle['scale'])
    with torch.no_grad():
        out = model(torch.tensor(z,dtype=torch.float32)).numpy().astype(float)
    return out*np.asarray(bundle['yscale'])


def ensemble(paths, x):
    return np.mean([predict(torch.load(p,weights_only=True),x) for p in paths],axis=0)


def train():
    data = load_data()
    trials = [fit(data,f'full_w{w}_s42','full',w,42) for w in [32,64]]
    chosen = min(trials,key=lambda b:b['val_score'])
    width = chosen['width']
    paths = [OUT/'models'/f'full_w{width}_s42.pt']
    for seed in [43,44]:
        label = f'full_w{width}_s{seed}'
        fit(data,label,'full',width,seed)
        paths.append(OUT/'models'/f'{label}.pt')
    variants = ['n_only','no_n','no_level','no_shape','no_spacing']
    for variant in variants:
        fit(data,variant,variant,width,42)
    holdouts = {'beta_2.5':data['beta']!=2.5, 'n_15':data['n']!=15, 'n_50':data['n']!=50}
    holdout_models = {}
    for name,eligible in holdouts.items():
        candidates = [fit(data,f'holdout_{name}_w{w}','full',w,42,eligible) for w in [32,64]]
        best = min(candidates,key=lambda b:b['val_score'])
        holdout_models[name] = f'models/holdout_{name}_w{best["width"]}.pt'
    selection = dict(width=width,seeds=[42,43,44], models=[str(p.relative_to(OUT)) for p in paths],
        validation_scores={str(b['width']):b['val_score'] for b in trials},
        ablations=variants, holdouts=list(holdouts), holdout_models=holdout_models, selection_uses_test=False,
        checkpoint_metric='mean-consistent risk score on validation only')
    json_write(OUT/'selection.json',selection)
    print('Training finished; selection frozen before test evaluation.',flush=True)


def equal_summary(errors, cells):
    pooled = summarize_standard_errors(errors)
    summaries = [summarize_standard_errors(errors[cells==c]) for c in np.unique(cells)]
    summaries = [s for s in summaries if s['n']]
    return dict(pooled=pooled, rmse=float(np.sqrt(np.mean([s['mse'] for s in summaries]))),
        bias=float(np.mean([s['bias'] for s in summaries])), mae=float(np.mean([s['mae'] for s in summaries])),
        p95_abs=float(np.percentile(np.abs(errors[np.isfinite(errors)]),95)) if np.isfinite(errors).any() else None)


def fallback(errors, valid, scores):
    order = np.argsort(scores,axis=1,kind='stable')
    available = np.take_along_axis(valid,order,axis=1)
    has = available.any(axis=1)
    first_good = available.argmax(axis=1)
    chosen = order[np.arange(len(order)),first_good]
    e = errors[np.arange(len(order)),chosen].copy()
    e[~has] = np.nan
    first = order[:,0]
    return e,first,chosen,~valid[np.arange(len(order)),first],~has


def bootstrap_delta(a,b,cells,repeats=1500):
    rng = np.random.default_rng(2026102409)
    aa,bb = np.zeros(repeats),np.zeros(repeats)
    for c in np.unique(cells):
        ii = np.flatnonzero(cells==c)
        draws = rng.integers(0,len(ii),(repeats,len(ii)))
        aa += np.mean(a[ii][draws]**2,axis=1)
        bb += np.mean(b[ii][draws]**2,axis=1)
    improve = (1-np.sqrt(bb/aa))*100
    return np.percentile(improve,[2.5,97.5]).tolist()


def training_rules(data, train_mask, target):
    common = data['valid'].all(axis=1) & train_mask
    cell_scores = {}
    for c in np.unique(data['cell'][common]):
        idx = common & (data['cell']==c)
        cell_scores[(float(data['beta'][idx][0]),int(data['n'][idx][0]))] = np.mean(data['e'][idx]**2,axis=0)
    fixed = np.mean(list(cell_scores.values()),axis=0)
    by_n = {n:np.mean([s for (b,nn),s in cell_scores.items() if nn==n],axis=0)
            for n in np.unique(data['n'][common])}
    n_scores = np.empty((len(target['x']),7))
    table_scores = np.empty_like(n_scores)
    for i,(n,beta) in enumerate(zip(target['n'],target['beta'])):
        n_scores[i] = by_n.get(int(n),fixed)
        table_scores[i] = cell_scores.get((float(beta),int(n)),fixed)
    return dict(fixed=np.broadcast_to(fixed,(len(target['x']),7)).copy(),n_rule=n_scores,
                truth_table_reference=table_scores)


def subset(data, mask):
    return {k:v[mask] for k,v in data.items()}


def evaluate_scores(data, score_map):
    common = data['valid'].all(axis=1)
    metrics, selections = {},{}
    for name,scores in score_map.items():
        e,first,chosen,first_fail,all_fail = fallback(data['e'],data['valid'],scores)
        common_e = data['e'][np.arange(len(first)),first]
        metrics[name] = dict(all_attempts=equal_summary(e,data['cell']),
            common=equal_summary(common_e[common],data['cell'][common]),
            first_failure_rate=float(first_fail.mean()), final_failure_rate=float(all_fail.mean()),
            first_choice_counts=np.bincount(first,minlength=7).tolist(),
            final_choice_counts=np.bincount(chosen[~all_fail],minlength=7).tolist())
        selections[name] = (e,first,chosen)
    fixed_e = selections['fixed'][0]
    for name in metrics:
        metrics[name]['improvement_all_pct'] = (1-metrics[name]['all_attempts']['rmse']/metrics['fixed']['all_attempts']['rmse'])*100
        metrics[name]['improvement_common_pct'] = (1-metrics[name]['common']['rmse']/metrics['fixed']['common']['rmse'])*100
        if name in ['network','full_single','n_rule']:
            metrics[name]['improvement_all_ci95'] = bootstrap_delta(fixed_e,selections[name][0],data['cell'])
    return metrics,selections


def evaluate():
    data = load_data()
    selection = json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
    test = subset(data,data['split']==2)
    paths = [OUT/p for p in selection['models']]
    score_map = training_rules(data,data['split']==0,test)
    score_map['network'] = ensemble(paths,test['x'])
    single_path = OUT/'models'/f'full_w{selection["width"]}_s42.pt'
    score_map['full_single'] = predict(torch.load(single_path,weights_only=True),test['x'])
    for variant in selection['ablations']:
        score_map[variant] = predict(torch.load(OUT/'models'/f'{variant}.pt',weights_only=True),test['x'])
    # Per-sample hindsight optimum is an opportunity reference, never a deployable strategy.
    score_map['hindsight_reference'] = np.where(test['valid'],test['e']**2,np.inf)
    metrics,chosen = evaluate_scores(test,score_map)
    calibration, calibration_bins = [],[]
    for j,m in enumerate(METHODS):
        good = test['valid'][:,j]
        y = test['e'][good,j]**2
        pred = score_map['network'][good,j]
        constant = score_map['fixed'][good,j]
        calibration.append(dict(method=m,n=int(good.sum()), predicted_mean=float(pred.mean()),
            observed_mean=float(y.mean()), ratio=float(pred.mean()/y.mean()),
            risk_prediction_rmse=float(np.sqrt(np.mean((pred-y)**2))),
            constant_prediction_rmse=float(np.sqrt(np.mean((constant-y)**2))),
            spearman=float(spearmanr(pred,y).statistic)))
        for k,idx in enumerate(np.array_split(np.argsort(pred),10)):
            calibration_bins.append(dict(method=m,bin=k+1,n=len(idx),predicted=float(pred[idx].mean()),observed=float(y[idx].mean())))
    rows, cell_rows = [],[]
    for i in range(len(test['x'])):
        row = {k: (int(test[k][i]) if k in ['n','rid'] else float(test[k][i]) if k=='beta' else str(test[k][i]))
               for k in ['beta','n','rid','cell','hash']}
        for name in ['network','fixed','n_rule','full_single']:
            row[name+'_error'] = float(chosen[name][0][i])
            row[name+'_first'] = METHODS[chosen[name][1][i]]
            row[name+'_final'] = METHODS[chosen[name][2][i]]
        for j,m in enumerate(METHODS):
            row[m+'_predicted_mse'] = float(score_map['network'][i,j])
            row[m+'_error'] = float(test['e'][i,j]) if test['valid'][i,j] else ''
        rows.append(row)
    for c in np.unique(test['cell']):
        mask = test['cell']==c
        for name in score_map:
            e = chosen[name][0][mask]
            stats = summarize_standard_errors(e)
            cell_rows.append(dict(cell=c,strategy=name,total=int(mask.sum()),**stats))
    holdouts = {}
    for name in selection['holdouts']:
        mask = data['beta']==2.5 if name=='beta_2.5' else data['n']==int(name.split('_')[1])
        target = subset(data,mask)
        scores = training_rules(data,(data['split']==0)&~mask,target)
        scores['network'] = predict(torch.load(OUT/selection['holdout_models'][name],weights_only=True),target['x'])
        holdouts[name],_ = evaluate_scores(target,scores)
    json_write(OUT/'evaluation.json',dict(test_rows=len(test['x']), common_rows=int(test['valid'].all(axis=1).sum()),
        methods=METHODS, metrics=metrics, calibration=calibration,holdouts=holdouts))
    csv_write(OUT/'test_predictions.csv',rows)
    csv_write(OUT/'cell_metrics.csv',cell_rows)
    csv_write(OUT/'risk_calibration.csv',calibration)
    csv_write(OUT/'risk_calibration_bins.csv',calibration_bins)
    print(json.dumps({k:dict(rmse=v['all_attempts']['rmse'], improvement=v['improvement_all_pct'])
                      for k,v in metrics.items()},ensure_ascii=False),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','train','evaluate','predict'])
    parser.add_argument('--sample',nargs='+',type=float)
    args = parser.parse_args()
    if args.phase=='prepare':
        prepare()
    elif args.phase=='train':
        train()
    elif args.phase=='evaluate':
        evaluate()
    else:
        selection = json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
        risk = ensemble([OUT/p for p in selection['models']],features(args.sample)[None,:])[0]
        print(json.dumps(dict(n=len(args.sample),training_scope=dict(eta=1000,gamma=500,
            beta_grid=CONFIG['beta'],n_grid=CONFIG['n'],risk_target='conditional on method success'),
            prediction=[dict(method=METHODS[j],expected_mse=float(risk[j]),
            expected_rms_error=float(np.sqrt(risk[j]))) for j in np.argsort(risk)]),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
