"""
E09-9a 跨样本量测试矩阵
- 加载 E09-2b 已训练的 6 个 BP-feature 模型
- 在所有样本量的测试集上交叉测试
- 输出 6×6 J_param 矩阵
"""

import sys
import os
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

from common import (
    generate_dataset,
    prepare_feature_input,
    SAMPLE_SIZES,
)
from bp_model import create_bp_feature_model

# 配置
N_CONFIGS_TEST = 100
N_REPEATS_TEST = 5
MODEL_DIR = os.path.join(SCRIPT_DIR, ".")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def calc_jparam(y_true, y_pred):
    err_beta = (y_pred[:, 0] - y_true[:, 0]) / y_true[:, 0]
    err_eta = (y_pred[:, 1] - y_true[:, 1]) / y_true[:, 1]
    err_gamma = (y_pred[:, 2] - y_true[:, 2]) / y_true[:, 1]
    return np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))


def calc_param_rmse(y_true, y_pred):
    """逐参数相对 RMSE"""
    results = {}
    for i, name in enumerate(['beta', 'eta', 'gamma']):
        if name == 'gamma':
            err = (y_pred[:, i] - y_true[:, i]) / y_true[:, 1]
        else:
            err = (y_pred[:, i] - y_true[:, i]) / y_true[:, i]
        results[name] = np.sqrt(np.mean(err**2))
    return results


def main():
    print("=" * 60)
    print("E09-9a: 跨样本量测试矩阵")
    print("=" * 60)

    # 生成所有样本量的测试数据
    test_data = {}
    for n in SAMPLE_SIZES:
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST,
                                   param_seed=200, sample_seed_start=20000)
        X_test, y_test = prepare_feature_input(df_test, n)
        test_data[n] = (X_test, y_test)
        print(f"测试集 n={n}: X={X_test.shape}, y={y_test.shape}")

    # 加载所有模型并交叉测试
    jparam_matrix = np.zeros((len(SAMPLE_SIZES), len(SAMPLE_SIZES)))
    all_results = []

    for i, train_n in enumerate(SAMPLE_SIZES):
        model_path = os.path.join(MODEL_DIR, f"E09-2b_bp_feature_n{train_n}.pt")
        if not os.path.exists(model_path):
            print(f"模型不存在: {model_path}")
            continue

        # 加载模型
        trainer = create_bp_feature_model()
        trainer.load(model_path)
        print(f"\n加载模型 n={train_n}: {model_path}")

        for j, test_n in enumerate(SAMPLE_SIZES):
            X_test, y_test = test_data[test_n]
            y_pred = trainer.predict(X_test)
            jparam = calc_jparam(y_test, y_pred)
            rmse = calc_param_rmse(y_test, y_pred)
            jparam_matrix[i, j] = jparam

            row = {
                'train_n': train_n,
                'test_n': test_n,
                'jparam': jparam,
                'rmse_beta': rmse['beta'],
                'rmse_eta': rmse['eta'],
                'rmse_gamma': rmse['gamma'],
            }
            all_results.append(row)

            marker = " ★" if train_n == test_n else ""
            print(f"  train_n={train_n:>2} → test_n={test_n:>2}: J={jparam:.4f}{marker}")

    # 保存结果
    df_results = pd.DataFrame(all_results)
    df_results.to_csv(os.path.join(OUTPUT_DIR, 'E09-9a_cross_n_matrix.csv'), index=False)

    # 打印矩阵
    print("\n" + "=" * 60)
    print("跨样本量 J_param 矩阵（行=训练n，列=测试n）")
    print("=" * 60)
    df_matrix = pd.DataFrame(jparam_matrix,
                             index=[f"train_{n}" for n in SAMPLE_SIZES],
                             columns=[f"test_{n}" for n in SAMPLE_SIZES])
    print(df_matrix.to_string(float_format='%.4f'))

    # 分析：对角线 vs 非对角线
    print("\n" + "=" * 60)
    print("泛化性分析")
    print("=" * 60)
    diag = np.diag(jparam_matrix)
    for i, train_n in enumerate(SAMPLE_SIZES):
        row = jparam_matrix[i, :]
        same_n = row[i]
        other_n = np.delete(row, i)
        avg_other = np.mean(other_n)
        best_other_n = SAMPLE_SIZES[np.argmin(other_n)]
        best_other = np.min(other_n)
        worst_other_n = SAMPLE_SIZES[np.argmax(other_n)]
        worst_other = np.max(other_n)
        print(f"train_n={train_n:>2}: 同n={same_n:.4f}  "
              f"跨n平均={avg_other:.4f}({avg_other/same_n:.2f}x)  "
              f"最佳跨n={best_other_n}(J={best_other:.4f})  "
              f"最差跨n={worst_other_n}(J={worst_other:.4f})")

    # 分析：哪个测试n最难
    print("\n各测试n的平均 J_param（跨所有训练n）：")
    for j, test_n in enumerate(SAMPLE_SIZES):
        col = jparam_matrix[:, j]
        avg = np.mean(col)
        print(f"  test_n={test_n:>2}: 平均 J={avg:.4f}")

    return df_results


if __name__ == "__main__":
    main()
