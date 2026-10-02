"""Rebuild the reviewed report and its LSE/LRE labels from saved results.

Use conventional regression notation 1-R² instead of the report-only D alias.
Reuse the existing report generator, plotting functions and provenance audit.
No samples, estimates, curve values or six-panel axis settings are changed.
"""
import json

import 生成报告 as report
import 绘制公式与拟合点图 as methods
from 统一简洁图样 import hashes, audit_figures


def main():
    before = hashes()
    report.main()
    target = methods.DATA / '逐法图核验.json'
    qa = json.loads(target.read_text(encoding='utf-8'))
    for index, figure in enumerate(qa['process_figures']):
        if figure['method'] in ('lse', 'lre'):
            updated = methods.method_figure(figure['method'])
            for old, new in zip([*figure['panels'], *figure['single_panels']],
                                [*updated['panels'], *updated['single_panels']]):
                assert old['axis_settings'] == new['axis_settings']
            qa['process_figures'][index] = updated
    target.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    audit_figures(before, task='2026-10-02: conventional formula notation and immediate symbol definitions; redraw LSE/LRE labels only')
    print('Rebuilt report and two labelled figures; data and all six-panel axes unchanged.')


if __name__ == '__main__':
    main()
