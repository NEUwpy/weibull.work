"""
E03-4c 方案阶梯表
汇总所有δ选择方案的精度、计算成本、部署可行性
"""
import sys
import numpy as np
import pandas as pd
import os

BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")

# 加载各实验结果
print("加载实验数据...")

# E03-2 层级最优
level_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))

# E03-4a 自迭代
iter_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4a_self_iteration.csv"))

# E03-4b 外部β预估（含Default对照）
ext_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4b_summary.csv"))

# E03-3 Oracle
oracle_df = pd.read_csv(os.path.join(DATA_DIR, "E03-3_L5_oracle_jparam.csv"))

# 计算各方案的平均J_param
print("\n计算各方案平均J_param...")

# 1. Default δ=0.1
default_jparam = ext_df[ext_df['method'] == 'Default(δ=0.1)']['jparam'].mean()
print(f"Default(δ=0.1): {default_jparam:.4f}")

# 2. L0 全局
l0_jparam = level_df[level_df['level'] == 'L0']['jparam'].values[0]
print(f"L0 全局: {l0_jparam:.4f}")

# 3. L1 按n
l1_jparam = level_df[level_df['level'] == 'L1']['jparam'].mean()
print(f"L1 按n: {l1_jparam:.4f}")

# 4. L3 按(β,n)
l3_jparam = level_df[level_df['level'] == 'L3']['jparam'].mean()
print(f"L3 按(β,n): {l3_jparam:.4f}")

# 5. L4 按(β,n,γ/η)
l4_jparam = level_df[level_df['level'] == 'L4']['jparam'].mean()
print(f"L4 按(β,n,γ/η): {l4_jparam:.4f}")

# 6. 自迭代
iter_jparam = iter_df['jparam_iterate'].mean()
print(f"自迭代: {iter_jparam:.4f}")

# 7. MLE外部β
mle_jparam = ext_df[ext_df['method'] == 'MLE']['jparam'].mean()
print(f"MLE外部β: {mle_jparam:.4f}")

# 8. LSE外部β
lse_jparam = ext_df[ext_df['method'] == 'LSE']['jparam'].mean()
print(f"LSE外部β: {lse_jparam:.4f}")

# 9. L5 Oracle
oracle_jparam = oracle_df['jparam'].mean()
print(f"L5 Oracle: {oracle_jparam:.4f}")

# 构建阶梯表
print("\n构建方案阶梯表...")

ladder = [
    {
        'method': 'Default(delta=0.1)',
        'jparam': default_jparam,
        'vs_oracle': default_jparam / oracle_jparam,
        'cost': 'very low (1 MDM)',
        'deployable': 'Y direct',
        'need_true': 'no'
    },
    {
        'method': 'L0 global',
        'jparam': l0_jparam,
        'vs_oracle': l0_jparam / oracle_jparam,
        'cost': 'very low (lookup)',
        'deployable': 'Y precompute',
        'need_true': 'no (offline calibrate)'
    },
    {
        'method': 'L1 by n',
        'jparam': l1_jparam,
        'vs_oracle': l1_jparam / oracle_jparam,
        'cost': 'very low (lookup)',
        'deployable': 'Y precompute',
        'need_true': 'no (offline calibrate)'
    },
    {
        'method': 'L3 by (beta,n)',
        'jparam': l3_jparam,
        'vs_oracle': l3_jparam / oracle_jparam,
        'cost': 'low (need beta est)',
        'deployable': 'Y need external beta',
        'need_true': 'no'
    },
    {
        'method': 'L4 by (beta,n,gamma/eta)',
        'jparam': l4_jparam,
        'vs_oracle': l4_jparam / oracle_jparam,
        'cost': 'low (need param est)',
        'deployable': 'Y need external est',
        'need_true': 'no'
    },
    {
        'method': 'Self-iterate',
        'jparam': iter_jparam,
        'vs_oracle': iter_jparam / oracle_jparam,
        'cost': 'medium (2 MDM)',
        'deployable': '? convergence unstable',
        'need_true': 'no'
    },
    {
        'method': 'MLE external beta',
        'jparam': mle_jparam,
        'vs_oracle': mle_jparam / oracle_jparam,
        'cost': 'high (MLE+MDM)',
        'deployable': '? MLE fails small n',
        'need_true': 'no'
    },
    {
        'method': 'LSE external beta',
        'jparam': lse_jparam,
        'vs_oracle': lse_jparam / oracle_jparam,
        'cost': 'high (LSE+MDM)',
        'deployable': 'Y LSE stable',
        'need_true': 'no'
    },
    {
        'method': 'L5 Oracle (per-sample)',
        'jparam': oracle_jparam,
        'vs_oracle': 1.0,
        'cost': 'very high (scan all delta)',
        'deployable': 'X need true values',
        'need_true': 'yes'
    }
]

ladder_df = pd.DataFrame(ladder)

# 按jparam排序
ladder_df = ladder_df.sort_values('jparam')

# 添加排名
ladder_df.insert(0, 'rank', range(1, len(ladder_df) + 1))

# 格式化vs_oracle列
ladder_df['vs_oracle'] = ladder_df['vs_oracle'].apply(lambda x: f"{x:.3f}")

print("\n=== Ladder Table ===")
for _, row in ladder_df.iterrows():
    print(f"{row['rank']}. {row['method']}: J_param={row['jparam']:.4f}, vs_oracle={row['vs_oracle']}")

# 保存
out_path = os.path.join(DATA_DIR, "E03-4c_ladder_table.csv")
ladder_df.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n阶梯表已保存: {out_path}")

# 分析结论
print("\n=== 关键结论 ===")
print(f"1. 默认delta=0.1已是L0全局最优（J_param={default_jparam:.4f}）")
print(f"2. 层级提升收益有限：L0->L4 改善{(l0_jparam-l4_jparam)/l0_jparam*100:.1f}%")
print(f"3. 自迭代方案不可行：平均改善{iter_df['improvement'].mean():.1f}%")
print(f"4. 外部beta预估风险大：MLE在小样本失效，LSE精度不如MDM")
print(f"5. Oracle下界={oracle_jparam:.4f}，可部署方案~{l3_jparam:.4f}，差距{(l3_jparam-oracle_jparam)/oracle_jparam*100:.1f}%")
