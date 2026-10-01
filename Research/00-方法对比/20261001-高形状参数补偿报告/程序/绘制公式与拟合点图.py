"""Method-specific diagnostics: regression observations, equations and likelihood.

Reuses existing curve data and plotting helpers. Every displayed point is either
an actual transformed observation or an explicitly numbered formula evaluation.
"""
import json
from pathlib import Path
import numpy as np
import 绘制逐法分析图 as base
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DATA, OUT = base.DATA, base.OUT
POINTS = json.loads((DATA / '单组绘图点与方程.json').read_text(encoding='utf-8'))
FORMULAS = {
    'mdm': r'$g(\gamma)=\frac{d}{d\gamma}\min_\beta\mathrm{SD}\{(t_i-\gamma)/[-\ln(1-p_i)]^{1/\beta}\};\quad g(\hat\gamma)=0.10$',
    'lse': r'$D(\gamma)=1-\mathrm{corr}^2\{z_i,\ln(t_i-\gamma)\};\quad \hat\gamma=\mathrm{argmin}_\gamma D(\gamma)$',
    'lre': r'$D(\gamma)=1-\mathrm{corr}^2\{\ln(t_i-\gamma),\ln[-\ln(1-p_i)]\};\quad \hat\gamma=\mathrm{argmin}_\gamma D(\gamma)$',
    'wmle': r'$T_1=J_2/\beta+\overline{\ln d}-\sum d_i^\beta\ln d_i/\sum d_i^\beta;\quad O=T_1^2+T_2^2$',
    'mle': r'$\ell_p(\gamma)=\max_{\beta>1,\eta>0}\ell(\beta,\eta,\gamma);\quad \Delta\ell=\ell_p(\gamma)-\ell_p(500)$',
}
SECOND_FORMULAS = {
    'mdm': r'$p_i=(i-0.3)/(n+0.4)$' + '；d的G号是候选γ计算点，连线连接计算值。',
    'lse': r'$z_i=E[\ln E_{(i:n)}],\ E\sim\mathrm{Exp}(1)$' + '；d的1–7是同一组观测，直线为条件OLS。',
    'lre': r'$p_i=(i-0.3)/(n+0.4)$' + '；d的1–7是同一组观测，直线为条件OLS。',
    'wmle': r'$T_2=\overline{1/d}\,\sum d_i^\beta/\sum d_i^{\beta-1}-J_3(n,\beta);\quad d_i=t_i-\gamma$',
    'mle': r'$\ell=n\ln\beta-n\beta\ln\eta+(\beta-1)\sum\ln d_i-\sum(d_i/\eta)^\beta;\quad d_i=t_i-\gamma$',
}
TITLES = dict(mdm='MDM：梯度与0.10阈值的交点', lse='LSE：最低回归损失与实际样本点',
              lre='LRE：最高相关性与实际样本点', wmle='WMLE：条件位置方程与联合方程交会',
              mle='MLE：有限剖面似然的高点或零边界')


def profile_values(r, method):
    if method == 'mle':
        return [p[5]-r['truth'][5] if p[5] is not None else np.nan for p in r['points']]
    return [p[1] if p[1] is not None else np.nan for p in r['points']]


def mle_axis(ax, original=False):
    ax.set_xlim(-25, 1400); ax.set_xticks([0, 500, 1000]); ax.set_xlabel('候选位置 γ')
    ax.set_ylabel(r'条件对数似然增量 $\Delta\ell(\gamma)$')
    ax.axvline(500, color='black', ls=':', lw=.8)
    ax.axhline(0, color='.55', lw=.6)
    ax.set_ylim((-.10, .067) if original else (-1., 2.65))


def mle_curve(ax, r, alpha=.18, lw=.65):
    xx, yy = [p[0] for p in r['points']], profile_values(r, 'mle')
    ax.plot(xx, yy, color=base.BLUE, alpha=alpha, lw=lw)
    if r['fit']['converged']:
        p = r['returned']
        ax.scatter(p[0], p[5]-r['truth'][5], s=12, color=base.RETURN, marker='x', alpha=.65, lw=.8, zorder=4)
        ax.plot(p[0], .018, marker='|', color=base.RETURN, ms=6, transform=ax.get_xaxis_transform(), alpha=.55)


def calculation_points(ax, r, method):
    pts = POINTS['evaluation_points'][method]
    defined = [p for p in pts['points'] if p['value'] is not None]
    ax.scatter([p['gamma'] for p in defined], [p['value'] for p in defined], s=5,
               facecolor='white', edgecolor=base.BLUE, linewidth=.45, alpha=.75, zorder=3)
    selected = [pts['true_gamma_point_id'], pts['returned_gamma_point_id']]
    for target in (0, 250, 750):
        p = min(defined, key=lambda p: abs(p['gamma']-target))
        if p['id'] not in selected:
            selected.append(p['id'])
    for pid in selected:
        p = next(p for p in defined if p['id'] == pid)
        if pid == pts['true_gamma_point_id']:
            text, offset = f'{pid}：γ=500', (10, -22 if method == 'mle' else 18)
        elif pid == pts['returned_gamma_point_id']:
            text, offset = f'{pid}：返回γ={p["gamma"]:.0f}', (-94, -17 if method == 'mle' else 16)
        else:
            text, offset = pid, (4, -13)
        ax.annotate(text, (p['gamma'], p['value']), xytext=offset, textcoords='offset points',
                    fontsize=5.8, color=base.RETURN if pid == pts['returned_gamma_point_id'] else base.BLUE,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.86, pad=.4), zorder=6)
    return dict(type='numbered_formula_evaluations', plotted_defined_points=len(defined),
                total_points=len(pts['points']), labelled_point_ids=selected,
                true_gamma_point_id=pts['true_gamma_point_id'], returned_gamma_point_id=pts['returned_gamma_point_id'])


def regression_panel(ax, method):
    case = POINTS['regressions'][method]
    for index, ds in enumerate(case['datasets']):
        pp = ds['points']; xx = np.array([p['x'] for p in pp]); yy = np.array([p['y'] for p in pp])
        color, marker, ls = (base.BLUE, 'o', '--') if index == 0 else (base.RETURN, 's', '-')
        line_x = np.linspace(xx.min(), xx.max(), 80)
        ax.plot(line_x, ds['slope']*line_x + ds['intercept'], color=color, ls=ls, lw=1.1)
        ax.scatter(xx, yy, color=color, marker=marker, s=17, linewidths=0, zorder=4)
        for p in pp:
            # Same observation number in both transformations; matched numbers.
            offset = (-10, 5) if index == 0 else (5, -11)
            ax.annotate(str(p['id']), (p['x'], p['y']), xytext=offset, textcoords='offset points',
                        color=color, fontsize=5.8, zorder=5)
    ax.set_xlabel(r'理论对数顺序统计量期望 $z_i$' if method == 'lse' else r'变换后观测 $\ln(t_i-\gamma)$')
    ax.set_ylabel(r'变换后观测 $\ln(t_i-\gamma)$' if method == 'lse' else r'绘图位置变换 $\ln[-\ln(1-p_i)]$')
    ds0, ds1 = case['datasets']
    ax.legend([Line2D([], [], color=base.BLUE, ls='--', marker='o', ms=3),
               Line2D([], [], color=base.RETURN, ls='-', marker='s', ms=3)],
              [f'固定γ=500：条件拟合，D={ds0["loss"]:.4f}',
               f'固定返回γ={ds1["gamma"]:.0f}：D={ds1["loss"]:.4f}'],
              loc='upper left', fontsize=5.5, handlelength=1.7)
    ax.margins(x=.13, y=.20)
    return dict(type='observed_regression_points', sample_id=case['sample_id'],
                observations=7, transformed_points=14, all_observation_ids_labelled=True,
                returned_gamma=ds1['gamma'], loss_true_gamma=ds0['loss'], loss_returned_gamma=ds1['loss'])


def wmle_panel(ax):
    w = POINTS['wmle']; gg, bb = np.array(w['gamma_grid']), np.array(w['beta_grid'])
    ax.contour(gg, bb, np.array(w['t1']), levels=[0], colors=[base.BLUE], linewidths=1.3)
    ax.contour(gg, bb, np.array(w['t2']), levels=[0], colors=['#4B8B86'], linewidths=1.3, linestyles='--')
    ax.scatter(w['truth_gamma'], w['truth_beta'], s=28, color='black', marker='D', zorder=5)
    ax.scatter(w['returned_gamma'], w['returned_beta'], s=34, color=base.RETURN, marker='x', linewidth=1.2, zorder=6)
    ax.annotate('生成真参数 (500,5)', (500, 5), xytext=(8, 8), textcoords='offset points', fontsize=5.8)
    ax.annotate(f'原返回 ({w["returned_gamma"]:.0f},{w["returned_beta"]:.2f})',
                (w['returned_gamma'], w['returned_beta']), xytext=(-108, 16), textcoords='offset points',
                arrowprops=dict(arrowstyle='-', lw=.6, color=base.RETURN), color=base.RETURN, fontsize=5.8)
    ax.axhline(5, color='.75', ls=':', lw=.6)
    ax.text(.02, 5.12, 'β>5：权重取表端点', transform=ax.get_yaxis_transform(), fontsize=5.5, color='.4')
    ax.set_xlim(-25, 1140); ax.set_ylim(.3, 10); ax.set_xticks([0, 500, 1000])
    ax.set_xlabel('候选位置 γ'); ax.set_ylabel('候选形状 β')
    ax.legend([Line2D([], [], color=base.BLUE, lw=1.3), Line2D([], [], color='#4B8B86', lw=1.3, ls='--')],
              [r'形状方程 $T_1=0$', r'位置方程 $T_2=0$'], loc='upper right', fontsize=6)
    return dict(type='joint_residual_zero_contours', sample_id=w['sample_id'], formula_grid_points=w['grid_points'],
                returned_gamma=w['returned_gamma'], returned_beta=w['returned_beta'],
                returned_t1=w['returned_t1'], returned_t2=w['returned_t2'], grid_not_optimizer_iterations=True)


def method_figure(method):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.8))
    rr = [r for r in base.source['curves'] if r['method'] == method]
    panels = []
    for index, (beta, n) in enumerate(base.CONDITIONS):
        ax = axes.flat[index]
        rows = [r for r in rr if r['source'] == 'paired' and r['beta'] == beta and r['n'] == n]
        stat = next(s for s in base.source['summaries'] if s['method'] == method and s['beta'] == beta and s['n'] == n)
        assert len(rows) == 50
        if method == 'mle':
            mle_axis(ax)
            for r in rows: mle_curve(ax, r)
        else:
            base.format_axis(ax, method, 1400)
            for r in rows: base.draw_curve(ax, r, base.BLUE, .18, .65, method)
        text = f'γ中位数 {stat["gamma_median"]:.0f}；γ>500：{stat["gamma_above_truth"]}/{stat["success"]}\nγ=0：{stat["gamma_at_zero"]}；失败：{50-stat["success"]}/50'
        if method == 'mdm':
            q = stat['truth_criterion_quartiles']; text += f'\ng(500)中位数 {q[1]:.3f}；IQR {q[2]-q[0]:.3f}'
        if method == 'wmle' and stat['truth_criterion_count'] < 50:
            text += f'\n真γ处条件方程有定义：{stat["truth_criterion_count"]}/50'
        ax.text(.025, .955, text, transform=ax.transAxes, ha='left', va='top', fontsize=6.0,
                bbox=dict(facecolor='white', edgecolor='none', alpha=.93, pad=2.3), zorder=8)
        ax.set_title(f'β={beta}，n={n}：全部50组', loc='left', pad=9); base.tag(ax, chr(97+index))
        panels.append(dict(beta=beta, n=n, curves=50, successful_returns=stat['success'],
            all_returns_marked_as_rug=True, x_limits=list(ax.get_xlim()), criterion_y_limits=list(ax.get_ylim())))
    ax = axes.flat[3]; chosen = next(r for r in rr if r['source'] == 'original')
    if method in ('lse', 'lre'):
        detail = regression_panel(ax, method); title = '七个样本点与条件回归直线'
    elif method == 'wmle':
        detail = wmle_panel(ax); title = '两条方程零线与原返回'
    else:
        if method == 'mle':
            mle_axis(ax, original=True); mle_curve(ax, chosen, alpha=1., lw=1.4)
        else:
            base.format_axis(ax, method, 1400, original=True)
            base.draw_curve(ax, chosen, base.BLUE, 1., 1.4, method)
        detail = calculation_points(ax, chosen, method)
        gamma = chosen['fit']['gamma_hat']; ax.axvline(gamma, color=base.RETURN, ls='--', lw=.8)
        title = '编号计算点与' + ('阈值交点' if method == 'mdm' else '似然高点')
    ax.set_title(f'原β=5，n=7，组#{chosen["sample_id"]}：{title}', loc='left', pad=9, fontsize=6.6)
    base.tag(ax, 'd')
    fig.suptitle(TITLES[method], x=.095, y=.994, ha='left', fontsize=9, weight='bold')
    fig.text(.095, .943, FORMULAS[method], fontsize=7.0)
    fig.text(.095, .910, SECOND_FORMULAS[method], fontsize=6.6)
    fig.legend([Line2D([], [], color=base.BLUE, lw=1), Line2D([], [], color=base.RETURN, marker='x', lw=0, ms=4),
                Line2D([], [], color='black', ls=':', lw=.9)],
               ['a–c：各组位置准则', 'a–c：实际返回γ（底部短线保留全部返回）', 'a–c：真γ=500'],
               ncol=3, loc='upper center', bbox_to_anchor=(.54, .894), fontsize=6.0, columnspacing=1.0)
    fig.text(.095, .012, 'a→b：同组潜在样本，仅改变β；b→c：样本量条件对照；d：原案例，标记含义随方法说明。', fontsize=6)
    fig.subplots_adjust(left=.105, right=.985, top=.795, bottom=.09, hspace=.59, wspace=.32)
    base.save(fig, base.FILES[method])
    return dict(method=method, file=base.FILES[method], panels=panels, original_sample_id=chosen['sample_id'],
        original_gamma=chosen['fit']['gamma_hat'], original_truth_value=chosen['truth'][1],
        original_returned_value=chosen['returned'][1], png_dimensions=[3240, 2610], original_panel=detail,
        profile_meaning='finite conditional loglik increment' if method == 'mle' else 'saved original criterion',
        formula_printed_on_figure=True)


def main():
    target = DATA / '逐法图核验.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    qa['process_figures'] = [method_figure(method) for method in base.METHODS]
    target.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print('EXPORTED 5 method-specific formula/point figures, PNG/PDF/SVG', flush=True)


if __name__ == '__main__':
    main()
