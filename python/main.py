from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
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
    params: Optional[dict] = {}

class CalculationResponse(BaseModel):
    beta: float
    eta: float
    gamma: float
    rSquared: float 
    method: str

@app.post("/calculate", response_model=CalculationResponse)
async def calculate(req: CalculationRequest):
    if len(req.data) < 2:
        raise HTTPException(status_code=400, detail="Insufficient data points")

    data = req.data
    
    # Map method IDs to Algorithm Classes
    # For aliases, we map to the same class
    method_map = {
        # Maximizing Adequacy
        "mle": MLE,
        "mmle": MLE, # Fallback/Alias
        "mps": MPS,
        "wmle": WMLE,  # Weighted MLE
        
        # Minimizing Adequacy
        "lse": LSE,
        "wlse": LSE, # Fallback
        "mde": MDE,
        "eiv": LSE, # Fallback
        
        # Linear Regression
        "lre": LRE,
        "rrx": LRE,
        "rry": LRE, 
        "blre": LRE, # Fallback
        
        # Moments
        "mm": MM,
        "pwm": PWM,
        "lm": PWM, # Fallback
        "tlm": PWM, # Fallback
        
        # Grey
        "grey": GreyGM11,
        "gm11": GreyGM11,
        
        # Constructing Stats
        "construct_stat": LRE, # Fallback
        "mve": LRE,
        "lsf": LRE,
        
        # Bayesian
        "bayesian": Bayesian,
        "gibbs": Bayesian,
        "map": Bayesian,
        
        # AI / Other
        "ai": LRE, # Fallback
        "pso": LRE,
        "svr": LRE,
        "ann": LRE,
        
        "default": LRE
    }

    selected_method_id = req.method.lower()
    AlgorithmClass = method_map.get(selected_method_id, LRE)

    try:
        # Instantiate and run
        algo_instance = AlgorithmClass(data)
        res = algo_instance.run()
        
        return {
            "beta": float(res[0]),
            "eta": float(res[1]),
            "gamma": float(res[2]),
            "rSquared": float(res[3]),
            "method": selected_method_id
        }
    except Exception as e:
        # Global fallback to LRE if specific algo fails
        try:
            print(f"Algorithm {selected_method_id} failed: {e}. Falling back to LRE.")
            fallback_instance = LRE(data)
            res = fallback_instance.run()
            return {
                "beta": float(res[0]),
                "eta": float(res[1]),
                "gamma": float(res[2]),
                "rSquared": float(res[3]),
                "method": "fallback_lre"
            }
        except Exception as fallback_error:
            raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)} -> Fallback failed: {str(fallback_error)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
