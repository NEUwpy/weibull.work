"""
⚠ 历史复现实验，不是当前默认 MDM 口径

案例13: 中位秩方法对比研究 (多样本量 + 多尺度参数)

研究内容:
- 对比两种中位秩方法: Bernard's approximation vs 精确中位秩
- 多样本量: n = 7, 10, 15
- 多尺度参数: η = 200, 1000, 5000 (分散性从小到大)
- 蒙特卡洛模拟: 各1000次/方法/样本量/η

输出:
- public/case-studies/mdm/case13/data.json

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from scipy.special import betaincinv


# ============== 中位秩函数 ==============
def median_rank_bernard(i: int, n: int) -> float:
    """Bernard's approximation for median rank"""
    return (i - 0.3) / (n + 0.4)


def median_rank_exact(i: int, n: int) -> float:
    """
    Exact median rank using inverse incomplete beta function.
    F(i,n) = B^(-1)(0.5; i, n-i+1)
    """
    return betaincinv(i, n - i + 1, 0.5)


# ============== MDM Case13 类 ==============
class MDMCase13:
    """
    支持多种中位秩方法的 MDM 实现
    """

    def __init__(self, data: list, rank_method: str = 'bernard'):
        self.data = np.array(sorted(data))
        self.n = len(data)
        self.rank_method = rank_method
        self.trace_data = None

    def _median_ranks(self) -> np.ndarray:
        """计算中位秩"""
        ranks = []
        for i in range(1, self.n + 1):
            if self.rank_method == 'exact':
                ranks.append(median_rank_exact(i, self.n))
            else:  # bernard
                ranks.append(median_rank_bernard(i, self.n))
        return np.array(ranks)

    def run(self, offset: float = 0.1, gamma_steps: int = 60, trace: bool = False):
        """
        运行 MDM 估计

        Returns:
            (beta, eta, gamma, r_squared, status)
        """
        t = self.data
        n = self.n

        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0:
                return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0 / beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        def find_best_beta_for_gamma(gamma):
            if gamma >= t[0]:
                return None, float('inf')

            # 离散搜索
            best_beta = 0.5
            best_sigma = float('inf')
            for beta in np.arange(0.1, 15.0, 0.01):
                sigma = calculate_eta_std(beta, gamma, t)
                if sigma < best_sigma:
                    best_sigma = sigma
                    best_beta = beta
            return best_beta, best_sigma

        t_min = t[0]
        gammas = np.linspace(0, t_min * 0.99, gamma_steps)

        sigma_mins = []
        best_betas = []

        for g in gammas:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins.append(sig)
            best_betas.append(b)

        sigma_mins = np.array(sigma_mins)
        best_betas = np.array(best_betas)
        grads = np.gradient(sigma_mins, gammas)

        diffs = grads - offset
        sign_changes = np.where(np.diff(np.sign(diffs)))[0]

        if len(sign_changes) == 0:
            # 扩展搜索
            gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
            sigma_mins2 = []
            best_betas2 = []

            for g in gammas2:
                b, sig = find_best_beta_for_gamma(g)
                sigma_mins2.append(sig)
                best_betas2.append(b)

            sigma_mins2 = np.array(sigma_mins2)
            best_betas2 = np.array(best_betas2)
            grads2 = np.gradient(sigma_mins2, gammas2)

            gammas = np.concatenate([gammas, gammas2])
            sigma_mins = np.concatenate([sigma_mins, sigma_mins2])
            best_betas = np.concatenate([best_betas, best_betas2])
            grads = np.concatenate([grads, grads2])

            diffs = grads - offset
            sign_changes = np.where(np.diff(np.sign(diffs)))[0]

        if len(sign_changes) == 0:
            return None, None, None, None, "no_intersection"

        # 线性插值找交点
        idx = sign_changes[-1]
        y1, y2 = diffs[idx], diffs[idx + 1]
        x1, x2 = gammas[idx], gammas[idx + 1]

        if y2 != y1:
            found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
        else:
            found_gamma = x1

        found_beta, _ = find_best_beta_for_gamma(found_gamma)

        denom = np.power(neg_ln_1_minus_F, 1.0 / found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)

        # R² 计算
        y_pred = np.log(neg_ln_1_minus_F)
        y_true = np.log((t - found_gamma) / found_eta)
        ss_res = np.sum((y_true - found_beta * y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), "success"

# 模拟参数 - 多个样本量
SAMPLE_SIZES = [7, 10, 15]  # 样本量列表
N_SIMULATIONS = 1000        # 每种方法的模拟次数

# 真实参数
TRUE_BETA = 2.0
ETA_VALUES = [200.0, 1000.0, 5000.0]  # 尺度参数列表 (分散性从小到大)
TRUE_GAMMA = 1000.0

# MDM参数
OFFSET = 0.1
GAMMA_STEPS = 60

# 随机种子 (用于可重复性)
SEED = 42


def generate_weibull_3p_samples(n: int, beta: float, eta: float, gamma: float, rng: np.random.Generator) -> list:
    """
    生成三参数Weibull分布的随机样本

    Weibull 3P: F(t) = 1 - exp(-((t - gamma) / eta)^beta)
    逆变换: t = gamma + eta * (-ln(1 - U))^(1/beta)
    """
    u = rng.uniform(0, 1, n)
    samples = gamma + eta * np.power(-np.log(1 - u), 1.0 / beta)
    return sorted(samples.tolist())


def run_single_simulation(data: list, rank_method: str, sim_id: int, trace: bool = False, true_eta: float = TRUE_GAMMA):
    """
    运行单次MDM估计
    """
    try:
        mdm = MDMCase13(data, rank_method=rank_method)
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
            result["bias_eta"] = eta - true_eta
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


def calculate_statistics(results: list, true_eta: float) -> dict:
    """
    计算统计量
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


def generate_median_rank_comparison(n: int) -> list:
    """
    生成中位秩值对比数据
    """
    comparison = []
    for i in range(1, n + 1):
        bernard_val = median_rank_bernard(i, n)
        exact_val = median_rank_exact(i, n)
        diff = exact_val - bernard_val
        comparison.append({
            "i": i,
            "bernard": bernard_val,
            "exact": exact_val,
            "diff": diff
        })
    return comparison


def run_simulations_for_sample_size(n: int, eta: float, rng: np.random.Generator) -> dict:
    """
    运行指定样本量和尺度参数的所有模拟
    """
    print(f"\n{'='*70}")
    print(f"样本量 n = {n}, 尺度参数 η = {eta}")
    print(f"{'='*70}")

    # 生成所有数据集
    print(f"生成 {N_SIMULATIONS} 个随机样本...")
    all_datasets = []
    for i in range(N_SIMULATIONS):
        data = generate_weibull_3p_samples(n, TRUE_BETA, eta, TRUE_GAMMA, rng)
        all_datasets.append(data)

    # 运行 Bernard's approximation
    print(f"运行 Bernard's approximation ({N_SIMULATIONS} 次模拟)...")
    bernard_results = []
    for i, data in enumerate(all_datasets):
        if (i + 1) % 200 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_single_simulation(data, 'bernard', i, true_eta=eta)
        bernard_results.append(result)

    # 运行精确中位秩
    print(f"运行 精确中位秩 ({N_SIMULATIONS} 次模拟)...")
    exact_results = []
    for i, data in enumerate(all_datasets):
        if (i + 1) % 200 == 0:
            print(f"  进度: {i + 1}/{N_SIMULATIONS}")
        result = run_single_simulation(data, 'exact', i + N_SIMULATIONS, true_eta=eta)
        exact_results.append(result)

    # 计算统计量
    print("计算统计量...")
    bernard_stats = calculate_statistics(bernard_results, eta)
    exact_stats = calculate_statistics(exact_results, eta)

    # 中位秩值对比
    median_rank_comparison = generate_median_rank_comparison(n)

    # 打印汇总
    print(f"\n汇总 (n={n}, η={eta}):")
    print(f"  Bernard: β偏差={bernard_stats.get('bias_beta', {}).get('mean', 'N/A'):.6f}, "
          f"收敛率={bernard_stats['convergence_rate']:.2%}")
    print(f"  Exact:   β偏差={exact_stats.get('bias_beta', {}).get('mean', 'N/A'):.6f}, "
          f"收敛率={exact_stats['convergence_rate']:.2%}")

    return {
        "n": n,
        "median_rank_comparison": median_rank_comparison,
        "bernard_stats": bernard_stats,
        "exact_stats": exact_stats,
        "bernard_results": bernard_results,
        "exact_results": exact_results,
    }


def run_simulations_for_eta(eta: float, rng: np.random.Generator) -> dict:
    """
    运行指定尺度参数的所有样本量模拟
    """
    print(f"\n{'#'*70}")
    print(f"# 尺度参数 η = {eta}")
    print(f"{'#'*70}")

    sample_results = []
    for n in SAMPLE_SIZES:
        result = run_simulations_for_sample_size(n, eta, rng)
        sample_results.append(result)

    return {
        "eta": eta,
        "sample_results": sample_results,
    }


def main():
    print("=" * 70)
    print("案例13: 中位秩方法对比研究 (多样本量 + 多尺度参数)")
    print(f"样本量: {SAMPLE_SIZES}")
    print(f"尺度参数: {ETA_VALUES}")
    print(f"模拟次数: {N_SIMULATIONS} 次/方法/样本量/η")
    print(f"真实参数: β={TRUE_BETA}, γ={TRUE_GAMMA}")
    print(f"偏移量: δ={OFFSET}")
    print("=" * 70)

    # 初始化随机数生成器
    rng = np.random.default_rng(SEED)

    # 存储所有尺度参数的结果
    all_eta_results = []

    # 对每个尺度参数运行模拟
    for eta in ETA_VALUES:
        result = run_simulations_for_eta(eta, rng)
        all_eta_results.append(result)

    # 构建输出数据
    output_data = {
        "simulation_params": {
            "sample_sizes": SAMPLE_SIZES,
            "eta_values": ETA_VALUES,
            "n_simulations": N_SIMULATIONS,
            "true_beta": TRUE_BETA,
            "true_gamma": TRUE_GAMMA,
            "offset": OFFSET,
            "gamma_steps": GAMMA_STEPS,
            "seed": SEED,
        },
        "eta_results": all_eta_results,
    }

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case13", "data.json")
    print(f"\n输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")

    # 打印最终汇总表
    print("\n" + "=" * 120)
    print("最终汇总表")
    print("=" * 120)

    for er in all_eta_results:
        eta = er["eta"]
        print(f"\n{'='*60}")
        print(f"η = {eta}")
        print(f"{'='*60}")
        print(f"\n{'n':<6} {'方法':<12} {'收敛率':<10} {'β偏差':<12} {'β标准差':<12} {'γ偏差':<12} {'γ标准差':<12}")
        print("-" * 80)

        for sr in er["sample_results"]:
            n = sr["n"]
            bs = sr["bernard_stats"]
            es = sr["exact_stats"]

            print(f"{n:<6} {'Bernard':<12} {bs['convergence_rate']:<10.2%} "
                  f"{bs.get('bias_beta', {}).get('mean', 'N/A'):<12.6f} "
                  f"{bs.get('beta', {}).get('std', 'N/A'):<12.4f} "
                  f"{bs.get('bias_gamma', {}).get('mean', 'N/A'):<12.2f} "
                  f"{bs.get('gamma', {}).get('std', 'N/A'):<12.2f}")

            print(f"{'':<6} {'Exact':<12} {es['convergence_rate']:<10.2%} "
                  f"{es.get('bias_beta', {}).get('mean', 'N/A'):<12.6f} "
                  f"{es.get('beta', {}).get('std', 'N/A'):<12.4f} "
                  f"{es.get('bias_gamma', {}).get('mean', 'N/A'):<12.2f} "
                  f"{es.get('gamma', {}).get('std', 'N/A'):<12.2f}")
            print("-" * 80)


if __name__ == "__main__":
    main()
