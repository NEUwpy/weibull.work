"""Recompute all three methods (MLE/MMLE/WMLE) in a fresh directory with the frozen pipeline."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    target = args.output.resolve()
    assert not target.exists(), 'Choose a fresh directory; existing results are never overwritten.'
    program = target / '程序'
    results = target / '结果'
    data = target / '数据'
    program.mkdir(parents=True)
    results.mkdir()
    data.mkdir()
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ['.py', '.mjs', '.ps1', '.json', '.md']:
            shutil.copy2(p, program / p.name)
    shutil.copytree(HERE / 'source_snapshot', program / 'source_snapshot')
    for p in (HERE.parent / '结果').glob('*.csv'):
        shutil.copy2(p, results / p.name)
    for script, options in [('compute.py', ['--workers', str(args.workers)]),
                            ('summarize.py', []), ('export_details.py', []), ('draw.py', [])]:
        subprocess.run([sys.executable, str(program / script), *options], check=True)
    print('MLE/MMLE/WMLE all recomputed with frozen code. Output:', target)
    print('For the current paired-sheet Excel, run the new directory 程序/export_workbook.ps1.')

if __name__ == '__main__':
    main()
