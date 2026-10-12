"""在报告2的2.1节前增加两类异常的分类原则，保留原计算和图片。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_typical_process', HERE / '20261012-典型形成过程表述.py')
prior = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prior
spec.loader.exec_module(prior)
base = prior.base
QA = HERE / (Path(__file__).stem + '-核验.json')
PRINCIPLE = '本报告将明显异常区分为两类：一类是在当前方法准则下确实存在的偏离真值的优选参数组合；另一类由搜索、停止或候选接受环节造成。'
BEFORE = '\n\n### 2.1　各方法的典型形成过程'
AFTER = '\n\n' + PRINCIPLE + BEFORE


def correct(text):
    if AFTER in text:
        return text
    assert text.count(BEFORE) == 1
    return text.replace(BEFORE, AFTER)


def apply():
    text = base.REPORT.read_text(encoding='utf-8')
    revised = correct(text)
    pair = base.module('20261011-MDM近真值对照')
    if revised != text:
        assert not QA.exists(), 'Preserve existing revision record'
        previous = base.load(prior.QA)
        assert base.text_digest(text) == previous['after_text_sha256']
        record = dict(before_text_sha256=base.text_digest(text), after_text_sha256=base.text_digest(revised),
                      outside_before_sha256=base.text_digest(pair.block(text)[1]),
                      outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                      previous_wording=dict(after_text_sha256=previous['after_text_sha256'],
                                            outside_after_sha256=previous['outside_after_sha256'],
                                            replacements=previous['replacements']), principle=PRINCIPLE)
        pair.write_text(base.REPORT, revised)
        base.write_json(QA, record)
        previous.update(after_text_sha256=record['after_text_sha256'],
                        outside_after_sha256=record['outside_after_sha256'], replacements=prior.REPLACEMENTS,
                        classification_revision=QA.name)
        base.write_json(prior.QA, previous)
        existing = base.load(pair.QA)
        assert existing['outside_block_sha256'] == record['outside_before_sha256']
        existing.update(outside_block_sha256=record['outside_after_sha256'], classification_revision=QA.name)
        base.write_json(pair.QA, existing)
    readme = base.ROOT / 'README.md'
    content = readme.read_text(encoding='utf-8')
    anchor = '报告2按典型形成过程组织分析，'
    changed = '报告2按典型形成过程组织分析，在2.1前区分方法准则支持的优选组合与搜索、停止或候选接受造成的异常；[分类原则脚本](交付/程序/报告2/20261012-异常分类原则.py)保存本次插入；'
    if changed not in content:
        assert content.count(anchor) == 1
        pair.write_text(readme, content.replace(anchor, changed))
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-MLE总述精简-核验.json').exists():
        text = base.module('20261012-MLE总述精简').restore(text)
    assert correct(text) == text and text.count(PRINCIPLE) == 1
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(text.replace(AFTER, BEFORE)) == record['before_text_sha256']
    prior.verify()
    record.update(validation='passed', formulas_tables_data_figures_unchanged=True, script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: classification principle occurs once before 2.1; formulas, results and figures unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
