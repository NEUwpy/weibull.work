"""Prepare current wide tables directly from the adjacent saved result CSVs."""
import argparse
import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / '数据'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-json', type=Path, required=True)
    args = parser.parse_args()
    samples = pd.read_csv(RESULTS / '样本.csv', float_precision='round_trip')
    detail = pd.read_csv(RESULTS / '估计明细.csv', float_precision='round_trip')
    assert len(samples) == 6000 and len(detail) == 18000
    fits = detail.set_index(['n', '组号', '方法'])
    assert fits.index.is_unique
    sheets = []
    for n in [7, 10, 15, 20, 50]:
        observed = samples[samples.n == n].sort_values('组号')
        assert observed['组号'].tolist() == list(range(1, 1201))
        sample_rows = observed[['组号'] + [f'x({i})' for i in range(1, n + 1)]].values.tolist()
        estimate_rows = []
        for group in range(1, 1201):
            values = [group]
            for method in ['MLE', 'MMLE', 'WMLE']:
                row = fits.loc[(n, group, method)]
                values.extend([float(row[c]) for c in ['β估计', 'η估计', 'γ估计']] if row['状态'] == '成功' else [None] * 3)
            estimate_rows.append(values)
        sheets += [dict(name=f'生成样本_n{n}', kind='samples', n=n, rows=sample_rows),
                   dict(name=f'估计结果_n{n}', kind='estimates', n=n, rows=estimate_rows)]
    summary = pd.read_csv(RESULTS / '三方法汇总.csv', float_precision='round_trip')
    assert summary.shape == (15, 14)
    data = dict(sheets=sheets, summary=dict(columns=summary.columns.tolist(), rows=summary.values.tolist()))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print('Saved CSVs prepared: 6000 sample groups and 18000 estimates; no sampling or fitting.')

if __name__ == '__main__':
    main()
