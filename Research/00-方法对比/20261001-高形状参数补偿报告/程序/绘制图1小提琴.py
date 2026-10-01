"""Figure 1 revision: archived estimates, violin densities and all raw points.

KDE uses log10 coordinates for positive beta/eta, linear coordinates for gamma.
Gamma's exact zero mass is shown separately and excluded from the positive KDE.
All points lie on their method's centerline; estimates are unchanged.
"""
import hashlib
import json
import numpy as np
import 绘制逐法分析图 as base
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import gaussian_kde


def main():
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.2))
    params = [('beta_hat', 5, '形状估计 β', True),
              ('eta_hat', 1000, '尺度估计 η', True),
              ('gamma_hat', 500, '位置估计 γ', False)]
    records = []
    for col, (param, truth, label, logarithmic) in enumerate(params):
        pooled = np.array([r[param] for r in base.old if r['beta'] == 5 and
                           r['n'] in (7, 15) and r['method'] in base.METHODS and r['converged']])
        limits = [float(pooled.min()*.80), float(pooled.max()*1.20)] if logarithmic else [-95., float(pooled.max()*1.08)]
        for row, n in enumerate((7, 15)):
            ax = axes[row, col]
            ax.set_xlim(limits); ax.set_ylim(4.65, -.65)
            if logarithmic:
                ax.set_xscale('log')
            ax.axvline(truth, ls='--', color='black', lw=.85, zorder=1)
            tick_labels = []
            for pos, method in enumerate(base.METHODS):
                rows = [r for r in base.old if r['beta'] == 5 and r['n'] == n and r['method'] == method]
                successful = sorted((r for r in rows if r['converged']), key=lambda r: r['sample_id'])
                values = np.array([r[param] for r in successful])
                ids = np.array([r['sample_id'] for r in successful])
                assert len(rows) == 50 and np.isfinite(values).all()
                color = base.COLORS[method]
                zeros = int(np.count_nonzero(values == 0)) if param == 'gamma_hat' else 0
                kde_values = values[values > 0] if param == 'gamma_hat' else values
                coords = np.log10(kde_values) if logarithmic else kde_values
                grid = np.linspace(coords.min(), coords.max(), 256)
                density = gaussian_kde(coords, bw_method='scott')(grid)
                width = .34*density/density.max()
                displayed_grid = 10**grid if logarithmic else grid
                ax.fill_between(displayed_grid, pos-width, pos+width, facecolor=color,
                                edgecolor=color, alpha=.22, linewidth=.65, zorder=2)
                point_y = np.full(len(values), float(pos))
                ax.scatter(values, point_y, s=3.0, color=color, alpha=.65,
                           linewidths=0, zorder=4)
                q25, median, q75 = np.quantile(values, [.25, .5, .75])
                ax.plot([q25, q75], [pos, pos], color='#48515A', lw=.55,
                        solid_capstyle='round', zorder=3)
                ax.scatter(median, pos, marker='D', s=10, facecolor='white',
                           edgecolor='#48515A', linewidth=.55, zorder=5)
                if zeros:
                    ax.annotate(f'0：{zeros}个', (0, pos), xytext=(-5, 0),
                                textcoords='offset points', fontsize=5.4, color=color, ha='right', va='center',
                                bbox=dict(facecolor='white', edgecolor='none', alpha=.9, pad=.4), zorder=6)
                tick_labels.append(f'{base.NAMES[method]}  {len(values)}/{50-len(values)}')
                records.append(dict(n=n, method=method, parameter=param, truth=truth,
                    success=len(values), failure=50-len(values), sample_ids=ids.tolist(),
                    values=values.tolist(), displayed_y=point_y.tolist(),
                    minimum=float(values.min()), maximum=float(values.max()),
                    quartiles=[float(q25), float(median), float(q75)], x_limits=limits,
                    zero_count=zeros, kde_count=len(kde_values),
                    kde_coordinate='log10' if logarithmic else 'linear', bandwidth='scott',
                    kde_coordinate_grid=grid.tolist(), kde_density=density.tolist(),
                    all_successful_values_included=True))
            ax.set_yticks(range(5), tick_labels if col == 0 else ['']*5)
            ax.tick_params(axis='y', length=0, pad=5)
            if not logarithmic:
                ax.set_xticks([0, 500, 1000, 1500])
            ax.set_xlabel(label + ('（对数轴）' if logarithmic else ''))
            ax.set_title(f'{label}；真值 {truth}', loc='left', pad=7, fontsize=7.1)
            if col == 0:
                ax.text(-.53, 1.18, f'n={n}，每方法50组', transform=ax.transAxes,
                        fontsize=7.8, weight='bold')
            ax.text(-.03, 1.045, chr(97+row*3+col), transform=ax.transAxes,
                    fontsize=8, weight='bold', ha='right')
    fig.suptitle('原β=5：位置偏高与尺度偏低同时出现', x=.02, y=.986,
                 ha='left', fontsize=9, weight='bold')
    fig.legend([Line2D([], [], marker='o', color='.45', ls='', ms=1.8),
                Line2D([], [], marker='D', markerfacecolor='white', color='#48515A', ls='', ms=3.0, markeredgewidth=.55),
                Line2D([], [], color='#48515A', lw=.55), Line2D([], [], color='black', ls='--', lw=.85)],
               ['每个成功估计', '中位数', '第25–75百分位', '真值'], ncol=4,
               loc='upper center', bbox_to_anchor=(.55, .939), fontsize=6.4, columnspacing=1.8)
    fig.text(.02, .017, '左侧数字为成功/失败；宽度表示平滑密度（每把独立归一）；γ=0单列个数，失败不补值。', fontsize=6)
    fig.subplots_adjust(left=.165, right=.985, top=.805, bottom=.105, hspace=.63, wspace=.20)
    base.save(fig, '图1_原案例参数分布')
    source_path = base.HERE/'输入快照'/'原案例估计.json'
    provenance = dict(figure_contract=dict(
        conclusion='原β=5小样本中位置偏高、尺度偏低，并伴随方法间不同的分布和零边界。',
        archetype='quantitative grid', backend='python',
        panels='n=7/15两行，形状/尺度/位置三列，各五方法；仅描述既有估计分布。',
        dimensions_inches=[7.2, 5.2], formats=['PNG 450dpi', 'PDF embedded TrueType', 'SVG live text']),
        input_path=source_path.relative_to(base.HERE.parent).as_posix(),
        input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        description='All successful archived estimates aligned on their method centerline. No new fits.',
        point_layout='centerline_without_jitter', iqr_linewidth_points=.55,
        density='Gaussian KDE with Scott bandwidth, restricted to observed range. log10 beta/eta; linear positive gamma; zero gamma excluded from KDE and counted separately.',
        width='Each violin independently normalized to maximum half-width 0.34; width is not a success count.',
        png_dimensions=[3240, 2340], panels=records)
    target = base.DATA/'图1小提琴数据与核验.json'
    target.write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    qa_path = base.DATA/'逐法图核验.json'
    checks = json.loads(qa_path.read_text(encoding='utf-8'))
    checks.pop('ecdf', None)
    detailed_fields = {'sample_ids', 'values', 'displayed_y', 'kde_coordinate_grid', 'kde_density'}
    checks['violin'] = [{k: v for k, v in r.items() if k not in detailed_fields} for r in records]
    checks['distribution_figure'] = dict(type='violin_with_all_points', png_dimensions=provenance['png_dimensions'],
                                      source_data_file=target.name)
    qa_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('EXPORTED Figure 1 violin: 6 panels, 30 method distributions, all successful estimates, PNG/PDF/SVG')


if __name__ == '__main__':
    main()
