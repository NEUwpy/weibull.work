import json
import numpy as np
from scipy.optimize import minimize_scalar
import os

def generate_limit_analysis_data():
    # 样本数据 (Case 3, Sim ID 19)
    t = np.array([1294.3591893594391, 1320.3495299256297, 1385.5551707382856, 1532.5482904128262, 1634.5383758002245, 2055.780184931579, 2196.802871370147])
    t_min = t[0]
    n = len(t)
    
    # 中位秩计算
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    neg_ln_1_minus_F = -np.log(1 - ranks)

    # 核心计算函数
    def calculate_eta_std(beta, gamma):
        if beta <= 0: return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0/beta)
        etas = (t - gamma) / denom
        return np.std(etas, ddof=1)

    def get_sigma_min(gamma):
        if gamma >= t_min: return None, None
        res = minimize_scalar(
            lambda b: calculate_eta_std(b, gamma),
            bounds=(0.1, 15.0),
            method='bounded'
        )
        return res.fun, res.x

    # 1. 常规范围数据 (0 ~ 1200)
    gammas_normal = np.linspace(0, 1200, 40)
    
    # 2. 过渡区数据 (1200 ~ 1290) - 这里增加密度以展示拐点
    gammas_transition = np.linspace(1200, 1290, 60)
    
    # 3. 极限逼近数据 (1290 ~ t_min) - 极高密度
    # 距离 t_min 的距离从 4.36 到 1e-6
    distances = np.logspace(np.log10(t_min - 1290), np.log10(1e-7 * t_min), 100)
    gammas_limit = t_min - distances
    
    # 合并并去重排序
    all_gammas = np.sort(np.unique(np.concatenate([gammas_normal, gammas_transition, gammas_limit])))
    
    all_data = []
    for g in all_gammas:
        if g >= t_min: continue
        s, b = get_sigma_min(g)
        if s is not None:
            all_data.append({
                "gamma": float(g),
                "sigma": float(s),
                "beta": float(b),
                "region": "normal" if g < t_min * 0.99 else "limit"
            })

    # 计算梯度 (使用数值差分)
    # 为了更准确，我们手动计算中心差分
    for i in range(len(all_data)):
        if i == 0:
            g_val = (all_data[i+1]['sigma'] - all_data[i]['sigma']) / (all_data[i+1]['gamma'] - all_data[i]['gamma'])
        elif i == len(all_data) - 1:
            g_val = (all_data[i]['sigma'] - all_data[i-1]['sigma']) / (all_data[i]['gamma'] - all_data[i-1]['gamma'])
        else:
            # 中心差分
            g_val = (all_data[i+1]['sigma'] - all_data[i-1]['sigma']) / (all_data[i+1]['gamma'] - all_data[i-1]['gamma'])
        
        all_data[i]['gradient'] = float(g_val)

    result = {
        "t_min": float(t_min),
        "data": all_data
    }
    
    output_path = os.path.join("public", "cases", "mdm_case3_limit_analysis.json")
    with open(output_path, "w") as f:
        json.dump(result, f)
    
    print(f"Data regenerated with {len(all_data)} points at {output_path}")

if __name__ == "__main__":
    generate_limit_analysis_data()
