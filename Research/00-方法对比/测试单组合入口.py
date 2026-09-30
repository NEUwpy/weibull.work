"""Smoke-test each formerly shared generator with one real n=7 sample.

No workbook or figure is written; temporary intermediate directories are isolated.
"""
from pathlib import Path
import importlib.util
import json
import os
import sys
import tempfile

ROOT=Path(__file__).resolve().parent

def main():
    checks=[]
    for shape,location in [(3,500),(3,1000),(3,3000),(5,500),(5,3000)]:
        batch=ROOT/f'W({shape},1000,{location})'/('20260907' if shape==3 else '20260906')
        program=batch/'程序'
        for key in list(sys.modules):
            if key=='base' or key=='methods' or key.startswith('methods.') or key=='studies' or key.startswith('studies.'):
                del sys.modules[key]
        with tempfile.TemporaryDirectory(prefix='research00-single-case-') as temp:
            os.environ['MPLCONFIGDIR']=temp
            path=program/('generate_cases.py' if shape==3 else 'run_w5_cases.py')
            spec=importlib.util.spec_from_file_location('case_entry',path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert module.run_method.__module__=='studies.common.runner'
            runner_path=Path(sys.modules['studies.common.runner'].__file__).resolve()
            assert runner_path.is_relative_to(program.resolve())
            module.REPEATS=1;module.SAMPLE_SIZES=(7,);module.OFFSETS=(.1,)
            module.WORK_DIR=Path(temp)
            if shape==3:
                assert module.LOCATIONS==(float(location),)
                module.plot_curves=lambda *args:None
                result=module.run_case(module.LOCATIONS[0])
                assert (result['shape'],result['scale'],result['location'])==(shape,1000,location)
                sample=result['samples']['7'][0]
                expected=json.loads((batch/'结果/中间数据/payload.json').read_text(encoding='utf-8-sig'))
                original=next(c for c in expected['cases'] if c['location']==location)['samples']['7'][0]
            else:
                assert len(module.CASES)==1 and module.CASES[0]['gamma']==location
                samples,*_=module.generate_results(module.CASES[0])
                assert module.BETA==shape and module.ETA==1000
                sample=[r['value'] for r in samples]
                import csv
                original=[float(r['value']) for r in csv.DictReader((batch/'结果/中间数据/samples.csv').open(encoding='utf-8-sig')) if int(r['sample_size'])==7 and int(r['sample_id'])==1]
            assert sample==original,(shape,location)
            checks.append({'case':batch.parent.name,'single_case':True,'actual_generator_first_sample_matches':True,'local_runner':runner_path.relative_to(ROOT).as_posix()})
    (ROOT/'单组合入口测试.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS',len(checks),'single-case generators')

if __name__=='__main__':
    main()
