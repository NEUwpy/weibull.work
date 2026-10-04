"""Figure 1: saved estimates displayed within fixed linear windows.

KDE uses original coordinates and only estimates inside the display window.
Gamma's exact zero mass is shown separately and excluded from the positive KDE.
Full estimates and summary statistics are retained; estimates are unchanged.
"""
import hashlib
import json
import numpy as np
import 绘制逐法分析图 as base
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from scipy.stats import gaussian_kde


def main():
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.4), sharex='col', sharey=True)
    params = [('beta_hat', 5, 'β', [0., 10.], [0., 2., 4., 6., 8., 10.]),
              ('eta_hat', 1000, 'η', [0., 2000.], [0., 500., 1000., 1500., 2000.]),
              ('gamma_hat', 500, 'γ', [0., 1500.], [0., 500., 1000., 1500.])]
    records = []
    for col, (param, truth, label, limits, ticks) in enumerate(params):
        for row, n in enumerate((7, 15)):
            ax = axes[row, col]
            ax.set_xlim(limits); ax.set_ylim(4.65, -.65)
            ax.set_xscale('linear'); ax.set_xticks(ticks)
            ax.xaxis.set_minor_locator(NullLocator())
            ax.axvline(truth, ls='--', color='black', lw=.75, zorder=1)
            tick_labels = []
            for pos, method in enumerate(base.METHODS):
                rows = [r for r in base.old if r['beta'] == 5 and r['n'] == n and r['method'] == method]
                successful = sorted((r for r in rows if r['converged']), key=lambda r: r['sample_id'])
                values = np.array([r[param] for r in successful])
                ids = np.array([r['sample_id'] for r in successful])
                assert len(rows) == 50 and np.isfinite(values).all()
                color = base.COLORS[method]
                zeros = int(np.count_nonzero(values == 0)) if param == 'gamma_hat' else 0
                displayed = (values >= limits[0]) & (values <= limits[1])
                shown_values = values[displayed]
                kde_values = shown_values[shown_values > 0] if param == 'gamma_hat' else shown_values
                grid = np.array([]); density = np.array([])
                if len(kde_values) > 1 and np.ptp(kde_values) > 1e-12:
                    grid = np.linspace(kde_values.min(), kde_values.max(), 256)
                    density = gaussian_kde(kde_values, bw_method='scott')(grid)
                    width = .32*density/density.max()
                    ax.fill_between(grid, pos-width, pos+width, facecolor=color,
                                    edgecolor=color, alpha=.22, linewidth=.6, zorder=2)
                point_y = np.full(len(shown_values), float(pos))
                ax.scatter(shown_values, point_y, s=3.0, color=color, alpha=.65,
                           linewidths=0, zorder=4)
                q25, median, q75 = np.quantile(values, [.25, .5, .75])
                ax.plot([q25, q75], [pos, pos], color='#48515A', lw=.5,
                        solid_capstyle='round', zorder=3)
                ax.scatter(median, pos, marker='D', s=10, facecolor='white',
                           edgecolor='#48515A', linewidth=.5, zorder=5)
                tick_labels.append(base.NAMES[method])
                records.append(dict(n=n, method=method, parameter=param, truth=truth,
                    success=len(values), failure=50-len(values), sample_ids=ids.tolist(),
                    values=values.tolist(), displayed_y=point_y.tolist(),
                    minimum=float(values.min()), maximum=float(values.max()),
                    quartiles=[float(q25), float(median), float(q75)], x_limits=limits,
                    display_values=shown_values.tolist(), display_sample_ids=ids[displayed].tolist(),
                    omitted_values=values[~displayed].tolist(), omitted_sample_ids=ids[~displayed].tolist(),
                    omitted_count=int(np.count_nonzero(~displayed)), x_ticks=ticks, axis_scale=ax.get_xscale(),
                    zero_count=zeros, kde_count=len(kde_values),
                    kde_coordinate='linear', bandwidth='scott',
                    kde_coordinate_grid=grid.tolist(), kde_density=density.tolist(),
                    all_successful_values_preserved_in_source=True,
                    density_limits=[float(kde_values.min()),float(kde_values.max())] if len(kde_values) else None))
            ax.set_yticks(range(5), tick_labels)
            ax.tick_params(axis='y', length=0, pad=5, labelleft=col == 0)
            ax.tick_params(axis='x', labelbottom=True)
            ax.set_xlabel(label)
            if col == 0:
                ax.text(-.28, 1.06, f'n={n}', transform=ax.transAxes,
                        fontsize=7.8, weight='bold')
            ax.text(-.03, 1.06, chr(97+row*3+col), transform=ax.transAxes,
                    fontsize=8, weight='bold', ha='right')
    fig.subplots_adjust(left=.105, right=.985, top=.945, bottom=.12, hspace=.58, wspace=.20)
    for col in range(3):
        assert np.array_equal(axes[0,col].get_xticks(),axes[1,col].get_xticks())
    base.save(fig, '图1_原案例参数分布', formats=('png',))
    source_path = base.HERE/'输入快照'/'原案例估计.json'
    provenance = dict(figure_contract=dict(
        conclusion='原β=5小样本中位置偏高、尺度偏低，并伴随方法间不同的分布和零边界。',
        archetype='quantitative grid', backend='python',
        panels='n=7/15两行，形状/尺度/位置三列，各五方法；仅描述既有估计分布。',
        dimensions_inches=[7.2, 4.4], formats=['PNG 450dpi']),
        input_path=source_path.relative_to(base.HERE.parent).as_posix(),
        input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        description='Fixed linear display windows; complete saved estimates and summaries retained. No new fits.',
        point_layout='centerline_without_jitter', iqr_linewidth_points=.5,
        annotations='Panel letters, method names, parameter axes and n only; statistics and marker definitions are in the report caption.',
        density='Gaussian KDE with Scott bandwidth on displayed original-coordinate values, restricted to their observed range; zero gamma excluded from KDE.',
        summary_source='all successful estimates', density_source='displayed successful estimates',
        tail_extension=False, shared_ticks_within_parameter=True,
        width='Each violin independently normalized to maximum half-width 0.32; width is not a success count.',
        png_dimensions=[3240, 1980], panels=records)
    target = base.DATA/'图1小提琴数据与核验.json'
    target.write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    qa_path = base.DATA/'逐法图核验.json'
    checks = json.loads(qa_path.read_text(encoding='utf-8'))
    checks.pop('ecdf', None)
    detailed_fields = {'sample_ids', 'values', 'displayed_y', 'display_values', 'display_sample_ids',
                      'omitted_values', 'omitted_sample_ids', 'kde_coordinate_grid', 'kde_density'}
    checks['violin'] = [{k: v for k, v in r.items() if k not in detailed_fields} for r in records]
    checks['distribution_figure'] = dict(type='violin_with_fixed_linear_windows', png_dimensions=provenance['png_dimensions'],
                                      source_data_file=target.name)
    qa_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('EXPORTED Figure 1: 6 linear panels, 30 method distributions, PNG only; full estimates retained.')


if __name__ == '__main__':
    main()
