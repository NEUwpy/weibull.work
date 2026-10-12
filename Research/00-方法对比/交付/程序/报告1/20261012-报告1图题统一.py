"""Apply Report 1's fifteen figure titles without changing figures or prose."""
from pathlib import Path
import argparse
import os
import re
import tempfile

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[2] / '报告1：高形状参数下的估计偏移.md'
TITLES = {
    1: '不同样本量下的参数估计偏移',
    2: '最小观测对位置参数的约束',
    3: '位置—尺度—形状参数的补偿效应',
    4: '固定梯度阈值下的MDM位置偏移',
    5: 'MDM参数偏移的传递关系',
    6: '不同β与样本量下LSE位置判据的变化',
    7: 'LSE位置偏移的参数传递',
    8: '不同β与样本量下LRE相关系数随γ的变化',
    9: 'LRE位置偏移的参数传递',
    10: 'WMLE联合判据下的位置偏移',
    11: 'WMLE参数的联合求解与尺度恢复',
    12: '不同β与样本量下MLE剖面对数似然随γ的变化',
    13: 'MLE位置偏移下的参数补偿',
    14: 'MMLE最小值定位下的形状估计偏移',
    15: 'MMLE参数估计的传递过程',
}
CAPTION = re.compile(r'^\*\*图(\d+)｜[^\n]*?\*\*', re.MULTILINE)
IMAGE = re.compile(r'^!\[图(\d+)[\s　][^\]\n]*\](?=\()', re.MULTILINE)


def normalized(text):
    updated = CAPTION.sub(lambda m: f'**图{m[1]}｜{TITLES[int(m[1])]}**', text)
    return IMAGE.sub(lambda m: f'![图{m[1]}　{TITLES[int(m[1])]}]', updated)


def without_titles(text):
    text = CAPTION.sub(lambda m: f'**图{m[1]}｜TITLE**', text)
    return IMAGE.sub(lambda m: f'![图{m[1]}　TITLE]', text)


def verify():
    text = REPORT.read_text(encoding='utf-8')
    assert [int(m[1]) for m in CAPTION.finditer(text)] == list(TITLES)
    assert [int(m[1]) for m in IMAGE.finditer(text)] == list(TITLES)
    assert normalized(text) == text
    print('核对通过：15个图题与图片标题一致，顺序为图1—15。')


def apply():
    before = REPORT.read_text(encoding='utf-8')
    after = normalized(before)
    assert without_titles(before) == without_titles(after)
    if after != before:
        with tempfile.NamedTemporaryFile(dir=REPORT.parent, prefix='.figure-titles-',
                                         suffix='.tmp', delete=False) as handle:
            handle.write(after.encode('utf-8'))
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, REPORT)
    assert REPORT.read_text(encoding='utf-8') == after
    verify()
    print('已统一图题；正文、公式、标记说明和图片路径保持不变。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'verify'], nargs='?', default='verify')
    globals()[parser.parse_args().action]()
