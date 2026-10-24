"""Side-by-side view of the fixed map and test-sample majority predictions."""
import csv
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
deps = ROOT / '.codex-tmp/b10-plot-deps'
if deps.exists():
    sys.path.insert(0, str(deps))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

STUDY = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get('B10_SELECTOR_OUTPUT', str(STUDY / '结果/B10方法选择-v1'))) / 'map_classifier'


def main():
    with (OUT / 'cells.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    methods = ['MLE', 'WMLE', 'LSE', 'LRE(Park)', 'MDM-0.1']
    short = ['MLE', 'WMLE', 'LSE', 'LRE', 'MDM']
    betas, ns = [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5], [50, 20, 15, 10, 7]
    lookup = {(int(r['n']), float(r['beta'])): r for r in rows}
    colors = ListedColormap(['#E69F00', '#56B4E9', '#009E73', '#CC79A7', '#F0E442'])
    plt.rcParams.update({'font.size': 11, 'pdf.fonttype': 42, 'figure.facecolor': 'white'})
    fig, axes = plt.subplots(1, 2, figsize=(14.8, 5.0))
    for ax, column, title in zip(axes, ['map_method', 'predicted_majority_method'],
                                 ['A  Original B10 map', 'B  Sample-feature classifier: test majority vote']):
        matrix = np.array([[methods.index(lookup[n, b][column]) for b in betas] for n in ns])
        ax.imshow(matrix, cmap=colors, vmin=-.5, vmax=4.5, aspect='auto')
        ax.set_xticks(range(len(betas)), [f'{b:g}' for b in betas])
        ax.set_yticks(range(len(ns)), ns)
        ax.set_xlabel('Shape parameter beta (grouping only)')
        ax.set_ylabel('Sample size n')
        ax.set_title(title, loc='left', fontsize=12, fontweight='bold', pad=14)
        ax.set_xticks(np.arange(-.5, len(betas), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(ns), 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=1.5)
        ax.tick_params(which='minor', length=0)
        for i, n in enumerate(ns):
            for j, beta in enumerate(betas):
                ax.text(j, i, short[matrix[i, j]], ha='center', va='center', fontsize=11)
                if column == 'predicted_majority_method' and lookup[n, beta]['map_match'] == 'False':
                    ax.add_patch(Rectangle((j-.46, i-.46), .92, .92, fill=False,
                                           edgecolor='black', linewidth=2, linestyle='--'))
    fig.text(.5, .055, 'Individual held-out groups: 7,053/9,642 match (73.15%)   |   Map majority vote: 35/40 cells match (87.5%)',
             ha='center', fontsize=12)
    fig.text(.5, .008, 'Dashed outline: mismatched cell. Beta is used only to summarize held-out predictions; it is not a model input.',
             ha='center', fontsize=10)
    fig.subplots_adjust(left=.05, right=.99, top=.88, bottom=.22, wspace=.19)
    fig.savefig(OUT / 'map_match.png', dpi=220, bbox_inches='tight')
    fig.savefig(OUT / 'map_match.pdf', bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
