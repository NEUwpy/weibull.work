"""Run sample groups through the shared estimator and save complete calculation records."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from studies.common.runner import run_method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('method')
    parser.add_argument('samples', type=Path, help='JSON: {"samples": [[...], ...], "truth": [...], "title": "..."}')
    parser.add_argument('--data-root', type=Path, default=Path(os.environ.get('WEIBULL_DATA_ROOT', '../weibull-data')))
    parser.add_argument('--offset', type=float)
    args = parser.parse_args()
    payload = json.loads(args.samples.read_text(encoding='utf-8-sig'))
    if not isinstance(payload.get('samples'), list) or not payload['samples']:
        parser.error('samples must be a nonempty list of sample groups')
    settings = {'offset': args.offset if args.offset is not None else 0.1} if args.method == 'mdm' else {}
    if args.offset is not None and args.method != 'mdm':
        parser.error('--offset is specific to MDM')
    records, implementation = [], None
    for index, sample in enumerate(payload['samples'], 1):
        observations = [float(value) for value in sample]
        result = run_method(args.method, observations, trace=True, **settings)
        calculation = result.get('calculation')
        if not calculation or not calculation.get('run'):
            raise ValueError(f'No complete calculation identity for group {index}')
        sources = calculation['run']['sources']
        if implementation is not None and implementation != sources:
            raise ValueError('Implementation changed within the record set')
        implementation = sources
        raw_status = (result.get('extra') or {}).get('raw_status', result['converged'])
        records.append({'id': index, 'input': {'observations': observations},
            'result': {'beta': result['beta_hat'], 'eta': result['eta_hat'], 'gamma': result['gamma_hat'],
                       'rSquared': result['r_squared'], 'converged': raw_status},
            'calculation': calculation, 'traceData': result.get('trace_data')})
    flow = json.loads(subprocess.check_output(['node', '--input-type=module', '-e',
        "import {loadMethodFlow} from './src/lib/server/method-flow.mjs'; process.stdout.write(JSON.stringify(loadMethodFlow(process.argv[1])))",
        args.method], cwd=Path(__file__).resolve().parents[1], encoding='utf-8'))
    if flow and any(not any(source['path'] == file['path'].removeprefix('python/') and source['sha256'] == file['sha256']
                           for source in implementation) for file in flow['sources']):
        raise ValueError('Flow source identity does not match the actual estimator')
    record_set = {'schemaVersion': 1, 'method': args.method, 'model': '3p',
        'title': payload.get('title', args.method.upper() + ' calculation records'),
        'settings': settings, 'truth': payload.get('truth', []),
        'implementation': {'sources': implementation}, 'flow': flow, 'records': records}
    raw = json.dumps(record_set, allow_nan=False, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    target = args.data_root.resolve() / 'calculation-records' / args.method / (digest + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('Existing calculation record has different content')
    else:
        with target.open('xb') as file:
            file.write(raw)
    print(json.dumps({'id': args.method + '-' + digest, 'records': len(records), 'path': str(target)}))


if __name__ == '__main__':
    main()
