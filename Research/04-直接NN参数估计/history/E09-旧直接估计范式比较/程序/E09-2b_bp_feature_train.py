"""
E09-2b BP-feature 训练脚本
对每个样本量训练一个 BP 网络（统计特征输入）
"""

import sys
import os
import time
import numpy as np
import pandas as pd

# 添加路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

from common import (
    generate_dataset,
    prepare_feature_input,
    evaluate_predictions,
    get_feature_dim,
    SAMPLE_SIZES,
)
from bp_model import create_bp_feature_model


# ============================================================
# 配置
# ============================================================

N_CONFIGS_TRAIN = 500
N_CONFIGS_VAL = 100
N_CONFIGS_TEST = 100
N_REPEATS_TRAIN = 4
N_REPEATS_VAL = 4
N_REPEATS_TEST = 5

EPOCHS = 200
BATCH_SIZE = 64
PATIENCE = 30

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
MODEL_DIR = os.path.join(SCRIPT_DIR, ".")


def train_single_n(n: int) -> dict:
    """对单个样本量进行训练和测试（使用统计特征输入）。"""

    print(f"\n{'='*60}")
    print(f"样本量 n = {n} (特征输入)")
    print(f"{'='*60}")

    # 1. 生成数据
    print("生成训练数据...")
    df_train = generate_dataset(N_CONFIGS_TRAIN, n, N_REPEATS_TRAIN, param_seed=42, sample_seed_start=0)
    df_val = generate_dataset(N_CONFIGS_VAL, n, N_REPEATS_VAL, param_seed=100, sample_seed_start=10000)
    df_test = generate_dataset(N_CONFIGS_TEST, n, N_REPEATS_TEST, param_seed=200, sample_seed_start=20000)

    X_train, y_train = prepare_feature_input(df_train, n)
    X_val, y_val = prepare_feature_input(df_val, n)
    X_test, y_test = prepare_feature_input(df_test, n)

    print(f"  特征维度: {X_train.shape[1]}")
    print(f"  训练集: {X_train.shape}")
    print(f"  验证集: {X_val.shape}")
    print(f"  测试集: {X_test.shape}")

    # 2. 创建模型
    trainer = create_bp_feature_model(
        n_features=get_feature_dim(),
        hidden_dims=[64, 32],
        lr=1e-3,
        dropout=0.1,
    )

    # 3. 训练
    print("开始训练...")
    start_time = time.time()
    history = trainer.train(
        X_train, y_train,
        X_val, y_val,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        patience=PATIENCE,
        verbose=True,
    )
    train_time = time.time() - start_time
    print(f"训练耗时: {train_time:.1f}s")

    # 4. 测试
    print("测试中...")
    y_pred = trainer.predict(X_test)
    metrics = evaluate_predictions(y_test, y_pred)

    # 5. 保存模型
    model_path = os.path.join(MODEL_DIR, f"E09-2b_bp_feature_n{n}.pt")
    trainer.save(model_path)
    print(f"模型已保存: {model_path}")

    # 6. 保存训练历史
    history_df = pd.DataFrame(history)
    history_df.to_csv(os.path.join(OUTPUT_DIR, f"E09-2b_history_n{n}.csv"), index=False)

    # 7. 保存测试结果
    test_results = pd.DataFrame({
        "beta_true": y_test[:, 0],
        "eta_true": y_test[:, 1],
        "gamma_true": y_test[:, 2],
        "beta_pred": y_pred[:, 0],
        "eta_pred": y_pred[:, 1],
        "gamma_pred": y_pred[:, 2],
    })
    test_results.to_csv(os.path.join(OUTPUT_DIR, f"E09-2b_test_n{n}.csv"), index=False)

    # 8. 汇总指标
    summary = {
        "n": n,
        "train_time": train_time,
        "n_epochs": len(history["train_loss"]),
        "final_train_loss": history["train_loss"][-1],
        "final_val_loss": history["val_loss"][-1] if history["val_loss"] else None,
        "failure_rate": metrics.get("failure_rate", 0),
    }

    # 提取关键指标
    for param in ["beta", "eta", "gamma"]:
        if param in metrics.get("param_standard", {}):
            abs_m = metrics["param_standard"][param].get("absolute", {})
            summary[f"rmse_{param}"] = abs_m.get("rmse")
            summary[f"mae_{param}"] = abs_m.get("mae")
            summary[f"bias_{param}"] = abs_m.get("bias")

    # x0.95 误差
    if 0.95 in metrics.get("quantile_standard", {}):
        rel_m = metrics["quantile_standard"][0.95].get("relative", {})
        summary["rmse_x095"] = rel_m.get("rmse")
        summary["mae_x095"] = rel_m.get("mae")

    return summary


def main():
    """主函数：遍历所有样本量进行训练。"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("="*60)
    print("E09-2b BP-feature 统计特征输入实验")
    print("="*60)

    all_summaries = []

    for n in SAMPLE_SIZES:
        summary = train_single_n(n)
        all_summaries.append(summary)

    # 保存汇总
    summary_df = pd.DataFrame(all_summaries)
    summary_path = os.path.join(OUTPUT_DIR, "E09-2b_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    print("\n" + "="*60)
    print("实验完成！汇总结果：")
    print("="*60)
    print(summary_df.to_string(index=False))
    print(f"\n汇总已保存: {summary_path}")


if __name__ == "__main__":
    main()
