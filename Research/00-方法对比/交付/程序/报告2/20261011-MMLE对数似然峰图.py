"""将MMLE两张流程图的形状判据改为真实剖面对数似然。

复用原四组样本、β网格与六格绘图程序；数据和核验留在程序目录。
build、render、revise、verify可分别运行，all执行完整修订。
"""
from pathlib import Path
import argparse
import re

from importlib.util import spec_from_file_location, module_from_spec
import sys

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location('mmle_process_base', HERE / '20261011-MMLE三参数流程图.py')
base = module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp
from scipy.stats import weibull_min

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '.json')
QA = HERE / (STEM + '-核验.json')
REPORT = base.REPORT
REPLACEMENTS = {
    'MMLE先用样本最小值估计位置，删除这个观测，再由其余n−1个距离估计形状与尺度：':
    'MMLE用样本最小值估计位置，删除该观测后，对其余n−1个距离作二参数Weibull极大似然估计：',
    '将式（25）的位置代入式（23），删去最小观测，将均值改为n−1个保留观测的均值，得到：':
    '在式（21）中删去最小观测，固定式（25）的位置，并代入式（27）的尺度，得到以β为变量的对数似然：',
    r'''U_\beta(\beta;\gamma)
=\frac1\beta+\frac1{n-1}\sum_{i=2}^n\ln (x_{(i)}-\hat\gamma)
-\frac{\sum_{i=2}^n (x_{(i)}-\hat\gamma)^\beta\ln (x_{(i)}-\hat\gamma)}{\sum_{i=2}^n (x_{(i)}-\hat\gamma)^\beta}=0.''':
    r'''\begin{aligned}
\ell(\beta;\hat\gamma)
={}&(n-1)\ln\beta
-(n-1)\ln\!\left[\frac1{n-1}\sum_{i=2}^n(x_{(i)}-\hat\gamma)^\beta\right]\\
&+(\beta-1)\sum_{i=2}^n\ln(x_{(i)}-\hat\gamma)-(n-1).
\end{aligned}''',
    'Uβ为形状得分，γ取式（25）确定的γ̂。程序从β=1作固定点迭代，求式（26）的根得到β̂，再按式（27）计算尺度：':
    '式（26）的ℓ为保留观测的对数似然，其最高点对应β̂。程序从β=1作固定点迭代，求对数似然导数为零的点，再计算尺度：',
    '由式（26），1/β等于保留对数距离的加权均值与普通均值之差。距离更集中时，这个差较小，根对应较大β；距离更分散时，根可移向较小β。图19、20按最小值定位、形状方程定根和尺度恢复排列。左列按式（25）确定γ̂，中列由式（26）与零线的交点确定β̂；右列固定γ̂，将式（27）的β̂换为β，画出尺度计算曲线η(β)，标出的点为最终η̂。':
    '图19、20左列按式（25）确定γ̂，中列绘制式（26）的对数似然，峰顶对应β̂；右列将式（27）的β̂换为β，绘制尺度计算曲线η(β)，标出最终η̂。',
    '**图19｜第11组最小值定位后的形状根较小，恢复尺度也偏低。**':
    '**图19｜第11组的似然峰对应较小形状，恢复尺度也偏低。**',
    '这种相对离散增大了式（26）的均值之差，零点对应β=1.54，低于5/3。第10组的保留对数距离相对更集中，方程的根为3.19，处于正常范围。两组的最小值均高于真位置，式（27）使用的是缩小后的保留距离；第11组在β̂=1.54处恢复η̂=28.69，低于真尺度100。':
    '第11组更分散的保留距离使式（26）的似然在β=1.54处达到最高，低于5/3；第10组的峰顶为3.19，处于正常范围。两组的最小值均高于真位置，式（27）使用的是缩小后的保留距离；第11组恢复η̂=28.69，低于真尺度100。',
    '**图20｜第5组保留距离集中，形状根偏大，恢复尺度仍偏低。**':
    '**图20｜第5组保留距离集中，似然峰对应较大形状，尺度仍偏低。**',
    '第5组集中的对数距离使式（26）的加权均值与普通均值之差较小，形状得分曲线直到β=7.69才与零线相交，超过高估界限6；第4组的交点为2.48。式（27）在β̂=7.69处给出η̂=690.49。较大β对应较大的距离幂均值，但保留距离上限仅789.60，尺度仍低于真值1000。':
    '第5组集中的保留距离使式（26）的似然峰落在β=7.69，超过高估界限6；第4组的峰顶为2.48。式（27）在β̂=7.69处给出η̂=690.49。较大β对应较大的距离幂均值，但保留距离上限仅789.60，尺度仍低于真值1000。',
    'MMLE中，保留距离的相对离散较大时可能形成β低估，过于集中时可能形成β高估；正常样本的距离特征则对应异常界限以内的方程根。':
    '最小值定位后，保留距离更分散或更集中，会使似然峰分别落在较小或较大的β上，形成两类明显异常估计。',
}


def profile(x, beta):
    """式（26），含全部常数的真实保留观测对数似然。"""
    logs = np.log(np.asarray(x)[1:] - x[0])
    q = len(logs)
    return float(q*np.log(beta) - q*(logsumexp(beta*logs)-np.log(q))
                 + (beta-1)*logs.sum() - q)


def correct(text):
    if (HERE / '20261012-方法响应直白表述-核验.json').exists():
        later = base.module('20261012-方法响应直白表述')
        prior = later.restore(text)
        if prior != text:
            return later.correct(correct(prior))
    for before, after in REPLACEMENTS.items():
        if text.count(after) == 1:
            continue
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    if (HERE / '20261012-典型形成过程表述-核验.json').exists():
        text = base.module('20261012-典型形成过程表述').correct(text)
    return text


def restore(text):
    if (HERE / '20261012-典型形成过程表述-核验.json').exists():
        text = base.module('20261012-典型形成过程表述').restore(text)
    for before, after in REPLACEMENTS.items():
        text = text.replace(after, before)
    return text


def approved_outside_hash(expected):
    if not QA.exists() or 'text' not in base.load(QA):
        return expected
    bounds = base.load(QA)['text']
    assert expected in (bounds['outside_before_sha256'], bounds['outside_after_sha256'])
    after = bounds['outside_after_sha256']
    if (HERE / '20261012-典型形成过程表述-核验.json').exists():
        after = base.module('20261012-典型形成过程表述').approved_outside_hash(after)
    return after


def build():
    if CACHE.exists():
        assert base.protected() == base.load(CACHE)['protected_sha256']
        return
    previous = base.load(base.CACHE)
    figures = {}
    for label, cases in previous['cases'].items():
        curves = {}
        for role, case in cases.items():
            obj = case['sample']
            peak = minimize_scalar(lambda b: -profile(obj['values'], b), bounds=(.05, 100),
                                   method='bounded', options={'xatol': 1e-10})
            assert peak.success and np.isclose(peak.x, obj['beta_hat'], rtol=2e-5)
            curves[role] = dict(beta=case['beta'], log_likelihood=[profile(obj['values'], b) for b in case['beta']],
                                at_return=profile(obj['values'], obj['beta_hat']), maximum_beta=float(peak.x))
        figures[label] = dict(cases=curves, ylim=[-65, -20] if label == 'MMLE_low' else [-65, -30],
                              yticks=[-60, -50, -40, -30, -20] if label == 'MMLE_low' else [-60, -50, -40, -30])
    base.write_json(CACHE, dict(figures=figures, source_cache_sha256=base.digest(base.CACHE),
                               protected_sha256=base.protected(), before_text=REPORT.read_text(encoding='utf-8'),
                               before_figures={str(p): base.digest(p) for p in base.TARGETS.values()},
                               figure_contract=dict(conclusion='原估计位于实际保留观测的似然峰；分散与集中对应形状低估和高估。',
                                                    panels=['sample minimum', 'profile log likelihood maximum', 'conditional scale'],
                                                    backend='Python/matplotlib', archetype='quantitative grid', export='PNG only',
                                                    sample_selection='Keep all four approved archived cases.', normalized=False),
                               samples_generated=0, estimates_modified=0))
    base.write_json(QA, dict(cache_sha256=base.digest(CACHE)))
    print('Saved exact profile log likelihoods for the same four archived cases.')


def render_pair(label, pairs, rows):
    if not CACHE.exists():
        build()
    shape = base.load(CACHE)['figures'][label]
    meta = base.render_pair(label, pairs, rows, shape=shape)
    meta.update(source_data=CACHE.name, process=['minimum location', 'profile likelihood maximum', 'scale recovery'])
    return meta


def render():
    cache = base.load(CACHE)
    assert base.protected() == cache['protected_sha256']
    rows = []
    pairs = base.load(base.PAIR_SOURCE)['pairs']
    figures = {label: render_pair(label, pairs, rows) for label in base.LABELS}
    record = base.load(QA)
    record.update(figures=figures, source_rows=rows, script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    prior = base.load(base.QA)
    prior.update(figures=figures, source_rows=rows, likelihood_revision=QA.name)
    base.write_json(base.QA, prior)
    base.refresh_checks()
    assert base.protected() == cache['protected_sha256']
    print('Rendered both MMLE six-panel PNGs with actual log likelihood peaks.')


def revise():
    cache, record = base.load(CACHE), base.load(QA)
    text = REPORT.read_text(encoding='utf-8')
    revised = correct(text)
    if text != revised:
        assert text == cache['before_text']
        pair = base.module('20261011-MDM近真值对照')
        record['text'] = dict(outside_before_sha256=base.text_digest(pair.block(text)[1]),
                              outside_after_sha256=base.text_digest(pair.block(revised)[1]))
        pair.write_text(REPORT, revised)
        prior = base.load(pair.QA)
        assert prior['outside_block_sha256'] == record['text']['outside_before_sha256']
        prior['outside_block_sha256'] = record['text']['outside_after_sha256']
        prior['mmle_likelihood_revision'] = dict(record=QA.name, text=record['text'])
        base.write_json(pair.QA, prior)
        base.write_json(QA, record)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    old = ('报告2的MMLE图19、20按“γ最小值定位—β形状方程定根—η尺度恢复”排列，原四组样本与估计保留。'
           '[本次脚本](交付/程序/报告2/20261011-MMLE三参数流程图.py)提供`build`、`render`、`revise`、`verify`、`all`；'
           '曲线与核验留在程序目录，仅更新两张PNG，原制图入口已调用本次流程。')
    new = ('报告2的MMLE图19、20按“γ最小值定位—β对数似然峰—η尺度恢复”排列，原四组样本与估计保留。'
           '[本次脚本](交付/程序/报告2/20261011-MMLE对数似然峰图.py)提供`build`、`render`、`revise`、`verify`、`all`；'
           '复用[六格绘图程序](交付/程序/报告2/20261011-MMLE三参数流程图.py)，原制图入口调用当前版本。'
           '式（26）与峰图采用保留观测的实际剖面对数似然；曲线与核验留在程序目录，结果仅更新两张PNG。')
    if new not in content:
        assert content.count(old) == 1
        base.module('20261011-MDM近真值对照').write_text(readme, content.replace(old, new))
    print('Updated MMLE formula 26, peak explanations and the existing README entry.')


def verify():
    cache, record = base.load(CACHE), base.load(QA)
    assert base.digest(CACHE) == record['cache_sha256']
    assert base.digest(base.CACHE) == cache['source_cache_sha256']
    assert base.protected() == cache['protected_sha256']
    checks = []
    originals = base.load(base.CACHE)['cases']
    for label, shape in cache['figures'].items():
        meta = record['figures'][label]
        assert base.digest(base.TARGETS[label]) == meta['sha256']
        assert all(meta['axes'][i] == meta['axes'][i+3] for i in range(3))
        for role, curve in shape['cases'].items():
            obj = originals[label][role]['sample']
            values = np.array(obj['values'])
            eta = np.array([base.scale(values, b) for b in curve['beta']])
            direct = [float(weibull_min.logpdf(values[1:]-values[0], b, scale=e).sum())
                      for b, e in zip(curve['beta'], eta)]
            assert np.allclose(direct, curve['log_likelihood'], rtol=1e-13, atol=1e-11)
            assert np.isclose(curve['maximum_beta'], obj['beta_hat'], rtol=2e-5)
            assert np.isclose(profile(values, obj['beta_hat']), max(curve['log_likelihood']), atol=1e-10)
            for b in (.7, obj['beta_hat'], 5., 8.):
                h = 1e-5
                derivative = (profile(values, b+h)-profile(values, b-h))/(2*h)
                assert np.isclose(derivative, (obj['n']-1)*base.score(values, b), rtol=1e-7, atol=2e-8)
            checks.append(dict(label=label, role=role, group=obj['group'], beta_hat=obj['beta_hat'],
                               maximum_beta=curve['maximum_beta'], log_likelihood=curve['at_return']))
    text = REPORT.read_text(encoding='utf-8')
    assert correct(text) == text and restore(text) == cache['before_text']
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    pair = base.module('20261011-MDM近真值对照')
    assert pair.tables(text) == pair.tables(cache['before_text'])
    record.update(validation=dict(status='passed', cases=checks, actual_density_likelihood_verified=True,
                                   original_beta_is_likelihood_maximum=True, matching_linear_axes=True,
                                   source_estimates_workbooks_frequencies_unchanged=True),
                  script_sha256=base.digest(__file__), report_sha256=base.digest(REPORT))
    base.write_json(QA, record)
    print('PASS: direct density likelihoods, four peak estimates, matched axes, source results and formula numbering.')


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
