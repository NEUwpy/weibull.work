"""Freeze the programs, actual input arrays, hashes and runtime without copying a virtualenv."""
import hashlib,json,platform,shutil,sys
from pathlib import Path
import numpy as np
import scipy,pandas,matplotlib,mpmath
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
sys.path.insert(0,str(REPO/'python'))
from studies.common.sample import generate_sample
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
def namespace(b):return CFG['base_seed_namespace'] if b==0 else f"{CFG['base_seed_namespace']}:research09-versions:block{b:02d}"
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    snapshot=HERE/'source_snapshot';snapshot.mkdir(exist_ok=True)
    paths=[*HERE.glob('*.py'),HERE/'config.json']
    for source in paths:shutil.copy2(source,snapshot/source.name)
    shared=['python/base.py','python/methods/registry.py','python/methods/wmle.py','python/methods/j3_weights.tsv','python/studies/common/sample.py','python/studies/common/runner.py',
            'python/studies/common/experiment.py','python/studies/common/metrics.py']
    for name in shared:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPO/name,dest)
    d=pandas.read_csv(HERE/'per_sample.csv.gz');reference=d[d.method_variant=='cw_engineering'].set_index(['n','block','repeat_id'])
    samples={}
    for n in CFG['n_values']:
        rows=[]
        for b in range(CFG['blocks']):
            for rid in range(CFG['repeats']):
                raw=generate_sample(*CFG['truth'],n,rid,seed=namespace(b))
                assert hashlib.sha256(raw.tobytes()).hexdigest()==reference.loc[(n,b,rid),'sample_sha256'];rows.append(raw)
        samples[f'n{n}']=np.array(rows)
    np.savez_compressed(HERE/'samples.npz',**samples)
    old=json.loads((HERE/'原主目录保护.json').read_text(encoding='utf-8'))
    old_base=HERE.parent/'20261005-MLE-MMLE-WMLE三方法'
    actual={str(p):digest(p) for p in old_base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert old==actual
    author=HERE/'三方法原文口径/作者wbl3.R'
    if author.exists():shutil.copy2(author,snapshot/'作者wbl3.R')
    outputs={str(p.relative_to(HERE)):digest(p) for p in HERE.rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p!=HERE/'manifest.json' and '程序复核' not in p.parts}
    manifest=dict(task_id=CFG['task_id'],runtime=dict(python=platform.python_version(),executable=sys.executable,numpy=np.__version__,
        scipy=scipy.__version__,pandas=pandas.__version__,matplotlib=matplotlib.__version__,mpmath=mpmath.__version__),
        inputs=dict(samples='samples.npz',row_index='block*100+repeat_id',samples_count=6000,new_samples=0),
        shared_sources={name:digest(REPO/name) for name in shared},outputs_sha256=outputs,
        protected_old_main_files=len(old),old_main_unchanged=True,
        certificates='mpmath.iv 40digits; all 0<d<infinity covered for each of 860 saved samples')
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=len(outputs),saved_input_samples=6000,protected_old_main_files=len(old)),ensure_ascii=False))
if __name__=='__main__':main()
