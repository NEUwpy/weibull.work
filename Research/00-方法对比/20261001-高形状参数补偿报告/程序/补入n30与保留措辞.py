"""2026-10-10: add archived n=30 estimates to Figure 1 and Chapter 1.

Preserve the user's live wording. The n=7/15 original batch stays intact;
n=30 is the later independent W(5,1000,500) batch, not paired continuation.
Read stored results only; do not call an estimator or alter failure states.
"""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
R00 = BATCH.parent
REPORT = R00 / '报告1：高形状参数下的估计偏移.md'
GENERATOR = HERE / '生成报告.py'
MATRIX = R00 / 'W(5,1000,500)/20260929-新抽样/程序/完整矩阵/数据/matrix.json'
WORKBOOK = R00 / 'W(5,1000,500)/20260929-新抽样/结果/W5,1000,500.xlsx'
BOUNDARY = '## 第二章　机制分析与对照实验'
CHAPTER = '## 第一章　问题描述'
METHODS = ('mdm', 'lse', 'lre', 'wmle', 'mle')
CAPTION = '**图1｜随样本量增大，位置与尺度的估计中位数向真值靠近，改善程度因方法而异。**'
SOURCE_NOTE = ' n=30为同参数的后续独立样本。'
LEGACY_PARAGRAPH_START = '在补充的n=30样本中，'
PARAGRAPH_START = '随着n增大，'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_text(code):
    for node in ast.parse(code).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REPORT_TEXT' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Missing report template')


def main():
    protected = [MATRIX, WORKBOOK, HERE/'输入快照/原案例估计.json',
                 HERE/'输入快照/原案例核验.json',
                 BATCH/'结果/中间数据/实际估计.json',
                 BATCH/'结果/中间数据/样本.json',
                 BATCH/'结果/中间数据/逐法过程曲线.json',
                 BATCH/'结果/高形状参数补偿统计.xlsx']
    protected.extend(p for p in (BATCH/'结果').iterdir()
                     if p.suffix in ('.png', '.pdf', '.svg') and p.name != '图1_原案例参数分布.png')
    before_hashes = {str(p): digest(p) for p in protected}
    current = REPORT.read_text(encoding='utf-8')
    heading, tail = current.split(BOUNDARY, 1)
    data = json.loads(MATRIX.read_text(encoding='utf-8'))
    assert data['config']['truth'] == [5., 1000., 500.]
    assert data['config']['seed_namespace_original'] == 2026092903
    assert len([s for s in data['samples'] if s['n'] == 30]) == 50
    selected = [r for r in data['results'] if r['n'] == 30 and r['method_id'] in METHODS
                and (r['method_id'] != 'mdm' or r['delta'] == .1)]
    assert len(selected) == 250
    records = [dict(beta=5, eta=1000., gamma=500., n=30, method=r['method_id'], sample_id=r['id'],
                    beta_hat=r['beta_hat'], eta_hat=r['eta_hat'], gamma_hat=r['gamma_hat'],
                    converged=r['converged'], status=r['status']) for r in selected]
    supplement = dict(truth=[5., 1000., 500.], n=30, samples=50,
                      source_matrix=str(MATRIX), source_matrix_sha256=digest(MATRIX),
                      source_workbook=str(WORKBOOK), source_workbook_sha256=digest(WORKBOOK),
                      source_batch='20260929-新抽样', seed_namespace=2026092903,
                      mdm_delta=.1, lre_version='Historical Bernard',
                      independent_of_original_n7_n15=True, records=records)
    (HERE/'图1n30补充.json').write_text(json.dumps(supplement, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    from 绘制图1小提琴 import main as draw, load_figure_records
    merged = load_figure_records()
    summaries = []
    for n in (7, 15, 30):
        for method in METHODS:
            attempts = [r for r in merged if r['beta'] == 5 and r['n'] == n and r['method'] == method]
            success = sorted((r for r in attempts if r['converged']), key=lambda r: r['sample_id'])
            assert len(attempts) == 50
            q = {k: np.quantile([r[k] for r in success], [.25, .5, .75]).tolist()
                 for k in ('beta_hat', 'eta_hat', 'gamma_hat')}
            summaries.append(dict(n=n, method=method, success=len(success), failed=50-len(success), quartiles=q))
    index = {(r['n'], r['method']): r for r in summaries}
    beta_medians = sorted(index[30, m]['quartiles']['beta_hat'][1] for m in ('mdm', 'wmle'))
    eta_medians = [index[30, m]['quartiles']['eta_hat'][1] for m in ('mdm', 'wmle')]
    gamma_medians = [index[30, m]['quartiles']['gamma_hat'][1] for m in ('mdm', 'wmle')]
    assert all(abs(e-730) < 5 for e in eta_medians)
    assert all(abs(g-750) < 10 for g in gamma_medians)
    paragraph = f'{PARAGRAPH_START}β和η低估、γ高估的现象总体减轻。'
    heading = heading.replace(SOURCE_NOTE, '')
    paragraph_starts = (PARAGRAPH_START, 'γ高估、η低估的现象', 'n由7增至15时，', 'n增至30时，',
                        'n=30时，', LEGACY_PARAGRAPH_START)
    old_paragraphs = [p for p in heading.split('\n\n') if p.startswith(paragraph_starts)]
    if old_paragraphs:
        heading = heading.replace(old_paragraphs[0], paragraph, 1)
        for old in old_paragraphs[1:]:
            heading = heading.replace(old+'\n\n', '', 1)
    else:
        heading = heading.rstrip()+'\n\n'+paragraph+'\n\n'
    updated = heading+BOUNDARY+tail
    # Replace the template's first chapter only; retain source bytes elsewhere.
    generator_bytes = GENERATOR.read_bytes()
    generated = reviewed_text(generator_bytes.decode('utf-8'))
    assert generated.split(BOUNDARY, 1)[1] == tail, 'Later manual edits need synchronization before revision'
    start = generator_bytes.index(CHAPTER.encode('utf-8'))
    end = generator_bytes.index(BOUNDARY.encode('utf-8'), start)
    line_ending = b'\r\n' if b'\r\n' in generator_bytes[start:end] else b'\n'
    block = heading.split(CHAPTER, 1)[1]
    new_bytes = (CHAPTER+block).encode('utf-8').replace(b'\n', line_ending)
    new_generator = generator_bytes[:start]+new_bytes+generator_bytes[end:]
    assert reviewed_text(new_generator.decode('utf-8')) == updated
    assert updated.split(BOUNDARY, 1)[1] == tail
    draw()
    figure_data = json.loads((BATCH/'结果/中间数据/图1小提琴数据与核验.json').read_text(encoding='utf-8'))
    assert len(figure_data['panels']) == 45 and figure_data['sample_sizes'] == [7, 15, 30]
    for summary in summaries:
        for parameter, q in summary['quartiles'].items():
            panel = next(p for p in figure_data['panels'] if (p['n'], p['method'], p['parameter']) == (summary['n'], summary['method'], parameter))
            assert np.allclose(panel['quartiles'], q, rtol=0, atol=1e-12)
    previous_stats = json.loads((HERE/'第一章偏移统计与修订.json').read_text(encoding='utf-8'))['summaries']
    for old in previous_stats:
        assert old['quartiles'] == index[old['n'], old['method']]['quartiles']
    assert all(digest(Path(p)) == h for p, h in before_hashes.items())
    REPORT.write_text(updated, encoding='utf-8', newline='\n')
    GENERATOR.write_bytes(new_generator)
    before_chapter = current.split(BOUNDARY, 1)[0].split(CHAPTER, 1)[1]
    after_chapter = heading.split(CHAPTER, 1)[1]
    preserved = [p.replace(SOURCE_NOTE, '') for p in before_chapter.split('\n\n')
                 if p.strip() and not p.startswith(paragraph_starts)]
    assert all(p in after_chapter for p in preserved), 'A user-edited paragraph was lost'
    audit = dict(sample_sizes=[7, 15, 30], methods=list(METHODS), summaries=summaries,
                 n30_source=str(MATRIX), n30_source_sha256=digest(MATRIX),
                 user_wording_preserved=True, original_n7_n15_estimates_unchanged=True,
                 other_chapters_and_figures_unchanged=True, new_samples=0, new_fits=0,
                 protected_sha256=before_hashes, figure_panels=9, method_distributions=45,
                 figure_dimensions=figure_data['png_dimensions'], formats=['png'],
                 first_chapter_source_difference='n30 is an independent later batch; not paired continuation',
                 report_generator_synchronized=True)
    (HERE/'补入n30与保留措辞.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(paragraph)
    print('PASS: user wording, original estimates and later chapters preserved; n30 plotted from stored results')


if __name__ == '__main__':
    main()
