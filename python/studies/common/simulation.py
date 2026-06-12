"""
统一蒙特卡洛模拟服务。

面向 API 和研究脚本复用：样本生成统一走 sample.generate_sample()，
方法估计统一走 runner.run_method()。新增参数估计方法后，只要在
methods/{method}.py 实现并在 methods.registry 注册，就能被这里调用。
"""

from typing import Dict, Iterable, List, Optional

from methods.registry import resolve_method
from studies.common.runner import run_method
from studies.common.sample import generate_sample


def _canonical_method_id(method_id: str) -> str:
    try:
        resolved, _ = resolve_method(method_id)
        return resolved
    except Exception:
        return method_id.lower()


def _method_kwargs(method_id: str, offset: Optional[float] = None) -> Dict:
    canonical = _canonical_method_id(method_id)
    if canonical == "mdm":
        return {"trace": False, "offset": 0.1 if offset is None else offset}
    return {"trace": False}


def _actual_offset(method_id: str, offset: Optional[float]) -> Optional[float]:
    if _canonical_method_id(method_id) == "mdm":
        return 0.1 if offset is None else offset
    return offset


def _bias(est_value: Optional[float], true_value: float) -> Optional[float]:
    if est_value is None:
        return None
    return est_value - true_value


def simulate_method(
    method_id: str,
    beta: float,
    eta: float,
    gamma: float,
    n: int,
    rep: int,
    seed: Optional[int] = None,
    offset: Optional[float] = None,
) -> List[Dict]:
    """运行单一方法的蒙特卡洛模拟，返回 API JSON 行。"""
    rows = []
    actual_offset = _actual_offset(method_id, offset)
    method_kwargs = _method_kwargs(method_id, actual_offset)

    for sim_id in range(1, rep + 1):
        sample = generate_sample(beta, eta, gamma, n, sim_id, seed=seed)
        estimate = run_method(method_id, sample, **method_kwargs)

        est_beta = estimate["beta_hat"]
        est_eta = estimate["eta_hat"]
        est_gamma = estimate["gamma_hat"]

        rows.append({
            "beta_true": beta,
            "eta_true": eta,
            "gamma": gamma,
            "sample_size": n,
            "offset_value": actual_offset,
            "sim_id": sim_id,
            "est_beta": est_beta,
            "est_eta": est_eta,
            "est_gamma": est_gamma,
            "bias_beta": _bias(est_beta, beta),
            "bias_eta": _bias(est_eta, eta),
            "bias_gamma": _bias(est_gamma, gamma),
            "r_squared": estimate["r_squared"],
        })

    return rows


def iter_batch_rows(
    method_id: str,
    true_beta: float,
    true_eta: float,
    true_gamma: float,
    sample_sizes: Iterable[int],
    beta_values: Optional[Iterable[float]],
    offset_values: Optional[Iterable[float]],
    num_simulations: int,
    seed: Optional[int] = None,
) -> Iterable[Dict]:
    """运行批量蒙特卡洛模拟，产出 main.py CSV 所需的逐行字典。"""
    betas = list(beta_values) if beta_values is not None else [None]
    offsets = list(offset_values) if offset_values is not None else [None]

    for sample_size in sample_sizes:
        for beta_value in betas:
            current_true_beta = beta_value if beta_value is not None else true_beta

            for offset_value in offsets:
                actual_offset = _actual_offset(method_id, offset_value)
                method_kwargs = _method_kwargs(method_id, actual_offset)

                for sim_id in range(1, num_simulations + 1):
                    sample = generate_sample(
                        current_true_beta,
                        true_eta,
                        true_gamma,
                        sample_size,
                        sim_id,
                        seed=seed,
                    )
                    estimate = run_method(method_id, sample, **method_kwargs)

                    est_beta = estimate["beta_hat"]
                    est_eta = estimate["eta_hat"]
                    est_gamma = estimate["gamma_hat"]

                    row = {
                        "beta_true": true_beta,
                        "eta_true": true_eta,
                        "gamma_true": true_gamma,
                        "sample_size": sample_size,
                        "sim_id": sim_id,
                        "est_beta": est_beta,
                        "est_eta": est_eta,
                        "est_gamma": est_gamma,
                        "bias_beta": _bias(est_beta, current_true_beta),
                        "bias_eta": _bias(est_eta, true_eta),
                        "bias_gamma": _bias(est_gamma, true_gamma),
                        "r_squared": estimate["r_squared"],
                    }

                    if beta_values is not None:
                        row["beta_value"] = beta_value
                    if offset_values is not None:
                        row["offset_value"] = actual_offset

                    yield row
