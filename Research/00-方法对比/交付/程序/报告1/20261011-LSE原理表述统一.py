"""Align Report 1's LSE principles with Report 2; keep computed figures intact.

Reuse the common derivation and definitions with Report 1's own equation
numbers. Its high-beta explanation and representative-sample transfer remain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT1 = ROOT / '报告1：高形状参数下的估计偏移.md'
REPORT2 = ROOT / '报告2：小样本情况下的明显异常估计.md'
README = ROOT / 'README.md'
QA = HERE / '20261011-LSE原理表述统一核验.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def common_principles(report2=None):
    text = report2 if report2 is not None else REPORT2.read_text(encoding='utf-8')
    start = text.index('LSE对每个候选位置γ拟合一条直线')
    end = text.index('x₍₁₎为样本最小值。', start)
    return text[start:end]


def references(text, mapping):
    """Remap explicit equation references, including 式（a）、（b）."""
    def replace(match):
        return '式' + re.sub(r'（(\d+)）',
                            lambda m: f"（{mapping.get(int(m[1]), int(m[1]))}）", match[1])
    return re.sub(r'式((?:（\d+）)(?:[、和及]（\d+）)*)', replace, text)


def tags(text, mapping):
    return re.sub(r'\\tag\{(\d+)\}',
                  lambda m: r'\tag{' + str(mapping.get(int(m[1]), int(m[1]))) + '}', text)


def align_report(text, report2=None):
    start, end = text.index('### 2.2　'), text.index('### 2.3　')
    section, after = text[start:end], text[end:]
    heading = section[:section.index('\n\n') + 2]
    common = common_principles(report2)
    mapping = {i: i + 3 for i in range(8, 13)}
    common = tags(references(common, mapping), mapping)
    tail = section[section.index('![图6　'):]
    if r'\tag{15}' in tail:
        tail = tags(references(tail, {12: 13, 14: 15, 15: 16, 16: 17}), {15: 16, 16: 17})
    tail = tail.replace(r't_{(i)}', r'x_{(i)}').replace(r'\overline t', r'\overline x')
    tail = tail.replace('其中，t̄为样本均值。', '其中，x̄为样本均值。')
    tail = tail.replace('位置选定后，回归斜率和截距决定其余两个参数。式（13）的最小二乘解为：',
                        '位置选定后，回归斜率和截距决定其余两个参数。对yᵢ≈a+bzᵢ作最小二乘回归，可得：')
    first_tag = int(re.search(r'\\tag\{(\d+)\}', after)[1])
    if first_tag == 17:
        mapping = {15: 16, **{i: i + 1 for i in range(17, 35)}}
        after = tags(references(after, mapping), mapping)
    else:
        assert first_tag == 18, first_tag
    boundary = ('x₍₁₎为样本最小值。图6按式（15）展示位置准则，橙叉标记所选γ。\n\n')
    return text[:start] + heading + common + boundary + tail + after


def verify_common(text, report2=None):
    first = text[text.index('LSE对每个候选位置γ拟合一条直线'):]
    first = first[:first.index('x₍₁₎为样本最小值。')]
    mapping = {i: i - 3 for i in range(11, 16)}
    assert tags(references(first, mapping), mapping) == common_principles(report2)
    numbers = [int(n) for n in re.findall(r'\\tag\{(\d+)\}', text)]
    assert numbers == list(range(1, 36))
    assert [int(n) for n in re.findall(r'\*\*图(\d+)｜', text)] == list(range(1, 12))
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in target and not target.startswith('#'):
            assert (ROOT / target.split('#')[0]).exists(), target
    return numbers


def run():
    report2 = REPORT2.read_text(encoding='utf-8')
    hashes = {p.relative_to(ROOT).as_posix(): sha(p)
              for p in (ROOT / '交付/结果/报告1').rglob('*') if p.is_file()}
    before = REPORT1.read_text(encoding='utf-8')
    updated = align_report(before, report2)
    numbers = verify_common(updated, report2)
    assert align_report(updated, report2) == updated
    if REPORT1.read_bytes() != updated.encode('utf-8'):
        REPORT1.write_bytes(updated.encode('utf-8'))
    readme = README.read_text(encoding='utf-8')
    old = '报告1的LSE原理与报告2统一：最大化F比等价于最小化1−R²。'
    new = ('报告1的LSE原理与报告2统一：对数距离关系、顺序统计量期望、斜率与参数关系、F比、位置判据的公式及说明一致，各报告独立编号。')
    readme = readme.replace(old, new)
    marker = '[原理表述同步脚本](交付/程序/报告1/20261011-LSE原理表述统一.py)'
    if marker not in readme:
        start = readme.index('报告1的LSE原理与报告2统一')
        end = readme.index('\n\n', start)
        readme = readme[:end] + '原理表述复现见' + marker + '。' + readme[end:]
    if README.read_bytes() != readme.encode('utf-8'):
        README.write_bytes(readme.encode('utf-8'))
    assert report2 == REPORT2.read_text(encoding='utf-8')
    assert hashes == {p.relative_to(ROOT).as_posix(): sha(p)
                      for p in (ROOT / '交付/结果/报告1').rglob('*') if p.is_file()}
    record = dict(common_formulas_and_explanations_identical_except_numbers=True,
                  common_equation_map={'report2': [8, 9, 10, 11, 12], 'report1': [11, 12, 13, 14, 15]},
                  report2_unchanged=True, report2_sha256=sha(REPORT2),
                  report1_sha256=sha(REPORT1), figures_and_results_unchanged=True,
                  protected_results=hashes, new_samples=0, new_estimates=0,
                  equations=numbers, main_figures=11, repeat_is_idempotent=True,
                  script_sha256=sha(__file__))
    QA.write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print({k: v for k, v in record.items() if k not in ('protected_results', 'equations')})


if __name__ == '__main__':
    run()
