"""Matched-seed information ablation and observed feature/error effect sizes."""
from __future__ import annotations
import argparse
import csv
import json
import numpy as np
import torch
import b10_feature_selector as s

DEST=s.OUT/'factor_analysis'
VARIANTS=['no_n','no_level','no_shape','no_spacing']
SEEDS=[42,43,44]
CONTRAST_FEATURES=['log_min','log_mean','gap_first','skewness']
GROUP_LABELS={'no_n':'样本量n','no_level':'位置与尺度','no_shape':'分布形状','no_spacing':'相邻间距'}


def path_for(variant,seed):
    if variant=='full':
        return s.OUT/'models'/f'full_w64_s{seed}.pt'
    return s.OUT/'models'/(f'{variant}.pt' if seed==42 else f'factor_{variant}_s{seed}.pt')


def train():
    DEST.mkdir(parents=True,exist_ok=True)
    data=s.load_data()
    selection=json.loads((s.OUT/'selection.json').read_text(encoding='utf-8'))
    assert selection['width']==64
    spec=dict(variants=VARIANTS,seeds=SEEDS,width=64,bootstrap=1500,contrast_features=CONTRAST_FEATURES,
        same_original_split=True,no_new_hyperparameter_selection=True,
        scheme='matched-seed full vs remove-group and refit; actual-error quartile associations separately')
    s.json_write(DEST/'analysis_spec.json',spec)
    for variant in VARIANTS:
        for seed in SEEDS:
            if seed==42:
                assert path_for(variant,seed).exists()
            else:
                s.fit(data,f'factor_{variant}_s{seed}',variant,64,seed)
    print('Matched-seed ablation training complete.',flush=True)


def deviance(prediction,errors,valid,yscale):
    y=np.nan_to_num(errors**2,nan=0)/yscale
    mu=prediction/yscale
    log_ratio=np.zeros_like(y)
    positive=y>0
    log_ratio[positive]=np.log(y[positive]/mu[positive])
    result=2*(y*log_ratio-y+mu)
    assert np.all(result>=-1e-9)
    return np.where(valid,result,0.)


def condition_average(losses,valid,cells):
    # losses shape: model/seed x sample x method; invalid labels are excluded, not zero-error labels.
    return np.mean([losses[:,cells==c,:].sum(axis=1)/valid[cells==c].sum(axis=0)
                    for c in np.unique(cells)],axis=0)


def bootstrap_losses(losses,valid,cells,repeats=1500):
    rng=np.random.default_rng(2026102411)
    sums=np.zeros((repeats,losses.shape[0],7))
    for c in np.unique(cells):
        idx=np.flatnonzero(cells==c)
        counts=rng.multinomial(len(idx),np.full(len(idx),1/len(idx)),size=repeats).astype(float)
        denom=counts@valid[idx].astype(float)
        assert (denom>0).all()
        flat=losses[:,idx,:].transpose(1,0,2).reshape(len(idx),-1)
        values=(counts@flat).reshape(repeats,losses.shape[0],7)
        sums+=values/denom[:,None,:]
    return sums/len(np.unique(cells))


def ablation():
    data=s.load_data();test=s.subset(data,data['split']==2)
    base=torch.load(path_for('full',42),weights_only=True)
    scale=np.asarray(base['yscale'])
    variants=['full']+VARIANTS
    loss_sets=[];seed_losses={};prediction_losses=[]
    for variant in variants:
        losses=[];raw_prediction_losses=[]
        for seed in SEEDS:
            bundle=torch.load(path_for(variant,seed),weights_only=True)
            np.testing.assert_allclose(bundle['yscale'],scale,rtol=0,atol=0)
            assert bundle['train_hash']==base['train_hash']
            prediction=s.predict(bundle,test['x'])
            losses.append(deviance(prediction,test['e'],test['valid'],scale))
            raw=np.where(test['valid'],(prediction-np.nan_to_num(test['e']**2,nan=0))**2,0.)
            raw_prediction_losses.append(raw)
        losses=np.asarray(losses)
        seed_losses[variant]=condition_average(losses,test['valid'],test['cell'])
        loss_sets.append(losses.mean(axis=0))
        prediction_losses.append(np.asarray(raw_prediction_losses).mean(axis=0))
    loss_sets=np.asarray(loss_sets)
    observed=condition_average(loss_sets,test['valid'],test['cell'])
    boot=bootstrap_losses(loss_sets,test['valid'],test['cell'])
    raw_rmse=np.sqrt(condition_average(np.asarray(prediction_losses),test['valid'],test['cell']))
    records=[]
    for i,variant in enumerate(VARIANTS,1):
        change=(observed[i]/observed[0]-1)*100
        boot_change=(boot[:,i,:]/boot[:,0,:]-1)*100
        seed_change=(seed_losses[variant]/seed_losses['full']-1)*100
        ci=np.percentile(boot_change,[2.5,97.5],axis=0)
        for j,m in enumerate(s.METHODS):
            records.append(dict(group=variant,label=GROUP_LABELS[variant],method=m,
                full_loss=float(observed[0,j]),removed_loss=float(observed[i,j]),
                loss_increase=float(observed[i,j]-observed[0,j]),loss_increase_pct=float(change[j]),
                ci95_low=float(ci[0,j]),ci95_high=float(ci[1,j]),
                seed_min=float(seed_change[:,j].min()),seed_max=float(seed_change[:,j].max()),
                full_risk_prediction_rmse=float(raw_rmse[0,j]),removed_risk_prediction_rmse=float(raw_rmse[i,j]),
                successful_test_samples=int(test['valid'][:,j].sum())))
    by_n=[]
    for n in s.CONFIG['n']:
        mask=test['n']==n
        scores=condition_average(loss_sets[:,mask,:],test['valid'][mask],test['cell'][mask])
        for i,variant in enumerate(VARIANTS,1):
            for j,m in enumerate(s.METHODS):
                by_n.append(dict(n=n,group=variant,method=m,loss_increase_pct=float((scores[i,j]/scores[0,j]-1)*100)))
    s.csv_write(DEST/'method_group_ablation.csv',records)
    s.csv_write(DEST/'method_group_ablation_by_n.csv',by_n)
    s.json_write(DEST/'method_group_ablation.json',dict(records=records,methods=s.METHODS,
        estimand='relative loss of per-method risk prediction after group removal and refitting',
        three_matched_initializations=True,all_beta_n_cells_equal_weight=True,
        bootstrap='paired resampling within beta*n; trained models fixed; seed range separate',
        causal_effect=False,negative_contributions_retained=True))
    print(json.dumps({g:{r['method']:round(r['loss_increase_pct'],2) for r in records if r['group']==g}
                     for g in VARIANTS},ensure_ascii=False),flush=True)


def feature_curves():
    data=s.load_data();common=data['valid'].all(axis=1)
    train=data['split']==0;test=(data['split']==2)&common
    rng=np.random.default_rng(2026102412)
    records=[];contrasts=[];repeats=1500
    for feature in CONTRAST_FEATURES:
        fi=s.FEATURES.index(feature)
        groups=[]
        for c in np.unique(data['cell']):
            tm=train&(data['cell']==c);vm=test&(data['cell']==c)
            cuts=np.quantile(data['x'][tm,fi],[.25,.5,.75])
            bins=np.searchsorted(cuts,data['x'][vm,fi],side='right')
            e=data['e'][vm]
            if any(not np.any(bins==k) for k in range(4)):
                continue
            groups.append([e[bins==k] for k in range(4)])
        if not groups:
            raise RuntimeError(f'No conditions support four bins: {feature}')
        mse=np.mean([[np.mean(e**2,axis=0) for e in group] for group in groups],axis=0)
        rmse=np.sqrt(mse)
        low_boot=np.zeros((repeats,7));high_boot=np.zeros_like(low_boot)
        for group in groups:
            for e,dest in [(group[0],low_boot),(group[3],high_boot)]:
                counts=rng.multinomial(len(e),np.full(len(e),1/len(e)),size=repeats)
                dest+=(counts@(e**2))/len(e)
        boot_pct=(np.sqrt(high_boot/low_boot)-1)*100
        boot_abs=np.sqrt(high_boot/len(groups))-np.sqrt(low_boot/len(groups))
        pci=np.percentile(boot_pct,[2.5,97.5],axis=0)
        aci=np.percentile(boot_abs,[2.5,97.5],axis=0)
        for j,m in enumerate(s.METHODS):
            contrasts.append(dict(feature=feature,method=m,conditions=len(groups),
                q1_rmse=float(rmse[0,j]),q4_rmse=float(rmse[3,j]),
                q4_minus_q1=float(rmse[3,j]-rmse[0,j]),q4_vs_q1_pct=float((rmse[3,j]/rmse[0,j]-1)*100),
                pct_ci95_low=float(pci[0,j]),pct_ci95_high=float(pci[1,j]),
                abs_ci95_low=float(aci[0,j]),abs_ci95_high=float(aci[1,j])))
            for k in range(4):
                records.append(dict(feature=feature,method=m,bin=k+1,rmse=float(rmse[k,j]),
                    conditions=len(groups),observations=sum(len(g[k]) for g in groups)))
    s.csv_write(DEST/'actual_error_quartile_curves.csv',records)
    s.csv_write(DEST/'actual_error_quartile_contrasts.csv',contrasts)
    s.json_write(DEST/'actual_error_quartile_contrasts.json',dict(records=contrasts,
        population='seven-method common success; eligible beta*n cells equal weight',
        bins='training-part quartiles within each beta*n; same condition set across all four bins',
        interpretation='observed association amplitude, not intervention or isolated causal effect'))
    print('Actual-error contrasts saved for four preselected observable features.',flush=True)


def sample_size_profile():
    data=s.load_data();test=data['split']==2
    rows=[]
    for n in s.CONFIG['n']:
        for j,m in enumerate(s.METHODS):
            values=[]
            for beta in s.CONFIG['beta']:
                mask=test&(data['n']==n)&(data['beta']==beta)&data['valid'][:,j]
                values.append(s.summarize_standard_errors(data['e'][mask,j])['mse'])
            group=test&(data['n']==n)
            rows.append(dict(n=n,method=m,rmse=float(np.sqrt(np.mean(values))),
                success=int(data['valid'][group,j].sum()),total=int(group.sum()),
                failure_rate=float(1-data['valid'][group,j].mean())))
    s.csv_write(DEST/'actual_method_error_by_n.csv',rows)


def verify():
    manifest=json.loads((s.OUT/'manifest.json').read_text(encoding='utf-8'))
    assert s.sha(s.OUT/'dataset.npz')==manifest['dataset_sha256']
    for name,expected in manifest['model_sha256'].items():
        assert s.sha(s.OUT/name)==expected
    s.verify_source_files()
    ones=np.ones((2,7));valid=np.ones((2,7),dtype=bool)
    np.testing.assert_allclose(deviance(ones,ones,valid,np.ones(7)),0,atol=1e-12)
    np.testing.assert_allclose(deviance(ones,np.zeros_like(ones),valid,np.ones(7)),2,atol=1e-12)
    a=deviance(2*ones,.5*ones,valid,np.ones(7))
    b=deviance(8*ones,ones,valid,4*np.ones(7))
    np.testing.assert_allclose(a,b,atol=1e-12)
    data=s.load_data();base=torch.load(path_for('full',42),weights_only=True)
    for variant in VARIANTS:
        for seed in SEEDS:
            bundle=torch.load(path_for(variant,seed),weights_only=True)
            assert bundle['columns']==s.columns(variant) and bundle['width']==64
            assert bundle['train_hash']==base['train_hash'] and bundle['train_rows']==28807
    with (DEST/'method_group_ablation.csv').open(encoding='utf-8-sig',newline='') as f:
        records=list(csv.DictReader(f))
    assert len(records)==28
    for row in records:
        expected=(float(row['removed_loss'])/float(row['full_loss'])-1)*100
        np.testing.assert_allclose(float(row['loss_increase_pct']),expected,atol=1e-12)
    with (DEST/'actual_error_quartile_contrasts.csv').open(encoding='utf-8-sig',newline='') as f:
        records=list(csv.DictReader(f))
    assert len(records)==28 and all(int(r['conditions'])==40 for r in records)
    # Independent reference calculation of one reported actual-error contrast.
    low=[];high=[];fi=s.FEATURES.index('log_min');j=s.METHODS.index('MLE')
    for c in np.unique(data['cell']):
        tr=(data['cell']==c)&(data['split']==0)
        te=(data['cell']==c)&(data['split']==2)&data['valid'].all(axis=1)
        q1,q3=np.quantile(data['x'][tr,fi],[.25,.75])
        low.append(s.summarize_standard_errors(data['e'][te&(data['x'][:,fi]<q1),j])['mse'])
        high.append(s.summarize_standard_errors(data['e'][te&(data['x'][:,fi]>=q3),j])['mse'])
    row=next(r for r in records if r['feature']=='log_min' and r['method']=='MLE')
    np.testing.assert_allclose([float(row['q1_rmse']),float(row['q4_rmse'])],np.sqrt([np.mean(low),np.mean(high)]),rtol=1e-12)
    result=dict(result='passed',method_group_contrasts=28,actual_error_contrasts=28,
        matched_seeds=[42,43,44],group_deletion_is_refit=True,all_contrasts_cover_conditions=40,
        original_checkpoint_hashes_unchanged=True,dataset_hash_unchanged=True,
        deviance_formula_and_units_checked=True,actual_error_reference_checked=True,
        interpretation='predictive contribution and observed association; not causal attribution')
    s.json_write(DEST/'verification.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['train','evaluate','verify'])
    args=parser.parse_args()
    if args.phase=='train':
        train()
    elif args.phase=='evaluate':
        ablation()
        feature_curves()
        sample_size_profile()
    else:
        verify()
