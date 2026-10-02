"""2026-10-02 figure revision from saved results; no sampling or estimation.

Rebuild Figures 2–7 and the six supplements with short coordinate labels.
Keep all curves, observations and necessary fitting-point identifiers.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import 绘制公式与拟合点图 as methods
import 绘制补充图 as supplements
import 绘制寿命对照图 as lifetime

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '结果'
DATA = OUT / '中间数据'
RENAMES = {
    '图2_MDM位置选择过程': '图2_MDM六格机制',
    '图3_LSE位置选择过程': '图3_LSE六格机制',
    '图4_LRE位置选择过程': '图4_LRE六格机制',
    '图5_WMLE位置选择过程': '图5_WMLE六格机制',
    '图6_MLE位置选择过程': '图6_MLE六格机制',
    '图7_不同参数的寿命曲线与分位点': '图7_寿命分布与分位点',
    '补充图1_成功比例': '补充图1_估计成功率',
    '补充图2_LRE版本': '补充图2_LRE绘图位置对照',
    '补充图3_形状与下尾信息': '补充图3_下尾观测对照',
    '补充图4_连续形状估计变化': '补充图4_连续形状对照',
    '补充图5_参数补偿与固定位置': '补充图5_位置尺度补偿',
}
INPUTS = [
    DATA / name for name in ('实际估计.json', '样本.json', '汇总.json',
                            '逐法过程曲线.json', '单组绘图点与方程.json')
] + [ROOT / '程序' / '输入快照' / name
     for name in ('原案例估计.json', '原案例核验.json')]


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in INPUTS}


def main():
    before = hashes()
    methods.main()
    supplements.lower_tail()
    supplements.continuous_estimates()
    supplements.compensation()
    supplements.supplement()
    lifetime.main()
    assert hashes() == before, 'Saved scientific inputs changed during plotting.'
    figures = []
    for name in [*RENAMES.values(),'补充图6_原案例回归与方程']:
        texts = [''.join(element.itertext()).strip() for element in ET.parse(
            OUT / f'{name}.svg').findall('.//{http://www.w3.org/2000/svg}text')]
        assert texts
        assert not any(token in text for text in texts
                       for token in ('阈值 0.10', '越低越好', '候选位置', '候选形状',
                                     '怎样读', '怎样算', '标准差剖面梯度'))
        assert all(sum('\u4e00' <= c <= '\u9fff' for c in text) <= 12
                   for text in texts), 'Long explanatory text remains on a figure.'
        figures.append({'file': name, 'formats': ['png', 'pdf', 'svg'],
                        'svg_text_labels': texts,
                        'notes_on_figure': False})
    qa = json.loads((DATA / '逐法图核验.json').read_text(encoding='utf-8'))
    for figure in qa['process_figures']:
        for panel in figure['single_panels']:
            detail = panel['detail']
            if detail['type'] == 'numbered_formula_evaluations':
                assert detail['labelled_point_ids'] == [detail['true_gamma_point_id'],
                                                       detail['returned_gamma_point_id']]
            if detail['type'] == 'observed_regression_points':
                assert detail['all_observation_ids_labelled']
    record = {
        'task': '2026-10-02: paired criterion figures and concise supplementary plots',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'new_samples': 0, 'new_fits': 0,
        'scientific_input_hashes': before, 'scientific_inputs_unchanged': True,
        'figure1_unchanged': True, 'file_renames': RENAMES,
        'notes_location': 'Report definitions and figure captions',
        'all_regression_observation_numbers_preserved': True,
        'formula_point_labels': 'Only the true and returned gamma point identifiers; all points preserved.',
        'figures': figures,
    }
    (DATA / '简洁图样核验.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    print('EXPORTED and checked 12 figures; saved scientific inputs unchanged.')


if __name__ == '__main__':
    main()
