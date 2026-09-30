"""A bounded beta scan using the frozen estimators and shared experiment runner."""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import sys
import time

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
sys.path.insert(0, str(HERE / '依赖快照' / 'python'))
from methods import registry
from methods.lre_park import LRE
from studies.common.experiment import run_experiment
registry.IMPLEMENTED['lre_park'] = LRE

BETAS = [2., 2.5, 3., 3.5, 4., 4.5, 5.]
NS = [7, 15]
REPEATS = 100
SEED = 2026100101
METHODS = [('mdm', {'offset': .1, 'gamma_steps': 240}), 'lse', 'lre_park', 'wmle', 'mle']

def run_cell(cell):
    beta, n, count, root = cell
    out = Path(root) / f'b{beta:g}_n{n}'
    if (out / 'manifest.json').exists():
        return beta, n, 'cached'
    start = time.perf_counter()
    run_experiment(METHODS, [(beta, 1000., 500.)], [n], count, str(out),
                   seed_namespace=SEED, code_version='Research00 frozen 20260930 estimator snapshot',
                   run_label='beta-continuation-20261001')
    return beta, n, round(time.perf_counter()-start, 2)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pilot', action='store_true')
    args = p.parse_args()
    if args.pilot:
        print(run_cell((5., 7, 1, BATCH / '结果' / '复核输出' / 'pilot')), flush=True)
        return
    root = BATCH / '结果' / '独立种子扫描'
    cells = [(b,n,REPEATS,str(root)) for b in BETAS for n in NS]
    with concurrent.futures.ProcessPoolExecutor(max_workers=7) as pool:
        for value in pool.map(run_cell, cells):
            print('cell completed:', value, flush=True)
    code = [{"path": str(x.relative_to(BATCH)), "sha256": hashlib.sha256(x.read_bytes()).hexdigest()}
            for x in sorted(HERE.rglob('*')) if x.is_file() and x.suffix in ('.py','.tsv')]
    contract = {'beta_grid':BETAS, 'eta':1000., 'gamma':500., 'n_values':NS,
                'n_repeats_per_cell':REPEATS, 'seed_namespace':SEED,
                'total_samples':len(BETAS)*len(NS)*REPEATS, 'total_fits':len(BETAS)*len(NS)*REPEATS*len(METHODS),
                'sample_pairing':'all five estimators share each sample; beta cells have independently derived deterministic seeds',
                'estimators':'frozen 20260930 versions; LRE Park; historical Nelder-Mead WMLE/MLE; no solver repair',
                'experiment_runner':'shared runner snapshot taken 20261001', 'code':code}
    (BATCH/'结果'/'独立种子扫描'/'扫描配置.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__ == '__main__':
    main()
