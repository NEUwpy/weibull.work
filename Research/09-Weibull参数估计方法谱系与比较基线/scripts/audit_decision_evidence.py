"""Recompute the decision-review denominators and verify source provenance."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'evidence' / name).read_text(encoding='utf-8'))


def main():
    comparison = read('benchmark_comparison_audit.json')
    direction = read('recent_direction_audit.json')
    primary = [r for r in comparison['records'] if r['primary_included']]
    filters = {
        'all': lambda r: True,
        'since2006': lambda r: r.get('year') is not None and r['year'] >= 2006,
        'since2016': lambda r: r.get('year') is not None and r['year'] >= 2016,
        'contains_n_le30': lambda r: bool(r.get('n')) and min(r['n']) <= 30,
    }
    for key, predicate in filters.items():
        rows = [r for r in primary if predicate(r)]
        count = Counter(f for r in rows for f in {b['family'] for b in r['sim_benchmarks']})
        expected = comparison['summary'][key]
        assert len(rows) == expected['denominator'], key
        assert dict(count) == {k: v['count'] for k, v in expected['families'].items()}, key
        assert set(r['id'] for r in rows) == set(expected['ids']), key
        print(key, len(rows), dict(count))
    for key, year in [('all_audited', None), ('recent_2006_2026', 2006), ('recent_2016_2026', 2016)]:
        rows = [r for r in direction['records'] if year is None or (r['year'] is not None and r['year'] >= year)]
        expected = direction['counts'][key]
        assert len(rows) == expected['n'], key
        for field in ['task', 'innovation']:
            actual = Counter(t for r in rows for t in set(r[field + '_tags']))
            assert dict(actual) == expected[field + '_counts'], (key, field)
        print(key, len(rows))
    checked = {}
    for r in comparison['records'] + direction['records']:
        path = Path(r['source_path'])
        if path not in checked:
            checked[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert checked[path].lower() == r['source_sha256'].lower(), str(path)
    print('source SHA256 verified:', len(checked))


if __name__ == '__main__':
    main()
