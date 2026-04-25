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

class DeltaMLP(nn.Module):
    """全连接 MLP：输入样本数据，输出最优偏移量 δ"""

    def __init__(self, input_dim: int, hidden1: int = 64, hidden2: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# 模型缓存
_ai_models = {}

def _load_delta_model(n: int):
    """按样本量 n 加载对应的模型"""
    if n in _ai_models:
        return _ai_models[n]

    models_dir = os.path.join(os.path.dirname(__file__), 'models', 'mdm_delta')
    model_path = os.path.join(models_dir, f'n{n}_model.pth')

    if not os.path.exists(model_path):
        return None

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model = DeltaMLP(
        input_dim=checkpoint['input_dim'],
        hidden1=checkpoint['hidden1'],
        hidden2=checkpoint['hidden2']
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    delta_min = checkpoint.get('delta_min', 0.01)
    delta_max = checkpoint.get('delta_max', 0.50)
    scaler_params = checkpoint.get('scaler_params', None)

    _ai_models[n] = (model, delta_min, delta_max, scaler_params)
    return _ai_models[n]


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
    AI 预测 MDM 最优偏移量 δ

    输入：样本数据（排序后的失效时间）
    输出：AI 预测的最优偏移量 δ
    """
    if len(req.data) < 3:
        raise HTTPException(status_code=400, detail="样本量至少为 3")

    n = len(req.data)

    # 加载模型
    result = _load_delta_model(n)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到样本量 n={n} 的模型。当前可用模型: {list(_ai_models.keys())}"
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
