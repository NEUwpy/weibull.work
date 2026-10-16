"""复用首轮计算入口，只为16个条件追加900次；保存为独立批次。"""
import argparse
import subprocess
from 存储路径 import ARCHIVE, batch_path
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROGRAM = Path(__file__).resolve().parent
STUDY = PROGRAM.parent
CONFIG = PROGRAM / '补齐重复数配置.json'
CFG = json.loads(CONFIG.read_text(encoding='utf-8'))
BASELINE = batch_path(CFG['baseline_run_id'])

spec = importlib.util.spec_from_file_location('study04_formal_comparison', PROGRAM / '运行正式比较.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
assert engine.CFG['methods'] == CFG['methods']
engine.CFG = CFG
engine.CONFIG_PATH = CONFIG
engine.OUT = ARCHIVE / CFG['run_id']
engine.SOURCES += [str(Path(__file__).resolve().relative_to(engine.ROOT)), str(CONFIG.relative_to(engine.ROOT))]


def prepare():
    out = engine.OUT
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'prepared.json').exists():
        saved = json.loads((out / 'prepared.json').read_text(encoding='utf-8'))
        assert saved['source_hashes'] == engine.fingerprints(), '补算准备后程序发生变化'
        return saved
    old = json.loads((BASELINE / 'prepared.json').read_text(encoding='utf-8'))
    assert all(engine.digest(engine.ROOT / p) == value for p, value in old['source_hashes'].items()), '首轮求解程序已变化，不能静默混用版本'
    historical = dict(old['historical_files'])
    for filename in ['prepared.json', 'manifest.json', 'results.csv.gz', 'summary.json', '条件汇总.csv']:
        path = BASELINE / filename
        historical[str(path.relative_to(engine.ROOT))] = engine.digest(path)
    sources = engine.fingerprints()
    for relative, value in sources.items():
        target = out / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(engine.ROOT / relative, target)
        assert engine.digest(target) == value
    grid = []
    baseline_inputs = {}
    additional = 0
    for prior in old['cells']:
        cell = dict(prior, repeats=1200, baseline_repeats=prior['repeats'])
        key = cell['key']
        original_folder = BASELINE / 'inputs' / key
        destination = out / 'inputs' / key
        destination.mkdir(parents=True, exist_ok=True)
        original_pack = original_folder / 'samples.npz'
        with np.load(original_pack, allow_pickle=False) as package:
            original = {name: package[name] for name in package.files}
        baseline_inputs[key] = dict(path=str(original_pack.relative_to(engine.ROOT)),
                                   sha256=engine.digest(original_pack), repeats=prior['repeats'])
        if prior['repeats'] == 1200:
            shutil.copyfile(original_pack, destination / 'samples.npz')
        else:
            assert prior['repeats'] == 300 and cell['beta'] in CFG['intermediate_beta']
            extra = np.array([engine.generate_sample(float(cell['beta']), 1000., 500., cell['n'], repeat,
                              seed=CFG['extension_seed_namespace']) for repeat in range(300, 1200)])
            samples = np.concatenate([original['samples'], extra], axis=0)
            assert samples[:300].tobytes() == original['samples'].tobytes()
            old_values = np.full((1200, len(engine.IDS), 3), np.nan)
            old_available = np.zeros((1200, len(engine.IDS)), dtype=bool)
            old_success = old_available.copy()
            old_values[:300] = original['old_estimates']
            old_available[:300] = original['old_available']
            old_success[:300] = original['old_success']
            np.savez_compressed(destination / 'samples.npz', samples=samples, old_estimates=old_values,
                                old_available=old_available, old_success=old_success)
            cell['source'] = 'Research05前300次 + 同规则追加900次'
            additional += len(extra)
        shutil.copyfile(original_folder / 'verified_cache.json.gz', destination / 'verified_cache.json.gz')
        metadata = json.loads((original_folder / 'manifest.json').read_text(encoding='utf-8'))
        metadata.update(cell)
        metadata['baseline_sample_pack'] = baseline_inputs[key]
        if prior['repeats'] == 300:
            metadata['extension'] = dict(seed_namespace=CFG['extension_seed_namespace'], repeat_ids=[300,1199],
                                         numeric_types='float beta/eta/gamma; int n/repeat', new_samples=900)
        metadata['sha256'] = {name: engine.digest(destination / name) for name in ['samples.npz', 'verified_cache.json.gz']}
        engine.dump(destination / 'manifest.json', metadata)
        with np.load(destination / 'samples.npz', allow_pickle=False) as package:
            assert package['samples'].shape == (1200, cell['n'])
            assert package['samples'][:prior['repeats']].tobytes() == original['samples'].tobytes()
        for start in range(0, prior['repeats'], CFG['chunk_size']):
            source = BASELINE / 'shards' / key / f'{start:04d}'
            target = out / 'shards' / key / f'{start:04d}'
            shutil.copytree(source, target, dirs_exist_ok=True)
            assert engine.task_complete(key, start), (key, start)
        grid.append(cell)
        print(f"Prepared {key}: keep {prior['repeats']}, add {1200-prior['repeats']}", flush=True)
    assert additional == CFG['additional_samples'] and sum(c['repeats'] for c in grid) == CFG['expected_samples']
    saved = dict(run_id=CFG['run_id'], cells=grid, source_hashes=sources, historical_files=historical,
                 original_result_validation=old['original_result_validation'], sample_count=CFG['expected_samples'],
                 expected_rows=CFG['expected_rows'], baseline_run_id=CFG['baseline_run_id'], baseline_inputs=baseline_inputs,
                 additional_samples=additional, prepared_at=datetime.now(timezone.utc).isoformat())
    engine.dump(out / 'prepared.json', saved)
    return saved


def annotate():
    path = engine.OUT / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['extension'] = dict(baseline_run_id=CFG['baseline_run_id'], baseline_samples=28800,
                                baseline_attempts=201600, additional_samples=14400, additional_attempts=100800,
                                repeats_per_condition=1200, original_records_unchanged=True,
                                note='reused计数仍指首轮已核验历史估计；本次另完整保留首轮201600条记录')
    engine.dump(path, manifest)


engine.prepare = prepare

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
        annotate()
    else:
        engine.finalize()
        annotate()
