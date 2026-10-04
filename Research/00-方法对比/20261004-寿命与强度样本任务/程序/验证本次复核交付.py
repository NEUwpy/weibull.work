"""Verify saved audit, pairing, workbook cells, independent roots, and unchanged deliveries."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from 核验任务 import check_layout,read_workbook,column

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'结果/复核与LRE对比'
layout=check_layout()
audit=json.loads((OUT/'全量复算核验.json').read_text(encoding='utf-8'))
assert audit['full_fit_recalculations']==6000 and audit['legacy_lre_recalculations']==1200
assert audit['original_delivery_changes']==[]
for record in audit['records']:
    assert record['full_fit_recalculations']==750 and not record['mismatches'] and not record['summary_mismatches']
baseline=json.loads((OUT/'原始交付SHA256.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in baseline.items())
for key,file in [('legacy_source_sha256','LRE_旧版Bernard.py'),('ablation_source_sha256','LRE_新版搜索与Bernard位置.py')]:
    assert audit[key]==hashlib.sha256((ROOT/'程序'/file).read_bytes()).hexdigest()
assert (ROOT/'程序/LRE_旧版Bernard.py').read_bytes()==subprocess.check_output(['git','show',audit['legacy_git_commit']+':python/methods/lre.py'])
labels=dict(unbounded='未取得有限解',equation_residual='加权方程残差超标',boundary_pathology='MDM端点候选',
            gamma_zero='零位置边界',likelihood_suboptimal='似然优化未达最优',finite_difference_sensitivity='梯度差分敏感')
tables=json.loads((OUT/'比较表数据.json').read_text(encoding='utf-8'))
sheets=read_workbook(OUT/'LRE新旧算法对比.xlsx')
assert [s[0] for s in sheets]==[t['name'] for t in tables]
cells_checked=0
for table,(name,cells) in zip(tables,sheets):
    for i,row in enumerate(table['rows'],5):
        for j,expected in enumerate(row,1):
            if name=='异常记录' and j==5:expected=labels[expected]
            cell=f'{column(j)}{i}'
            actual=cells.get(cell)
            if expected is None:assert actual is None,(name,cell,actual)
            elif isinstance(expected,(int,float)):
                assert isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10),(name,cell,actual,expected)
            else:assert actual==expected,(name,cell,actual,expected)
            cells_checked+=1
wmle=json.loads((OUT/'WMLE失败根核查.json').read_text(encoding='utf-8'))
assert len(wmle['records'])==62 and sum(bool(r['admissible_roots']) for r in wmle['records'])==58
for r in wmle['records']:
    raw=json.loads((ROOT/'结果'/r['distribution']/'中间数据/results.json').read_text(encoding='utf-8'))
    minimum=next(s['values'][0] for s in raw['samples'] if (s['n'],s['id'])==(r['n'],r['id']))
    for root in r['admissible_roots']:
        assert 0<root['beta']<9.99 and root['eta']>0 and 0<=root['gamma']<minimum-1e-6
        assert root['squared_residual']<=1e-12 and root['direct_production_formula_squared_residual']<=1e-12
mdm=json.loads((OUT/'MDM梯度独立核查.json').read_text(encoding='utf-8'))
assert sum(r['status']=='failure' for r in mdm)==12
mle=json.loads((OUT/'MLE局部收敛核查.json').read_text(encoding='utf-8'))
assert mle['admissible_interior_example']['loglik_increase']>0.45
assert mle['small_location_step_loglik_increase']>0
report=dict(layout=layout,full_fits_verified=6000,lre_pairs=1200,original_files_unchanged=len(baseline),
            comparison_sheets=len(sheets),comparison_data_cells_checked=cells_checked,
            wmle_failures_checked=62,wmle_admissible_roots=58,mdm_pathological_candidates=12,
            mle_suboptimal_return=1,visual_sheets_reviewed=[s[0] for s in sheets])
(OUT/'交付核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
