"""Check data boundaries and independently reloaded feature-only inference."""
import csv
import hashlib
import json
import numpy as np
import torch
import b10_feature_selector as s


def main():
    data=s.load_data()
    manifest=json.loads((s.OUT/'manifest.json').read_text(encoding='utf-8'))
    selection=json.loads((s.OUT/'selection.json').read_text(encoding='utf-8'))
    s.verify_source_files()
    for name,digest in manifest['source_hashes'].items():
        assert s.sha(s.STUDY/name)==digest
    raw_metadata=json.loads((s.STUDY/'结果/数据说明.json').read_text(encoding='utf-8'))
    for name,digest in raw_metadata['file_sha256'].items():
        assert s.sha(s.STUDY/'结果'/name)==digest
    assert s.sha(s.OUT/'dataset.npz')==manifest['dataset_sha256']
    assert s.sha(s.STUDY/'结果/数据说明.json')==manifest['metadata_sha256']
    split_sets=[set(data['hash'][data['split']==i]) for i in range(3)]
    assert all(not split_sets[i]&split_sets[j] for i in range(3) for j in range(i))
    rng=np.random.default_rng(101)
    for n in [3,7,10,15,20,30,50]:
        x=np.linspace(21,135,n)**1.2
        v=s.features(x)
        assert v.shape==(30,) and np.isfinite(v).all()
        np.testing.assert_allclose(v,s.features(rng.permutation(x)),rtol=0,atol=0)
        invariant=[s.FEATURES.index(f) for g in ['quantiles','spacing'] for f in s.GROUPS[g]]
        np.testing.assert_allclose(v[invariant],s.features(2.7*x+50)[invariant],atol=2e-14)
    paths=[s.OUT/p for p in selection['models']]
    for path in paths:
        bundle=torch.load(path,weights_only=True)
        train=data['split']==0
        xt=data['x'][train][:,bundle['columns']]
        np.testing.assert_allclose(bundle['center'],xt.mean(axis=0),atol=0,rtol=0)
        scales=xt.std(axis=0);scales=np.where(scales<1e-10,1.,scales)
        np.testing.assert_allclose(bundle['scale'],scales,atol=0,rtol=0)
        assert bundle['features']==[s.FEATURES[i] for i in bundle['columns']]
    with (s.OUT/'test_predictions.csv').open(encoding='utf-8-sig',newline='') as f:
        row=next(csv.DictReader(f))
    index=int(np.flatnonzero(data['hash']==row['hash'])[0])
    predictions=s.ensemble(paths,data['x'][index:index+1])[0]
    np.testing.assert_allclose(predictions,[float(row[m+'_predicted_mse']) for m in s.METHODS],rtol=2e-6,atol=.01)
    assert np.isfinite(predictions).all() and (predictions>=0).all()
    assert all(not any(t in name for t in ['beta','eta','gamma','估计','状态']) for name in s.FEATURES)
    fresh=json.loads((s.OUT/'fresh_evaluation.json').read_text(encoding='utf-8'))
    assert len(fresh)==5 and all(v['samples']==200 for v in fresh.values())
    from b10_fresh_validation import COHORTS, SEED
    from studies.common.sample import generate_sample
    original_hashes=set(data['hash'])
    fresh_hashes=set()
    for _,b,e,g,n in COHORTS:
        for rid in range(200):
            x=np.asarray(generate_sample(b,e,g,n,rid,seed=SEED),dtype='<f8')
            fresh_hashes.add(hashlib.sha256(x.tobytes()).hexdigest())
    assert len(fresh_hashes)==1000 and not original_hashes&fresh_hashes
    result=dict(result='passed',raw_csv_unchanged=sum(name.endswith('.csv') for name in raw_metadata['file_sha256']),
        all_original_file_hashes_checked=len(raw_metadata['file_sha256']),frozen_implementation_unchanged=True,
        split_groups_disjoint=True,feature_dimensions_checked=[3,7,10,15,20,30,50],
        feature_permutation_invariant=True,train_only_standardization=True,
        independently_reloaded_prediction_matches=True,truth_or_estimator_outputs_in_features=False,
        fresh_samples_disjoint=1000,script_sha256=s.sha(s.__file__))
    s.json_write(s.OUT/'verification.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
