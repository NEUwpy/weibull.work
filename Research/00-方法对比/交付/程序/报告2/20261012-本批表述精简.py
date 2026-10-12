"""删去结论中的三处重复限定，保留五处实际实现与实验条件。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_scope_wording', HERE / '20261012-MLE总述精简.py')
run = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run
spec.loader.exec_module(run)
base = run.base
QA = HERE / (Path(__file__).stem + '-核验.json')
REPLACEMENTS = {
    '本批明显异常分为阈值交点低估和程序回退高估。': '明显异常分为阈值交点低估和程序回退高估。',
    '本批左侧大形状候选较多得到似然支持。': '左侧大形状候选较多得到似然支持。',
    '本批较多出现小形状结果。': '较多出现小形状结果。',
}


def restore(text):
    if (HERE / '20261012-共同样本特征与方法响应-核验.json').exists():
        text = base.module('20261012-共同样本特征与方法响应').restore(text)
    for before, after in REPLACEMENTS.items():
        text = text.replace(after, before)
    return text


def apply():
    text = base.REPORT.read_text(encoding='utf-8')
    if QA.exists():
        verify()
        return
    revised = text
    for before, after in REPLACEMENTS.items():
        assert revised.count(before) == 1
        revised = revised.replace(before, after)
    previous = base.load(run.prior.QA)
    assert base.text_digest(text) == previous['after_text_sha256']
    pair = base.module('20261011-MDM近真值对照')
    record = dict(before_text_sha256=base.text_digest(text), after_text_sha256=base.text_digest(revised),
                  previous_outside_sha256=previous['outside_after_sha256'], replacements=REPLACEMENTS,
                  before_count=text.count('本批'), preserved_settings=[line for line in revised.splitlines() if '本批' in line])
    pair.write_text(base.REPORT, revised)
    base.write_json(QA, record)
    previous.update(after_text_sha256=record['after_text_sha256'], outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                    replacements=run.prior.REPLACEMENTS, batch_wording_revision=QA.name)
    base.write_json(run.prior.QA, previous)
    existing = base.load(pair.QA)
    assert existing['outside_block_sha256'] == record['previous_outside_sha256']
    existing.update(outside_block_sha256=previous['outside_after_sha256'], batch_wording_revision=QA.name)
    base.write_json(pair.QA, existing)
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-共同样本特征与方法响应-核验.json').exists():
        text = base.module('20261012-共同样本特征与方法响应').restore(text)
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert text.count('本批') == record['before_count'] - 3 == 5
    assert [line for line in text.splitlines() if '本批' in line] == record['preserved_settings']
    run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: three redundant qualifiers removed; five setting qualifiers, formulas, data and figures retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
