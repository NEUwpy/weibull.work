"""
案例12: MDM vs WMLE 方法对比研究

研究内容:
- 对比两种威布尔参数估计方法: MDM vs WMLE
- 多样本量: n = 7, 10, 15
- 蒙特卡洛模拟: 各5000次/方法/样本量
- 全面统计: 全范围、99%置信区间、95%置信区间

输出:
- public/case-studies/mdm/case12/data.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from methods.mdm import MDM
from methods.wmle import WMLE

# 模拟参数
SAMPLE_SIZES = [7, 9, 10, 12, 15, 20]
N_SIMULATIONS = 5000

# 真实参数
TRUE_BETA = 2.0
TRUE_ETA = 1000.0
TRUE_GAMMA = 1000.0

# MDM 参数
OFFSET = 0.1

# 随机种子
SEED = 42


def generate_weibull_3p_samples(n: int, beta: float, eta: float, gamma: float, rng: np.random.Generator) -> list:
    """
    生成三参数Weibull分布的随机样本
    """
    u = rng.uniform(0, 1, n)
    samples = gamma + eta * np.power(-np.log(1 - u), 1.0 / beta)
    return sorted(samples.tolist())


def run_mdm(data: list, sim_id: int) -> dict:
    """
    运行 MDM 估计
    """
    try:
        mdm = MDM(data)
        result = mdm.run(offset=OFFSET, trace=False)

        if len(result) == 5:
            beta, eta, gamma, r2, status = result
        else:
            beta, eta, gamma, r2 = result[:4]
            status = True

        if beta is None or status == "no_intersection":
            return {
                "sim_id": sim_id,
                "method": "mdm",
                "beta": None,
                "eta": None,
                "gamma": None,
                "status": "no_solution",
            }

        return {
            "sim_id": sim_id,
            "method": "mdm",
            "beta": float(beta),
            "eta": float(eta),
            "gamma": float(gamma),
            "status": "success",
        }
    except Exception as e:
        return {
            "sim_id": sim_id,
            "method": "mdm",
            "beta": None,
            "eta": None,
            "gamma": None,
            "status": f"error",
        }


def run_wmle(data: list, sim_id: int) -> dict:
    """
    运行 WMLE 估计
    """
    try:
        wmle = WMLE(data)
        result = wmle.run(trace=False)

        beta, eta, gamma, r2 = result[0], result[1], result[2], result[3]

        if beta is None or beta <= 0:
            return {
                "sim_id": sim_id,
                "method": "wmle",
                "beta": None,
                "eta": None,
                "gamma": None,
                "status": "no_solution",
            }

        return {
            "sim_id": sim_id,
            "method": "wmle",
            "beta": float(beta),
            "eta": float(eta),
            "gamma": float(gamma),
            "status": "success",
        }
    except Exception as e:
        return {
            "sim_id": sim_id,
            "method": "wmle",
            "beta": None,
            "eta": None,
            "gamma": None,
            "status": "error",
        }


def calculate_statistics(results: list, true_beta: float, true_eta: float, true_gamma: float) -> dict:
    """
    计算全面统计量

    包括:
    - 全范围: min, max
    - 99% 置信区间: p0.5, p99.5
    - 95% 置信区间: p2.5, p97.5
    - 集中趋势: mean, median
    - 离散程度: std
    - 偏差: bias (相对于真实值)
    """
    valid_results = [r for r in results if r.get("beta") is not None and r.get("status") == "success"]

    if not valid_results:
        return {
            "count": len(results),
            "valid_count": 0,
            "solution_rate": 0.0,
        }

    betas = np.array([r["beta"] for r in valid_results])
    etas = np.array([r["eta"] for r in valid_results])
    gammas = np.array([r["gamma"] for r in valid_results])

    def calc_param_stats(values, true_value):
        return {
            # 集中趋势
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            # 离散程度
            "std": float(np.std(values, ddof=1)),
            # 全范围
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            # 99% 置信区间 (两端各舍弃 0.5%)
            "p005": float(np.percentile(values, 0.5)),
            "p995": float(np.percentile(values, 99.5)),
            # 95% 置信区间 (两端各舍弃 2.5%)
            "p025": float(np.percentile(values, 2.5)),
            "p975": float(np.percentile(values, 97.5)),
            # 四分位数
            "q1": float(np.percentile(values, 25)),
            "q3": float(np.percentile(values, 75)),
            # 偏差
            "bias": float(np.mean(values) - true_value),
            # MSE
            "mse": float(np.mean((values - true_value) ** 2)),
        }

    return {
        "count": len(results),
        "valid_count": len(valid_results),
        "solution_rate": len(valid_results) / len(results),
        "beta": calc_param_stats(betas, true_beta),
        "eta": calc_param_stats(etas, true_eta),
        "gamma": calc_param_stats(gammas, true_gamma),
    }


def run_simulations_for_sample_size(n: int, all_datasets: list) -> dict:
    """
    运行指定样本量的所有模拟
    """
    print(f"\n{'='*70}")
    print(f"样本量 n = {n}")
    print(f"{'='*70}")

    # 运行 MDM
    print(f"运行 MDM ({N_SIMULATIONS} 次模拟)...")
    mdm_results = []
    for i, data in enumerate(all_datasets):
        if (i + 1) % 200 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_mdm(data, i)
        mdm_results.append(result)

    # 运行 WMLE
    print(f"运行 WMLE ({N_SIMULATIONS} 次模拟)...")
    wmle_results = []
    for i, data in enumerate(all_datasets):
        if (i + 1) % 200 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_wmle(data, i + N_SIMULATIONS)
        wmle_results.append(result)

    # 计算统计量
    print("计算统计量...")
    mdm_stats = calculate_statistics(mdm_results, TRUE_BETA, TRUE_ETA, TRUE_GAMMA)
    wmle_stats = calculate_statistics(wmle_results, TRUE_BETA, TRUE_ETA, TRUE_GAMMA)

    # 打印汇总
    print(f"\n汇总 (n={n}):")
    print(f"  MDM:  有解率={mdm_stats['solution_rate']:.2%}, "
          f"β均值={mdm_stats['beta']['mean']:.4f}, "
          f"β偏差={mdm_stats['beta']['bias']:.6f}")
    print(f"  WMLE: 有解率={wmle_stats['solution_rate']:.2%}, "
          f"β均值={wmle_stats['beta']['mean']:.4f}, "
          f"β偏差={wmle_stats['beta']['bias']:.6f}")

    return {
        "n": n,
        "mdm_stats": mdm_stats,
        "wmle_stats": wmle_stats,
        "mdm_results": mdm_results,
        "wmle_results": wmle_results,
    }


def main():
    print("=" * 70)
    print("案例12: MDM vs WMLE 方法对比研究")
    print(f"样本量: {SAMPLE_SIZES}")
    print(f"模拟次数: {N_SIMULATIONS} 次/方法/样本量")
    print(f"真实参数: β={TRUE_BETA}, η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"MDM偏移量: δ={OFFSET}")
    print("=" * 70)

    # 初始化随机数生成器
    rng = np.random.default_rng(SEED)

    all_sample_results = []

    for n in SAMPLE_SIZES:
        print(f"\n生成 n={n} 的随机样本...")
        datasets = []
        for i in range(N_SIMULATIONS):
            data = generate_weibull_3p_samples(n, TRUE_BETA, TRUE_ETA, TRUE_GAMMA, rng)
            datasets.append(data)

        result = run_simulations_for_sample_size(n, datasets)
        all_sample_results.append(result)

    # 构建输出数据
    output_data = {
        "simulation_params": {
            "sample_sizes": SAMPLE_SIZES,
            "n_simulations": N_SIMULATIONS,
            "true_beta": TRUE_BETA,
            "true_eta": TRUE_ETA,
            "true_gamma": TRUE_GAMMA,
            "offset": OFFSET,
            "seed": SEED,
        },
        "sample_results": all_sample_results,
    }

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case12", "data.json")
    print(f"\n输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")

    # 打印最终汇总表
    print("\n" + "=" * 120)
    print("最终汇总表")
    print("=" * 120)

    # 表头
    print(f"\n{'n':<4} {'方法':<6} {'有解率':<8} {'均值':<10} {'标准差':<10} "
          f"{'95%CI下':<12} {'95%CI上':<12} {'99%CI下':<12} {'99%CI上':<12} {'全范围':<20}")
    print("-" * 120)

    for sr in all_sample_results:
        n = sr["n"]
        for method_name, stats in [("MDM", sr["mdm_stats"]), ("WMLE", sr["wmle_stats"])]:
            b = stats["beta"]
            print(f"{n:<4} {method_name:<6} {stats['solution_rate']:<8.1%} "
                  f"{b['mean']:<10.4f} {b['std']:<10.4f} "
                  f"{b['p025']:<12.4f} {b['p975']:<12.4f} "
                  f"{b['p005']:<12.4f} {b['p995']:<12.4f} "
                  f"[{b['min']:.4f}, {b['max']:.4f}]")
        print("-" * 120)

    # γ 参数汇总
    print(f"\n{'n':<4} {'方法':<6} {'有解率':<8} {'γ均值':<10} {'γ标准差':<10} "
          f"{'95%CI下':<12} {'95%CI上':<12}")
    print("-" * 80)

    for sr in all_sample_results:
        n = sr["n"]
        for method_name, stats in [("MDM", sr["mdm_stats"]), ("WMLE", sr["wmle_stats"])]:
            g = stats["gamma"]
            print(f"{n:<4} {method_name:<6} {stats['solution_rate']:<8.1%} "
                  f"{g['mean']:<10.2f} {g['std']:<10.2f} "
                  f"{g['p025']:<12.2f} {g['p975']:<12.2f}")
        print("-" * 80)


if __name__ == "__main__":
    main()
