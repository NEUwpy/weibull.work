"""
E09-7e 增强特征实验
- 扩展统计特征维度，测试分类是否能突破信息瓶颈
- 对比原始 12 维 vs 增强特征集
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
K = 10

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 增强特征提取
# ============================================================

def extract_features_original(x):
    """原始 12 维特征"""
    x = np.sort(x)
    n = len(x)
    mean = np.mean(x)
    std = np.std(x, ddof=1) if n > 1 else 0.0
    xmin, xmax = x[0], x[-1]
    rng = xmax - xmin
    q25 = np.percentile(x, 25)
    q50 = np.percentile(x, 50)
    q75 = np.percentile(x, 75)
    iqr = q75 - q25
    if n > 2 and std > 0:
        z = (x - mean) / std
        skew = np.mean(z ** 3)
        kurt = np.mean(z ** 4) - 3.0
    else:
        skew = 0.0
        kurt = 0.0
    cv = std / mean if mean > 0 else 0.0
    return np.array([mean, std, xmin, xmax, rng, q25, q50, q75, iqr, skew, kurt, cv])


def extract_features_enhanced(x):
    """增强特征集：在原始基础上扩展到 ~30 维"""
    x = np.sort(x)
    n = len(x)

    # --- 基础统计量（与原始相同）---
    mean = np.mean(x)
    std = np.std(x, ddof=1) if n > 1 else 0.0
    xmin, xmax = x[0], x[-1]
    rng = xmax - xmin
    q25 = np.percentile(x, 25)
    q50 = np.percentile(x, 50)
    q75 = np.percentile(x, 75)
    iqr = q75 - q25
    if n > 2 and std > 0:
        z = (x - mean) / std
        skew = np.mean(z ** 3)
        kurt = np.mean(z ** 4) - 3.0
    else:
        skew = 0.0
        kurt = 0.0
    cv = std / mean if mean > 0 else 0.0

    basic = [mean, std, xmin, xmax, rng, q25, q50, q75, iqr, skew, kurt, cv]

    # --- 更多分位数 ---
    q10 = np.percentile(x, 10)
    q20 = np.percentile(x, 20)
    q30 = np.percentile(x, 30)
    q40 = np.percentile(x, 40)
    q60 = np.percentile(x, 60)
    q70 = np.percentile(x, 70)
    q80 = np.percentile(x, 80)
    q90 = np.percentile(x, 90)
    quantiles = [q10, q20, q30, q40, q60, q70, q80, q90]

    # --- 分位数间距（捕获分布形状）---
    q_ratios = [
        q90 - q10,    # 90% range
        q80 - q20,    # 80% range
        q70 - q30,    # 60% range
        q75 / q25 if q25 > 0 else 0,  # IQR ratio
    ]

    # --- 顺序统计量（小样本时比百分位数更精确）---
    order_stats = []
    if n >= 3:
        order_stats.append(x[1])      # 2nd smallest
    if n >= 5:
        order_stats.append(x[-2])     # 2nd largest
        order_stats.append(x[n // 4]) # ~25th percentile by rank
        order_stats.append(x[3 * n // 4])  # ~75th percentile by rank

    # --- 截尾均值（抗异常值）---
    trim_frac = 0.1
    n_trim = max(1, int(n * trim_frac))
    trimmed_mean = np.mean(x[n_trim:-n_trim]) if n > 2 * n_trim else mean

    # --- 对数统计量（Weibull 样本常取对数后更对称）---
    if xmin > 0:
        log_x = np.log(x)
        log_mean = np.mean(log_x)
        log_std = np.std(log_x, ddof=1) if n > 1 else 0.0
    else:
        log_mean = 0.0
        log_std = 0.0

    # --- MAD（中位数绝对偏差，鲁棒）---
    mad = np.median(np.abs(x - q50))

    # --- 变异系数的补充 ---
    iqr_ratio = iqr / q50 if q50 > 0 else 0  # IQR / median

    extra = quantiles + q_ratios + order_stats + [trimmed_mean, log_mean, log_std, mad, iqr_ratio]

    return np.array(basic + extra)


def prepare_enhanced_features(df, n_samples):
    """用增强特征替代原始特征"""
    x_cols = [f"x{i+1}" for i in range(n_samples)]
    samples = df[x_cols].values
    X = np.array([extract_features_enhanced(s) for s in samples])
    y = df[["beta", "eta", "gamma"]].values
    return X, y


# ============================================================
# Fisher 比分析
# ============================================================

def compute_fisher_ratios(X, y, params, param_indices, K):
    """计算各参数的 Fisher 判别比"""
    from sklearn.preprocessing import StandardScaler
    X_scaled = StandardScaler().fit_transform(X)
    results = {}
    for param, idx in zip(params, param_indices):
        low, high = PARAM_RANGES[param]
        edges = np.linspace(low, high, K + 1)
        labels = np.digitize(y[:, idx], edges[1:-1])
        centers = []
        within_vars = []
        for c in range(K):
            mask = (labels == c)
            if mask.sum() < 2:
                continue
            centers.append(X_scaled[mask].mean(axis=0))
            within_vars.append(X_scaled[mask].var(axis=0).mean())
        centers = np.array(centers)
        between_var = centers.var(axis=0).mean()
        within_var = np.mean(within_vars)
        results[param] = between_var / within_var if within_var > 0 else 0
    return results


# ============================================================
# 分类实验
# ============================================================

def run_classification(X_train, y_train, X_test, y_test, params, param_indices, K):
    """训练 XGBoost 分类器并返回结果"""
    bin_edges_dict = {}
    bin_centers_dict = {}
    classifiers = {}

    start = time.time()
    for param, idx in zip(params, param_indices):
        low, high = PARAM_RANGES[param]
        bin_edges = np.linspace(low, high, K + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_edges_dict[param] = bin_edges
        bin_centers_dict[param] = bin_centers

        y_discrete = np.digitize(y_train[:, idx], bin_edges[1:-1])
        clf = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1,
                                  random_state=42, verbosity=0, eval_metric='mlogloss',
                                  use_label_encoder=False))
        ])
        clf.fit(X_train, y_discrete)
        classifiers[param] = clf
    elapsed = time.time() - start

    # 预测
    proba_preds = []
    accs = []
    for param, idx in zip(params, param_indices):
        proba = classifiers[param].predict_proba(X_test)
        pred = np.dot(proba, bin_centers_dict[param])
        proba_preds.append(pred)

        y_test_discrete = np.digitize(y_test[:, idx], bin_edges_dict[param])
        acc = classifiers[param].score(X_test, y_test_discrete)
        accs.append(acc)

    y_pred = np.column_stack(proba_preds)
    err_beta = (y_pred[:, 0] - y_test[:, 0]) / y_test[:, 0]
    err_eta = (y_pred[:, 1] - y_test[:, 1]) / y_test[:, 1]
    err_gamma = (y_pred[:, 2] - y_test[:, 2]) / y_test[:, 1]
    jparam = np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))

    return jparam, accs, elapsed


# ============================================================
# 主实验
# ============================================================

def main():
    print("=" * 60)
    print("E09-7e: 增强特征实验")
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

        # 原始特征
        X_train_orig, y_train = prepare_feature_input(df_train, n)
        X_test_orig, y_test = prepare_feature_input(df_test, n)

        # 增强特征
        X_train_enh, _ = prepare_enhanced_features(df_train, n)
        X_test_enh, _ = prepare_enhanced_features(df_test, n)

        print(f"  原始特征: {X_train_orig.shape[1]} 维")
        print(f"  增强特征: {X_train_enh.shape[1]} 维")

        # Fisher 比对比
        fisher_orig = compute_fisher_ratios(X_train_orig, y_train, params, param_indices, K)
        fisher_enh = compute_fisher_ratios(X_train_enh, y_train, params, param_indices, K)

        print(f"\n  Fisher 比对比:")
        for p in params:
            print(f"    {p}: 原始={fisher_orig[p]:.4f}  增强={fisher_enh[p]:.4f}  "
                  f"提升={fisher_enh[p]/fisher_orig[p]:.2f}x")

        # 分类对比
        jparam_orig, accs_orig, t_orig = run_classification(
            X_train_orig, y_train, X_test_orig, y_test, params, param_indices, K)
        jparam_enh, accs_enh, t_enh = run_classification(
            X_train_enh, y_train, X_test_enh, y_test, params, param_indices, K)

        print(f"\n  分类结果:")
        print(f"    原始: J={jparam_orig:.4f}  acc={[f'{a:.3f}' for a in accs_orig]}  ({t_orig:.1f}s)")
        print(f"    增强: J={jparam_enh:.4f}  acc={[f'{a:.3f}' for a in accs_enh]}  ({t_enh:.1f}s)")
        print(f"    改善: {(1 - jparam_enh/jparam_orig)*100:.1f}%")

        for feat_name, jparam, accs, fisher, tm in [
            ('original_12', jparam_orig, accs_orig, fisher_orig, t_orig),
            ('enhanced', jparam_enh, accs_enh, fisher_enh, t_enh),
        ]:
            row = {
                'n': n,
                'features': feat_name,
                'n_features': X_train_orig.shape[1] if feat_name == 'original_12' else X_train_enh.shape[1],
                'jparam': jparam,
                'acc_mean': np.mean(accs),
                'acc_beta': accs[0],
                'acc_eta': accs[1],
                'acc_gamma': accs[2],
                'fisher_beta': fisher['beta'],
                'fisher_eta': fisher['eta'],
                'fisher_gamma': fisher['gamma'],
                'time': tm,
            }
            all_results.append(row)

    # 保存
    df_results = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, 'E09-7e_enhanced_features.csv')
    df_results.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总：J_param 对比")
    print("=" * 60)
    pivot = df_results.pivot_table(index='n', columns='features', values='jparam')
    print(pivot.to_string(float_format='%.4f'))

    print("\n" + "=" * 60)
    print("汇总：平均准确率")
    print("=" * 60)
    pivot_acc = df_results.pivot_table(index='n', columns='features', values='acc_mean')
    print(pivot_acc.to_string(float_format='%.3f'))

    print("\n" + "=" * 60)
    print("汇总：Fisher 比（gamma）")
    print("=" * 60)
    pivot_fisher = df_results.pivot_table(index='n', columns='features', values='fisher_gamma')
    print(pivot_fisher.to_string(float_format='%.4f'))

    return df_results


if __name__ == "__main__":
    main()
