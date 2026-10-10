"""Replace six parameter-support tables with three sample-size heatmap tables.

Read the archived 624 condition cells, independently count the original 963
classified estimates, and reconcile each method/combination/n with Figure 1.
Only PNG presentation and the classification-table introductions are revised.
"""
from collections import Counter
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
REPORT = ROOT / '报告2：小样本情况下的明显异常估计.md'
IMAGES = HERE.parents[1] / '图片'
PREFIX = '20261010-异常分类三档热力表'
SAMPLE_SIZES = [7, 15, 30]
METHODS = ['LSE', 'LRE', 'MLE', 'MDM δ=0.20', 'WMLE', 'MMLE']
LEADS = {
    'LSE': 'LSE的明显异常分为零边界高估、内部左侧高估和内部右侧低估。',
    'LRE': 'LRE的明显异常也分为零边界高估、内部左侧高估和内部右侧低估。',
    'MLE': '按所选位置的条件似然比较，MLE的明显异常分为左侧较高似然高估、右侧较高似然低估和搜索停点高估。',
    'MDM δ=0.20': 'MDM的明显异常分为阈值交点低估和右端回退高估。',
    'WMLE': 'WMLE的明显异常分为右侧交点低估和左侧交点高估，原结果均满足两条校准方程。',
    'MMLE': 'MMLE的明显异常分为最小值平移低估、删点后集中高估和完整样本集中高估。',
}
PRINCIPLE_STARTS = {
    'LSE': 'LSE通过调整γ',
    'LRE': 'LRE拟合的Weibull关系为',
    'MLE': 'MLE同时搜索形状',
    'MDM δ=0.20': 'MDM先在每个候选γ',
    'WMLE': 'WMLE用两条校准方程',
    'MMLE': 'MMLE直接用样本最小值',
}
OLD_NOTE = '分类表的单元格列出出现该类异常的样本量n，列名括号内为异常数量。'
HEADING = '### 2.1　各方法的异常形成机制\n\n'
PREAMBLE = '三张热力表分别列出n=7、15、30时各类异常的发生次数，空白格为0。'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def truth(row):
    return tuple(float(row[name]) for name in ['beta_true', 'eta_true', 'gamma_true'])


def combo_name(values):
    return 'W(' + ','.join(f'{value:g}' for value in values) + ')'


def render_heatmap(n, matrix, row_keys, combinations):
    """Use identical rows, columns, limits, and counts for all three tables."""
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
        'font.size': 11, 'axes.unicode_minus': False,
        'axes.linewidth': 0.6,
    })
    cmap = LinearSegmentedColormap.from_list(
        'restrained_blue', ['#ffffff', '#e0edf5', '#a8cbdc', '#5d95b3', '#255d7b'])
    norm = Normalize(0, 25)
    fig = plt.figure(figsize=(13.8, 8.5), facecolor='white')
    ax = fig.add_axes([0.235, 0.235, 0.69, 0.68])
    cax = fig.add_axes([0.943, 0.235, 0.013, 0.68])
    artist = ax.imshow(matrix, cmap=cmap, norm=norm, aspect='auto', interpolation='nearest')
    ax.set_xticks(range(len(combinations)))
    ax.set_xticklabels([combo_name(c) for c in combinations], rotation=48,
                       ha='right', rotation_mode='anchor', fontsize=10)
    ax.set_yticks(range(len(row_keys)))
    ax.set_yticklabels([r[2] for r in row_keys], fontsize=11)
    ax.tick_params(axis='both', length=0, pad=7)
    ax.set_xticks(np.arange(-0.5, len(combinations), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_keys), 1), minor=True)
    ax.grid(which='minor', color='#e5e9ec', linewidth=0.45)
    ax.tick_params(which='minor', bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_color('#d6dde1')
    positive_texts = []
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            value = int(matrix[y, x])
            if value:
                txt = ax.text(x, y, str(value), ha='center', va='center', fontsize=11,
                              color='white' if value >= 17 else '#263746')
                positive_texts.append((txt, value, x, y))
    starts = [0]
    for i in range(1, len(row_keys)):
        if row_keys[i][0] != row_keys[i-1][0]:
            starts.append(i)
            ax.axhline(i-0.5, color='#94a1ab', linewidth=0.9)
    starts.append(len(row_keys))
    method_texts = []
    for begin, end in zip(starts, starts[1:]):
        method = row_keys[begin][0]
        label = 'MDM\nδ=0.20' if method.startswith('MDM') else method
        center_fraction = 1-(begin+end)/(2*len(row_keys))
        txt = ax.text(-0.265, center_fraction, label, transform=ax.transAxes,
                      ha='center', va='center', fontsize=11.5, fontweight='bold',
                      color='#253441', linespacing=1.5, clip_on=False)
        method_texts.append(txt)
    ax.set_title(f'n = {n}', loc='left', fontsize=13, pad=13)
    bar = fig.colorbar(artist, cax=cax, ticks=[0, 5, 10, 15, 20, 25])
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, pad=5, labelsize=10)
    bar.ax.set_title('次数', fontsize=10, pad=10)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    label_boxes = [txt.get_window_extent(renderer) for txt in
                   [*ax.get_xticklabels(), *ax.get_yticklabels(), *method_texts,
                    ax.title, ax._left_title, *bar.ax.get_yticklabels()]]
    assert all(b.x0 >= 0 and b.y0 >= 0 and b.x1 <= canvas.x1 and b.y1 <= canvas.y1
               for b in label_boxes), 'A table label falls outside the canvas'
    for text, value, x, y in positive_texts:
        assert text.get_text() == str(int(matrix[y, x])) == str(value)
    filename = IMAGES / f'分类热力表_n{n}.png'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.savefig(filename, dpi=400, facecolor='white')
    assert not any('Glyph' in str(w.message) for w in caught), 'Missing font glyph'
    plt.close(fig)
    with Image.open(filename) as image:
        assert image.format == 'PNG' and image.size == (5520, 3400)
        dimensions = image.size
    return dict(path=str(filename), sha256=digest(filename), pixels=dimensions,
                n=n, shape=list(matrix.shape), color_limits=[0, 25],
                ticks=[0, 5, 10, 15, 20, 25], zero_cells_blank=True,
                annotated_positive_cells=len(positive_texts), all_labels_within_canvas=True)


def revise_report(original):
    current = original
    bodies = {}
    for index, method in enumerate(METHODS, 1):
        heading = f'#### 2.1.{index}　{method.split(" δ=")[0]}'
        leading, section = current.split(heading, 1)
        next_heading = '#### 2.1.' if index < 6 else '### 2.2'
        area, tail = section.split(next_heading, 1)
        body = area[area.index(PRINCIPLE_STARTS[method]):]
        bodies[method] = hashlib.sha256(body.encode()).hexdigest()
        area = '\n\n' + LEADS[method] + '\n\n' + body
        current = leading + heading + area + next_heading + tail
    block = PREAMBLE + '\n\n'
    for i, n in enumerate(SAMPLE_SIZES, 1):
        block += (f'![n={n}时各类明显异常估计的发生次数]'
                  f'(跨组合诊断/20261009-形状异常退化解/图片/分类热力表_n{n}.png)\n\n'
                  f'**表{i}｜n={n}时各类明显异常估计的发生次数。**\n\n')
    leading, section = current.split(HEADING, 1)
    marker = '以下组图中的γ₀、η₀'
    assert marker in section
    current = leading + HEADING + block + section[section.index(marker):]
    assert OLD_NOTE not in current
    assert current.split('\n## 2', 1)[0] == original.split('\n## 2', 1)[0]
    assert current.split('### 2.2', 1)[1] == original.split('### 2.2', 1)[1]
    assert re.findall(r'\*\*图(\d+)｜', current) == list(map(str, range(1, 19)))
    assert re.findall(r'\*\*表(\d+)｜', current) == ['1', '2', '3']
    assert not re.findall(r'^\| 参数组合 \|', current, flags=re.M)
    assert re.findall(r'^\| (?:正常|异常)[^\n]*', current, flags=re.M) == re.findall(
        r'^\| (?:正常|异常)[^\n]*', original, flags=re.M)
    for index, method in enumerate(METHODS, 1):
        heading = f'#### 2.1.{index}　{method.split(" δ=")[0]}'
        area = current.split(heading, 1)[1].split(
            '#### 2.1.' if index < 6 else '### 2.2', 1)[0]
        body = area[area.index(PRINCIPLE_STARTS[method]):]
        assert hashlib.sha256(body.encode()).hexdigest() == bodies[method]
    return current, bodies


def main():
    data_path = HERE / '20261010-各类异常参数空间.csv'
    data_qa_path = HERE / '20261010-各类异常参数空间核验.json'
    class_path = HERE / '20261010-六方法异常情形.csv'
    class_qa_path = HERE / '20261010-六方法异常情形核验.json'
    flow_path = HERE / '全量流程定位.csv'
    frequency_path = HERE / '第一章频率.csv'
    data_qa = json.loads(data_qa_path.read_text(encoding='utf-8'))
    assert digest(data_path) == data_qa['data_sha256']
    sources = dict(data_qa['source_sha256'])
    sources.update({str(p):digest(p) for p in [data_path, data_qa_path, class_path,
                                              class_qa_path, flow_path, frequency_path,
                                              Path(__file__)]})
    assert all(digest(path) == value for path, value in sources.items())
    protected_pngs = {str(p):digest(p) for p in IMAGES.glob('*.png')
                      if p.name not in {f'分类热力表_n{n}.png' for n in SAMPLE_SIZES}}
    original_report = REPORT.read_text(encoding='utf-8')
    cells = read_csv(data_path)
    assert len(cells) == 624
    row_keys = list(dict.fromkeys((r['method'], r['case'], r['case_label']) for r in cells))
    assert len(row_keys) == 16
    assert list(dict.fromkeys(row[0] for row in row_keys)) == METHODS
    combinations = sorted({truth(r) for r in cells})
    assert len(combinations) == 13
    counts = {}
    for r in cells:
        cell = r['method'], r['case'], truth(r), int(r['n'])
        assert cell not in counts
        counts[cell] = int(r['count'])
        assert 0 <= counts[cell] <= 50
    assert sum(counts.values()) == 963
    assert set(c[3] for c in counts) == set(SAMPLE_SIZES)

    classes = read_csv(class_path)
    full = read_csv(flow_path)
    record_key = lambda r: (r['combination'], int(r['n']), int(r['group']), r['method'])
    abnormal = {record_key(r):r for r in full if r['abnormal'] == 'True'}
    assert len(classes) == len(abnormal) == 963
    assert len({record_key(r) for r in classes}) == 963
    assert {record_key(r) for r in classes} == set(abnormal)
    independently_counted = Counter()
    for r in classes:
        origin = abnormal[record_key(r)]
        for parameter in ['beta_hat', 'eta_hat', 'gamma_hat', 'beta_true', 'eta_true', 'gamma_true']:
            assert float(r[parameter]) == float(origin[parameter])
        case = r['case']
        if r['method'] == 'MMLE' and case == 'concentrated_retained_high':
            already_high = float(origin['beta_full_sample_fixed_true']) >= 3*float(origin['beta_true'])
            case = 'complete_concentrated_high' if already_high else 'deletion_concentrated_high'
        independently_counted[r['method'], case, truth(r), int(r['n'])] += 1
    assert all(count == independently_counted[key] for key, count in counts.items())
    assert all(key in counts for key in independently_counted)

    frequency = {(r['method'], r['combination'], int(r['n'])):r for r in read_csv(frequency_path)}
    frequency_checks = []
    for method in METHODS:
        for combo in combinations:
            for n in SAMPLE_SIZES:
                count = sum(v for (m, _, c, nn), v in counts.items()
                            if (m, c, nn) == (method, combo, n))
                original = frequency[method, combo_name(combo), n]
                assert int(original['total']) == 50 and count == int(original['abnormal'])
                frequency_checks.append(dict(method=method, combination=combo_name(combo), n=n, count=count))
    assert len(frequency_checks) == 234
    report, mechanism_hashes = revise_report(original_report)

    matrices = {}
    figures = []
    for n in SAMPLE_SIZES:
        matrix = np.array([[counts[m, case, combo, n] for combo in combinations]
                           for m, case, _ in row_keys], dtype=int)
        assert matrix.shape == (16, 13)
        matrices[str(n)] = matrix.tolist()
        figures.append(render_heatmap(n, matrix, row_keys, combinations))
    assert all(digest(path) == value for path, value in sources.items())
    assert all(digest(path) == value for path, value in protected_pngs.items())
    REPORT.write_text(report, encoding='utf-8')
    output = dict(
        scope='R00 only; all 963 archived anomalies and 624 condition cells, including zeros.',
        figure_contract=dict(
            claim='Sample size, method and parameter conditions distinguish the frequencies of individual anomaly cases.',
            archetype='quantitative grid', backend='Python/matplotlib', export='PNG only, 400 dpi',
            evidence='Three tables use the same 16 case rows and 13 truth-parameter columns; n=7,15,30.',
            statistic='Count of classified archived estimates out of 50 original sample groups per method/combination/n.',
            threshold='beta_hat >= 3*beta_true or beta_hat <= beta_true/3',
            zero_display='Blank white cell; all zeros retained in source data.',
            no_axis_or_color_clipping=True, resampling=False, reestimation=False),
        row_order=[dict(method=m, case=c, label=l) for m,c,l in row_keys],
        column_order=[combo_name(c) for c in combinations],
        sample_sizes=SAMPLE_SIZES, counts_by_n={n:int(np.sum(matrices[str(n)])) for n in SAMPLE_SIZES},
        matrices=matrices, figures=figures, frequency_cell_checks=frequency_checks,
        original_anomaly_records=963, cells=624, independent_classification_count_matches=True,
        figure1_frequency_reconciled=True, source_sha256=sources,
        sources_unchanged=True, protected_png_sha256=protected_pngs, existing_pngs_unchanged=True,
        chapter1_unchanged=True, mechanism_bodies_unchanged=mechanism_hashes,
        section2_2_and_chapter3_unchanged=True, sample_tables_unchanged=True,
        report_sha256=digest(REPORT), visual_review='pending',
    )
    qa_path = HERE / f'{PREFIX}核验.json'
    if qa_path.exists():
        prior = json.loads(qa_path.read_text(encoding='utf-8'))
        if [f['sha256'] for f in prior['figures']] == [f['sha256'] for f in figures]:
            output['visual_review'] = prior.get('visual_review', 'pending')
    qa_path.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: three 16x13 heatmap tables cover all 963 anomalies; 624 counts independently checked; '
          'all 234 Figure 1 totals match; samples, estimates, existing figures and mechanism bodies unchanged.')


if __name__ == '__main__':
    main()
