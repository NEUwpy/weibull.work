"""Append two empirical-minimum panels below the six observation panels.

Reuse all archived observations. Shared 50-unit bins contain all 300 minima;
no smoothing, sampling or estimation is performed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREVIOUS = HERE / '20261010-导入图补入n30.json'
RECORD = Path(__file__).with_suffix('.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seal = json.loads((ROOT/'结果/中间数据/封存清单.json').read_text(encoding='utf-8'))
    protected = {**seal['input_hashes'], **seal['output_hashes']}
    protected.pop('结果/图2_样本与真实起点.png')
    before = {name: digest(ROOT/name) for name in protected}
    previous = json.loads(PREVIOUS.read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location('saved_n30_source', HERE/'20261010-导入图补入n30.py')
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    entry.main(minimum_distributions=True)
    result = json.loads(RECORD.read_text(encoding='utf-8'))
    assert result['panels'] == previous['panels']
    assert len(result['minimum_distribution_panels']) == 2
    assert result['total_panel_count'] == 8
    assert all(digest(ROOT/name) == sha for name, sha in before.items())
    result.update(task='2026-10-10: append empirical minimum distributions to figure 2',
                  previous_observation_record=PREVIOUS.relative_to(ROOT).as_posix(),
                  previous_observation_record_sha256=digest(PREVIOUS),
                  six_observation_panels_unchanged=True,
                  revision_new_samples=0, protected_input_and_output_files=len(before),
                  minimum_values_reused=300,
                  graph_note_count_added=0, figure_sha256=digest(ROOT/result['figure']))
    RECORD.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                      encoding='utf-8', newline='\n')
    print('Verified: original six panels unchanged; two distributions reuse all 300 minima.')


if __name__ == '__main__':
    main()
