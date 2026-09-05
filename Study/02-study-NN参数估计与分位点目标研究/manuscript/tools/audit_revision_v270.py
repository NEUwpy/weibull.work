"""Final integrity audit of the actual v2.7.0 manuscripts and evidence."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
import numpy as np

S=Path(__file__).resolve().parents[2];M=S/'manuscript';OUT=S/'artifacts/manuscript_review_v270'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def table(text,label,english=False):
    marker=r'\*\*(?:Table\s*' if english else r'\*\*(?:表\s*'
    m=re.search(marker+re.escape(label)+r'[\s　.])[^\n]*\n',text)
    assert m,('table missing',label,english)
    rest=text[m.end():].lstrip();lines=[]
    for line in rest.splitlines():
        if not line.startswith('|'):break
        lines.append(line)
    rows=[]
    for line in lines[2:]:
        # Row labels can differ in language, but every numeric data cell must agree.
        data='|'.join(line.strip('|').split('|')[1:]).replace('−','-')
        rows.append(re.findall(r'[-+]?\d+(?:\.\d+)?',data))
    assert rows,label
    return rows

def main():
    count=0;links=0
    docs=[M/'Study02论文初稿-v2.7.0.md',M/'Study02论文附录-v2.7.0.md',
          M/'submission/Study02-manuscript-v2.7.0-en.md',M/'submission/Study02-supplement-v2.7.0-en.md']
    texts=[p.read_text(encoding='utf-8') for p in docs]
    for label in ['1','2','3']:
        a,b=table(texts[0],label),table(texts[2],label,True);assert a==b,('main table differs',label,a,b);count+=sum(map(len,a))
    for label in ['A3']+[f'B{i}' for i in range(1,11)]+['C1','D1','F1','F2']:
        a,b=table(texts[1],label),table(texts[3],label,True);assert a==b,('supplement table differs',label,a,b);count+=sum(map(len,a))
    for p,t in zip(docs,texts):
        assert not re.search(r'<!-- (?:SUPPLEMENTAL|ABSTRACT_FROM|REFERENCES_FROM)',t),p
        for target in re.findall(r'\]\(([^)]+)\)',t):
            if target.startswith(('http','mailto:','#')):continue
            assert (p.parent/target.split('#')[0]).exists(),(p,target);links+=1
    for p in [docs[0],docs[2]]:
        subprocess.run([sys.executable,str(M/'tools/audit_zero_orphan.py'),str(p)],check=True,capture_output=True)
    source=S/'artifacts/manuscript_figures_v270/manifest.json';fig=json.loads(source.read_text(encoding='utf-8'))
    for field in ['source_sha256','output_sha256']:
        for rel,h in fig[field].items():assert sha(S/rel)==h,rel
    for folder in [M/'submission/figures/main',M/'submission/figures/appendix']:
        for p in folder.glob('*.svg'):
            # SVG text is retained; no untranslated Chinese label should remain.
            assert not re.search(r'[\u4e00-\u9fff]',p.read_text(encoding='utf-8')),p
    snap=S/'归档/旧稿/v2.6.0';saved=json.loads((snap/'snapshot_sha256.json').read_text(encoding='utf-8'))
    for rel,h in saved.items():assert sha(snap/rel)==h,rel
    control=S/'artifacts/submission_controls_v1';manifest=json.loads((control/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['complete_jobs']==600 and not manifest['smoke']
    for rel,h in manifest['source_sha256'].items():assert sha(S/rel)==h,rel
    for rel,h in manifest['output_sha256'].items():assert sha(control/rel)==h,rel
    summary=json.loads((control/'analysis/summary.json').read_text());assert summary['q_reproduction_all_200']
    analysis=json.loads((control/'analysis/manifest.json').read_text(encoding='utf-8'))
    for rel,h in analysis['source_sha256'].items():assert sha(S/rel)==h,rel
    old=json.loads((S/'artifacts/qp_comparison_v270/summary.json').read_text())
    for r in ['0.9','0.95','0.99']:
        for route in ['P','QP','QCP']:
            np.testing.assert_allclose(old['pooled'][r][route],summary['pooled'][r][route],rtol=1e-12)
    result={'bilingual_matching_numeric_tokens':count,'manuscript_local_links':links,
        'references_per_language':19,'orphan_references':0,'unused_references':0,
        'figure_sources':len(fig['source_sha256']),'figure_outputs':len(fig['output_sha256']),
        'original_snapshot_files':len(saved),'completed_training_trajectories':600,
        'q_reproduced_model_units':200,'q_feas_available':summary['q_feas']['available'],
        'supplementary_output_hashes':len(manifest['output_sha256']),
        'status':'PASS','script_sha256':sha(Path(__file__))}
    OUT.mkdir(exist_ok=True);(OUT/'integrity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
