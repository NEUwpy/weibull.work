"""Descriptive reanalysis of frozen candidates; no MDM fits or model training.

Run from any directory. Outputs are exploratory, not an independent test set.
Within each true-parameter cell use ddof=0 so empirical MSE=Bias^2+Var exactly.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/exploratory/offset_mechanism_scan_20260905'
SOURCE = ROOT / 'artifacts/formal/E5_normalized_raw/shared_data/chunks'
CELL = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n']
KEY = CELL + ['repeat_id']


def main():
    paths = sorted(SOURCE.glob('chunk_*_mdm.csv'))
    d = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    assert len(d) == 1248000 and not d.duplicated(KEY + ['delta']).any()
    assert len(d[KEY].drop_duplicates()) == 48000
    assert np.allclose(sorted(d.delta.unique()), np.arange(26) * .02)
    assert d.status.eq('success').all()
    for p in ['beta', 'eta', 'gamma']:
        d['e_' + p] = (d[p + '_hat'] - d[p]) / d['eta' if p == 'gamma' else p]
    cols = ['e_beta', 'e_eta', 'e_gamma']
    assert np.isfinite(d[cols].to_numpy()).all()
    d['risk'] = (d[cols] ** 2).sum(axis=1)
    g = d.groupby(CELL + ['delta'], sort=True)
    assert g.size().eq(300).all() and len(g) == 160 * 26
    c = g.size().rename('count').to_frame()
    for p in ['beta', 'eta', 'gamma']:
        c[p + '_bias'] = g['e_' + p].mean()
        c[p + '_bias_sq'] = c[p + '_bias'] ** 2
        c[p + '_var'] = g['e_' + p].var(ddof=0)
    c['bias_sq_sum'] = c[[p + '_bias_sq' for p in ['beta','eta','gamma']]].sum(axis=1)
    c['var_sum'] = c[[p + '_var' for p in ['beta','eta','gamma']]].sum(axis=1)
    c['risk'] = g.risk.mean()
    residual = float((c.risk - c.bias_sq_sum - c.var_sum).abs().max())
    assert residual < 1e-10
    c = c.reset_index()
    a = c.groupby('delta')[['bias_sq_sum','var_sum','risk']].mean()
    a['J1'] = np.sqrt(a.risk)
    n = c.groupby(['n','delta'])[['bias_sq_sum','var_sum','risk']].mean()
    n['J1'] = np.sqrt(n.risk)
    comparison = {}
    for lo, hi in [(0., .1), (.06, .1), (.1, .5)]:
        low = c[c.delta.eq(lo)].set_index(CELL)
        high = c[c.delta.eq(hi)].set_index(CELL)
        change = high[['bias_sq_sum','var_sum','risk']] - low[['bias_sq_sum','var_sum','risk']]
        comparison[f'{lo:g}_to_{hi:g}'] = {
            'cells_bias_sq_decreased': int((change.bias_sq_sum < 0).sum()),
            'cells_var_decreased': int((change.var_sum < 0).sum()),
            'cells_risk_decreased': int((change.risk < 0).sum()),
            'cells_both_decreased': int(((change.bias_sq_sum < 0) & (change.var_sum < 0)).sum()),
        }
    # Paired changes diagnose which parameter estimates actually move.
    low = d[d.delta.eq(0.)].set_index(KEY)
    high = d[d.delta.eq(.1)].set_index(KEY)
    moves = {}
    for p in ['beta','eta','gamma']:
        v = high[p + '_hat'] - low[p + '_hat']
        moves[p] = {'increased': int((v > 1e-6).sum()),
                    'decreased': int((v < -1e-6).sum()),
                    'within_1e_6': int((v.abs() <= 1e-6).sum())}
    OUT.mkdir(parents=True, exist_ok=True)
    c.to_csv(OUT / 'cell_bias_variance.csv', index=False)
    a.to_csv(OUT / 'pooled_bias_variance.csv')
    n.to_csv(OUT / 'per_n_bias_variance.csv')
    info = {
        'scope': 'exploratory descriptive reanalysis of existing 48000 samples; no new fits',
        'rows': len(d), 'cells': 160, 'repeats_per_cell': 300, 'ddof': 0,
        'max_identity_residual': residual, 'cell_comparisons': comparison,
        'paired_estimate_movements_0_to_0_1': moves,
        'minimum_grid_delta': {k: float(a[k].idxmin()) for k in ['bias_sq_sum','var_sum','risk']},
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / 'summary.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(a.loc[[0., .06, .1, .5]].to_string())
    print(json.dumps({k: v for k,v in info.items() if 'sha256' not in k}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
