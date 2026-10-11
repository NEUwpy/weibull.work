"""Show pre-estimation sample distances in WMLE panels a/d.

The default stage uses the original four archived samples and cached curves.
The current control-selection script supplies new normal-sample caches through
the optional overrides and saves its own QA. PNGs are delivered; source rows and
QA stay with the calling script. No sampling or estimation is performed here.
"""
from pathlib import Path
from io import BytesIO, StringIO
import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, setup_runtime, write_atomic
setup_runtime()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = RESULT / '报告2/数据'
IMAGES = RESULT / '报告2'
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
README = ROOT / 'README.md'
RECORD = HERE / (Path(__file__).stem + '.json')
ROWS = HERE / (Path(__file__).stem + '.csv')
LABELS = ['WMLE_low', 'WMLE_high']
CHANGED = {'配对情形_' + label + '.png' for label in LABELS}
SOURCE_SHA = 'e0f6df0b4aae74cf11407acd5011eb89f4ac7b9573c27cc7b8ac060d51170e90'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def math_blocks(text):
    return re.findall(r'\$\$.*?\$\$', text, re.S)


def protected_files():
    paths = [DATA / '20261010-配对图参照线精简核验.json',
             DATA / '20261010-参照线精简图数据.csv',
             DATA / '20261010-参照线精简WMLE网格.npz']
    paths.extend(path for path in IMAGES.glob('*.png') if path.name not in CHANGED)
    for source in load(PROGRAM / '跨参数对比/13组合取数.json')['sources']:
        path = matrix_path(source)
        assert digest(path) == source['matrix_sha256']
        paths.append(path)
        paths.extend((RESULT / source['program']).glob('*.xlsx'))
    return {str(path): digest(path) for path in paths}


def preserved_pixels(data, region='right'):
    array = plt.imread(BytesIO(data), format='png')
    if region == 'abnormal':
        return array[array.shape[0] // 2:]
    if region == 'left':
        return array[:, :int(array.shape[1] * .68)]
    assert region == 'right'
    return array[:, int(array.shape[1] * .35):]


def render(*, pair_overrides=None, curve_overrides=None, grid_overrides=None, preserve='right', show_scale=False):
    style = module(HERE / '20261010-配对图参照线精简.py', 'wmle_sample_style')
    pairs = load(DATA / '20261010-配对图参照线精简核验.json')
    curve_rows = list(csv.DictReader((DATA / '20261010-参照线精简图数据.csv').open(encoding='utf-8-sig')))
    if pair_overrides:
        for label, obj in pair_overrides.items():
            pairs['pairs'][label]['normal'] = obj
    if curve_overrides:
        curve_rows = [row for row in curve_rows if not
                      (row['example'] in pair_overrides and row['role'] == '正常' and row['panel'] == 'shape_zero_branch')]
        curve_rows.extend(curve_overrides)
    protected = protected_files()
    source_rows, figures = [], {}
    with np.load(DATA / '20261010-参照线精简WMLE网格.npz') as saved_grids:
        grids = {key: saved_grids[key] for key in saved_grids.files}
        if grid_overrides:
            grids.update(grid_overrides)
        for label in LABELS:
            pair = pairs['pairs'][label]
            old_meta = pairs['figures'][label]
            objects = [pair['normal'], pair['abnormal']]
            fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.7))
            for index, ax in enumerate(axes.ravel()):
                meta = old_meta['axes'][index]
                ax.set(xlim=meta['xlim'], ylim=meta['ylim'], xticks=meta['xticks'], yticks=meta['yticks'])
                ax.xaxis.set_major_formatter(StrMethodFormatter('{x:g}'))
                ax.text(-.16, 1.04, chr(97 + index), transform=ax.transAxes, fontweight='bold', fontsize=11)
            for row, obj in enumerate(objects):
                ax = axes[row, 0]
                x = np.asarray(obj['values'], float)
                distances = x - obj['gamma_true']
                ratios = distances / obj['eta_true']
                ranks = np.arange(1, len(x) + 1)
                assert np.all(distances > 0) and np.all(np.diff(x) >= 0)
                assert np.all((ratios >= ax.get_ylim()[0]) & (ratios <= ax.get_ylim()[1]))
                ax.set(xlabel=r'$i$', ylabel=r'$(x_{(i)}-\gamma_0)/\eta_0$')
                ax.plot(ranks, ratios, color=style.BROWN, lw=1, marker='o', ms=3.8)
                ax.set_title(obj['role'] + f" · 第{obj['group']}组", loc='left', pad=14, fontsize=9)
                source_rows.extend(dict(example=label, role=obj['role'], combination=obj['combination'],
                                        n=obj['n'], group=obj['group'], rank=int(i), observation=float(value),
                                        gamma_true=obj['gamma_true'], eta_true=obj['eta_true'],
                                        distance=float(distance), distance_ratio=float(ratio))
                                   for i, value, distance, ratio in zip(ranks, x, distances, ratios))
                if show_scale:
                    for record in source_rows[-len(x):]:
                        record.update(beta_hat=obj['beta_hat'], gamma_hat=obj['gamma_hat'], eta_hat=obj['eta_hat'],
                                      selected_distance=record['observation']-obj['gamma_hat'],
                                      selected_distance_ratio=(record['observation']-obj['gamma_hat'])/obj['eta_true'],
                                      eta_ratio=obj['eta_hat']/obj['eta_true'])
                prefix = label + '_' + obj['role'] + '_'
                gs, bs = grids[prefix + 'gamma'], grids[prefix + 'beta']
                ax = axes[row, 1]
                ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$\beta$')
                ax.axvline(1, color=style.GRAY, lw=.7, ls='--', zorder=0)
                ax.contour(gs / obj['gamma_true'], bs, grids[prefix + 'T1'].T,
                           levels=[0], colors=[style.BLUE], linewidths=1.2)
                ax.contour(gs / obj['gamma_true'], bs, grids[prefix + 'T2'].T,
                           levels=[0], colors=[style.BROWN], linewidths=1.2)
                ax.scatter([1], [obj['beta_true']], marker='D', facecolors='white',
                           edgecolors=style.GRAY, s=25, lw=.8, zorder=5)
                ax.scatter([obj['gamma_hat'] / obj['gamma_true']], [obj['beta_hat']],
                           marker='*', s=58, color=style.BROWN, edgecolors='white', lw=.5, zorder=6, clip_on=False)
                if row == 0:
                    ax.legend(handles=[Line2D([0], [0], color=style.BLUE, lw=1.2, label=r'$T_1=0$'),
                                       Line2D([0], [0], color=style.BROWN, lw=1.2, label=r'$T_2=0$')],
                              loc='upper right', fontsize=7)
                ax = axes[row, 2]
                if show_scale:
                    ax.set(xlim=axes[row, 0].get_xlim(), xticks=axes[row, 0].get_xticks(),
                           ylim=axes[row, 0].get_ylim(), yticks=axes[row, 0].get_yticks(),
                           xlabel=r'$i$', ylabel=r'$(x_{(i)}-\hat\gamma)/\eta_0$')
                    ax.plot(ranks, (x-obj['gamma_hat'])/obj['eta_true'], color=style.BROWN, lw=1, marker='o', ms=3.8)
                    ax.axhline(1, color=style.GRAY, lw=.7, ls='--', zorder=0)
                    ax.axhline(obj['eta_hat']/obj['eta_true'], color=style.BROWN, lw=.8, ls='--')
                    ax.scatter([len(x)], [obj['eta_hat']/obj['eta_true']], marker='*', s=58,
                               color=style.BROWN, edgecolors='white', lw=.5, zorder=6)
                else:
                    ax.set(xlabel=r'$\gamma/\gamma_0$', ylabel=r'$T_2[\hat\beta(\gamma),\gamma]$')
                    ax.axvline(1, color=style.GRAY, lw=.7, ls='--', zorder=0)
                    points = [r for r in curve_rows if r['example'] == label and r['role'] == obj['role']
                              and r['panel'] == 'shape_zero_branch']
                    assert len(points) == len(gs)
                    ax.plot([float(r['gamma_ratio']) for r in points], [float(r['t2']) for r in points],
                            color='#444444', lw=1.15)
                    ax.axhline(0, color=style.GRAY, lw=.7, ls=':')
                    ax.scatter([obj['gamma_hat'] / obj['gamma_true']], [obj['at_original']['t2']],
                               marker='*', s=58, color=style.BROWN, edgecolors='white', lw=.5, zorder=6, clip_on=False)
            legend = [Line2D([0], [0], color=style.BROWN, marker='o', ms=3, lw=1, label='样本距离'),
                      Line2D([0], [0], marker='*', ms=7, color=style.BROWN, ls='none', label='原估计'),
                      Line2D([0], [0], marker='D', mfc='white', mec=style.GRAY, ls='none', ms=4, label='真参数')]
            fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(.52, .015), ncol=3, fontsize=8)
            fig.subplots_adjust(left=.08, right=.985, bottom=.14, top=.91, wspace=.39, hspace=.48)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            for item in fig.findobj(matplotlib.text.Text):
                if item.get_visible() and item.get_text():
                    box = item.get_window_extent(renderer)
                    assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= fig.bbox.x1 + 1 and box.y1 <= fig.bbox.y1 + 1
            axes_meta = [{key: [float(value) for value in getattr(ax, 'get_' + key)()]
                          for key in ['xlim', 'ylim', 'xticks', 'yticks']} for ax in axes.ravel()]
            expected_axes = [dict(item) for item in old_meta['axes']]
            if show_scale:
                expected_axes[2], expected_axes[5] = expected_axes[0], expected_axes[3]
            assert axes_meta == expected_axes
            buffer = BytesIO()
            fig.savefig(buffer, dpi=400, facecolor='white')
            plt.close(fig)
            path = IMAGES / ('配对情形_' + label + '.png')
            after_pixels = None
            if preserve is not None:
                before_pixels = preserved_pixels(path.read_bytes(), preserve)
                after_pixels = preserved_pixels(buffer.getvalue(), preserve)
                assert np.array_equal(before_pixels, after_pixels), label + ': unrelated panels changed'
            write_atomic(path, buffer.getvalue())
            figures[label] = dict(path=str(path), sha256=digest(path), axes=axes_meta,
                                 preserved_region=preserve,
                                 preserved_pixels_sha256=hashlib.sha256(after_pixels.tobytes()).hexdigest() if after_pixels is not None else None,
                                 distances_at_true_position=True, observation_points=14)
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=list(source_rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(source_rows)
    write_atomic(ROWS, csv_buffer.getvalue().encode('utf-8-sig'))
    assert protected_files() == protected
    text = REPORT.read_text(encoding='utf-8')
    previous = load(RECORD) if RECORD.exists() else {}
    record = dict(backend='Python/matplotlib', export='PNG', samples={label: pairs['pairs'][label] for label in LABELS},
                  figures=figures, source_sha256=protected, source_rows_sha256=digest(ROWS),
                  original_math_blocks=math_blocks(text), script_sha256=digest(__file__),
                  new_samples=0, new_estimates=0,
                  updated_panels=['c', 'f'] if show_scale else (['a', 'b', 'c'] if pair_overrides else ['a', 'd']),
                  figure_contract=dict(conclusion='Compare sample features at the true location, then explain the equation intersection.',
                                       archetype='quantitative grid', size_inches=[9.6, 5.7],
                                       panels='a/d true-location distances; b/e equation zero sets; c/f selected-location distances and scale.' if show_scale else 'a/d true-location distances; b/e cached equation zero sets; c/f cached conditional residual.',
                                       scale='Keep all six panels and their existing matching linear limits and ticks.'))
    if 'text_revision' in previous:
        record['text_revision'] = previous['text_revision']
    write_atomic(RECORD, (json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    print('Rendered WMLE low/high figures with matching ticks; preserved region: ' + str(preserve))


def revise():
    text = REPORT.read_text(encoding='utf-8')
    if '图16、17的a、d按真位置γ₀' in text:
        print('WMLE prose already explains true-location sample distances.')
        return
    assert digest(REPORT) == SOURCE_SHA, 'Report changed; review before applying prose revision'
    original = text
    changes = [
        ('图16、17同时给出两条零线及其交点；',
         '图16、17的a、d按真位置γ₀绘制样本距离(x₍ᵢ₎−γ₀)/η₀，η₀为尺度真值；b、e给出两条零线及其交点，c、f给出上述条件残差；'),
        ('图16对照式（21）、（22）的联合交点及其对应形状。',
         '图16先比较两组样本的下端空缺，再对照式（21）、（22）的联合交点及其对应形状。'),
        ('两组在真位置处按式（22）计算的T₂都为负，样本乘积低于校准项。第10组的两式在距最小观测27.06处平衡；第11组下端空缺更大，联合交点直到距最小观测2.44处才出现。',
         '以真位置500为起点，第10组的最小观测高于起点43.87，第11组高于起点75.95；后者的前四个观测集中在575.95—586.04，下端空缺更大。两组在真位置处按式（22）计算的T₂都为负，样本乘积低于校准项。联合交点分别位于γ=516.81、573.51，与各自最小观测相差27.06、2.44。第11组需要更靠近最小值的位置才能使两式平衡。'),
        ('图17比较点列较分散和较集中时，式（21）、（22）的联合交点对应的形状。',
         '图17先在真位置下比较样本的集中程度，再对照式（21）、（22）的联合交点对应的形状。'),
        ('第9组的最小观测较孤立，其余观测集中。在真位置处，式（21）已给出4.25，',
         '第9组的最小观测为551.95，其余六个观测集中在606.91—659.99；第10组则分布在506.42—734.47，跨度更大。按真位置计算的距离保留了这一集中差异。在真位置处，式（21）已给出4.25，')]
    for old, new in changes:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    assert math_blocks(text) == math_blocks(original)
    assert re.findall(r'^\|.*$', text, re.M) == re.findall(r'^\|.*$', original, re.M)
    before, after = text.split('#### 2.1.5', 1)[0], text.split('#### 2.1.6', 1)[1]
    assert before == original.split('#### 2.1.5', 1)[0]
    assert after == original.split('#### 2.1.6', 1)[1]
    write_atomic(REPORT, text.encode('utf-8'))
    readme = README.read_text(encoding='utf-8')
    note = ('报告2的WMLE图16、17将a、d改为按真位置γ₀计算的样本距离，先呈现样本特征，再解释方程交点。'
            '[20261011-WMLE真位置样本距离.py](交付/程序/报告2/20261011-WMLE真位置样本距离.py)'
            '提供`render`、`revise`、`verify`；原样本、估计、其他四个面板及刻度保留，数据与核验记录放在程序目录。\n\n')
    assert note not in readme
    write_atomic(README, readme.replace('## 整理与恢复\n', note + '## 整理与恢复\n', 1).encode('utf-8'))
    record = load(RECORD)
    record['text_revision'] = dict(before_sha256=SOURCE_SHA, after_sha256=digest(REPORT),
                                   section='2.1.5 WMLE', equations_unchanged=True, tables_unchanged=True)
    write_atomic(RECORD, (json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    print('Revised WMLE prose: true-location sample features -> residual balance -> selected parameters.')


def verify():
    record = load(RECORD)
    for path, sha in record['source_sha256'].items():
        assert digest(path) == sha, path
    assert digest(ROWS) == record['source_rows_sha256']
    rows = list(csv.DictReader(ROWS.open(encoding='utf-8-sig')))
    assert len(rows) == 28
    for label in LABELS:
        meta = record['figures'][label]
        assert digest(meta['path']) == meta['sha256']
        region = meta.get('preserved_region', 'right')
        expected = meta.get('preserved_pixels_sha256', meta.get('unchanged_right_pixels_sha256'))
        if region is not None:
            assert hashlib.sha256(preserved_pixels(Path(meta['path']).read_bytes(), region).tobytes()).hexdigest() == expected
        for role in ['normal', 'abnormal']:
            obj = record['samples'][label][role]
            points = [r for r in rows if r['example'] == label and r['role'] == obj['role']]
            assert np.allclose([float(r['distance_ratio']) for r in points],
                               (np.asarray(obj['values']) - obj['gamma_true']) / obj['eta_true'], rtol=0, atol=1e-15)
    text = REPORT.read_text(encoding='utf-8')
    assert math_blocks(text) == record['original_math_blocks']
    assert [int(n) for n in re.findall(r'\\tag\{(\d+)\}', text)] == list(range(1, 31))
    assert '图16、17的a、d按真位置γ₀' in text
    for link in re.findall(r'!\[.*?\]\((.*?)\)', text):
        assert (ROOT / link).exists()
    print('PASS: 28 true-location distances; designated panels preserved; archived samples, estimates, equations and ticks verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['render', 'revise', 'verify'])
    globals()[parser.parse_args().action]()
