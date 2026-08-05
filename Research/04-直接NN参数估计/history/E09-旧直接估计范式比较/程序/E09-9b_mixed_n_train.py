"""
E09-9b 混合样本量训练
- 合并所有样本量的训练数据，训练一个统一模型
- 与各单样本量模型对比
"""

import sys
import os
import time
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
N_CONFIGS_TRAIN = 500
N_CONFIGS_VAL = 100
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_VAL = 4
N_REPEATS_TEST = 5
EPOCHS = 200
BATCH_SIZE = 64
PATIENCE = 30

MODEL_DIR = os.path.join(SCRIPT_DIR, ".")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def calc_jparam(y_true, y_pred):
    err_beta = (y_pred[:, 0] - y_true[:, 0]) / y_true[:, 0]
    err_eta = (y_pred[:, 1] - y_true[:, 1]) / y_true[:, 1]
    err_gamma = (y_pred[:, 2] - y_true[:, 2]) / y_true[:, 1]
    return np.sqrt(np.mean(err_beta**2 + err_eta**2 + err_gamma**2))


def main():
    print("=" * 60)
    print("E09-9b: 混合样本量训练")
    print("=" * 60)

    # 1. 合并所有样本量的训练数据
    print("\n生成混合训练数据...")
    X_train_all = []
    y_train_all = []
    X_val_all = []
    y_val_all = []

    for n in SAMPLE_SIZES:
        df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN,
                                    param_seed=42, sample_seed_start=0)
        df_val = generate_dataset(N_CONFIGS_VAL, n, N_REPEATS_VAL,
                                  param_seed=100, sample_seed_start=10000)
        X_tr, y_tr = prepare_feature_input(df_train, n)
        X_va, y_va = prepare_feature_input(df_val, n)
        X_train_all.append(X_tr)
        y_train_all.append(y_tr)
        X_val_all.append(X_va)
        y_val_all.append(y_va)
        print(f"  n={n}: train={X_tr.shape}, val={X_va.shape}")

    X_train = np.vstack(X_train_all)
    y_train = np.vstack(y_train_all)
    X_val = np.vstack(X_val_all)
    y_val = np.vstack(y_val_all)
    print(f"合并后: train={X_train.shape}, val={X_val.shape}")

    # 2. 训练统一模型
    trainer = create_bp_feature_model(hidden_dims=[64, 32], lr=1e-3, dropout=0.1)
    start = time.time()
    history = trainer.train(X_train, y_train, X_val, y_val,
                           epochs=EPOCHS, batch_size=BATCH_SIZE,
                           patience=PATIENCE, verbose=True)
    train_time = time.time() - start
    print(f"训练耗时: {train_time:.1f}s")

    # 保存模型
    model_path = os.path.join(MODEL_DIR, "E09-9b_mixed_n_model.pt")
    trainer.save(model_path)
    print(f"模型已保存: {model_path}")

    # 3. 在各样本量测试集上测试
    print("\n" + "=" * 60)
    print("混合模型在各样本量测试集上的表现")
    print("=" * 60)

    results = []
    for n in SAMPLE_SIZES:
        df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST,
                                   param_seed=200, sample_seed_start=20000)
        X_test, y_test = prepare_feature_input(df_test, n)
        y_pred = trainer.predict(X_test)
        jparam = calc_jparam(y_test, y_pred)

        # 加载单样本量模型对比
        single_model_path = os.path.join(MODEL_DIR, f"E09-2b_bp_feature_n{n}.pt")
        single_trainer = create_bp_feature_model()
        single_trainer.load(single_model_path)
        y_pred_single = single_trainer.predict(X_test)
        jparam_single = calc_jparam(y_test, y_pred_single)

        ratio = jparam / jparam_single
        results.append({
            'n': n,
            'jparam_mixed': jparam,
            'jparam_single': jparam_single,
            'ratio': ratio,
        })
        print(f"  n={n:>2}: 混合={jparam:.4f}  单n={jparam_single:.4f}  "
              f"比值={ratio:.3f}  {'混合更优' if ratio < 1 else '单n更优'}")

    # 保存
    df_results = pd.DataFrame(results)
    df_results.to_csv(os.path.join(OUTPUT_DIR, 'E09-9b_mixed_n_compare.csv'), index=False)

    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    print(df_results.to_string(index=False, float_format='%.4f'))

    avg_ratio = df_results['ratio'].mean()
    print(f"\n平均比值: {avg_ratio:.3f} ({'混合更优' if avg_ratio < 1 else '单n更优'})")

    return df_results


if __name__ == "__main__":
    main()
