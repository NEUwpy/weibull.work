from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
import sys
import os

# Add methods directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))

from methods.mle import MLE
from methods.lre import LRE
from methods.lse import LSE
from methods.mps import MPS
from methods.mde import MDE
from methods.mm import MM
from methods.pwm import PWM
from methods.grey_gm11 import GreyGM11
from methods.bayesian import Bayesian
from methods.wmle import WMLE

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
    trace: Optional[bool] = False # New field
    params: Optional[dict] = {}

class CalculationResponse(BaseModel):
    beta: float
    eta: float
    gamma: float
    rSquared: float 
    method: str
    trace_data: Optional[List[dict]] = None # New field

@app.post("/calculate", response_model=CalculationResponse)
async def calculate(req: CalculationRequest):
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    data = req.data
    
    # Map method IDs to Algorithm Classes
    method_map = {
        "mle": MLE, "mmle": MLE, "mps": MPS, "wmle": WMLE,
        "lse": LSE, "wlse": LSE, "mde": MDE, "eiv": LSE,
        "lre": LRE, "rrx": LRE, "rry": LRE, "blre": LRE,
        "mm": MM, "pwm": PWM, "lm": PWM, "tlm": PWM,
        "grey": GreyGM11, "gm11": GreyGM11,
        "construct_stat": WMLE, "mve": WMLE, "lsf": WMLE,
        "bayesian": Bayesian, "gibbs": Bayesian, "map": Bayesian,
        "ai": WMLE, "pso": WMLE, "svr": WMLE, "ann": WMLE,
        "default": WMLE
    }

    selected_method_id = req.method.lower()
    AlgorithmClass = method_map.get(selected_method_id, WMLE)

    try:
        # Instantiate
        algo_instance = AlgorithmClass(data)
        
        # Run with optional trace
        # Only pass 'trace' if the run method accepts it (we implemented it for Base, but check to be safe or just pass kwargs)
        # For now, we manually updated MLE and WMLE. Others inherit Base but don't use 'trace' in run yet.
        # We can inspect the method signature or just try/except
        try:
            res = algo_instance.run(trace=req.trace)
        except TypeError:
             # Fallback for methods that don't support trace arg yet
             res = algo_instance.run()
        
        return {
            "beta": float(res[0]),
            "eta": float(res[1]),
            "gamma": float(res[2]),
            "rSquared": float(res[3]),
            "method": selected_method_id,
            "trace_data": algo_instance.trace_data if req.trace else None
        }

    except NotImplementedError:
        try:
            print(f"Algorithm {selected_method_id} not implemented. Fallback to WMLE.")
            fallback_instance = WMLE(data)
            res = fallback_instance.run(trace=req.trace) # WMLE supports trace
            return {
                "beta": float(res[0]),
                "eta": float(res[1]),
                "gamma": float(res[2]),
                "rSquared": float(res[3]),
                "method": f"{selected_method_id}_fallback_wmle",
                "trace_data": fallback_instance.trace_data if req.trace else None
            }
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Fallback WMLE failed: {str(e)}")

    except Exception as e:
        try:
            print(f"Algorithm {selected_method_id} failed: {e}. Fallback to WMLE.")
            fallback_instance = WMLE(data)
            res = fallback_instance.run(trace=req.trace)
            return {
                "beta": float(res[0]),
                "eta": float(res[1]),
                "gamma": float(res[2]),
                "rSquared": float(res[3]),
                "method": f"{selected_method_id}_fallback_wmle",
                "trace_data": fallback_instance.trace_data if req.trace else None
            }
        except Exception as fallback_error:
            raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)} -> Fallback WMLE failed: {str(fallback_error)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)