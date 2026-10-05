"""Append n=100 to E10 without rewriting the frozen n=30/50 outputs.

Run stages in order: scan, train, test, summarize, audit. Each scan and test
cell is an atomic checkpoint. Set OPENBLAS/OMP/MKL threads to one before launch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_e10 as base

base.NS = (100,)
HERE = Path(__file__).resolve().parent
OUT = HERE / 'n100'
METHODS = list(base.METHODS)
PARAMS = ('beta', 'eta', 'gamma')
DRAW_COUNT = 2000


def old_hashes():
    reference = json.loads((HERE / 'n100_baseline_hashes.json').read_text(encoding='utf8'))
    changed = [name for name, value in reference.items() if not (HERE / name).is_file()
               or base.file_sha(HERE / name) != value]
    if changed:
        raise RuntimeError(f'frozen n=30/50 artifacts changed: {changed[:8]}')
    return {'files':len(reference), 'all_unchanged':True,
            'baseline_sha256':base.file_sha(HERE / 'n100_baseline_hashes.json')}


def verify_mdm():
    OUT.mkdir(exist_ok=True)
    records=[]
    for beta,ratio,repeat in ((1.5,.1,0),(2.,.5,37),(3.,1.,149),(5.,.25,299)):
        obs=base.generate_sample(beta,1000.,ratio*1000.,100,repeat,seed=base.DEV_SEED)
        cached=base.CachedMDM(obs)
        for delta in (0.,.1,.24,.5):
            got,strategy=cached.fit(delta)
            direct=base.run_method('mdm',obs,offset=delta,gamma_steps=60)
            expected=np.array([direct[k] for k in ('beta_hat','eta_hat','gamma_hat')])
            err=float(np.max(np.abs(got-expected)/np.maximum(np.abs(expected),1.)))
            records.append(dict(beta=beta,ratio=ratio,repeat_id=repeat,delta=delta,
                                max_relative=err,cached_strategy=strategy,
                                production_converged=bool(direct['converged'])))
    report=dict(comparisons=len(records),max_relative=max(row['max_relative'] for row in records),records=records)
    assert report['max_relative']<1e-8
    base.write_json(OUT/'cached_mdm_verification.json',report)
    print(f"n=100 cached MDM matches production: {len(records)} probes",flush=True)


def rows():
    files = sorted((HERE / 'test_cells').glob('n100_cell*.csv'))
    assert len(files) == 12, len(files)
    df = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
    assert len(df) == 4800
    df.valid = df.valid.astype(str).str.lower().eq('true')
    assert not df.duplicated(['cell_id','repeat_id','method']).any()
    assert df.groupby(['cell_id','repeat_id']).sample_sha256.nunique().eq(1).all()
    for param, denominator in [('beta', df.beta), ('eta', df.eta), ('gamma', df.eta)]:
        df[f'err_{param}'] = (df[f'{param}_hat'] - df[param]) / denominator
    df['squared_loss'] = df[[f'err_{p}' for p in PARAMS]].pow(2).sum(axis=1,min_count=3)
    return df


def metrics(group):
    valid = group[group.valid]
    result = dict(samples=len(group),valid_samples=len(valid),failures=len(group)-len(valid),
                  failure_rate=1-len(valid)/len(group),
                  J1_valid=float(np.sqrt(valid.squared_loss.mean())))
    for param in PARAMS:
        errors = valid[f'err_{param}']
        result[f'bias_{param}'] = float(errors.mean())
        result[f'sd_{param}'] = float(errors.std(ddof=1))
        result[f'rmse_{param}'] = float(np.sqrt(np.mean(errors**2)))
    return pd.Series(result)


def summarize():
    old_hashes()
    OUT.mkdir(exist_ok=True)
    df = rows()
    df.to_csv(OUT / 'per_sample.csv.gz',index=False,compression='gzip')
    df.groupby(['n','method']).apply(metrics,include_groups=False).reset_index().to_csv(
        OUT/'by_n.csv',index=False)
    df.groupby(['n','cell_id','beta','gamma_over_eta','method']).apply(metrics,include_groups=False).reset_index().to_csv(
        OUT/'by_cell.csv',index=False)

    keys = ['cell_id','repeat_id']
    valid = df.pivot(index=keys,columns='method',values='valid')[METHODS]
    assert valid.shape == (1200,4) and not valid.isna().any().any()
    wide_loss = df.pivot(index=keys,columns='method',values='squared_loss')
    pair = valid['AMDM'] & valid['MDM-0.1']
    rng = np.random.default_rng(20260925)
    pair_blocks = []
    for cell in sorted(valid.index.get_level_values('cell_id').unique()):
        mask = pair.loc[cell]
        block = wide_loss.loc[cell].loc[mask,['AMDM','MDM-0.1']].to_numpy()
        assert len(block) > 0 and np.isfinite(block).all()
        pair_blocks.append(block)
    paired = np.concatenate(pair_blocks)
    pair_j1 = np.sqrt(paired.mean(axis=0))
    pair_sums = np.zeros((DRAW_COUNT,2))
    for block in pair_blocks:
        ids = rng.integers(0,len(block),size=(DRAW_COUNT,len(block)))
        pair_sums += block[ids].sum(axis=1)
    pair_j1_draws = np.sqrt(pair_sums/len(paired))
    pair_gain = 1-pair_j1_draws[:,0]/pair_j1_draws[:,1]
    pd.DataFrame([dict(n=100,pair_valid_samples=len(paired),AMDM_J1=pair_j1[0],
        MDM_J1=pair_j1[1],relative_gain=1-pair_j1[0]/pair_j1[1],
        ci95_low=np.quantile(pair_gain,.025),ci95_high=np.quantile(pair_gain,.975),
        bootstrap_draws=DRAW_COUNT)]).to_csv(OUT/'paired_interval.csv',index=False)

    common = valid.all(axis=1)
    retained = {cell:int(common.loc[cell].sum()) for cell in sorted(valid.index.get_level_values('cell_id').unique())}
    common_ids = common[common].index
    assert len(common_ids) > 0
    selected = df.set_index(keys+['method']).loc[
        [(cell,repeat,method) for cell,repeat in common_ids for method in METHODS]].reset_index()
    selected[keys+['sample_sha256']].drop_duplicates().to_csv(OUT/'four_method_common_samples.csv',index=False)
    by_cell_array = []
    for cell in sorted(retained):
        ids = common.loc[cell][common.loc[cell]].index
        block = selected[selected.cell_id==cell].set_index(['repeat_id','method'])
        cube = np.stack([block.loc[[(repeat,method) for repeat in ids],
                               [f'err_{p}' for p in PARAMS]].to_numpy(dtype=float)**2
                         for method in METHODS],axis=1)
        assert cube.shape == (len(ids),4,3) and np.isfinite(cube).all()
        by_cell_array.append(cube)
    all_errors = np.concatenate(by_cell_array)
    assert len(all_errors)==len(common_ids)
    rmse = np.sqrt(all_errors.mean(axis=0))
    boot_sums = np.zeros((DRAW_COUNT,4,3))
    for block in by_cell_array:
        ids = rng.integers(0,len(block),size=(DRAW_COUNT,len(block)))
        boot_sums += block[ids].sum(axis=1)
    boot_rmse = np.sqrt(boot_sums/len(all_errors))
    boot_gain = 1-boot_rmse/boot_rmse[:,3:4,:]
    curve_rows = []
    for j,param in enumerate(PARAMS):
        for k,method in enumerate(METHODS):
            lo,hi = np.quantile(boot_gain[:,k,j],[.025,.975])
            curve_rows.append(dict(n=100,parameter=param,method=method,
                common_valid_samples=len(common_ids),rmse=rmse[k,j],MLE_rmse=rmse[3,j],
                relative_reduction=1-rmse[k,j]/rmse[3,j],ci95_low=lo,ci95_high=hi,
                bootstrap_draws=DRAW_COUNT,retained_per_cell=json.dumps(retained,sort_keys=True)))
    pd.DataFrame(curve_rows).to_csv(OUT/'parameter_vs_mle.csv',index=False)
    np.savez_compressed(OUT/'bootstrap_draws.npz',pair_gain=pair_gain,
                        parameter_vs_mle_gain=boot_gain)
    report = dict(status='completed',n=100,development_samples=12000,
        candidate_losses=312000,test_samples=1200,method_rows=4800,
        four_method_common_valid=len(common_ids),retained_per_cell=retained,
        development_seed=base.DEV_SEED,test_seed=base.TEST_SEED,model_seed=1,
        resampling='2000 paired repeat draws within each condition; four method common-valid samples for MLE-relative RMSE',
        frozen_old_artifacts=old_hashes(),
        source_hashes={str(p.relative_to(base.REPO)):base.file_sha(p) for p in [
            base.REPO/'python/methods/mdm.py',base.REPO/'python/methods/mle.py',
            base.REPO/'python/methods/wmle.py',base.REPO/'python/studies/common/sample.py',
            base.REPO/'python/studies/common/runner.py',
            HERE.parent/'E09_六方法共同测试/wmle_solver.py',HERE/'run_e10.py',HERE/'run_e10_n100.py']},
        model_sha256=base.file_sha(HERE/'models'/'n100_final.json'),
        output_hashes={p.name:base.file_sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ('manifest.json','verification.json')})
    base.write_json(OUT/'manifest.json',report)
    print(pd.read_csv(OUT/'paired_interval.csv').to_string(index=False),flush=True)
    print(pd.read_csv(OUT/'parameter_vs_mle.csv')[['parameter','method','relative_reduction','ci95_low','ci95_high']].to_string(index=False),flush=True)


def audit():
    old = old_hashes()
    mdm_report=json.loads((OUT/'cached_mdm_verification.json').read_text(encoding='utf8'))
    assert mdm_report['comparisons']>=16 and mdm_report['max_relative']<1e-8
    dev = sorted((HERE/'dev_cells').glob('n100_cell*.npz'))
    assert len(dev)==40
    dev_hashes=set()
    bad_candidates=0
    for path in dev:
        with np.load(path) as z:
            x,hats,loss,valid,hashes=[z[k] for k in ('x','hats','loss','valid','sample_sha256')]
            beta,eta,gamma=[float(z[k]) for k in ('beta','eta','gamma')]
            assert x.shape==(300,100) and hats.shape==(300,26,3) and loss.shape==(300,26)
            calculated=np.sum(((hats-[beta,eta,gamma])/[beta,eta,eta])**2,axis=2)
            assert np.array_equal(np.isfinite(loss),valid)
            assert np.allclose(loss[valid],calculated[valid],rtol=1e-12,atol=1e-13)
            bad_candidates += int((~valid).sum())
            for repeat in range(300):
                assert base.sample_sha(x[repeat])==hashes[repeat]
                dev_hashes.add(hashes[repeat])
            for repeat in (0,149,299):
                reconstructed=base.generate_sample(beta,eta,gamma,100,repeat,seed=base.DEV_SEED)
                assert np.array_equal(reconstructed,x[repeat])
    assert len(dev_hashes)==12000
    model=json.loads((HERE/'models'/'n100_final.json').read_text(encoding='utf8'))
    assert model['seed']==1 and model['train_n_samples']==12000 and model['serialized_forward_max_abs']<1e-9
    df=rows()
    test_hashes=set()
    solver_checks=0
    for (cell,repeat), block in df.groupby(['cell_id','repeat_id']):
        row=block.iloc[0]
        obs=base.generate_sample(float(row.beta),float(row.eta),float(row.gamma),100,int(repeat),seed=base.TEST_SEED)
        h=base.sample_sha(obs)
        assert h==row.sample_sha256 and h not in dev_hashes and len(block)==4
        test_hashes.add(h)
        chosen=float(base.DELTAS[np.argmin(base.predict_curve(obs,model))])
        assert np.isclose(block.loc[block.method=='AMDM','delta'].iloc[0],chosen,atol=1e-14)
        if cell.endswith(('00','05','11')) and repeat==0:
            for saved in block.itertuples():
                if saved.method in ('AMDM','MDM-0.1'):
                    fit=base.run_method('mdm',obs,offset=float(saved.delta),gamma_steps=60); scale=1.
                elif saved.method=='WMLE':
                    fit=base.run_wmle_checked(obs/1000.); scale=1000.
                else:
                    fit=base.run_method('mle',obs/1000.); scale=1000.
                vals=[fit.get(k) for k in ('beta_hat','eta_hat','gamma_hat')]
                valid=bool(fit.get('converged')) and all(v is not None and np.isfinite(v) for v in vals)
                if valid:
                    vals[1]*=scale; vals[2]*=scale
                    valid=vals[0]>0 and vals[1]>0 and 0<=vals[2]<obs[0]
                assert bool(saved.valid)==bool(valid)
                if valid:
                    assert np.allclose(vals,[saved.beta_hat,saved.eta_hat,saved.gamma_hat],rtol=1e-9,atol=1e-8)
                solver_checks+=1
    assert len(test_hashes)==1200
    summary=pd.read_csv(OUT/'by_n.csv')
    for row in summary.itertuples():
        part=df[df.method==row.method]
        valid=part[part.valid]
        assert len(part)==1200 and len(valid)==row.valid_samples
        assert np.isclose(np.sqrt(valid.squared_loss.mean()),row.J1_valid,rtol=1e-12)
        for param in PARAMS:
            assert np.isclose(np.sqrt(np.mean(valid[f'err_{param}']**2)),getattr(row,f'rmse_{param}'),rtol=1e-12)
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    assert all(base.file_sha(OUT/name)==h for name,h in manifest['output_hashes'].items())
    report=dict(status='passed',development_samples=len(dev_hashes),candidate_losses=312000,
                invalid_candidate_losses=bad_candidates,test_samples=len(test_hashes),
                development_test_overlap=len(dev_hashes & test_hashes),
                model_deltas_checked=1200,test_solver_rows_recomputed=solver_checks,
                by_n_rows_recomputed=len(summary),frozen_old_artifacts=old)
    report['cached_mdm_comparisons']=mdm_report['comparisons']
    base.write_json(OUT/'verification.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('verify','scan','train','test','summarize','audit','all'))
    stage=parser.parse_args().stage
    old_hashes()
    if stage in ('verify','all'): verify_mdm()
    if stage in ('scan','all'): base.scan()
    if stage in ('train','all'): base.train()
    if stage in ('test','all'): base.test()
    if stage in ('summarize','all'): summarize()
    if stage in ('audit','all'): audit()


if __name__=='__main__':
    main()
