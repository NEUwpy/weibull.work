"""Extend the opening figure using saved n=30 beta=5 observations.

The beta=2 comparison uses the same recovered latent exponential quantiles.
No random draws or parameter estimates are added or replaced.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT.parent / 'W(5,1000,500)' / '20260929-新抽样' / '程序' / '完整矩阵' / '数据' / 'matrix.json'
CACHE = HERE / '20261010-导入图n30样本.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(minimum_distributions=False):
    source_hash = digest(SOURCE)
    matrix = json.loads(SOURCE.read_text(encoding='utf-8'))
    assert matrix['config']['truth'] == [5., 1000., 500.]
    original = sorted((r for r in matrix['samples'] if r['n'] == 30), key=lambda r: r['id'])
    assert len(original) == 50 and [r['id'] for r in original] == list(range(1,51))
    rows = []
    for r in original:
        x5 = np.array(r['values'], dtype=float)
        assert len(x5) == 30 and np.all(x5 > 500.) and np.all(np.diff(x5) >= 0)
        latent = ((x5 - 500.) / 1000.) ** 5.
        x2 = 500. + 1000. * latent ** .5
        for beta, x in ((2.,x2), (5.,x5)):
            rows.append({'beta': beta, 'n': 30, 'sample_id': r['id'],
                         'observations': x.tolist(),
                         'origin': 'same-latent conversion' if beta == 2. else 'archived beta5 observations'})
    provenance = {
        'source_matrix': '../W(5,1000,500)/20260929-新抽样/程序/完整矩阵/数据/matrix.json',
        'source_sha256': source_hash, 'source_seed_namespace': 2026092903,
        'beta5_archived_groups': 50, 'beta2_mapped_groups': 50,
        'mapping': 'E=((t_beta5-500)/1000)^5; t_beta2=500+1000*E^(1/2)',
        'new_random_draws': 0, 'new_fits': 0, 'samples': rows,
    }
    if CACHE.exists():
        assert json.loads(CACHE.read_text(encoding='utf-8')) == provenance
    else:
        CACHE.write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    assert digest(SOURCE) == source_hash
    spec = importlib.util.spec_from_file_location('intro_mother', HERE / '20261010-导入样本起点图.py')
    mother = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mother)
    mother.main(extra_samples=rows, minimum_distributions=minimum_distributions, extra_provenance={
        'snapshot': CACHE.relative_to(ROOT).as_posix(), 'snapshot_sha256': digest(CACHE),
        'source_matrix': provenance['source_matrix'], 'source_sha256': source_hash,
        'beta5_archived_groups': 50, 'beta2_mapped_groups': 50,
        'new_random_draws': 0, 'new_fits': 0,
    })


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('intro_latest', HERE / '20261010-图2最小值密度曲线.py')
    latest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(latest)
    latest.main()
