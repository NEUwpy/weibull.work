"""Regenerate eight violin grids within fixed linear windows; retain all fits.

The 3 x 3 grids compare the central estimate distributions of the same saved
samples. Python produces PNG only; no parameter estimation or MDM redraw occurs.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PARAMETERS=('beta_hat','eta_hat','gamma_hat')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(case):
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
             OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),
                    '--case',str(case)],env=env,check=True)


def run(*,verify_only=False):
    from 核验任务 import check_layout,one_case

    cases=sorted((ROOT/'程序').glob('W(*)'))
    assert len(cases)==8
    allowed={'估计分布_小提琴图.png','绘图核验.json'}
    protected={p:digest(p) for case in cases for p in (ROOT/'结果'/case.name).rglob('*')
               if p.is_file() and p.name not in allowed}
    sealed=json.loads((ROOT/'程序/封存清单.json').read_text(encoding='utf-8'))['files']
    assert all(sha==sealed[p.relative_to(ROOT).as_posix()]['sha256'] for p,sha in protected.items())
    if not verify_only:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker,cases))
    assert all(digest(p)==sha for p,sha in protected.items())
    layout=check_layout()
    assert {p.name for p in (ROOT/'结果').iterdir()}=={p.name for p in cases}
    records=[]
    windows=[]
    total_omitted=0
    ticks_by_background={}
    for case in cases:
        records.append(one_case(case,False))
        output=ROOT/'结果'/case.name
        qa=json.loads((output/'中间数据/绘图核验.json').read_text(encoding='utf-8'))
        data=json.loads((output/'中间数据/results.json').read_text(encoding='utf-8'))
        parameters={}
        for key in PARAMETERS:
            panels=[p for p in qa['violin']['records'] if p['parameter']==key]
            assert len(panels)==15
            limits=panels[0]['x_limits']
            ticks=panels[0]['x_ticks']
            assert all(p['x_limits']==limits and p['x_ticks']==ticks for p in panels)
            group=(data['truth'][1],key)
            assert group not in ticks_by_background or ticks_by_background[group]==(limits,ticks)
            ticks_by_background[group]=(limits,ticks)
            values=[v for p in panels for v in p['values']]
            omitted=sum(p['omitted_count'] for p in panels)
            total_omitted+=omitted
            parameters[key]=dict(total=len(values),omitted=omitted,limits=limits,ticks=ticks,
                                 full_minimum=min(values),full_maximum=max(values))
        windows.append(dict(distribution=case.name,parameters=parameters))
    report=dict(date='2026-10-04',layout=layout,records=records,
                axis_scales='all linear',display_rule='fixed engineering windows',
                display_windows=windows,density_source='displayed successful estimates',
                median_iqr_source='all successful estimates',density_tails_extended=False,
                all_zero_gamma_points_preserved=True,all_raw_estimate_values_preserved=True,
                unchanged_result_files=len(protected),method_refits_this_revision=0,
                programmatic_panels_checked=72,visual_panels_inspected=0,
                omitted_estimate_values=total_omitted)
    (ROOT/'程序/绘图调整核验.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('VERIFIED 8 violin grids; original data, workbooks and MDM plots unchanged.',flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--verify-only']:
        run(verify_only=True)
    elif len(sys.argv)>1:
        assert len(sys.argv)==3 and sys.argv[1]=='--case'
        from 绘图母体 import draw
        draw(Path(sys.argv[2]),violin_only=True)
    else:
        run()
