"""在统一1200次批次上追加4个n=50条件，保留原有36个条件。"""
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[key] = '1'

import argparse
import gzip
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROGRAM = Path(__file__).resolve().parent
STUDY = PROGRAM.parent
CONFIG = PROGRAM / '补齐N50配置.json'
CFG = json.loads(CONFIG.read_text(encoding='utf-8'))
BASELINE = STUDY / '结果' / CFG['baseline_run_id']


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


engine = load_module('study04_n50_engine', PROGRAM / '运行正式比较.py')
summary_engine = load_module('study04_general_summary', PROGRAM / '比较批次汇总.py')
assert engine.CFG['methods'] == CFG['methods']
engine.CFG = CFG
engine.CONFIG_PATH = CONFIG
engine.OUT = STUDY / '结果' / CFG['run_id']
baseline_prepared = json.loads((BASELINE / 'prepared.json').read_text(encoding='utf-8'))
engine.SOURCES = list(dict.fromkeys(list(baseline_prepared['source_hashes']) +
    [str(path.relative_to(engine.ROOT)) for path in [Path(__file__).resolve(), CONFIG, PROGRAM / '比较批次汇总.py']]))


def prepare():
    out = engine.OUT
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'prepared.json').exists():
        saved = json.loads((out / 'prepared.json').read_text(encoding='utf-8'))
        assert saved['source_hashes'] == engine.fingerprints(), '准备后计算源码发生变化'
        return saved
    old = baseline_prepared
    assert all(engine.digest(engine.ROOT / path) == value for path, value in old['source_hashes'].items()), '原批次源码已变化'
    sources = engine.fingerprints()
    for relative, value in sources.items():
        target = out / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(engine.ROOT / relative, target)
        assert engine.digest(target) == value
    historical = dict(old['historical_files'])
    for name in ['manifest.json', 'prepared.json', 'results.csv.gz', 'summary.json', '条件汇总.csv']:
        path = BASELINE / name
        historical[str(path.relative_to(engine.ROOT))] = engine.digest(path)
    grid = []
    baseline_inputs = {}
    for prior in old['cells']:
        cell = dict(prior, baseline_repeats=prior['repeats'])
        key = cell['key']
        source = BASELINE / 'inputs' / key
        target = out / 'inputs' / key
        shutil.copytree(source, target, dirs_exist_ok=True)
        baseline_inputs[key] = dict(path=str((source / 'samples.npz').relative_to(engine.ROOT)),
                                   sha256=engine.digest(source / 'samples.npz'), repeats=prior['repeats'])
        assert engine.digest(target / 'samples.npz') == baseline_inputs[key]['sha256']
        for start in range(0, cell['repeats'], CFG['chunk_size']):
            shutil.copytree(BASELINE / 'shards' / key / f'{start:04d}', out / 'shards' / key / f'{start:04d}', dirs_exist_ok=True)
            assert engine.task_complete(key, start)
        grid.append(cell)
    for beta in CFG['intermediate_beta']:
        cell = dict(key=engine.cell_key(beta, 50), beta=beta, n=50, repeats=1200,
                    baseline_repeats=0, source='新增n=50完整网格样本')
        assert cell['key'] not in {prior['key'] for prior in grid}
        samples = np.array([engine.generate_sample(float(beta), 1000., 500., 50, repeat,
                            seed=CFG['extension_seed_namespace']) for repeat in range(1200)])
        assert len({row.tobytes() for row in samples}) == 1200
        old_values = np.full((1200, len(engine.IDS), 3), np.nan)
        available = np.zeros((1200, len(engine.IDS)), dtype=bool)
        engine.write_inputs(cell, samples, old_values, available, available.copy(), {},
                            dict(seed_namespace=CFG['extension_seed_namespace'], repeat_ids=[0,1199],
                                 numeric_types='float beta/eta/gamma; int n/repeat'))
        grid.append(cell)
        print(f"Prepared {cell['key']}: add 1200 samples", flush=True)
    assert len(grid) == CFG['expected_cells'] and sum(c['repeats'] for c in grid) == CFG['expected_samples']
    saved = dict(run_id=CFG['run_id'], cells=grid, source_hashes=sources, historical_files=historical,
                 original_result_validation=old['original_result_validation'], sample_count=CFG['expected_samples'],
                 expected_rows=CFG['expected_rows'], baseline_run_id=CFG['baseline_run_id'], baseline_inputs=baseline_inputs,
                 ancestor_inputs=old.get('baseline_inputs', {}), additional_samples=CFG['additional_samples'],
                 prepared_at=datetime.now(timezone.utc).isoformat())
    engine.dump(out / 'prepared.json', saved)
    return saved


def finalize():
    summary_engine.finalize(engine)
    path = engine.OUT / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['extension'] = dict(baseline_run_id=CFG['baseline_run_id'], baseline_samples=43200,
                                baseline_attempts=302400, additional_samples=4800, additional_attempts=33600,
                                repeats_per_condition=1200, original_records_unchanged=True,
                                added_cells=[engine.cell_key(beta, 50) for beta in CFG['intermediate_beta']])
    engine.dump(path, manifest)


engine.prepare = prepare
engine.finalize = finalize

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ['prepare', 'run', 'verify']:
        action.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.run:
        engine.run()
    else:
        finalize()
