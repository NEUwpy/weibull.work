"""Audit the retained manuscript evidence; never train or rewrite frozen results."""
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

import numpy as np
from audit_revision_v270 import table

S = Path(__file__).resolve().parents[2]
REPO = S.parents[1]
M = S / 'manuscript'
OUT = S / 'snapshots/2026-09-08'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.DEVNULL)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    snapshot = read_json(OUT / 'snapshot.json')
    docs = [M/'Study02论文初稿-v2.7.0.md', M/'Study02论文附录-v2.7.0.md',
            M/'submission/Study02-manuscript-v2.7.0-en.md', M/'submission/Study02-supplement-v2.7.0-en.md']
    texts = [p.read_text(encoding='utf-8') for p in docs]
    for p, t in zip(docs, texts):
        original = git('show', snapshot['git_sha']+':'+p.relative_to(REPO).as_posix()).decode('utf-8')
        assert re.sub(r'^<a id="(?:methods|main-3-[1-5]|appendix-[a-f]|table-[a-f]?\d+)"></a>\n', '', t, flags=re.M) == original, p
    tokens = 0
    for i, labels in [(0, ['1','2','3']), (1, ['A3']+[f'B{x}' for x in range(1,11)]+['C1','D1','F1','F2'])]:
        for label in labels:
            a, b = table(texts[i], label), table(texts[i+2], label, True)
            assert a == b, label
            tokens += sum(map(len, a))
    for i in (0, 2):
        body, refs = texts[i].split('## 参考文献' if i == 0 else '## References')
        cited = {int(n) for group in re.findall(r'\[([^\]]*)\]', body)
                 if re.fullmatch(r'\s*\d{1,2}(?:\s*,\s*\d{1,2})*\s*', group)
                 for n in re.findall(r'\d+', group)}
        entries = {int(n) for n in re.findall(r'^\[(\d+)\]', refs, re.M)}
        assert cited == entries and len(entries) == 19

    edited = set(docs)
    # Saved scope makes the check rerunnable after committing as well.
    scope_file = OUT / 'edited-markdown.json'
    if scope_file.exists():
        edited.update(REPO / rel for rel in read_json(scope_file))
    for args in [('diff', snapshot['git_sha'], '--name-only', '-z', '--diff-filter=AM'),
                 ('ls-files', '--others', '--exclude-standard', '-z')]:
        edited.update(REPO / r.decode('utf-8') for r in git(*args).split(b'\0') if r.endswith(b'.md'))
    edited = {p for p in edited if p.is_file() and (p.is_relative_to(S) or p in (REPO/'README.md',REPO/'Study/README.md',REPO/'Study/研究规划v0.3.md'))}
    scope_file.write_text(json.dumps(sorted(p.relative_to(REPO).as_posix() for p in edited), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    links = anchors = 0
    for p in edited:
        t = p.read_text(encoding='utf-8')
        ids = re.findall(r'<a id="([^"]+)"', t)
        assert len(ids) == len(set(ids)), ('duplicate anchors', p)
        for link in re.findall(r'\]\(([^)]+)\)', t):
            link = unquote(link.strip('<>'))
            if re.match(r'^[a-zA-Z]+:', link):
                continue
            rel, _, fragment = link.partition('#')
            target = (p.parent / rel).resolve() if rel else p
            assert target.exists(), (p, link)
            links += 1
            if fragment and target.suffix == '.md':
                dest = target.read_text(encoding='utf-8')
                slugs = [re.sub(r'[^\w\-\s]', '', h.lower()).replace(' ', '-') for h in re.findall(r'^#+\s+(.*)', dest, re.M)]
                assert fragment in re.findall(r'<a id="([^"]+)"', dest)+slugs, (p, link, 'anchor')
                anchors += 1

    raw = newline = 0
    def verify(path, expected):
        nonlocal raw, newline
        data = path.read_bytes()
        if sha(data) == expected:
            raw += 1
        else:
            assert path.suffix.lower() in ('.json','.csv','.svg','.py','.md','.txt'), path
            lf = data.replace(b'\r\n', b'\n')
            assert expected in (sha(lf), sha(lf.replace(b'\n', b'\r\n'))), ('hash mismatch', path)
            newline += 1

    for rel in ['artifacts/manuscript_figures_v270/manifest.json',
                'artifacts/submission_controls_v1/analysis/manifest.json',
                'artifacts/qp_comparison_v270/manifest.json']:
        manifest = read_json(S/rel)
        for field in ('source_sha256','output_sha256'):
            for path, expected in manifest.get(field, {}).items():
                verify(S/path, expected)
    word = read_json(M/'figures/word/assembly-manifest.json')
    for figure in word['figures']:
        for ext in ('png','svg'):
            # Preserve the historical manifest; locate its project-relative suffix here.
            rel = figure[ext].replace('\\','/').split('/manuscript/',1)[1]
            verify(M/rel, figure[f'output_{ext}_sha256'])

    inv = list(csv.DictReader((OUT/'file-inventory.csv').open(encoding='utf-8')))
    unchanged = 0
    for row in inv:
        if row['scope'] != 'worktree' or row['action'] != 'retain':
            continue
        path = S/row['relative_path']
        assert path.exists(), path
        if path not in edited:
            assert sha(path.read_bytes()) == row['sha256'], ('retained file changed', path)
            unchanged += 1
    moved = list(csv.DictReader((OUT/'deletion-log.csv').open(encoding='utf-8-sig')))
    roots = {'worktree':S, 'main':Path('D:/weibull')/S.relative_to(REPO), 'external':Path('C:/weibull-runs/study02')}
    for row in moved:
        assert not (roots[row['scope']]/row['relative_path']).exists()
        assert sha(Path(row['pending_path']).read_bytes()) == row['sha256']

    summary = read_json(S/'artifacts/submission_controls_v1/analysis/summary.json')
    qp = read_json(S/'artifacts/qp_comparison_v270/summary.json')
    assert summary['training_trajectories'] == 600 and summary['q_reproduction_all_200']
    assert summary['q_feas']['available'] == 0
    old = S/'归档/旧实验/四路线同预算敏感性/artifacts/equal_budget_sensitivity'
    for p in (S/'artifacts/submission_controls_v1/fits').glob('*_rQ.json'):
        new = read_json(p)['meta']; previous = read_json(old/'fit_metadata'/p.name)
        assert new['best_epoch'] == previous['best_epoch']
        np.testing.assert_allclose(new['rrmse_x95'], previous['rrmse_x95'], rtol=1e-10, atol=1e-12)
        for key in ('init_param_sha','batch_order_sha','scaler_sha','train_rows_sha','val_rows_sha','test_rows_sha','network_sha'):
            assert new[key] == previous[key], (p,key)
    assert len(list((S/'artifacts/submission_controls_v1/fits').glob('*_rQ.json'))) == 200
    for r in ('0.9','0.95','0.99'):
        for route in ('P','QP','QCP'):
            np.testing.assert_allclose(qp['pooled'][r][route],summary['pooled'][r][route],rtol=1e-12)
    result = dict(status='PASS', manuscript_content_unchanged_except_anchors=4,
                  bilingual_matching_numeric_tokens=tokens, references_per_language=19,
                  edited_markdown_files=len(edited), local_links=links, linked_anchors=anchors,
                  manifest_hashes_exact=raw, manifest_hashes_newline_only=newline,
                  word_figures=word['count'], retained_files_unchanged=unchanged,
                  moved_files_verified=len(moved), q_reproduced_model_units=200,
                  actual_deleted_bytes=0, note='Historical text hash differences are exclusively LF/CRLF; source manifests remain unchanged.')
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
