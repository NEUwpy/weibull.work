"""Report 2 WMLE: actual joint iterations, equation intersections, scale equation.

build replays four archived samples with their frozen estimator solely to record
callbacks; official estimates remain unchanged. render reads saved diagnostics.
Source data and checks stay beside this script; only two PNGs are delivered.
"""
from pathlib import Path
from io import StringIO
import argparse
import csv
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from 共用 import PROGRAM, RESULT, ROOT, setup_runtime, matrix_path, snapshot_path, write_atomic, save_png, load_conditional_profiles
setup_runtime()
import numpy as np

STEM = Path(__file__).stem
CACHE = HERE / (STEM + '-数据.json')
QA = HERE / (STEM + '-核验.json')
ROWS = HERE / (STEM + '-图数据.csv')
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
IMAGES = RESULT / '报告2'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


base = module(HERE / '20261011-WMLE联合求解与尺度恢复.py', 'wmle_previous_joint_scale')
load, digest = base.load, base.digest
profiles = load_conditional_profiles()


def write_json(path, obj):
    write_atomic(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def protected():
    return base.renderer.protected_files()


def replay(obj, weights):
    """Wrap callbacks, leaving objective, starts, stopping and selection unchanged."""
    original, calls = weights.minimize, []

    def recorded(fun, *args, **kwargs):
        start = np.asarray(kwargs['x0'], float)
        callback = kwargs.get('callback')
        points = []

        def point(p):
            b, g = map(float, p)
            t1, t2 = profiles.wmle_residuals(obj['values'], b, g, weights)
            objective = float(fun(p))
            assert np.isclose(objective, t1*t1+t2*t2, rtol=1e-9, atol=1e-13)
            points.append(dict(iteration=len(points), beta=b, gamma=g, t1=t1, t2=t2, objective=objective))

        point(start)

        def capture(p):
            point(p)
            if callback is not None:
                return callback(p)

        kwargs['callback'] = capture
        result = original(fun, *args, **kwargs)
        point(result.x)
        calls.append(dict(start_index=len(calls), points=points, success=bool(result.success),
                          nit=int(result.nit), nfev=int(result.nfev), objective=float(result.fun)))
        return result

    weights.minimize = recorded
    try:
        estimator = weights.WMLE(obj['values'])
        returned = estimator.run(trace=True, generate_surface=False)
    finally:
        weights.minimize = original
    expected = [obj[k] for k in ('beta_hat', 'eta_hat', 'gamma_hat')]
    assert np.allclose(returned[:3], expected, rtol=1e-10, atol=1e-8), (returned, expected)
    assert len(calls) == 5 and estimator.last_solution_info['status'] == 'ok'
    assert all(len(c['points']) == c['nit'] + 1 for c in calls)
    return dict(returned=list(map(float, returned[:3])), calls=calls,
                solution_info=estimator.last_solution_info,
                selected_start=int(estimator.last_solution_info['selected_start']))


def build():
    previous = load(base.CACHE)
    for p, sha in previous['source_sha256'].items():
        assert digest(p) == sha, p
    catalog = {s['combination']: s for s in load(PROGRAM / '跨参数对比/13组合取数.json')['sources']}
    inputs = {**previous['source_sha256'], str(base.CACHE): digest(base.CACHE)}
    before = protected()
    cases = {}
    for label, pair in previous['pairs'].items():
        for role in ('normal', 'abnormal'):
            obj = pair[role]
            entry = catalog[obj['combination']]
            snapshot = snapshot_path(entry)
            sys.path.insert(0, str(snapshot))
            weights = module(snapshot / 'methods/wmle.py', 'r2_wmle_iteration_' + label + role)
            inputs.update({str(snapshot / 'base.py'): digest(snapshot / 'base.py')})
            trace = replay(obj, weights)
            j1 = float(weights.get_weight_j1(obj['n']))
            etas = np.unique(np.r_[np.linspace(.5, 200, 600), obj['eta_hat'], obj['eta_true']])
            d = np.asarray(obj['values']) - obj['gamma_hat']
            lhs = np.mean((d[None, :] / etas[:, None]) ** obj['beta_hat'], axis=1)
            at_fit = float(np.mean((d / obj['eta_hat']) ** obj['beta_hat']))
            assert np.isclose(at_fit, j1, rtol=1e-12, atol=1e-12)
            cases[label + '_' + role] = dict(sample=obj, trace=trace, j1=j1,
                                            eta_grid=etas.tolist(), scale_lhs=lhs.tolist(),
                                            scale_lhs_at_return=at_fit)
    assert before == protected()
    selected = [c['trace']['calls'][c['trace']['selected_start']]['points'] for c in cases.values()]
    maximum_iteration = max(len(p)-1 for p in selected)
    limit = float(np.ceil(maximum_iteration / 30) * 30)
    # A shared linear window makes residual convergence near zero visible.
    # Early residuals outside this window remain in the complete trace cache.
    residual_limit = .2
    axes = dict(iterations=dict(xlim=[0., limit], xticks=np.arange(0, limit+1, 30).tolist(),
                                ylim=[-residual_limit, residual_limit],
                                yticks=[-.2, -.1, 0., .1, .2]),
                scale=dict(xlim=[0., 200.], xticks=[0., 50., 100., 150., 200.],
                           ylim=[0., 2.], yticks=[0., .5, 1., 1.5, 2.]))
    write_json(CACHE, dict(cases=cases, pairs=previous['pairs'], axes=axes, source_sha256=inputs,
                          protected_sha256=before, case_checks=previous['case_checks'],
                          abnormal_checks=previous['abnormal_checks'], new_samples=0,
                          replayed_samples=4, archived_estimates_replaced=0,
                          figure_contract=dict(conclusion='Both normal and anomalous cases converge to joint weighted-equation roots; those roots determine scale.',
                                               archetype='quantitative grid', backend='Python/matplotlib', export='PNG only',
                                               panels='a/d actual selected-start residual iterations; b/e joint equation zero sets; c/f scale equation in eta.',
                                               redundant_joint_objective_map=False,
                                               sample_selection='Previous normal groups 3/1 and abnormal groups 11/9 retained.')))
    for key, c in cases.items():
        points = c['trace']['calls'][c['trace']['selected_start']]['points']
        print(key, 'start', c['trace']['selected_start'], 'points', len(points),
              'last residual', points[-1]['objective'], 'eta', c['sample']['eta_hat'])


def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import StrMethodFormatter
    cache = load(CACHE)
    for p, sha in cache['source_sha256'].items():
        assert digest(p) == sha, p
    style = module(HERE / '20261010-配对图参照线精简.py', 'wmle_iteration_style')
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                         'font.size': 9, 'axes.labelsize': 9, 'axes.titlesize': 9,
                         'xtick.labelsize': 8, 'ytick.labelsize': 8, 'axes.linewidth': .7,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.unicode_minus': False,
                         'legend.frameon': False})
    old_meta = load(base.DATA / '20261010-配对图参照线精简核验.json')['figures']
    with np.load(base.DATA / '20261010-参照线精简WMLE网格.npz') as old:
        grids = {k: old[k] for k in old.files}
    with np.load(base.NORMAL_GRID) as normals:
        grids.update({k: normals[k] for k in normals.files})
    before, source_rows, figures = protected(), [], {}
    for label in base.renderer.LABELS:
        fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
        for row, role in enumerate(('normal', 'abnormal')):
            c = cache['cases'][label + '_' + role]
            obj = c['sample']
            path = c['trace']['calls'][c['trace']['selected_start']]['points']
            a, b, s = axes[row]
            for key, values in cache['axes']['iterations'].items():
                getattr(a, 'set_' + key)(values)
            a.set(xlabel='迭代次数', ylabel=r'$T_1,\ T_2$')
            a.axhline(0, color=style.GRAY, lw=.6, ls=':', zorder=0)
            a.set_title(obj['role'] + f" · 第{obj['group']}组", loc='left', pad=14)
            for term, color in [('t1', style.BLUE), ('t2', style.BROWN)]:
                a.plot([p['iteration'] for p in path], [p[term] for p in path], color=color,
                       lw=1.1, marker='o', ms=1.7, markeredgewidth=0)
            for point in path:
                source_rows.append(dict(example=label, role=role, group=obj['group'], panel='iteration',
                                        x=point['iteration'], y1=point['t1'], y2=point['t2'],
                                        beta=point['beta'], gamma=point['gamma'], objective=point['objective']))
            prefix = label + '_' + obj['role'] + '_'
            gs, bs = grids[prefix + 'gamma'], grids[prefix + 'beta']
            for key, value in old_meta[label]['axes'][row*3+1].items():
                getattr(b, 'set_' + key)(value)
            b.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\beta$')
            b.axvline(1, color=style.GRAY, ls='--', lw=.7, zorder=0)
            for term, color in [('T1', style.BLUE), ('T2', style.BROWN)]:
                b.contour(gs/obj['gamma_true'], bs, grids[prefix + term].T, levels=[0],
                          colors=[color], linewidths=1.2)
            b.scatter([1], [obj['beta_true']], marker='D', facecolors='white', edgecolors=style.GRAY, s=25, lw=.8, zorder=5)
            b.scatter([obj['gamma_hat']/obj['gamma_true']], [obj['beta_hat']], marker='*', s=58,
                      color=style.BROWN, edgecolors='white', lw=.5, zorder=6)
            for key, values in cache['axes']['scale'].items():
                getattr(s, 'set_' + key)(values)
            s.set(xlabel=r'$\eta$', ylabel=r'$\frac{1}{n}\sum_i[(x_{(i)}-\hat\gamma)/\eta]^{\hat\beta}$')
            eta, lhs = np.asarray(c['eta_grid']), np.asarray(c['scale_lhs'])
            s.plot(eta, lhs, color=style.BROWN, lw=1.1)
            s.axhline(c['j1'], color=style.GRAY, lw=.8, ls='--')
            s.scatter([obj['eta_hat']], [c['j1']], marker='*', s=58, color=style.BROWN,
                      edgecolors='white', lw=.5, zorder=6)
            s.scatter([obj['eta_true']], [c['j1']], marker='D', facecolors='white', edgecolors=style.GRAY,
                      s=25, lw=.8, zorder=5)
            source_rows.extend(dict(example=label, role=role, group=obj['group'], panel='scale',
                                    x=float(e), y1=float(y), y2=c['j1'], beta=obj['beta_hat'],
                                    gamma=obj['gamma_hat'], objective='') for e, y in zip(eta, lhs))
        axes[0, 0].legend(handles=[Line2D([0], [0], color=style.BLUE, lw=1.1, label=r'$T_1$'),
                                 Line2D([0], [0], color=style.BROWN, lw=1.1, label=r'$T_2$')], fontsize=8, loc='upper right')
        axes[0, 1].legend(handles=[Line2D([0], [0], color=style.BLUE, lw=1.2, label=r'$T_1=0$'),
                                 Line2D([0], [0], color=style.BROWN, lw=1.2, label=r'$T_2=0$')], fontsize=7, loc='upper right')
        axes[0, 2].legend(handles=[Line2D([0], [0], color=style.GRAY, lw=.8, ls='--', label=r'$J_1(n)$')], fontsize=8, loc='upper right')
        for i, ax in enumerate(axes.flat):
            ax.text(-.16, 1.04, chr(97+i), transform=ax.transAxes, fontweight='bold', fontsize=11)
            ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
            ax.yaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
        fig.legend(handles=[Line2D([0], [0], marker='*', ms=7, color=style.BROWN, ls='none', label='原估计'),
                            Line2D([0], [0], marker='D', mfc='white', mec=style.GRAY, ls='none', ms=4, label='真参数')],
                   loc='lower center', bbox_to_anchor=(.52, .015), ncol=2, fontsize=8)
        fig.subplots_adjust(left=.08, right=.985, bottom=.14, top=.91, wspace=.39, hspace=.48)
        fig.canvas.draw()
        axes_meta = [dict(xlim=list(ax.get_xlim()), ylim=list(ax.get_ylim()), xticks=ax.get_xticks().tolist(),
                          yticks=ax.get_yticks().tolist(), xlabel=ax.get_xlabel(), ylabel=ax.get_ylabel(),
                          xscale=ax.get_xscale(), yscale=ax.get_yscale()) for ax in axes.flat]
        assert all(axes_meta[i] == axes_meta[i+3] for i in range(3))
        text_boxes = [t.get_window_extent(fig.canvas.get_renderer()) for t in fig.findobj(matplotlib.text.Text)
                      if t.get_visible() and t.get_text()]
        assert all(b.x0 >= -1 and b.y0 >= -1 and b.x1 <= fig.bbox.x1+1 and b.y1 <= fig.bbox.y1+1 for b in text_boxes)
        output = IMAGES / ('配对情形_' + label + '.png')
        save_png(fig, output, dpi=400)
        plt.close(fig)
        clipped = {role: [{**p, 'outside_window': [t for t in ('t1', 't2') if abs(p[t]) > .2]}
                          for p in cache['cases'][label+'_'+role]['trace']['calls'][
                              cache['cases'][label+'_'+role]['trace']['selected_start']]['points']
                          if abs(p['t1']) > .2 or abs(p['t2']) > .2] for role in ('normal', 'abnormal')}
        figures[label] = dict(path=str(output), sha256=digest(output), axes=axes_meta,
                              shape_location_contours='Same stored grids and zero levels as previous version',
                              iteration_nodes_outside_display=clipped,
                              scale_curve_visible_window=[0., 2.], scale_nodes_saved=len(c['eta_grid']))
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(source_rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(source_rows)
    write_atomic(ROWS, buffer.getvalue().encode('utf-8-sig'))
    assert protected() == before
    record = load(QA) if QA.exists() else {}
    record.update(figures=figures, cache_sha256=digest(CACHE), rows_sha256=digest(ROWS),
                  protected_sha256=before, figure_contract=cache['figure_contract'],
                  script_sha256=digest(__file__),
                  new_samples=0, replayed_samples=4, archived_estimates_replaced=0)
    write_json(QA, record)
    print('Rendered actual residual iterations, joint zero sets and scale-equation intersections; PNG only.')


def revise():
    text = REPORT.read_text(encoding='utf-8')
    current = re.search(r'^#### 2\.1\.\d+[^\n]*\[WMLE\].*?(?=^#### |^### |\Z)', text, re.M | re.S)
    if current and '的a、d为原程序选中起点的实际迭代' in current[0] and 'T_1(\\beta,\\gamma)=' in current[0]:
        print('WMLE already uses actual iterations, joint residual equations and scale recovery.')
        return
    before, remainder = text.split('#### 2.1.5', 1)
    section, after = remainder.split('#### 2.1.6', 1)
    tables = re.findall(r'^\|.*$', section, re.M)
    previous_math = base.renderer.math_blocks(text)
    original_sha = digest(REPORT)
    replacements = {
        21: r'''$$
T_1(\beta,\gamma)=\frac{J_2(n)}{\beta}+\frac1n\sum_i\ln(x_{(i)}-\gamma)
-\frac{\sum_i(x_{(i)}-\gamma)^\beta\ln(x_{(i)}-\gamma)}{\sum_i(x_{(i)}-\gamma)^\beta}.
\tag{21}
$$''',
        22: r'''$$
T_2(\beta,\gamma)=\left(\frac1n\sum_i\frac1{x_{(i)}-\gamma}\right)
\frac{\sum_i(x_{(i)}-\gamma)^\beta}{\sum_i(x_{(i)}-\gamma)^{\beta-1}}-J_3(n,\beta).
\tag{22}
$$''',
        24: r'''$$
\frac1n\sum_i\left(\frac{x_{(i)}-\hat\gamma}{\eta}\right)^{\hat\beta}=J_1(n)
\quad\Longrightarrow\quad
\hat\eta=\left[\frac{\sum_i(x_{(i)}-\hat\gamma)^{\hat\beta}}{nJ_1(n)}\right]^{1/\hat\beta}.
\tag{24}
$$'''}
    section = re.sub(r'\$\$(?:(?!\$\$).)*\$\$',
                     lambda m: replacements.get(int(re.search(r'\\tag\{(\d+)\}', m[0])[1]), m[0]), section, flags=re.S)
    section = section.replace('WMLE先根据样本量取得校准权重，用观测到候选位置的距离建立形状与位置的两条加权方程：',
                              'WMLE先根据样本量取得校准权重，将形状与位置的两条加权方程写成残差：')
    section = section.replace('两条方程共享β和γ，需要联立求解。将式（21）、（22）左侧减右侧分别记为残差T₁、T₂，程序共同调整β、γ，最小化残差平方和：',
                              'T₁、T₂为形状与位置方程的残差。两式共享β和γ，需要联立求解；程序共同调整β、γ，最小化残差平方和：')
    start = section.index('图16、17的b、e分别')
    end = section.index('得到β̂、γ̂后', start)
    section = section[:start] + '图16、17的a、d为原程序选中起点的实际迭代，展示式（21）、（22）的两个残差怎样趋近零；b、e为T₁=0与T₂=0的参数组合，共同交点同时确定β̂、γ̂。程序按式（23）求解，以残差平方和≤1e−8接受返回值。\n\n' + section[end:]
    start = section.index('J₁为尺度校准权重。')
    end = section.index('本批J₃权重表', start)
    section = section[:start] + 'J₁为尺度校准权重。图16、17的c、f固定已求得的β̂、γ̂，以η为横坐标画式（24）左侧。曲线与J₁水平线的交点对应η̂，白菱形标出尺度真值。\n\n' + section[end:]
    section = section.replace('第11组的最小观测高于真位置75.95，前四个观测集中在575.95—586.04；第3组的下端空缺为48.67。样本距离的结构不同，改变了式（21）、（22）中两组统计量的关系。',
                              '第3组的最小观测与第二小观测相隔33.64；第11组前四个观测集中在575.95—586.04。不同的间距结构改变式（21）、（22）的平衡位置。图16a、d中，两组的T₁、T₂均随迭代趋近零。')
    section = section.replace('图16f中，选定位置后的距离为2.44—56.38，明显小于真位置下的75.95—129.89。将β=1.10与这些距离代入式（24），得到η=26.30；第3组同样计算得到η=86.69。明显异常由偏离真参数的共同交点及其尺度恢复形成。',
                              '将β=1.10、γ=573.51代入式（24），图16f的尺度方程在η=26.30处与J₁相交；第3组的交点为η=86.69。第11组已将两条加权方程解到接近零，但联合解偏离真参数，并通过尺度公式形成η的低估。')
    section = section.replace('第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第1组分布在522.01—678.65，跨度更大。第1组的共同交点为γ=503.91、β=1.60，接近真参数；第9组两条方程则在γ=475.49、β=5.31处共同满足。',
                              '第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第1组分布在522.01—678.65，跨度更大。图17a、d中，两组残差均趋近零；b、e的共同交点分别为γ=503.91、β=1.60和γ=475.49、β=5.31，后者的形状明显偏大。')
    section = section.replace('图17f中，选定位置后的距离为76.46—184.50。按式（24）计算，η=163.08；第1组为η=100.92。共同求出的形状、位置通过同一尺度公式继续传递到η。',
                              '固定第9组的β=5.31、γ=475.49后，图17f的尺度方程在η=163.08处与J₁相交；第1组为η=100.92。偏大的形状和向左的位置通过式（24）共同确定偏大的尺度。')
    final = before + '#### 2.1.5' + section + '#### 2.1.6' + after
    assert re.findall(r'^\|.*$', section, re.M) == tables
    assert re.findall(r'\\tag\{(\d+)\}', final) == [str(i) for i in range(1, 31)]
    final_math = base.renderer.math_blocks(final)
    assert all(a == b for i, (a, b) in enumerate(zip(previous_math, final_math), 1) if i not in (21, 22, 24))
    write_atomic(REPORT, final.encode('utf-8'))
    record = load(QA) if QA.exists() else {}
    record.update(text_revision=dict(before_sha256=original_sha, after_sha256=digest(REPORT),
                                     changed_equations=[21, 22, 24], equation_23_unchanged=True,
                                     tables_unchanged=True, scope='WMLE section only'))
    write_json(QA, record)
    print('Updated T1/T2 definitions and scale-equation interpretation; all 30 equation numbers retained.')


def verify():
    cache, qa = load(CACHE), load(QA)
    assert qa['cache_sha256'] == digest(CACHE) and qa['rows_sha256'] == digest(ROWS)
    assert qa['script_sha256'] == digest(__file__)
    for p, sha in cache['source_sha256'].items():
        assert digest(p) == sha, p
    assert qa['protected_sha256'] == protected()
    assert len(cache['abnormal_checks']) == 84
    assert all(r['residual_sum'] <= 1e-8 for r in cache['abnormal_checks'])
    for c in cache['cases'].values():
        obj = c['sample']
        assert all(len(call['points']) == call['nit'] + 1 for call in c['trace']['calls'])
        last = c['trace']['calls'][c['trace']['selected_start']]['points'][-1]
        assert last['objective'] <= 1e-8
        assert np.allclose([last['beta'], last['gamma']], [obj['beta_hat'], obj['gamma_hat']], rtol=1e-10, atol=1e-8)
        assert np.isclose(c['scale_lhs_at_return'], c['j1'], rtol=1e-12)
        assert np.all(np.diff(c['scale_lhs']) < 0)
    for fig in qa['figures'].values():
        assert digest(fig['path']) == fig['sha256']
        assert all(fig['axes'][i] == fig['axes'][i+3] for i in range(3))
        assert all(a['xscale'] == a['yscale'] == 'linear' for a in fig['axes'])
    text = REPORT.read_text(encoding='utf-8')
    assert re.findall(r'\\tag\{(\d+)\}', text) == [str(i) for i in range(1, 31)]
    section = re.search(r'^#### 2\.1\.\d+[^\n]*\[WMLE\].*?(?=^#### |^### |\Z)', text, re.M | re.S)[0]
    assert 'T_1(\\beta,\\gamma)=' in section and 'T_2(\\beta,\\gamma)=' in section
    assert '真位置γ₀展示样本距离' not in section
    qa['validation'] = dict(status='passed', cases=4, abnormal_residual_checks=84,
                            same_original_estimates=True, matched_linear_axes=True, equation_numbers=30)
    write_json(QA, qa)
    print('PASS: 4 archived estimates replayed unchanged; actual selected-start traces, scale equations, 84 anomaly checks and 30 formula numbers.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['build', 'render', 'revise', 'verify'])
    globals()[parser.parse_args().action]()
