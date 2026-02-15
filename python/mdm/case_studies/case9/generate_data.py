"""
案例9: β步长对MDM估计结果的影响研究 (实际样本)
数据来源: 实际样本 (7个数据点)
研究内容: β步长从0.01到0.1对估计结果的影响

β步长设置: 0.01, 0.02, 0.03, ..., 0.1 (共10种)
偏移量: 0.1, 0.15
γ搜索:
  - 图4: 60次迭代（连续）
  - 图5: 离散搜索（1430, 1400, 1350, ...）

研究目标:
1. β步长对最优β取值的影响
2. β步长对σ-β曲线的影响
3. β步长对σ_min-γ曲线的影响
4. β步长对最优γ估计的影响
5. 与Brent优化结果的对比
6. γ搜索方式（连续 vs 离散）的影响

输出:
- public/case-studies/mdm/case9/data.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from methods.mdm_case8 import MDMCase8  # 复用case8的算法，它支持自定义beta_step
from methods.mdm_case7 import MDMCase7  # 使用Brent优化的版本

# 实际样本数据 (与案例7/8相同)
SAMPLE_DATA = [1430.724077, 2632.924529, 1463.409269, 1469.488488, 2019.967671, 1620.885368, 1811.277248]

# 要测试的偏移量
OFFSETS = [0.1, 0.15]

# β步长: 0.01 到 0.1，间隔 0.01
BETA_STEPS = [round(0.01 * i, 2) for i in range(1, 11)]  # [0.01, 0.02, ..., 0.1]

# γ搜索：60次迭代（用于图4）
GAMMA_STEPS = 60

def run_with_beta_step(data, offset, beta_step, discrete_gamma=False):
    """运行指定β步长的MDM估计"""
    mdm = MDMCase8(data)

    beta, eta, gamma, r2, status = mdm.run(
        trace=True,
        offset=offset,
        gamma_steps=GAMMA_STEPS,
        discrete_gamma=discrete_gamma,
        beta_step=beta_step
    )

    result = {
        "beta_step": beta_step,
        "offset": offset,
        "gamma_mode": "discrete" if discrete_gamma else "continuous",
        "beta": float(beta) if beta is not None else None,
        "eta": float(eta) if eta is not None else None,
        "gamma": float(gamma) if gamma is not None else None,
        "r2": float(r2) if r2 is not None else None,
        "status": status,
    }

    # 添加trace数据用于绘图
    if mdm.trace_data:
        result["trace_data"] = mdm.trace_data

    return result

def run_with_brent(data, offset):
    """运行Brent优化的MDM估计（作为参考基准）"""
    mdm = MDMCase7(data)

    beta, eta, gamma, r2, status = mdm.run(
        trace=True,
        offset=offset,
        gamma_steps=GAMMA_STEPS,
        discrete_gamma=False
    )

    result = {
        "method": "brent",
        "offset": offset,
        "beta": float(beta) if beta is not None else None,
        "eta": float(eta) if eta is not None else None,
        "gamma": float(gamma) if gamma is not None else None,
        "r2": float(r2) if r2 is not None else None,
        "status": status,
    }

    # 添加trace数据用于绘图
    if mdm.trace_data:
        result["trace_data"] = mdm.trace_data

    return result

def main():
    print("=" * 70)
    print("案例9: β步长对MDM估计结果的影响研究")
    print(f"数据: 实际样本 (n={len(SAMPLE_DATA)})")
    print(f"样本值: {SAMPLE_DATA}")
    print(f"偏移量: {OFFSETS}")
    print(f"β步长: {BETA_STEPS}")
    print(f"γ搜索: {GAMMA_STEPS}次迭代 + 离散搜索")
    print("=" * 70)

    all_results = []
    discrete_results = []  # 离散γ搜索的结果（图5用）
    brent_results = []

    # 首先运行Brent优化作为参考
    print("\n[参考基准] Brent优化结果:")
    print("-" * 50)
    for offset in OFFSETS:
        print(f"  δ={offset}...", end=" ")
        try:
            result = run_with_brent(SAMPLE_DATA, offset)
            if result["gamma"] is not None:
                print(f"γ={result['gamma']:.2f}, β={result['beta']:.6f}, η={result['eta']:.1f}")
            else:
                print(f"无交点")
            brent_results.append(result)
        except Exception as e:
            print(f"错误: {e}")

    # 运行不同β步长的连续搜索（图4）
    for offset in OFFSETS:
        print(f"\n[图4] 连续搜索 (60次迭代):")
        print("-" * 50)

        for beta_step in BETA_STEPS:
            print(f"  β步长={beta_step:.2f}...", end=" ")

            try:
                result = run_with_beta_step(SAMPLE_DATA, offset, beta_step, discrete_gamma=False)

                if result["gamma"] is not None:
                    print(f"γ={result['gamma']:.2f}, β={result['beta']:.4f}, η={result['eta']:.1f}")
                else:
                    print(f"无交点 (status={result['status']})")

                all_results.append(result)

            except Exception as e:
                print(f"错误: {e}")
                all_results.append({
                    "beta_step": beta_step,
                    "offset": offset,
                    "gamma_mode": "continuous",
                    "error": str(e)
                })

    # 运行不同β步长的离散搜索（图5）
    for offset in OFFSETS:
        print(f"\n[图5] 离散搜索 (1430, 1400, 1350...):")
        print("-" * 50)

        for beta_step in BETA_STEPS:
            print(f"  β步长={beta_step:.2f}...", end=" ")

            try:
                result = run_with_beta_step(SAMPLE_DATA, offset, beta_step, discrete_gamma=True)

                if result["gamma"] is not None:
                    print(f"γ={result['gamma']:.2f}, β={result['beta']:.4f}, η={result['eta']:.1f}")
                else:
                    print(f"无交点 (status={result['status']})")

                discrete_results.append(result)

            except Exception as e:
                print(f"错误: {e}")
                discrete_results.append({
                    "beta_step": beta_step,
                    "offset": offset,
                    "gamma_mode": "discrete",
                    "error": str(e)
                })

    # 计算相对于Brent优化的误差
    brent_ref = {}
    for r in brent_results:
        brent_ref[r["offset"]] = r

    for r in all_results + discrete_results:
        if "error" not in r and r["offset"] in brent_ref:
            ref = brent_ref[r["offset"]]
            if ref.get("beta") is not None and r.get("beta") is not None:
                r["beta_error"] = abs(r["beta"] - ref["beta"])
                r["gamma_error"] = abs(r["gamma"] - ref["gamma"])
                r["eta_error"] = abs(r["eta"] - ref["eta"])

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case9", "data.json")
    print(f"\n输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "source_case": "real_sample",
            "data": SAMPLE_DATA,
            "true_params": {"beta": None, "eta": None, "gamma": None},
            "beta_steps": BETA_STEPS,
            "offsets": OFFSETS,
            "gamma_steps": GAMMA_STEPS,
            "brent_results": brent_results,
            "results": all_results,
            "discrete_results": discrete_results
        }, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")
    print(f"共生成 {len(all_results)} 组连续搜索 + {len(discrete_results)} 组离散搜索 + {len(brent_results)} 组Brent优化")

    # 打印汇总表
    print("\n" + "=" * 100)
    print("汇总表")
    print("=" * 100)

    for offset in OFFSETS:
        brent_r = brent_ref.get(offset)
        print(f"\nδ = {offset}")
        if brent_r:
            print(f"  [Brent] γ={brent_r['gamma']:.2f}, β={brent_r['beta']:.6f}, η={brent_r['eta']:.1f}")
        print(f"{'β步长':<10} {'γ估计':<12} {'β估计':<12} {'η估计':<12} {'β误差(vs Brent)':<16} {'γ误差(vs Brent)':<16}")
        print("-" * 80)

        for r in [x for x in all_results if x.get("offset") == offset and "error" not in x]:
            gamma_str = f"{r['gamma']:.2f}" if r.get('gamma') else "N/A"
            beta_str = f"{r['beta']:.4f}" if r.get('beta') else "N/A"
            eta_str = f"{r['eta']:.1f}" if r.get('eta') else "N/A"
            beta_err = f"{r.get('beta_error', 0):.6f}" if r.get('beta_error') else "-"
            gamma_err = f"{r.get('gamma_error', 0):.4f}" if r.get('gamma_error') else "-"
            print(f"{r['beta_step']:<10.2f} {gamma_str:<12} {beta_str:<12} {eta_str:<12} {beta_err:<16} {gamma_err:<16}")

if __name__ == "__main__":
    main()
