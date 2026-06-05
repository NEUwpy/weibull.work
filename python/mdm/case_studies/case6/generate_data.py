"""
⚠ 历史复现实验，不是当前默认 MDM 口径

案例6: 搜索步长对结果的影响
数据来源: c2案例 (7个数据点)
研究内容: 不同迭代次数和搜索策略对MDM参数估计的影响

四种策略:
1. 60次迭代 (默认)
2. 30次迭代
3. 15次迭代
4. 离散搜索 (间隔100)

输出:
- public/case-studies/mdm/case6/data.json

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from methods.mdm_case6 import MDMCase6

# c2案例数据 (保留一位小数)
C2_DATA = [2169.4, 1495.1, 1611.6, 1875.7, 1396.7, 2567.3, 1970.9]

# 要测试的偏移量
OFFSETS = [0.1, 0.15]

# 四种搜索策略
STRATEGIES = [
    {"id": "iter60", "name": "60次迭代", "gamma_steps": 60, "discrete": False},
    {"id": "iter30", "name": "30次迭代", "gamma_steps": 30, "discrete": False},
    {"id": "iter15", "name": "15次迭代", "gamma_steps": 15, "discrete": False},
    {"id": "discrete", "name": "离散搜索(间隔100)", "gamma_steps": 0, "discrete": True},
]

def run_strategy(data, offset, strategy):
    """运行单个策略并返回结果"""
    mdm = MDMCase6(data)

    if strategy["discrete"]:
        beta, eta, gamma, r2, status = mdm.run(
            trace=True,
            offset=offset,
            discrete_gamma=True
        )
    else:
        beta, eta, gamma, r2, status = mdm.run(
            trace=True,
            offset=offset,
            gamma_steps=strategy["gamma_steps"]
        )

    result = {
        "strategy_id": strategy["id"],
        "strategy_name": strategy["name"],
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
    print("=" * 60)
    print("案例6: 搜索步长对MDM结果的影响")
    print(f"数据: c2案例 (n={len(C2_DATA)})")
    print(f"偏移量: {OFFSETS}")
    print("=" * 60)

    all_results = []

    for strategy in STRATEGIES:
        print(f"\n策略: {strategy['name']}")
        print("-" * 40)

        for offset in OFFSETS:
            print(f"  offset={offset}...", end=" ")

            try:
                result = run_strategy(C2_DATA, offset, strategy)

                if result["gamma"] is not None:
                    print(f"γ={result['gamma']:.2f}, β={result['beta']:.4f}")
                else:
                    print(f"无交点 (status={result['status']})")

                all_results.append(result)

            except Exception as e:
                print(f"错误: {e}")
                all_results.append({
                    "strategy_id": strategy["id"],
                    "strategy_name": strategy["name"],
                    "offset": offset,
                    "error": str(e)
                })

    # 保存结果 - 使用绝对路径
    # 脚本在 python/mdm/case_studies/case6/，需要走4级到项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case6", "data.json")
    print(f"输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "source_case": "c2",
            "data": C2_DATA,
            "true_params": {"beta": 2.0, "eta": 1000, "gamma": 1000},
            "strategies": STRATEGIES,
            "offsets": OFFSETS,
            "results": all_results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")
    print(f"共生成 {len(all_results)} 组结果")

    # 打印汇总表
    print("\n" + "=" * 60)
    print("汇总表")
    print("=" * 60)
    print(f"{'策略':<20} {'offset':<8} {'γ估计':<12} {'β估计':<10} {'状态'}")
    print("-" * 60)
    for r in all_results:
        gamma_str = f"{r.get('gamma', 'N/A'):.2f}" if r.get('gamma') else "N/A"
        beta_str = f"{r.get('beta', 'N/A'):.4f}" if r.get('beta') else "N/A"
        status = r.get('status', 'error')
        print(f"{r['strategy_name']:<20} {r['offset']:<8} {gamma_str:<12} {beta_str:<10} {status}")

if __name__ == "__main__":
    main()
