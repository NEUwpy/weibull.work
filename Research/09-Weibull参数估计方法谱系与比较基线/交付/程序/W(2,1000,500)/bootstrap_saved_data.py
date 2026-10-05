"""Restore runtime-only NPZ and reuse CSV from the adjacent saved tables."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / '数据'

def main():
    sample = pd.read_csv(RESULTS / '样本.csv', float_precision='round_trip')
    arrays = {}
    for n in [7, 10, 15, 20, 50]:
        rows = sample[sample.n == n].sort_values('组号')
        values = rows[[f'x({i})' for i in range(1, n + 1)]].to_numpy(dtype=float)
        assert values.shape == (1200, n)
        for x, digest in zip(values, rows['样本SHA256']):
            assert hashlib.sha256(x.tobytes()).hexdigest() == digest
        arrays[f'n{n}'] = values
    np.savez_compressed(HERE / '输入样本.npz', **arrays)
    source = pd.read_csv(RESULTS / '估计明细.csv', float_precision='round_trip')
    raw = source.rename(columns={'方法': 'method_variant', 'β真值': 'beta', 'η真值': 'eta', 'γ真值': 'gamma',
                                 'β估计': 'beta_hat', 'η估计': 'eta_hat', 'γ估计': 'gamma_hat',
                                 '收敛': 'converged', '耗时(秒)': 'time', '样本SHA256': 'sample_sha256'})
    raw['method_variant'] = raw.method_variant.replace({'MMLE': 'K-R MMLE'})
    raw['status'] = source['状态'].map({'成功': 'success', '失败': 'failure'})
    raw['extra'] = [json.dumps({'solution_info': {'status': 'ok' if s == '成功' else str(reason)}})
                    for s, reason in zip(source['状态'], source['失败原因代码'])]
    cols = ['n', 'block', 'repeat_id', 'method_variant', 'beta', 'eta', 'gamma', 'beta_hat', 'eta_hat',
            'gamma_hat', 'converged', 'status', 'time', 'sample_sha256', 'extra']
    reuse = HERE / 'reuse' / '三方法原文口径'
    reuse.mkdir(parents=True, exist_ok=True)
    raw.loc[raw.method_variant.isin(['MLE', 'WMLE']), cols].to_csv(reuse / 'per_sample.csv.gz', index=False, compression='gzip')
    print('Original sample SHA verified; runtime input restored, MLE/WMLE preserved for reuse.')

if __name__ == '__main__':
    main()
