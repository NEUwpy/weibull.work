"""读取Study04现有CSV，绘制偏差与稳定性试图；不抽样、不调用估计器。"""
import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from studies.common.metrics import summarize_standard_errors
from 分析现有结果 import analyze_cell, export_analysis

PARAMETERS = [('beta', 'β', '形状估计'), ('eta', 'η', '尺度估计'), ('gamma', 'γ', '位置估计')]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(fig, output, stem, config, audit):
    # 实际渲染后检查图例边界。
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist in fig.legends:
        if artist is not None:
            box = artist.get_window_extent(renderer)
            assert box.x0 >= 0 and box.y0 >= 0 and box.x1 <= fig.bbox.width and box.y1 <= fig.bbox.height
    for suffix in config['formats']:
        path = output / f'{stem}.{suffix}'
        # 先完整写入临时文件，再替换成图，避免直接截断正在预览的图片。
        with tempfile.NamedTemporaryFile(dir=output, suffix=f'.{suffix}', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            fig.savefig(temporary, dpi=config['dpi'], facecolor='white')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        audit['outputs'][path.name] = dict(sha256=sha(path), bytes=path.stat().st_size)
    plt.close(fig)


def source_tables(config, audit):
    paths = sorted((STUDY / '结果').glob('W*/条件汇总.csv'))
    assert len(paths) == 8
    for path in paths:
        audit['sources'][str(path.relative_to(STUDY))] = sha(path)
    table = pd.concat([pd.read_csv(path, float_precision='round_trip') for path in paths], ignore_index=True)
    assert len(table) == 280 and not table.duplicated(['beta', 'n', 'method']).any()
    assert set(table['method']) == {method['id'] for method in config['methods']}
    assert table['total'].eq(1200).all() and (table['success'] + table['failure']).eq(table['total']).all()
    assert table['eta'].eq(1000).all() and table['gamma'].eq(500).all()
    assert table.groupby(['beta', 'n']).size().eq(7).all()
    audit['input_grid'] = dict(conditions=40, methods=7, repeats=1200,
                              beta=sorted(table.beta.unique().tolist()),
                              sample_sizes=sorted(table.n.unique().tolist()))
    return table


def selected_distributions(config, table, audit, analysis):
    records = {}
    for beta in config['distribution_beta']:
        for n in config['sample_sizes']:
            folder = STUDY / '结果' / f'W{beta:g},1000,500'
            paths = [folder / sub / f'n{n}.csv' for sub in ['原始样本', '估计结果']]
            for path in paths:
                audit['sources'][str(path.relative_to(STUDY))] = sha(path)
            samples, estimates = [pd.read_csv(path, float_precision='round_trip') for path in paths]
            assert len(samples) == len(estimates) == 1200
            assert samples['样本编号'].tolist() == estimates['样本编号'].tolist() == list(range(1200))
            assert np.array_equal(samples.to_numpy(), estimates[samples.columns].to_numpy())
            summary = table[(table.beta == beta) & (table.n == n)].set_index('method')
            arrays, valid_masks = {}, {}
            for method in config['methods']:
                name = method['id']
                status = estimates[f'{name}_状态']
                assert set(status) <= {'success', 'failure'}
                valid = estimates.loc[status.eq('success')]
                valid_masks[name] = status.eq('success').to_numpy()
                arrays[name] = estimates[[f'{name}_{field}' for _, _, field in PARAMETERS]].to_numpy(dtype=float)
                row = summary.loc[name]
                assert len(valid) == row['success']
                for param, _, field in PARAMETERS:
                    values = valid[f'{name}_{field}'].to_numpy(dtype=float)
                    assert np.isfinite(values).all()
                    # 调用共享指标只作读图验真；正式曲线直接使用已保存的指标。
                    stats = summarize_standard_errors(values - float(row[param]))
                    for metric in ['bias', 'sd', 'rmse', 'mae']:
                        assert np.isclose(stats[metric], row[f'{param}_{metric}'], rtol=1e-11, atol=1e-10)
                    audit['metric_crosschecks'] += 4
                    records[(beta, n, name, param)] = (values, row)
            analyze_cell(beta, n, estimates, arrays, valid_masks, config, analysis)
    return records


def distribution_figure(beta, records, config, output, audit):
    ns, methods = config['sample_sizes'], config['methods']
    fig, axes = plt.subplots(len(ns), len(PARAMETERS), figsize=(15.2, 2.7*len(ns)+.8), squeeze=False)
    fig.subplots_adjust(left=.12, right=.98, bottom=.05, top=.94, wspace=.22, hspace=.42)
    legend = [Line2D([], [], color='#222222', ls='--', lw=1, label='真值'),
              Line2D([], [], marker='o', color='#C52E42', ls='', ms=5, label='均值'),
              Line2D([], [], marker='D', markerfacecolor='white', markeredgecolor='#333333',
                     color='none', ms=5, label='中位数'),
              Line2D([], [], color='#333333', lw=2, label='四分位区间')]
    fig.legend(handles=legend, ncol=4, loc='upper center', bbox_to_anchor=(.53, .995), frameon=False)
    for row, n in enumerate(ns):
        for col, (param, symbol, _) in enumerate(PARAMETERS):
            ax = axes[row, col]
            lower, upper = config['display_windows'][param]
            truth = beta if param == 'beta' else (1000 if param == 'eta' else 500)
            ax.set(xlim=(lower, upper), ylim=(len(methods)-.4, -.6), xlabel=f'{symbol}估计值')
            ax.set_xticks(config['display_ticks'][param])
            ax.axvline(truth, color='#222222', ls='--', lw=1, zorder=1)
            labels = []
            for pos, method in enumerate(methods):
                values, summary = records[(beta, n, method['id'], param)]
                visible = values[(values >= lower) & (values <= upper)]
                kde_values = visible[visible > 0] if param == 'gamma' else visible
                if len(kde_values) > 1 and np.ptp(kde_values) > 1e-12:
                    grid = np.linspace(kde_values.min(), kde_values.max(), 256)
                    density = gaussian_kde(kde_values, bw_method='scott')(grid)
                    width = .31 * density / density.max()
                    ax.fill_between(grid, pos-width, pos+width, color=method['color'], alpha=.2, lw=.7)
                ax.scatter(visible, np.full(len(visible), pos), s=2.4, alpha=.12,
                           color=method['color'], linewidths=0, zorder=3, rasterized=True)
                q1, median, q3 = np.quantile(values, [.25, .5, .75])
                mean = truth + float(summary[f'{param}_bias'])
                ax.plot([q1, q3], [pos, pos], color='#444444', lw=1.5, solid_capstyle='round', zorder=4)
                for value, marker, face in [(median, 'D', 'white'), (mean, 'o', '#C52E42')]:
                    if lower <= value <= upper:
                        ax.scatter(value, pos, marker=marker, s=23, facecolor=face,
                                   edgecolor='#333333' if marker == 'D' else 'white', lw=.6, zorder=6)
                left, right = int(np.sum(values < lower)), int(np.sum(values > upper))
                labels.append(method['label'])
                audit['distributions'].append(dict(beta=beta, n=n, method=method['id'], parameter=param,
                    valid=len(values), failure=int(summary['failure']), mean=mean, median=float(median),
                    q1=float(q1), q3=float(q3), sd=float(summary[f'{param}_sd']),
                    minimum=float(values.min()), maximum=float(values.max()),
                    displayed=len(visible), below_window=left, above_window=right,
                    gamma_zero_count=int(np.sum(values == 0)) if param == 'gamma' else 0))
            ax.set_yticks(range(len(methods)), labels if col == 0 else [''] * len(methods))
            ax.tick_params(axis='y', length=0, labelsize=9)
            ax.tick_params(axis='x', labelsize=10)
            if col == 0:
                ax.text(-.12, 1.04, f'n={n}', transform=ax.transAxes,
                        fontsize=11, fontweight='bold', ha='right', va='bottom')
            ax.text(-.055, 1.04, chr(97+row*len(PARAMETERS)+col), transform=ax.transAxes, fontweight='bold', fontsize=11)
    save(fig, output, f'01_估计值分布_β{beta:g}', config, audit)


def method_legend(fig, config, y=.995):
    handles = [Line2D([], [], color=m['color'], marker=m['marker'], ls=m['linestyle'],
                      lw=1.3, ms=4.5, label=m['label']) for m in config['methods']]
    fig.legend(handles=handles, ncol=7, loc='upper center', bbox_to_anchor=(.52, y),
               frameon=False, fontsize=10, columnspacing=1.6, handlelength=2.3)


def trend_series(ax, subset, param, metric, config, audit, panel):
    for method in config['methods']:
        group = subset[subset.method.eq(method['id'])].sort_values('beta')
        xs = group.beta.to_numpy()
        ys = group[f'{param}_{metric}'].to_numpy()
        assert len(group) == 8 and np.isfinite(ys).all()
        ax.plot(xs, ys, color=method['color'], ls=method['linestyle'], marker=method['marker'],
                lw=1.25, ms=4, markeredgewidth=.5, label=method['label'])
        counts = group['success'] if 'success' in group else group['effective_count']
        audit['trend_series'].append(dict(panel=panel, method=method['id'], x=xs.tolist(), y=ys.tolist(),
                                         effective_counts=counts.tolist()))
    ax.set_xlim(1.4, 5.1)
    ax.set_xticks([1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5])
    ax.tick_params(labelsize=9)
    ax.grid(axis='y', color='#E9E9E9', lw=.55, zorder=0)
    ax.axhline(0, color='#555555', ls='--', lw=.8)


def metric_figure(metric, table, config, output, audit, stem=None):
    ns = config['sample_sizes']
    selected = table[table.n.isin(ns)]
    fig, axes = plt.subplots(len(ns), 3, figsize=(15.2, 2.7*len(ns)+.8), squeeze=False)
    fig.subplots_adjust(left=.09, right=.975, top=.94, bottom=.05, wspace=.30, hspace=.45)
    method_legend(fig, config)
    for col, (param, symbol, _) in enumerate(PARAMETERS):
        if param == 'beta' and metric in config['shape_focus']:
            limits = config['shape_focus'][metric]
        else:
            values = selected[f'{param}_{metric}'].to_numpy()
            if metric == 'bias':
                extent = np.ceil(max(abs(values.min()), abs(values.max())) / 100) * 100
                limits = [-extent, extent]
            else:
                step = 5 if param == 'beta' else 100
                limits = [0, np.ceil(values.max() / step) * step]
        for row, n in enumerate(ns):
            ax = axes[row, col]
            subset = table[table.n.eq(n)]
            panel = f'{stem or metric}:{param}:n{n}'
            trend_series(ax, subset, param, metric, config, audit, panel)
            ax.set_ylim(limits)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.set_xlabel('真实形状参数 β', fontsize=10)
            label = {'bias':'Bias', 'sd':'SD', 'rmse':'RMSE', 'q95_abs':'P95绝对误差'}[metric]
            ax.set_ylabel(f'{symbol} {label}', fontsize=11)
            if col == 0:
                ax.text(-.12, 1.04, f'n={n}',
                        transform=ax.transAxes, fontsize=10, fontweight='bold', ha='right', va='bottom')
            ax.text(-.055, 1.04, chr(97+row*3+col), transform=ax.transAxes, fontweight='bold', fontsize=11)
            outside = subset[(subset[f'{param}_{metric}'] < limits[0]) | (subset[f'{param}_{metric}'] > limits[1])]
            if not outside.empty:
                # 窗外指标仅记录于核验文件，不在图的边界增加投影标记。
                audit['outside_trend_window'].append(dict(panel=panel, count=len(outside),
                    points=outside[['beta', 'n', 'method', f'{param}_{metric}']].to_dict('records')))
    stem = stem or {'bias':'02_Bias趋势', 'sd':'03_SD趋势', 'rmse':'05_RMSE趋势', 'q95_abs':'11_P95绝对误差'}[metric]
    save(fig, output, stem, config, audit)


def full_shape_figure(table, config, output, audit):
    ns = config['sample_sizes']
    fig, axes = plt.subplots(len(ns), 3, figsize=(15.2, 2.7*len(ns)+.8), squeeze=False)
    fig.subplots_adjust(left=.09, right=.975, bottom=.05, top=.94, wspace=.30, hspace=.45)
    method_legend(fig, config)
    for col, metric in enumerate(['bias', 'sd', 'rmse']):
        values = table[table.n.isin(ns)][f'beta_{metric}']
        if metric == 'bias':
            limits = [np.floor(min(0, values.min())/5)*5, np.ceil(max(0, values.max())/5)*5]
        else:
            limits = [0, np.ceil(values.max()/100)*100]
        for row, n in enumerate(ns):
            ax = axes[row, col]
            trend_series(ax, table[table.n.eq(n)], 'beta', metric, config, audit, f'full:{metric}:n{n}')
            ax.set_ylim(limits)
            ax.set_xlabel('真实形状参数 β', fontsize=10)
            ax.set_ylabel(f'β {"Bias" if metric == "bias" else metric.upper()}', fontsize=11)
            if col == 0:
                ax.text(-.12, 1.04, f'n={n}', transform=ax.transAxes,
                        fontsize=10, fontweight='bold', ha='right', va='bottom')
            ax.text(-.055, 1.04, chr(97+row*3+col), transform=ax.transAxes, fontweight='bold', fontsize=11)
    save(fig, output, '04_形状指标全范围', config, audit)


def rate_heatmap(risk, value, stem, config, output, audit):
    selected = risk[risk.factor.eq(3)]
    methods, ns = config['methods'], config['sample_sizes']
    betas = sorted(selected.beta.unique())
    maximum = 100 if value == 'success_rate' else max(5, np.ceil(selected[value].max()*100/5)*5)
    fig, axes = plt.subplots(2, 4, figsize=(15.2, 7.1))
    fig.subplots_adjust(left=.05, right=.925, bottom=.10, top=.93, wspace=.30, hspace=.58)
    for index, method in enumerate(methods):
        ax = axes.flat[index]
        group = selected[selected.method.eq(method['id'])]
        values = group.pivot(index='n', columns='beta', values=value).loc[ns, betas].to_numpy()*100
        mesh = ax.imshow(values, aspect='auto', vmin=0, vmax=maximum,
                         cmap='Blues' if value == 'success_rate' else 'YlOrRd', interpolation='none')
        for row in range(len(ns)):
            for col in range(len(betas)):
                number = values[row, col]
                ax.text(col, row, f'{number:.1f}', ha='center', va='center', fontsize=7,
                        color='white' if number/maximum > .57 else '#222222')
        ax.set_xticks(range(len(betas)), [f'{b:g}' for b in betas], fontsize=8)
        ax.set_yticks(range(len(ns)), ns, fontsize=8)
        ax.set(xlabel='真实形状参数 β', ylabel='n')
        ax.set_title(method['label'], fontsize=11, pad=7)
    axes.flat[-1].set_visible(False)
    color_axis = fig.add_axes([.95, .17, .012, .62])
    bar = fig.colorbar(mesh, cax=color_axis)
    bar.set_label({'success_rate':'有效率（%）', 'anomaly_valid_rate':'形状异常频率（%）',
                   'gamma_zero_valid_rate':'位置估计为0的频率（%）'}[value], fontsize=10)
    save(fig, output, stem, config, audit)


def anomaly_sensitivity(risk, config, output, audit):
    ns, factors = config['sample_sizes'], config['anomaly_factors']
    fig, axes = plt.subplots(len(ns), len(factors), figsize=(15.2, 2.7*len(ns)+.8), squeeze=False)
    fig.subplots_adjust(left=.09, right=.975, bottom=.05, top=.92, wspace=.30, hspace=.45)
    method_legend(fig, config)
    maximum = max(5, np.ceil(risk.anomaly_valid_rate.max()*100/5)*5)
    for row, n in enumerate(ns):
        for col, factor in enumerate(factors):
            ax = axes[row, col]
            for method in config['methods']:
                data = risk[(risk.n == n) & (risk.factor == factor) & (risk.method == method['id'])].sort_values('beta')
                ax.plot(data.beta, data.anomaly_valid_rate*100, color=method['color'], ls=method['linestyle'],
                        marker=method['marker'], ms=4, lw=1.25)
            ax.set(xlim=(1.4, 5.1), ylim=(0, maximum), xlabel='真实形状参数 β', ylabel='形状异常频率（%）')
            ax.set_xticks([1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5])
            ax.grid(axis='y', color='#E9E9E9', lw=.55)
            if row == 0:
                ax.set_title(f'k={factor}', fontsize=12, pad=10)
            if col == 0:
                ax.text(-.12, 1.04, f'n={n}', transform=ax.transAxes,
                        fontsize=10, fontweight='bold', ha='right', va='bottom')
    save(fig, output, '08_形状异常阈值敏感性', config, audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=HERE / '绘图配置.json')
    parser.add_argument('--output', type=Path, default=HERE / '图片')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
        'font.size':10, 'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
        'axes.linewidth':.75, 'savefig.facecolor':'white'})
    audit = dict(created_at=datetime.now(timezone.utc).isoformat(), sources={}, outputs={}, distributions=[],
                 trend_series=[], outside_trend_window=[], metric_crosschecks=0,
                 program_sha256=sha(Path(__file__)), config_sha256=sha(args.config),
                 analysis_program_sha256=sha(HERE/'分析现有结果.py'),
                 metric_program_sha256=sha(ROOT/'python/studies/common/metrics.py'),
                 mm_diagnostic_program_sha256=sha(ROOT/'python/methods/mm.py'),
                 scope='现有估计结果的描述性再分析；不抽样、不拟合；自身有效与七法共同有效分别计算',
                 kde='Scott，线性坐标，窗口内样本；gamma=0单列散点；各轮廓独立归一化，宽度不代表成功数')
    table = source_tables(config, audit)
    analysis = dict(metrics=[], risk=[], common_counts=[], tail_cases=[], paired=[])
    records = selected_distributions(config, table, audit, analysis)
    metrics, risk, counts = export_analysis(analysis, HERE/'分析数据', config)
    own = metrics[metrics.subset.eq('own')]
    common = metrics[metrics.subset.eq('common')]
    saved_risk = risk[risk.factor.eq(3)].set_index(['beta', 'n', 'method'])
    for item in table.itertuples():
        assert np.isclose(item.shape_anomaly_rate, saved_risk.loc[(item.beta, item.n, item.method), 'anomaly_valid_rate'], atol=1e-12)
    for beta in config['distribution_beta']:
        distribution_figure(beta, records, config, output, audit)
    for metric in ['bias', 'sd', 'rmse']:
        metric_figure(metric, table, config, output, audit)
    full_shape_figure(table, config, output, audit)
    rate_heatmap(risk, 'success_rate', '06_有效率', config, output, audit)
    rate_heatmap(risk, 'anomaly_valid_rate', '07_形状异常频率', config, output, audit)
    anomaly_sensitivity(risk, config, output, audit)
    rate_heatmap(risk, 'gamma_zero_valid_rate', '09_零位置边界频率', config, output, audit)
    metric_figure('rmse', common, config, output, audit, stem='10_共同有效样本RMSE')
    metric_figure('q95_abs', own, config, output, audit)
    audit['common_valid_counts'] = counts.to_dict('records')
    audit['analysis_tables'] = dict(metrics=len(metrics), risk=len(risk), common_counts=len(counts))
    assert all(sha(STUDY / path) == digest for path, digest in audit['sources'].items()), '绘图期间源数据变化'
    audit['source_files_unchanged'] = True
    audit['result'] = 'passed'
    (output / '绘图核验.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(result='passed', figures=len(audit['outputs']),
        source_files=len(audit['sources']), metric_crosschecks=audit['metric_crosschecks'],
        distribution_panels=len(audit['distributions'])//len(config['methods']),
        source_files_unchanged=True), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
