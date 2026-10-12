"""补上位置尺度比经距离集中程度与方法关系影响形状估计的逻辑。"""
from pathlib import Path
import argparse
import importlib.util
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r2_wording_patch', HERE / '20261012-MLE总述精简.py')
run = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run
spec.loader.exec_module(run)
base = run.base
QA = HERE / (Path(__file__).stem + '-核验.json')
REPLACEMENTS = {
    '**位置相对尺度较大，会放大左侧候选的形状。**':
    '**位置尺度比与左侧候选的形状高估。**',
    '本批位置下界为0。将候选位置移向零时，样本距离更接近原始观测，较大的γ/η因而可对应更集中的距离。回归或似然准则选择这类左侧候选后，形状关系容易给出更大的β。它放大了2.1中左移定位所形成的高估。':
    '本批位置下界为0。较大的γ/η会使接近零位置的候选距离表现出更小的相对离散度；对于将较集中的距离结构对应为较大形状的回归或似然关系（式（10）、（15）、（23）），这会增强左侧候选产生形状高估的倾向。',
}


def restore(text):
    if (HERE / '20261012-本批表述精简-核验.json').exists():
        text = base.module('20261012-本批表述精简').restore(text)
    if QA.exists():
        record = base.load(QA)
        text = text.replace(record['after'], record['before'])
    return text


def verify():
    record = base.load(QA)
    text = base.REPORT.read_text(encoding='utf-8')
    if (HERE / '20261012-本批表述精简-核验.json').exists():
        text = base.module('20261012-本批表述精简').restore(text)
    assert text.count(record['after']) == 1
    assert base.text_digest(text) == record['after_text_sha256']
    assert base.text_digest(restore(text)) == record['before_text_sha256']
    assert re.findall(r'\$\$.*?\$\$', record['before'], re.S) == re.findall(r'\$\$.*?\$\$', record['after'], re.S)
    run.prior.verify()
    record.update(validation='passed', script_sha256=base.digest(__file__))
    base.write_json(QA, record)
    print('PASS: position-scale explanation revised; formula 30 and all results/figures unchanged.')


def apply():
    if QA.exists():
        verify()
        return
    text = base.REPORT.read_text(encoding='utf-8')
    start = text.index(next(iter(REPLACEMENTS)))
    end = text.index('\n\n### 2.3', start)
    before = text[start:end]
    after = before
    for old, new in REPLACEMENTS.items():
        assert after.count(old) == 1
        after = after.replace(old, new)
    run.BEFORE, run.AFTER, run.QA, run.verify = before, after, QA, verify
    run.REVISION_KEY = 'location_scale_revision'
    run.apply()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='verify', choices=['apply', 'verify'])
    globals()[parser.parse_args().action]()
