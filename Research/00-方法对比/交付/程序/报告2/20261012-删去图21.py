"""仅删去报告2正文的图21及图题，保留响应比较与计算记录。"""
from pathlib import Path
import argparse
import importlib.util
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_improvement_tasks', HERE / '20261012-针对性改进任务.py')
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)
base, prior = stage.base, stage.prior
QA = HERE / (Path(__file__).stem + '-核验.json')
IMAGE = '交付/结果/报告2/固定位置的回归与形状得分.png'
BLOCK = ('![固定位置时对数距离集中对回归与似然形状的影响](' + IMAGE + ')\n\n'
         '**图21｜固定真位置时，距离集中仍可能对应较大形状。**\n\n')
ANCHOR = '#### 2.3.3　对距离过度分散或远端点的响应'


def correct(text):
    if QA.exists():
        for before, after in base.load(QA).get('existing_working_copy_edits', {}).items():
            text = text.replace(before, after)
    assert text.count(BLOCK) <= 1
    return text.replace(BLOCK, '')


def restore_current(text):
    if IMAGE not in text and text.count(ANCHOR) == 1:
        return text.replace(ANCHOR, BLOCK + ANCHOR)
    return text


def restore(text):
    text = restore_current(text)
    if QA.exists():
        record = base.load(QA)
        if base.text_digest(text) == record['before_text_sha256']:
            for before, after in reversed(list(record.get('existing_working_copy_edits', {}).items())):
                text = text.replace(after, before) if after else text + before
            assert base.text_digest(text) == record['previous_check_text_sha256']
    return text


def apply():
    if QA.exists():
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    assert text.count(BLOCK) == 1
    expected = stage.correct(base.load(stage.stage.QA)['after_text'])
    assert base.text_digest(expected) == base.load(stage.QA)['after_text_sha256']
    previous = base.load(prior.QA)
    assert base.text_digest(expected) == previous['after_text_sha256']
    table = re.compile(r'^\| 样本特征[^\n]*\n(?:\|[^\n]*\n)+', re.M)
    edits = {table.search(expected)[0]: table.search(text)[0]}
    ending = '\n这两个研究方向应在独立模拟样本上比较参数误差、明显异常频率及求解成功率，检验是否减少异常而未扩大其他条件下的误差。\n'
    if ending in expected and ending not in text:
        edits[ending] = ''
    accepted = expected
    for before, after in edits.items():
        accepted = accepted.replace(before, after)
    assert accepted == text, 'Unexpected concurrent report edit'
    revised = correct(text)
    pair = base.module('20261011-MDM近真值对照')
    record = dict(removed_block=BLOCK, before_text_sha256=base.text_digest(text),
                  after_text_sha256=base.text_digest(revised),
                  previous_check_text_sha256=base.text_digest(expected),
                  existing_working_copy_edits=edits,
                  previous_outside_sha256=previous['outside_after_sha256'])
    base.write_json(QA, record)
    pair.write_text(base.REPORT, revised)
    previous.update(after_text_sha256=record['after_text_sha256'],
                    outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    figure21_removal=QA.name)
    base.write_json(prior.QA, previous)
    old_pair = base.load(pair.QA)
    assert old_pair['outside_block_sha256'] == record['previous_outside_sha256']
    old_pair.update(outside_block_sha256=previous['outside_after_sha256'], figure21_removal=QA.name)
    base.write_json(pair.QA, old_pair)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    anchor = '保存直白的2.3及原公式归位，'
    assert content.count(anchor) == 1
    content = content.replace(anchor, anchor + '[删图脚本](交付/程序/报告2/20261012-删去图21.py)移除正文图21，')
    assert content.count('正文现有21张图') == 1
    pair.write_text(readme, content.replace('正文现有21张图', '正文现有20张图'))
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    assert correct(text) == text and IMAGE not in text and '图21' not in text
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore_current(text)) == record['before_text_sha256']
    assert re.findall(r'^\*\*图(\d+)｜', text, re.M) == [str(i) for i in range(1, 21)]
    prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__), figures_in_report=20,
                  only_figure21_reference_and_caption_removed=True, calculations_and_source_images_unchanged=True)
    base.write_json(QA, record)
    print('PASS: figure 21 and caption removed; all other report text and calculation artifacts unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
