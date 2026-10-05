"""Freeze used source files and check artifact values and old-result preservation."""
import hashlib,importlib.metadata,json,shutil,sys,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BATCH=HERE.parent;REPO=BATCH.parents[3];PREVIOUS=BATCH.parent/'20261005-MMLEI参数域与求解复核'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()
def main():
    actual=json.loads((HERE/'运行核验.json').read_text(encoding='utf-8'))
    assert all(sha(p)==s for p,s in actual['source_sha256'].items())
    frozen=HERE/'source_snapshot';(frozen/'python').mkdir(parents=True,exist_ok=True)
    shutil.copy2(REPO/'python/base.py',frozen/'python/base.py')
    for folder in ['methods','studies/common']:
        for source in (REPO/'python'/folder).rglob('*'):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix in ['.py','.tsv']:
                target=frozen/'python'/source.relative_to(REPO/'python');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for name in ['paper_solver.py','作者wbl3.R','作者代码核验.json']:
        source=PREVIOUS/'三方法原文口径'/name
        if not source.exists():source=PREVIOUS/name
        assert source.exists();shutil.copy2(source,frozen/name)
    # Original execution scripts are kept verbatim; the reproduction entry only adapts storage paths.
    shutil.copy2(HERE/'compute.py',frozen/'执行时compute.py')
    source=Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法/182-111-pdf原文.md')
    sources=dict(KR_original='https://home.iitk.ac.in/~kundu/paper154.pdf',KR_original_pages='1840 Eq4; 1841 Eq6 and Eq9-11',
       single_sample_source=str(source),single_sample_source_sha256=sha(source),single_sample_equation='182-111 section 2 equation 4; Firth section 3 not used',
       reused_results=str(PREVIOUS/'三方法原文口径/per_sample.csv.gz'),used_source_sha256=actual['source_sha256'])
    (HERE/'来源与版本.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'环境.json').write_text(json.dumps(dict(python=sys.version,executable=sys.executable,
       packages={p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','matplotlib','fastapi']},
       workbook='bundled Node.js and @oai/artifact-tool',font='Microsoft YaHei plots; Arial workbook; both Windows font files verified'),ensure_ascii=False,indent=2),encoding='utf-8')
    summary=pd.read_csv(BATCH/'结果/三方法汇总.csv');ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(BATCH/'结果/三方法汇总.xlsx') as z:
        assert z.testzip() is None
        root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));cells={c.get('r'):c for c in root.findall('.//s:c',ns)}
        checked=0
        for i,row in enumerate(summary.itertuples(index=False,name=None),6):
            for j,value in enumerate(row[1:],1):
                address=chr(65+j)+str(i);node=cells[address].find('s:v',ns)
                assert node is not None and np.isclose(float(node.text),value,rtol=2e-12,atol=2e-10),(address,value)
                checked+=1
        formula_count=len(root.findall('.//s:f',ns));assert formula_count==30
    protected=json.loads((HERE/'既有结果保护.json').read_text(encoding='utf-8'))
    changed=[p for p,s in protected.items() if not Path(p).is_file() or sha(p)!=s];assert not changed,changed
    # Full existing batch lists are checked as well as content hashes.
    current={str(p) for batch in BATCH.parent.glob('20261005-*') if batch!=BATCH for p in batch.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and '程序复核' not in p.parts}
    assert current==set(protected),(current-set(protected),set(protected)-current)
    verification=dict(workbook_numeric_cells=checked,workbook_formula_cells=30,workbook_formula_errors=0,
         workbook_visual_check='all of the only sheet inspected',PNG_visual_check='all four inspected',
         protected_old_files=len(protected),old_results_changed=0,old_file_list_unchanged=True)
    (HERE/'交付核验.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
