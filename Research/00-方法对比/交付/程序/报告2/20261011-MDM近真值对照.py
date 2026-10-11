"""用同一近真值正常样本对照MDM的交点低估与右端回退高估。

读取存档结果，按冻结准则计算诊断曲线；不重新抽样，不替换参数估计。
build保存配对与曲线，render输出两张PNG，revise更新对应图文，verify核对。
"""
from pathlib import Path
from collections import Counter
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path, write_atomic, setup_runtime
setup_runtime()
import matplotlib
import numpy as np

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '.json')
QA = HERE / (STEM + '-核验.json')
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
DATA = RESULT / '报告2/数据'
CATALOG = PROGRAM / '跨参数对比/13组合取数.json'
LABELS = ('MDM_low', 'MDM_edge')
TARGETS = {label: RESULT / '报告2' / ('配对情形_' + label + '.png') for label in LABELS}
START = '**（1）阈值交点的低估。**'
END = '#### 2.1.2'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(stem):
    name = 'mdm_pair_' + stem
    spec = importlib.util.spec_from_file_location(name, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def write_text(path, text):
    previous = path.read_bytes()
    data = text.encode('utf-8')
    try:
        write_atomic(path, data)
    except PermissionError:
        assert path.read_bytes() == previous, 'File changed during revision'
        path.write_bytes(data)
    assert path.read_bytes() == data


def block(text):
    a = text.index(START)
    b = text.index(END, a)
    return text[a:b], text[:a] + text[b:]


def tables(text):
    records = []
    for match in re.finditer(r'^\| 样本 \|[^\n]*\n(?:\|[^\n]*\n)+', text, re.M):
        lines = match[0].splitlines()
        cells = lambda line: [s.strip() for s in line.strip().strip('|').split('|')]
        header = cells(lines[0])
        records.extend(json.dumps(dict(zip(header, cells(line))), ensure_ascii=False, sort_keys=True)
                       for line in lines[2:])
    return dict(Counter(records))


def protected():
    paths = {p for p in (RESULT / '报告2').rglob('*') if p.is_file() and p not in TARGETS.values()}
    paths.add(CATALOG)
    for src in load(CATALOG)['sources']:
        p = matrix_path(src)
        assert digest(p) == src['matrix_sha256']
        paths.add(p)
        paths.update(p for p in (RESULT / src['program']).rglob('*') if p.is_file())
    paths.update((HERE / '第一章频率.csv', DATA / '全量流程定位.csv'))
    return {str(p): digest(p) for p in sorted(paths)}


def source_inputs():
    src = next(s for s in load(CATALOG)['sources'] if s['combination'] == 'W(2,1000,3000)')
    matrix = load(matrix_path(src))
    assert matrix['config']['truth'] == [2, 1000, 3000]
    return src, matrix, snapshot_path(src)


def sample_record(matrix, group, role, profile, gradient):
    x = sorted(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == group))
    saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == group
                 and r['method_id'] == 'mdm' and r['delta'] == .2)
    obj = dict(role=role, combination='W(2,1000,3000)', n=7, group=group,
               method='MDM δ=0.20', version='', beta_true=2., eta_true=1000., gamma_true=3000.,
               values=x, root_solver=saved['original_record']['root_solver'])
    obj.update({k: saved[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')})
    obj['abnormal'] = obj['beta_hat'] / 2 >= 3 or obj['beta_hat'] / 2 <= 1 / 3
    for name, gamma in (('at_true', 3000.), ('at_original', obj['gamma_hat'])):
        obj[name] = dict(gamma=gamma, **profile(gamma), gradient=float(gradient(gamma)))
    assert all(abs(obj['at_original'][k] - obj[k + '_hat']) < 1e-8 * (1 + abs(obj[k + '_hat']))
               for k in ('beta', 'eta'))
    return obj


def axis_contract(label, old):
    axes = copy.deepcopy(old['axes'])
    if label == 'MDM_low':
        for i in (0, 3):
            axes[i].update(xlim=[2600 / 3000, 3500 / 3000], xticks=[2700 / 3000, 3000 / 3000, 3300 / 3000],
                           ylim=[-4, 1], yticks=[-4, -3, -2, -1, 0, 1])
        for i in (1, 4):
            axes[i].update(xlim=[0, 8], xticks=[0, 2, 4, 6, 8])
    return dict(axes=axes)


def build():
    eta_helper = module('20261010-MDM条件尺度图')
    gradient_helper = module('20261011-MDM图14横轴扩展')
    archive_path = DATA / '20261010-配对图参照线精简核验.json'
    rows_path = DATA / '20261010-参照线精简图数据.csv'
    archive = load(archive_path)
    old_rows = list(csv.DictReader(rows_path.open(encoding='utf-8-sig')))
    old_etas_path = HERE / '20261010-MDM条件尺度图.csv'
    old_etas = list(csv.DictReader(old_etas_path.open(encoding='utf-8-sig')))
    wide_path = HERE / '20261011-MDM图14横轴扩展-曲线.json'
    src, matrix, snapshot = source_inputs()
    flow = list(csv.DictReader((DATA / '全量流程定位.csv').open(encoding='utf-8-sig')))
    candidates = []
    for r in flow:
        if r['combination'] != src['combination'] or int(r['n']) != 7 or r['method'] != 'MDM δ=0.20':
            continue
        errors = {p: abs(float(r[p + '_hat']) / float(r[p + '_true']) - 1) for p in ('beta', 'eta', 'gamma')}
        candidates.append(dict(group=int(r['group']), maximum_relative_error=max(errors.values()),
                               mean_squared_relative_error=sum(v * v for v in errors.values()) / 3,
                               relative_errors=errors, root_solver=r['archived_root_solver'],
                               abnormal=r['abnormal'] == 'True'))
    candidates.sort(key=lambda r: (r['maximum_relative_error'], r['mean_squared_relative_error'], r['group']))
    eligible = [r for r in candidates if not r['abnormal'] and r['root_solver'] == 'brent']
    assert len(candidates) == 50 and eligible[0]['group'] == 47 and eligible[0]['maximum_relative_error'] < .05
    objects, rows, conditional = {}, [], {}
    for group, role in ((47, '正常'), (35, '异常')):
        x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == group))
        profile = eta_helper.frozen_profile(snapshot, x.tolist())
        gradient = gradient_helper.frozen_gradient(snapshot / 'methods/mdm.py', x)
        obj = sample_record(matrix, group, role, profile, gradient)
        objects[group] = obj
        # Uniform nodes show the whole trend; geometric nodes resolve the threshold near min(X).
        gammas = set(np.linspace(0, x[0] - .001 * x[0], 640).tolist())
        gammas.update((x[0] - np.geomspace(.001 * x[0], .25 * x[0], 320)).tolist())
        gammas.update((3000., obj['gamma_hat']))
        gradient_rows = [dict(role=role, group=group, panel='gradient', gamma=g,
                              gamma_ratio=g / 3000, gradient=float(gradient(g))) for g in sorted(gammas)]
        ranks = (np.arange(1, 8) - .3) / (7 + .4)
        negln = -np.log(1 - ranks)
        betas = sorted(set(np.linspace(.1, 15, 640).tolist() + [obj['beta_hat'], 2.]))
        sigma_rows = [dict(role=role, group=group, panel='conditional_sigma', beta=b,
                           sigma_ratio=float(np.std((x - obj['gamma_hat']) / negln ** (1 / b), ddof=1) / 1000))
                      for b in betas]
        sigma_selected = next(r['sigma_ratio'] * 1000 for r in sigma_rows if r['beta'] == obj['beta_hat'])
        assert abs(sigma_selected - obj['at_original']['sigma']) < 1e-8
        eta_left = 2600
        eta_gammas = set(np.linspace(eta_left, x[0] - .001 * x[0], 480).tolist())
        eta_gammas.update((x[0] - np.geomspace(.001 * x[0], min(.25 * x[0], x[0] - eta_left), 180)).tolist())
        eta_gammas.update((3000., obj['gamma_hat']))
        eta_curve = [dict(gamma=g, **profile(g)) for g in sorted(eta_gammas)]
        objects[group]['sigma_at_true_beta_selected_gamma'] = next(r['sigma_ratio'] * 1000 for r in sigma_rows if r['beta'] == 2.)
        for label in (LABELS if group == 47 else ('MDM_low',)):
            rows.extend(dict(example=label, **r) for r in gradient_rows + sigma_rows)
            conditional.setdefault(label, {})['normal' if group == 47 else 'abnormal'] = eta_curve
    obj5 = copy.deepcopy(archive['pairs']['MDM_edge']['abnormal'])
    assert obj5['group'] == 5 and obj5['root_solver'] == 'right_edge_fit'
    saved5 = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == 5 and r['method_id'] == 'mdm' and r['delta'] == .2)
    assert all(saved5[k] == obj5[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
    assert obj5['values'] == sorted(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == 5))
    retained5 = [r for r in old_rows if r['example'] == 'MDM_edge' and r['role'] == obj5['role']]
    rows.extend(retained5)
    extra5 = [r for r in load(wide_path)['additional_rows'] if r['role'] == obj5['role']]
    rows.extend(extra5)
    conditional['MDM_edge']['abnormal'] = [{**r, 'gamma': float(r['gamma']), 'eta': float(r['eta'])}
                                         for r in old_etas if r['example'] == 'MDM_edge' and r['role'] == obj5['role']]
    assert len(obj5['gradient_roots']) == 2 and len([r for r in retained5 if r['panel'] == 'right_anchor']) == 24
    text = REPORT.read_text(encoding='utf-8')
    oldblock, outside = block(text)
    paths = [CATALOG, matrix_path(src), snapshot / 'base.py', snapshot / 'methods/mdm.py',
             archive_path, rows_path, old_etas_path, wide_path, DATA / '全量流程定位.csv']
    oldcache = load(CACHE) if CACHE.exists() else {}
    write_json(CACHE, dict(pairs={'MDM_low': dict(normal=objects[47], abnormal=objects[35]),
                                  'MDM_edge': dict(normal=objects[47], abnormal=obj5)},
                          rows=rows, conditional=conditional,
                          axes={label: axis_contract(label, archive['figures']['MDM_edge']) for label in LABELS},
                          gradient_axis={'MDM_low': None, 'MDM_edge': dict(xlim=[0, 4000], xticks=[0, 1000, 2000, 3000, 4000])},
                          source_sha256={str(p): digest(p) for p in paths},
                          protected_sha256=protected(), candidates=candidates, selected_normal=eligible[0],
                          original_group5=obj5, group5_retained_rows=retained5, group5_extra_rows=extra5,
                          before_block=oldcache.get('before_block', oldblock),
                          outside_block_sha256=hashlib.sha256(outside.encode('utf-8')).hexdigest(),
                          before_math=re.findall(r'\$\$.*?\$\$', text, re.S),
                          before_images=re.findall(r'!\[[^\]]*\]\((.*?)\)', text),
                          before_figures=oldcache.get('before_figures', {str(p): digest(p) for p in TARGETS.values()}),
                          backend='Python/matplotlib', export='PNG only',
                          figure_contract=dict(archetype='quantitative grid', size_inches=[9.6, 5.7],
                                               panels=6, same_axes_for_normal_abnormal=True,
                                               conclusion='Contrast near-true group 47 with low-intersection group 35 and unchanged high-fallback group 5.'),
                          samples_generated=0, estimates_recomputed=0))
    print('Cached groups 47/35 and 47/5; archived estimates and group5 roots/probes retained.')


def render():
    cache = load(CACHE)
    for path, sha in cache['source_sha256'].items():
        assert digest(path) == sha, path
    mother = module('20261010-MDM公式逐项对应原文')
    before = protected()
    assert before == cache['protected_sha256'], 'Protected inputs changed after build'
    report_sha = digest(REPORT)
    figures = {}
    for label in LABELS:
        temporary = HERE / (STEM + '-' + label + '-render.png')
        rows = sorted((r for r in cache['rows'] if r['example'] == label),
                      key=lambda r: (r['role'], r['panel'], float(r.get('gamma') or r.get('beta') or 0)))
        try:
            with matplotlib.rc_context():
                meta = mother.render(label, cache['pairs'][label], rows, cache['axes'][label],
                                     cache['conditional'][label], gradient_axis=cache['gradient_axis'][label],
                                     target_path=temporary)
            write_atomic(TARGETS[label], temporary.read_bytes())
        finally:
            if temporary.exists():
                temporary.unlink()
        meta.update(path=str(TARGETS[label]), sha256=digest(TARGETS[label]))
        figures[label] = meta
    assert protected() == before and digest(REPORT) == report_sha
    record = load(QA) if QA.exists() else {}
    record.update(cache_sha256=digest(CACHE), source_sha256=cache['source_sha256'],
                  protected_sha256=before, figures=figures, before_figures=cache['before_figures'],
                  script_sha256=digest(__file__), renderer_sha256=digest(mother.__file__),
                  new_samples=0, new_estimates=0)
    write_json(QA, record)
    print('Rendered two six-panel PNGs; matching linear limits and ticks within each comparison.')


def sample_row(obj):
    return (f"| {obj['role']}·第{obj['group']}组 | {obj['beta_hat']:.2f} | {obj['eta_hat']:.2f} | "
            f"{obj['gamma_hat']:.2f} | " + '，'.join(f'{x:.2f}' for x in obj['values']) + ' |')


def revised_block(cache):
    normal = sample_row(cache['pairs']['MDM_low']['normal'])
    low = sample_row(cache['pairs']['MDM_low']['abnormal'])
    high = sample_row(cache['pairs']['MDM_edge']['abnormal'])
    header = '| 样本 | 形状β̂ | 尺度η̂ | 位置γ̂ | 观测值（升序） |\n| --- | ---: | ---: | ---: | --- |'
    text = f'''**（1）阈值交点的低估。**

W(2,1000,3000)、n=7的正常与异常样本如下：

{header}
{normal}
{low}

图3对照式（5）的阈值交点及式（4）、（7）对应的形状和尺度。

![MDM正常与异常样本对照](交付/结果/报告2/配对情形_MDM_low.png)

**图3｜第35组的阈值交点接近最小观测，随后得到较小形状和尺度。**

第47组在γ=3088.73处达到δ=0.20，交点距最小观测294.69，形状和尺度接近真值。第35组有四个观测集中在样本下端，最大观测明显较远；其梯度在真位置处为−0.225，直到γ=3211.67、距最小观测3.91时才达到δ。

在这一位置，首个与最大观测距γ分别为3.91和1486.87。减小β会拉开理论分位距离，使这些观测反算的伪尺度更接近。式（4）的标准差最低点因此对应β=0.55，式（7）的伪尺度均值为260.62。与真位置处的条件估计β=1.68、η=606.71相比，靠右的阈值交点进一步压低形状和尺度，形成明显异常估计。

**（2）右端回退的高估。**

W(2,1000,3000)、n=7的正常与异常样本如下：

{header}
{normal}
{high}

图4对照式（5）的内部交点与右端回退位置，以及式（4）、（7）对应的形状和尺度。

![MDM正常与异常样本对照](交付/结果/报告2/配对情形_MDM_edge.png)

**图4｜第5组的右端探测漏掉内部交点，回退位置随后对应形状高估。**

第47组的梯度曲线达到δ时，程序找到内部交点。第5组的梯度先升后降，在γ≈3098.95、3248.08两处达到δ=0.20；右端探测从γ≈3298.40开始，探测点已在两交点右侧，梯度均低于阈值，程序进入回退，将γ置于最小观测附近。

第5组的最小观测较孤立，其余观测集中。回退位置使首个伪尺度接近零，标准差由其余伪尺度的水平和离散程度共同决定。在该位置，增大形状使其余伪尺度更集中、标准差下降，式（4）的最低点对应β=6.43，按式（6）取伪尺度均值得568.02。

'''
    return module('20261011-MDM回退程序归因').correct(text)


def outside_hash(expected):
    return module('20261011-MDM回退程序归因').approved_outside_hash(expected)


def refresh_checks(record):
    """保护记录登记已批准的两张图变动，原数据哈希仍严格核对。"""
    updates = {str(TARGETS[k]): v['sha256'] for k, v in record['figures'].items()}
    for name in ('20261011-WMLE迭代残差与尺度方程-核验.json',
                 '20261011-展开观测位置差-核验.json',
                 '20261011-合并高估与MMLE实际流程.json'):
        path = HERE / name
        obj = load(path)
        changes = obj.get('mdm_pair_revision', {}).get('changed_protected_files', {})
        for collection in ('protected_sha256', 'source_sha256'):
            for p, after in updates.items():
                if p not in obj.get(collection, {}) or obj[collection][p] == after:
                    continue
                before = obj[collection][p]
                assert before == record['before_figures'][p], (name, p)
                changes[p] = dict(before=before, after=after)
                obj[collection][p] = after
        obj['mdm_pair_revision'] = dict(record=QA.name, changed_protected_files=changes)
        write_json(path, obj)


def revise():
    cache, record = load(CACHE), load(QA)
    text = REPORT.read_text(encoding='utf-8')
    oldblock, outside = block(text)
    newblock = revised_block(cache)
    assert oldblock in (cache['before_block'], newblock), 'MDM cases changed independently'
    assert hashlib.sha256(outside.encode('utf-8')).hexdigest() == outside_hash(cache['outside_block_sha256'])
    revised = text.replace(oldblock, newblock, 1)
    assert re.findall(r'\$\$.*?\$\$', revised, re.S) == cache['before_math']
    assert block(revised)[1] == outside
    if revised != text:
        write_text(REPORT, revised)
    oldrows = re.findall(r'^\|.*组.*$', cache['before_block'], re.M)
    newrows = re.findall(r'^\|.*组.*$', newblock, re.M)
    assert len(oldrows) == len(newrows) == 4
    record.update(row_map=dict(zip(oldrows, newrows)), after_table_records=tables(revised),
                  outside_block_sha256=hashlib.sha256(outside.encode('utf-8')).hexdigest(),
                  after_report_sha256=digest(REPORT))
    write_json(QA, record)
    refresh_checks(record)
    readme = ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    note = ('报告2图3、4共用W(2,1000,3000)、n=7的正常第47组（三个参数偏差均小于5%），分别对照低估第35组和保留的右端回退第5组。'
            '[20261011-MDM近真值对照.py](交付/程序/报告2/20261011-MDM近真值对照.py)提供`build`、`render`、`revise`、`verify`及`all`；'
            '配对、曲线和核验留在程序目录，已接入`report2`。原样本、估计、工作簿和频率保留，图4的两个交点及24个右端探测点沿用原数据。\n\n')
    if '20261011-MDM近真值对照.py' not in content:
        content = content.replace('## 整理与恢复', note + '## 整理与恢复')
    content = content.replace('曲线和核验与脚本同目录，已接入`report2`入口。\n\n报告1的WMLE',
                              '曲线和核验与脚本同目录；当前图4的正常样本替换及制图入口见下文近真值对照脚本。\n\n报告1的WMLE')
    write_text(readme, content.replace('\n', '\r\n') if b'\r\n' in readme.read_bytes() else content)
    print('Revised two MDM sample tables, captions and explanations; all other report content retained.')


def updated_protection(expected):
    record = load(QA)
    result = dict(expected)
    for label, figure in record['figures'].items():
        p = str(TARGETS[label])
        if p in result:
            assert result[p] in (record['before_figures'][p], figure['sha256'])
            result[p] = figure['sha256']
    return result


def verify():
    cache, record = load(CACHE), load(QA)
    assert digest(CACHE) == record['cache_sha256']
    for collection in ('source_sha256', 'protected_sha256'):
        for path, sha in record[collection].items():
            assert digest(path) == sha, path
    src, matrix, snapshot = source_inputs()
    eta_helper = module('20261010-MDM条件尺度图')
    gradient_helper = module('20261011-MDM图14横轴扩展')
    anchors = []
    for label, pair in cache['pairs'].items():
        assert record['figures'][label]['axes'][:3] == record['figures'][label]['axes'][3:]
        assert digest(TARGETS[label]) == record['figures'][label]['sha256']
        for role, obj in pair.items():
            x = sorted(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == obj['group']))
            assert x == obj['values']
            saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == obj['group']
                         and r['method_id'] == 'mdm' and r['delta'] == .2)
            assert all(saved[k] == obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
            profile = eta_helper.frozen_profile(snapshot, x)
            actual = profile(obj['gamma_hat'])
            errors = {p: abs(actual[p] - obj[p + '_hat']) for p in ('beta', 'eta')}
            assert max(errors.values()) < 1e-8
            anchors.append(dict(example=label, role=role, group=obj['group'], absolute_errors=errors))
            if obj['root_solver'] == 'brent':
                grad = gradient_helper.frozen_gradient(snapshot / 'methods/mdm.py', np.array(x))
                assert abs(grad(obj['gamma_hat']) - .2) < 1e-7
    assert cache['pairs']['MDM_edge']['abnormal'] == cache['original_group5']
    assert all(r in cache['rows'] for r in cache['group5_retained_rows'] + cache['group5_extra_rows'])
    normal = cache['pairs']['MDM_low']['normal']
    assert normal == cache['pairs']['MDM_edge']['normal'] and normal['group'] == 47
    assert max(abs(normal[p + '_hat'] / normal[p + '_true'] - 1) for p in ('beta', 'eta', 'gamma')) < .05
    assert cache['pairs']['MDM_low']['abnormal']['beta_hat'] / 2 < 1 / 3
    assert cache['pairs']['MDM_edge']['abnormal']['beta_hat'] / 2 > 3
    text = REPORT.read_text(encoding='utf-8')
    assert block(text)[0] == revised_block(cache)
    assert hashlib.sha256(block(text)[1].encode('utf-8')).hexdigest() == record['outside_block_sha256']
    assert record['outside_block_sha256'] == outside_hash(cache['outside_block_sha256'])
    math_text = module('20261011-MMLE对数似然峰图').restore(text) if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists() else text
    assert re.findall(r'\$\$.*?\$\$', math_text, re.S) == cache['before_math']
    assert re.findall(r'!\[[^\]]*\]\((.*?)\)', text) == cache['before_images']
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    assert tables(text) == record['after_table_records']
    record.update(script_sha256=digest(__file__), validation=dict(status='passed',
                  archive_anchors=anchors, original_estimates_and_workbooks_unchanged=True,
                  frequency_unchanged=True, group5_roots_and_probes_unchanged=True,
                  sample_pairs_preserved=True, wording_matches_approved_revisions=True,
                  normal_max_relative_error=cache['selected_normal']['maximum_relative_error']))
    write_json(QA, record)
    print('PASS: near-true group47, low group35, original high group5; source results/frequencies unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['build', 'render', 'revise', 'verify', 'all'])
    action = parser.parse_args().action
    if action == 'all':
        build()
        render()
        revise()
        verify()
    else:
        globals()[action]()
