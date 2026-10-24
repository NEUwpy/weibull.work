"""重绘home报告已公开在正文中的40格结果，不读取或重建原模型预测。

结论：样本特征分类器的测试多数票恢复35/40格，遗漏4个LSE格和1个MLE格。
证据：左图为冻结地图，右图为测试样本多数票；不把格子匹配当逐样本准确率。
图型：quantitative grid；Python/matplotlib；双栏地图、可编辑SVG及审阅PNG。
数据源：地图分类匹配报告中的逐格表；不新增样本、训练或统计推断。
"""
from pathlib import Path
import hashlib
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle
import numpy as np

STUDY = Path(__file__).resolve().parents[2]
SOURCE = STUDY / 'B10方法选择-地图分类匹配-v1.0.md'
ASSETS = STUDY / 'reviewbyhtml/方法对比-v1.0/assets'
METHODS = ['MLE', 'WMLE', 'LSE', 'LRE(Park)', 'MDM-0.1']
SHORT = ['MLE', 'WMLE', 'LSE', 'LRE', 'MDM']
COLORS = ['#F5D7A3', '#C1DEEE', '#B3DACB', '#DEC4D8', '#F4EDB4']


def main():
    text = SOURCE.read_text(encoding='utf-8')
    rows = []
    for line in text.splitlines():
        if not re.match(r'^\| (50|20|15|10|7) \|', line) or '→' not in line:
            continue
        cells = [c.strip().replace('**', '') for c in line.strip('|').split('|')]
        rows.append((int(cells[0]), [tuple(v.strip() for v in c.split('→')) for c in cells[1:]]))
    assert [n for n, _ in rows] == [50, 20, 15, 10, 7]
    assert all(len(cells) == 8 for _, cells in rows)
    matches = sum(a == b for _, cells in rows for a, b in cells)
    assert matches == 35
    plt.rcParams.update({
        'font.family': ['Times New Roman', 'Microsoft YaHei'],
        'font.size': 8, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'axes.linewidth': .6, 'figure.facecolor': 'white',
    })
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.35))
    cmap = ListedColormap(COLORS)
    for panel, ax in enumerate(axes):
        matrix = np.array([[METHODS.index(pair[panel]) for pair in cells] for _, cells in rows])
        ax.imshow(matrix, cmap=cmap, vmin=-.5, vmax=4.5, aspect='auto')
        ax.set_xticks(range(8), ['1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5'])
        ax.set_yticks(range(5), [n for n, _ in rows])
        ax.set_xlabel(r'$\beta$')
        ax.set_ylabel(r'$n$')
        ax.set_title(['(a) 原B10性能地图', '(b) 测试样本预测的多数票'][panel], loc='left', fontsize=10, pad=10)
        ax.set_xticks(np.arange(-.5, 8, 1), minor=True)
        ax.set_yticks(np.arange(-.5, 5, 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=1.3)
        ax.tick_params(which='both', length=0)
        for i, (_, cells) in enumerate(rows):
            for j, pair in enumerate(cells):
                ax.text(j, i, SHORT[matrix[i, j]], ha='center', va='center', fontsize=8)
                if panel == 1 and pair[0] != pair[1]:
                    ax.add_patch(Rectangle((j-.46, i-.46), .92, .92,
                                           fill=False, edgecolor='#333333', linewidth=1.15, linestyle='--'))
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.subplots_adjust(left=.05, right=.99, top=.83, bottom=.17, wspace=.19)
    target = ASSETS / '43_B10地图分类对照'
    for ext in ['png', 'svg']:
        fig.savefig(target.with_suffix('.'+ext), dpi=250, bbox_inches='tight')
    vector = target.with_suffix('.svg')
    vector.write_text('\n'.join(line.rstrip() for line in vector.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)
    manifest = {
        'source_report': SOURCE.relative_to(STUDY).as_posix(),
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'source_commit': 'b2d445df1a70af26d0e95a0e7f61439249a4295c',
        'basis': 'Published 40-cell table; no model or raw prediction recomputation',
        'map_matches': matches, 'total_cells': 40,
        'individual_match_count': 7053, 'test_groups': 9642,
        'mismatches': [{'n': n, 'beta': [1.5,2,2.5,3,3.5,4,4.5,5][j],
                        'map': a, 'prediction': b} for n, cells in rows
                       for j, (a, b) in enumerate(cells) if a != b],
    }
    (Path(__file__).with_suffix('.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
