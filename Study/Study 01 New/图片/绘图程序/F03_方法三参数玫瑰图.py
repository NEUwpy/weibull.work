"""E09 shared-valid-sample parameter RMSE; editable vector exports."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / '数据/E09_六方法共同测试/per_sample.csv.gz'
STEM = 'F03_方法三参数玫瑰图'
METHODS = ['AMDM', 'MDM-0.1', 'WMLE', 'LSE', 'LRE', 'MLE']
LABELS = ['AMDM', 'MDM (δ = 0.1)', 'WMLE', 'LSE', 'LRE', 'MLE']
PARAMS = ['beta', 'eta', 'gamma']
SYMBOLS = ['β', 'η', 'γ']
COLORS = ['#648BB0', '#DEA273', '#88B5A4']


SAMPLE_SIZES = [7, 10, 15, 20]


def draw_panel(ax, data, extent, ticks):
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    radial = lambda v: np.asarray(v)
    ax.set_ylim(0, extent*1.20)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['polar'].set_visible(False)
    angle = np.linspace(0, 2*np.pi, 720)
    # Method sectors retain equal angular widths; all panels use an identical linear radial scale.
    step = 360/len(METHODS)
    for i in range(len(METHODS)):
        center = np.deg2rad(step/2 + step*i)
        ax.bar(center, extent, width=np.deg2rad(step-4), color='#F4F7F9', edgecolor='none', zorder=0)
    for tick in ticks:
        radius = radial(tick)
        ax.plot(angle, np.full_like(angle, radius), color='#D8E0E6', lw=.65, zorder=1)
        ax.text(0, radius, f'{tick:g}', ha='center', va='center', color='#77828C',
                fontsize=7, bbox=dict(facecolor='white', edgecolor='none', pad=.4), zorder=5)
    for i, (method, label) in enumerate(zip(METHODS, LABELS)):
        center = np.deg2rad(step/2 + step*i)
        for j, param in enumerate(PARAMS):
            theta = center + np.deg2rad((j-1)*step*.265)
            value = float(data.loc[(data.method == method) & (data.parameter == param), 'rmse'].iloc[0])
            ax.bar(theta, radial(value), width=np.deg2rad(step*.235), color=COLORS[j],
                   edgecolor='white', linewidth=1, zorder=3)
            label_r = max(radial(value)+extent*.04, extent*.64)
            if label_r > radial(value)+extent*.06:
                ax.plot([theta, theta], [radial(value)+extent*.01, label_r-extent*.035],
                        color=COLORS[j], lw=.65, zorder=4)
            ax.text(theta, label_r, f'{value:.3f}', ha='center', va='center',
                    fontsize=8, color='#2D3C49', zorder=6)
        ax.text(center, extent*1.125, label, ha='center', va='center', fontsize=10,
                fontweight='bold', color='#304C63')


def export(fig, path):
    for extension in ['png', 'svg', 'pdf']:
        fig.savefig(path.with_suffix('.'+extension), dpi=300, facecolor='white')
    plt.close(fig)


def legend(fig, y):
    handles = [Patch(facecolor=c, label=t) for c,t in zip(COLORS, ['β 形状', 'η 尺度', 'γ 位置'])]
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5,y), ncol=3,
               frameon=False, handlelength=1.1, columnspacing=2.4)


def main():
    rows = pd.read_csv(SOURCE)
    rows = rows[rows.method.isin(METHODS)].copy()
    keys = ['cell_id', 'repeat_id', 'sample_sha256']
    assert not rows.duplicated(keys + ['method']).any()
    output, groups = [], []
    for n in SAMPLE_SIZES:
        group = rows[rows.n == n]
        valid = group.pivot(index=keys, columns='method', values='valid')
        assert not valid[METHODS].isna().any().any()
        shared = valid.index[valid[METHODS].eq(True).all(axis=1)]
        selected = group.set_index(keys).loc[shared].reset_index()
        assert len(shared) > 0 and len(valid) == 1200
        groups.append(dict(n=n, population_samples=len(valid), common_valid_samples=len(shared),
                           failures={m:int((~group.loc[group.method==m,'valid']).sum()) for m in METHODS}))
        for method in METHODS:
            part = selected[selected.method == method]
            assert len(part) == len(shared)
            for param in PARAMS:
                output.append(dict(n=n, method=method, parameter=param,
                                   rmse=float(np.sqrt(np.mean(part['err_'+param]**2))),
                                   common_valid_samples=len(shared)))
    data = pd.DataFrame(output)
    data.to_csv(ROOT/'数据'/(STEM+'.csv'), index=False, encoding='utf-8-sig')
    max_value = float(data.rmse.max())
    extent = float(np.ceil(max_value*1.04/.2)*.2)
    ticks = np.arange(.2, extent+.01, .2).round(2).tolist()
    metadata = dict(source=str(SOURCE.relative_to(ROOT.parent)),
                    source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    sample_sizes=SAMPLE_SIZES, groups=groups, displayed_methods=METHODS,
                    omitted_method={'method':'MM','reason':'Outside the current six-method manuscript comparison; retained in original E09 experiment archive.'},
                    metric='sqrt(mean(standardized error squared)); six-method shared valid samples within each n',
                    normalization={'beta':'true beta','eta':'true eta','gamma':'true eta'},
                    geometry='Equal-width polar bars; radius=RMSE, linear zero origin; identical scale in all four panels. Labels show original RMSE; area is not RMSE.',
                    common_radial_extent=float(extent), common_ticks=ticks,
                    conclusion='Compare parameter accuracy of six estimators separately at n=7,10,15,20.',
                    uncertainty='Point estimates; no uncertainty intervals. Success-conditioned populations can differ across sample sizes.')
    (ROOT/'数据'/(STEM+'.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                         'font.size':9,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
    # Quantitative grid: same methods, parameters, scale and population definition in every panel.
    fig = plt.figure(figsize=(12.8,12.5), facecolor='white')
    for i,group in enumerate(groups):
        col,row = i%2,i//2
        ax = fig.add_axes([.055+.50*col,.535-.445*row,.39,.39], projection='polar')
        part=data[data.n==group['n']]
        draw_panel(ax,part,extent,ticks)
        fig.text(.25+.50*col,.955-.445*row,f"({chr(97+i)})  n = {group['n']}",
                 ha='center',fontsize=13,fontweight='bold',color='#304C63')
    legend(fig,.045)
    export(fig,ROOT/STEM)
    for i,group in enumerate(groups):
        fig = plt.figure(figsize=(7.2,7.2),facecolor='white')
        ax=fig.add_axes([.10,.16,.80,.75],projection='polar')
        draw_panel(ax,data[data.n==group['n']],extent,ticks)
        fig.text(.5,.96,f"({chr(97+i)})  n = {group['n']}",ha='center',fontsize=12,fontweight='bold',color='#304C63')
        legend(fig,.09)
        export(fig,ROOT/'子图'/f'F03{chr(97+i)}_n{group["n"]}_方法三参数玫瑰图')
    print(json.dumps(groups,ensure_ascii=False,indent=2))
    print(data.to_string(index=False))


if __name__ == '__main__':
    main()
