# -*- coding: utf-8 -*-
"""
E03 固定δ下误差分布分析
目的：展示不同δ下逐样本j_i的分布，解释为什么δ=0.1是最优
"""
import os, sys, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Nature style
sys.path.insert(0, os.path.expanduser(r"~\AppData\Local\hermes\skills\scientific-visualization\scripts"))
from style_presets import configure_for_journal
configure_for_journal('nature', figure_width='single')

BASE = r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE, "实验数据")
IMG_DIR  = os.path.join(BASE, "图像")

# 真值参数 (η=1固定，γ_true = γ/η ratio)
TRUE_PARAMS = {
    'beta': None,   # 从文件名读
    'eta':  1.0,
    'gamma': None,  # 从文件名读 gamma_ratio
}

def parse_config(fname):
    """从文件名解析 beta, n, gamma_ratio"""
    base = os.path.basename(fname)
    # E03-3_delta_sweep_beta2.0_n7_gamma0.1.csv
    parts = base.replace('.csv','').split('_')
    beta = float([p for p in parts if p.startswith('beta')][0].replace('beta',''))
    n = int([p for p in parts if p.startswith('n') and p[1:].isdigit()][0].replace('n',''))
    gr = float([p for p in parts if p.startswith('gamma')][0].replace('gamma',''))
    return beta, n, gr

def load_all_data():
    """加载所有27个分片CSV，计算逐样本j_i"""
    files = glob.glob(os.path.join(DATA_DIR, "E03-3_delta_sweep_*.csv"))
    all_dfs = []
    for f in files:
        beta, n, gr = parse_config(f)
        df = pd.read_csv(f)
        df['beta_true'] = beta
        df['eta_true'] = 1.0
        df['gamma_true'] = gr  # η=1, 所以γ_true = γ/η ratio
        df['n'] = n
        df['gamma_ratio'] = gr
        all_dfs.append(df)
    
    big = pd.concat(all_dfs, ignore_index=True)
    # 计算逐样本 j_i
    big['j_i'] = np.sqrt(
        ((big['beta_hat'] - big['beta_true']) / big['beta_true'])**2 +
        ((big['eta_hat'] - big['eta_true']) / big['eta_true'])**2 +
        ((big['gamma_hat'] - big['gamma_true']) / big['eta_true'])**2
    )
    return big

# === 1. 加载数据 ===
print("Loading data...")
df = load_all_data()
print(f"Total rows: {len(df):,}")
print(f"Unique deltas: {sorted(df['delta'].unique())}")
print(f"Configs: {df.groupby(['beta_true','n','gamma_ratio']).ngroups}")
