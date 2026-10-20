"""核对现有估计的η分化、γ偏移与零边界配对；不调用估计器。"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
TARGET = HERE.parent / '分析数据/β变化分布结构核对.json'
METHODS = ['MDM-0.1', 'LSE', 'LRE(Park)', 'WMLE', 'MLE', 'MMLE(KR)', 'MM']


def main():
    sources, records = {}, []
    for n in [50, 7]:
        for beta in np.arange(1.5, 5.1, .5):
            path = STUDY / f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[path.relative_to(STUDY).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            frame = pd.read_csv(path, float_precision='round_trip')
            assert frame['样本编号'].tolist() == list(range(1200))
            for method in METHODS:
                valid = frame[frame[method + '_状态'].eq('success')]
                eta = valid[method + '_尺度估计'].to_numpy()
                gamma = valid[method + '_位置估计'].to_numpy()
                assert np.isfinite(eta).all() and np.isfinite(gamma).all()
                zero = np.isclose(gamma, 0, atol=1e-8, rtol=0)
                row = dict(n=n, beta=float(beta), method=method, valid=len(valid),
                           eta_mean=float(eta.mean()), gamma_mean=float(gamma.mean()),
                           eta_quartiles=np.quantile(eta, [.25, .5, .75]).tolist(),
                           gamma_quartiles=np.quantile(gamma, [.25, .5, .75]).tolist(),
                           gamma_zero_rate=float(zero.mean()),
                           eta_median_gamma_zero=float(np.median(eta[zero])) if zero.any() else None,
                           eta_median_gamma_positive=float(np.median(eta[~zero])) if (~zero).any() else None,
                           eta_gamma_correlation=float(np.corrcoef(eta, gamma)[0, 1]))
                # 三种带宽仅核对图示双峰是否保持，不作为多峰显著性检验。
                if method in ['LSE', 'LRE(Park)']:
                    visible = eta[(eta >= 0) & (eta <= 2000)]
                    grid = np.linspace(0, 2000, 1001)
                    row['eta_kde_modes'] = {}
                    for factor in [.7, 1., 1.3]:
                        density = gaussian_kde(visible, bw_method=lambda obj: obj.scotts_factor() * factor)(grid)
                        peaks, _ = find_peaks(density, prominence=density.max() * .04)
                        row['eta_kde_modes'][str(factor)] = grid[peaks].tolist()
                records.append(row)
            print(f'已核对 n={n}，β={beta:g}', flush=True)
    for method in ['LSE', 'LRE(Park)']:
        for n in [50, 7]:
            low = next(row for row in records if (row['n'], row['beta'], row['method']) == (n, 1.5, method))
            high = next(row for row in records if (row['n'], row['beta'], row['method']) == (n, 5., method))
            assert all(len(modes) == 1 for modes in low['eta_kde_modes'].values())
            assert all(len(modes) == 2 for modes in high['eta_kde_modes'].values())
            assert high['gamma_zero_rate'] > low['gamma_zero_rate']
            assert high['eta_median_gamma_zero'] > high['eta_median_gamma_positive']
    TARGET.write_text(json.dumps(dict(sources=sources, records=records), ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(dict(source_files=len(sources), records=len(records), output=TARGET.as_posix()), ensure_ascii=False))


if __name__ == '__main__':
    main()
