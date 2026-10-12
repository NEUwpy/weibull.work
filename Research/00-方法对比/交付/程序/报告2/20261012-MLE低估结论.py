"""将MLE第4组的求解不足与持续低估写成两个直接结论。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_mle_wording', HERE / '20261012-MLE总述精简.py')
run = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run
spec.loader.exec_module(run)
base = run.base
QA = HERE / (Path(__file__).stem + '-核验.json')
BEFORE = '右移使最小距离明显缩小，对数跨度扩大，式（23）的均值之差增大，条件形状降至1.44。原返回点右侧的β=1分支还有更高似然，表明该结果同时包含求解不足；沿该分支改善似然后，形状仍低于5/3。'
AFTER = ('右移使最小距离明显缩小，对数跨度扩大，式（23）的均值之差增大，条件形状降至1.44。\n\n'
         '原返回值不是接受域内的最优候选，属于数值求解不足。进一步沿更高似然的β=1分支搜索后，形状仍低于异常阈值5/3，因此该样本的低估不能完全由数值求解问题解释。')


def restore(text):
    if (HERE / '20261012-位置尺度比解释-核验.json').exists():
        text = base.module('20261012-位置尺度比解释').restore(text)
    return text.replace(AFTER, BEFORE)


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-位置尺度比解释-核验.json').exists():
        text = base.module('20261012-位置尺度比解释').restore(text)
    assert text.count(AFTER) == 1 and BEFORE not in text
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: group4 conclusions separated; calculations, tables and figures unchanged.')


def apply():
    run.BEFORE, run.AFTER, run.QA, run.verify = BEFORE, AFTER, QA, verify
    run.apply()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
