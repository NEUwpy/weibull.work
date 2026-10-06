"""Rebuild two cross-parameter PNGs from the 120-row summary, without fitting."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
METHODS = ['MLE', 'MMLE', 'WMLE']
NS = [7, 10, 15, 20, 50]
PARAMS = ['β', 'η', 'γ']
BASE_COLORS = {'MLE': '#5F6570', 'MMLE': '#345D7E', 'WMLE': '#B27448'}
MARKERS = {'MLE': 'o', 'MMLE': 'D', 'WMLE': 's'}
DEPTHS = [.40, .55, .70, .85, 1.0]
ORDER = [(1.5,1000,500), (2,1000,500), (3,1000,500), (5,1000,500),
         (2,1000,1000), (2,1000,3000), (2,100,500), (1.5,100,500)]
BLOCKS = [
    ('β', {'η':1000, 'γ':500}, [1.5,2,3,5], '形状扫描：β = 1.5 / 2 / 3 / 5 ｜ 固定 η=1000、γ=500'),
    ('γ', {'β':2, 'η':1000}, [500,1000,3000], '位置扫描：γ = 500 / 1000 / 3000 ｜ 固定 β=2、η=1000'),
    ('η', {'β':2, 'γ':500}, [100,1000], '尺度扫描：η = 100 / 1000 ｜ 固定 β=2、γ=500'),
]
TITLE_HEAT = '三方法在 8 个参数组合 × 5 个样本量下的有解率（每组 1200 组）'
TITLE_SCAN = '跨参数对比 ｜ 单变量扫描 ｜ 纵轴为 RMSE/真值 ｜ 颜色=方法、深浅=n（浅 7 → 深 50）'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(t):
    return 'W(' + ','.join(f'{v:g}' for v in t) + ')'


def shade(method, index):
    base = np.array(colors.to_rgb(BASE_COLORS[method]))
    return tuple(1 - DEPTHS[index] * (1 - base))


def load_source(path):
    data = pd.read_csv(path, float_precision='round_trip')
    assert len(data) == 120
    assert not data.duplicated(['组合', '方法', 'n']).any()
    assert set(data['组合']) == {label(t) for t in ORDER}
    assert set(data['方法']) == set(METHODS) and set(data.n) == set(NS)
    assert (data['总组数'] == 1200).all()
    np.testing.assert_allclose(data['有解率'], data['成功数']/data['总组数'], rtol=1e-14)
    assert data['有解率'].between(0,1).all()
    for t in ORDER:
        g = data[data['组合'] == label(t)]
        assert len(g) == 15 and g[[p+'真值' for p in PARAMS]].eq(list(t)).all().all()
    for p in PARAMS:
        assert (data[p+'真值'] > 0).all()
        np.testing.assert_allclose(data[p+' RMSE']**2, data[p+' Bias']**2 + data[p+' SD']**2, rtol=3e-12)
    return data


def draw_heat(data, out, points):
    fig, axes = plt.subplots(1, 3, figsize=(17, 7.1))
    fig.subplots_adjust(left=.16, right=.918, bottom=.155, top=.81, wspace=.13)
    fig.suptitle(TITLE_HEAT, y=.962, fontsize=16)
    labels = [label(t) for t in ORDER]
    text_artists = []
    for col, method in enumerate(METHODS):
        ax = axes[col]
        matrix = data[data['方法'] == method].pivot(index='组合', columns='n', values='有解率').loc[labels, NS].to_numpy()
        im = ax.imshow(matrix, cmap='Blues', vmin=0, vmax=1, aspect='auto', interpolation='nearest')
        ax.set_title('有解率 ｜ '+method, fontsize=14, pad=15)
        ax.set_xticks(range(5), labels=NS, fontsize=12)
        ax.set_yticks(range(8), labels=labels if col == 0 else ['']*8, fontsize=11)
        ax.set_xlabel('样本量 n', labelpad=10)
        ax.tick_params(length=0, pad=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-.5, 5, 1), minor=True)
        ax.set_yticks(np.arange(-.5, 8, 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=1.1)
        ax.tick_params(which='minor', bottom=False, left=False)
        for separator in [3.5, 5.5]:
            ax.axhline(separator, color='white', linewidth=3.2)
        for i, combination in enumerate(labels):
            for j, n in enumerate(NS):
                value = float(matrix[i,j])
                text = f'{value*100:.1f}%' if value < 1 else '100%'
                artist = ax.text(j, i, text, ha='center', va='center', fontsize=11.5,
                                 color='white' if value >= .60 else '#17212B')
                text_artists.append((artist, ax, i, j))
                points.append(dict(figure='heatmap', block='', parameter='', combination=combination,
                                   method=method, n=n, x=j, source_value=value, denominator=1, plotted_value=value))
    bar = fig.colorbar(im, cax=fig.add_axes([.94, .155, .013, .655]), ticks=[0,.25,.5,.75,1])
    bar.ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    bar.set_label('有效解比例', labelpad=10)
    rates = data.groupby('方法')['有解率'].agg(['min', 'max'])
    assert set(rates.index) == set(METHODS)
    summary = '；'.join('%s %.1f%%–%.1f%%' % (m, 100 * rates.loc[m, 'min'], 100 * rates.loc[m, 'max'])
                        for m in METHODS)
    fig.text(.5, .054, '每个条件下 1200 组，有解率区间：%s' % summary, ha='center', fontsize=12)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist, ax, i, j in text_artists:
        box = artist.get_window_extent(renderer)
        corners = ax.transData.transform([[j-.5,i-.5],[j+.5,i+.5]])
        lo, hi = corners.min(axis=0), corners.max(axis=0)
        assert box.x0 > lo[0]+2 and box.x1 < hi[0]-2
        assert box.y0 > lo[1]+2 and box.y1 < hi[1]-2
    fig.savefig(out/'跨参数对比_有解率热图.png', dpi=300, facecolor='white')
    plt.close(fig)


def draw_scan(data, out, points):
    """One figure PER sample size: rows = scan blocks, columns = estimated parameter."""
    subsets = []
    for scan, fixed, ticks, title in BLOCKS:
        mask = np.ones(len(data), dtype=bool)
        for p, value in fixed.items():
            mask &= data[p+'真值'].eq(value)
        subset = data.loc[mask].sort_values(scan+'真值')
        assert sorted(subset[scan+'真值'].unique()) == ticks
        subsets.append(subset)
    limits = {}
    for p in PARAMS:
        maximum = max(float((s[p+' RMSE']/s[p+'真值']).max()) for s in subsets)
        ticks = MaxNLocator(nbins=4, steps=[1,2,3,4,5,6,8,10]).tick_values(0, maximum*1.03)
        limits[p] = ticks.tolist()
    for n in NS:
        fig, axes = plt.subplots(3, 3, figsize=(12.6, 11.4))
        fig.subplots_adjust(left=.075, right=.975, bottom=.058, top=.868, hspace=.55, wspace=.26)
        fig.suptitle(f'跨参数对比 ｜ 单变量扫描 ｜ n = {n} ｜ 纵轴为 RMSE/真值（越低越准）',
                     y=.978, fontsize=14)
        for row, ((scan, fixed, xticks, title), subset) in enumerate(zip(BLOCKS, subsets)):
            ytitle = axes[row,0].get_position().y1 + .030
            fig.text(.075, ytitle, title, fontsize=12, weight='bold', va='bottom')
            for col, p in enumerate(PARAMS):
                ax = axes[row, col]
                ax.set_title('估计 ' + p, fontsize=11.5, pad=8)
                for method in METHODS:
                    selected = subset[(subset['方法']==method) & (subset.n==n)].sort_values(scan+'真值')
                    assert len(selected) == len(xticks)
                    x = selected[scan+'真值'].to_numpy(dtype=float)
                    denominator = selected[p+'真值'].to_numpy(dtype=float)
                    raw = selected[p+' RMSE'].to_numpy(dtype=float)
                    y = raw/denominator
                    line, = ax.plot(x, y, color=BASE_COLORS[method], marker=MARKERS[method],
                                    ms=5, lw=1.7, label=method)
                    np.testing.assert_array_equal(line.get_ydata(), y)
                    for combination, xv, rawv, den, yv in zip(selected['组合'], x, raw, denominator, y):
                        points.append(dict(figure='scan', block=scan, parameter=p, combination=combination,
                                           method=method, n=n, x=float(xv), source_value=float(rawv),
                                           denominator=float(den), plotted_value=float(yv)))
                ax.set_xticks(xticks, labels=[f'{v:g}' for v in xticks])
                width = xticks[-1]-xticks[0]
                ax.set_xlim(xticks[0]-.05*width, xticks[-1]+.05*width)
                ax.set_xlabel(scan+' 真值', labelpad=6)
                ax.set_ylabel(p+' RMSE / '+p+' 真值', labelpad=7)
                ax.set_ylim(limits[p][0], limits[p][-1]); ax.set_yticks(limits[p])
                ax.spines[['top','right']].set_visible(False)
                ax.tick_params(direction='out', length=3, pad=5)
                ax.set_axisbelow(True)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='upper center', ncol=3, frameon=False,
                   bbox_to_anchor=(.5, .945), fontsize=11)
        fig.savefig(out/f'跨参数对比_单变量扫描_n{n}.png', dpi=300, facecolor='white')
        plt.close(fig)
    return limits


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'实验/跨组合汇总/跨组合汇总.csv')
    parser.add_argument('--output',type=Path,default=ROOT/'交付/结果')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    fontpath=Path('C:/Windows/Fonts/msyh.ttc')
    assert fontpath.exists()
    font_manager.fontManager.addfont(str(fontpath))
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':11,'axes.unicode_minus':False,
                         'axes.linewidth':.85,'figure.facecolor':'white','axes.facecolor':'white',
                         'savefig.facecolor':'white'})
    source_hash=sha(args.source);data=load_source(args.source);points=[]
    legacy=args.output/'跨参数对比_单变量扫描.png'
    if legacy.exists():legacy.unlink()
    draw_heat(data,args.output,points)
    limits=draw_scan(data,args.output,points)
    assert len(points)==525 and sum(x['figure']=='scan' for x in points)==405
    # Independent scalar lookup verifies every recorded point and its denominator.
    indexed=data.set_index(['组合','方法','n'])
    for rec in points:
        src=indexed.loc[(rec['combination'],rec['method'],rec['n'])]
        if rec['figure']=='heatmap':
            expected=float(src['成功数']/src['总组数'])
        else:
            p=rec['parameter'];assert rec['denominator']==src[p+'真值']
            expected=float(src[p+' RMSE']/src[p+'真值'])
        assert np.isclose(expected,rec['plotted_value'],rtol=1e-14,atol=0)
    assert sha(args.source)==source_hash
    with (HERE/'绘图数据.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(points[0]));writer.writeheader();writer.writerows(points)
    audit={'source':str(args.source.resolve()),'source_sha256':source_hash,'rows':120,
           'heatmap_cells':120,'heatmap_method_order':METHODS,'heatmap_row_order':[label(t) for t in ORDER],
           'heatmap_common_scale':[0,1],'heatmap_text_inside_cells':True,
           'scan_figures':len(NS),'scan_panels_per_figure':9,'scan_lines_per_figure':27,
           'scan_lines_total':135,'scan_points':405,'scan_figure_n_order':NS,
           'base_colors':BASE_COLORS,'shade_depths':DEPTHS,
           'method_encoding':'one solid colour per method; n fixed per figure',
           'normalization':'RMSE / estimated parameter own true value',
           'y_ticks_shared_by_parameter':limits,'font':str(fontpath),
           'titles':[TITLE_HEAT,'跨参数对比 ｜ 单变量扫描 ｜ n = <n> ｜ 纵轴为 RMSE/真值（越低越准）'],
           'output_sha256':{p.name:sha(p) for p in args.output.glob('*.png')}}
    (HERE/'绘图核验.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))


if __name__=='__main__':
    main()
