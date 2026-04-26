from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Union
import sys
import os
import io
import numpy as np

# Add methods directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

from methods.registry import resolve_method
from methods.mdm import MDM
from methods.wmle import WMLE
from base import MethodResult

app = FastAPI()

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://weibull.work,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CalculationRequest(BaseModel):
    method: str
    data: List[float]
    trace: Optional[bool] = False
    offset: Optional[float] = None
    params: Optional[dict] = {}

class Surface3DRequest(BaseModel):
    method: str
    data: List[float]
    trace_data: Optional[dict] = None

class BatchSimulationRequest(BaseModel):
    method: str
    true_beta: float
    true_eta: float
    true_gamma: float
    sample_sizes: List[int]
    betas: Optional[List[float]] = None
    offsets: Optional[List[float]] = None
    num_simulations: int = 100

class MonteCarloRequest(BaseModel):
    """蒙特卡洛模拟请求 - 用于方法对比功能"""
    method: str
    beta: float              # 真实β
    eta: float               # 真实η
    n: int                   # 样本量
    rep: int = 100           # 重复次数
    seed: int = 42           # 随机种子
    gamma: float = 0         # 真实γ（默认0）
    offset: Optional[float] = None  # MDM偏移量

class CalculationResponse(BaseModel):
    beta: Optional[float]
    eta: Optional[float]
    gamma: Optional[float]
    rSquared: Optional[float]
    method: str
    converged: Union[bool, str] = True
    trace_data: Optional[Any] = None


def _extract_result(res, method_id, trace_data=None):
    """
    从 run() 返回值中提取统一的响应字典。
    兼容三种格式：
    - MethodResult 对象（新）
    - 5 元素 list/tuple [beta, eta, gamma, r2, converged]（较新）
    - 4 元素 list/tuple [beta, eta, gamma, r2]（旧）
    """
    if isinstance(res, MethodResult):
        converged = res.converged
        return {
            "beta": float(res.beta) if res.beta is not None else None,
            "eta": float(res.eta) if res.eta is not None else None,
            "gamma": float(res.gamma) if res.gamma is not None else None,
            "rSquared": float(res.r_squared) if res.r_squared is not None else None,
            "method": method_id,
            "converged": converged if isinstance(converged, str) else bool(converged),
            "trace_data": trace_data,
        }

    # 旧的 list/tuple 格式
    converged = res[4] if len(res) >= 5 else True
    if isinstance(converged, str):
        converged_value = converged
    else:
        converged_value = bool(converged)

    return {
        "beta": float(res[0]) if res[0] is not None else None,
        "eta": float(res[1]) if res[1] is not None else None,
        "gamma": float(res[2]) if res[2] is not None else None,
        "rSquared": float(res[3]) if res[3] is not None else None,
        "method": method_id,
        "converged": converged_value,
        "trace_data": trace_data,
    }


def _run_algorithm(method_id, AlgorithmClass, data, trace=False, offset=None):
    """执行算法并返回结果，处理不同方法签名差异"""
    algo_instance = AlgorithmClass(data)
    try:
        if method_id == 'mdm' and offset is not None:
            res = algo_instance.run(trace=trace, offset=offset)
        else:
            res = algo_instance.run(trace=trace)
    except TypeError:
        res = algo_instance.run()

    trace_data = algo_instance.trace_data if trace else None
    return _extract_result(res, method_id, trace_data)


def _run_with_fallback(method_id, AlgorithmClass, data, trace=False, offset=None):
    """执行算法，失败时自动 fallback 到 WMLE"""
    try:
        return _run_algorithm(method_id, AlgorithmClass, data, trace=trace, offset=offset)
    except Exception as e:
        print(f"Algorithm {method_id} failed: {e}. Fallback to WMLE.")
        try:
            return _run_algorithm(f"{method_id}_fallback_wmle", WMLE, data, trace=trace)
        except Exception as fallback_error:
            raise HTTPException(status_code=500,
                                detail=f"Calculation failed: {e} -> Fallback WMLE failed: {fallback_error}")


@app.post("/calculate", response_model=CalculationResponse)
async def calculate(req: CalculationRequest):
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    selected_method_id, AlgorithmClass = resolve_method(req.method)
    return _run_with_fallback(selected_method_id, AlgorithmClass, req.data,
                              trace=req.trace, offset=req.offset)

@app.post("/calculate_3d_surface")
async def calculate_3d_surface(req: Surface3DRequest):
    """
    Calculate 3D surface data for MDM method.
    Computes sigma(beta, gamma) for 20 gamma values with 50 beta points each.
    """
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    if req.method.lower() != "mdm":
        raise HTTPException(status_code=400, detail="3D surface only supported for MDM method")

    try:
        return _run_algorithm("mdm", MDM, req.data, trace=True, offset=0.1)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D surface calculation failed: {str(e)}")

@app.post("/batch_simulation")
async def batch_simulation(req: BatchSimulationRequest):
    """
    Batch Monte Carlo simulation for case study.

    Returns CSV with columns:
    - beta_true, eta_true, gamma_true (true parameters)
    - sample_size (n)
    - beta_value, offset_value (for multi-dimension cases)
    - sim_id (simulation index 1-100)
    - est_beta, est_eta, est_gamma (estimated parameters)
    - bias_beta, bias_eta, bias_gamma (bias = estimated - true)
    - r_squared (goodness of fit)
    """
    try:
        selected_method_id, AlgorithmClass = resolve_method(req.method)

        # Generate CSV content
        output = io.StringIO()
        # Header
        header = ["beta_true", "eta_true", "gamma_true", "sample_size"]
        if req.betas:
            header.append("beta_value")
        if req.offsets:
            header.append("offset_value")
        header.extend(["sim_id", "est_beta", "est_eta", "est_gamma", "bias_beta", "bias_eta", "bias_gamma", "r_squared"])
        output.write(",".join(header) + "\n")

        # Iterate over all parameter combinations
        for sample_size in req.sample_sizes:
            # For beta dimension variation
            beta_values = req.betas if req.betas else [None]
            # For offset dimension variation
            offset_values = req.offsets if req.offsets else [None]

            for beta_val in beta_values:
                for offset_val in offset_values:
                    # Determine true beta for this iteration
                    current_true_beta = beta_val if beta_val is not None else req.true_beta

                    # Run Monte Carlo simulations
                    for sim_id in range(1, req.num_simulations + 1):
                        # Generate sample from true Weibull distribution
                        np.random.seed(sim_id + sample_size * 1000 + int((beta_val or 0) * 100) + int((offset_val or 0) * 1000))
                        u = np.random.uniform(0, 1, sample_size)
                        # Weibull inverse CDF: x = gamma + eta * (-ln(1-u))^(1/beta)
                        sample = req.true_gamma + req.true_eta * (-np.log(1 - u)) ** (1 / current_true_beta)
                        sample = np.sort(sample)

                        # Estimate parameters using selected method
                        try:
                            algo_instance = AlgorithmClass(sample.tolist())

                            # Run with offset if MDM
                            if selected_method_id == 'mdm' and offset_val is not None:
                                res = algo_instance.run(trace=False, offset=offset_val)
                            else:
                                res = algo_instance.run(trace=False)

                            est_beta = float(res[0]) if res[0] is not None else 0
                            est_eta = float(res[1]) if res[1] is not None else 0
                            est_gamma = float(res[2]) if res[2] is not None else 0
                            r_squared = float(res[3]) if res[3] is not None else 0
                        except (NotImplementedError, Exception) as e:
                            print(f"Simulation failed: {e}")
                            est_beta, est_eta, est_gamma, r_squared = 0, 0, 0, 0

                        # Calculate biases
                        bias_beta = est_beta - current_true_beta
                        bias_eta = est_eta - req.true_eta
                        bias_gamma = est_gamma - req.true_gamma

                        # Write row
                        row = [
                            str(req.true_beta),
                            str(req.true_eta),
                            str(req.true_gamma),
                            str(sample_size)
                        ]
                        if req.betas:
                            row.append(str(beta_val) if beta_val is not None else "")
                        if req.offsets:
                            row.append(str(offset_val) if offset_val is not None else "")
                        row.extend([
                            str(sim_id),
                            f"{est_beta:.6f}",
                            f"{est_eta:.6f}",
                            f"{est_gamma:.6f}",
                            f"{bias_beta:.6f}",
                            f"{bias_eta:.6f}",
                            f"{bias_gamma:.6f}",
                            f"{r_squared:.6f}"
                        ])
                        output.write(",".join(row) + "\n")

        # Return as CSV file
        csv_content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=batch_simulation.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch simulation failed: {str(e)}")

@app.post("/monte_carlo_simulate")
async def monte_carlo_simulate(req: MonteCarloRequest):
    """
    蒙特卡洛模拟 - 用于方法对比功能

    生成 rep 个威布尔分布样本，对每个样本执行参数估计，
    返回与预计算chunk相同格式的JSON数据。
    """
    # 参数验证
    errors = []
    if not req.method:
        errors.append("缺少参数: method")
    if req.beta is None or req.beta <= 0:
        errors.append(f"beta 必须大于 0，当前值: {req.beta}")
    if req.eta is None or req.eta <= 0:
        errors.append(f"eta 必须大于 0，当前值: {req.eta}")
    if req.n is None or req.n < 3:
        errors.append(f"n (样本量) 必须至少为 3，当前值: {req.n}")
    if req.rep is None or req.rep < 1:
        errors.append(f"rep (重复次数) 必须至少为 1，当前值: {req.rep}")

    if errors:
        raise HTTPException(status_code=400, detail=f"参数验证失败: {'; '.join(errors)}")

    try:
        selected_method_id, AlgorithmClass = resolve_method(req.method)

        print(f"[MonteCarlo] 开始模拟: method={req.method}, beta={req.beta}, eta={req.eta}, gamma={req.gamma}, n={req.n}, rep={req.rep}")

        rows = []

        for sim_id in range(1, req.rep + 1):
            # 使用种子生成可复现的随机数
            np.random.seed(req.seed + sim_id)

            # 生成威布尔分布样本
            u = np.random.uniform(0, 1, req.n)
            # Weibull inverse CDF: x = gamma + eta * (-ln(1-u))^(1/beta)
            sample = req.gamma + req.eta * (-np.log(1 - u)) ** (1 / req.beta)
            sample = np.sort(sample)

            # 执行参数估计
            try:
                algo_instance = AlgorithmClass(sample.tolist())

                # MDM支持offset参数，默认使用0.1
                if selected_method_id == 'mdm':
                    offset_val = req.offset if req.offset is not None else 0.1
                    res = algo_instance.run(trace=False, offset=offset_val)
                else:
                    res = algo_instance.run(trace=False)

                est_beta = float(res[0]) if res[0] is not None else None
                est_eta = float(res[1]) if res[1] is not None else None
                est_gamma = float(res[2]) if res[2] is not None else None
                r_squared = float(res[3]) if res[3] is not None else None
            except Exception as e:
                print(f"Simulation {sim_id} failed: {e}")
                est_beta, est_eta, est_gamma, r_squared = None, None, None, None

            # 计算偏差
            bias_beta = est_beta - req.beta if est_beta is not None else None
            bias_eta = est_eta - req.eta if est_eta is not None else None
            bias_gamma = est_gamma - req.gamma if est_gamma is not None else None

            rows.append({
                "beta_true": req.beta,
                "eta_true": req.eta,
                "gamma": req.gamma,
                "sample_size": req.n,
                "offset_value": req.offset,
                "sim_id": sim_id,
                "est_beta": est_beta,
                "est_eta": est_eta,
                "est_gamma": est_gamma,
                "bias_beta": bias_beta,
                "bias_eta": bias_eta,
                "bias_gamma": bias_gamma,
                "r_squared": r_squared
            })

        print(f"[MonteCarlo] 完成: method={req.method}, 成功 {len(rows)}/{req.rep} 次")
        return {"rows": rows, "count": len(rows), "success": True}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[MonteCarlo] 错误: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Monte Carlo simulation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


# ============================================================
# AI Methods — 关系建立: MDM 偏移量优化
# ============================================================

import torch
import torch.nn as nn

class DeltaMLP_N2(nn.Module):
    """路线 1 模型：样本 → 最优 δ
    Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid
    """
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


class DeltaMLP_N1(nn.Module):
    """路线 2 公共模型：(β,η,γ) 真值 → 最优 δ
    Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# 模型缓存
_ai_models_n2 = {}   # 路线 1 模型（按 n 缓存）
_ai_model_n1 = None  # 路线 2 公共模型


# ============================================================
# AI Methods — 直接估计: 端到端参数预测
# ============================================================

class DirectEstimationMLP(nn.Module):
    """直接估计模型：样本 → (β, η, γ)
    Linear(n,128)→ReLU→Linear(128,64)→ReLU→Linear(64,32)→ReLU→Linear(32,3)
    输出层线性，直接输出原始值
    """
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 3),
        )

    def forward(self, x):
        return self.net(x)


# 直接估计模型缓存
_ai_direct_models = {}  # 按 n 缓存

def _load_delta_model(n: int):
    """按样本量 n 加载路线 1 的 N₂ 模型"""
    if n in _ai_models_n2:
        return _ai_models_n2[n]

    models_dir = os.path.join(os.path.dirname(__file__), 'models', 'mdm_delta')
    model_path = os.path.join(models_dir, f'n{n}_model.pth')

    if not os.path.exists(model_path):
        return None

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model = DeltaMLP_N2(input_dim=checkpoint['input_dim'])
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    delta_min = checkpoint.get('delta_min', 0.01)
    delta_max = checkpoint.get('delta_max', 0.50)
    scaler_params = checkpoint.get('scaler_params', None)

    _ai_models_n2[n] = (model, delta_min, delta_max, scaler_params)
    return _ai_models_n2[n]


def _load_delta_params_model():
    """加载路线 2 的 N₁ 公共模型（真值→δ）"""
    global _ai_model_n1
    if _ai_model_n1 is not None:
        return _ai_model_n1

    models_dir = os.path.join(os.path.dirname(__file__), 'models', 'mdm_delta')
    model_path = os.path.join(models_dir, 'delta_from_params.pth')

    if not os.path.exists(model_path):
        return None

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model = DeltaMLP_N1()
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    delta_min = checkpoint.get('delta_min', 0.01)
    delta_max = checkpoint.get('delta_max', 0.50)
    scaler_params = checkpoint.get('scaler_params', None)

    _ai_model_n1 = (model, delta_min, delta_max, scaler_params)
    return _ai_model_n1


class AIDeltaRequest(BaseModel):
    """AI 偏移量预测请求"""
    data: List[float]

class AIDeltaResponse(BaseModel):
    """AI 偏移量预测响应"""
    optimal_delta: float
    model_n: int
    confidence: Optional[str] = None


@app.post("/ai/relationship/mdm", response_model=AIDeltaResponse)
async def ai_predict_delta(req: AIDeltaRequest):
    """
    路线 1：AI 直接预测 MDM 最优偏移量 δ（N₂ 模型）

    输入：样本数据（排序后的失效时间）
    输出：AI 预测的最优偏移量 δ
    """
    if len(req.data) < 3:
        raise HTTPException(status_code=400, detail="样本量至少为 3")

    n = len(req.data)

    # 加载 N₂ 模型
    result = _load_delta_model(n)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到样本量 n={n} 的 N₂ 模型。当前可用模型: {list(_ai_models_n2.keys())}"
        )

    model, delta_min, delta_max, scaler_params = result

    # 排序
    sample = sorted(req.data)
    sample_arr = np.array(sample).reshape(1, -1)

    # 标准化输入
    if scaler_params:
        x_mean = np.array(scaler_params['x_mean'])
        x_std = np.array(scaler_params['x_std'])
        sample_arr = (sample_arr - x_mean) / x_std

    sample_tensor = torch.FloatTensor(sample_arr)

    # 推理
    with torch.no_grad():
        pred = model(sample_tensor).squeeze().item()

    # 缩放到 δ 范围
    optimal_delta = pred * (delta_max - delta_min) + delta_min

    # 置信度评估（基于是否接近边界）
    if optimal_delta <= delta_min + 0.01 or optimal_delta >= delta_max - 0.01:
        confidence = "low"
    elif optimal_delta <= delta_min + 0.03 or optimal_delta >= delta_max - 0.03:
        confidence = "medium"
    else:
        confidence = "high"

    return AIDeltaResponse(
        optimal_delta=round(optimal_delta, 4),
        model_n=n,
        confidence=confidence
    )


# ============================================================
# 路线 2：迭代逼近
# ============================================================

class AIIterateRequest(BaseModel):
    """路线 2 迭代请求"""
    data: List[float]

class AIIterateStep(BaseModel):
    """迭代历史中的单步"""
    step: int
    delta: float
    beta: Optional[float] = None
    eta: Optional[float] = None
    gamma: Optional[float] = None
    mdm_status: str  # "ok" | "no_intersection" | "diverged"

class AIIterateResponse(BaseModel):
    """路线 2 迭代响应"""
    final_delta: float
    final_params: Optional[dict] = None  # {beta, eta, gamma}
    iterations: List[AIIterateStep]
    converged: bool
    convergence_reason: str  # "delta_stable" | "max_iterations" | "mdm_failed"


@app.post("/ai/relationship/mdm/iterate", response_model=AIIterateResponse)
async def ai_predict_delta_iterate(req: AIIterateRequest):
    """
    路线 2：迭代逼近预测 MDM 最优偏移量 δ

    流程：
    1. δ₀ = 0.5
    2. MDM(δₖ) → (β̂ₖ, η̂ₖ, γ̂ₖ)
    3. N₁(β̂ₖ, η̂ₖ, γ̂ₖ) → δₖ₊₁
    4. 检验收敛：|δₖ₊₁ - δₖ| < 0.001 或 最大 10 步 或 MDM 失败
    """
    if len(req.data) < 3:
        raise HTTPException(status_code=400, detail="样本量至少为 3")

    # 加载 N₁ 模型
    n1_result = _load_delta_params_model()
    if n1_result is None:
        raise HTTPException(
            status_code=404,
            detail="未找到路线 2 的 N₁ 公共模型 (delta_from_params.pth)"
        )

    n1_model, delta_min, delta_max, scaler_params = n1_result

    # 排序样本
    sample = sorted(req.data)
    sample_arr = np.array(sample)

    # 迭代参数
    delta_current = 0.5
    max_iterations = 10
    convergence_threshold = 0.001
    iterations = []
    converged = False
    convergence_reason = "max_iterations"
    final_params = None

    for step in range(max_iterations):
        # 运行 MDM
        try:
            algo = MDM(sample, rank_method='bernard')
            mdm_result = algo.run(
                trace=False,
                offset=delta_current,
                gamma_steps=60,
                rank_method='bernard'
            )
        except Exception:
            iterations.append(AIIterateStep(
                step=step,
                delta=round(delta_current, 6),
                mdm_status="mdm_failed"
            ))
            convergence_reason = "mdm_failed"
            break

        # 检查 MDM 是否有解
        if mdm_result[4] == "no_intersection":
            iterations.append(AIIterateStep(
                step=step,
                delta=round(delta_current, 6),
                mdm_status="no_intersection"
            ))
            convergence_reason = "mdm_failed"
            break

        est_beta, est_eta, est_gamma = mdm_result[0], mdm_result[1], mdm_result[2]

        # 检查是否发散
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            iterations.append(AIIterateStep(
                step=step,
                delta=round(delta_current, 6),
                beta=est_beta,
                eta=est_eta,
                gamma=est_gamma,
                mdm_status="diverged"
            ))
            convergence_reason = "mdm_failed"
            break

        iterations.append(AIIterateStep(
            step=step,
            delta=round(delta_current, 6),
            beta=round(est_beta, 4),
            eta=round(est_eta, 4),
            gamma=round(est_gamma, 4),
            mdm_status="ok"
        ))

        # 用 N₁ 预测下一个 δ
        params_arr = np.array([[est_beta, est_eta, est_gamma]])

        # 标准化输入
        if scaler_params:
            x_mean = np.array(scaler_params['x_mean'])
            x_std = np.array(scaler_params['x_std'])
            params_arr = (params_arr - x_mean) / x_std

        params_tensor = torch.FloatTensor(params_arr)
        with torch.no_grad():
            pred = n1_model(params_tensor).squeeze().item()

        delta_new = pred * (delta_max - delta_min) + delta_min

        # 更新最终参数
        final_params = {
            "beta": round(est_beta, 4),
            "eta": round(est_eta, 4),
            "gamma": round(est_gamma, 4)
        }

        # 检验收敛
        if abs(delta_new - delta_current) < convergence_threshold:
            delta_current = delta_new
            converged = True
            convergence_reason = "delta_stable"
            iterations.append(AIIterateStep(
                step=step + 1,
                delta=round(delta_new, 6),
                mdm_status="converged"
            ))
            break

        delta_current = delta_new

    return AIIterateResponse(
        final_delta=round(delta_current, 6),
        final_params=final_params,
        iterations=iterations,
        converged=converged,
        convergence_reason=convergence_reason
    )


# ============================================================
# 直接估计：端到端参数预测
# ============================================================

def _load_direct_estimation_model(n: int, scheme: str = 'a1'):
    """按样本量 n 和预处理方案加载直接估计模型"""
    cache_key = f'{n}_{scheme}'
    if cache_key in _ai_direct_models:
        return _ai_direct_models[cache_key]

    models_dir = os.path.join(os.path.dirname(__file__), 'models', 'direct_estimation')

    if scheme == 'b1':
        model_path = os.path.join(models_dir, 'b1_model.pth')
    else:
        suffix = f'_{scheme}' if scheme != 'a1' else ''
        model_path = os.path.join(models_dir, f'n{n}{suffix}_model.pth')

    if not os.path.exists(model_path):
        return None

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model = DirectEstimationMLP(input_dim=checkpoint['input_dim'])
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    scaler_params = checkpoint.get('scaler_params', None)
    y_scaler = checkpoint.get('y_scaler', None)
    preprocessing = checkpoint.get('preprocessing', 'a1')
    n_max = checkpoint.get('n_max', None)

    _ai_direct_models[cache_key] = (model, scaler_params, y_scaler, preprocessing, n_max)
    return _ai_direct_models[cache_key]


class AIDirectEstimationRequest(BaseModel):
    """直接估计请求"""
    data: List[float]
    scheme: str = 'a1'  # 预处理方案: a1, a2, a3, b1, b2, c1, c2, c3


class AIDirectEstimationResponse(BaseModel):
    """直接估计响应"""
    beta: float
    eta: float
    gamma: float
    model_n: int


@app.post("/ai/direct-estimation", response_model=AIDirectEstimationResponse)
async def ai_direct_estimation(req: AIDirectEstimationRequest):
    """
    直接估计：AI 端到端直接输出 β、η、γ

    输入：样本数据（排序后的失效时间）+ 预处理方案
    输出：AI 预测的 β（形状参数）、η（尺度参数）、γ（位置参数）
    """
    if len(req.data) < 3:
        raise HTTPException(status_code=400, detail="样本量至少为 3")

    n = len(req.data)
    scheme = req.scheme

    # 加载模型
    result = _load_direct_estimation_model(n, scheme)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到方案 {scheme} 样本量 n={n} 的直接估计模型"
        )

    model, scaler_params, y_scaler, preprocessing, n_max = result

    # 排序
    sample = sorted(req.data)
    sample_arr = np.array(sample).reshape(1, -1)

    # 预处理
    if preprocessing == 'a2':
        t_bar = np.mean(sample_arr, axis=1, keepdims=True)
        t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
        sample_arr = np.concatenate([sample_arr / t_bar_safe, t_bar], axis=1)
    elif preprocessing == 'a3':
        t_min = np.min(sample_arr, axis=1, keepdims=True)
        sample_arr = sample_arr - t_min
    elif preprocessing == 'c1':
        t_bar = np.mean(sample_arr, axis=1, keepdims=True)
        t_std = np.std(sample_arr, axis=1, keepdims=True)
        t_min = np.min(sample_arr, axis=1, keepdims=True)
        t_max = np.max(sample_arr, axis=1, keepdims=True)
        sample_arr = np.concatenate([t_bar, t_std, t_min, t_max], axis=1)
    elif preprocessing == 'c2':
        from scipy import stats
        t_bar = np.mean(sample_arr, axis=1, keepdims=True)
        t_std = np.std(sample_arr, axis=1, keepdims=True)
        t_min = np.min(sample_arr, axis=1, keepdims=True)
        t_max = np.max(sample_arr, axis=1, keepdims=True)
        t_median = np.median(sample_arr, axis=1, keepdims=True)
        skewness = np.array([stats.skew(sample_arr[0])]).reshape(1, -1)
        kurtosis = np.array([stats.kurtosis(sample_arr[0])]).reshape(1, -1)
        sample_arr = np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median], axis=1)
    elif preprocessing == 'c3':
        from scipy import stats
        t_bar = np.mean(sample_arr, axis=1, keepdims=True)
        t_std = np.std(sample_arr, axis=1, keepdims=True)
        t_min = np.min(sample_arr, axis=1, keepdims=True)
        t_max = np.max(sample_arr, axis=1, keepdims=True)
        t_median = np.median(sample_arr, axis=1, keepdims=True)
        skewness = np.array([stats.skew(sample_arr[0])]).reshape(1, -1)
        kurtosis = np.array([stats.kurtosis(sample_arr[0])]).reshape(1, -1)
        q1 = np.percentile(sample_arr, 25, axis=1, keepdims=True)
        q3 = np.percentile(sample_arr, 75, axis=1, keepdims=True)
        iqr = q3 - q1
        t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
        cv = t_std / t_bar_safe
        sample_arr = np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median, q1, q3, iqr, cv], axis=1)
    elif preprocessing == 'b1':
        n_max_val = n_max or 15
        padded = np.zeros((1, n_max_val))
        padded[0, :n] = sample_arr[0]
        mask = np.zeros((1, n_max_val))
        mask[0, :n] = 1.0
        sample_arr = np.concatenate([padded, mask], axis=1)
    elif preprocessing == 'b2':
        n_max_val = n_max or 15
        t_bar = np.mean(sample_arr, axis=1, keepdims=True)
        t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
        normalized = sample_arr / t_bar_safe
        padded = np.zeros((1, n_max_val))
        padded[0, :n] = normalized[0]
        mask = np.zeros((1, n_max_val))
        mask[0, :n] = 1.0
        sample_arr = np.concatenate([padded, t_bar, mask], axis=1)

    # 标准化输入
    if scaler_params:
        x_mean = np.array(scaler_params['x_mean'])
        x_std = np.array(scaler_params['x_std'])
        sample_arr = (sample_arr - x_mean) / x_std

    sample_tensor = torch.FloatTensor(sample_arr)

    # 推理
    with torch.no_grad():
        pred_norm = model(sample_tensor).squeeze().numpy()

    # 反归一化输出
    if y_scaler:
        y_mean = np.array(y_scaler['y_mean'])
        y_std = np.array(y_scaler['y_std'])
        pred = pred_norm * y_std + y_mean
    else:
        pred = pred_norm

    return AIDirectEstimationResponse(
        beta=round(float(pred[0]), 4),
        eta=round(float(pred[1]), 2),
        gamma=round(float(pred[2]), 2),
        model_n=n
    )
