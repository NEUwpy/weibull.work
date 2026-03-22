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

from methods.mle import MLE
from methods.mmle import MMLE
from methods.lre import LRE
from methods.lse import LSE
from methods.mps import MPS
from methods.mm import MM
from methods.pwm import PWM
from methods.grey_gm11 import GreyGM11
from methods.bayesian import Bayesian
from methods.wmle import WMLE
from methods.mdm import MDM

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    converged: Union[bool, str] = True  # Support both boolean and "unbounded" string
    trace_data: Optional[Any] = None

@app.post("/calculate", response_model=CalculationResponse)
async def calculate(req: CalculationRequest):
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    data = req.data

    # Map method IDs to Algorithm Classes
    method_map = {
        "mle": MLE, "mmle": MMLE, "mps": MPS, "wmle": WMLE,
        "lse": LSE, "wlse": LSE, "mde": MDM, "eiv": LSE, # MDE aliased to MDM
        "lre": LRE, "rrx": LRE, "rry": LRE, "blre": LRE,
        "mm": MM, "pwm": PWM, "lm": PWM, "tlm": PWM,
        "grey": GreyGM11, "gm11": GreyGM11,
        "construct_stat": WMLE, "mve": WMLE, "lsf": WMLE,
        "bayesian": Bayesian, "gibbs": Bayesian, "map": Bayesian,
        "ai": WMLE, "pso": WMLE, "svr": WMLE, "ann": WMLE,
        "mdm": MDM,
        "default": WMLE
    }

    selected_method_id = req.method.lower()
    AlgorithmClass = method_map.get(selected_method_id, WMLE)

    try:
        # Instantiate
        algo_instance = AlgorithmClass(data)

        # Run with optional trace and offset (for MDM)
        try:
            # MDM supports offset parameter
            if selected_method_id == 'mdm' and req.offset is not None:
                res = algo_instance.run(trace=req.trace, offset=req.offset)
            else:
                res = algo_instance.run(trace=req.trace)
        except TypeError:
             # Fallback for methods that don't support trace arg yet
             res = algo_instance.run()

        # Handle both 4-element (old) and 5-element (new with converged) return
        if len(res) >= 5:
            converged = res[4]
        else:
            converged = True

        # Convert converged: keep string values like "unbounded", convert others to bool
        if isinstance(converged, str):
            converged_value = converged  # Keep "unbounded" as-is
        else:
            converged_value = bool(converged)  # Convert True/False/None to bool

        return {
            "beta": float(res[0]) if res[0] is not None else None,
            "eta": float(res[1]) if res[1] is not None else None,
            "gamma": float(res[2]) if res[2] is not None else None,
            "rSquared": float(res[3]) if res[3] is not None else None,
            "method": selected_method_id,
            "converged": converged_value,
            "trace_data": algo_instance.trace_data if req.trace else None
        }

    except NotImplementedError:
        try:
            print(f"Algorithm {selected_method_id} not implemented. Fallback to WMLE.")
            fallback_instance = WMLE(data)
            res = fallback_instance.run(trace=req.trace) # WMLE supports trace

            if len(res) >= 5:
                fallback_converged = res[4]
            else:
                fallback_converged = True

            if isinstance(fallback_converged, str):
                fallback_converged_value = fallback_converged
            else:
                fallback_converged_value = bool(fallback_converged)

            return {
                "beta": float(res[0]) if res[0] is not None else None,
                "eta": float(res[1]) if res[1] is not None else None,
                "gamma": float(res[2]) if res[2] is not None else None,
                "rSquared": float(res[3]) if res[3] is not None else None,
                "method": f"{selected_method_id}_fallback_wmle",
                "converged": fallback_converged_value,
                "trace_data": fallback_instance.trace_data if req.trace else None
            }
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Fallback WMLE failed: {str(e)}")

    except Exception as e:
        try:
            print(f"Algorithm {selected_method_id} failed: {e}. Fallback to WMLE.")
            fallback_instance = WMLE(data)
            res = fallback_instance.run(trace=req.trace)

            if len(res) >= 5:
                fallback_converged = res[4]
            else:
                fallback_converged = True

            if isinstance(fallback_converged, str):
                fallback_converged_value = fallback_converged
            else:
                fallback_converged_value = bool(fallback_converged)

            return {
                "beta": float(res[0]) if res[0] is not None else None,
                "eta": float(res[1]) if res[1] is not None else None,
                "gamma": float(res[2]) if res[2] is not None else None,
                "rSquared": float(res[3]) if res[3] is not None else None,
                "method": f"{selected_method_id}_fallback_wmle",
                "converged": fallback_converged_value,
                "trace_data": fallback_instance.trace_data if req.trace else None
            }
        except Exception as fallback_error:
            raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)} -> Fallback WMLE failed: {str(fallback_error)}")

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
        # Run MDM with trace to get sigma_beta_gamma
        algo_instance = MDM(req.data)
        res = algo_instance.run(trace=True, offset=0.1)

        if len(res) >= 5:
            converged = res[4]
        else:
            converged = True

        return {
            "beta": float(res[0]) if res[0] is not None else None,
            "eta": float(res[1]) if res[1] is not None else None,
            "gamma": float(res[2]) if res[2] is not None else None,
            "rSquared": float(res[3]) if res[3] is not None else None,
            "method": req.method,
            "converged": bool(converged) if not isinstance(converged, str) else converged,
            "trace_data": algo_instance.trace_data
        }

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
        method_map = {
            "mle": MLE, "mmle": MLE, "mps": MPS, "wmle": WMLE,
            "lse": LSE, "wlse": LSE, "mde": MDM, "eiv": LSE,
            "lre": LRE, "rrx": LRE, "rry": LRE, "blre": LRE,
            "mm": MM, "pwm": PWM, "lm": PWM, "tlm": PWM,
            "grey": GreyGM11, "gm11": GreyGM11,
            "construct_stat": WMLE, "mve": WMLE, "lsf": WMLE,
            "bayesian": Bayesian, "gibbs": Bayesian, "map": Bayesian,
            "ai": WMLE, "pso": WMLE, "svr": WMLE, "ann": WMLE,
            "mdm": MDM,
            "default": WMLE
        }

        selected_method_id = req.method.lower()
        AlgorithmClass = method_map.get(selected_method_id, MDM)

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
                        except Exception as e:
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
        method_map = {
            "mle": MLE, "mmle": MLE, "mps": MPS, "wmle": WMLE,
            "lse": LSE, "wlse": LSE, "mde": MDM, "eiv": LSE,
            "lre": LRE, "rrx": LRE, "rry": LRE, "blre": LRE,
            "mm": MM, "pwm": PWM, "lm": PWM, "tlm": PWM,
            "grey": GreyGM11, "gm11": GreyGM11,
            "construct_stat": WMLE, "mve": WMLE, "lsf": WMLE,
            "bayesian": Bayesian, "gibbs": Bayesian, "map": Bayesian,
            "ai": WMLE, "pso": WMLE, "svr": WMLE, "ann": WMLE,
            "mdm": MDM,
            "default": WMLE
        }

        selected_method_id = req.method.lower()
        if selected_method_id not in method_map:
            raise HTTPException(status_code=400, detail=f"不支持的方法: {req.method}。支持的方法: {', '.join(method_map.keys())}")

        AlgorithmClass = method_map[selected_method_id]

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
