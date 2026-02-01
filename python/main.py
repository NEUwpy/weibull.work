from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any, Union
import sys
import os

# Add methods directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

from methods.mle import MLE
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
        "mle": MLE, "mmle": MLE, "mps": MPS, "wmle": WMLE,
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
