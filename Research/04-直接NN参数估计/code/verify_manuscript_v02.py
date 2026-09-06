"""Check v0.2 tables against sealed summaries; never recompute scientific metrics."""
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sources = {}
checks = []


def read(name):
    path = ROOT / name
    sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def tables(path):
    content = path.read_text(encoding="utf-8")
    found = {}
    for match in re.finditer(r"(?:^\|.*\n)+", content, re.M):
        caption = re.match(r"\s*\*\*表(A?\d+)", content[match.end():])
        if caption:
            rows = [[c.strip() for c in line.strip().strip('|').split('|')]
                    for line in match.group().strip().splitlines()]
            found[caption[1]] = rows[2:]
    return found


def check(label, printed, expected):
    value = printed.replace(',', '').replace('%', '').replace('−', '-')
    decimal = value.lower().split('e')[0]
    digits = len(decimal.split('.')[1]) if '.' in decimal else 0
    tolerance = 0.50001 * 10 ** -digits
    assert abs(float(value) - float(expected)) <= tolerance, (label, printed, expected)
    checks.append(label)


main = next(ROOT.glob('03-稿件-*-v0.2.md'))
appendix = next(ROOT.glob('03-附录-*-v0.2.md'))
mt, at = tables(main), tables(appendix)
methods = ['Direct-P', 'Adaptive-MDM', 'MDM-0.1', 'WMLE', 'LSE']
groups = ['seen_grid', 'in_domain_unseen', 'near_ood', 'far_ood']
domain = read('artifacts/traditional_aligned_v1/combined_domain_summary.csv')
di = {(r['method'], r['beta_group']): r for r in domain}
for cells, method in zip(mt['2'], methods, strict=True):
    for col, group in enumerate(groups, 1):
        check(f'T2/{method}/{group}', cells[col], di[method, group]['J1'])
    rows = [r for r in domain if r['method'] == method]
    total = sum(int(r['n_total']) for r in rows)
    failed = sum(int(r['n_total']) - int(r['n_valid']) for r in rows)
    check(f'T2/{method}/failure_percent', cells[5], 100 * failed / total)

width = read('artifacts/training_domain_width_location_v1/analysis/width_common_beta_summary.csv')
width.sort(key=lambda r: (float(r['train_beta_width']), r['budget_policy'] != 'fixed_total'))
for i, (cells, row) in enumerate(zip(mt['3'], width, strict=True)):
    for col, field in enumerate(['n_train_per_n', 'J1', 'beta_rmse', 'x0.95_rmse'], 2):
        check(f'T3/{i}/{field}', cells[col], row[field])
for i, cells in enumerate(mt['4']):
    row = di[methods[i % 2], groups[i // 2]]
    for col, field in enumerate(['x0.95_bias', 'x0.95_sd', 'x0.95_rmse'], 2):
        check(f'T4/{i}/{field}', cells[col], row[field])

beta = read('artifacts/traditional_aligned_v1/combined_beta_summary.csv')
bi = {(r['method'], float(r['beta'])): r for r in beta}
for cells in at['A1']:
    for col, method in enumerate(methods, 2):
        check(f'TA1/{cells[1]}/{method}', cells[col], bi[method, float(cells[1])]['J1'])
ns = read('artifacts/study01_aligned_generalization_v1/analysis/n_domain_summary.csv')
ni = {(r['method'], int(r['n'])): r for r in ns if r['beta_group'] == 'seen_grid'}
for cells in at['A2']:
    for col, (method, field) in enumerate([(methods[0], 'J1'), (methods[1], 'J1'),
                                         (methods[0], 'x0.95_rmse'), (methods[1], 'x0.95_rmse')], 1):
        check(f'TA2/{cells[0]}/{col}', cells[col], ni[method, int(cells[0])][field])
large = read('artifacts/study01_aligned_generalization_v1/analysis/large_beta_summary.csv')
li = {(float(r['beta']), int(r['n'])): r for r in large if r['method'] == 'Adaptive-MDM'}
for cells in at['A3']:
    row = li[float(cells[0]), int(cells[1])]
    for col, field in enumerate(['J1', 'beta_bias', 'eta_bias', 'gamma_bias', 'x0.95_rmse'], 2):
        check(f'TA3/{cells[0]}/{cells[1]}/{field}', cells[col], row[field])
location = read('artifacts/training_domain_width_location_v1/analysis/location_aligned_summary.csv')
location.sort(key=lambda r: (float(r['train_beta_min']), r['budget_policy'] != 'fixed_total'))
for i, (cells, row) in enumerate(zip(at['A4'], location, strict=True)):
    for col, field in enumerate(['n_train_per_n', 'J1', 'x0.95_rmse', 'failure_rate'], 2):
        check(f'TA4/{i}/{field}', cells[col], float(row[field]) * (100 if field == 'failure_rate' else 1))
scales = read('artifacts/scale_equivariance_v1/pooled_scale_summary.csv')
scales.sort(key=lambda r: float(r['eta']))
for i, (cells, row) in enumerate(zip(at['A5'], scales, strict=True)):
    for col, field in enumerate(['eta', 'n_samples', 'J1', 'x095_rmse', 'failure_rate']):
        check(f'TA5/{i}/{field}', cells[col], float(row[field]) * (100 if field == 'failure_rate' else 1))

links = []
for path in [main, appendix]:
    content = path.read_text(encoding='utf-8')
    assert not re.search(r'\\\\[A-Za-z]', content), f'Doubled TeX backslash in {path.name}'
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if target.startswith(('https://', 'http://', '#')):
            continue
        destination = path.parent / unquote(target.split('#')[0])
        assert destination.exists(), (path.name, target)
        links.append({'file': path.name, 'target': target})
report = {'status': 'PASS', 'numeric_values_checked': len(checks),
          'tables_checked': ['2', '3', '4', 'A1', 'A2', 'A3', 'A4', 'A5'],
          'local_links_checked': len(links), 'source_csv_sha256': sources,
          'manuscript_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [main, appendix]},
          'checks': checks, 'links': links,
          'scope': 'Rounded table values and local links only; no raw-data or training rerun.'}
output = ROOT / 'manuscript/v0.2-numeric-verification.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'PASS: {len(checks)} table values; {len(links)} local links; TeX backslashes checked')
