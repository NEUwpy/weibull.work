"""Complete empirical distributions and one computed process figure per method."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from 计算逐法过程曲线 import mother
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / '结果'
DATA = OUT / '中间数据'
METHODS = ['mdm', 'lse', 'lre', 'wmle', 'mle']
NAMES = dict(mdm='MDM', lse='LSE', lre='LRE', wmle='WMLE', mle='MLE')
COLORS = dict(mdm='#345D7E', lse='#589CA3', lre='#8A7398', wmle='#B27448', mle='#5F6570')
STYLES = ['-', '--', '-.', (0, (5, 2, 1, 2)), ':']
BLUE, RETURN = '#345D7E', '#B55E3E'
CONDITIONS = [(2, 7), (5, 7), (5, 15)]
TITLES = dict(mdm='MDM：在哪里达到固定梯度阈值？', lse='LSE：在哪里得到最小回归损失？',
              lre='LRE：在哪里得到最高直线相关性？', wmle='WMLE：加权位置方程在哪里满足？',
              mle='MLE：有限似然分支在哪里停止上升？')
FILES = dict(mdm='图2_MDM位置选择过程', lse='图3_LSE位置选择过程', lre='图4_LRE位置选择过程',
             wmle='图5_WMLE位置选择过程', mle='图6_MLE位置选择过程')
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
    'font.size': 7, 'axes.titlesize': 7.2, 'axes.labelsize': 7, 'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.linewidth': .7,
    'axes.spines.right': False, 'axes.spines.top': False, 'axes.unicode_minus': False,
    'pdf.fonttype': 42, 'svg.fonttype': 'none', 'legend.frameon': False})
source = json.loads((DATA / '逐法过程曲线.json').read_text(encoding='utf-8'))
old = json.loads((HERE / '输入快照' / '原案例估计.json').read_text(encoding='utf-8'))
qa = dict(ecdf=[], process_figures=[])


def save(fig, name):
    for ext in ('png', 'pdf', 'svg'):
        path = OUT / f'{name}.{ext}'
        fig.savefig(path, dpi=450, facecolor='white')
        if ext == 'svg':
            # XML attribute whitespace is immaterial; keep Git diffs clean.
            path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)


def tag(ax, label):
    ax.text(-.13, 1.10, label, transform=ax.transAxes, fontsize=8, weight='bold')


def distributions():
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.0))
    params = [('beta_hat', 5, '形状估计 β', True), ('eta_hat', 1000, '尺度估计 η', True),
              ('gamma_hat', 500, '位置估计 γ', False)]
    for col, (param, truth, label, logarithmic) in enumerate(params):
        all_values = np.array([r[param] for r in old if r['beta'] == 5 and r['method'] in METHODS and r['converged']])
        limits = (float(all_values.min() * .86), float(all_values.max() * 1.16)) if logarithmic else (-30., float(all_values.max() * 1.045))
        for row, n in enumerate((7, 15)):
            ax = axes[row, col]
            if logarithmic:
                ax.set_xscale('log')
            for method, style in zip(METHODS, STYLES):
                rr = [r for r in old if r['beta'] == 5 and r['n'] == n and r['method'] == method]
                values = np.sort([r[param] for r in rr if r['converged']])
                # Duplicate values (including gamma=0) form a true vertical ECDF jump.
                xx = np.r_[limits[0], values, limits[1]]
                yy = np.r_[0., np.arange(1, len(values) + 1) / len(values), 1.]
                ax.step(xx, yy, where='post', color=COLORS[method], ls=style, lw=1.15)
                assert len(values) == sum(r['converged'] for r in rr)
                assert limits[0] <= values[0] <= values[-1] <= limits[1]
                qa['ecdf'].append(dict(n=n, method=method, parameter=param, success=len(values), failure=50-len(values),
                    minimum=float(values[0]), maximum=float(values[-1]), x_limits=list(limits), all_successful_values_included=True))
            ax.axvline(truth, ls='--', color='black', lw=.8)
            ax.axhline(.5, color='.75', ls=':', lw=.6)
            ax.set_ylim(-.025, 1.035); ax.set_xlim(limits); ax.set_xlabel(label + ('（对数轴）' if logarithmic else ''))
            ax.set_yticks([0, .25, .5, .75, 1.], ['0', '25%', '50%', '75%', '100%'])
            if col == 0:
                ax.set_ylabel('不超过横坐标的成功估计比例')
                ax.set_title(f'n={n}，每方法50组', loc='left', pad=10)
            else:
                ax.set_yticklabels([])
            ax.text(truth, 1.008, f'真值 {truth}', ha='center', va='bottom', fontsize=6.2)
            tag(ax, chr(97 + row * 3 + col))
    handles = [Line2D([], [], color=COLORS[m], ls=s, lw=1.2) for m, s in zip(METHODS, STYLES)]
    for n, y in [(7, .972), (15, .501)]:
        labels = [f'{NAMES[m]} 成功{sum(r["converged"] for r in old if r["beta"] == 5 and r["n"] == n and r["method"] == m)} / 失败{sum(not r["converged"] for r in old if r["beta"] == 5 and r["n"] == n and r["method"] == m)}' for m in METHODS]
        fig.legend(handles, labels, ncol=5, loc='upper center', bbox_to_anchor=(.52, y), fontsize=5.7,
                   handlelength=2.1, columnspacing=.9)
    fig.subplots_adjust(left=.095, right=.982, top=.848, bottom=.09, hspace=.69, wspace=.18)
    save(fig, '图1_原案例参数分布')


def format_axis(ax, method, xmax, original=False):
    ax.set_xlim(-25, xmax)
    ax.set_xlabel('候选位置 γ')
    ax.axvline(500, color='black', ls=':', lw=.9, zorder=3)
    ax.set_xticks([0, 500, 1000])
    if method in ('lse', 'lre'):
        ax.set_yscale('log'); ax.set_ylim(.001, 1.)
        ax.set_ylabel(r'回归损失 $1-\rho^2$（越低越好）')
    elif method == 'mdm':
        ax.set_ylim((-.04, .23) if original else (-.46, 1.10))
        ax.axhline(.1, color='black', ls='--', lw=.85)
        ax.set_ylabel(r'标准差剖面梯度 $g(\gamma)$')
        ax.text(.99, .1, '阈值 0.10', transform=ax.get_yaxis_transform(), ha='right', va='bottom', fontsize=6)
    else:
        ax.axhline(0, color='black', ls='--', lw=.85)
        if method == 'wmle':
            ax.set_ylim((-.32, .13) if original else (-.13, .13))
        else:
            ax.set_ylim((-.05, .035) if original else (-.25, .27))
        ax.set_ylabel(r'条件位置残差 $T_2(\gamma)$' if method == 'wmle' else r'有限分支分数 $1000\,U_\gamma/n$')


def draw_curve(ax, r, color, alpha, lw, method):
    pp = np.array([[p[0], np.nan if p[1] is None else p[1]] for p in r['points']])
    if method == 'wmle':
        ordinary = [p[1] if p[1] is not None and not p[4] else np.nan for p in r['points']]
        ax.plot(pp[:, 0], ordinary, color=color, alpha=alpha, lw=lw, zorder=1)
        clamp = [p[1] if p[4] else np.nan for p in r['points']]
        ax.plot(pp[:, 0], clamp, color=color, ls=(0, (2, 2)), alpha=alpha, lw=lw + .1)
    else:
        ax.plot(pp[:, 0], pp[:, 1], color=color, alpha=alpha, lw=lw, zorder=1)
    truth = r['truth']
    if truth is not None and truth[1] is not None:
        ax.scatter(500, truth[1], s=5 if alpha < .9 else 14, color=color, alpha=max(.35, alpha), linewidths=0, zorder=3)
    if r['fit']['converged']:
        g = r['fit']['gamma_hat']
        p = r['returned']
        if p is not None and p[1] is not None:
            ax.scatter(g, p[1], s=11 if alpha < .9 else 26, color=RETURN, alpha=.65 if alpha < .9 else 1,
                       marker='x', lw=.8, zorder=4)
        # Rug preserves every returned gamma even when the conditional y is outside the zoom.
        ax.plot(g, .018, marker='|', color=RETURN, ms=6, alpha=.55 if alpha < .9 else 1,
                transform=ax.get_xaxis_transform(), clip_on=True, zorder=5)


def method_figure(method):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.35))
    rr = [r for r in source['curves'] if r['method'] == method]
    xmax = 1400.
    panel_records = []
    for index, (beta, n) in enumerate(CONDITIONS):
        ax = axes.flat[index]
        rows = [r for r in rr if r['source'] == 'paired' and r['beta'] == beta and r['n'] == n]
        assert len(rows) == 50
        stat = next(s for s in source['summaries'] if s['method'] == method and s['beta'] == beta and s['n'] == n)
        format_axis(ax, method, xmax)
        for r in rows:
            draw_curve(ax, r, BLUE, .18, .65, method)
        text = f'γ中位数 {stat["gamma_median"]:.0f}；γ>500：{stat["gamma_above_truth"]}/{stat["success"]}\nγ=0：{stat["gamma_at_zero"]}；失败：{50-stat["success"]}/50'
        if method == 'mdm':
            q = stat['truth_criterion_quartiles']
            text += f'\ng(500)中位数 {q[1]:.3f}；IQR {q[2]-q[0]:.3f}'
        if method == 'wmle' and stat['truth_criterion_count'] < 50:
            text += f'\n真γ处条件方程有定义：{stat["truth_criterion_count"]}/50'
        ax.text(.025, .955, text, transform=ax.transAxes, ha='left', va='top', fontsize=6.2,
                bbox=dict(facecolor='white', edgecolor='none', alpha=.93, pad=2.4), zorder=8)
        ax.set_title(f'β={beta}，n={n}：全部50组', loc='left', pad=9)
        tag(ax, chr(97+index))
        panel_records.append(dict(beta=beta, n=n, curves=len(rows), successful_returns=stat['success'],
            all_returns_marked_as_rug=True, x_limits=list(ax.get_xlim()), criterion_y_limits=list(ax.get_ylim())))
    ax = axes.flat[3]
    chosen = next(r for r in rr if r['source'] == 'original')
    format_axis(ax, method, xmax, original=True)
    draw_curve(ax, chosen, BLUE, 1., 1.4, method)
    gamma = chosen['fit']['gamma_hat']
    ax.axvline(gamma, color=RETURN, ls='--', lw=.8)
    ax.text(gamma, 1.012, f'返回 γ={gamma:.0f}', transform=ax.get_xaxis_transform(), color=RETURN, ha='center', fontsize=6)
    truth_value, returned_value = chosen['truth'][1], chosen['returned'][1]
    if method == 'mdm':
        text = f'真γ处 g={truth_value:.3f}<0.10\n向右至γ={gamma:.0f}，g=0.10'
    elif method in ('lse', 'lre'):
        text = f'真γ处损失 {truth_value:.4f}\n返回处损失 {returned_value:.4f}，更低'
    elif method == 'wmle':
        text = f'真γ处残差 {truth_value:.3f}\n返回处残差接近0'
    else:
        increase = chosen['returned'][5] - chosen['truth'][5]
        text = f'真γ处分数 {truth_value:.3f}>0\n返回处正转负；对数似然提高{increase:.3f}'
    ax.text(.025, .955, text, transform=ax.transAxes, ha='left', va='top', fontsize=6.2,
            bbox=dict(facecolor='white', edgecolor='none', alpha=.94, pad=2.4), zorder=8)
    ax.set_title(f'原β=5，n=7，组#{chosen["sample_id"]}：实际高估单例', loc='left', pad=9)
    tag(ax, 'd')
    fig.suptitle(TITLES[method], x=.095, y=.993, ha='left', fontsize=9, weight='bold')
    fig.legend([Line2D([], [], color=BLUE, lw=1), Line2D([], [], color=RETURN, marker='x', lw=0, ms=4),
                Line2D([], [], color='black', ls=':', lw=.9)],
               ['准则曲线；蓝点为真γ处', '实际返回γ；底部短线保留全部成功返回', '真γ=500'],
               ncol=3, loc='upper center', bbox_to_anchor=(.54, .955), fontsize=6.1, columnspacing=1.2)
    fig.text(.095, .012, 'a→b：同组潜在样本，仅改变β；b→c：样本量条件对照；d：另一批原案例单例。', fontsize=6.3)
    fig.subplots_adjust(left=.105, right=.985, top=.84, bottom=.095, hspace=.56, wspace=.31)
    save(fig, FILES[method])
    qa['process_figures'].append(dict(method=method, file=FILES[method], panels=panel_records,
        original_sample_id=chosen['sample_id'], original_gamma=gamma, original_truth_value=truth_value,
        original_returned_value=returned_value, conditional_not_optimizer_iterations=method in ('wmle', 'mle')))


def main():
    distributions()
    for method in METHODS:
        method_figure(method)
    (DATA / '逐法图核验.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print('EXPORTED full ECDF and 5 process figures (PNG/PDF/SVG)', flush=True)


if __name__ == '__main__':
    main()
