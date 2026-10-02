"""2026-10-02: redraw five method figures with identical axes in all six panels.

Reuse saved curves and paired examples; no sampling or parameter estimation.
Keep the current auxiliary figures and numerical inputs unchanged.
"""
import json
import 绘制公式与拟合点图 as methods
from 统一简洁图样 import hashes, audit_figures


def main():
    before = hashes()
    target = methods.DATA / '逐法图核验.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    qa['process_figures'] = [methods.method_figure(m) for m in methods.base.METHODS]
    target.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    audit_figures(before, task='2026-10-02: identical limits, scales and ticks across all six method panels')
    print('Verified identical x/y limits, scale types, tick positions and labels in five six-panel figures.')


if __name__ == '__main__':
    main()
