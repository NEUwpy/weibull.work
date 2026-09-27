"""Recount positive, source-verified metric codes; no keyword inference."""
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'evidence/complete_sample_metric_audit.json').read_text(encoding='utf-8'))
records = data['records']
assert len({r['id'] for r in records}) == len(records)
assert all(r['source_path'] and r['source_sha256'] and r['locator'] for r in records)
eligible = [r for r in records if r['count_eligible']]
simulation = [r for r in eligible if 'S' in r['modes']]
real = [r for r in eligible if 'R' in r['modes']]
result = {
    'records': len(records),
    'eligible_empirical_records': len(eligible),
    'confirmed_repeated_sampling': len(simulation),
    'confirmed_real_application': len(real),
    'both': len({r['id'] for r in simulation} & {r['id'] for r in real}),
    'parameter_metric_counts_in_simulation': dict(Counter(tag for r in simulation for tag in r['positive_metric_tags'])),
    'unencoded_candidates': data['remaining_candidates'],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
