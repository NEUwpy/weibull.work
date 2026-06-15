"""
E09-7b 分箱数 K 敏感性实验
- 用最佳分类器（XGBoost），扫描 K=5/10/20/50
- 观察准确率与 J_param 的权衡
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

from common import (
    generate_dataset,
    prepare_feature_input,
    PARAM_RANGES,
    SAMPLE_SIZES,
)


# ============================================================
# 配置
# ============================================================

N_CONFIGS_TRAIN = 500
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_TEST = 5

K_CANDIDATES = [5, 10, 20, 50]

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 分箱工具
# ============================================================

def create_bins(param_name, n_bins):
    low, high = PARAM_RANGES[param_name]
    bin_edges = np.linspace(low, high, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    return bin_edges, bin_centers


def discretize(values, bin_edges):
    return np.digitize(values, bin_edges[1:-1])


def undiscretize_proba(proba, bin_centers):
    return np.dot(proba, bin_centers)


# ============================================================
# 离散化误差下界
# ============================================================

def compute_discretization_bound(y_true, param_idx, bin_edges, bin_centers):
    """完美分类时的最小 J_param 贡献"""
    values = y_true[:, param_idx]
    labels = discretize(values, bin_edges)
    reconstructed = bin_centers[labels]
    errors = (reconstructed - values) / values
    return np.sqrt(np.mean(errors**2))


# ============================================================
# 主实验
# ============================================================

def main():
    print("=" * 60)
    print("E09-7b: 分箱数 K 敏感性实验")
    print("=" * 60)

    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]
    all_results = []

    for n in SAMPLE_SIZES:
        print(f"\n--- 样本量 n = {n} ---")

        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN,
                                    param_seed=42, sample_seed_start=0)
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST,
                                   param_seed=200, sample_seed_start=20000)
        X_train, y_train = prepare_feature_input(df_train, n)
        X_test, y_test = prepare_feature_input(df_test, n)

        for K in K_CANDIDATES:
            # 离散化误差下界
            bound_components = []
            for param, idx in zip(params, param_indices):
                bin_edges, bin_centers = create_bins(param, K)
                b = compute_discretization_bound(y_test, idx, bin_edges, bin_centers)
                bound_components.append(b)
            jparam_bound = np.sqrt(sum(b**2 for b in bound_components))

            # 训练 XGBoost
            bin_edges_dict = {}
            bin_centers_dict = {}
            classifiers = {}

            start = time.time()
            for param, idx in zip(params, param_indices):
                bin_edges, bin_centers = create_bins(param, K)
                bin_edges_dict[param] = bin_edges
                bin_centers_dict[param] = bin_centers

                y_discrete = discretize(y_train[:, idx], bin_edges)
                clf = Pipeline([
                    ('scaler', StandardScaler()),
                    ('clf', XGBClassifier(
                        n_estimators=200, max_depth=6, learning_rate=0.1,
                        use_label_encoder=False, eval_metric='mlogloss',
                        random_state=42, verbosity=0
                    ))
                ])
                clf.fit(X_train, y_discrete)
                classifiers[param] = clf
            elapsed = time.time() - start

            # 预测
            proba_preds = []
            accs = []
            for param, idx in zip(params, param_indices):
                proba = classifiers[param].predict_proba(X_test)
                pred = undiscretize_proba(proba, bin_centers_dict[param])
                proba_preds.append(pred)

                y_test_discrete = discretize(y_test[:, idx], bin_edges_dict[param])
                acc = classifiers[param].score(X_test, y_test_discrete)
                accs.append(acc)

            y_pred = np.column_stack(proba_preds)
            err_beta = (y_pred[:, 0] - y_test[:, 0]) / y_test[:, 0]
            err_eta = (y_pred[:, 1] - y_test[:, 1]) / y_test[:, 1]
            err_gamma = (y_pred[:, 2] - y_test[:, 2]) / y_test[:, 1]
            jparam = np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))

            row = {
                'n': n,
                'K': K,
                'jparam_bound': jparam_bound,
                'jparam': jparam,
                'oracle_gap': jparam - jparam_bound,
                'acc_mean': np.mean(accs),
                'acc_beta': accs[0],
                'acc_eta': accs[1],
                'acc_gamma': accs[2],
                'time': elapsed,
            }
            all_results.append(row)
            print(f"  K={K:3d}  bound={jparam_bound:.4f}  "
                  f"J={jparam:.4f}  gap={row['oracle_gap']:.4f}  "
                  f"acc={row['acc_mean']:.3f}  ({elapsed:.1f}s)")

    # 保存
    df_results = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, 'E09-7b_bins_sensitivity.csv')
    df_results.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    # 汇总：J_param vs K
    print("\n" + "=" * 60)
    print("汇总：J_param vs K（XGBoost）")
    print("=" * 60)
    pivot = df_results.pivot_table(index='n', columns='K', values='jparam')
    print(pivot.to_string(float_format='%.4f'))

    # 汇总：离散化下界
    print("\n" + "=" * 60)
    print("汇总：离散化误差下界")
    print("=" * 60)
    pivot_bound = df_results.pivot_table(index='n', columns='K', values='jparam_bound')
    print(pivot_bound.to_string(float_format='%.4f'))

    # 汇总：oracle gap
    print("\n" + "=" * 60)
    print("汇总：Oracle Gap（J_param - 下界）")
    print("=" * 60)
    pivot_gap = df_results.pivot_table(index='n', columns='K', values='oracle_gap')
    print(pivot_gap.to_string(float_format='%.4f'))

    # 汇总：准确率
    print("\n" + "=" * 60)
    print("汇总：平均分类准确率")
    print("=" * 60)
    pivot_acc = df_results.pivot_table(index='n', columns='K', values='acc_mean')
    print(pivot_acc.to_string(float_format='%.3f'))

    return df_results


if __name__ == "__main__":
    main()
