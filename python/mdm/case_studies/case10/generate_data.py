"""
案例10: 中位秩方法对比研究 (蒙特卡洛模拟 + 曲线对比)

研究内容:
- 蒙特卡洛模拟: n=7, 1000次/方法, 用于统计分析
- 固定样本: 使用实际样本数据，记录完整 trace 曲线用于可视化对比
- 对比两种中位秩方法: Bernard's approximation vs 精确中位秩

输出:
- public/case-studies/mdm/case10/data.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from methods.mdm_case10 import MDMCase10, median_rank_bernard, median_rank_exact

# 模拟参数
N_SAMPLES = 7           # 样本量
N_SIMULATIONS = 1000    # 每种方法的模拟次数

# 真实参数
TRUE_BETA = 2.0
TRUE_ETA = 1000.0
TRUE_GAMMA = 1000.0

# MDM参数
OFFSET = 0.1
GAMMA_STEPS = 60

# 随机种子 (用于可重复性)
SEED = 42

# 固定样本数据 (来自案例7的实际样本)
FIXED_SAMPLE = [1430.724077, 2632.924529, 1463.409269, 1469.488488, 2019.967671, 1620.885368, 1811.277248]


def generate_weibull_3p_samples(n: int, beta: float, eta: float, gamma: float, rng: np.random.Generator) -> list:
    """
    生成三参数Weibull分布的随机样本

    Weibull 3P: F(t) = 1 - exp(-((t - gamma) / eta)^beta)
    逆变换: t = gamma + eta * (-ln(1 - U))^(1/beta)

    Args:
        n: 样本量
        beta: 形状参数
        eta: 尺度参数
        gamma: 位置参数
        rng: 随机数生成器

    Returns:
        排序后的样本列表
    """
    u = rng.uniform(0, 1, n)
    samples = gamma + eta * np.power(-np.log(1 - u), 1.0 / beta)
    return sorted(samples.tolist())


def run_single_simulation(data: list, rank_method: str, sim_id: int, trace: bool = False):
    """
    运行单次MDM估计

    Args:
        data: 样本数据
        rank_method: 中位秩方法 ('bernard' 或 'exact')
        sim_id: 模拟ID
        trace: 是否记录trace数据

    Returns:
        估计结果字典
    """
    try:
        mdm = MDMCase10(data, rank_method=rank_method)
        beta, eta, gamma, r2, status = mdm.run(offset=OFFSET, gamma_steps=GAMMA_STEPS, trace=trace)

        result = {
            "sim_id": sim_id,
            "rank_method": rank_method,
            "beta": float(beta) if beta is not None else None,
            "eta": float(eta) if eta is not None else None,
            "gamma": float(gamma) if gamma is not None else None,
            "r2": float(r2) if r2 is not None else None,
            "status": status if isinstance(status, str) else ("success" if status else "failed"),
        }

        # 计算偏差
        if beta is not None:
            result["bias_beta"] = beta - TRUE_BETA
            result["bias_eta"] = eta - TRUE_ETA
            result["bias_gamma"] = gamma - TRUE_GAMMA

        # 保存trace数据
        if trace and hasattr(mdm, 'trace_data') and mdm.trace_data:
            result["trace_data"] = mdm.trace_data

        return result

    except Exception as e:
        return {
            "sim_id": sim_id,
            "rank_method": rank_method,
            "beta": None,
            "eta": None,
            "gamma": None,
            "r2": None,
            "status": f"error: {str(e)}",
            "error": str(e)
        }


def calculate_statistics(results: list) -> dict:
    """
    计算统计量

    Args:
        results: 估计结果列表

    Returns:
        统计量字典
    """
    # 过滤有效结果
    valid_results = [r for r in results if r.get("beta") is not None and r.get("status") == "success"]

    if not valid_results:
        return {
            "count": 0,
            "valid_count": 0,
            "convergence_rate": 0.0,
        }

    betas = np.array([r["beta"] for r in valid_results])
    etas = np.array([r["eta"] for r in valid_results])
    gammas = np.array([r["gamma"] for r in valid_results])

    bias_betas = np.array([r["bias_beta"] for r in valid_results])
    bias_etas = np.array([r["bias_eta"] for r in valid_results])
    bias_gammas = np.array([r["bias_gamma"] for r in valid_results])

    return {
        "count": len(results),
        "valid_count": len(valid_results),
        "convergence_rate": len(valid_results) / len(results),
        "beta": {
            "mean": float(np.mean(betas)),
            "std": float(np.std(betas, ddof=1)),
            "min": float(np.min(betas)),
            "max": float(np.max(betas)),
            "median": float(np.median(betas)),
            "q1": float(np.percentile(betas, 25)),
            "q3": float(np.percentile(betas, 75)),
            "p01": float(np.percentile(betas, 1)),
            "p99": float(np.percentile(betas, 99)),
        },
        "eta": {
            "mean": float(np.mean(etas)),
            "std": float(np.std(etas, ddof=1)),
            "min": float(np.min(etas)),
            "max": float(np.max(etas)),
            "median": float(np.median(etas)),
            "q1": float(np.percentile(etas, 25)),
            "q3": float(np.percentile(etas, 75)),
            "p01": float(np.percentile(etas, 1)),
            "p99": float(np.percentile(etas, 99)),
        },
        "gamma": {
            "mean": float(np.mean(gammas)),
            "std": float(np.std(gammas, ddof=1)),
            "min": float(np.min(gammas)),
            "max": float(np.max(gammas)),
            "median": float(np.median(gammas)),
            "q1": float(np.percentile(gammas, 25)),
            "q3": float(np.percentile(gammas, 75)),
            "p01": float(np.percentile(gammas, 1)),
            "p99": float(np.percentile(gammas, 99)),
        },
        "bias_beta": {
            "mean": float(np.mean(bias_betas)),
            "std": float(np.std(bias_betas, ddof=1)),
        },
        "bias_eta": {
            "mean": float(np.mean(bias_etas)),
            "std": float(np.std(bias_etas, ddof=1)),
        },
        "bias_gamma": {
            "mean": float(np.mean(bias_gammas)),
            "std": float(np.std(bias_gammas, ddof=1)),
        },
        "mse_beta": float(np.mean(bias_betas ** 2)),
        "mse_eta": float(np.mean(bias_etas ** 2)),
        "mse_gamma": float(np.mean(bias_gammas ** 2)),
    }


def run_fixed_sample_analysis():
    """
    运行固定样本的分析，记录完整 trace 数据

    Returns:
        固定样本分析结果
    """
    print("\n" + "=" * 70)
    print("固定样本曲线分析")
    print(f"样本数据: {FIXED_SAMPLE}")
    print("=" * 70)

    # Bernard 方法
    print("\n运行 Bernard 近似...")
    bernard_result = run_single_simulation(FIXED_SAMPLE, 'bernard', 0, trace=True)
    print(f"  β = {bernard_result.get('beta', 'N/A'):.6f}, γ = {bernard_result.get('gamma', 'N/A'):.2f}")

    # Exact 方法
    print("\n运行 精确中位秩...")
    exact_result = run_single_simulation(FIXED_SAMPLE, 'exact', 1, trace=True)
    print(f"  β = {exact_result.get('beta', 'N/A'):.6f}, γ = {exact_result.get('gamma', 'N/A'):.2f}")

    return {
        "data": FIXED_SAMPLE,
        "bernard": {
            "beta": bernard_result.get("beta"),
            "eta": bernard_result.get("eta"),
            "gamma": bernard_result.get("gamma"),
            "r2": bernard_result.get("r2"),
            "status": bernard_result.get("status"),
            "trace_data": bernard_result.get("trace_data"),
        },
        "exact": {
            "beta": exact_result.get("beta"),
            "eta": exact_result.get("eta"),
            "gamma": exact_result.get("gamma"),
            "r2": exact_result.get("r2"),
            "status": exact_result.get("status"),
            "trace_data": exact_result.get("trace_data"),
        }
    }


def main():
    print("=" * 70)
    print("案例10: 中位秩方法对比研究 (蒙特卡洛模拟 + 曲线对比)")
    print(f"样本量: n = {N_SAMPLES}")
    print(f"模拟次数: {N_SIMULATIONS} 次/方法")
    print(f"真实参数: β={TRUE_BETA}, η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"偏移量: δ={OFFSET}")
    print("=" * 70)

    # 初始化随机数生成器
    rng = np.random.default_rng(SEED)

    # 存储所有模拟结果
    all_results = []
    bernard_results = []
    exact_results = []

    # 生成所有数据集 (两种方法使用相同的数据)
    print("\n生成随机样本数据...")
    all_datasets = []
    for i in range(N_SIMULATIONS):
        data = generate_weibull_3p_samples(N_SAMPLES, TRUE_BETA, TRUE_ETA, TRUE_GAMMA, rng)
        all_datasets.append(data)

    # 运行 Bernard's approximation
    print(f"\n运行 Bernard's approximation ({N_SIMULATIONS} 次模拟)...")
    for i, data in enumerate(all_datasets):
        if (i + 1) % 100 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_single_simulation(data, 'bernard', i)
        bernard_results.append(result)
        all_results.append(result)

    # 运行精确中位秩
    print(f"\n运行 精确中位秩 ({N_SIMULATIONS} 次模拟)...")
    for i, data in enumerate(all_datasets):
        if (i + 1) % 100 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_single_simulation(data, 'exact', i + N_SIMULATIONS)
        exact_results.append(result)
        all_results.append(result)

    # 计算统计量
    print("\n计算统计量...")
    bernard_stats = calculate_statistics(bernard_results)
    exact_stats = calculate_statistics(exact_results)

    # 中位秩值对比
    print("\n中位秩值对比:")
    print(f"  {'i':<5} {'Bernard':<15} {'Exact':<15} {'差异':<15}")
    print("  " + "-" * 50)

    # 保存中位秩值对比数据
    median_rank_comparison = []
    for i in range(1, N_SAMPLES + 1):
        bernard_val = median_rank_bernard(i, N_SAMPLES)
        exact_val = median_rank_exact(i, N_SAMPLES)
        diff = exact_val - bernard_val
        print(f"  {i:<5} {bernard_val:<15.8f} {exact_val:<15.8f} {diff:+.8f}")
        median_rank_comparison.append({
            "i": i,
            "bernard": bernard_val,
            "exact": exact_val,
            "diff": diff
        })

    # 固定样本曲线分析
    fixed_sample_analysis = run_fixed_sample_analysis()

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case10", "data.json")
    print(f"\n输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output_data = {
        "simulation_params": {
            "n_samples": N_SAMPLES,
            "n_simulations": N_SIMULATIONS,
            "true_beta": TRUE_BETA,
            "true_eta": TRUE_ETA,
            "true_gamma": TRUE_GAMMA,
            "offset": OFFSET,
            "gamma_steps": GAMMA_STEPS,
            "seed": SEED,
        },
        "median_rank_comparison": median_rank_comparison,
        "bernard_stats": bernard_stats,
        "exact_stats": exact_stats,
        "bernard_results": bernard_results,
        "exact_results": exact_results,
        "fixed_sample": fixed_sample_analysis,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")

    # 打印汇总
    print("\n" + "=" * 100)
    print("汇总表")
    print("=" * 100)

    print(f"\n{'方法':<20} {'收敛率':<12} {'β偏差均值':<15} {'β偏差标准差':<15} {'γ偏差均值':<15} {'γ偏差标准差':<15}")
    print("-" * 90)

    print(f"{'Bernard近似':<20} {bernard_stats['convergence_rate']:<12.4f} "
          f"{bernard_stats.get('bias_beta', {}).get('mean', 'N/A'):<15.6f} "
          f"{bernard_stats.get('bias_beta', {}).get('std', 'N/A'):<15.6f} "
          f"{bernard_stats.get('bias_gamma', {}).get('mean', 'N/A'):<15.4f} "
          f"{bernard_stats.get('bias_gamma', {}).get('std', 'N/A'):<15.4f}")

    print(f"{'精确中位秩':<20} {exact_stats['convergence_rate']:<12.4f} "
          f"{exact_stats.get('bias_beta', {}).get('mean', 'N/A'):<15.6f} "
          f"{exact_stats.get('bias_beta', {}).get('std', 'N/A'):<15.6f} "
          f"{exact_stats.get('bias_gamma', {}).get('mean', 'N/A'):<15.4f} "
          f"{exact_stats.get('bias_gamma', {}).get('std', 'N/A'):<15.4f}")

    print("\n参数估计值统计:")
    print(f"{'方法':<15} {'β均值':<12} {'β标准差':<12} {'γ均值':<12} {'γ标准差':<12}")
    print("-" * 65)
    print(f"{'Bernard':<15} {bernard_stats.get('beta', {}).get('mean', 'N/A'):<12.4f} "
          f"{bernard_stats.get('beta', {}).get('std', 'N/A'):<12.4f} "
          f"{bernard_stats.get('gamma', {}).get('mean', 'N/A'):<12.2f} "
          f"{bernard_stats.get('gamma', {}).get('std', 'N/A'):<12.2f}")
    print(f"{'Exact':<15} {exact_stats.get('beta', {}).get('mean', 'N/A'):<12.4f} "
          f"{exact_stats.get('beta', {}).get('std', 'N/A'):<12.4f} "
          f"{exact_stats.get('gamma', {}).get('mean', 'N/A'):<12.2f} "
          f"{exact_stats.get('gamma', {}).get('std', 'N/A'):<12.2f}")

    # 固定样本结果
    print("\n固定样本曲线分析结果:")
    print(f"{'方法':<15} {'β估计':<12} {'γ估计':<12} {'状态':<15}")
    print("-" * 55)
    print(f"{'Bernard':<15} {fixed_sample_analysis['bernard'].get('beta', 'N/A'):<12.6f} "
          f"{fixed_sample_analysis['bernard'].get('gamma', 'N/A'):<12.2f} "
          f"{fixed_sample_analysis['bernard'].get('status', 'N/A'):<15}")
    print(f"{'Exact':<15} {fixed_sample_analysis['exact'].get('beta', 'N/A'):<12.6f} "
          f"{fixed_sample_analysis['exact'].get('gamma', 'N/A'):<12.2f} "
          f"{fixed_sample_analysis['exact'].get('status', 'N/A'):<15}")


if __name__ == "__main__":
    main()
