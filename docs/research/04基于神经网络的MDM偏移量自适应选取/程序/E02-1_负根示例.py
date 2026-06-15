"""
E02-1 负根示例图（Nature 样式）
构造典型成因①样本，画差异函数曲线，展示"根为负被切掉"
"""
import sys
sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")
sys.path.insert(0, "C:/Users/36089/AppData/Local/hermes/skills/scientific-visualization/scripts")

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from methods.mdm import MDM
from studies.common.sample import generate_sample
from style_presets import configure_for_journal

# Nature 样式 + 中文支持
configure_for_journal('nature', 'single')
mpl.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
mpl.rcParams['axes.unicode_minus'] = False

# 配置
beta_true = 2.0
eta_true = 100
gamma_true = 0
n = 20
offset = 0.1

# 找典型负根样本
for repeat_id in range(200):
    sample = generate_sample(beta_true, eta_true, gamma_true, n, repeat_id)
    t_min = sample[0]
    
    mdm = MDM(sample)
    t = mdm.data
    ranks = mdm._median_ranks()
    neg_ln_1_minus_F = -np.log(1 - ranks)
    
    def calculate_eta_std(beta, gamma):
        if beta <= 0: return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0/beta)
        etas = (t - gamma) / denom
        return np.std(etas, ddof=1)
    
    from scipy.optimize import minimize_scalar
    beta_sigma_cache = {}
    
    def find_best_beta_for_gamma(gamma):
        if gamma >= t[0]: return None, float('inf')
        cache_key = float(gamma)
        if cache_key in beta_sigma_cache: return beta_sigma_cache[cache_key]
        res = minimize_scalar(lambda b: calculate_eta_std(b, gamma), bounds=(0.1, 15.0), method='bounded')
        beta_sigma_cache[cache_key] = (res.x, res.fun)
        return beta_sigma_cache[cache_key]
    
    def profile_sigma(gamma):
        _, sigma = find_best_beta_for_gamma(float(gamma))
        return float(sigma)
    
    def profile_gradient(gamma):
        gamma = float(gamma)
        t_min_float = float(t_min)
        scale = max(abs(t_min_float), 1.0)
        nominal_h = scale * 1e-5
        left_room = max(gamma, 0.0)
        right_room = max(t_min_float - gamma, 0.0)
        if right_room <= 0: return float("inf")
        if gamma <= 0.0 or left_room <= nominal_h:
            h = min(nominal_h, right_room * 0.25)
            h = max(h, np.finfo(float).eps * scale)
            return (profile_sigma(gamma + h) - profile_sigma(gamma)) / h
        if right_room <= nominal_h:
            h = min(nominal_h, left_room * 0.25, right_room * 0.5)
            h = max(h, np.finfo(float).eps * scale)
            return (profile_sigma(gamma) - profile_sigma(gamma - h)) / h
        h = min(nominal_h, left_room * 0.25, right_room * 0.25)
        h = max(h, np.finfo(float).eps * scale)
        return (profile_sigma(gamma + h) - profile_sigma(gamma - h)) / (2.0 * h)
    
    # 搜索负根
    gamma_search = np.linspace(-0.3 * eta_true, t_min, 200)
    diffs = [profile_gradient(g) - offset for g in gamma_search]
    
    for i in range(len(diffs) - 1):
        if diffs[i] * diffs[i+1] < 0:
            gamma_root = gamma_search[i] - diffs[i] * (gamma_search[i+1] - gamma_search[i]) / (diffs[i+1] - diffs[i])
            if gamma_root < 0:
                print(f"找到负根样本: repeat_id={repeat_id}, γ*={gamma_root:.4f}")
                
                fig, ax = plt.subplots(figsize=(3.5, 2.625))
                
                gamma_fine = np.linspace(-0.3 * eta_true, t_min * 1.1, 500)
                diffs_fine = [profile_gradient(g) - offset for g in gamma_fine]
                
                ax.plot(gamma_fine, diffs_fine, 'b-', linewidth=1.2, label=r'$g(\gamma) - \delta$')
                ax.axhline(y=0, color='k', linewidth=0.5)
                ax.axvline(x=0, color='r', linestyle='--', linewidth=1.2, label=r'$\gamma=0$')
                ax.axvline(x=t_min, color='g', linestyle=':', linewidth=1.2, label=r'$t_{(1)}$')
                ax.plot(gamma_root, 0, 'ro', markersize=4, label=rf'$\gamma^*$={gamma_root:.1f}')
                ax.axvspan(-0.3 * eta_true, 0, alpha=0.15, color='gray', label='非法区域')
                
                ax.set_xlabel(r'$\gamma$')
                ax.set_ylabel(r'$g(\gamma) - \delta$')
                ax.set_title('成因①：无约束根为负被截断')
                ax.legend(fontsize=6, loc='upper left')
                ax.set_xlim(-0.3 * eta_true, t_min * 1.1)
                
                outpath = 'D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/图像/E02-1_负根示例.png'
                fig.savefig(outpath, dpi=300, bbox_inches='tight', facecolor='white')
                plt.close()
                print(f"图片已保存: {outpath}")
                break
    else:
        continue
    break
