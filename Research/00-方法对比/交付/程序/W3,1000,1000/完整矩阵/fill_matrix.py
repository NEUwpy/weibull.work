"""Task 026 mother program: preserved inputs, append-only calculation, original plots.

Uses each batch's frozen sampler and runner/registry. Existing estimates are
read only; new method calls are logged per row for interrupted-run continuation.
"""
import ast
from collections import defaultdict
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

METHODS = [('mdm', .10), ('mdm', .15), ('mdm', .20),
           ('lse', None), ('lre', None), ('mle', None), ('wmle', None), ('mmle', None)]
LABELS = {'LS': 'lse', 'LRE': 'lre', 'WMLM': 'wmle', 'MLM': 'mle'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def checkpoint(message):
    target = os.environ.get('R00_CHECKPOINT_PATH')
    if target:
        with Path(target).open('a', encoding='utf-8') as handle:
            handle.write('\n' + message + '\n')

def write_json(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [plain(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value

def normalized(raw):
    row = {}
    for current, legacy in [('beta_hat', 'shape_hat'), ('eta_hat', 'scale_hat'), ('gamma_hat', 'location_hat'), ('r_squared', 'r_squared')]:
        value = raw.get(current, raw.get(legacy))
        row[current] = float(value) if value not in ('', None) else None
    row['converged'] = raw.get('converged') in (True, 'True')
    row['original_record'] = raw
    return row

def load_existing(batch, cfg):
    samples, estimates = {}, {}
    def add(n, sid, method, delta, raw):
        key = (int(n), int(sid), method, delta)
        row = normalized(raw)
        if key in estimates:
            assert row == estimates[key], ('duplicate estimate mismatch', key)
        estimates[key] = row
    if cfg['input_mode'] == 'payload':
        data = json.loads((batch / '结果/中间数据/payload.json').read_text(encoding='utf-8-sig'))
        case = next(case for case in data['cases'] if case['label'] == cfg['combination'])
        assert data['protocol']['seed_namespace'] == cfg['seed_namespace_original']
        for n, groups in case['samples'].items():
            for sid, x in enumerate(groups, 1):
                samples[int(n), sid] = x
        for n, offsets in case['results'].items():
            for offset, groups in offsets.items():
                for record in groups:
                    sid = record['sample_id']
                    add(n, sid, 'mdm', float(offset), record['MDM'])
                    for label, method in LABELS.items():
                        add(n, sid, method, None, record[label])
    elif cfg['input_mode'] == 'fresh':
        for rel in cfg['source_files']:
            data = json.loads((batch / rel).read_text(encoding='utf-8-sig'))
            assert data['seed'] == cfg['seed_namespace_original'] and data['truth'] == cfg['truth']
            for sample in data['samples']:
                samples[sample['n'], sample['id']] = sample['values']
            for row in data['results']:
                add(row['n'], row['id'], row['method_id'], row['delta'], row)
    else:
        observations = defaultdict(list)
        with (batch / '结果/中间数据/samples.csv').open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                observations[int(row['sample_size']), int(row['sample_id'])].append((int(row['observation_index']), float(row['value'])))
        samples = {key: [x for _, x in sorted(values)] for key, values in observations.items()}
        for rel in cfg['source_files']:
            if not rel.endswith('estimates.csv'):
                continue
            with (batch / rel).open(encoding='utf-8-sig', newline='') as handle:
                for row in csv.DictReader(handle):
                    method = row.get('method_id') or 'mdm'
                    offset = float(row['offset']) if method == 'mdm' else None
                    add(row['sample_size'], row['sample_id'], method, offset, row)
    expected = {(n, sid) for n in ([7, 15] if cfg['new_n30'] else [7, 15, 30]) for sid in range(1, 51)}
    assert set(samples) == expected
    assert len(estimates) == len(samples) * 7
    for (n, sid), sample in samples.items():
        assert len(sample) == n and np.all(np.diff(sample) >= 0)
    return samples, estimates

def criterion_only_function(module):
    """Use exact AST prefix of frozen MDM.run; stop before offset root/estimation.

    This generates only the original trace grid and its actual gradients. It
    does not invoke run(), solve a new location, or replace existing estimates.
    """
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8-sig'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MDM')
    run = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    prefix = []
    for node in run.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Tuple) and any(isinstance(v, ast.Name) and v.id == 'root_info' for v in t.elts) for t in node.targets):
            break
        prefix.append(copy.deepcopy(node))
    assert any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'grads' for t in n.targets) for n in prefix)
    ending = ast.parse('return [{"gamma":float(g),"gradient":float(v)} for g,v in zip(gammas,grads) if np.isfinite(v)]').body
    function = ast.FunctionDef(name='_criterion_only', args=copy.deepcopy(run.args),
                              body=prefix + ending, decorator_list=[])
    temp = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    env = dict(module.__dict__)
    exec(compile(temp, module.__file__ + ':criterion_prefix', 'exec'), env)
    return env['_criterion_only']

def plot_curves(directory, cfg, curves, replace=False):
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator
    mpl.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 8, 'axes.linewidth': .8, 'axes.unicode_minus': True})
    artifacts = []
    for n in (7, 15, 30):
        expected = list(range(1, 51))
        if any((n, sid) not in curves for sid in expected):
            # Existing figure bytes are reused; there is no reason to rerun those traces.
            continue
        for _, delta in METHODS[:3]:
            target = directory.parent.parent / '结果' / f'样本量{n}_偏移量{delta:.2f}.png'
            if target.exists() and not replace:
                artifacts.append({'path': str(target), 'sha256': sha(target), 'action': 'original_bytes_reused'})
                continue
            fig, ax = plt.subplots(figsize=(130 / 25.4, 92 / 25.4))
            for sid in expected:
                points = sorted(curves[n, sid], key=lambda p: p['gamma'])
                ax.plot([p['gamma'] for p in points], [p['gradient'] for p in points], color='black', linewidth=.48, alpha=.82, solid_capstyle='round')
            ax.axhline(delta, color='#b2182b', linewidth=.85, linestyle='-.', zorder=5)
            ax.set_xlim(*cfg['figure_contract']['x_range'])
            ax.set_ylim(*cfg['figure_contract']['y_range'])
            ax.spines['bottom'].set_position(('data', 0.))
            ax.spines['left'].set_position(('data', 0.))
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.set_xticks(np.arange(0., cfg['figure_contract']['x_range'][1] + .1, 500.))
            ax.set_yticks([-.6, -.2, .2, .6, 1.] if cfg['figure_contract']['y_range'][0] == -.6 else np.arange(-.8, 1.6001, .4))
            ax.xaxis.set_minor_locator(MultipleLocator(100))
            ax.yaxis.set_minor_locator(MultipleLocator(.1))
            ax.tick_params(which='major', direction='in', length=4.2, pad=3)
            ax.tick_params(which='minor', direction='in', length=2.4)
            ax.set_ylabel('Std gradient', labelpad=8)
            fig.text(.56, .055, 'Location parameter value adopted', ha='center', va='center')
            fig.subplots_adjust(left=.14, right=.96, bottom=.18, top=.975)
            fig.savefig(target, dpi=600, facecolor='white')
            plt.close(fig)
            artifacts.append({'path': str(target), 'sha256': sha(target), 'action': 'new_png', 'curves': 50})
    return artifacts

def main(directory):
    directory = Path(directory)
    batch = directory.parent.parent
    cfg = json.loads((directory / 'config.json').read_text(encoding='utf-8'))
    snapshot = directory.parent / '依赖快照/python'
    sys.path.insert(0, str(snapshot))
    from studies.common.sample import generate_sample
    from studies.common.runner import run_method
    from studies.common.metrics import check_status
    import methods.mdm as mdm_module
    for rel, expected in cfg['source_files'].items():
        assert sha(batch / rel) == expected, ('existing source changed', rel)
    for rel, expected in cfg['dependency_hashes'].items():
        assert sha(snapshot / rel) == expected, ('dependency changed', rel)
    samples, old = load_existing(batch, cfg)
    original_sample_count = len(samples)
    data_dir = directory / '数据'
    data_dir.mkdir(exist_ok=True)
    if cfg['new_n30']:
        newpath = data_dir / 'samples_n30.csv'
        if not newpath.exists():
            rows = []
            for sid in range(1, 51):
                x = generate_sample(*cfg['truth'], 30, sid - 1, seed=cfg['seed_namespace_n30'])
                rows += [{'sample_size': 30, 'sample_id': sid, 'repeat_id': sid - 1, 'observation_index': i, 'value': float(v)} for i, v in enumerate(x, 1)]
            # Exclusive new file: original samples are never overwritten.
            with newpath.open('x', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        grouped = defaultdict(list)
        with newpath.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                grouped[int(row['sample_id'])].append((int(row['observation_index']), float(row['value'])))
        assert set(grouped) == set(range(1, 51))
        for sid, values in grouped.items():
            samples[30, sid] = [v for _, v in sorted(values)]
            assert len(samples[30, sid]) == 30
        print(cfg['combination'], 'new n30 stored', cfg['seed_namespace_n30'], sha(newpath), flush=True)
        checkpoint(f"{cfg['combination']} n30已单独保存50组，namespace={cfg['seed_namespace_n30']}，文件={newpath}，SHA={sha(newpath)}。中断后读取此文件，不再次抽样。")
    newfile = data_dir / 'new_estimates.jsonl'
    computed = {}
    if newfile.exists():
        with newfile.open(encoding='utf-8') as handle:
            for line in handle:
                row = json.loads(line)
                key = (row['n'], row['id'], row['method_id'], row['delta'])
                assert key not in computed
                computed[key] = row
    for (n, sid), x in sorted(samples.items()):
        for method, delta in METHODS:
            key = (n, sid, method, delta)
            must_compute = method == 'mmle' or (cfg['new_n30'] and n == 30) or (cfg['replace_lre'] and method == 'lre')
            if not must_compute or key in computed:
                continue
            kwargs = {'offset': delta, 'gamma_steps': 240, 'trace': delta == .1} if method == 'mdm' else {}
            raw = run_method(method, x, variant=f'mdm-delta-{delta:.2f}' if method == 'mdm' else method, **kwargs)
            curve = None
            trace = raw.pop('trace_data', None)
            if trace:
                curve = [{'gamma': p['gamma'], 'gradient': p['gradient']} for p in trace.get('grad_gamma_curve', []) if p.get('source') == 'trace_grid' and not p.get('virtual') and np.isfinite(p['gradient'])]
            row = plain({'n': n, 'id': sid, 'delta': delta, **raw})
            if curve is not None:
                row['criterion_curve'] = plain(curve)
            with newfile.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                handle.flush()
            computed[key] = row
        if sid % 10 == 0:
            print(cfg['combination'], 'computed', n, sid, flush=True)
    matrix, reused = [], 0
    for (n, sid), x in sorted(samples.items()):
        for method, delta in METHODS:
            key = (n, sid, method, delta)
            if key in computed:
                row = normalized(computed[key])
                action = 'LRE_replaced' if cfg['replace_lre'] and method == 'lre' else 'new_estimate'
            else:
                row = copy.deepcopy(old[key])
                action = 'original_estimate_reused'
                reused += 1
            reference_min = x[1] if method == 'mmle' else x[0]
            values = [row[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')]
            status = check_status(*values, *cfg['truth'], converged=row['converged'], sample_min=reference_min) if all(v is not None for v in values) else 'failure'
            matrix.append({'n': n, 'id': sid, 'method_id': method, 'delta': delta, **row,
                           'action': action, 'sample_min_original': x[0], 'sample_min_support': reference_min, 'status': status})
    assert len(matrix) == 1200 and len(samples) == 150
    output = {'config': cfg, 'samples': [{'n': n, 'id': sid, 'values': x} for (n, sid), x in sorted(samples.items())], 'results': matrix}
    write_json(data_dir / 'matrix.json', output)
    checkpoint(f"{cfg['combination']}补算完成：matrix SHA={sha(data_dir / 'matrix.json')}；新算={len(computed)}，复用={reused}，程序SHA={sha(directory / 'fill_matrix.py')}。下一步表图。")
    curves = {(row['n'], row['id']): row['criterion_curve'] for row in computed.values() if 'criterion_curve' in row}
    diagnostic_match = None
    if cfg['replace_lre']:
        diagnostic = data_dir / 'criterion_only.jsonl'
        if diagnostic.exists():
            for line in diagnostic.read_text(encoding='utf-8').splitlines():
                row = json.loads(line)
                curves[row['n'], row['id']] = row['curve']
        function = criterion_only_function(mdm_module)
        for (n, sid), x in sorted(samples.items()):
            if (n, sid) in curves:
                continue
            curve = function(mdm_module.MDM(x), offset=.1, gamma_steps=240)
            with diagnostic.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({'n': n, 'id': sid, 'curve': curve}, ensure_ascii=False, allow_nan=False) + '\n')
            curves[n, sid] = curve
            if sid % 10 == 0:
                print(cfg['combination'], 'criterion only', n, sid, flush=True)
    # Verify the exact diagnostic prefix against one already computed real trace.
    if any('criterion_curve' in r for r in computed.values()):
        reference = next(r for r in computed.values() if 'criterion_curve' in r)
        function = criterion_only_function(mdm_module)
        curve = function(mdm_module.MDM(samples[reference['n'], reference['id']]), offset=.1, gamma_steps=240)
        diagnostic_match = sorted(curve, key=lambda p:p['gamma']) == sorted(reference['criterion_curve'], key=lambda p:p['gamma'])
        assert diagnostic_match
    figures = plot_curves(directory, cfg, curves)
    all_figures = []
    for n in (7, 15, 30):
        for _, delta in METHODS[:3]:
            target = batch / '结果' / f'样本量{n}_偏移量{delta:.2f}.png'
            assert target.exists(), target
            all_figures.append({'path': str(target), 'sha256': sha(target)})
    mmle = [r for r in matrix if r['method_id'] == 'mmle']
    lre_change = []
    if cfg['replace_lre']:
        for row in matrix:
            if row['method_id'] != 'lre':
                continue
            previous = old[row['n'], row['id'], 'lre', None]
            lre_change.append({'n':row['n'],'id':row['id'], 'old':[previous[k] for k in ('beta_hat','eta_hat','gamma_hat')],
                'new':[row[k] for k in ('beta_hat','eta_hat','gamma_hat')], 'old_converged':previous['converged'], 'new_converged':row['converged']})
        write_json(data_dir / 'lre_change.json', lre_change)
    manifest = {'combination': cfg['combination'], 'batch': cfg['batch'], 'n_values':[7,15,30],
        'samples':150, 'estimates':1200, 'new_estimates':len(computed), 'reused_estimates':reused,
        'original_sample_groups':original_sample_count, 'new_sample_groups':50 if cfg['new_n30'] else 0,
        'seed_namespace_n30':cfg['seed_namespace_n30'],
        'new_sample_sha256':sha(data_dir / 'samples_n30.csv') if cfg['new_n30'] else None,
        'source_hashes':cfg['source_files'], 'dependency_hashes':cfg['dependency_hashes'],
        'script_hashes':{p.name:sha(p) for p in directory.glob('*.py')},
        'matrix_sha256':sha(data_dir / 'matrix.json'), 'figures':all_figures,
        'mmle_support':{'reference':'second smallest retained observation x2',
            'success':sum(r['status']=='success' for r in mmle), 'failure':sum(r['status']=='failure' for r in mmle),
            'gamma_equals_original_minimum':sum(r['gamma_hat']==r['sample_min_original'] for r in mmle if r['converged']),
            'gamma_below_retained_minimum':sum(r['gamma_hat'] < r['sample_min_support'] for r in mmle if r['converged'])},
        'diagnostic_AST_prefix_matches_real_trace':diagnostic_match,
        'LRE_before_sha256':cfg['lre_before_sha256'], 'LRE_after_sha256':cfg['lre_after_sha256']}
    write_json(directory / 'manifest.json', manifest)
    checkpoint(f"{cfg['combination']}数据与九图已齐：manifest={directory / 'manifest.json'} SHA={sha(directory / 'manifest.json')}；MMLE支撑={manifest['mmle_support']}。下一步建表及交付核验。")
    namespace = cfg['seed_namespace_n30'] or str(cfg['seed_namespace_original'])
    sample_note = (f"新n30命名空间：`{namespace}`（以seed字符串传入，共用生成器按repr编码）；新样本独立保存在数据目录，已有文件不覆盖。"
                   if cfg['new_n30'] else f"三档样本全部复用，原种子命名空间为`{cfg['seed_namespace_original']}`；本轮未生成新样本。")
    (directory / 'README.md').write_text(f"# {cfg['combination']}完整矩阵\n\nn=7、15、30各50组，八方法1200条估计；既有估计复用{reused}条，新增或换版{len(computed)}条。\n\n"
        f"入口：`run_20261007.py`；配置：`config.json`；母体：`fill_matrix.py`；建表：`build_matrix.mjs`。运行Python入口后，以Node执行建表脚本（需要可用的`@oai/artifact-tool`模块）。所有方法从本批`../依赖快照/python`经runner/registry分派。\n\n"
        f"原样本及估计来源、SHA见config和manifest。{sample_note}\n\n"
        'MMLE支撑检查在本调用点传sample_min=x₂，其余方法使用x₁；共享metrics默认语义未改。失败记录保留，不补入其它求解器的解。\n\n'
        '图为原形式的MDM梯度—γ曲线，每图50组及一条δ参考线；九张PNG按(n,δ)命名。已有PNG复用原字节。诊断补图使用本批MDM实际trace或其函数AST在求解位置参数前的计算片段，不重算已有参数估计。\n\n'
        + (f"LRE口径变更：Park（2017）Proposed+Plot改回历史Bernard秩回归；前SHA `{cfg['lre_before_sha256']}`，后SHA `{cfg['lre_after_sha256']}`。本批150条LRE已重算，旧实现与旧结果源文件保留；差值记录位于数据/lre_change.json。\n" if cfg['replace_lre'] else 'LRE继续使用本批历史Bernard实现，未换版。\n'), encoding='utf-8')
    print('COMPLETE', cfg['combination'], json.dumps({k:manifest[k] for k in ('samples','estimates','new_estimates','reused_estimates','mmle_support')}, ensure_ascii=False), flush=True)
