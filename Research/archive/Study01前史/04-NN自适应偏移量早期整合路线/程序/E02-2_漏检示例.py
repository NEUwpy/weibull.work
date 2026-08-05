"""
E02-2 漏检示例图（Nature 样式）
构造典型成因②样本，用20个搜索点画差异函数离散采样，展示"根靠近t₁导致漏检"
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
configure_for_journal('nature', 'double')
mpl.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
mpl.rcParams['axes.unicode_minus'] = False

# 配置
beta_true = 1.0
eta_true = 100
gamma_true = 50
n = 30
offset = 0.1

# 找典型漏检样本
for repeat_id in range(500):
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
    
    # 高分辨率找根
    gamma_fine = np.linspace(0, t_min * 0.999, 1000)
    diffs_fine = [profile_gradient(g) - offset for g in gamma_fine]
    
    root_gamma = None
    for i in range(len(diffs_fine) - 1):
        if diffs_fine[i] * diffs_fine[i+1] < 0:
            root_gamma = gamma_fine[i] - diffs_fine[i] * (gamma_fine[i+1] - gamma_fine[i]) / (diffs_fine[i+1] - diffs_fine[i])
            break
    
    if root_gamma is None: continue
    
    # 检查是否靠近 t₁
    if (t_min - root_gamma) < 0.1 * t_min:
        print(f"找到漏检样本: repeat_id={repeat_id}, γ*={root_gamma:.4f}, t₁={t_min:.4f}")
        
        # 20个搜索点（两段均匀网格）
        grid1 = np.linspace(0, t_min / 2, 10)
        grid2 = np.linspace(t_min / 2, t_min * 0.999, 10)
        grid_points = np.concatenate([grid1, grid2])
        grid_diffs = [profile_gradient(g) - offset for g in grid_points]
        
        # 画图
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.625))
        
        # 左图：全局
        ax1.plot(gamma_fine, diffs_fine, 'b-', linewidth=1.2, label='连续差异函数')
        ax1.plot(grid_points, grid_diffs, 'ko', markersize=3, label='20个搜索点')
        ax1.axhline(y=0, color='k', linewidth=0.5)
        ax1.axvline(x=t_min, color='g', linestyle=':', linewidth=1.2, label=r'$t_{(1)}$')
        ax1.axvline(x=root_gamma, color='r', linestyle='--', linewidth=1.2, label=rf'$\gamma^*$={root_gamma:.1f}')
        ax1.plot(grid_points, grid_diffs, 'k-', linewidth=0.4, alpha=0.5)
        ax1.set_xlabel(r'$\gamma$')
        ax1.set_ylabel(r'$g(\gamma) - \delta$')
        ax1.set_title('(a) 全局视图')
        ax1.legend(fontsize=5, loc='upper left')
        
        # 右图：放大
        zoom_min = max(0, root_gamma - 0.15 * t_min)
        zoom_max = min(t_min * 1.05, root_gamma + 0.15 * t_min)
        mask = (grid_points >= zoom_min) & (grid_points <= zoom_max)
        zoom_points = grid_points[mask]
        zoom_diffs = np.array(grid_diffs)[mask]
        
        gamma_zoom = np.linspace(zoom_min, zoom_max, 200)
        diffs_zoom = [profile_gradient(g) - offset for g in gamma_zoom]
        
        ax2.plot(gamma_zoom, diffs_zoom, 'b-', linewidth=1.2, label='连续差异函数')
        ax2.plot(zoom_points, zoom_diffs, 'ko', markersize=4, label='搜索点')
        ax2.axhline(y=0, color='k', linewidth=0.5)
        ax2.axvline(x=t_min, color='g', linestyle=':', linewidth=1.2, label=r'$t_{(1)}$')
        ax2.axvline(x=root_gamma, color='r', linestyle='--', linewidth=1.2, label=rf'$\gamma^*$={root_gamma:.1f}')
        ax2.plot(zoom_points, zoom_diffs, 'k-', linewidth=0.4, alpha=0.5)
        
        # 标注漏检区间
        left_pts = zoom_points[zoom_points < root_gamma]
        right_pts = zoom_points[zoom_points > root_gamma]
        if len(left_pts) > 0 and len(right_pts) > 0:
            ax2.axvspan(left_pts[-1], right_pts[0], alpha=0.15, color='orange', label='漏检区间')
            ax2.annotate('根被跳过', xy=(root_gamma, 0), xytext=(root_gamma, 0.03),
                        arrowprops=dict(arrowstyle='->', color='red', lw=0.8),
                        fontsize=7, color='red', ha='center')
        
        ax2.set_xlabel(r'$\gamma$')
        ax2.set_ylabel(r'$g(\gamma) - \delta$')
        ax2.set_title('(b) 根附近放大')
        ax2.legend(fontsize=5, loc='upper left')
        ax2.set_xlim(zoom_min, zoom_max)
        
        plt.tight_layout()
        outpath = 'D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/图像/E02-2_漏检示例.png'
        fig.savefig(outpath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"图片已保存: {outpath}")
        break
