"""Aggregate existing rows with shared metrics; audit sample/solver provenance."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run import HERE, REPO, E09, CONFIG, cells, source_hashes
from studies.common.metrics import summarize_standard_errors
from studies.common.sample import generate_sample

KEYS = ['beta', 'eta', 'gamma', 'n', 'repeat_id']
MAIN = ['cw_i_nonnegative', 'wmle_checked']


def summary(data, groups):
    rows = []
    for key, part in data.groupby(groups, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        valid = part[part.status.eq('success')]
        item = dict(zip(groups, key))
        item.update(total=len(part), valid=len(valid), failures=len(part)-len(valid),
                    failure_rate=1-len(valid)/len(part),
                    J1_valid=float(np.sqrt(valid.joint_squared.mean())) if len(valid) else np.nan,
                    J1_failure3=float(np.sqrt(np.where(part.status.eq('success'),
                                                       part.joint_squared, 3.0).mean())))
        for name in ['beta', 'eta', 'gamma']:
            for scale in ['raw', 'norm']:
                metrics = summarize_standard_errors(valid[f'{name}_{scale}_error'].to_numpy())
                for metric in ['bias', 'rmse', 'sd', 'mae']:
                    item[f'{name}_{scale}_{metric}'] = metrics[metric]
        rows.append(item)
    return pd.DataFrame(rows)


def common(data, methods):
    success = data[data.method_variant.isin(methods) & data.status.eq('success')]
    ids = success.groupby(KEYS).method_variant.nunique()
    ids = ids[ids.eq(len(methods))].reset_index()[KEYS]
    return data[data.method_variant.isin(methods)].merge(ids, on=KEYS, validate='many_to_one')


def main():
    folders = sorted((HERE / 'cells').glob('cell_*'))
    assert len(folders) == 60
    sources = source_hashes()
    frames, manifests = [], []
    for folder in folders:
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['source_sha256'] == sources
        assert manifest['n_repeats'] == CONFIG['repeats']
        frame = pd.read_csv(folder / 'results.csv')
        assert len(frame) == 300
        frame['cell_id'] = int(folder.name.split('_')[-1])
        frames.append(frame)
        manifests.append(manifest)
    data = pd.concat(frames, ignore_index=True)
    assert len(data) == 18000 and not data.duplicated(KEYS + ['method_variant']).any()
    samples = []
    for key in data[KEYS].drop_duplicates().itertuples(index=False, name=None):
        b, e, g, n, rid = key
        x = generate_sample(float(b), float(e), float(g), int(n), int(rid),
                            seed=CONFIG['seed_namespace'])
        samples.append(dict(zip(KEYS, key)) | {'sample_min': float(x.min()),
            'sample_sha256': hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()})
    data = data.merge(pd.DataFrame(samples), on=KEYS, validate='many_to_one')
    success = data.status.eq('success')
    assert (data.loc[success, 'gamma_hat'] < data.loc[success, 'sample_min']).all()
    for p in ['beta', 'eta', 'gamma']:
        # These fields already come from the shared MC metric functions.
        data[f'{p}_raw_error'] = data[f'{p}_error']
        data[f'{p}_norm_error'] = data[f'{p}_rel_error']
    data['joint_squared'] = sum(data[f'{p}_norm_error'] ** 2 for p in ['beta','eta','gamma'])
    info = data.extra.map(lambda t: json.loads(t).get('solution_info', {}) if isinstance(t, str) else {})
    data['failure_reason'] = [v.get('status','unknown') if s != 'success' else ''
                              for v, s in zip(info, data.status)]
    data['production_status'] = [v.get('production_status', '') for v in info]
    data['recovered'] = [bool(v.get('recovered', False)) for v in info]
    data['objective'] = [v.get('objective', np.nan) for v in info]
    data['gamma_over_eta'] = data.gamma / data.eta
    data['min_gap_over_eta'] = (data.sample_min - data.gamma_hat) / data.eta
    data.to_csv(HERE / 'per_sample.csv.gz', index=False, compression='gzip')
    summary(data, ['method_variant','n']).to_csv(HERE/'by_n_own_valid.csv',index=False)
    summary(data, ['method_variant','beta','n']).to_csv(HERE/'by_beta_n.csv',index=False)
    summary(data, ['method_variant','beta','gamma_over_eta','n']).to_csv(HERE/'by_cell.csv',index=False)
    paired = common(data, MAIN)
    summary(paired, ['method_variant','n']).to_csv(HERE/'by_n_common.csv',index=False)
    summary(paired, ['method_variant','beta','n']).to_csv(HERE/'by_beta_n_common.csv',index=False)
    summary(common(data, ['cw_i_paper_domain','wmle_checked']), ['method_variant','n']).to_csv(
        HERE/'by_n_paper_common.csv',index=False)
    data[data.failure_reason.ne('')].groupby(['method_variant','n','failure_reason']).size().rename(
        'count').reset_index().to_csv(HERE/'failure_reasons.csv',index=False)
    boundary = []
    for (method,n), part in data.groupby(['method_variant','n']):
        good = part[part.status.eq('success')]
        boundary.append({'method_variant':method,'n':n,'negative_location':int((good.gamma_hat<0).sum()),
            'near_zero_location':int((good.gamma_hat.abs()/good.eta<1e-5).sum()),
            'near_sample_min_1pct_eta':int((good.min_gap_over_eta<.01).sum()),
            'production_rejected':int(part.production_status.ne('ok').sum()) if method=='wmle_checked' else 0,
            'recovered':int(part.recovered.sum()),'unresolved':int(part.status.ne('success').sum())})
    pd.DataFrame(boundary).to_csv(HERE/'boundary_diagnostics.csv',index=False)
    # Same two methods on the same successful samples, stratified by design cell.
    rng = np.random.default_rng(20260923)  # E09 paired-uncertainty convention
    uncertainty = []
    for n, part in paired.groupby('n'):
        pivot = part.pivot(index=['cell_id','repeat_id'],columns='method_variant',values='joint_squared')
        point = np.sqrt(pivot[MAIN[0]].mean())-np.sqrt(pivot[MAIN[1]].mean())
        arrays = [p[MAIN].to_numpy() for _,p in pivot.groupby(level='cell_id')]
        draws = np.zeros((2000,2))
        total = sum(len(a) for a in arrays)
        for a in arrays:
            indices = rng.integers(0,len(a),size=(2000,len(a)))
            draws += a[indices].sum(axis=1)
        deltas = np.sqrt(draws[:,0]/total)-np.sqrt(draws[:,1]/total)
        uncertainty.append({'n':int(n),'common_samples':total,'delta_J1_mmle_minus_wmle':point,
            'ci95_low':float(np.quantile(deltas,.025)),'ci95_high':float(np.quantile(deltas,.975)),
            'draws':2000,'seed':20260923})
    pd.DataFrame(uncertainty).to_csv(HERE/'paired_uncertainty.csv',index=False)
    # Old samples are reused, not claimed to be new independent evidence.
    old = pd.read_csv(E09/'per_sample.csv.gz')
    old = old[old.method.eq('WMLE')]
    new = data[data.method_variant.eq('wmle_checked') & data.n.ne(50)]
    audit = new.merge(old[['beta','gamma_over_eta','n','repeat_id','sample_sha256']],
                      on=['beta','gamma_over_eta','n','repeat_id'],suffixes=('','_old'),validate='one_to_one')
    assert len(audit)==4800 and audit.sample_sha256.eq(audit.sample_sha256_old).all()
    manifest = {'contract':CONFIG,'total_samples':6000,'total_rows':18000,'cells':60,
                'source_sha256':sources,'code_version':manifests[0]['code_version'],
                'reused_E09_samples_verified':4800,'new_n50_samples':1200,
                'paired_common_counts':dict(zip(pd.DataFrame(uncertainty).n.astype(str),
                                                pd.DataFrame(uncertainty).common_samples)),
                'failure_policy':'separate failure counts; valid-row metrics; sensitivity fixed joint squared loss3'}
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(pd.read_csv(HERE/'by_n_own_valid.csv')[['method_variant','n','failures',
           'beta_norm_rmse','eta_norm_rmse','gamma_norm_rmse','J1_valid']].to_string(index=False))
    print(pd.DataFrame(uncertainty).to_string(index=False))


if __name__ == '__main__':
    main()
