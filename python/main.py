from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Union
import sys
import os
import io
import csv
import math
import numpy as np

# Add methods directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

from methods.registry import resolve_method
from methods.mdm import MDM
from studies.common.runner import run_method
from studies.common.simulation import aggregate_simulation_rows, iter_batch_rows, simulate_method

app = FastAPI()

MDM_CALCULATOR_DEFAULT_OFFSET = 0.1
MDM_CALCULATOR_MIN_OFFSET = 0.0
MDM_CALCULATOR_MAX_OFFSET = 0.5

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "https://weibull.work,http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
).split(",")

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
    offset: Optional[float] = Field(
        default=None,
        ge=MDM_CALCULATOR_MIN_OFFSET,
        le=MDM_CALCULATOR_MAX_OFFSET,
    )
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


def _calculation_kwargs(method_id: str, trace: bool = False, offset: Optional[float] = None) -> dict:
    """构建统一方法调用参数；方法签名差异由 run_method 负责过滤。"""
    kwargs = {"trace": trace}
    if method_id == "mdm":
        selected_offset = MDM_CALCULATOR_DEFAULT_OFFSET if offset is None else float(offset)
        if not math.isfinite(selected_offset):
            raise ValueError("MDM offset must be finite")
        if not MDM_CALCULATOR_MIN_OFFSET <= selected_offset <= MDM_CALCULATOR_MAX_OFFSET:
            raise ValueError(
                f"MDM offset must be between {MDM_CALCULATOR_MIN_OFFSET} "
                f"and {MDM_CALCULATOR_MAX_OFFSET}"
            )
        kwargs["offset"] = selected_offset
    return kwargs


def _calculation_response(result: dict, method_id: str) -> dict:
    """把 studies.common.runner 的标准结果转换为 API 响应。"""
    extra = result.get("extra") or {}
    converged = extra.get("raw_status") if "raw_status" in extra else result["converged"]

    return {
        "beta": float(result["beta_hat"]) if result["beta_hat"] is not None else None,
        "eta": float(result["eta_hat"]) if result["eta_hat"] is not None else None,
        "gamma": float(result["gamma_hat"]) if result["gamma_hat"] is not None else None,
        "rSquared": float(result["r_squared"]) if result["r_squared"] is not None else None,
        "method": method_id,
        "converged": converged if isinstance(converged, str) else bool(converged),
        "trace_data": result.get("trace_data"),
    }


def _run_calculation_method(method_id: str, data, trace=False, offset=None):
    """执行单次估计；失败时返回明确 HTTP 422，不回退到其他方法。"""
    result = run_method(method_id, data, **_calculation_kwargs(method_id, trace=trace, offset=offset))
    if result["beta_hat"] is not None:
        return _calculation_response(result, method_id)

    error_info = result.get("extra") or {}
    raise HTTPException(
        status_code=422,
        detail=f"Method '{method_id}' failed: {error_info}",
    )


_CSV_FLOAT_COLUMNS = {
    "est_beta", "est_eta", "est_gamma",
    "bias_beta", "bias_eta", "bias_gamma", "r_squared",
}


def _csv_cell(column: str, value):
    """保持 batch_simulation 历史 CSV 数值格式。"""
    if value is None:
        return "0" if column in _CSV_FLOAT_COLUMNS else ""
    if column in _CSV_FLOAT_COLUMNS:
        return f"{float(value):.6f}"
    return value


@app.post("/calculate", response_model=CalculationResponse)
async def calculate(req: CalculationRequest):
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    selected_method_id, _ = resolve_method(req.method)
    return _run_calculation_method(selected_method_id, req.data,
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
        return _run_calculation_method("mdm", req.data, trace=True, offset=0.1)

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
        selected_method_id, _ = resolve_method(req.method)

        # Generate CSV content
        output = io.StringIO()

        header = ["beta_true", "eta_true", "gamma_true", "sample_size"]
        if req.betas:
            header.append("beta_value")
        if req.offsets:
            header.append("offset_value")
        header.extend(["sim_id", "est_beta", "est_eta", "est_gamma", "bias_beta", "bias_eta", "bias_gamma", "r_squared"])

        writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()

        for row in iter_batch_rows(
            method_id=selected_method_id,
            true_beta=req.true_beta,
            true_eta=req.true_eta,
            true_gamma=req.true_gamma,
            sample_sizes=req.sample_sizes,
            beta_values=req.betas,
            offset_values=req.offsets,
            num_simulations=req.num_simulations,
        ):
            writer.writerow({column: _csv_cell(column, row.get(column)) for column in header})

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
        selected_method_id, _ = resolve_method(req.method)

        print(f"[MonteCarlo] 开始模拟: method={req.method}, beta={req.beta}, eta={req.eta}, gamma={req.gamma}, n={req.n}, rep={req.rep}")

        rows = simulate_method(
            method_id=selected_method_id,
            beta=req.beta,
            eta=req.eta,
            gamma=req.gamma,
            n=req.n,
            rep=req.rep,
            seed=req.seed,
            offset=req.offset,
        )

        print(f"[MonteCarlo] 完成: method={req.method}, 成功 {len(rows)}/{req.rep} 次")
        metrics = aggregate_simulation_rows(rows)
        return {"rows": rows, "count": len(rows), "metrics": metrics, "success": True}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[MonteCarlo] 错误: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Monte Carlo simulation failed: {str(e)}")

# ============================================================
# AI Methods — 过程量优化: MDM 偏移量选择
# ============================================================

import torch
import torch.nn as nn
from ai_methods.mdm_process_optimizer import (
    MDMProcessOptimizationError,
    select_mdm_offset,
)

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

class AIDeltaRequest(BaseModel):
    """MDM 过程量优化请求。"""
    data: List[float]

class AIDeltaResponse(BaseModel):
    """当前样本的离散候选偏移量预测损失曲线。"""
    model_n: int
    delta_grid: List[float]
    predicted_loss_curve: List[float]
    selected_index: int
    selected_delta: float
    selected_predicted_loss: float
    default_delta: float
    default_index: int
    default_predicted_loss: float
    model_source_commit: str
    model_sha256: str
    representation: str


@app.post("/ai/relationship/mdm", response_model=AIDeltaResponse, include_in_schema=False)
@app.post("/ai/process-optimization/mdm", response_model=AIDeltaResponse)
async def ai_predict_delta(req: AIDeltaRequest):
    """
    预测 26 个候选 MDM 偏移量的损失曲线并选择离散最低点。

    返回的是模型对当前样本的预测损失，用于候选值间比较；不是在未知
    真参数条件下可观测的真实损失。MDM 参数估计仍由 /calculate 执行。
    """
    try:
        return AIDeltaResponse(**select_mdm_offset(req.data))
    except MDMProcessOptimizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
