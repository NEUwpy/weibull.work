"""将报告2的机制标题及导语改为典型形成过程；不修改计算或图片。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_likelihood_revision', HERE / '20261011-MMLE对数似然峰图.py')
prior = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prior
spec.loader.exec_module(prior)
base = prior.base
QA = HERE / (Path(__file__).stem + '-核验.json')
REPLACEMENTS = {
    '## 2　明显异常估计的形成机制': '## 2　明显异常估计的形成过程',
    '### 2.1　各方法的异常形成机制': '### 2.1　各方法的典型形成过程',
    '2.1节逐个方法分析正常与异常样本的估计过程，定位偏差形成的环节；2.2节解释哪些条件更容易触发这些过程；2.3节比较不同方法对同类样本特征的响应。':
    '2.1节通过正常与异常样本对照，分析各方法的典型形成过程；2.2节讨论样本条件的影响；2.3节比较不同方法对同类样本特征的响应。\n\n'
    '本报告将明显异常区分为两类：一类是在当前方法准则下确实存在的偏离真值的优选参数组合；另一类由搜索、停止或候选接受环节造成。',
    '前两类的候选比真位置条件拟合具有更高似然，其中部分返回值仍可改善。':
    '前两类候选的似然高于真位置下的条件拟合。',
    '右移使最小距离明显缩小，对数跨度扩大，式（23）的均值之差增大，条件形状降至1.44。原返回点右侧的β=1分支还有更高似然，表明该结果同时包含求解不足；沿该分支改善似然后，形状仍低于5/3。':
    '右移使最小距离明显缩小，对数跨度扩大，式（23）的均值之差增大，条件形状降至1.44。\n\n'
    '原返回值不是接受域内的最优候选，属于数值求解不足。进一步沿更高似然的β=1分支搜索后，形状仍低于异常阈值5/3，因此该样本的低估不能完全由数值求解问题解释。',
}


def correct(text):
    for before, after in REPLACEMENTS.items():
        if text.count(after) == 1:
            continue
        assert text.count(before) == 1, before
        text = text.replace(before, after)
    return text


def restore(text):
    for before, after in REPLACEMENTS.items():
        text = text.replace(after, before)
    return text


def approved_outside_hash(expected):
    if not QA.exists():
        return expected
    record = base.load(QA)
    assert expected in (record['outside_before_sha256'], record['outside_after_sha256'])
    return record['outside_after_sha256']


def apply():
    text = base.REPORT.read_text(encoding='utf-8')
    revised = correct(text)
    if revised != text:
        assert not QA.exists(), 'Existing revision record must be preserved'
        pair = base.module('20261011-MDM近真值对照')
        record = dict(before_text_sha256=base.text_digest(text), after_text_sha256=base.text_digest(revised),
                      outside_before_sha256=base.text_digest(pair.block(text)[1]),
                      outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                      protected_sha256=base.protected(), target_figures_sha256={str(p): base.digest(p) for p in base.TARGETS.values()},
                      replacements=REPLACEMENTS, script_sha256=base.digest(__file__))
        pair.write_text(base.REPORT, revised)
        base.write_json(QA, record)
        existing = base.load(pair.QA)
        assert existing['outside_block_sha256'] == record['outside_before_sha256']
        existing['outside_block_sha256'] = record['outside_after_sha256']
        existing['typical_process_revision'] = QA.name
        base.write_json(pair.QA, existing)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    content = content.replace('两者可以共享机制，但分别组织论证。', '两者可以共享部分解释，但分别组织论证。')
    old = '报告正文保存在本目录，图片保存在`交付/结果/报告1`或`交付/结果/报告2`；正文引用与制图输出路径保持一致。'
    new = old + '报告2按典型形成过程组织分析，[表述修订脚本](交付/程序/报告2/20261012-典型形成过程表述.py)提供`apply`、`verify`，核验记录留在程序目录。'
    if new not in content:
        assert content.count(old) == 1
        content = content.replace(old, new)
    base.module('20261011-MDM近真值对照').write_text(readme, content)
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    assert correct(text) == text
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert base.protected() == record['protected_sha256']
    assert all(base.digest(p) == sha for p, sha in record['target_figures_sha256'].items())
    record.update(validation='passed', changes=len(REPLACEMENTS), formulas_tables_estimates_figures_unchanged=True,
                  script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: typical-process headings, introduction and classification; formulas, tables and figures unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
