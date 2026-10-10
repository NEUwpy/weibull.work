"""Draw three archived anomaly matrices as one shared-axis PNG figure.

Use the previous task's fully checked 624 counts. Only the figure layout,
its report placement and the following figure numbers change.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1] / '图片'
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
OUTPUT = IMAGES / '图2_异常分类样本量对比.png'
QA = HERE / '20261010-异常分类三子图核验.json'
NS = [7, 15, 30]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(matrices, row_order, columns):
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
        'font.size': 10, 'axes.unicode_minus': False,
    })
    cmap = LinearSegmentedColormap.from_list(
        'restrained_blue', ['#ffffff', '#e0edf5', '#a8cbdc', '#5d95b3', '#255d7b'])
    norm = Normalize(0, 25)
    fig = plt.figure(figsize=(22, 7.4), facecolor='white')
    axes = [fig.add_axes([0.158+i*0.257, 0.215, 0.246, 0.71]) for i in range(3)]
    cax = fig.add_axes([0.946, 0.215, 0.01, 0.71])
    starts = [0]+[i for i in range(1, 16) if row_order[i]['method'] != row_order[i-1]['method']]+[16]
    labels = []
    annotations = []
    for panel, (n, ax) in enumerate(zip(NS, axes)):
        matrix = matrices[str(n)]
        artist = ax.imshow(matrix, cmap=cmap, norm=norm, aspect='auto', interpolation='nearest')
        ax.set_xticks(range(13))
        ax.set_xticklabels(columns, rotation=65, ha='right', rotation_mode='anchor', fontsize=9)
        ax.set_yticks(range(16))
        ax.set_yticklabels([r['label'] for r in row_order] if panel == 0 else ['']*16, fontsize=10)
        ax.tick_params(axis='both', length=0, pad=6)
        ax.set_xticks(np.arange(-0.5, 13, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 16, 1), minor=True)
        ax.grid(which='minor', color='#e5e9ec', linewidth=0.4)
        ax.tick_params(which='minor', bottom=False, left=False)
        for boundary in starts[1:-1]:
            ax.axhline(boundary-0.5, color='#94a1ab', linewidth=0.8)
        for spine in ax.spines.values():
            spine.set_color('#d6dde1'); spine.set_linewidth(0.6)
        for y, x in zip(*np.nonzero(matrix)):
            value = int(matrix[y, x])
            text = ax.text(x, y, str(value), ha='center', va='center', fontsize=10,
                           color='white' if value >= 17 else '#263746')
            annotations.append(dict(n=n, row=int(y), column=int(x), count=value, text=text))
        title = ax.set_title(f'n = {n}', fontsize=12, pad=12)
        letter = ax.text(-0.02, 1.035, 'abc'[panel], transform=ax.transAxes,
                         fontweight='bold', fontsize=13, ha='left', va='bottom')
        labels += [*ax.get_xticklabels(), *ax.get_yticklabels(), title, letter]
    for begin, end in zip(starts, starts[1:]):
        method = row_order[begin]['method']
        label = 'MDM\nδ=0.20' if method.startswith('MDM') else method
        center_y = 0.215+0.71*(1-(begin+end)/32)
        labels.append(fig.text(0.023, center_y, label, ha='center', va='center',
                               fontsize=10.5, fontweight='bold', linespacing=1.5, color='#253441'))
    bar = fig.colorbar(artist, cax=cax, ticks=[0, 5, 10, 15, 20, 25])
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, pad=4, labelsize=9)
    labels += [*bar.ax.get_yticklabels(), bar.ax.set_title('次数', fontsize=10, pad=10)]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in labels if t.get_text()]
    assert all(b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.x1 and b.y1 <= fig.bbox.y1
               for b in boxes), 'A shared label falls outside the canvas'
    for ax, n in zip(axes, NS):
        assert ax.get_xlim() == (-0.5, 12.5) and ax.get_ylim() == (15.5, -0.5)
        assert ax.get_images()[0].get_clim() == (0.0, 25.0)
        assert np.array_equal(ax.get_images()[0].get_array(), matrices[str(n)])
    for cell in annotations:
        assert cell['text'].get_text() == str(int(matrices[str(cell['n'])][cell['row'],cell['column']]))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(OUTPUT, dpi=400, facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught), 'Missing font glyph'
    plt.close(fig)
    with Image.open(OUTPUT) as image:
        assert image.format == 'PNG' and image.size == (8800, 2960)
    return len(annotations)


def revise_report(original):
    heading = '### 2.1　各方法的异常形成机制\n\n'
    leading, section = original.split(heading, 1)
    _, body = section.split('以下组图中的γ₀、η₀', 1)
    body = '以下组图中的γ₀、η₀'+body
    already_grouped = OUTPUT.name in original
    if not already_grouped:
        assert re.findall(r'\*\*图(\d+)｜', original) == list(map(str, range(1, 19)))
        body = re.sub(r'图(\d+)', lambda m:'图'+str(int(m.group(1))+1), body)
    block = ('![各类明显异常估计在不同样本量下的发生次数]'
             '(跨组合诊断/20261009-形状异常退化解/图片/图2_异常分类样本量对比.png)\n\n'
             '**图2｜各类明显异常估计在不同样本量下的发生次数。** '
             'a—c分别为n=7、15、30，空白格为0。\n\n')
    revised = leading+heading+block+body
    assert re.findall(r'\*\*图(\d+)｜', revised) == list(map(str, range(1, 20)))
    assert not re.findall(r'\*\*表[123]｜', revised)
    assert not any(f'分类热力表_n{n}.png' in revised for n in NS)
    assert original.split('\n## 2',1)[0] == revised.split('\n## 2',1)[0]
    normalize = lambda text:re.sub(r'图\d+', '图', text)
    assert normalize(original.split('以下组图中的γ₀、η₀',1)[1]) == normalize(revised.split('以下组图中的γ₀、η₀',1)[1])
    return revised


def main():
    previous_qa = HERE/'20261010-异常分类三档热力表核验.json'
    previous = json.loads(previous_qa.read_text(encoding='utf-8'))
    sources = dict(previous['source_sha256'])
    data_path = HERE/'20261010-各类异常参数空间.csv'
    sources.update({str(p):digest(p) for p in [previous_qa, data_path, Path(__file__)]})
    assert all(digest(path) == value for path, value in sources.items())
    protected_pngs = {str(p):digest(p) for p in IMAGES.glob('*.png') if p != OUTPUT}
    with data_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 624 and sum(int(r['count']) for r in rows) == 963
    row_order = previous['row_order']
    columns = previous['column_order']
    assert len(row_order) == 16 and len(columns) == 13
    assert columns == sorted(columns, key=lambda c:tuple(map(float, c[2:-1].split(','))))
    counts = {(r['method'],r['case'],r['combination'],int(r['n'])):int(r['count']) for r in rows}
    assert len(counts) == 624
    matrices = {str(n):np.array([[counts[r['method'],r['case'],c,n] for c in columns]
                               for r in row_order], dtype=int) for n in NS}
    for n in NS:
        assert np.array_equal(matrices[str(n)], previous['matrices'][str(n)])
    assert {n:int(matrices[str(n)].sum()) for n in NS} == {7:650,15:250,30:63}
    original = REPORT.read_text(encoding='utf-8')
    revised = revise_report(original)
    annotated = render(matrices, row_order, columns)
    assert all(digest(path) == value for path, value in sources.items())
    assert all(digest(path) == value for path, value in protected_pngs.items())
    REPORT.write_text(revised, encoding='utf-8')
    result = dict(
        scope='Display-only regrouping of the same 624 R00 condition counts and 963 anomalies.',
        figure_contract=dict(claim='Aligned case rows reveal how anomaly frequencies differ across n=7,15,30.',
                             archetype='quantitative grid', backend='Python/matplotlib',
                             export='One PNG, 400 dpi', shared_y_labels=True, shared_colorbar=True,
                             row_order='16 cases grouped by six methods', column_order='13 combinations sorted beta,eta,gamma',
                             blank_cells='Count zero; retained in source data'),
        path=str(OUTPUT), image_sha256=digest(OUTPUT), pixels=[8800,2960],
        panel_order=[dict(letter=l,n=n) for l,n in zip('abc',NS)],
        matrices={n:m.tolist() for n,m in matrices.items()},
        counts_by_n={n:int(matrices[str(n)].sum()) for n in NS},
        shared_color_limits=[0,25], shared_color_ticks=[0,5,10,15,20,25],
        annotated_positive_cells=annotated, all_labels_within_canvas=True,
        source_sha256=sources, sources_unchanged=True,
        protected_png_sha256=protected_pngs, existing_pngs_unchanged=True,
        previous_624_counts_exact=True, chapter1_unchanged=True,
        remaining_text_unchanged_except_figure_numbers=True,
        figure_numbers=list(range(1,20)), report_sha256=digest(REPORT), visual_review='pending')
    if QA.exists():
        old = json.loads(QA.read_text(encoding='utf-8'))
        if old['image_sha256'] == result['image_sha256']:
            result['visual_review'] = old.get('visual_review', 'pending')
    QA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: one PNG with three aligned heatmap panels and a shared colorbar; all 624 counts unchanged; '
          'original sources and PNGs unchanged; report figures numbered 1-19.')


if __name__ == '__main__':
    main()
