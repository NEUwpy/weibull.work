"""
E09-7c 分层分类实验
- 粗分 K1=3 → 细分 K2=3（共 9 个最终分箱）
- 与扁平 K=9、K=10 对比
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


def make_clf():
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            use_label_encoder=False, eval_metric='mlogloss',
            random_state=42, verbosity=0
        ))
    ])


# ============================================================
# 扁平分类（baseline）
# ============================================================

def flat_classify(X_train, y_train, X_test, y_test, param_name, param_idx, K):
    """扁平 K 类分类"""
    bin_edges, bin_centers = create_bins(param_name, K)
    y_discrete = discretize(y_train[:, param_idx], bin_edges)

    clf = make_clf()
    clf.fit(X_train, y_discrete)

    proba = clf.predict_proba(X_test)
    pred = undiscretize_proba(proba, bin_centers)

    y_test_discrete = discretize(y_test[:, param_idx], bin_edges)
    acc = clf.score(X_test, y_test_discrete)

    return pred, acc


# ============================================================
# 分层分类
# ============================================================

def hierarchical_classify(X_train, y_train, X_test, y_test,
                          param_name, param_idx, K1, K2):
    """
    两阶段分层分类：
    第1阶段：粗分 K1 类
    第2阶段：在每个粗分箱内细分 K2 类
    总共 K1*K2 个最终分箱
    """
    low, high = PARAM_RANGES[param_name]

    # 第1阶段：粗分箱
    coarse_edges = np.linspace(low, high, K1 + 1)
    coarse_centers = (coarse_edges[:-1] + coarse_edges[1:]) / 2
    y_coarse = discretize(y_train[:, param_idx], coarse_edges)

    # 训练粗分类器
    coarse_clf = make_clf()
    coarse_clf.fit(X_train, y_coarse)

    # 第2阶段：在每个粗分箱内细分
    fine_clfs = {}
    fine_edges = {}
    fine_centers = {}

    for c in range(K1):
        # 该粗分箱的范围
        c_low = coarse_edges[c]
        c_high = coarse_edges[c + 1]

        # 创建细分箱
        c_edges = np.linspace(c_low, c_high, K2 + 1)
        c_centers = (c_edges[:-1] + c_edges[1:]) / 2
        fine_edges[c] = c_edges
        fine_centers[c] = c_centers

        # 筛选属于该粗分箱的训练样本
        mask = (y_coarse == c)
        if mask.sum() < K2 + 1:
            # 样本太少，跳过训练
            fine_clfs[c] = None
            continue

        X_sub = X_train[mask]
        y_sub_values = y_train[mask, param_idx]
        y_sub_discrete = discretize(y_sub_values, c_edges)

        clf = make_clf()
        clf.fit(X_sub, y_sub_discrete)
        fine_clfs[c] = clf

    # 预测
    coarse_pred = coarse_clf.predict(X_test)
    coarse_proba = coarse_clf.predict_proba(X_test)

    # 最终预测：结合粗分类概率和细分类概率
    # 简化方案：取粗分类最可能的类别，再用该类别的细分类器预测
    K_total = K1 * K2
    total_edges = np.linspace(low, high, K_total + 1)
    total_centers = (total_edges[:-1] + total_edges[1:]) / 2

    # 方法1：硬分配（粗分类决定用哪个细分类器）
    pred_hard = np.zeros(len(X_test))
    for c in range(K1):
        mask = (coarse_pred == c)
        if mask.sum() == 0:
            continue
        if fine_clfs.get(c) is None:
            # 没有细分类器，用粗分箱中心
            pred_hard[mask] = coarse_centers[c]
            continue
        proba = fine_clfs[c].predict_proba(X_test[mask])
        pred_hard[mask] = undiscretize_proba(proba, fine_centers[c])

    # 方法2：软分配（用粗分类概率加权各细分类器的输出）
    pred_soft = np.zeros(len(X_test))
    for c in range(K1):
        if fine_clfs.get(c) is None:
            continue
        proba = fine_clfs[c].predict_proba(X_test)
        fine_pred = undiscretize_proba(proba, fine_centers[c])
        pred_soft += coarse_proba[:, c] * fine_pred

    # 计算准确率（基于最终分箱）
    y_test_discrete = discretize(y_test[:, param_idx], total_edges)
    # 硬分配的准确率
    pred_hard_labels = discretize(pred_hard, total_edges)
    acc_hard = np.mean(pred_hard_labels == y_test_discrete)

    return pred_hard, pred_soft, acc_hard


# ============================================================
# 主实验
# ============================================================

def main():
    print("=" * 60)
    print("E09-7c: 分层分类实验")
    print("=" * 60)

    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]

    # 分层配置：K1=3, K2=3 → 共 9 个最终分箱
    K1, K2 = 3, 3
    K_total = K1 * K2  # 9

    all_results = []

    for n in SAMPLE_SIZES:
        print(f"\n--- 样本量 n = {n} ---")

        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN,
                                    param_seed=42, sample_seed_start=0)
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST,
                                   param_seed=200, sample_seed_start=20000)
        X_train, y_train = prepare_feature_input(df_train, n)
        X_test, y_test = prepare_feature_input(df_test, n)

        # --- 扁平 K=9 ---
        start = time.time()
        flat_preds_9 = []
        flat_accs_9 = []
        for param, idx in zip(params, param_indices):
            pred, acc = flat_classify(X_train, y_train, X_test, y_test,
                                      param, idx, K_total)
            flat_preds_9.append(pred)
            flat_accs_9.append(acc)
        flat_time_9 = time.time() - start
        y_flat_9 = np.column_stack(flat_preds_9)
        err = (y_flat_9 - y_test) / y_test
        err[:, 2] = (y_flat_9[:, 2] - y_test[:, 2]) / y_test[:, 1]
        jparam_flat_9 = np.sqrt(np.mean(err[:, 0]**2 + err[:, 1]**2 + err[:, 2]**2))

        # --- 扁平 K=10 ---
        start = time.time()
        flat_preds_10 = []
        flat_accs_10 = []
        for param, idx in zip(params, param_indices):
            pred, acc = flat_classify(X_train, y_train, X_test, y_test,
                                      param, idx, 10)
            flat_preds_10.append(pred)
            flat_accs_10.append(acc)
        flat_time_10 = time.time() - start
        y_flat_10 = np.column_stack(flat_preds_10)
        err = (y_flat_10 - y_test) / y_test
        err[:, 2] = (y_flat_10[:, 2] - y_test[:, 2]) / y_test[:, 1]
        jparam_flat_10 = np.sqrt(np.mean(err[:, 0]**2 + err[:, 1]**2 + err[:, 2]**2))

        # --- 分层 K1=3, K2=3 ---
        start = time.time()
        hier_hard_preds = []
        hier_soft_preds = []
        hier_accs = []
        for param, idx in zip(params, param_indices):
            pred_hard, pred_soft, acc = hierarchical_classify(
                X_train, y_train, X_test, y_test,
                param, idx, K1, K2
            )
            hier_hard_preds.append(pred_hard)
            hier_soft_preds.append(pred_soft)
            hier_accs.append(acc)
        hier_time = time.time() - start

        y_hier_hard = np.column_stack(hier_hard_preds)
        y_hier_soft = np.column_stack(hier_soft_preds)

        for method_name, y_pred in [('hier_hard', y_hier_hard), ('hier_soft', y_hier_soft)]:
            err = (y_pred - y_test) / y_test
            err[:, 2] = (y_pred[:, 2] - y_test[:, 2]) / y_test[:, 1]
            jparam = np.sqrt(np.mean(err[:, 0]**2 + err[:, 1]**2 + err[:, 2]**2))

            row = {
                'n': n,
                'method': method_name,
                'jparam': jparam,
                'acc_mean': np.mean(hier_accs),
                'acc_beta': hier_accs[0],
                'acc_eta': hier_accs[1],
                'acc_gamma': hier_accs[2],
                'time': hier_time,
            }
            all_results.append(row)

        # 添加扁平结果
        for method_name, jparam, accs, tm in [
            ('flat_K9', jparam_flat_9, flat_accs_9, flat_time_9),
            ('flat_K10', jparam_flat_10, flat_accs_10, flat_time_10),
        ]:
            row = {
                'n': n,
                'method': method_name,
                'jparam': jparam,
                'acc_mean': np.mean(accs),
                'acc_beta': accs[0],
                'acc_eta': accs[1],
                'acc_gamma': accs[2],
                'time': tm,
            }
            all_results.append(row)

        # 计算分层 J_param 用于打印
        err_h = (y_hier_hard - y_test) / y_test
        err_h[:, 2] = (y_hier_hard[:, 2] - y_test[:, 2]) / y_test[:, 1]
        jparam_hier_hard = np.sqrt(np.mean(err_h[:, 0]**2 + err_h[:, 1]**2 + err_h[:, 2]**2))
        err_s = (y_hier_soft - y_test) / y_test
        err_s[:, 2] = (y_hier_soft[:, 2] - y_test[:, 2]) / y_test[:, 1]
        jparam_hier_soft = np.sqrt(np.mean(err_s[:, 0]**2 + err_s[:, 1]**2 + err_s[:, 2]**2))

        print(f"  flat K=9:   J={jparam_flat_9:.4f}  acc={np.mean(flat_accs_9):.3f}")
        print(f"  flat K=10:  J={jparam_flat_10:.4f}  acc={np.mean(flat_accs_10):.3f}")
        print(f"  hier hard:  J={jparam_hier_hard:.4f}  acc={np.mean(hier_accs):.3f}")
        print(f"  hier soft:  J={jparam_hier_soft:.4f}")

    # 保存
    df_results = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, 'E09-7c_hierarchical_compare.csv')
    df_results.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总：J_param 对比")
    print("=" * 60)
    pivot = df_results.pivot_table(index='n', columns='method', values='jparam')
    print(pivot.to_string(float_format='%.4f'))

    return df_results


if __name__ == "__main__":
    main()
