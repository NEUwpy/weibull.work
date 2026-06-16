"""
E09-4 SVM 分类实验
- E09-4a: 分箱方案与离散化误差下界
- E09-4b: SVM 逐参数分类
- E09-4c: 类别中心 / 概率加权还原参数
- E09-4d: SVM vs BP 对比
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import pickle
from sklearn.svm import SVC
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


# ============================================================
# 配置
# ============================================================

N_CONFIGS_TRAIN = 500
N_CONFIGS_VAL = 100
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_VAL = 4
N_REPEATS_TEST = 5

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
MODEL_DIR = os.path.join(SCRIPT_DIR, ".")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 分箱数候选
K_CANDIDATES = [5, 10, 20]


# ============================================================
# 分箱工具
# ============================================================

def create_bins(param_name, n_bins):
    """创建等距分箱边界和类别中心"""
    low, high = PARAM_RANGES[param_name]
    bin_edges = np.linspace(low, high, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    return bin_edges, bin_centers


def discretize(values, bin_edges):
    """将连续值离散化为类别标签"""
    # 将值分配到对应的 bin
    labels = np.digitize(values, bin_edges[1:-1])  # 0-indexed
    return labels


def undiscretize(labels, bin_centers):
    """将类别标签还原为参数值（类别中心法）"""
    return bin_centers[labels]


def undiscretize_proba(proba, bin_centers):
    """将概率输出还原为参数值（概率加权法）"""
    return np.dot(proba, bin_centers)


# ============================================================
# 离散化误差下界
# ============================================================

def compute_discretization_error(y_true, bin_edges, bin_centers, param_idx=0):
    """计算离散化误差下界（完美分类时的最小误差）"""
    values = y_true[:, param_idx]
    labels = discretize(values, bin_edges)
    reconstructed = undiscretize(labels, bin_centers)
    errors = (reconstructed - values) / values  # 相对误差
    return np.sqrt(np.mean(errors ** 2))  # RMSE


def E09_4a_discretization_bounds():
    """E09-4a: 分箱方案与离散化误差下界"""
    print("\n" + "="*60)
    print("E09-4a: 分箱方案与离散化误差下界")
    print("="*60)

    # 生成测试数据
    df_test = generate_dataset(N_CONFIGS_TEST, 10, N_REPEATS_TEST, param_seed=200, sample_seed_start=20000)
    _, y_test = prepare_feature_input(df_test, n_samples=10)

    rows = []
    params = ['beta', 'eta', 'gamma']
    param_indices = [0, 1, 2]

    for k in K_CANDIDATES:
        row = {'K': k}
        for param, idx in zip(params, param_indices):
            bin_edges, bin_centers = create_bins(param, k)
            rmse = compute_discretization_error(y_test, bin_edges, bin_centers, idx)
            row[f'bound_{param}'] = rmse
        row['bound_jparam'] = np.sqrt(row['bound_beta']**2 + row['bound_eta']**2 + row['bound_gamma']**2)
        rows.append(row)

    bounds_df = pd.DataFrame(rows)
    print("\n离散化误差下界（完美分类时）：")
    print(bounds_df.to_string(index=False))

    bounds_df.to_csv(os.path.join(OUTPUT_DIR, 'E09-4a_discretization_bounds.csv'), index=False)
    return bounds_df


# ============================================================
# SVM 训练
# ============================================================

def train_svm_classifier(X_train, y_train, n_bins, param_name):
    """训练单个 SVM 分类器"""
    bin_edges, _ = create_bins(param_name, n_bins)
    y_discrete = discretize(y_train, bin_edges)

    # 创建 SVM pipeline（含标准化）
    svmPipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('svm', SVC(kernel='rbf', probability=True, random_state=42))
    ])

    svmPipeline.fit(X_train, y_discrete)
    return svmPipeline, bin_edges


def predict_svm(svm_pipeline, X, bin_centers):
    """SVM 预测（类别中心法 + 概率加权法）"""
    # 类别预测
    labels = svm_pipeline.predict(X)
    center_pred = bin_centers[labels]

    # 概率预测
    proba = svm_pipeline.predict_proba(X)
    proba_pred = undiscretize_proba(proba, bin_centers)

    return center_pred, proba_pred


def E09_4b_train_svm():
    """E09-4b: 训练 SVM 分类器"""
    print("\n" + "="*60)
    print("E09-4b: SVM 逐参数分类训练")
    print("="*60)

    results = []

    for n in SAMPLE_SIZES:
        print(f"\n--- 样本量 n = {n} ---")

        # 生成数据
        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN, param_seed=42, sample_seed_start=0)
        df_val = generate_dataset(N_CONFIGS_VAL, n, N_REPEATS_VAL, param_seed=100, sample_seed_start=10000)
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST, param_seed=200, sample_seed_start=20000)

        X_train, y_train = prepare_feature_input(df_train, n)
        X_val, y_val = prepare_feature_input(df_val, n)
        X_test, y_test = prepare_feature_input(df_test, n)

        # 选择最佳分箱数（用 K=10 作为默认）
        K = 10

        # 训练三个 SVM
        params = ['beta', 'eta', 'gamma']
        param_indices = [0, 1, 2]
        svm_models = {}
        bin_edges_dict = {}
        bin_centers_dict = {}

        start_time = time.time()
        for param, idx in zip(params, param_indices):
            svm_pipeline, bin_edges = train_svm_classifier(X_train, y_train[:, idx], K, param)
            svm_models[param] = svm_pipeline
            bin_edges_dict[param] = bin_edges
            _, bin_centers = create_bins(param, K)
            bin_centers_dict[param] = bin_centers

            # 计算训练准确率
            train_acc = svm_pipeline.score(X_train, discretize(y_train[:, idx], bin_edges))
            val_acc = svm_pipeline.score(X_val, discretize(y_val[:, idx], bin_edges))
            print(f"  {param}: train_acc={train_acc:.3f}, val_acc={val_acc:.3f}")

        train_time = time.time() - start_time

        # 测试：类别中心法
        center_preds = []
        proba_preds = []
        for param in params:
            center_pred, proba_pred = predict_svm(svm_models[param], X_test, bin_centers_dict[param])
            center_preds.append(center_pred)
            proba_preds.append(proba_pred)

        y_pred_center = np.column_stack(center_preds)
        y_pred_proba = np.column_stack(proba_preds)

        # 评估
        metrics_center = evaluate_predictions(y_test, y_pred_center)
        metrics_proba = evaluate_predictions(y_test, y_pred_proba)

        # 计算 J_param
        def calc_jparam(y_true, y_pred):
            err_beta = (y_pred[:, 0] - y_true[:, 0]) / y_true[:, 0]
            err_eta = (y_pred[:, 1] - y_true[:, 1]) / y_true[:, 1]
            err_gamma = (y_pred[:, 2] - y_true[:, 2]) / y_true[:, 1]
            return np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))

        jparam_center = calc_jparam(y_test, y_pred_center)
        jparam_proba = calc_jparam(y_test, y_pred_proba)

        result = {
            'n': n,
            'K': K,
            'train_time': train_time,
            'jparam_center': jparam_center,
            'jparam_proba': jparam_proba,
            'failure_rate_center': metrics_center.get('failure_rate', 0),
            'failure_rate_proba': metrics_proba.get('failure_rate', 0),
        }

        # 各参数 RMSE
        for param in params:
            if param in metrics_center.get('param_standard', {}):
                result[f'rmse_{param}_center'] = metrics_center['param_standard'][param].get('absolute', {}).get('rmse')
            if param in metrics_proba.get('param_standard', {}):
                result[f'rmse_{param}_proba'] = metrics_proba['param_standard'][param].get('absolute', {}).get('rmse')

        results.append(result)

        # 保存模型
        model_path = os.path.join(MODEL_DIR, f'E09-4_svm_n{n}.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump({
                'models': svm_models,
                'bin_edges': bin_edges_dict,
                'bin_centers': bin_centers_dict,
                'K': K,
            }, f)
        print(f"  模型已保存: {model_path}")

    # 保存汇总
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, 'E09-4b_svm_summary.csv'), index=False)

    print("\n" + "="*60)
    print("SVM 分类汇总：")
    print(results_df[['n', 'K', 'jparam_center', 'jparam_proba', 'train_time']].to_string(index=False))

    return results_df


# ============================================================
# SVM vs BP 对比
# ============================================================

def E09_4d_comparison():
    """E09-4d: SVM vs BP 对比"""
    print("\n" + "="*60)
    print("E09-4d: SVM vs BP 对比")
    print("="*60)

    # 加载 SVM 结果
    svm_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-4b_svm_summary.csv'))

    # 加载 BP 结果
    bp_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-2a_summary_corrected.csv'))

    # 对比表格
    print("\nJ_param 对比 (SVM vs BP-raw):")
    print(f"{'n':>5} {'SVM-center':>12} {'SVM-proba':>12} {'BP-raw':>12} {'SVM/BA BP':>12}")
    print("-" * 60)

    for _, svm_row in svm_df.iterrows():
        n = svm_row['n']
        bp_row = bp_df[bp_df['n'] == n].iloc[0]
        ratio = svm_row['jparam_proba'] / bp_row['j_param']
        print(f"{int(n):>5} {svm_row['jparam_center']:>12.4f} {svm_row['jparam_proba']:>12.4f} {bp_row['j_param']:>12.4f} {ratio:>12.2f}")

    # 保存对比
    comparison = pd.DataFrame({
        'n': svm_df['n'],
        'svm_jparam_center': svm_df['jparam_center'],
        'svm_jparam_proba': svm_df['jparam_proba'],
        'bp_jparam': bp_df['j_param'],
        'ratio': svm_df['jparam_proba'] / bp_df['j_param'],
    })
    comparison.to_csv(os.path.join(OUTPUT_DIR, 'E09-4d_comparison.csv'), index=False)

    return comparison


# ============================================================
# 主函数
# ============================================================

def main():
    print("="*60)
    print("E09-4 SVM 分类实验")
    print("="*60)

    # E09-4a: 离散化误差下界
    E09_4a_discretization_bounds()

    # E09-4b: SVM 训练
    E09_4b_train_svm()

    # E09-4d: 对比
    E09_4d_comparison()

    print("\nDone!")


if __name__ == "__main__":
    main()
