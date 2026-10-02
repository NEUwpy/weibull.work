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


def profile_values(r, method):
    if method == 'mle':
        return [p[5]-r['truth'][5] if p[5] is not None else np.nan for p in r['points']]
    return [p[1] if p[1] is not None else np.nan for p in r['points']]


def mle_axis(ax, original=False):
    ax.set_xlim(-25, 1400); ax.set_xticks([0, 500, 1000]); ax.set_xlabel('γ')
    ax.set_ylabel(r'$\Delta\ell(\gamma)$')
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
    pts = POINTS['cases_by_beta'][str(r['beta'])]['evaluation_points'][method]
    defined = [p for p in pts['points'] if p['value'] is not None]
    ax.scatter([p['gamma'] for p in defined], [p['value'] for p in defined], s=5,
               facecolor='white', edgecolor=base.BLUE, linewidth=.45, alpha=.75, zorder=3)
    selected = [pts['true_gamma_point_id'], pts['returned_gamma_point_id']]
    for pid in selected:
        p = next(p for p in defined if p['id'] == pid)
        if pid == pts['true_gamma_point_id']:
            text, offset = pid, (10, -22 if method == 'mle' else 18)
        elif pid == pts['returned_gamma_point_id']:
            text, offset = pid, (-24, -17 if method == 'mle' else 12)
        ax.annotate(text, (p['gamma'], p['value']), xytext=offset, textcoords='offset points',
                    fontsize=5.8, color=base.RETURN if pid == pts['returned_gamma_point_id'] else base.BLUE,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.86, pad=.4), zorder=6)
    return dict(type='numbered_formula_evaluations', plotted_defined_points=len(defined),
                total_points=len(pts['points']), labelled_point_ids=selected,
                true_gamma_point_id=pts['true_gamma_point_id'], returned_gamma_point_id=pts['returned_gamma_point_id'])


def regression_panel(ax, method, beta):
    case = POINTS['cases_by_beta'][str(beta)]['regressions'][method]
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
    ax.set_xlabel(r'$z_i$' if method == 'lse' else r'$X_i(\gamma)$')
    ax.set_ylabel(r'$y_i(\gamma)$' if method == 'lse' else r'$Y_i$')
    ds0, ds1 = case['datasets']
    ax.legend([Line2D([], [], color=base.BLUE, ls='--', marker='o', ms=3),
               Line2D([], [], color=base.RETURN, ls='-', marker='s', ms=3)],
              [f'γ=500', f'γ={ds1["gamma"]:.0f}'],
              loc='upper left', fontsize=5.5, handlelength=1.7)
    ax.margins(x=.13, y=.20)
    return dict(type='observed_regression_points', sample_id=case['sample_id'],
                observations=7, transformed_points=14, all_observation_ids_labelled=True,
                returned_gamma=ds1['gamma'], loss_true_gamma=ds0['loss'], loss_returned_gamma=ds1['loss'])


def wmle_panel(ax, beta):
    w = POINTS['cases_by_beta'][str(beta)]['wmle']; gg, bb = np.array(w['gamma_grid']), np.array(w['beta_grid'])
    ax.contour(gg, bb, np.array(w['t1']), levels=[0], colors=[base.BLUE], linewidths=1.3)
    ax.contour(gg, bb, np.array(w['t2']), levels=[0], colors=['#4B8B86'], linewidths=1.3, linestyles='--')
    ax.scatter(w['truth_gamma'], w['truth_beta'], s=28, color='black', marker='D', zorder=5)
    ax.scatter(w['returned_gamma'], w['returned_beta'], s=34, color=base.RETURN, marker='x', linewidth=1.2, zorder=6)
    ax.axhline(5, color='.75', ls=':', lw=.6)
    ax.set_xlim(-25, 1140); ax.set_ylim(.3, 10); ax.set_xticks([0, 500, 1000])
    ax.set_xlabel('γ'); ax.set_ylabel('β')
    ax.legend([Line2D([], [], color=base.BLUE, lw=1.3), Line2D([], [], color='#4B8B86', lw=1.3, ls='--')],
              [r'$T_1=0$', r'$T_2=0$'], loc='upper right', fontsize=6)
    return dict(type='joint_residual_zero_contours', sample_id=w['sample_id'], formula_grid_points=w['grid_points'],
                returned_gamma=w['returned_gamma'], returned_beta=w['returned_beta'],
                returned_t1=w['returned_t1'], returned_t2=w['returned_t2'], grid_not_optimizer_iterations=True)


def method_figure(method):
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.2))
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
        ax.set_title(f'β={beta}，n={n}', loc='left', pad=9); base.tag(ax, chr(97+index))
        panels.append(dict(beta=beta, n=n, curves=50, successful_returns=stat['success'],
            all_returns_marked_as_rug=True, x_limits=list(ax.get_xlim()), criterion_y_limits=list(ax.get_ylim())))
    singles = []
    for index, beta in enumerate((2,5),4):
        ax = axes.flat[index]
        chosen = next(r for r in rr if r['source'] == 'original' and r['beta'] == beta)
        if method in ('lse', 'lre'):
            detail = regression_panel(ax, method, beta)
        elif method == 'wmle':
            detail = wmle_panel(ax, beta)
        else:
            if method == 'mle':
                mle_axis(ax, original=True)
                peak = chosen['returned'][5]-chosen['truth'][5]
                ax.set_ylim(-.10, max(.067, peak*1.25))
                mle_curve(ax, chosen, alpha=1., lw=1.4)
            else:
                base.format_axis(ax, method, 1400, original=True)
                v = chosen['truth'][1]
                ax.set_ylim(min(-.04, v-.04), max(.23, v+.04))
                base.draw_curve(ax, chosen, base.BLUE, 1., 1.4, method)
            detail = calculation_points(ax, chosen, method)
            gamma = chosen['fit']['gamma_hat']; ax.axvline(gamma, color=base.RETURN, ls='--', lw=.8)
        ax.set_title(f'β={beta}，n=7', loc='left', pad=9)
        base.tag(ax, chr(97+index))
        singles.append(dict(beta=beta, sample_id=chosen['sample_id'], gamma=chosen['fit']['gamma_hat'],
                            criterion_y_limits=list(ax.get_ylim()), detail=detail))
    fig.subplots_adjust(left=.105, right=.985, top=.945, bottom=.075, hspace=.64, wspace=.32)
    base.save(fig, base.FILES[method])
    return dict(method=method, file=base.FILES[method], panels=panels, original_panels=singles,
        png_dimensions=[3240, 3240],
        profile_meaning='finite conditional loglik increment' if method == 'mle' else 'saved original criterion',
        formula_printed_on_figure=False, formula_documented_in_report=True,
        notes_location='report text and figure caption')


def main():
    target = DATA / '逐法图核验.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    qa['process_figures'] = [method_figure(method) for method in base.METHODS]
    target.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print('EXPORTED 5 method-specific formula/point figures, PNG/PDF/SVG', flush=True)


if __name__ == '__main__':
    main()
