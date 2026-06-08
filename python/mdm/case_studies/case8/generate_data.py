"""
⚠ 历史复现实验，不是当前默认 MDM 口径

案例8: β搜索方式对比研究 (实际样本)
数据来源: 实际样本 (7个数据点)
研究内容: β使用固定步长0.05遍历 vs Brent优化

与案例7的区别:
- 案例7: β 用 Brent 优化 (连续搜索)
- 案例8: β 用固定步长 0.05 遍历 (离散搜索)

四种策略:
1. 60次迭代 (β步长0.05)
2. 30次迭代 (β步长0.05)
3. 15次迭代 (β步长0.05)
4. 离散搜索 (间隔100，β步长0.05)

输出:
- public/case-studies/mdm/case8/data.json

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json

# 实际样本数据 (与案例7相同)
SAMPLE_DATA = [1430.724077, 2632.924529, 1463.409269, 1469.488488, 2019.967671, 1620.885368, 1811.277248]

# 要测试的偏移量
OFFSETS = [0.1, 0.15]

# β步长
BETA_STEP = 0.05

# 四种搜索策略
STRATEGIES = [
    {"id": "iter60", "name": "60次迭代(β步长0.05)", "gamma_steps": 60, "discrete": False},
    {"id": "iter30", "name": "30次迭代(β步长0.05)", "gamma_steps": 30, "discrete": False},
    {"id": "iter15", "name": "15次迭代(β步长0.05)", "gamma_steps": 15, "discrete": False},
    {"id": "discrete", "name": "离散搜索(γ:1430~0,间隔50,β步长0.05)", "gamma_steps": 0, "discrete": True},
]

def run_strategy(data, offset, strategy):
    """运行单个策略并返回结果"""
    mdm = MDMCase8(data)

    if strategy["discrete"]:
        beta, eta, gamma, r2, status = mdm.run(
            trace=True,
            offset=offset,
            discrete_gamma=True,
            beta_step=BETA_STEP
        )
    else:
        beta, eta, gamma, r2, status = mdm.run(
            trace=True,
            offset=offset,
            gamma_steps=strategy["gamma_steps"],
            beta_step=BETA_STEP
        )

    result = {
        "strategy_id": strategy["id"],
        "strategy_name": strategy["name"],
        "offset": offset,
        "beta_step": BETA_STEP,
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
    raise SystemExit(
        "案例8依赖已废弃的 beta_step MDM 分支。当前项目只保留 methods.mdm.MDM，"
        "历史结果请读取 public/case-studies/mdm/case8/data.json。"
    )

    print("=" * 60)
    print("案例8: β搜索方式对比研究 (β步长0.05)")
    print(f"数据: 实际样本 (n={len(SAMPLE_DATA)})")
    print(f"样本值: {SAMPLE_DATA}")
    print(f"偏移量: {OFFSETS}")
    print(f"β步长: {BETA_STEP}")
    print("=" * 60)

    all_results = []

    for strategy in STRATEGIES:
        print(f"\n策略: {strategy['name']}")
        print("-" * 40)

        for offset in OFFSETS:
            print(f"  offset={offset}...", end=" ")

            try:
                result = run_strategy(SAMPLE_DATA, offset, strategy)

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

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case8", "data.json")
    print(f"输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "source_case": "real_sample",
            "data": SAMPLE_DATA,
            "true_params": {"beta": None, "eta": None, "gamma": None},
            "strategies": STRATEGIES,
            "offsets": OFFSETS,
            "beta_step": BETA_STEP,
            "results": all_results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")
    print(f"共生成 {len(all_results)} 组结果")

    # 打印汇总表
    print("\n" + "=" * 60)
    print("汇总表")
    print("=" * 60)
    print(f"{'策略':<30} {'offset':<8} {'γ估计':<12} {'β估计':<10} {'状态'}")
    print("-" * 60)
    for r in all_results:
        gamma_str = f"{r.get('gamma', 'N/A'):.2f}" if r.get('gamma') else "N/A"
        beta_str = f"{r.get('beta', 'N/A'):.4f}" if r.get('beta') else "N/A"
        status = r.get('status', 'error')
        print(f"{r['strategy_name']:<30} {r['offset']:<8} {gamma_str:<12} {beta_str:<10} {status}")

if __name__ == "__main__":
    main()
