"""MMLE正常与异常对照：最小值定位、形状方程定根、尺度恢复。

build保存本次曲线；render输出两张PNG；revise同步图文；verify核对；all执行全部。
沿用已保存样本与原估计，不重新抽样，不替换估计器。
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path, setup_runtime, write_atomic
setup_runtime()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '.json')
QA = HERE / (STEM + '-核验.json')
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
PAIR_SOURCE = RESULT / '报告2/数据/20261010-配对图参照线精简核验.json'
LABELS = ('MMLE_low', 'MMLE_high_deletion')
TARGETS = {label: RESULT / '报告2' / ('配对情形_' + label + '.png') for label in LABELS}
REPLACEMENTS = {
    '图19、20对照正常与异常样本的实际保留距离及式（26）的形状得分曲线，曲线与零线的交点对应β̂。':
    '图19、20按最小值定位、形状方程定根和尺度恢复排列。左列按式（25）确定γ̂，中列由式（26）与零线的交点确定β̂；右列固定γ̂，将式（27）的β̂换为β，画出尺度计算曲线η(β)，标出的点为最终η̂。',
    '![MMLE正常与低估样本的实际保留距离和形状得分]':
    '![MMLE正常与低估样本的三参数估计流程]',
    '**图19｜第11组的保留距离相对分散，形状得分的零点落在低估范围。**':
    '**图19｜第11组最小值定位后的形状根较小，恢复尺度也偏低。**',
    '这种相对离散增大了式（26）的均值之差，零点对应β=1.54，低于5/3。第10组的保留对数距离相对更集中，方程的根为3.19，处于正常范围。':
    '这种相对离散增大了式（26）的均值之差，零点对应β=1.54，低于5/3。第10组的保留对数距离相对更集中，方程的根为3.19，处于正常范围。两组的最小值均高于真位置，式（27）使用的是缩小后的保留距离；第11组在β̂=1.54处恢复η̂=28.69，低于真尺度100。',
    '![MMLE正常与高估样本的实际保留距离和形状得分]':
    '![MMLE正常与高估样本的三参数估计流程]',
    '**图20｜第5组的保留距离集中，形状得分的零点移向较大β。**':
    '**图20｜第5组保留距离集中，形状根偏大，恢复尺度仍偏低。**',
    '第5组集中的对数距离使式（26）的加权均值与普通均值之差较小，形状得分曲线直到β=7.69才与零线相交，超过高估界限6；第4组的交点为2.48。两组都执行相同的最小值定位与保留样本拟合，最终差别来自方法实际使用的距离分散程度。':
    '第5组集中的对数距离使式（26）的加权均值与普通均值之差较小，形状得分曲线直到β=7.69才与零线相交，超过高估界限6；第4组的交点为2.48。式（27）在β̂=7.69处给出η̂=690.49。较大β对应较大的距离幂均值，但保留距离上限仅789.60，尺度仍低于真值1000。',
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def module(stem):
    name = 'mmle_process_' + stem
    spec = importlib.util.spec_from_file_location(name, HERE / (stem + '.py'))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def score(x, beta):
    logs = np.log(np.asarray(x)[1:] - x[0])
    centered = logs - logs.mean()
    weights = np.exp(beta * centered - np.max(beta * centered))
    weights /= weights.sum()
    return float(1 / beta - weights @ centered)


def scale(x, beta):
    logs = np.log(np.asarray(x)[1:] - x[0])
    return float(np.exp((logsumexp(beta * logs) - np.log(len(logs))) / beta))


def protected():
    paths = {p for p in (RESULT / '报告2').rglob('*') if p.is_file() and p not in TARGETS.values()}
    catalog = PROGRAM / '跨参数对比/13组合取数.json'
    paths.add(catalog)
    for src in load(catalog)['sources']:
        path = matrix_path(src)
        assert digest(path) == src['matrix_sha256']
        paths.add(path)
        paths.update(p for p in (RESULT / src['program']).rglob('*') if p.is_file())
    paths.add(HERE / '第一章频率.csv')
    return {str(p): digest(p) for p in sorted(paths)}


def build():
    if CACHE.exists():
        cache = load(CACHE)
        assert protected() == cache['protected_sha256']
        print('Reusing saved MMLE process curves.')
        return
    pairs = load(PAIR_SOURCE)['pairs']
    cases = {}
    for label in LABELS:
        cases[label] = {}
        for role in ('normal', 'abnormal'):
            obj = pairs[label][role]
            x = obj['values']
            beta = np.unique(np.r_[np.linspace(.2, 10, 550), obj['beta_hat'], obj['beta_true']])
            root = brentq(lambda b: score(x, b), .05, 100)
            assert np.isclose(root, obj['beta_hat'], rtol=2e-5)
            assert np.isclose(scale(x, obj['beta_hat']), obj['eta_hat'], rtol=2e-5)
            cases[label][role] = dict(sample=obj, beta=beta.tolist(),
                                     score=[score(x, b) for b in beta], eta=[scale(x, b) for b in beta],
                                     root=root, score_at_return=score(x, obj['beta_hat']),
                                     recovered_eta=scale(x, obj['beta_hat']))
    cache = dict(cases=cases, protected_sha256=protected(),
                 before_figures={str(p): digest(p) for p in TARGETS.values()},
                 before_text=REPORT.read_text(encoding='utf-8'), replacements=REPLACEMENTS,
                 figure_contract=dict(conclusion='最小值定位后的保留距离决定形状方程根和恢复尺度。',
                                      panels=['gamma minimum', 'beta score zero', 'eta power mean'],
                                      archetype='quantitative grid', backend='Python/matplotlib', export='PNG only',
                                      comparison='Same archived normal and abnormal cases; matching linear axes per column.'),
                 samples_generated=0, archived_estimates_modified=0)
    write_json(CACHE, cache)
    write_json(QA, dict(cache_sha256=digest(CACHE)))
    print('Saved four archived samples and beta/eta process curves.')


def render_pair(label, pairs, source_rows, shape=None):
    if shape is None and (HERE / '20261011-MMLE对数似然峰图.json').exists():
        return module('20261011-MMLE对数似然峰图').render_pair(label, pairs, source_rows)
    if not CACHE.exists():
        build()
    cache = load(CACHE)
    style = module('20261011-合并高估与MMLE实际流程')
    style.style()
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
    low = label == 'MMLE_low'
    for ax in axes[:, 0]:
        ax.set(xlim=(.6, 7.4), xticks=range(1, 8), xlabel=r'$i$', ylabel=r'$x_{(i)}$',
               ylim=(480, 650) if low else (2800, 4800),
               yticks=[500, 550, 600, 650] if low else [3000, 3500, 4000, 4500])
    for ax in axes[:, 1]:
        ax.set(xlim=(0, 10), xticks=[0, 2, 4, 6, 8, 10], xlabel=r'$\beta$',
               ylabel=r'$\ell(\beta;\hat\gamma)$' if shape else r'$U_\beta(\beta;\hat\gamma)$',
               ylim=shape['ylim'] if shape else (-.6, .9),
               yticks=shape['yticks'] if shape else [-.6, -.3, 0, .3, .6, .9])
        if shape is None:
            ax.axhline(0, color=style.GRAY, lw=.65, ls=':')
    for ax in axes[:, 2]:
        ax.set(xlim=(0, 10), xticks=[0, 2, 4, 6, 8, 10], xlabel=r'$\beta$', ylabel=r'$\eta(\beta)$',
               ylim=(0, 125) if low else (0, 1600),
               yticks=[0, 25, 50, 75, 100, 125] if low else [0, 500, 1000, 1500])
    samples = []
    for row, role, color in ((0, 'normal', style.BLUE), (1, 'abnormal', style.BROWN)):
        case = cache['cases'][label][role]
        obj = case['sample']
        assert obj == pairs[label][role]
        x, beta = np.asarray(obj['values']), np.asarray(case['beta'])
        axes[row, 0].scatter(np.arange(2, 8), x[1:], color=color, s=15, zorder=3)
        axes[row, 0].axhline(obj['gamma_true'], color=style.GRAY, lw=.7, ls='--')
        style.star(axes[row, 0], 1, obj['gamma_hat'], color)
        axes[row, 0].set_title(obj['role'] + f'·第{obj["group"]}组', loc='left', pad=13, fontsize=9)
        curve = shape['cases'][role] if shape else None
        if curve:
            assert curve['beta'] == case['beta']
        criterion = curve['log_likelihood'] if curve else case['score']
        axes[row, 1].plot(beta, criterion, color=color, lw=1.2)
        axes[row, 1].axvline(obj['beta_true'], color=style.GRAY, lw=.7, ls='--')
        style.star(axes[row, 1], obj['beta_hat'], curve['at_return'] if curve else case['score_at_return'], color)
        axes[row, 2].plot(beta, case['eta'], color=color, lw=1.2)
        axes[row, 2].axhline(obj['eta_true'], color=style.GRAY, lw=.7, ls='--')
        style.star(axes[row, 2], obj['beta_hat'], obj['eta_hat'], color)
        for rank, value in enumerate(x, 1):
            source_rows.append(dict(figure=label, sample=obj['role'], combination=obj['combination'],
                                    n=obj['n'], group=obj['group'], panel='minimum_location', rank=rank,
                                    observation=float(value), gamma_hat=obj['gamma_hat']))
        for b, s, e in zip(beta, criterion, case['eta']):
            source_rows.append(dict(figure=label, sample=obj['role'], combination=obj['combination'],
                                    n=obj['n'], group=obj['group'], panel='shape_and_scale', beta=float(b), score=s, eta=e))
            if curve:
                source_rows[-1]['log_likelihood'] = source_rows[-1].pop('score')
        logs = np.log(x[1:] - x[0])
        samples.append(dict(role=obj['role'], group=obj['group'], combination=obj['combination'], n=obj['n'],
                            gamma=obj['gamma_hat'], beta=obj['beta_hat'], eta=obj['eta_hat'],
                            root=case['root'], score_at_return=case['score_at_return'], recovered_eta=case['recovered_eta'],
                            log_range=float(np.ptp(logs)), log_sd=float(np.std(logs, ddof=1))))
    legend = [Line2D([0], [0], marker='o', color=style.BLUE, lw=1, ms=3, label='正常'),
              Line2D([0], [0], marker='o', color=style.BROWN, lw=1, ms=3, label='异常'),
              Line2D([0], [0], marker='*', color='#555555', ls='none', ms=7, label='原估计'),
              Line2D([0], [0], color=style.GRAY, ls='--', lw=.7, label='真值')]
    meta = style.finish(fig, axes, TARGETS[label].name, legend)
    for a in meta['axes']:
        a.update(xscale='linear', yscale='linear')
    meta.update(samples=samples, process=['minimum location', 'shape root', 'scale recovery'],
                source_data=CACHE.name, actual_retained_sample_only=True)
    return meta


def render():
    cache, record = load(CACHE), load(QA)
    assert protected() == cache['protected_sha256']
    pairs = load(PAIR_SOURCE)['pairs']
    rows = []
    record['figures'] = {label: render_pair(label, pairs, rows) for label in LABELS}
    record.update(script_sha256=digest(__file__), source_rows=rows)
    write_json(QA, record)
    refresh_checks()
    assert protected() == cache['protected_sha256']
    print('Rendered two MMLE PNGs: gamma location, beta root and eta recovery.')


def refresh_checks():
    """登记两张图的显示修订；输入与旧曲线记录保留。"""
    current, cache = load(QA), load(CACHE)
    updates = {str(TARGETS[label]): meta['sha256'] for label, meta in current['figures'].items()}
    for stem in ('20261011-MDM近真值对照-核验', '20261011-MDM回退程序归因', '20261011-MLE近零停点表述',
                 '20261011-WMLE迭代残差与尺度方程-核验', '20261011-展开观测位置差-核验',
                 '20261011-合并高估与MMLE实际流程', '20261011-方法顺序统一-核验', '20261011-样本表参数顺序-核验'):
        path = HERE / (stem + '.json')
        obj = load(path)
        changes = obj.get('mmle_process_revision', {}).get('changed_protected_files', {})
        for key in ('protected_sha256', 'source_sha256'):
            for p, after in updates.items():
                if p not in obj.get(key, {}) or obj[key][p] == after:
                    continue
                assert obj[key][p] in (cache['before_figures'][p], changes.get(p, {}).get('after')), (path.name, p)
                changes[p] = dict(before=cache['before_figures'][p], after=after)
                obj[key][p] = after
        for label, meta in current['figures'].items():
            if label not in obj.get('figures', {}):
                continue
            if stem.startswith('20261011-合并'):
                obj['figures'][label] = meta
            else:
                obj['figures'][label].update(sha256=meta['sha256'])
        obj['mmle_process_revision'] = dict(obj.get('mmle_process_revision', {}),
                                          record=QA.name, source_data=CACHE.name, changed_protected_files=changes)
        write_json(path, obj)


def correct(text):
    if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists():
        later = module('20261011-MMLE对数似然峰图')
        prior = later.restore(text)
        if prior != text:
            return later.correct(correct(prior))
    for old, new in REPLACEMENTS.items():
        if text.count(new) == 1:
            continue
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def restore(text):
    if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists():
        text = module('20261011-MMLE对数似然峰图').restore(text)
    for old, new in REPLACEMENTS.items():
        text = text.replace(new, old)
    return text


def approved_outside_hash(expected):
    record = load(QA) if QA.exists() else {}
    if 'text' not in record:
        return expected
    bounds = record['text']
    assert expected in (bounds['outside_before_sha256'], bounds['outside_after_sha256'])
    after = bounds['outside_after_sha256']
    if (HERE / '20261011-MMLE对数似然峰图-核验.json').exists():
        after = module('20261011-MMLE对数似然峰图').approved_outside_hash(after)
    return after


def revise():
    pair = module('20261011-MDM近真值对照')
    text = REPORT.read_text(encoding='utf-8')
    revised = correct(text)
    if text == revised:
        return
    assert text == load(CACHE)['before_text']
    record = load(QA)
    record['text'] = dict(outside_before_sha256=text_digest(pair.block(text)[1]),
                          outside_after_sha256=text_digest(pair.block(revised)[1]),
                          before_normalized_text_sha256=text_digest(text), after_normalized_text_sha256=text_digest(revised))
    pair.write_text(REPORT, revised)
    write_json(QA, record)
    prior = load(pair.QA)
    assert prior['outside_block_sha256'] == record['text']['outside_before_sha256']
    prior['outside_block_sha256'] = record['text']['outside_after_sha256']
    prior['mmle_process_revision'].update(text=record['text'])
    pair.write_json(pair.QA, prior)
    readme = ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    note = ('报告2的MMLE图19、20按“γ最小值定位—β形状方程定根—η尺度恢复”排列，原四组样本与估计保留。'
            '[本次脚本](交付/程序/报告2/20261011-MMLE三参数流程图.py)提供`build`、`render`、`revise`、`verify`、`all`；'
            '曲线与核验留在程序目录，仅更新两张PNG，原制图入口已调用本次流程。')
    if note not in content:
        pair.write_text(readme, content.rstrip() + '\n\n' + note + '\n')
    print('Updated MMLE descriptions and captions; formulas and sample tables unchanged.')


def verify():
    cache, record = load(CACHE), load(QA)
    assert digest(CACHE) == record['cache_sha256']
    assert protected() == cache['protected_sha256']
    sources = load(PROGRAM / '跨参数对比/13组合取数.json')['sources']
    checks = []
    for label, cases in cache['cases'].items():
        meta = record['figures'][label]
        assert digest(TARGETS[label]) == meta['sha256']
        assert all(meta['axes'][i] == meta['axes'][i + 3] for i in range(3))
        for case in cases.values():
            obj = case['sample']
            src = next(s for s in sources if s['combination'] == obj['combination'])
            matrix = load(matrix_path(src))
            x = sorted(next(s['values'] for s in matrix['samples'] if s['n'] == obj['n'] and s['id'] == obj['group']))
            saved = next(r for r in matrix['results'] if r['n'] == obj['n'] and r['id'] == obj['group'] and r['method_id'] == 'mmle')
            assert x == obj['values'] and obj['gamma_hat'] == x[0]
            assert all(saved[k] == obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
            assert np.allclose([score(x, b) for b in case['beta']], case['score'], atol=1e-13)
            assert np.allclose([scale(x, b) for b in case['beta']], case['eta'], rtol=1e-13)
            assert np.all(np.diff(case['score']) < 0) and np.all(np.diff(case['eta']) > 0)
            assert abs(case['score_at_return']) < 1e-6
            assert np.isclose(case['root'], obj['beta_hat'], rtol=2e-5)
            assert np.isclose(case['recovered_eta'], obj['eta_hat'], rtol=2e-5)
            distances = np.asarray(x)[1:] - x[0]
            assert distances.min() <= obj['eta_hat'] <= distances.max()
            checks.append(dict(combination=obj['combination'], group=obj['group'], n=obj['n'],
                               original_parameters=[obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')],
                               score_at_return=case['score_at_return'], recovered_eta=case['recovered_eta'],
                               frozen_method_sha256=digest(snapshot_path(src) / 'methods/mmle.py')))
    text = REPORT.read_text(encoding='utf-8')
    assert correct(text) == text
    assert restore(text) == cache['before_text']
    prior = module('20261011-MMLE对数似然峰图').restore(text) if 'likelihood_revision' in record else text
    assert re.findall(r'\$\$.*?\$\$', prior, re.S) == re.findall(r'\$\$.*?\$\$', cache['before_text'], re.S)
    assert module('20261011-MDM近真值对照').tables(text) == module('20261011-MDM近真值对照').tables(cache['before_text'])
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    record.update(validation=dict(status='passed', checks=checks, figures=2, same_archived_results=True,
                                   formulas_tables_frequencies_unchanged=True, matched_linear_axes=True),
                  script_sha256=digest(__file__), after_report_sha256=digest(REPORT))
    write_json(QA, record)
    print('PASS: four archived estimates, shape roots, scale recovery, matching axes and unchanged source outputs.')


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
