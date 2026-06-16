"""
重新计算正确的 J_param 并更新汇总文件
J_param = √( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )
"""

import pandas as pd
import numpy as np
import os
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")


def compute_jparam_correct(csv_path):
    """按定义计算 J_param"""
    df = pd.read_csv(csv_path)

    err_beta = (df['beta_pred'] - df['beta_true']) / df['beta_true']
    err_eta = (df['eta_pred'] - df['eta_true']) / df['eta_true']
    err_gamma = (df['gamma_pred'] - df['gamma_true']) / df['eta_true']  # gamma 用 eta 归一化

    j_param_sq = err_beta**2 + err_eta**2 + err_gamma**2
    j_param = np.sqrt(j_param_sq.mean())

    # 各分量的相对 RMSE
    rmse_beta_rel = np.sqrt((err_beta**2).mean())
    rmse_eta_rel = np.sqrt((err_eta**2).mean())
    rmse_gamma_rel = np.sqrt((err_gamma**2).mean())

    return {
        'j_param': j_param,
        'rmse_beta_rel': rmse_beta_rel,
        'rmse_eta_rel': rmse_eta_rel,
        'rmse_gamma_rel': rmse_gamma_rel,
    }


def recompute_summary(prefix):
    """重新计算汇总数据"""
    rows = []

    for n in [5, 7, 10, 15, 20, 50]:
        csv_path = os.path.join(OUTPUT_DIR, f'{prefix}_test_n{n}.csv')

        if not os.path.exists(csv_path):
            print(f"Warning: {csv_path} not found")
            continue

        metrics = compute_jparam_correct(csv_path)

        # 读取原始汇总获取其他指标
        orig_summary_path = os.path.join(OUTPUT_DIR, f'{prefix}_summary.csv')
        orig_summary = pd.read_csv(orig_summary_path)
        orig_row = orig_summary[orig_summary['n'] == n].iloc[0]

        row = {
            'n': n,
            'j_param': metrics['j_param'],
            'rmse_beta_rel': metrics['rmse_beta_rel'],
            'rmse_eta_rel': metrics['rmse_eta_rel'],
            'rmse_gamma_rel': metrics['rmse_gamma_rel'],
            # 保留绝对 RMSE（但不叫 J_param）
            'rmse_beta_abs': orig_row['rmse_beta'],
            'rmse_eta_abs': orig_row['rmse_eta'],
            'rmse_gamma_abs': orig_row['rmse_gamma'],
            # 保留其他指标
            'mae_beta': orig_row['mae_beta'],
            'mae_eta': orig_row['mae_eta'],
            'mae_gamma': orig_row['mae_gamma'],
            'bias_beta': orig_row['bias_beta'],
            'bias_eta': orig_row['bias_eta'],
            'bias_gamma': orig_row['bias_gamma'],
            'rmse_x095': orig_row['rmse_x095'],
            'mae_x095': orig_row['mae_x095'],
            'failure_rate': orig_row['failure_rate'],
            'train_time': orig_row['train_time'],
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # 保存修正后的汇总
    output_path = os.path.join(OUTPUT_DIR, f'{prefix}_summary_corrected.csv')
    df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")

    return df


def main():
    print("="*60)
    print("重新计算正确的 J_param")
    print("="*60)

    print("\nE09-2a BP-raw:")
    df_a = recompute_summary('E09-2a')
    print(df_a[['n', 'j_param', 'rmse_beta_rel', 'rmse_eta_rel', 'rmse_gamma_rel']].to_string(index=False))

    print("\nE09-2b BP-feature:")
    df_b = recompute_summary('E09-2b')
    print(df_b[['n', 'j_param', 'rmse_beta_rel', 'rmse_eta_rel', 'rmse_gamma_rel']].to_string(index=False))

    print("\n对比 (J_param):")
    print(f"{'n':>5} {'E09-2a':>10} {'E09-2b':>10} {'差异':>10}")
    for _, row_a in df_a.iterrows():
        row_b = df_b[df_b['n'] == row_a['n']].iloc[0]
        diff = row_b['j_param'] - row_a['j_param']
        print(f"{int(row_a['n']):>5} {row_a['j_param']:>10.4f} {row_b['j_param']:>10.4f} {diff:>10.4f}")


if __name__ == "__main__":
    main()
