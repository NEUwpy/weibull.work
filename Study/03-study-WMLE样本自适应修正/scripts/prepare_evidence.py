"""Copy selected evidence without changing originals; record byte hashes and lineage."""
from pathlib import Path
import hashlib, json, shutil, sys
import numpy as np
import pandas as pd

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path[:0] = [str(ROOT/'python'), str(STUDY/'scripts')]
from run_wmle_on_existing_cases import CASES, load_csv_samples, load_xlsx_samples
from studies.common.sample import generate_sample

def main():
    src = next((ROOT/'docs/临时任务').glob('*W2-1000-3000*'))
    records=[]
    def copy(f,dest):
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(f,dest)
        sha=hashlib.sha256(f.read_bytes()).hexdigest()
        assert sha==hashlib.sha256(dest.read_bytes()).hexdigest()
        records.append(dict(source=str(f.relative_to(ROOT)),destination=str(dest.relative_to(STUDY)),sha256=sha,bytes=f.stat().st_size))
    chosen=set()
    for c in CASES:
        chosen.add(src/c['source_path'])
    chosen.add(src/'260825给老师/估计结果表.xlsx')
    for pattern in ('*.csv','*.json','*.py','*.mjs','README.md'):
        chosen.update(src.glob(pattern))
    chosen={f for f in chosen if f.name!='gradient_curves.csv'}
    chosen.update((src/'WMLE过程图').glob('*.py'))
    chosen.update((src/'WMLE过程图').glob('*.png'))
    chosen.update((src/'四种对照方法-代码与原文/01-Python代码').glob('*.py'))
    chosen.update((src/'四种对照方法-代码与原文/02-方法原文').glob('182-088*.pdf'))
    for f in sorted(chosen):copy(f,STUDY/'evidence/source-task'/f.relative_to(src))
    work=ROOT/'docs/临时任务/工作输出'
    for sub in ['20260826-gamma500-six-figures-table','20260906-W5-parameters','20260825-n7-200-seed20260826']:
        for f in (work/sub).rglob('*'):
            if 'node_modules' in f.parts or '__pycache__' in f.parts:
                continue
            if f.is_file() and (f.suffix in ['.py','.mjs'] or f.name in ['samples.csv','other_method_estimates.csv','mdm_estimates.csv','manifest.json','samples_200.json']):
                copy(f,STUDY/'evidence/source-work'/f.relative_to(work))
    for f in ['python/base.py','python/methods/wmle.py','python/methods/j3_weights.tsv','python/methods/registry.py','python/studies/common/sample.py','python/studies/common/runner.py','python/studies/common/metrics.py','python/studies/common/experiment.py']:
        copy(ROOT/f,STUDY/'evidence/runtime-snapshot'/f)
    # The sample-only set is separate from the eight case datasets.
    inventory=[]; long=[]; old=[]
    for c in CASES:
        path=STUDY/'evidence/source-task'/c['source_path']
        samples=load_csv_samples(path) if c['source']=='top_level_csv' else load_xlsx_samples(path,c['sizes'])
        max_delta=0.
        for key,values in samples.items():
            n,sid=divmod(key,1000)
            regen=generate_sample(c['beta'],c['eta'],c['gamma'],n,sid-1,seed=c['seed_namespace'])
            max_delta=max(max_delta,float(np.max(np.abs(regen-values))))
            for i,value in enumerate(values,1):
                long.append(dict(case_id=c['case_id'],beta=c['beta'],eta=c['eta'],gamma=c['gamma'],sample_size=n,sample_id=sid,observation_index=i,value=value))
        assert max_delta<1e-8,(c['case_id'],max_delta)
        inv={**c,'sizes':','.join(map(str,c['sizes'])),'groups':len(samples),'max_regeneration_delta':max_delta,'source_path':str(path.relative_to(STUDY))}
        inventory.append(inv)
        book=path if c['source']=='xlsx' else STUDY/'evidence/source-task/260825给老师/估计结果表.xlsx'
        for sh in pd.ExcelFile(book).sheet_names:
            if '结果' not in sh:continue
            n=int(sh.split('_n')[-1]); d=pd.read_excel(book,sheet_name=sh,header=None)
            # Three MDM offsets repeat the same WMLE estimate: keep one row and verify all three.
            for sid in range(1,51):
                block=d[d[0]==sid]
                assert len(block)==3,(book,sh,sid)
                vals=block.iloc[:,10:13].apply(pd.to_numeric,errors='coerce').to_numpy(float)
                assert np.allclose(vals,vals[0],equal_nan=True), (book,sh,sid,'WMLE differs across offsets')
                b,e,g=vals[0];good=np.isfinite(vals[0]).all()
                old.append(dict(cohort='historical_display',case_id=c['case_id'],beta=c['beta'],eta=c['eta'],gamma=c['gamma'],sample_size=n,sample_id=sid,beta_hat=b,eta_hat=e,gamma_hat=g,converged=bool(good),solution_status='display_numeric_unverified' if good else 'display_missing',source_workbook=str(book.relative_to(STUDY)),source_sheet=sh,source_row=int(block.index[0]+1)))
    dest=STUDY/'results/existing_cases_v1';dest.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(inventory).to_csv(dest/'source_inventory.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(long).to_csv(dest/'samples_long.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(old).to_csv(dest/'historical_display_estimates.csv',index=False,encoding='utf-8-sig')
    (STUDY/'evidence/source_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Copied and hash-verified {len(records)} files; {len(CASES)} cases, {len(old)} original estimates; all historical samples regenerate within 1e-8.')

if __name__=='__main__':main()
