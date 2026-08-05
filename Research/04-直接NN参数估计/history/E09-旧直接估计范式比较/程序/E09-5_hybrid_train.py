"""
E09-5 混合模型实验
- SVM 分类 + BP 局部回归
- Oracle 分类上限
- 分类错误传播分析
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import pickle
from sklearn.svm import SVC
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# 添加路径
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
from bp_model import create_bp_feature_model

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 配置
N_CONFIGS_TRAIN = 500
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_TEST = 5
K = 10  # 分箱数


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


def undiscretize(labels, bin_centers):
    return bin_centers[labels]


# ============================================================
# 混合模型：SVM 分类 + SVR 局部回归
# ============================================================

def train_hybrid_svm_svr(X_train, y_train, K=10):
    """训练混合模型：SVM 分类 + SVR 局部回归"""
    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]

    classifiers = {}  # SVM 分类器
    regressors = {}   # 每个类别的 SVR 回归器
    bin_edges_dict = {}
    bin_centers_dict = {}

    for param, idx in zip(params, param_indices):
        # 分箱
        bin_edges, bin_centers = create_bins(param, K)
        bin_edges_dict[param] = bin_edges
        bin_centers_dict[param] = bin_centers

        # 训练分类器
        y_discrete = discretize(y_train[:, idx], bin_edges)
        clf = Pipeline([
            ('scaler', StandardScaler()),
            ('svm', SVC(kernel='rbf', random_state=42))
        ])
        clf.fit(X_train, y_discrete)
        classifiers[param] = clf

        # 训练每个类别的局部回归器
        regressors[param] = {}
        for k in range(K):
            mask = y_discrete == k
            if mask.sum() < 5:
                # 样本太少，用全局回归器
                regressors[param][k] = None
            else:
                svr = Pipeline([
                    ('scaler', StandardScaler()),
                    ('svr', SVR(kernel='rbf'))
                ])
                svr.fit(X_train[mask], y_train[mask, idx])
                regressors[param][k] = svr

    return classifiers, regressors, bin_edges_dict, bin_centers_dict


def predict_hybrid(X, classifiers, regressors, bin_centers_dict, params=['beta', 'eta', 'gamma']):
    """混合模型预测"""
    predictions = []

    for param in params:
        # 分类预测
        labels = classifiers[param].predict(X)

        # 局部回归预测
        preds = np.zeros(len(X))
        for k in range(len(bin_centers_dict[param])):
            mask = labels == k
            if mask.sum() == 0:
                continue
            if regressors[param][k] is not None:
                preds[mask] = regressors[param][k].predict(X[mask])
            else:
                # 用类别中心值
                preds[mask] = bin_centers_dict[param][k]

        predictions.append(preds)

    return np.column_stack(predictions)


# ============================================================
# Oracle 分类上限
# ============================================================

def train_oracle_regression(X_train, y_train, K=10):
    """Oracle 回归：使用真实类别标签训练局部回归器"""
    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]

    regressors = {}
    bin_edges_dict = {}
    bin_centers_dict = {}

    for param, idx in zip(params, param_indices):
        bin_edges, bin_centers = create_bins(param, K)
        bin_edges_dict[param] = bin_edges
        bin_centers_dict[param] = bin_centers

        y_discrete = discretize(y_train[:, idx], bin_edges)

        regressors[param] = {}
        for k in range(K):
            mask = y_discrete == k
            if mask.sum() < 5:
                regressors[param][k] = None
            else:
                svr = Pipeline([
                    ('scaler', StandardScaler()),
                    ('svr', SVR(kernel='rbf'))
                ])
                svr.fit(X_train[mask], y_train[mask, idx])
                regressors[param][k] = svr

    return regressors, bin_edges_dict, bin_centers_dict


def predict_oracle(X, y_true, regressors, bin_edges_dict, bin_centers_dict):
    """Oracle 预测：使用真实类别标签"""
    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]
    predictions = []

    for param, idx in zip(params, param_indices):
        bin_edges = bin_edges_dict[param]
        labels = discretize(y_true[:, idx], bin_edges)

        preds = np.zeros(len(X))
        for k in range(len(bin_centers_dict[param])):
            mask = labels == k
            if mask.sum() == 0:
                continue
            if regressors[param][k] is not None:
                preds[mask] = regressors[param][k].predict(X[mask])
            else:
                preds[mask] = bin_centers_dict[param][k]

        predictions.append(preds)

    return np.column_stack(predictions)


# ============================================================
# 计算 J_param
# ============================================================

def calc_jparam(y_true, y_pred):
    err_beta = (y_pred[:, 0] - y_true[:, 0]) / y_true[:, 0]
    err_eta = (y_pred[:, 1] - y_true[:, 1]) / y_true[:, 1]
    err_gamma = (y_pred[:, 2] - y_true[:, 2]) / y_true[:, 1]
    return np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))


# ============================================================
# 主函数
# ============================================================

def main():
    print("="*60)
    print("E09-5 混合模型实验")
    print("="*60)

    results = []

    for n in SAMPLE_SIZES:
        print(f"\n--- 样本量 n = {n} ---")

        # 生成数据
        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN, param_seed=42, sample_seed_start=0)
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST, param_seed=200, sample_seed_start=20000)

        X_train, y_train = prepare_feature_input(df_train, n)
        X_test, y_test = prepare_feature_input(df_test, n)

        start_time = time.time()

        # E09-5a: SVM + SVR 混合
        classifiers, regressors, bin_edges, bin_centers = train_hybrid_svm_svr(X_train, y_train, K)
        y_pred_hybrid = predict_hybrid(X_test, classifiers, regressors, bin_centers)
        jparam_hybrid = calc_jparam(y_test, y_pred_hybrid)

        # E09-5c: Oracle 上限
        oracle_regressors, oracle_bin_edges, oracle_bin_centers = train_oracle_regression(X_train, y_train, K)
        y_pred_oracle = predict_oracle(X_test, y_test, oracle_regressors, oracle_bin_edges, oracle_bin_centers)
        jparam_oracle = calc_jparam(y_test, y_pred_oracle)

        train_time = time.time() - start_time

        # 评估
        metrics_hybrid = evaluate_predictions(y_test, y_pred_hybrid)
        metrics_oracle = evaluate_predictions(y_test, y_pred_oracle)

        # 加载 BP 和 SVM 结果
        bp_summary = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-2a_summary_corrected.csv'))
        svm_summary = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-4b_svm_summary.csv'))

        bp_row = bp_summary[bp_summary['n'] == n].iloc[0]
        svm_row = svm_summary[svm_summary['n'] == n].iloc[0]

        result = {
            'n': n,
            'jparam_bp': bp_row['j_param'],
            'jparam_svm': svm_row['jparam_proba'],
            'jparam_hybrid': jparam_hybrid,
            'jparam_oracle': jparam_oracle,
            'train_time': train_time,
            'failure_rate_hybrid': metrics_hybrid.get('failure_rate', 0),
            'failure_rate_oracle': metrics_oracle.get('failure_rate', 0),
        }

        results.append(result)

        print(f"  BP:     J_param = {bp_row['j_param']:.4f}")
        print(f"  SVM:    J_param = {svm_row['jparam_proba']:.4f}")
        print(f"  Hybrid: J_param = {jparam_hybrid:.4f}")
        print(f"  Oracle: J_param = {jparam_oracle:.4f}")

    # 保存汇总
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, 'E09-5_hybrid_summary.csv'), index=False)

    print("\n" + "="*60)
    print("混合模型汇总：")
    print(results_df.to_string(index=False))

    # 计算相对 BP 的比率
    print("\n相对 BP-raw 的比率：")
    print(f"{'n':>5} {'SVM/BP':>10} {'Hybrid/BP':>12} {'Oracle/BP':>12}")
    print("-" * 45)
    for _, row in results_df.iterrows():
        print(f"{int(row['n']):>5} {row['jparam_svm']/row['jparam_bp']:>10.3f} {row['jparam_hybrid']/row['jparam_bp']:>12.3f} {row['jparam_oracle']/row['jparam_bp']:>12.3f}")


if __name__ == "__main__":
    main()
