"""Append the missing beta2/n15 profiles and beta2 original single cases.

Reuses every existing curve byte-for-value. Computes only missing conditional
criteria with the frozen mother. Original observations and fit records are fixed.
"""
import json
from concurrent.futures import ProcessPoolExecutor
import 计算逐法过程曲线 as base


def key(r):
    return r['source'], r['beta'], r['n'], r['sample_id'], r['method']


def main():
    path = base.DATA/'逐法过程曲线.json'
    saved = base.load(path)
    for name, expected in saved['provenance']['input_hashes'].items():
        assert base.sha(base.HERE.parent/name) == expected
    original_curves = {key(r): r for r in saved['curves']}
    samples = base.load(base.DATA/'样本.json')
    fits = base.load(base.DATA/'实际估计.json')
    audit = base.load(base.INPUT/'原案例核验.json')
    old = base.load(base.INPUT/'原案例估计.json')
    fit_index = {(r['beta'],r['n'],r['sample_id'],r['method']):r for r in fits}
    tasks = []
    for beta,n in base.CONDITIONS:
        for method in base.METHODS:
            for s in sorted((s for s in samples if s['beta']==beta and s['n']==n),key=lambda s:s['sample_id']):
                k=('paired',beta,n,s['sample_id'],method)
                if k not in original_curves:
                    tasks.append((*k,s['observations'],fit_index[beta,n,s['sample_id'],method]))
    for beta in (2,5):
        for method in base.METHODS:
            fit,s=base.original_example(old,audit,beta,method)
            k=('original',beta,7,fit['sample_id'],method)
            if k not in original_curves:
                tasks.append((*k,s['observations'],fit))
    assert len(original_curves)+len(tasks)==1010
    with ProcessPoolExecutor(max_workers=3) as pool:
        for i,r in enumerate(pool.map(base.curve,tasks,chunksize=5),1):
            saved['curves'].append(r)
            if i%25==0 or i==len(tasks):
                print(f'Additional profiles {i}/{len(tasks)}',flush=True)
    assert all(r==original_curves[key(r)] for r in saved['curves'] if key(r) in original_curves)
    extension=dict(script='程序/补齐六格过程数据.py',new_profiles=len(tasks),preserved_profiles=len(original_curves),
                                  new_samples=0,new_fits=0,conditions=[list(c) for c in base.CONDITIONS])
    path.write_text(json.dumps(saved,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    base.main()
    record_path=base.DATA/'六格补充记录.json'
    if tasks or not record_path.exists():
        record_path.write_text(json.dumps(extension,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPLETE 1010 curves; original fits and all previously saved evaluations preserved.',flush=True)


if __name__=='__main__':
    main()
