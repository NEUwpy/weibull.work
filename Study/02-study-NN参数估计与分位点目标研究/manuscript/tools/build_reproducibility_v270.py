"""Build a bounded local evidence bundle after the supplementary matrix passes."""
from pathlib import Path
import json,hashlib,zipfile,platform,importlib.metadata as md

S=Path(__file__).resolve().parents[2];REPO=S.parents[1];OUT=S/'reproducibility'
ARTIFACTS=['qcp_main_analysis','qcp_cross_quantile_recovery','qcp_resolution_distribution',
 'manuscript_review_v250','qcp_sample_size_analysis','qcp_bias_variance',
 'qcp_constrained_pilot','qcp_constrained_resource','qcp_constrained_confirm',
 'qp_comparison_v270','manuscript_figures_v270','manuscript_review_v270','submission_controls_v1',
 'pq_iid_main','pq_s5b_revision/analysis','pq_s5b_revision/grid_extra',
 'pq_paper_core/analysis','pq_mechanism_closure','pq_target_matrix_pilot','pq_engineering_audit']

def main():
    summary=json.loads((S/'artifacts/submission_controls_v1/analysis/summary.json').read_text())
    assert summary['training_trajectories']==600 and summary['q_reproduction_all_200']
    OUT.mkdir(exist_ok=True)
    env={'python':platform.python_version(),'platform':platform.platform(),
         'packages':{m:md.version(m) for m in ['numpy','pandas','torch','matplotlib','pytest']},
         'note':'Current revision environment; not a reconstructed historical hardware record.'}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2)+'\n',encoding='utf-8')
    files=set()
    def add(p):
        for f in p.rglob('*') if p.is_dir() else [p]:
            if f.is_file() and '__pycache__' not in f.parts and 'reading-assets' not in f.parts and f.suffix not in ('.pyc','.zip','.html'):
                if f.name.startswith('Study02论文') and 'v2.7.0' not in f.name:continue
                files.add(f)
    for rel in ['code/study02pq','configs','protocols','manuscript']:
        add(S/rel)
    for rel in ARTIFACTS:add(S/'artifacts'/rel)
    add(S/'归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity')
    add(S/'归档/旧实验/固定加权路线/configs')
    for name in ['sample.py','__init__.py']:add(REPO/'python/studies/common'/name)
    add(REPO/'python/studies/__init__.py')
    for name in ['README.md','verify_bundle.py','environment.json']:add(OUT/name)
    for name in ['README.md','docs/v2.7.0-投稿修订与验证.md','docs/independent/submission-controls-v1-结果报告.md']:add(S/name)
    hashes={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    manifest={'scope':'local manuscript and evidence bundle; not publicly released','files':hashes}
    payload=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    archive=OUT/'Study02-v2.7.0-reproducibility.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        z.writestr('BUNDLE_MANIFEST.json',payload)
        for p in sorted(files):z.write(p,p.relative_to(REPO).as_posix())
    (OUT/'bundle-manifest.json').write_text(payload,encoding='utf-8')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for rel,h in hashes.items():assert hashlib.sha256(z.read(rel)).hexdigest()==h,rel
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT/'SHA256SUMS').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print('PASS bundle',len(files),'files;',round(archive.stat().st_size/1024**2,1),'MiB;',digest)

if __name__=='__main__':main()
