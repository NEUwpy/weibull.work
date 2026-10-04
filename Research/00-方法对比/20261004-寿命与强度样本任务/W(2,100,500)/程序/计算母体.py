"""Shared sampler/runner/experiment with a paired-quantile input adapter.

The frozen experiment module still performs method dispatch and aggregation.
Only its input sampler and result-capture hook are adapted in this process.
"""
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np


def dump(path, value):
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        if isinstance(v, (float, np.floating)) and not math.isfinite(v):
            return None
        return v
    path.write_text(json.dumps(clean(value), ensure_ascii=False, allow_nan=False), encoding='utf-8', newline='\n')


def calculate(program, output=None):
    program = Path(program)
    config = json.loads((program / '配置.json').read_text(encoding='utf-8'))
    target = Path(output) if output else program.parent / '结果' / '中间数据'
    if (target / 'results.json').exists():
        raise SystemExit('Saved results already exist. Use --output for an independent rerun.')
    target.mkdir(parents=True, exist_ok=True)
    snapshot = program / '依赖快照' / 'python'
    sys.path.insert(0, str(snapshot))
    from studies.common.sample import generate_sample
    from studies.common.runner import run_method
    from studies.common import experiment
    beta, eta, gamma = config['truth']
    samples, results, curves = [], [], []
    current = {}

    def paired_sample(b, e, g, n, rid, seed=None):
        latent = generate_sample(1., 1., 0., n, rid, seed=seed)
        x = g + e * latent ** (1 / b)
        recovered = ((x-g)/e) ** b
        assert np.max(np.abs(recovered-latent)) < 1e-11
        current.update(n=n, id=rid+1)
        samples.append(dict(n=n, id=rid+1, values=x.tolist(), latent_E=latent.tolist()))
        return x

    def capture_method(method, sample, variant=None, **kwargs):
        result = run_method(method, sample, variant=variant, **kwargs)
        trace = result.pop('trace_data', None)
        if trace:
            points = [p for p in trace.get('grad_gamma_curve', [])
                      if not p.get('virtual', False) and math.isfinite(p['gradient'])]
            curves.append(dict(**current, points=points))
        row = dict(**current, delta=config['offset'] if method == 'mdm' else None, **result)
        results.append(row)
        if method == 'mle' and current['id'] % 10 == 0:
            print(f"{config['distribution']} n={current['n']}: {current['id']}/50", flush=True)
        return result

    experiment.generate_sample = paired_sample
    experiment.run_method = capture_method
    specs = [('mdm', dict(offset=config['offset'], gamma_steps=config['gamma_steps'], trace=True)),
             'lse', 'lre', 'wmle', 'mle']
    experiment.run_experiment(specs, [(beta, eta, gamma)], config['n'], config['groups'], str(target),
                              seed_namespace=config['seed'], code_version=config['source_commit'],
                              run_label=config['distribution'])
    with (target / 'results.csv').open(encoding='utf-8', newline='') as stream:
        statuses = {(int(r['n']), int(r['repeat_id'])+1, r['method_id']): r['status'] for r in csv.DictReader(stream)}
    for row in results:
        row['status'] = statuses[row['n'], row['id'], row['method_id']]
    assert len(samples) == 150 and len(results) == 750
    source_hashes = {p.relative_to(program).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in snapshot.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    payload = dict(**config, samples=samples, results=results, gradient_curves=curves,
                   code_sha256=source_hashes, runtime=dict(python=platform.python_version(), numpy=np.__version__))
    dump(target / 'results.json', payload)
    manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
    manifest.update(sampling='generate_sample(1,1,0,n,id-1,seed) -> E; x=gamma+eta*E**(1/beta)',
                    original_shared_sampler_unmodified=True, stored_samples=len(samples),
                    code_sha256=source_hashes, lre='Park (2017) Proposed+Plot')
    dump(target / 'manifest.json', manifest)
    print('SAVED', config['distribution'], len(results), flush=True)
