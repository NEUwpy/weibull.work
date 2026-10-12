"""删去MLE总述中提前插入的候选改善说明，保留正文中的具体复核。"""
from pathlib import Path
import argparse
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_wording', HERE / '20261012-典型形成过程表述.py')
prior = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prior
spec.loader.exec_module(prior)
base = prior.base
QA = HERE / (Path(__file__).stem + '-核验.json')
BEFORE = '前两类的候选比真位置条件拟合具有更高似然，其中部分返回值仍可改善。'
AFTER = '前两类候选的似然高于真位置下的条件拟合。'


def restore(text):
    if (HERE / '20261012-MLE低估结论-核验.json').exists():
        text = base.module('20261012-MLE低估结论').restore(text)
    return text.replace(AFTER, BEFORE)


def apply():
    text = base.REPORT.read_text(encoding='utf-8')
    if AFTER not in text:
        assert text.count(BEFORE) == 1 and not QA.exists()
        revised = text.replace(BEFORE, AFTER)
        pair = base.module('20261011-MDM近真值对照')
        previous = base.load(prior.QA)
        assert base.text_digest(text) == previous['after_text_sha256']
        record = dict(before=BEFORE, after=AFTER, before_text_sha256=base.text_digest(text),
                      after_text_sha256=base.text_digest(revised), previous_outside_sha256=previous['outside_after_sha256'])
        pair.write_text(base.REPORT, revised)
        base.write_json(QA, record)
        previous.update(after_text_sha256=record['after_text_sha256'],
                        outside_after_sha256=base.text_digest(pair.block(revised)[1]),
                        replacements=prior.REPLACEMENTS, mle_summary_revision=QA.name)
        base.write_json(prior.QA, previous)
        existing = base.load(pair.QA)
        assert existing['outside_block_sha256'] == record['previous_outside_sha256']
        existing.update(outside_block_sha256=previous['outside_after_sha256'], mle_summary_revision=QA.name)
        base.write_json(pair.QA, existing)
    verify()


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-MLE低估结论-核验.json').exists():
        text = base.module('20261012-MLE低估结论').restore(text)
    assert text.count(AFTER) == 1 and BEFORE not in text
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: only the MLE summary sentence changed; calculations and figures retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
