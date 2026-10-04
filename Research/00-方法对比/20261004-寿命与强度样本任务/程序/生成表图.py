"""Build each combination's unchanged-format workbook and four figures."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'


def one_case(case):
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    if not (ROOT/'结果'/case.name/f'{case.name}.xlsx').exists():
        subprocess.run([str(NODE),str(case/'本次建表.mjs')],env=env,check=True)
    subprocess.run([sys.executable,'-B',str(case/'本次绘图.py')],env=env,check=True)


if __name__=='__main__':
    cases=sorted((ROOT/'程序').glob('W(*)'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one_case,cases))
    print('COMPLETE: 8 workbooks, 24 MDM plots and 8 violin figures.',flush=True)
