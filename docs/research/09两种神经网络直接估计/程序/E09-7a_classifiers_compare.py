"""
E09-7a 多分类器对比实验
- 保持 K=10、12 维特征不变
- 横向对比 SVM / XGBoost / LightGBM / 随机森林
- 输出分类准确率 + J_param
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import pickle
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

from common import (
    generate_dataset,
    prepare_feature_input,
    evaluate_predictions,
    PARAM_RANGES,
    SAMPLE_SIZES,
)


# ============================================================
# 配置
# ============================================================

N_CONFIGS_TRAIN = 500
N_CONFIGS_VAL = 100
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_VAL = 4
N_REPEATS_TEST = 5
K = 10

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 分箱工具（复用 E09-4）
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
# 分类器定义
# ============================================================

def get_classifiers():
    """返回所有候选分类器（含名称和构造函数）"""
    return {
        'SVM': lambda: Pipeline([
            ('scaler', StandardScaler()),
            ('clf', SVC(kernel='rbf', probability=True, random_state=42))
        ]),
        'XGBoost': lambda: Pipeline([
            ('scaler', StandardScaler()),
            ('clf', XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                use_label_encoder=False, eval_metric='mlogloss',
                random_state=42, verbosity=0
            ))
        ]),
        'LightGBM': lambda: Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LGBMClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                random_state=42, verbosity=-1
            ))
        ]),
        'RandomForest': lambda: Pipeline([
            ('scaler', StandardScaler()),
            ('clf', RandomForestClassifier(
                n_estimators=200, max_depth=10, random_state=42
            ))
        ]),
    }


# ============================================================
# 训练与评估
# ============================================================

def train_and_evaluate(clf_name, clf_factory, X_train, y_train, X_test, y_test,
                       bin_edges_dict, bin_centers_dict, params, param_indices):
    """训练单个分类器（逐参数），返回准确率和 J_param"""
    classifiers = {}
    accuracies = {}

    for param, idx in zip(params, param_indices):
        y_discrete = discretize(y_train[:, idx], bin_edges_dict[param])
        clf = clf_factory()
        clf.fit(X_train, y_discrete)
        classifiers[param] = clf

        y_test_discrete = discretize(y_test[:, idx], bin_edges_dict[param])
        acc = clf.score(X_test, y_test_discrete)
        accuracies[param] = acc

    # 概率加权还原
    proba_preds = []
    for param in params:
        proba = classifiers[param].predict_proba(X_test)
        # predict_proba 可能不返回所有类别（如果某类在训练中没有样本）
        # 需要对齐 bin_centers
        pred = undiscretize_proba(proba, bin_centers_dict[param])
        proba_preds.append(pred)

    y_pred = np.column_stack(proba_preds)

    # 计算 J_param
    err_beta = (y_pred[:, 0] - y_test[:, 0]) / y_test[:, 0]
    err_eta = (y_pred[:, 1] - y_test[:, 1]) / y_test[:, 1]
    err_gamma = (y_pred[:, 2] - y_test[:, 2]) / y_test[:, 1]
    jparam = np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))

    return accuracies, jparam


# ============================================================
# 主实验
# ============================================================

def main():
    print("=" * 60)
    print("E09-7a: 多分类器对比实验")
    print("=" * 60)

    classifiers = get_classifiers()
    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]

    all_results = []

    for n in SAMPLE_SIZES:
        print(f"\n--- 样本量 n = {n} ---")

        # 生成数据（与 E09-4 相同的种子）
        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN,
                                    param_seed=42, sample_seed_start=0)
        df_val = generate_dataset(N_CONFIGS_VAL, n, N_REPEATS_VAL,
                                  param_seed=100, sample_seed_start=10000)
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST,
                                   param_seed=200, sample_seed_start=20000)

        X_train, y_train = prepare_feature_input(df_train, n)
        X_val, y_val = prepare_feature_input(df_val, n)
        X_test, y_test = prepare_feature_input(df_test, n)

        # 分箱
        bin_edges_dict = {}
        bin_centers_dict = {}
        for param in params:
            bin_edges, bin_centers = create_bins(param, K)
            bin_edges_dict[param] = bin_edges
            bin_centers_dict[param] = bin_centers

        # 逐分类器训练
        for clf_name, clf_factory in classifiers.items():
            start = time.time()
            accs, jparam = train_and_evaluate(
                clf_name, clf_factory,
                X_train, y_train, X_test, y_test,
                bin_edges_dict, bin_centers_dict, params, param_indices
            )
            elapsed = time.time() - start

            row = {
                'n': n,
                'classifier': clf_name,
                'acc_beta': accs['beta'],
                'acc_eta': accs['eta'],
                'acc_gamma': accs['gamma'],
                'acc_mean': np.mean(list(accs.values())),
                'jparam': jparam,
                'time': elapsed,
            }
            all_results.append(row)
            print(f"  {clf_name:15s}  acc={row['acc_mean']:.3f}  "
                  f"J={jparam:.4f}  ({elapsed:.1f}s)")

    # 保存结果
    df_results = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, 'E09-7a_classifiers_compare.csv')
    df_results.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    # 汇总表格
    print("\n" + "=" * 60)
    print("汇总：各分类器 J_param 对比")
    print("=" * 60)
    pivot = df_results.pivot_table(
        index='n', columns='classifier', values='jparam'
    )
    # 按 J_param 排序列
    col_order = pivot.mean().sort_values().index.tolist()
    pivot = pivot[col_order]
    print(pivot.to_string(float_format='%.4f'))

    # 汇总准确率
    print("\n" + "=" * 60)
    print("汇总：各分类器平均准确率")
    print("=" * 60)
    pivot_acc = df_results.pivot_table(
        index='n', columns='classifier', values='acc_mean'
    )
    pivot_acc = pivot_acc[col_order]
    print(pivot_acc.to_string(float_format='%.3f'))

    return df_results


if __name__ == "__main__":
    main()
