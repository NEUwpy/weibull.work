"""
直接估计 — MDM 基准对比数据生成

用途：
    在 M3 相同的测试集上运行 MDM(δ=0.5)，生成基准精度数据，
    用于 M3 方法对比 Tab 展示 AI 直接估计 vs MDM。
    指标与 M3 完全一致：MAE、MRE，分参数 + 聚合。

使用方法：
    cd python/studies/direct_estimation
    python generate_mdm_baseline.py

输出：
    public/ai/data/mdm_baseline_comparison.json

作者：Claude Code
日期：2026-04-27
"""

import sys
import json
import csv
import time
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM

PUBLIC_DATA_DIR = PROJECT_ROOT / 'public' / 'ai' / 'data'
DATA_DIR = Path(__file__).parent / 'data'

SAMPLE_SIZES = [5, 7, 10, 15]
DELTA = 0.5
N_SAMPLES = 500  # 从 10000 中抽样


def run_mdm(sample, delta):
    """对单个样本运行 MDM，返回 (beta, eta, gamma) 或 None"""
    try:
        algo = MDM(sample, rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=60)
        if result[4] == "no_intersection":
            return None
        b, e, g = result[0], result[1], result[2]
        if b is None or e is None or g is None:
            return None
        if b <= 0 or b > 50 or e <= 0 or e > 1e6:
            return None
        return (b, e, g)
    except Exception:
        return None


def load_test_data(n):
    """加载 M3 的 in-group 测试数据，抽样 N_SAMPLES 个"""
    csv_path = DATA_DIR / f'test_data_ig_n{n}.csv'
    if not csv_path.exists():
        return None

    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            rows.append(row)

    rng = np.random.RandomState(42 + n)
    if len(rows) > N_SAMPLES:
        indices = rng.choice(len(rows), N_SAMPLES, replace=False)
        rows = [rows[i] for i in sorted(indices)]

    cases = []
    for row in rows:
        row_n = int(row[0])
        cases.append({
            'beta': float(row[1]),
            'eta': float(row[2]),
            'gamma': float(row[3]),
            'sample': [float(v) for v in row[5:5 + row_n]],
        })
    return cases


def main():
    output = {}

    for n in SAMPLE_SIZES:
        print(f"\n=== n={n} ===")
        cases = load_test_data(n)
        if cases is None:
            print("  测试数据不存在，跳过")
            continue

        print(f"  抽样 {len(cases)} 个样本, 运行 MDM(δ={DELTA})...")
        t0 = time.time()

        est_b, est_e, est_g = [], [], []
        true_b, true_e, true_g = [], [], []
        success = 0

        for c in cases:
            result = run_mdm(c['sample'], DELTA)
            true_b.append(c['beta'])
            true_e.append(c['eta'])
            true_g.append(c['gamma'])
            if result is not None:
                est_b.append(result[0])
                est_e.append(result[1])
                est_g.append(result[2])
                success += 1
            else:
                est_b.append(None)
                est_e.append(None)
                est_g.append(None)

        elapsed = time.time() - t0
        print(f"  成功: {success}/{len(cases)} ({elapsed:.1f}s)")

        # 计算指标（只用成功的样本）
        valid_b = [(e, t) for e, t in zip(est_b, true_b) if e is not None]
        valid_e = [(e, t) for e, t in zip(est_e, true_e) if e is not None]
        valid_g = [(e, t) for e, t in zip(est_g, true_g) if e is not None]

        def calc_mae(pairs):
            if not pairs:
                return None
            return sum(abs(e - t) for e, t in pairs) / len(pairs)

        def calc_mre(pairs):
            if not pairs:
                return None
            rels = [abs(e - t) / max(abs(t), 1e-6) for e, t in pairs]
            return sum(rels) / len(rels)

        mae_b = calc_mae(valid_b)
        mae_e = calc_mae(valid_e)
        mae_g = calc_mae(valid_g)
        mre_b = calc_mre(valid_b)
        mre_e = calc_mre(valid_e)
        mre_g = calc_mre(valid_g)

        # 聚合指标
        total_mae = sum(v for v in [mae_b, mae_e, mae_g] if v is not None)
        total_mre = sum(v for v in [mre_b, mre_e, mre_g] if v is not None)

        output[f'n{n}'] = {
            'n': n,
            'total_samples': len(cases),
            'success_count': success,
            'success_rate': round(success / len(cases), 4),
            'avg_time_ms': round(elapsed / len(cases) * 1000, 2),
            'per_param': {
                'beta': {'mae': round(mae_b, 6) if mae_b else None, 'mre': round(mre_b, 6) if mre_b else None},
                'eta':  {'mae': round(mae_e, 4) if mae_e else None, 'mre': round(mre_e, 6) if mre_e else None},
                'gamma': {'mae': round(mae_g, 4) if mae_g else None, 'mre': round(mre_g, 6) if mre_g else None},
            },
            'aggregate': {
                'total_mae': round(total_mae, 4),
                'total_mre': round(total_mre, 6),
            }
        }

        if mae_b:
            print(f"  MAE(β)={mae_b:.4f}, MAE(η)={mae_e:.1f}, MAE(γ)={mae_g:.1f}")
            print(f"  MRE(β)={mre_b:.4f}, MRE(η)={mre_e:.4f}, MRE(γ)={mre_g:.4f}")

    # 加载 M3 AI 直接估计的精度
    output['ai_direct'] = {}
    for n in SAMPLE_SIZES:
        m3_path = PUBLIC_DATA_DIR / f'direct_estimation_n{n}_metrics.json'
        if m3_path.exists():
            with open(m3_path, 'r', encoding='utf-8') as f:
                m3 = json.load(f)['metrics']
            output['ai_direct'][f'n{n}'] = {
                'per_param': {
                    'beta': {'mae': round(m3['mae_beta'], 6), 'mre': round(m3['mean_relative_error_beta'], 6)},
                    'eta':  {'mae': round(m3['mae_eta'], 4), 'mre': round(m3['mean_relative_error_eta'], 6)},
                    'gamma': {'mae': round(m3['mae_gamma'], 4), 'mre': round(m3['mean_relative_error_gamma'], 6)},
                },
                'aggregate': {
                    'total_mae': round(m3['mae_beta'] + m3['mae_eta'] + m3['mae_gamma'], 4),
                    'total_mre': round(m3['mean_relative_error_beta'] + m3['mean_relative_error_eta'] + m3['mean_relative_error_gamma'], 6),
                }
            }

    # 保存
    output_path = PUBLIC_DATA_DIR / 'mdm_baseline_comparison.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n输出: {output_path}")


if __name__ == '__main__':
    main()
