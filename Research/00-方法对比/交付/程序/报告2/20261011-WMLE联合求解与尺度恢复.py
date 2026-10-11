"""Revise report 2 WMLE around its original joint equations and scale recovery.

Keep the four current archived cases, equation zero sets, estimates and counts.
Replace the conditional T2 plots with selected-location distances and the scale
computed by the original weighted power-mean formula. No estimator is run.
"""
from pathlib import Path
import argparse
import csv
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import PROGRAM, RESULT, matrix_path, snapshot_path, setup_runtime, load_conditional_profiles, write_atomic
setup_runtime()
import numpy as np
import importlib.util

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '-数据.json')
QA = HERE / (STEM + '-核验.json')
POINTS = HERE / (STEM + '-图数据.csv')
DATA = RESULT / '报告2/数据'
NORMALS = HERE / '20261011-WMLE近真值对照样本-缓存.json'
NORMAL_GRID = HERE / '20261011-WMLE近真值对照样本-网格.npz'
SOURCE_SHA = 'ded6fa53a69852a045d2ab0e4cd2c848a908d9c372ab20aea484efb08b8536d4'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


renderer = module(HERE / '20261011-WMLE真位置样本距离.py', 'wmle_joint_scale_renderer')
renderer.RECORD, renderer.ROWS = QA, POINTS
load, digest = renderer.load, renderer.digest
profiles = load_conditional_profiles()


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def build():
    pairs_file = DATA / '20261010-配对图参照线精简核验.json'
    pairs = {label: pair for label, pair in load(pairs_file)['pairs'].items() if label in renderer.LABELS}
    for label, obj in load(NORMALS)['controls'].items():
        pairs[label]['normal'] = obj
    catalog_path = PROGRAM / '跨参数对比/13组合取数.json'
    catalog = {s['combination']: s for s in load(catalog_path)['sources']}
    flow_path = DATA / '全量流程定位.csv'
    flow = list(csv.DictReader(flow_path.open(encoding='utf-8-sig')))
    sources = {str(p): digest(p) for p in (pairs_file, NORMALS, NORMAL_GRID, catalog_path, flow_path,
                                         Path(profiles.__file__), DATA / '20261010-参照线精简WMLE网格.npz')}
    loaded = {}

    def source(combo):
        if combo not in loaded:
            entry = catalog[combo]
            path, snapshot = matrix_path(entry), snapshot_path(entry)
            assert digest(path) == entry['matrix_sha256']
            sys.path.insert(0, str(snapshot))
            weights = module(snapshot / 'methods/wmle.py', 'wmle_joint_scale_weights_' + str(len(loaded)))
            loaded[combo] = load(path), weights
            sources.update({str(p): digest(p) for p in (path, snapshot / 'methods/wmle.py', snapshot / 'methods/j3_weights.tsv')})
        return loaded[combo]

    case_checks = []
    for label, pair in pairs.items():
        for role in ('normal', 'abnormal'):
            obj = pair[role]
            matrix, weights = source(obj['combination'])
            x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == obj['n'] and s['id'] == obj['group']))
            saved = next(r for r in matrix['results'] if r['n'] == obj['n'] and r['id'] == obj['group'] and r['method_id'] == 'wmle')
            assert x.tolist() == obj['values']
            assert all(saved[k] == obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat'))
            b, g = obj['beta_hat'], obj['gamma_hat']
            d = x - g
            j1 = float(weights.get_weight_j1(len(x)))
            eta = float((np.mean(d ** b) / j1) ** (1 / b))
            t1, t2 = profiles.wmle_residuals(x, b, g, weights)
            assert t1 * t1 + t2 * t2 <= 1e-8
            assert np.isclose(eta, obj['eta_hat'], rtol=1e-12, atol=1e-10)
            case_checks.append(dict(label=label, role=role, group=obj['group'], j1=j1,
                                    t1=t1, t2=t2, residual_sum=t1*t1+t2*t2,
                                    scale_recomputed=eta, scale_error=abs(eta-obj['eta_hat']),
                                    distance_range=[float(d.min()), float(d.max())],
                                    true_distance_range=[float(x[0]-obj['gamma_true']), float(x[-1]-obj['gamma_true'])],
                                    selected_log_range=float(np.ptp(np.log(d))),
                                    true_log_range=float(np.ptp(np.log(x-obj['gamma_true'])))))
    abnormal_checks = []
    for row in flow:
        if row['method'] != 'WMLE' or row['abnormal'] != 'True':
            continue
        matrix, weights = source(row['combination'])
        n, group = int(row['n']), int(row['group'])
        x = np.sort(next(s['values'] for s in matrix['samples'] if s['n'] == n and s['id'] == group))
        t1, t2 = profiles.wmle_residuals(x, float(row['beta_hat']), float(row['gamma_hat']), weights)
        residual = t1*t1+t2*t2
        assert residual <= 1e-8, (row['combination'], n, group, residual)
        abnormal_checks.append(dict(combination=row['combination'], n=n, group=group, t1=t1, t2=t2, residual_sum=residual))
    assert len(abnormal_checks) == 84
    write_json(CACHE, dict(pairs=pairs, case_checks=case_checks, abnormal_checks=abnormal_checks,
                           source_sha256=sources, new_samples=0, new_estimates=0,
                           argument='Sample distance statistics determine the joint weighted-equation intersection; the selected pair then determines scale.',
                           terminology=dict(beta='shape', gamma='location', eta='scale',
                                            T1='left minus right of equation 21', T2='left minus right of equation 22'),
                           figure_contract=dict(backend='Python/matplotlib', export='PNG only', archetype='quantitative grid',
                                                panels='a/d sample features; b/e joint equation zeros; c/f distances at selected location and recovered scale.',
                                                matched_linear_axes=True)))
    print('Checked 4 archived joint solutions and recovered scales; all 84 anomalous WMLE returns satisfy the same equations.')
    for r in case_checks:
        print(r['label'], r['role'], r['group'], 'eta=', r['scale_recomputed'], 'residual=', r['residual_sum'])


def render(*, preserve_current=True):
    cache = load(CACHE)
    for path, sha in cache['source_sha256'].items():
        assert digest(path) == sha, path
    with np.load(NORMAL_GRID) as saved:
        grids = {k: saved[k] for k in saved.files}
    renderer.render(pair_overrides={k: p['normal'] for k, p in cache['pairs'].items()},
                    grid_overrides=grids, show_scale=True, preserve='left' if preserve_current else None)
    record = load(QA)
    record.update(cache_sha256=digest(CACHE), task_script_sha256=digest(__file__),
                  criterion='Joint minimization of T1^2+T2^2, then original weighted scale formula.',
                  conditional_T2_curve_removed=True, actual_optimizer_path_drawn=False,
                  independent_scale_checks=cache['case_checks'], all_abnormal_equations_checked=84)
    write_json(QA, record)


PRINCIPLE = r'''WMLE先根据样本量取得校准权重，用观测到候选位置的距离建立形状与位置的两条加权方程：

$$
\frac{J_2(n)}{\beta}+\frac1n\sum_i\ln d_i
=\frac{\sum_i d_i^\beta\ln d_i}{\sum_i d_i^\beta}.
\tag{21}
$$
$$
\left(\frac1n\sum_i\frac1{d_i}\right)
\frac{\sum_i d_i^\beta}{\sum_i d_i^{\beta-1}}
=J_3(n,\beta).
\tag{22}
$$

dᵢ=x₍ᵢ₎−γ为观测到候选位置的距离；J₂、J₃分别为形状与位置的校准权重，J₃随候选β更新。

两条方程共享β和γ，需要联立求解。将式（21）、（22）左侧减右侧分别记为残差T₁、T₂，程序共同调整β、γ，最小化残差平方和：

$$
(\hat\beta,\hat\gamma)=\underset{\beta,\gamma}{\arg\min}
\left[T_1(\beta,\gamma)^2+T_2(\beta,\gamma)^2\right].
\tag{23}
$$

图16、17的b、e分别画出T₁=0与T₂=0的参数组合，两条线的共同交点满足式（21）、（22）。程序按式（23）求解，以残差平方和≤1e−8接受返回值。

得到β̂、γ̂后，将它们代入尺度公式：

$$
\hat\eta=\left[\frac{\sum_i(x_{(i)}-\hat\gamma)^{\hat\beta}}{nJ_1(n)}\right]^{1/\hat\beta}.
\tag{24}
$$

J₁为尺度校准权重。图16、17的a、d按真位置γ₀展示样本距离，c、f按求得的γ̂展示距离；两列均除以尺度真值η₀，c、f中的棕色横线和星号为式（24）计算的η̂/η₀，灰线为真值1。

本批J₃权重表覆盖β=0.1—5，β>5采用端点工程近似。明显异常分为右侧交点低估和左侧交点高估。

![WMLE各类明显异常估计的发生次数](交付/结果/报告2/异常分类_WMLE_三子图.png)

**图15｜WMLE各类明显异常估计的发生次数。**

'''


def revise():
    original = renderer.REPORT.read_text(encoding='utf-8')
    before, remaining = original.split('#### 2.1.5', 1)
    section, after = remaining.split('#### 2.1.6', 1)
    if '两条方程共享β和γ，需要联立求解。' in section:
        print('WMLE prose already follows joint solution -> scale recovery.')
        return
    assert digest(renderer.REPORT) == SOURCE_SHA
    tables = re.findall(r'\| 样本 \| 位置γ̂.*?(?=\n\n)', section, re.S)
    assert len(tables) == 2
    new_section = '　[WMLE](../../src/content/algorithms/wmle.md)\n\n' + PRINCIPLE
    new_section += '**（1）右侧交点的低估。**\n\nW(5,100,500)、n=7的正常与异常样本如下：\n\n' + tables[0] + '\n\n'
    new_section += '''![WMLE正常与异常样本的联合求解及尺度恢复](交付/结果/报告2/配对情形_WMLE_low.png)

**图16｜第11组的共同交点靠近最小观测，同时给出较小的形状与尺度。**

第11组的最小观测高于真位置75.95，前四个观测集中在575.95—586.04；第3组的下端空缺为48.67。样本距离的结构不同，改变了式（21）、（22）中两组统计量的关系。

第3组两条方程的共同交点为γ=508.70、β=5.35，接近真参数。第11组的共同交点则为γ=573.51、β=1.10，位置距最小观测仅2.44。这个组合扩大了对数距离的跨度，式（21）的加权均值与普通均值之差随之改变，两式在较小形状处同时满足。

图16f中，选定位置后的距离为2.44—56.38，明显小于真位置下的75.95—129.89。将β=1.10与这些距离代入式（24），得到η=26.30；第3组同样计算得到η=86.69。明显异常由偏离真参数的共同交点及其尺度恢复形成。

**（2）左侧交点的高估。**

W(1.5,100,500)、n=7的正常与异常样本如下：

''' + tables[1] + '\n\n'
    new_section += '''![WMLE正常与异常样本的联合求解及尺度恢复](交付/结果/报告2/配对情形_WMLE_high.png)

**图17｜第9组较集中的样本，使共同交点对应较大的形状与尺度。**

第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第1组分布在522.01—678.65，跨度更大。第1组的共同交点为γ=503.91、β=1.60，接近真参数；第9组两条方程则在γ=475.49、β=5.31处共同满足。

第9组的位置向左偏移，使观测距离整体增大、对数距离的跨度缩小。式（21）的加权均值与普通均值之差减小，与较大的β相匹配；式（22）也在这个参数组合下满足。高估由两条方程共同支持的偏大形状形成。

图17f中，选定位置后的距离为76.46—184.50。按式（24）计算，η=163.08；第1组为η=100.92。共同求出的形状、位置通过同一尺度公式继续传递到η。

将全量WMLE明显异常记录的返回参数代入式（21）、（22），残差平方和均不超过1e−8。满足加权方程仍可能得到明显偏离真值的参数；不同样本改变距离统计量，使共同交点落在不同的形状与位置组合上。

'''
    old_row = '| WMLE | 使式（21）、（22）的形状与位置残差同时为零 |'
    new_row = '| WMLE | 联立式（21）、（22）求形状与位置，再由式（24）求尺度 |'
    assert after.count(old_row) == 1
    text = before + '#### 2.1.5' + new_section + '#### 2.1.6' + after.replace(old_row, new_row, 1)
    assert re.findall(r'^\|.*$', new_section, re.M) == re.findall(r'^\|.*$', section, re.M)
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    old_math, new_math = renderer.math_blocks(original), renderer.math_blocks(text)
    assert len(old_math) == len(new_math) == 30
    assert all(a == b for i, (a, b) in enumerate(zip(old_math, new_math), 1) if i not in (21, 22, 23))
    write_atomic(renderer.REPORT, text.encode('utf-8'))
    record = load(QA)
    record.update(original_math_blocks=new_math, previous_math_blocks=old_math,
                  text_revision=dict(before_sha256=SOURCE_SHA, after_sha256=digest(renderer.REPORT),
                                     section='2.1.5 WMLE and its final comparison row',
                                     equations_21_22='Original weighted equations, without residual rearrangement.',
                                     equation_23='Original joint residual minimization; replaces conditional T1 root.',
                                     equation_24='Original scale recovery, unchanged.', tables_unchanged=True))
    write_json(QA, record)
    print('WMLE text revised around original equations -> joint parameters -> original scale formula; numbering and sample tables preserved.')


def verify():
    renderer.verify()
    record, cache = load(QA), load(CACHE)
    assert digest(CACHE) == record['cache_sha256']
    for path, sha in cache['source_sha256'].items():
        assert digest(path) == sha, path
    rows = list(csv.DictReader(POINTS.open(encoding='utf-8-sig')))
    assert len(rows) == 28
    for row in rows:
        assert np.isclose(float(row['selected_distance_ratio']),
                          (float(row['observation'])-float(row['gamma_hat']))/float(row['eta_true']), rtol=0, atol=1e-15)
    for label in renderer.LABELS:
        axes = record['figures'][label]['axes']
        assert axes[0] == axes[2] == axes[3] == axes[5] and axes[1] == axes[4]
        assert record['samples'][label] == cache['pairs'][label]
    text = renderer.REPORT.read_text(encoding='utf-8')
    section = text.split('#### 2.1.5', 1)[1].split('#### 2.1.6', 1)[0]
    assert '条件形状' not in section and 'T_1[\\hat\\beta' not in section
    assert '式（23）' in section and '式（24）' in section
    print('PASS: same 4 cases, joint equation contours, 28 observed points and recovered scales; all 84 anomaly residuals checked; 30 equation numbers preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['build', 'render', 'revise', 'verify'])
    globals()[parser.parse_args().action]()
