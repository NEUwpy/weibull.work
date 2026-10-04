"""Run the eight self-contained, parameter-specific task entrypoints."""
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]


def run(case):
    target = case / '结果' / '中间数据' / 'results.json'
    if target.exists():
        print('REUSE', case.name, flush=True)
        return
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    subprocess.run([sys.executable, '-B', str(case / '程序' / '本次计算.py')], env=env, check=True)


if __name__ == '__main__':
    cases = sorted(ROOT.glob('W(*)'))
    assert len(cases) == 8
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, cases))
    print('COMPLETE: 8 combinations, 1200 samples, 6000 method records.', flush=True)
