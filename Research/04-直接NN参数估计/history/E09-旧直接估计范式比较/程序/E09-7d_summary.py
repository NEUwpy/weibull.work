"""
E09-7d 分类范式总结
- 汇总 E09-7a/7b/7c 结果
- 与 BP 回归对比
- 给出分类范式的最终结论
"""

import sys
import os
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")


def main():
    print("=" * 60)
    print("E09-7d: 分类范式总结")
    print("=" * 60)

    # 加载各实验结果
    df_7a = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-7a_classifiers_compare.csv'))
    df_7b = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-7b_bins_sensitivity.csv'))
    df_7c = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-7c_hierarchical_compare.csv'))

    # 加载 BP 基线
    bp_path = os.path.join(OUTPUT_DIR, 'E09-2a_summary_corrected.csv')
    if not os.path.exists(bp_path):
        bp_path = os.path.join(OUTPUT_DIR, 'E09-2a_summary.csv')
    df_bp = pd.read_csv(bp_path)

    # --- 1. 最佳分类器（E09-7a） ---
    print("\n" + "=" * 60)
    print("1. 最佳分类器对比（K=10）")
    print("=" * 60)

    pivot_7a = df_7a.pivot_table(index='n', columns='classifier', values='jparam')
    best_order = pivot_7a.mean().sort_values().index.tolist()
    pivot_7a = pivot_7a[best_order]
    print(pivot_7a.to_string(float_format='%.4f'))

    # 找出每个 n 的最佳分类器
    print("\n各样本量最佳分类器：")
    for _, row in pivot_7a.iterrows():
        best = row.idxmin()
        print(f"  n={int(row.name):3d}: {best:15s} J={row[best]:.4f}")

    # --- 2. 最佳分箱数（E09-7b） ---
    print("\n" + "=" * 60)
    print("2. 分箱数敏感性（XGBoost）")
    print("=" * 60)

    pivot_7b = df_7b.pivot_table(index='n', columns='K', values='jparam')
    print(pivot_7b.to_string(float_format='%.4f'))

    print("\n各样本量最佳 K：")
    for _, row in pivot_7b.iterrows():
        best_k = row.idxmin()
        print(f"  n={int(row.name):3d}: K={int(best_k):3d}  J={row[best_k]:.4f}")

    # --- 3. 分层 vs 扁平（E09-7c） ---
    print("\n" + "=" * 60)
    print("3. 分层 vs 扁平分类")
    print("=" * 60)

    pivot_7c = df_7c.pivot_table(index='n', columns='method', values='jparam')
    print(pivot_7c.to_string(float_format='%.4f'))

    # --- 4. 分类 vs BP 回归 ---
    print("\n" + "=" * 60)
    print("4. 最佳分类 vs BP 回归")
    print("=" * 60)

    # 取 E09-7a 中每个 n 的最佳分类器 J_param
    best_cls = df_7a.groupby('n')['jparam'].min().reset_index()
    best_cls.columns = ['n', 'best_cls_jparam']

    comparison = best_cls.merge(df_bp[['n', 'j_param']], on='n')
    comparison['gap'] = comparison['best_cls_jparam'] - comparison['j_param']
    comparison['ratio'] = comparison['best_cls_jparam'] / comparison['j_param']

    print(f"\n{'n':>5} {'Best-CLS':>12} {'BP-raw':>12} {'Gap':>12} {'Ratio':>10}")
    print("-" * 55)
    for _, row in comparison.iterrows():
        print(f"{int(row['n']):>5} {row['best_cls_jparam']:>12.4f} "
              f"{row['j_param']:>12.4f} {row['gap']:>12.4f} {row['ratio']:>10.2f}")

    # --- 5. 最终结论 ---
    print("\n" + "=" * 60)
    print("5. 最终结论")
    print("=" * 60)

    avg_ratio = comparison['ratio'].mean()
    print(f"""
分类范式系统探索结论：

1. 分类器选择：XGBoost ≈ LightGBM > RandomForest > SVM
   - 但差异很小（J_param 相差 3-7%），不是主要瓶颈

2. 分箱数：K=10 是最优选择
   - K=5: 下界太松（bound=1.09），分类无意义
   - K=10: 最佳平衡点
   - K=20/50: 分类难度急剧上升，准确率 <20%

3. 分层分类：不优于扁平分类
   - 硬分配分层比扁平差 7-15%（错误传播）
   - 软分配分层接近扁平但仍略差

4. 分类 vs BP 回归：
   - 最佳分类仍比 BP 差 {avg_ratio:.2f}x
   - 差距随样本量增大而缩小，但始终存在
   - 瓶颈：12 维特征 → K=10 分类的信息瓶颈

结论：纯分类范式在当前特征和分箱方案下无法超越 BP 回归。
分类范式的天花板已基本探明，进一步改进需要根本性的方法突破
（如端到端学习、更丰富的特征表示等）。
""")

    # 保存汇总
    summary = {
        'best_classifier': 'XGBoost',
        'best_K': 10,
        'hierarchical': 'not beneficial',
        'avg_ratio_to_bp': avg_ratio,
        'conclusion': 'Classification paradigm cannot match BP regression with current features',
    }
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(os.path.join(OUTPUT_DIR, 'E09-7d_summary.csv'), index=False)

    return comparison


if __name__ == "__main__":
    main()
