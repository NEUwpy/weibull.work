"""Read archived estimates only; describe the two directions of threefold error."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
METHODS = ['MDM δ=0.20', 'LSE', 'LRE', 'MLE', 'WMLE', 'MMLE']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = json.loads((ROOT / '跨组合汇总/程序/20261007-新增五组合/13组合取数.json').read_text(encoding='utf-8'))['sources']
    attempts = Counter()
    flagged = []
    source_hashes = {}
    for source in sources:
        program = Path(source['program'])
        path = program / '中间数据/matrix.json' if program.name == '程序' else program.parent / '完整矩阵/数据/matrix.json'
        source_hashes[str(path)] = digest(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        beta, eta, gamma = map(float, data['config']['truth'])
        for row in data['results']:
            method = f"MDM δ={row['delta']:.2f}" if row['method_id'] == 'mdm' else row['method_id'].upper()
            if method not in METHODS:
                continue
            attempts[method] += 1
            valid = row['converged'] and all(isinstance(row[k], (int, float)) and math.isfinite(row[k]) for k in ['beta_hat', 'eta_hat', 'gamma_hat'])
            if not valid:
                continue
            ratio = row['beta_hat'] / beta
            direction = 'over' if ratio >= 3 else ('under' if ratio <= 1/3 else None)
            if direction:
                flagged.append(dict(combination=source['combination'], n=row['n'], group=row['id'],
                                    method=method, direction=direction,
                                    beta_true=beta, eta_true=eta, gamma_true=gamma,
                                    beta_hat=row['beta_hat'], eta_hat=row['eta_hat'], gamma_hat=row['gamma_hat']))
    assert sum(attempts.values()) == 11700 and len(flagged) == 963
    reference = json.loads((HERE / '第一章频率核对.json').read_text(encoding='utf-8'))
    by_method = {m: sum(r['method'] == m for r in flagged) for m in METHODS}
    assert by_method == reference['plot_by_method']
    assert source_hashes == reference['source_sha256']
    directions = {}
    for direction in ['over', 'under']:
        rows = [r for r in flagged if r['direction'] == direction]
        directions[direction] = dict(
            count=len(rows),
            gamma_below_truth=sum(r['gamma_hat'] < r['gamma_true'] for r in rows),
            gamma_above_truth=sum(r['gamma_hat'] > r['gamma_true'] for r in rows),
            eta_below_truth=sum(r['eta_hat'] < r['eta_true'] for r in rows),
            eta_above_truth=sum(r['eta_hat'] > r['eta_true'] for r in rows),
            gamma_zero=sum(r['gamma_hat'] == 0 for r in rows),
            by_method={m: sum(r['method'] == m for r in rows) for m in METHODS},
        )
    assert directions['over']['count'] == 449
    assert directions['under']['count'] == 514
    assert directions['under']['gamma_above_truth'] == directions['under']['eta_below_truth'] == 514
    with (HERE / '形成条件异常记录.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flagged[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(flagged)
    summary = dict(
        criterion='beta_hat >= 3*beta_true or beta_hat <= beta_true/3',
        methods=METHODS, directions=directions,
        minimum_probability_example={
            'n': 15, 'normalized_gap': 0.5,
            'probability_min_within_gap': {str(b): -math.expm1(-15 * 0.5**b) for b in [2, 5]},
            'formula': 'P(min(X) > gamma + a*eta) = exp(-n*a**beta)',
        },
        source_sha256=source_hashes,
        source_unchanged=all(digest(Path(p)) == value for p, value in source_hashes.items()),
    )
    assert summary['source_unchanged']
    (HERE / '形成条件复核.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS', {k: v['count'] for k, v in directions.items()}, summary['minimum_probability_example']['probability_min_within_gap'])


if __name__ == '__main__':
    main()
