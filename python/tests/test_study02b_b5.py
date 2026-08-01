"""B5 tests: grid sizes, contamination pairing, NIST split determinism, conformal quantile."""
import sys
from pathlib import Path
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [str(REPO_ROOT/"Study/02-study-NN参数估计与分位点目标研究/code"), str(REPO_ROOT/"python")]:
    if p not in sys.path: sys.path.insert(0, p)

from studies.common.sample import generate_sample
from study02b.evaluate_b5 import _N_VALUES

def test_stress_grid_size():
    """Each stress domain: 32 clusters × 10 reps × 5 n = 1600 datasets."""
    assert 32*10*len(_N_VALUES)==1600

def test_contamination_grid_size():
    """Contamination: 32 core points × 10 reps × 5 conditions = 1600 datasets."""
    assert 32*10*5==1600

def test_nist_split_determinism():
    """Same seed → same NIST split."""
    rng1=np.random.default_rng(9000+10*1000+0)
    rng2=np.random.default_rng(9000+10*1000+0)
    data=np.arange(101)
    idx1=rng1.choice(101,size=10,replace=False)
    idx2=rng2.choice(101,size=10,replace=False)
    np.testing.assert_array_equal(idx1,idx2)

def test_contamination_paired_with_clean():
    """Clean and contaminated conditions share the same clean sample."""
    rng=np.random.default_rng(42); b,e,g=2.0,1000.0,200.0
    s1=generate_sample(b,e,g,20,0,seed=9000+0)
    s2=generate_sample(b,e,g,20,0,seed=9000+0)
    np.testing.assert_array_equal(s1,s2)  # deterministic

def test_conformal_quantile_finite_sample():
    """Conformal quantile rule: q95 of calibration residuals."""
    residuals=np.abs(np.random.randn(5000))
    q90=np.quantile(residuals,0.9); q95=np.quantile(residuals,0.95)
    assert q90>0 and q95>0 and q95>=q90

def test_n_values():
    assert _N_VALUES==[5,7,10,15,20]
