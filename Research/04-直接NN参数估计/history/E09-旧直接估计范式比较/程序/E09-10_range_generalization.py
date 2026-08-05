"""
E09-10 跨参数范围泛化实验
- 10a: 范围扩展测试（训练范围不变，测试范围扩大）
- 10b: 范围收缩测试（训练范围不变，测试范围缩小）
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
    PARAM_RANGES,
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


def generate_dataset_custom_ranges(n_configs, n_samples, n_repeats, param_ranges,
                                    param_seed, sample_seed_start):
    """用自定义参数范围生成数据集"""
    rng = np.random.RandomState(param_seed)
    configs = []
    for _ in range(n_configs):
        beta = rng.uniform(*param_ranges['beta'])
        eta = rng.uniform(*param_ranges['eta'])
        gamma = rng.uniform(*param_ranges['gamma'])
        configs.append((beta, eta, gamma))

    from common import generate_weibull_sample
    rows = []
    for cfg_idx, (beta, eta, gamma) in enumerate(configs):
        for rep in range(n_repeats):
            seed = sample_seed_start + cfg_idx * n_repeats + rep
            sample = generate_weibull_sample(beta, eta, gamma, n_samples, seed=seed)
            row = {'beta': beta, 'eta': eta, 'gamma': gamma,
                   'config_id': cfg_idx, 'repeat': rep}
            for j, x in enumerate(sample):
                row[f'x{j+1}'] = x
            rows.append(row)
    return pd.DataFrame(rows)


def test_model_on_data(trainer, df_test, n_samples):
    """在指定数据上测试模型"""
    X_test, y_test = prepare_feature_input(df_test, n_samples)
    y_pred = trainer.predict(X_test)
    jparam = calc_jparam(y_test, y_pred)

    # 逐参数
    err_beta = (y_pred[:, 0] - y_test[:, 0]) / y_test[:, 0]
    err_eta = (y_pred[:, 1] - y_test[:, 1]) / y_test[:, 1]
    err_gamma = (y_pred[:, 2] - y_test[:, 2]) / y_test[:, 1]
    rmse_beta = np.sqrt(np.mean(err_beta**2))
    rmse_eta = np.sqrt(np.mean(err_eta**2))
    rmse_gamma = np.sqrt(np.mean(err_gamma**2))

    return jparam, rmse_beta, rmse_eta, rmse_gamma


def main():
    print("=" * 60)
    print("E09-10: 跨参数范围泛化实验")
    print("=" * 60)

    # 使用 n=20 作为代表样本量
    n = 20
    model_path = os.path.join(MODEL_DIR, f"E09-2b_bp_feature_n{n}.pt")
    trainer = create_bp_feature_model()
    trainer.load(model_path)
    print(f"加载模型: n={n}")

    # 基准范围
    base_ranges = PARAM_RANGES.copy()
    print(f"基准范围: β∈{base_ranges['beta']}, η∈{base_ranges['eta']}, γ∈{base_ranges['gamma']}")

    # --- 10a: 范围扩展测试 ---
    print("\n" + "=" * 60)
    print("10a: 范围扩展测试")
    print("=" * 60)

    extension_scenarios = {
        '基准': base_ranges,
        'β扩展[1,6]': {**base_ranges, 'beta': (1.0, 6.0)},
        'η扩展[0.5,6]': {**base_ranges, 'eta': (0.5, 6.0)},
        'γ扩展[0,2.5]': {**base_ranges, 'gamma': (0.0, 2.5)},
        '全部扩展': {'beta': (1.0, 6.0), 'eta': (0.5, 6.0), 'gamma': (0.0, 2.5)},
    }

    results_ext = []
    for name, ranges in extension_scenarios.items():
        df_test = generate_dataset_custom_ranges(
            N_CONFIGS_TEST, n, N_REPEATS_TEST, ranges,
            param_seed=200, sample_seed_start=20000)
        jparam, rmse_b, rmse_e, rmse_g = test_model_on_data(trainer, df_test, n)
        results_ext.append({
            'scenario': name,
            'jparam': jparam,
            'rmse_beta': rmse_b,
            'rmse_eta': rmse_e,
            'rmse_gamma': rmse_g,
        })
        print(f"  {name:20s}  J={jparam:.4f}  β={rmse_b:.4f}  η={rmse_e:.4f}  γ={rmse_g:.4f}")

    df_ext = pd.DataFrame(results_ext)

    # --- 10b: 范围收缩测试 ---
    print("\n" + "=" * 60)
    print("10b: 范围收缩测试")
    print("=" * 60)

    contraction_scenarios = {
        '基准': base_ranges,
        'β收缩[2,4]': {**base_ranges, 'beta': (2.0, 4.0)},
        'η收缩[1,4]': {**base_ranges, 'eta': (1.0, 4.0)},
        'γ收缩[0.5,1.5]': {**base_ranges, 'gamma': (0.5, 1.5)},
        '全部收缩': {'beta': (2.0, 4.0), 'eta': (1.0, 4.0), 'gamma': (0.5, 1.5)},
    }

    results_con = []
    for name, ranges in contraction_scenarios.items():
        df_test = generate_dataset_custom_ranges(
            N_CONFIGS_TEST, n, N_REPEATS_TEST, ranges,
            param_seed=200, sample_seed_start=20000)
        jparam, rmse_b, rmse_e, rmse_g = test_model_on_data(trainer, df_test, n)
        results_con.append({
            'scenario': name,
            'jparam': jparam,
            'rmse_beta': rmse_b,
            'rmse_eta': rmse_e,
            'rmse_gamma': rmse_g,
        })
        print(f"  {name:20s}  J={jparam:.4f}  β={rmse_b:.4f}  η={rmse_e:.4f}  γ={rmse_g:.4f}")

    df_con = pd.DataFrame(results_con)

    # 保存
    df_all = pd.concat([df_ext, df_con], keys=['扩展', '收缩'])
    df_all.to_csv(os.path.join(OUTPUT_DIR, 'E09-10_range_generalization.csv'))

    # 多样本量测试
    print("\n" + "=" * 60)
    print("10a 补充：多样本量下的范围扩展")
    print("=" * 60)

    results_multi = []
    for n in SAMPLE_SIZES:
        model_path = os.path.join(MODEL_DIR, f"E09-2b_bp_feature_n{n}.pt")
        if not os.path.exists(model_path):
            continue
        trainer_n = create_bp_feature_model()
        trainer_n.load(model_path)

        for name, ranges in [('基准', base_ranges), ('全部扩展', extension_scenarios['全部扩展'])]:
            df_test = generate_dataset_custom_ranges(
                N_CONFIGS_TEST, n, N_REPEATS_TEST, ranges,
                param_seed=200, sample_seed_start=20000)
            jparam, rmse_b, rmse_e, rmse_g = test_model_on_data(trainer_n, df_test, n)
            results_multi.append({
                'n': n,
                'scenario': name,
                'jparam': jparam,
                'rmse_beta': rmse_b,
                'rmse_eta': rmse_e,
                'rmse_gamma': rmse_g,
            })

    df_multi = pd.DataFrame(results_multi)
    df_multi.to_csv(os.path.join(OUTPUT_DIR, 'E09-10b_multi_n_range.csv'), index=False)

    print(f"\n{'n':>5} {'场景':>10} {'J_param':>10} {'β_RMSE':>10} {'η_RMSE':>10} {'γ_RMSE':>10}")
    print("-" * 60)
    for _, row in df_multi.iterrows():
        print(f"{int(row['n']):>5} {row['scenario']:>10} {row['jparam']:>10.4f} "
              f"{row['rmse_beta']:>10.4f} {row['rmse_eta']:>10.4f} {row['rmse_gamma']:>10.4f}")

    return df_ext, df_con, df_multi


if __name__ == "__main__":
    main()
