"""
E03-4c ladder table v2: updated with all 4 beta estimation methods
"""
import numpy as np, pandas as pd, os

BASE = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE, "实验数据")

# Load data
level_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))
iter_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4a_self_iteration.csv"))
ext_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4b_v2_summary.csv"))
oracle_df = pd.read_csv(os.path.join(DATA_DIR, "E03-3_L5_oracle_jparam.csv"))

# Average J_param by method
l0  = level_df[level_df['level']=='L0']['jparam'].values[0]
l1  = level_df[level_df['level']=='L1']['jparam'].mean()
l3  = level_df[level_df['level']=='L3']['jparam'].mean()
l4  = level_df[level_df['level']=='L4']['jparam'].mean()
default = ext_df[ext_df['method']=='default']['jparam'].mean()
oracle_l5 = oracle_df['jparam'].mean()
oracle_l3 = ext_df[ext_df['method']=='oracle']['jparam'].mean()

# New methods
wmle  = ext_df[ext_df['method']=='wmle']['jparam'].mean()
mdm0  = ext_df[ext_df['method']=='mdm0']['jparam'].mean()
dual  = ext_df[ext_df['method']=='dual']['jparam'].mean()
lmom  = ext_df[ext_df['method']=='lmom']['jparam'].mean()

# Old methods
iterate  = iter_df['jparam_iterate'].mean()
mle      = ext_df[ext_df['method']=='MLE']['jparam'].mean() if 'MLE' in ext_df['method'].values else default
lse      = ext_df[ext_df['method']=='LSE']['jparam'].mean() if 'LSE' in ext_df['method'].values else default

# Build ladder
ladder = [
    ('L5 Oracle (per-sample)',  oracle_l5, 'X', 'upper bound'),
    ('L4 by (b,n,g/eta)',       l4,        'X', 'needs all true params'),
    ('L3 Oracle (true beta)',   oracle_l3, 'X', 'needs true beta'),
    ('L1 by n',                 l1,        'Y', 'n is known'),
    ('Default delta=0.1',       default,   'Y', 'zero cost, RECOMMENDED'),
    ('Self-iterate',            iterate,   'N', 'unstable, worsens'),
    ('WMLE + table',            wmle,      'N', '+7.5% worse'),
    ('MDM d=0 + table',         mdm0,      'N', '+9.6% worse'),
    ('Dual-delta + table',      dual,      'N', '+9.8% worse'),
    ('L-moments + table',       lmom,      'N', '+11.4%, 15.6% valid'),
]

ladder.sort(key=lambda x: x[1])

print("=== Updated Scheme Ladder ===")
for i, (name, jp, deploy, note) in enumerate(ladder):
    delta = (jp - default) / default * 100
    marker = ' <<<' if name.startswith('Default') else ''
    print(f"{i+1:2d}. {name:30s} J={jp:.4f}  ({delta:+.1f}%)  [{deploy}] {note}{marker}")

df = pd.DataFrame(ladder, columns=['method','jparam','deployable','note'])
df.insert(0, 'rank', range(1, len(df)+1))
df.to_csv(os.path.join(DATA_DIR, "E03-4c_ladder_table.csv"), index=False, encoding='utf-8-sig')
print("\nSaved: E03-4c_ladder_table.csv")
