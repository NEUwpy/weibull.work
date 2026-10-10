"""Place one three-panel anomaly heatmap in each of the six method sections.

The 624 source counts and original estimates remain unchanged. Each method
figure shares the thirteen parameter rows across n=7,15,30, with its own case
columns. This task saves a dedicated script and hash-bound verification.
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
QA = HERE / '20261010-逐方法异常分类三子图核验.json'
NS = [7, 15, 30]
METHODS = ['LSE', 'LRE', 'MLE', 'MDM δ=0.20', 'WMLE', 'MMLE']
PRINCIPLES = [('LSE先将Weibull变量', 'LSE以标准对数Weibull顺序统计量', 'LSE通过调整γ'),
              ('LRE从Weibull分布函数', 'LRE按观测次序', 'LRE拟合的Weibull关系为'), 'MLE同时搜索形状',
              'MDM先在每个候选γ', 'WMLE用两条校准方程', 'MMLE直接用样本最小值']
DISPLAY_NOTE = '分类热力图显示各类异常的发生次数，空白格为0。'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def filename(method):
    return '异常分类_' + method.split(' δ=')[0] + '_三子图.png'


def render(method, matrices, cases, combinations):
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
        'font.size': 10.5, 'axes.unicode_minus': False,
    })
    cmap = LinearSegmentedColormap.from_list(
        'restrained_blue', ['#ffffff', '#e0edf5', '#a8cbdc', '#5d95b3', '#255d7b'])
    fig = plt.figure(figsize=(11.8, 6.6), facecolor='white')
    axes = [fig.add_axes([0.175+i*0.248, 0.205, 0.23, 0.695]) for i in range(3)]
    cax = fig.add_axes([0.939, 0.205, 0.013, 0.695])
    labels, displayed = [], []
    for panel, (ax, n) in enumerate(zip(axes, NS)):
        matrix = matrices[str(n)]
        artist = ax.imshow(matrix, cmap=cmap, norm=Normalize(0, 25),
                           aspect='auto', interpolation='nearest')
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels([c['label'] for c in cases], fontsize=10, rotation=33,
                           ha='right', rotation_mode='anchor')
        ax.set_yticks(range(13))
        ax.set_yticklabels(combinations if panel == 0 else ['']*13, fontsize=10)
        ax.tick_params(axis='both', length=0, pad=6)
        ax.set_xticks(np.arange(-0.5, len(cases), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 13, 1), minor=True)
        ax.grid(which='minor', color='#e5e9ec', linewidth=0.45)
        ax.tick_params(which='minor', bottom=False, left=False)
        for spine in ax.spines.values():
            spine.set_color('#d6dde1'); spine.set_linewidth(0.6)
        for y, x in zip(*np.nonzero(matrix)):
            value = int(matrix[y, x])
            text = ax.text(x, y, str(value), ha='center', va='center', fontsize=11,
                           color='white' if value >= 17 else '#263746')
            assert text.get_text() == str(value)
            displayed.append(dict(n=n, row=int(y), column=int(x), count=value))
        title = ax.set_title(f'n = {n}', fontsize=12, pad=12)
        letter = ax.text(-0.025, 1.035, 'abc'[panel], transform=ax.transAxes,
                         ha='left', va='bottom', fontsize=13, fontweight='bold')
        labels += [*ax.get_xticklabels(), *ax.get_yticklabels(), title, letter]
        assert np.array_equal(ax.get_images()[0].get_array(), matrix)
    bar = fig.colorbar(artist, cax=cax, ticks=[0, 5, 10, 15, 20, 25])
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, pad=5, labelsize=10)
    labels += [*bar.ax.get_yticklabels(), bar.ax.set_title('次数', fontsize=10, pad=10)]
    if method.startswith('MDM'):
        labels.append(fig.text(0.52, 0.972, 'δ=0.20', ha='center', fontsize=10.5))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in labels if t.get_text()]
    assert all(b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.x1 and b.y1 <= fig.bbox.y1
               for b in boxes), f'{method}: label outside canvas'
    for ax in axes:
        assert ax.get_ylim() == (12.5, -0.5) and ax.get_xlim() == (-0.5, len(cases)-0.5)
        assert ax.get_images()[0].get_clim() == (0.0, 25.0)
    output = IMAGES/filename(method)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(output, dpi=400, facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught), 'Missing font glyph'
    plt.close(fig)
    with Image.open(output) as image:
        assert image.format == 'PNG' and image.size == (4720, 2640)
    return dict(method=method, path=str(output), sha256=digest(output), pixels=[4720,2640],
                case_order=cases, parameter_order=combinations,
                matrices={n:m.tolist() for n,m in matrices.items()},
                counts_by_n={n:int(matrices[str(n)].sum()) for n in NS},
                color_limits=[0,25], color_ticks=[0,5,10,15,20,25],
                visible_cells=displayed, all_labels_within_canvas=True)


def remove_old_display(text):
    return re.sub(
        r'^!\[[^\n]*\]\([^\n]*(?:图2_异常分类样本量对比|异常分类_[A-Z]+_三子图)\.png\)\n\n'
        r'\*\*图\d+｜[^\n]*\n\n', '', text, flags=re.M).replace(DISPLAY_NOTE+'\n\n','')


def revise_report(original):
    current = remove_old_display(original)
    current = current.replace('### 2.1　各方法的异常形成机制\n\n',
                              '### 2.1　各方法的异常形成机制\n\n'+DISPLAY_NOTE+'\n\n',1)
    image_figure_map = {}
    for i, (method, principle) in enumerate(zip(METHODS, PRINCIPLES), 1):
        heading = f'#### 2.1.{i}　{method.split(" δ=")[0]}'
        leading, tail = current.split(heading, 1)
        if isinstance(principle, tuple):
            principle = next(anchor for anchor in principle if anchor in tail)
        intro, body = tail.split(principle, 1)
        label = method.replace(' δ=0.20', '（δ=0.20）')
        block = (f'![{label}各类明显异常估计的发生次数]'
                 f'(跨组合诊断/20261009-形状异常退化解/图片/{filename(method)})\n\n'
                 f'**图0｜{label}各类明显异常估计的发生次数。**\n\n')
        current = leading+heading+intro+block+principle+body
    captions = list(re.finditer(r'\*\*图(\d+)｜', current))
    assert len(captions) == 24
    old_to_new = {int(match.group(1)):i for i,match in enumerate(captions,1) if match.group(1) != '0'}
    chunks, pos = [], 0
    for new_number, match in enumerate(captions, 1):
        between = current[pos:match.start()]
        between = re.sub(r'图(\d+)', lambda m:'图'+str(old_to_new.get(int(m.group(1)),int(m.group(1)))), between)
        chunks += [between, f'**图{new_number}｜']
        pos = match.end()
    ending = re.sub(r'图(\d+)', lambda m:'图'+str(old_to_new.get(int(m.group(1)),int(m.group(1)))), current[pos:])
    revised = ''.join(chunks)+ending
    assert re.findall(r'\*\*图(\d+)｜', revised) == list(map(str,range(1,25)))
    normalize = lambda t:re.sub(r'图\d+', '图', remove_old_display(t))
    assert normalize(original) == normalize(revised), 'Content changed beyond displays and figure numbers'
    assert original.split('\n## 2',1)[0] == revised.split('\n## 2',1)[0]
    for i, method in enumerate(METHODS,1):
        heading = f'#### 2.1.{i}　{method.split(" δ=")[0]}'
        section = revised.split(heading,1)[1].split('#### 2.1.' if i<6 else '### 2.2',1)[0]
        assert section.count('/'+filename(method)+')') == 1
        image_figure_map[method] = int(re.search(
            re.escape(filename(method))+r'\)\n\n\*\*图(\d+)｜', section).group(1))
    assert image_figure_map == dict(zip(METHODS,[2,6,10,14,17,20]))
    return revised, image_figure_map


def main():
    baseline_path = HERE/'20261010-异常分类三档热力表核验.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    data_path = HERE/'20261010-各类异常参数空间.csv'
    sources = dict(baseline['source_sha256'])
    sources.update({str(p):digest(p) for p in [baseline_path,data_path,Path(__file__)]})
    assert all(digest(p) == value for p,value in sources.items())
    names = {filename(m) for m in METHODS}
    protected = {str(p):digest(p) for p in IMAGES.glob('*.png') if p.name not in names}
    with data_path.open(encoding='utf-8-sig',newline='') as handle:
        rows = list(csv.DictReader(handle))
    counts = {(r['method'],r['case'],r['combination'],int(r['n'])):int(r['count']) for r in rows}
    assert len(rows) == len(counts) == 624 and sum(counts.values()) == 963
    combinations = baseline['column_order']
    assert combinations == sorted(combinations, key=lambda c:tuple(map(float,c[2:-1].split(','))))
    original = REPORT.read_text(encoding='utf-8')
    revised, numbering = revise_report(original)
    figures, represented = [], set()
    for method in METHODS:
        cases = [r for r in baseline['row_order'] if r['method'] == method]
        indices = [i for i,r in enumerate(baseline['row_order']) if r['method'] == method]
        matrices = {str(n):np.array([[counts[method,c['case'],combo,n] for c in cases]
                                    for combo in combinations],dtype=int) for n in NS}
        for n in NS:
            assert np.array_equal(matrices[str(n)], np.array(baseline['matrices'][str(n)])[indices,:].T)
            represented.update((method,c['case'],combo,n) for c in cases for combo in combinations)
        figures.append(render(method,matrices,cases,combinations))
    assert represented == set(counts)
    assert all(digest(p) == value for p,value in sources.items())
    assert all(digest(p) == value for p,value in protected.items())
    REPORT.write_text(revised,encoding='utf-8')
    result = dict(
        scope='R00 only; six method figures, three sample-size panels each; the same 624 counts and 963 anomalies.',
        figure_contract=dict(claim='Each method section shows the conditions and frequencies of its own anomaly types.',
                             archetype='quantitative grid', backend='Python/matplotlib', export='Six PNGs, 400 dpi',
                             panels='a,b,c are n=7,15,30', rows='13 combinations sorted beta,eta,gamma',
                             columns='Original cases for the corresponding method', blank_cells='Zero count',
                             color='Shared 0-25 range and one colorbar per method figure'),
        figures=figures, report_figure_numbers=numbering, all_624_cells_preserved=True,
        all_six_figures_in_own_method_sections=True, source_sha256=sources, sources_unchanged=True,
        protected_png_sha256=protected, existing_pngs_unchanged=True, chapter1_unchanged=True,
        remaining_text_unchanged_except_figure_numbers=True, figure_numbers=list(range(1,25)),
        report_sha256=digest(REPORT), visual_review='pending')
    if QA.exists():
        prior = json.loads(QA.read_text(encoding='utf-8'))
        if [f['sha256'] for f in prior['figures']] == [f['sha256'] for f in figures]:
            result['visual_review'] = prior.get('visual_review','pending')
    QA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: six separate method figures, each with three panels; all 624 cells and 963 anomalies unchanged; '
          'each figure in its own section; report figures 1-24; existing samples, estimates and PNGs unchanged.')


if __name__ == '__main__':
    main()
