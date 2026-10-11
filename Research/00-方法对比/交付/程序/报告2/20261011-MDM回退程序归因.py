"""复核第5组交点处理，并将报告中的高估原因明确归于程序求解流程。

只修订解释文字；原样本、参数估计、图片、工作簿与频率均保留。
apply保存本次核验，verify复核冻结准则、报告文字及原始文件哈希。
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, write_atomic

REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
QA = Path(__file__).with_suffix('.json')
REPLACEMENTS = {
    '明显异常分为阈值交点低估和右端回退高估。':
    '本批明显异常分为阈值交点低估和程序回退高估。',
    '**（2）右端回退的高估。**':
    '**（2）程序回退造成的高估。**',
    '**图4｜第5组的右端探测漏掉内部交点，回退位置随后对应形状高估。**':
    '**图4｜第5组已检出交点，但程序未采用，右端回退后得到形状高估。**',
    '第47组的梯度曲线达到δ时，程序找到内部交点。第5组的梯度先升后降，在γ≈3098.95、3248.08两处达到δ=0.20；右端探测从γ≈3298.40开始，探测点已在两交点右侧，梯度均低于阈值，程序进入回退，将γ置于最小观测附近。':
    '第47组按内部交点返回估计。第5组的高估起于程序的交点处理问题：曲线在γ≈3098.95、3248.08两处达到δ=0.20，离散扫描已检出交点，但最终选参分支未采用这一结果。该分支只根据γ=0与最小观测附近的梯度构造求根区间；24个右端探测点从γ≈3298.40开始，已越过两个交点，梯度均低于δ，程序于是回退到γ≈3301.70。',
    '交点靠近最小值时，条件拟合可得到小形状；非单调梯度的交点漏检可使程序进入回退':
    '交点靠近最小值时，条件拟合可得到小形状；第5组未采用已检出的交点，程序回退后形成高估',
    'MDM第5组来自漏交点后的回退。':
    'MDM第5组的离散扫描已发现交点，最终选参分支未采用该结果，导致右端回退和高估。',
    'MDM需完善非单调梯度的交点搜索与回退处理。':
    'MDM需将离散扫描得到的交点区间用于求根，并在回退前检查内部交点。',
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def module(stem):
    name = 'mdm_attribution_' + stem
    spec = importlib.util.spec_from_file_location(name, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def write_json(obj):
    write_atomic(QA, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def write_text(path, text):
    previous = path.read_bytes()
    data = text.encode('utf-8')
    try:
        write_atomic(path, data)
    except PermissionError:
        assert path.read_bytes() == previous, 'File changed during revision'
        path.write_bytes(data)
    assert path.read_bytes() == data


def correct(text, strict=False):
    for before, after in REPLACEMENTS.items():
        if strict:
            assert text.count(before) + text.count(after) == 1, before
        text = text.replace(before, after)
    return text


def restore(text):
    for before, after in REPLACEMENTS.items():
        text = text.replace(after, before)
    return text


def approved_outside_hash(expected):
    """接纳本次明确列出的文字更正，保留此前配对任务的原核验边界。"""
    if not QA.exists():
        return expected
    record = load(QA)
    assert expected in (record['outside_before_sha256'], record['outside_after_sha256'])
    return module('20261011-MLE近零停点表述').approved_outside_hash(record['outside_after_sha256'])


def evidence():
    import numpy as np
    pair = module('20261011-MDM近真值对照')
    helper = module('20261011-MDM图14横轴扩展')
    src, matrix, snapshot = pair.source_inputs()
    case = load(pair.CACHE)['pairs']['MDM_edge']['abnormal']
    assert case['group'] == 5 and case['n'] == 7 and case['root_solver'] == 'right_edge_fit'
    x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == 7 and s['id'] == 5))
    saved = next(r for r in matrix['results'] if r['n'] == 7 and r['id'] == 5
                 and r['method_id'] == 'mdm' and r['delta'] == .2)
    assert x.tolist() == case['values']
    assert all(saved[k] == case[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
    path = snapshot / 'methods/mdm.py'
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    run = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'run')
    references = [n for n in ast.walk(run) if isinstance(n, ast.Name)
                  and n.id == 'root_info' and isinstance(n.ctx, ast.Load)]
    assert len(references) == 1
    flag = next(n for n in run.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'legacy_grid_crossing' for t in n.targets))
    assert references[0].lineno == flag.lineno
    selection = next(n for n in run.body if isinstance(n, ast.If)
                     and any(isinstance(v, ast.Name) and v.id == 'probe_gradient_at_zero' for v in ast.walk(n.test)))
    assert not any(isinstance(n, ast.Name) and n.id == 'root_info' for n in ast.walk(selection))
    names = {'_json_float', '_build_geometric_gamma_grid', '_find_offset_crossing'}
    ns = dict(np=np)
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names],
                            type_ignores=[]), str(path), 'exec'), ns)
    gradient = helper.frozen_gradient(path, x)
    grids = []
    for steps in (60, 240):
        gs = ns['_build_geometric_gamma_grid'](x[0], steps)
        values = np.array([gradient(float(g)) for g in gs])
        root, _ = ns['_find_offset_crossing'](gs, values, .2)
        assert root is not None
        grids.append(dict(steps=steps, detected_crossing=float(root[0]), bracket=root[1]))
    probes = [dict(gamma=p['gamma'], gradient=float(gradient(p['gamma']))) for p in case['right_anchor_probes']]
    assert len(probes) == 24 and all(p['gradient'] < .2 for p in probes)
    # 最接近机器精度的差分节点有消减误差；逐点核对阈值判断。
    assert all((a['gradient'] < .2) == (b['gradient'] < .2) for a, b in zip(probes, case['right_anchor_probes']))
    probe_error = max(abs(a['gradient'] - b['gradient']) for a, b in zip(probes, case['right_anchor_probes']))
    roots = [dict(gamma=g, gradient=float(gradient(g))) for g in case['gradient_roots']]
    assert len(roots) == 2 and max(abs(p['gradient'] - .2) for p in roots) < 1e-7
    assert float(gradient(0)) < .2 and min(p['gamma'] for p in probes) > max(p['gamma'] for p in roots)
    assert case['gamma_hat'] == float(np.nextafter(x[0], 0.))
    return dict(source=str(path), source_sha256=digest(path), original_estimate=saved,
                roots=roots, discrete_scans=grids, right_probes=probes,
                probe_recheck_max_absolute_error=probe_error,
                probe_threshold_decisions_identical=True,
                gradient_at_zero=float(gradient(0)),
                root_info_usage='Recorded as legacy_grid_crossing; not used by final parameter selection.',
                root_info_flag_line=flag.lineno, selection_line=selection.lineno,
                attribution='Program selection ignores an already detected crossing and enters the right-edge fallback.')


def protected():
    pair = module('20261011-MDM近真值对照')
    result = pair.protected()
    result.update({str(p): digest(p) for p in pair.TARGETS.values()})
    result[str(pair.CACHE)] = digest(pair.CACHE)
    return result


def apply():
    old = REPORT.read_text(encoding='utf-8')
    new = correct(old, strict=True)
    if QA.exists() and new == old:
        verify()
        return
    assert new != old
    pair = module('20261011-MDM近真值对照')
    proof, unchanged = evidence(), protected()
    before_outside = text_digest(pair.block(old)[1])
    assert before_outside == load(pair.CACHE)['outside_block_sha256']
    record = dict(before_report_sha256=digest(REPORT), before_normalized_text_sha256=text_digest(old),
                  replacements=REPLACEMENTS, evidence=proof, protected_sha256=unchanged,
                  before_math=re.findall(r'\$\$.*?\$\$', old, re.S),
                  before_sample_rows=re.findall(r'^\|.*组.*$', old, re.M),
                  before_images=re.findall(r'!\[[^\]]*\]\((.*?)\)', old),
                  outside_before_sha256=before_outside,
                  outside_after_sha256=text_digest(pair.block(new)[1]),
                  samples_generated=0, source_estimates_modified=0, figures_redrawn=0)
    write_text(REPORT, new)
    assert protected() == unchanged
    record['after_report_sha256'] = digest(REPORT)
    write_json(record)
    pair_record = load(pair.QA)
    assert pair_record['outside_block_sha256'] == record['outside_before_sha256']
    pair_record.update(outside_block_sha256=record['outside_after_sha256'],
                       after_report_sha256=digest(REPORT),
                       program_attribution_revision=dict(record=QA.name,
                           outside_before_sha256=record['outside_before_sha256'],
                           outside_after_sha256=record['outside_after_sha256']))
    pair.write_json(pair.QA, pair_record)
    readme = ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    anchor = '原样本、估计、工作簿和频率保留，图4的两个交点及24个右端探测点沿用原数据。'
    note = ('第5组高估的起因已明确为程序未采用离散扫描检出的交点，随后触发右端回退；'
            '[归因复核脚本](交付/程序/报告2/20261011-MDM回退程序归因.py)与核验记录保存在程序目录。')
    if note not in content:
        assert content.count(anchor) == 1
        content = content.replace(anchor, anchor + note)
        write_text(readme, content.replace('\n', '\r\n') if b'\r\n' in readme.read_bytes() else content)
    verify()


def verify():
    record = load(QA)
    assert record['evidence'] == evidence()
    assert record['protected_sha256'] == protected()
    text = REPORT.read_text(encoding='utf-8')
    assert correct(text, strict=True) == text
    mle = module('20261011-MLE近零停点表述')
    mmle = module('20261011-MMLE三参数流程图')
    prior = mmle.restore(text) if mmle.QA.exists() else text
    prior = mle.restore(prior) if mle.QA.exists() else prior
    original = restore(prior)
    assert text_digest(original) == record['before_normalized_text_sha256']
    assert re.findall(r'\$\$.*?\$\$', prior, re.S) == record['before_math']
    assert re.findall(r'^\|.*组.*$', original, re.M) == record['before_sample_rows']
    assert re.findall(r'!\[[^\]]*\]\((.*?)\)', text) == record['before_images']
    pair = module('20261011-MDM近真值对照')
    assert pair.tables(text) == pair.tables(original)
    assert text_digest(pair.block(prior)[1]) == record['outside_after_sha256']
    record.update(script_sha256=digest(__file__), after_report_sha256=digest(REPORT),
                  validation=dict(status='passed', detected_crossing_unused_by_selection=True,
                                  frozen_criterion_reproduced=True, formulas_samples_figures_frequencies_unchanged=True,
                                  text_changes_limited_to_listed_attribution_revisions=True))
    write_json(record)
    print('PASS: discrete crossings detected but unused; program fallback attribution corrected; original results retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
